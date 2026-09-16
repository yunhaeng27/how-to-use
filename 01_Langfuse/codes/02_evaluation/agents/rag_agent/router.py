"""더미 RAG tool-calling 에이전트의 FastAPI 라우터.

새 예제 에이전트를 추가할 때는 같은 방식으로 ``agents/<name>/router.py`` 를 만들고
``main.py`` 에서 ``include_router`` 하면 된다. 엔드포인트는 항상 ``/chat`` 으로 끝나는
규칙을 따른다.
"""
from __future__ import annotations

from fastapi import APIRouter

from .schema import RagAgentRequest, RagAgentResponse
from .service import handle_turn

router = APIRouter(prefix="/agents/rag", tags=["rag-agent"])


@router.post("/chat", response_model=RagAgentResponse)
async def run_rag_agent(payload: RagAgentRequest) -> RagAgentResponse:
    return await handle_turn(payload)
