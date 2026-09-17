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
    # GenOS 게이트웨이가 실어 보내는 trace_id 헤더 — genos 는 아직 parent_span_id 를 전달해주는
    # 기능이 없으므로, 지금은 이 trace_id 만 이어 붙여서 로깅한다(handle_turn 에서 처리).
    header_trace_id = request.headers.get("x-genos-trace-id")
    # genportal-api/gateway-api 내부 홉은 x-genos-trace-id 를 보존하지 않고 표준 W3C traceparent
    # 로만 trace 를 전파한다(최외곽 진입점에서만 x-genos-trace-id 로 root trace_id 를 시딩). 실제
    # 코드서빙 배포 경로에서는 header_trace_id 가 항상 비어 있으므로 이 헤더를 폴백으로 읽어 넘긴다.
    traceparent = request.headers.get("traceparent")
    return await handle_turn(
        payload, session_id=session_id, header_trace_id=header_trace_id, traceparent=traceparent
    )
