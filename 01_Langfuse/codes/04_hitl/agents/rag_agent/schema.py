"""RAG 에이전트 라우터의 요청/응답 pydantic 스키마.

GenOS 코드서빙이 워크플로우 노드로 호출할 때의 계약(genportal-api
``service/agent/agent_service.py`` 의 ``is_code_serving`` 분기)을 따른다.
호출 경로에 따라 바디 모양이 다르다:

- A2A 표면(``admin-api a2a_code_serving_exec.py``): ``{"question", "chatId", ...}``
- 채팅(워크플로우) 표면(``/chat`` 이 실제로 타는 현재 경로): 바디는 ``{"question",
  "stream", "humanInput"?}`` 뿐이다. ``run_id``/``context_id``/``messages`` 는
  실제로 오지 않는다 — 세션(대화) 식별자는 바디가 아니라 ``x-genos-session-id``
  요청 헤더로만 전달된다(``03_langfuse_propagation`` 의 ``master_agent`` 와 동일,
  ``router.py`` 참고). 과거 이 스키마가 ``context_id`` 를 상관키로 썼던 것은 이
  헤더 기반 계약을 반영하지 못한 구현이었다.

응답은 ``{"code": 0, "data": {"text": ..., "sourceDocuments": [...]}}``.

HITL(사람 개입) 확장은 사용자 확인이 필요하면 응답에 채팅(워크플로우) 표면이
읽는 ``data.messages[].event == "action"`` 과 A2A 표면이 읽는
``data.a2a_status``/``interactionId``/``component`` 를 함께 싣는다. 사용자 응답은
같은 상관키(A2A는 ``chatId``, 채팅 표면은 ``x-genos-session-id`` 헤더)의 다음
요청에 ``humanInput`` 필드로 되돌아온다.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class HumanInputValues(BaseModel):
    selected: List[str] = Field(default_factory=list)
    customInput: Optional[str] = None


class HumanInput(BaseModel):
    """직전 ``action`` 이벤트에 대한 사용자 응답. 같은 chatId의 다음 요청에 실려 온다."""

    interactionId: str
    action: Literal["submit", "cancel"]
    values: HumanInputValues = Field(default_factory=HumanInputValues)


class RagAgentRequest(BaseModel):
    # HITL 재개 요청은 질문 없이 humanInput만 실어 보낼 수 있어 기본값을 비워둔다.
    # A2A 표면(및 구버전 직접 호출)이 쓰는 필드 — question/chatId.
    question: str = ""
    chatId: Optional[str] = None
    # 과거 채팅(워크플로우) 표면이 보낸다고 가정했던 필드. 실제로는 이 경로가 보내지
    # 않지만, 다른 호출자가 대화 히스토리를 실어 보내는 경우를 위해 폴백으로만 남겨둔다
    # (세션 상관키로는 더 이상 쓰지 않는다 — correlation_key() 참고).
    messages: Optional[List[Dict[str, Any]]] = None
    stream: Optional[bool] = False
    # 워크플로우 API(/run/v2) 직접 호출 시 body에 실어 보내는 Langfuse trace 연결 정보.
    # A2A 경유 호출은 이 필드를 실어 보낼 방법이 없으므로 항상 비어 있을 수 있다 — service.py가
    # 없거나 형식이 잘못된 값을 안전하게 무시하고 폴백한다.
    trace_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    # 이 필드가 오면 새 질문이 아니라, 저장해둔 HITL 대기 상태를 재개하는 요청으로 처리한다.
    humanInput: Optional[HumanInput] = None

    def correlation_key(self, session_id: Optional[str] = None) -> Optional[str]:
        """HITL 대기 상태를 저장/조회할 상관키.

        A2A 표면의 ``chatId`` 가 있으면 그것을, 없으면(채팅/워크플로우 표면) 호출자가
        ``x-genos-session-id`` 헤더에서 읽어 넘겨준 ``session_id`` 를 쓴다. 바디의
        ``context_id`` 는 실제 요청에 실려 오지 않으므로 더 이상 쓰지 않는다.
        """
        return self.chatId or session_id

    def effective_question(self) -> str:
        """question(A2A/구버전)이 비어 있으면 messages(채팅 표면)의 마지막 user 메시지로 폴백한다."""
        if self.question:
            return self.question
        for message in reversed(self.messages or []):
            if isinstance(message, dict) and message.get("role") == "user":
                content = message.get("content")
                if isinstance(content, str):
                    return content
        return ""


class EvaluationResult(BaseModel):
    score: float
    reasoning: str


class SourceDocument(BaseModel):
    pageContent: str
    metadata: Dict[str, Any]


class ActionComponentOption(BaseModel):
    value: str
    label: str
    desc: Optional[str] = None


class ActionComponent(BaseModel):
    type: Literal["confirm", "single-select", "multi-select"]
    title: str
    options: List[ActionComponentOption] = Field(default_factory=list)


class ActionElement(BaseModel):
    interactionId: str
    component: ActionComponent


class ChatEvent(BaseModel):
    """채팅(워크플로우) 표면이 SSE ``action`` 이벤트로 그대로 재생하는 프레임(§1)."""

    event: str
    data: Dict[str, Any]


class RagAgentResponseData(BaseModel):
    text: str
    # --- 정상 완료 응답에만 채워진다 ---
    sourceDocuments: Optional[List[SourceDocument]] = None
    evaluation: Optional[EvaluationResult] = None
    tool_call_count: Optional[int] = None
    langfuse_manual_tracing: Optional[bool] = None
    # --- HITL 대기(action) 응답에만 채워진다 (§7.2 "권장 응답 바디 (양쪽 겸용)") ---
    messages: Optional[List[ChatEvent]] = None  # 채팅(워크플로우) 표면용
    a2a_status: Optional[Literal["input-required"]] = None  # A2A 표면용
    interactionId: Optional[str] = None
    component: Optional[ActionComponent] = None


class RagAgentResponse(BaseModel):
    code: int = 0
    data: RagAgentResponseData
