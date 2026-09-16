"""RAG 에이전트 라우터의 요청/응답 pydantic 스키마.

GenOS 코드서빙이 워크플로우 노드로 호출할 때의 계약(genportal-api
``service/agent/agent_service.py`` 의 ``is_code_serving`` 분기)을 따른다:
요청은 ``{"question": ..., "stream": ...}``, 응답은
``{"code": 0, "data": {"text": ..., "sourceDocuments": [...]}}``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RagAgentRequest(BaseModel):
    question: str
    stream: Optional[bool] = False
    chatId: Optional[str] = None


class EvaluationResult(BaseModel):
    score: float
    reasoning: str


class SourceDocument(BaseModel):
    pageContent: str
    metadata: Dict[str, Any]


class RagAgentResponseData(BaseModel):
    text: str
    sourceDocuments: List[SourceDocument] = []
    evaluation: EvaluationResult
    tool_call_count: int
    langfuse_manual_tracing: bool


class RagAgentResponse(BaseModel):
    code: int = 0
    data: RagAgentResponseData
