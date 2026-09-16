"""마스터 에이전트의 FastAPI 라우터.

에이전트 엔드포인트는 항상 ``/chat`` 으로 끝나는 규칙(``02_langfuse_evaluation`` 과 동일)을 따른다.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from .schema import MasterAgentRequest, MasterAgentResponse
from .service import handle_turn

router = APIRouter(prefix="/agents/master", tags=["master-agent"])


@router.post("/chat", response_model=MasterAgentResponse)
async def run_master_agent(payload: MasterAgentRequest, request: Request) -> MasterAgentResponse:
    # GenOS 게이트웨이가 대화(세션) 단위로 실어 보내는 헤더 — trace의 session_id 태깅 +
    # 세션 메모리 조회 키로 그대로 사용한다. 헤더가 없으면(로컬 curl 등) 둘 다 자동으로 no-op.
    session_id = request.headers.get("x-genos-session-id")
    return await handle_turn(payload, session_id=session_id)
