"""tool-calling 마스터 에이전트 루프.

``02_langfuse_evaluation/src/agents/rag_agent/agent.py`` 와 동일한 최소 루프(LLM 호출 ->
tool_calls 있으면 dispatch 후 재호출 -> 없으면 그 content 가 최종 답)를 쓰되, 도구가 로컬 로직이
아니라 GenOS 코드서빙으로 배포된 02 RAG 서브에이전트를 HTTP 로 호출한다는 점이 다르다.

이 예제(langfuse propagation)의 핵심은 ``_execute_tool`` 이다: ``@observe(as_type="tool")`` 가
연 이 함수 자신의 관측(tool span)에서 trace_id/observation_id 를 읽어 그대로 서브에이전트 호출
body 에 실어 보낸다. 그러면 서브에이전트 쪽 trace 가 별도 trace 로 뜨지 않고, 이 tool span 의
자식으로 같은 trace 트리에 이어 붙는다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from common.genos_client import call_genos_chat
from common.langfuse_utils import get_client, observe

from .tools import DelegateToRagSubagentTool

MAX_TOOL_ITERATIONS = 4

SYSTEM_PROMPT = (
    "당신은 사내 헬프데스크 마스터 에이전트입니다. GenOS 플랫폼(코드서빙 배포, tool calling, "
    "Langfuse 연동/평가 등)에 대한 질문이 들어오면 직접 답하지 말고 반드시 ask_internal_rag_agent "
    "도구로 사내 지식베이스 전문 서브에이전트에게 위임한 뒤, 그 답변을 근거로 최종 답을 정리하세요. "
    "그 외 GenOS 와 무관한 일반 질문은 도구 없이 직접 답하세요."
)

_TOOL = DelegateToRagSubagentTool()


@dataclass
class AgentResult:
    answer: str
    delegated: bool = False
    sub_agent_calls: List[Dict[str, Any]] = field(default_factory=list)


@observe(as_type="generation", name="llm-call")
def _call_model_step(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    response = call_genos_chat(messages=messages, tools=[_TOOL.to_openai_tool()])
    message = response["choices"][0]["message"]
    get_client().update_current_generation(
        model=response.get("model"),
        usage_details=response.get("usage") or {},
    )
    return message


@observe(as_type="tool", name="ask_internal_rag_agent")
def _execute_tool(instruction: str) -> Dict[str, Any]:
    client = get_client()
    result = _TOOL.run(
        instruction=instruction,
        trace_id=client.get_current_trace_id(),
        parent_span_id=client.get_current_observation_id(),
    )
    client.update_current_span(output=result.get("text"))
    return result


@observe(as_type="agent", name="agent-loop")
async def run_agent(query: str, history: List[Dict[str, str]] | None = None) -> AgentResult:
    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history or []:
        messages.append({"role": "user", "content": turn["question"]})
        messages.append({"role": "assistant", "content": turn["answer"]})
    messages.append({"role": "user", "content": query})

    sub_agent_calls: List[Dict[str, Any]] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        message = _call_model_step(messages)
        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            return AgentResult(
                answer=message.get("content") or "",
                delegated=bool(sub_agent_calls),
                sub_agent_calls=sub_agent_calls,
            )

        for call in tool_calls:
            args = json.loads(call["function"]["arguments"] or "{}")
            instruction = args["instruction"]
            result = _execute_tool(instruction)
            sub_agent_calls.append({"instruction": instruction, **result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    raise RuntimeError(f"{MAX_TOOL_ITERATIONS}회 반복 내에 최종 답변을 얻지 못했습니다.")
