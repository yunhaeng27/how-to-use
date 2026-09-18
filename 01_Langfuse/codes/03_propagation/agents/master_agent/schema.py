"""마스터 에이전트 라우터의 요청/응답 pydantic 스키마.

``02_langfuse_evaluation`` 과 동일하게 GenOS 코드서빙이 워크플로우 노드로 호출할 때의 계약을
따른다: 요청은 ``{"question": ..., "stream": ...}``, 응답은 ``{"code": 0, "data": {...}}``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class MasterAgentRequest(BaseModel):
    question: str
    stream: Optional[bool] = False
    chatId: Optional[str] = None


class SubAgentCall(BaseModel):
    instruction: str
    text: str
    sourceDocuments: List[Dict[str, Any]] = []
    evaluation: Optional[Dict[str, Any]] = None
    tool_call_count: int = 0


class MasterAgentResponseData(BaseModel):
    text: str
    delegated: bool
    sub_agent_calls: List[SubAgentCall] = []
    langfuse_manual_tracing: bool
    trace_id: Optional[str] = None
    session_id: Optional[str] = None


class MasterAgentResponse(BaseModel):
    code: int = 0
    data: MasterAgentResponseData
