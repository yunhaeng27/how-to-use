"""마스터 에이전트가 사용하는 도구 정의.

``02_langfuse_evaluation/src/agents/rag_agent/tools.py`` 의 BaseTool(name/description/
parameters/run/to_openai_tool) + resolve_refs 패턴을 그대로 가져와, 이 예제의 유일한 도구
``ask_internal_rag_agent`` 하나에 맞춘다.

LLM 이 만드는 건 ``instruction`` 하나뿐이다 — trace 전파 정보는 LLM 의 tool call 스키마에
노출하지 않고, ``agent.py::_execute_tool`` 이 자신의 현재 관측(tool span) 에서 trace_id/
observation_id 를 읽어 표준 W3C ``traceparent`` 문자열로 조립한 뒤 ``run()`` 호출 시 별도
인자로 주입한다 — 서브에이전트(02) 호출은 더 이상 body 로 trace_id/parent_span_id 를
싣지 않고 이 헤더 하나로만 trace 를 이어 붙인다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, Field

from common.subagent_client import call_rag_subagent


def resolve_refs(schema: Any, defs: Optional[Dict[str, Any]] = None) -> Any:
    """JSON Schema 내 $ref 를 재귀적으로 인라인 전개한다 (02_langfuse_evaluation/tools.py 동일 로직)."""
    if defs is None:
        defs = schema.get("$defs") or schema.get("definitions") or {}
    if isinstance(schema, dict):
        if "$ref" in schema:
            name = schema["$ref"].split("/")[-1]
            if name in defs:
                return resolve_refs(defs[name], defs)
        return {k: resolve_refs(v, defs) for k, v in schema.items() if k not in ("$defs", "definitions")}
    if isinstance(schema, list):
        return [resolve_refs(item, defs) for item in schema]
    return schema


class BaseTool(ABC):
    name: str
    description: str
    parameters: Type[BaseModel]

    @abstractmethod
    def run(self, **kwargs: Any) -> Any:
        """도구 실행 로직."""

    def to_openai_tool(self) -> Dict[str, Any]:
        schema = self.parameters.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": resolve_refs(schema),
            },
        }


class DelegateToRagSubagentParams(BaseModel):
    instruction: str = Field(
        description=(
            "GenOS 사내 지식베이스 RAG 서브에이전트에게 전달할, 검색과 답변 생성을 위한 명확한 "
            "질문 형태의 지시사항. 사용자의 원 질문을 그대로 넘기지 말고, 검색에 유리하도록 핵심 "
            "키워드를 포함해 한 문장으로 다듬어서 전달한다."
        )
    )


class DelegateToRagSubagentTool(BaseTool):
    name = "ask_internal_rag_agent"
    description = (
        "GenOS 플랫폼(코드서빙 배포, tool calling, Langfuse 연동/평가)에 대한 사내 문서 기반 "
        "질문에 답하는 전문 서브에이전트를 호출한다. 서브에이전트는 사내 지식베이스를 검색해 "
        "근거 문서와 함께 답변하고, 그 답변의 groundedness 를 LLM judge 로 채점한 점수도 함께 "
        "돌려준다. GenOS 내부 동작에 대한 질문이면 직접 답하지 말고 반드시 이 도구를 사용한다."
    )
    parameters = DelegateToRagSubagentParams

    def run(
        self,
        instruction: str,
        *,
        traceparent: Optional[str] = None,
    ) -> Dict[str, Any]:
        return call_rag_subagent(instruction=instruction, traceparent=traceparent)
