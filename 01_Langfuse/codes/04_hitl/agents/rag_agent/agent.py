"""tool-calling RAG 에이전트 루프 + HITL(사람 개입) 확장.

GenA ``research/agents/main.py`` 의 루프 뼈대(LLM 호출 -> tool_calls 있으면 dispatch
후 재호출 -> 없으면 그 content가 최종 답)를 세션/SSE/계획수립 없이 최소한으로 가져온다.

HITL 데모: ``search_documents`` 도구가 처음 실행되면 바로 답을 만들지 않고, 검색된
문서 중 어떤 것을 근거로 쓸지 사용자에게 single-select로 물어보고 멈춘다
(``AgentPaused``). 사용자의 선택은 ``resume_agent`` 로 되돌아와 그 문서들로만 근거를
좁혀 답변을 이어서 만든다. 재개 이후 또 tool_calls가 나와도 다시 멈추지 않는다 —
대화당 HITL 게이트는 1회로 한정한다(데모 범위 단순화).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Union
from uuid import uuid4

from common.genos_client import call_genos_chat
from common.langfuse_utils import get_client, observe

from .schema import HumanInputValues
from .tools import SearchDocumentsTool, get_documents_by_ids

MAX_TOOL_ITERATIONS = 4

SYSTEM_PROMPT = (
    "당신은 사내 지식베이스 문서를 검색해 답하는 어시스턴트입니다. "
    "질문에 답하기 전에 반드시 search_documents 도구로 관련 문서를 검색하고, "
    "검색된 문서 내용에 근거해서만 답변하세요."
)

_TOOL = SearchDocumentsTool()


@dataclass
class AgentResult:
    answer: str
    retrieved_documents: List[str] = field(default_factory=list)
    tool_call_count: int = 0


@dataclass
class PendingInteraction:
    """HITL 대기 중 재개에 필요한 실행 컨텍스트(문서 §3의 "자체적으로 기억해둬야" 하는 상태)."""

    interaction_id: str
    query: str
    messages: List[Dict[str, Any]]
    retrieved_documents: List[str]
    tool_call_count: int
    offered_doc_ids: List[str]


@dataclass
class AgentPaused:
    pending: PendingInteraction
    title: str
    options: List[Dict[str, str]]


AgentOutcome = Union[AgentResult, AgentPaused]


@observe(as_type="generation", name="llm-call")
def _call_model_step(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    response = call_genos_chat(messages=messages, tools=[_TOOL.to_openai_tool()])
    message = response["choices"][0]["message"]
    get_client().update_current_generation(
        model=response.get("model"),
        usage_details=response.get("usage") or {},
    )
    return message


@observe(as_type="tool", name="search_documents")
def _execute_tool(args: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _TOOL.run(**args)


def _run_tool_calls(
    tool_calls: List[Dict[str, Any]],
    messages: List[Dict[str, Any]],
    retrieved_documents: List[str],
) -> int:
    executed = 0
    for call in tool_calls:
        args = json.loads(call["function"]["arguments"] or "{}")
        result = _execute_tool(args)
        executed += 1
        retrieved_documents.extend(doc["doc_id"] for doc in result)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False),
            }
        )
    return executed


def _finish_loop(
    messages: List[Dict[str, Any]],
    retrieved_documents: List[str],
    tool_call_count: int,
) -> AgentResult:
    # 재개 이후에는 새로 MAX_TOOL_ITERATIONS 만큼 여유를 준다(데모 단순화 — 일시정지 전
    # 소모한 반복 횟수를 깎지 않는다).
    for _ in range(MAX_TOOL_ITERATIONS):
        message = _call_model_step(messages)
        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            return AgentResult(
                answer=message.get("content") or "",
                retrieved_documents=retrieved_documents,
                tool_call_count=tool_call_count,
            )

        tool_call_count += _run_tool_calls(tool_calls, messages, retrieved_documents)

    raise RuntimeError(f"{MAX_TOOL_ITERATIONS}회 반복 내에 최종 답변을 얻지 못했습니다.")


@observe(as_type="agent", name="agent-loop")
async def run_agent(query: str) -> AgentOutcome:
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]
    retrieved_documents: List[str] = []
    tool_call_count = 0

    for _ in range(MAX_TOOL_ITERATIONS):
        message = _call_model_step(messages)
        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            return AgentResult(
                answer=message.get("content") or "",
                retrieved_documents=retrieved_documents,
                tool_call_count=tool_call_count,
            )

        tool_call_count += _run_tool_calls(tool_calls, messages, retrieved_documents)

        # 첫 tool 실행 결과가 생기자마자 최종 답변으로 넘어가지 않고, 어떤 문서를 근거로
        # 쓸지 사용자에게 확인받기 위해 멈춘다.
        offered_doc_ids = list(dict.fromkeys(retrieved_documents))
        docs = get_documents_by_ids(offered_doc_ids)
        pending = PendingInteraction(
            interaction_id=str(uuid4()),
            query=query,
            messages=messages,
            retrieved_documents=retrieved_documents,
            tool_call_count=tool_call_count,
            offered_doc_ids=offered_doc_ids,
        )
        options = [
            {"value": doc["doc_id"], "label": doc["title"], "desc": doc["text"][:80]}
            for doc in docs
        ]
        return AgentPaused(
            pending=pending,
            title="답변의 근거로 사용할 문서를 선택해 주세요.",
            options=options,
        )

    raise RuntimeError(f"{MAX_TOOL_ITERATIONS}회 반복 내에 최종 답변을 얻지 못했습니다.")


@observe(as_type="agent", name="agent-loop-resume")
async def resume_agent(
    pending: PendingInteraction, action: str, values: HumanInputValues
) -> AgentResult:
    if action == "cancel":
        return AgentResult(
            answer="사용자가 문서 선택을 취소하여 답변 생성을 중단했습니다.",
            retrieved_documents=pending.retrieved_documents,
            tool_call_count=pending.tool_call_count,
        )

    selected = [doc_id for doc_id in values.selected if doc_id in pending.offered_doc_ids]
    selected = selected or pending.offered_doc_ids  # 선택이 비었거나 전부 무효면 원래 후보 그대로 사용

    messages = list(pending.messages)
    filtered_docs = get_documents_by_ids(selected)
    for entry in reversed(messages):
        if entry.get("role") == "tool":
            entry["content"] = json.dumps(filtered_docs, ensure_ascii=False)
            break

    return _finish_loop(messages, list(selected), pending.tool_call_count)
