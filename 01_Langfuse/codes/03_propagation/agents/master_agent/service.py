"""마스터 에이전트 턴 오케스트레이션 + Langfuse 계측.

``02_langfuse_evaluation/src/agents/rag_agent/service.py`` 와 동일한 trace_id/parent_span_id
검증·이어붙이기 로직을 그대로 따른다 — 이 마스터 에이전트 자체도 상위(예: 이 예제를 다시 감싸는
또 다른 워크플로우)에서 body 로 trace 연결 정보를 받으면 그 trace 를 이어서 쓴다.

여기에 더해 이 턴 내부에서 ``agent.py::_execute_tool`` 이 자신의 trace_id/observation_id 를 02
서브에이전트 호출에 실어 보내 trace 를 한 단계 더 전파한다. 그래서 최종적으로 Langfuse 에는
(상위 trace 가 있었다면 그 trace 안에) ``master-agent-turn -> agent-loop ->
ask_internal_rag_agent(tool) -> rag-agent-turn(02) -> ...`` 이 하나의 trace 트리로 남는다.

``router.py`` 가 읽어 넘긴 ``x-genos-session-id`` 값은 여기서 두 가지로 쓰인다: (1)
``propagate_attributes(session_id=...)`` 로 이 trace(및 자식 span들)에 Langfuse 의 session_id
로 태깅하고, (2) ``memory`` 모듈의 세션별 대화 기록을 읽고/쌓는 키로 사용해 같은 세션의 다음 턴에
이전 질문·답변을 이어서 참고할 수 있게 한다.
"""
from __future__ import annotations

import logging
import re

from common.langfuse_utils import LANGFUSE_ENABLED, get_client, observe, propagate_attributes

from . import memory
from .agent import run_agent
from .schema import MasterAgentRequest, MasterAgentResponse, MasterAgentResponseData, SubAgentCall

logger = logging.getLogger(__name__)

# Langfuse(OTel) trace_id는 32자, span_id(observation_id)는 16자 소문자 16진수여야 한다.
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


@observe(as_type="span", name="master-agent-turn")
async def _run_traced_turn(
    payload: MasterAgentRequest, session_id: str | None = None
) -> MasterAgentResponse:
    history = memory.get_history(session_id)

    # "현재 활성 span"(=@observe 가 방금 연 이 함수의 루트 span)에 session_id 를 바로 태깅하고,
    # 이후 생성되는 자식 span(agent-loop/llm-call/tool)에도 전파한다 — run_agent 호출만 감싸면 충분
    # (Langfuse SDK: propagate_attributes 는 with 진입 시점에 곧바로 span.set_attribute 를 호출).
    with propagate_attributes(session_id=session_id):
        agent_result = await run_agent(payload.question, history=history)

    memory.append_turn(session_id, payload.question, agent_result.answer)

    client = get_client()
    client.update_current_span(output=agent_result.answer)

    return MasterAgentResponse(
        data=MasterAgentResponseData(
            text=agent_result.answer,
            delegated=agent_result.delegated,
            sub_agent_calls=[SubAgentCall(**call) for call in agent_result.sub_agent_calls],
            langfuse_manual_tracing=LANGFUSE_ENABLED,
            trace_id=client.get_current_trace_id() if LANGFUSE_ENABLED else None,
            session_id=session_id,
        )
    )


async def handle_turn(payload: MasterAgentRequest, session_id: str | None = None) -> MasterAgentResponse:
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
