"""더미 RAG tool-calling 에이전트의 FastAPI 라우터.

새 예제 에이전트를 추가할 때는 같은 방식으로 ``agents/<name>/router.py`` 를 만들고
``main.py`` 에서 ``include_router`` 하면 된다. 엔드포인트는 항상 ``/chat`` 으로 끝나는
규칙을 따른다.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from .schema import RagAgentRequest, RagAgentResponse
from .service import handle_turn

router = APIRouter(prefix="/agents/rag", tags=["rag-agent"])


@router.post("/chat", response_model=RagAgentResponse, response_model_exclude_none=True)
async def run_rag_agent(payload: RagAgentRequest, request: Request) -> RagAgentResponse:
    # GenOS 게이트웨이가 대화(세션) 단위로 실어 보내는 헤더 — HITL 대기 상태의 상관키 +
    # Langfuse trace의 session_id 태깅에 그대로 쓴다(03_langfuse_propagation의
    # master_agent와 동일한 계약). 헤더가 없으면(로컬 curl 등) chatId(A2A)로만 동작한다.
    session_id = request.headers.get("x-genos-session-id")
    return await handle_turn(payload, session_id=session_id)
