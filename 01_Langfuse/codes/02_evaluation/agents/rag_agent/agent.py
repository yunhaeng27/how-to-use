"""tool-calling RAG 에이전트 루프.

GenA ``research/agents/main.py`` 의 루프 뼈대(LLM 호출 -> tool_calls 있으면 dispatch
후 재호출 -> 없으면 그 content가 최종 답)를 세션/SSE/계획수립 없이 최소한으로 가져온다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from common.genos_client import call_genos_chat
from common.langfuse_utils import get_client, observe

from .tools import SearchDocumentsTool

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


@observe(as_type="agent", name="agent-loop")
async def run_agent(query: str) -> AgentResult:
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

        for call in tool_calls:
            args = json.loads(call["function"]["arguments"] or "{}")
            result = _execute_tool(args)
            tool_call_count += 1
            retrieved_documents.extend(doc["doc_id"] for doc in result)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    raise RuntimeError(f"{MAX_TOOL_ITERATIONS}회 반복 내에 최종 답변을 얻지 못했습니다.")
