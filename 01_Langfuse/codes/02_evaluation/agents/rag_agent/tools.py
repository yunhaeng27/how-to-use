"""더미 지식베이스 + tool-calling 스키마로 노출하는 검색 도구.

GenA ``common/tools/base.py`` 의 BaseTool(name/description/parameters/run/to_openai_tool)
+ resolve_refs($ref 인라인) 패턴을 이 예제 하나의 도구에 맞게 축소해 가져온다.
세션/States 의존은 없다 — 이 예제는 단일 도구·단일 턴이라 필요 없다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

_KNOWLEDGE_BASE: List[Dict[str, Any]] = [
    {
        "doc_id": "doc-001",
        "title": "GenOS 서빙 배포 가이드",
        "text": "GenOS 서빙은 serving_id 로 식별되는 게이트웨이 엔드포인트를 통해 OpenAI 호환 API를 노출한다.",
        "score": 0.92,
    },
    {
        "doc_id": "doc-002",
        "title": "Tool Calling 사용법",
        "text": "모델 응답의 tool_calls 필드를 확인해 함수를 실행하고, 결과를 role=tool 메시지로 대화에 추가하면 된다.",
        "score": 0.88,
    },
    {
        "doc_id": "doc-003",
        "title": "Langfuse 평가(evaluation) 가이드",
        "text": "생성된 답변은 LLM judge 로 groundedness 를 채점하고, score_current_trace 로 trace 에 점수를 남긴다.",
        "score": 0.83,
    },
    {
        "doc_id": "doc-004",
        "title": "no-reasoning 모델 호출",
        "text": "reasoning.enabled 를 false 로 보내면 사고 과정 없이 바로 답변을 생성하도록 모델에 지시할 수 있다.",
        "score": 0.71,
    },
]


def resolve_refs(schema: Any, defs: Optional[Dict[str, Any]] = None) -> Any:
    """JSON Schema 내 $ref 를 재귀적으로 인라인 전개한다 (GenA common/tools/base.py 동일 로직)."""
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


class SearchDocumentsParams(BaseModel):
    query: str = Field(description="검색할 질문 또는 키워드")
    top_k: int = Field(default=3, ge=1, le=10, description="반환할 문서 개수")


class SearchDocumentsTool(BaseTool):
    name = "search_documents"
    description = "더미 지식베이스에서 질문과 관련된 문서를 검색합니다."
    parameters = SearchDocumentsParams

    def run(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        ranked = sorted(_KNOWLEDGE_BASE, key=lambda d: d["score"], reverse=True)
        return ranked[:top_k]


def get_documents_by_ids(doc_ids: List[str]) -> List[Dict[str, Any]]:
    """evaluator가 groundedness 채점 시 문서 원문을 함께 보여주기 위해 doc_id로 조회한다."""
    by_id = {doc["doc_id"]: doc for doc in _KNOWLEDGE_BASE}
    return [by_id[doc_id] for doc_id in doc_ids if doc_id in by_id]
