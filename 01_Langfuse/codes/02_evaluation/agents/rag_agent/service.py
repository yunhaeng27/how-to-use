"""RAG 에이전트 턴 오케스트레이션 + Langfuse 계측.

``01_langfuse_base/examples/service_decorator.py`` 와 동일하게, 각 단계 함수를
호출하는 것만으로 span 트리가 구성된다(``@observe`` 가 호출 스택을 그대로 부모-자식
관계로 반영). Langfuse 미설정 시에도 동일한 함수 호출 경로가 그대로 실행되고
(no-op 데코레이터), 응답의 ``langfuse_manual_tracing`` 값만 달라진다.
"""
from __future__ import annotations

from common.langfuse_utils import LANGFUSE_ENABLED, get_client, observe, propagate_attributes

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


async def handle_turn(payload: RagAgentRequest) -> RagAgentResponse:
    with propagate_attributes(session_id=payload.chatId, user_id=None):
        result = await _run_traced_turn(payload)

    if LANGFUSE_ENABLED:
        get_client().flush()

    return result
