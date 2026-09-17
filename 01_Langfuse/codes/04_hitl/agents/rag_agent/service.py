"""RAG 에이전트 턴 오케스트레이션 + Langfuse 계측 + HITL 재개.

``01_langfuse_base/examples/service_decorator.py`` 와 동일하게, 각 단계 함수를
호출하는 것만으로 span 트리가 구성된다(``@observe`` 가 호출 스택을 그대로 부모-자식
관계로 반영). Langfuse 미설정 시에도 동일한 함수 호출 경로가 그대로 실행되고
(no-op 데코레이터), 응답의 ``langfuse_manual_tracing`` 값만 달라진다.

HITL 흐름은 이 코드서빙 앱이 전적으로 책임진다: 대기 상태는 상관키(A2A는
``chatId``, 채팅/워크플로우 표면은 ``router.py`` 가 읽어 넘긴 ``x-genos-session-id``
헤더 값 — ``RagAgentRequest.correlation_key`` 참고)를 키로 ``hitl_store`` 에
저장하고, 다음 요청의 ``humanInput.interactionId`` 가 일치할 때만(그리고 한 번만)
재개한다.

``router.py`` 가 읽어 넘긴 ``x-genos-session-id`` 값은 ``03_langfuse_propagation``
의 ``master_agent`` 와 동일하게 ``propagate_attributes(session_id=...)`` 로 이
turn의 trace(및 자식 span들)에 Langfuse session_id로도 태깅한다.
"""
from __future__ import annotations

import logging
import re

from fastapi import HTTPException

from common.langfuse_utils import LANGFUSE_ENABLED, get_client, observe, propagate_attributes

from . import hitl_store
from .agent import AgentOutcome, AgentPaused, AgentResult, resume_agent, run_agent
from .evaluator import evaluate_groundedness
from .schema import (
    ActionComponent,
    ActionComponentOption,
    ActionElement,
    ChatEvent,
    EvaluationResult,
    HumanInputValues,
    RagAgentRequest,
    RagAgentResponse,
    RagAgentResponseData,
    SourceDocument,
)
from .tools import get_documents_by_ids

logger = logging.getLogger(__name__)

# Langfuse(OTel) trace_id는 32자, span_id(observation_id)는 16자 소문자 16진수여야 한다.
# 형식이 어긋난 값을 그대로 넘기면 langfuse SDK 내부의 int(value, 16) 변환에서 예외가 날 수
# 있으므로, 외부(HTTP body)에서 들어온 값은 반드시 여기서 먼저 검증한다.
_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_SPAN_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")


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


def _build_hitl_response(outcome: AgentPaused) -> RagAgentResponse:
    """검색 문서 선택을 요청하는 HITL 응답. 채팅 표면과 A2A 표면이 각자 읽는 필드를
    한 응답에 함께 싣는다(§7.2 "권장 응답 바디 (양쪽 겸용)")."""
    interaction_id = outcome.pending.interaction_id
    component = ActionComponent(
        type="single-select",
        title=outcome.title,
        options=[ActionComponentOption(**opt) for opt in outcome.options],
    )
    element = ActionElement(interactionId=interaction_id, component=component)
    return RagAgentResponse(
        data=RagAgentResponseData(
            text=outcome.title,
            # 채팅(워크플로우) 표면: SSE `action` 이벤트로 그대로 재생된다.
            messages=[ChatEvent(event="action", data={"elements": [element.model_dump()]})],
            # A2A 표면: `_normalize_workflow_result` 가 직접 읽는다.
            a2a_status="input-required",
            interactionId=interaction_id,
            component=component,
        )
    )


async def _finalize(query: str, result: AgentResult) -> RagAgentResponse:
    eval_result = await evaluate_groundedness(query, result.retrieved_documents, result.answer)

    get_client().score_current_trace(
        name="groundedness",
        value=eval_result["score"],
        comment=eval_result["reasoning"],
    )
    get_client().update_current_span(output=result.answer)

    documents = get_documents_by_ids(list(dict.fromkeys(result.retrieved_documents)))
    source_documents = [
        SourceDocument(pageContent=doc["text"], metadata={"doc_id": doc["doc_id"], "title": doc["title"]})
        for doc in documents
    ]

    return RagAgentResponse(
        data=RagAgentResponseData(
            text=result.answer,
            sourceDocuments=source_documents,
            evaluation=EvaluationResult(**eval_result),
            tool_call_count=result.tool_call_count,
            langfuse_manual_tracing=LANGFUSE_ENABLED,
        )
    )


async def _start_turn(payload: RagAgentRequest, session_id: str | None) -> RagAgentResponse:
    question = payload.effective_question()
    outcome: AgentOutcome = await run_agent(question)
    if isinstance(outcome, AgentPaused):
        chat_id = payload.correlation_key(session_id)
        if not chat_id:
            # chatId(A2A)/x-genos-session-id(채팅 표면) 가 둘 다 없으면 대기 상태를 저장/조회할
            # 키가 없다. GenOS 워크플로우 등록 시의 엔드포인트 연결 테스트처럼 상관키 없이
            # 단발성으로 호출되는 경우가 여기 해당하므로, 에러로 끊지 않고 HITL 확인 단계를
            # 건너뛴 채 검색된 문서 전체를 근거로 바로 답변을 완성한다(선택 없이 진행하는 것과
            # 동일하게 처리).
            logger.info("chatId/session_id 없는 요청 — HITL 확인을 건너뛰고 검색 결과 전체로 바로 완료합니다.")
            values = HumanInputValues(selected=list(outcome.pending.offered_doc_ids))
            result = await resume_agent(outcome.pending, "submit", values)
            return await _finalize(question, result)
        hitl_store.store(chat_id, outcome.pending)
        return _build_hitl_response(outcome)
    return await _finalize(question, outcome)


async def _resume_turn(payload: RagAgentRequest, session_id: str | None) -> RagAgentResponse:
    human_input = payload.humanInput
    assert human_input is not None
    chat_id = payload.correlation_key(session_id)
    if not chat_id:
        raise HTTPException(
            status_code=400,
            detail="HITL 재개에는 대기 상태를 저장할 때 쓴 chatId 또는 x-genos-session-id 헤더가 필요합니다.",
        )

    pending = hitl_store.pop(chat_id)  # 조회 즉시 제거 — single-use 강제
    if pending is None or pending.interaction_id != human_input.interactionId:
        raise HTTPException(
            status_code=409,
            detail="알 수 없거나 이미 소비된 interactionId 입니다.",
        )

    result = await resume_agent(pending, human_input.action, human_input.values)

    if human_input.action == "cancel":
        # 취소 시에는 groundedness 평가를 돌릴 실제 답변이 없으므로 그대로 반환한다.
        return RagAgentResponse(
            data=RagAgentResponseData(
                text=result.answer,
                sourceDocuments=[],
                tool_call_count=result.tool_call_count,
                langfuse_manual_tracing=LANGFUSE_ENABLED,
            )
        )

    return await _finalize(pending.query, result)


@observe(as_type="span", name="rag-agent-turn")
async def _run_traced_turn(payload: RagAgentRequest, session_id: str | None = None) -> RagAgentResponse:
    # "현재 활성 span"(=@observe 가 방금 연 이 함수의 루트 span)에 session_id 를 바로 태깅하고,
    # 이후 생성되는 자식 span(agent-loop/llm-call/tool)에도 전파한다(master_agent/service.py 와 동일).
    with propagate_attributes(session_id=session_id):
        if payload.humanInput is not None:
            return await _resume_turn(payload, session_id)
        return await _start_turn(payload, session_id)


async def handle_turn(payload: RagAgentRequest, session_id: str | None = None) -> RagAgentResponse:
    # 워크플로우 API(/run/v2)를 직접 호출하는 쪽이 body에 trace_id/parent_span_id를 실어 보내면
    # 그 trace의 그 span 아래로 이어 붙인다. 값이 없거나 형식이 잘못됐으면(예: 미전달, 길이 오류)
    # langfuse_trace_id kwarg 자체를 넘기지 않아 @observe가 새 trace를 발급하는 기본 동작으로
    # 안전하게 폴백한다 — 이 경로에서 예외가 나서 요청이 실패하는 일은 없다.
    trace_id = _validated_trace_id(payload.trace_id) if LANGFUSE_ENABLED else None

    if trace_id:
        kwargs = {"langfuse_trace_id": trace_id}
        parent_span_id = _validated_parent_span_id(payload.parent_span_id)
        if parent_span_id:
            kwargs["langfuse_parent_observation_id"] = parent_span_id
        result = await _run_traced_turn(payload, session_id=session_id, **kwargs)
    else:
        result = await _run_traced_turn(payload, session_id=session_id)

    if LANGFUSE_ENABLED:
        get_client().flush()

    return result
