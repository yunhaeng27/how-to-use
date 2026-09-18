"""RAG 에이전트 턴 오케스트레이션 + Langfuse 계측.

``01_langfuse_base/examples/service_decorator.py`` 와 동일하게, 각 단계 함수를
호출하는 것만으로 span 트리가 구성된다(``@observe`` 가 호출 스택을 그대로 부모-자식
관계로 반영). Langfuse 미설정 시에도 동일한 함수 호출 경로가 그대로 실행되고
(no-op 데코레이터), 응답의 ``langfuse_manual_tracing`` 값만 달라진다.
"""
from __future__ import annotations

import logging
import re

from common.langfuse_utils import LANGFUSE_ENABLED, get_client, observe

from .agent import run_agent
from .evaluator import evaluate_groundedness
from .schema import (
    EvaluationResult,
    RagAgentRequest,
    RagAgentResponse,
    RagAgentResponseData,
    SourceDocument,
)
from .tools import get_documents_by_ids

logger = logging.getLogger(__name__)

# Langfuse(OTel) trace_id는 32자, span_id(observation_id)는 16자 소문자 16진수여야 한다.
# 형식이 어긋난 값을 그대로 넘기면 langfuse SDK 내부의 int(value, 16) 변환에서 예외가 날 수
# 있으므로, 외부(HTTP 헤더)에서 들어온 값은 반드시 여기서 먼저 검증한다.
_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_SPAN_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")
# W3C traceparent: "<version>-<trace-id 32hex>-<parent-id 16hex>-<flags>" (RFC 형식 그대로).
_TRACEPARENT_PATTERN = re.compile(r"^[0-9a-f]{2}-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$")


def _validated_trace_id(value: str | None) -> str | None:
    """형식이 맞으면 그대로, 없거나 형식이 틀리면 None(→ 새 trace로 폴백)."""
    if not value:
        return None
    if not _TRACE_ID_PATTERN.fullmatch(value):
        logger.warning("무시된 trace_id — 32자 소문자 16진수가 아님: %r", value)
        return None
    return value


def _validated_parent_span_id(value: str | None) -> str | None:
    """형식이 맞으면 그대로, 없거나 형식이 틀리면 None(→ trace 안에서 부모 없이 시작)."""
    if not value:
        return None
    if not _SPAN_ID_PATTERN.fullmatch(value):
        logger.warning("무시된 parent_span_id — 16자 소문자 16진수가 아님: %r", value)
        return None
    return value


def _parsed_traceparent(value: str | None) -> tuple[str | None, str | None]:
    """W3C ``traceparent`` 헤더에서 trace_id/parent_span_id 를 뽑아낸다.

    상위 호출자(03 master agent 의 ``ask_internal_rag_agent`` 도구 호출 등)가 이 표준 헤더로
    trace 를 전파하면 그 trace_id/parent_span_id 아래로 이어 붙인다 — 더 이상 body 로는
    받지 않는다.
    """
    if not value:
        return None, None
    match = _TRACEPARENT_PATTERN.fullmatch(value.strip())
    if not match:
        return None, None
    trace_id, parent_span_id = match.groups()
    if trace_id == "0" * 32 or parent_span_id == "0" * 16:
        return None, None
    return trace_id, parent_span_id


@observe(as_type="span", name="rag-agent-turn")
async def _run_traced_turn(payload: RagAgentRequest) -> RagAgentResponse:
    agent_result = await run_agent(payload.question)
    eval_result = await evaluate_groundedness(
        payload.question, agent_result.retrieved_documents, agent_result.answer
    )

    get_client().score_current_trace(
        name="groundedness",
        value=eval_result["score"],
        comment=eval_result["reasoning"],
    )
    get_client().update_current_span(output=agent_result.answer)

    documents = get_documents_by_ids(list(dict.fromkeys(agent_result.retrieved_documents)))
    source_documents = [
        SourceDocument(pageContent=doc["text"], metadata={"doc_id": doc["doc_id"], "title": doc["title"]})
        for doc in documents
    ]

    return RagAgentResponse(
        data=RagAgentResponseData(
            text=agent_result.answer,
            sourceDocuments=source_documents,
            evaluation=EvaluationResult(**eval_result),
            tool_call_count=agent_result.tool_call_count,
            langfuse_manual_tracing=LANGFUSE_ENABLED,
        )
    )


async def handle_turn(payload: RagAgentRequest, traceparent: str | None = None) -> RagAgentResponse:
    # 상위 호출자가 표준 W3C traceparent 로 trace 를 실어 보내면 그 trace 의 그 span 아래로 이어
    # 붙인다. 값이 없거나 형식이 잘못됐으면(예: 미전달, 길이 오류) langfuse_trace_id kwarg 자체를
    # 넘기지 않아 @observe가 새 trace를 발급하는 기본 동작으로 안전하게 폴백한다 — 이 경로에서
    # 예외가 나서 요청이 실패하는 일은 없다.
    trace_id = None
    parent_span_id = None
    if LANGFUSE_ENABLED:
        traceparent_trace_id, traceparent_parent_span_id = _parsed_traceparent(traceparent)
        trace_id = _validated_trace_id(traceparent_trace_id)
        if trace_id:
            parent_span_id = _validated_parent_span_id(traceparent_parent_span_id)

    if trace_id:
        kwargs = {"langfuse_trace_id": trace_id}
        if parent_span_id:
            kwargs["langfuse_parent_observation_id"] = parent_span_id
        result = await _run_traced_turn(payload, **kwargs)
    else:
        result = await _run_traced_turn(payload)

    if LANGFUSE_ENABLED:
        get_client().flush()

    return result
