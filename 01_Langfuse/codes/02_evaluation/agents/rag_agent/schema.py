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
    # 워크플로우 API(/run/v2) 직접 호출 시 body에 실어 보내는 Langfuse trace 연결 정보.
    # A2A 경유 호출은 이 필드를 실어 보낼 방법이 없으므로 항상 비어 있을 수 있다 — service.py가
    # 없거나 형식이 잘못된 값을 안전하게 무시하고 폴백한다.
    trace_id: Optional[str] = None
    parent_span_id: Optional[str] = None


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
