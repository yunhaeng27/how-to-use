"""GenOS 코드서빙 게이트웨이 경유로 02(RAG) 서브에이전트를 호출하는 클라이언트.

``02_langfuse_evaluation`` 은 GenOS **코드서빙**으로 배포된다. 게이트웨이(``gateway-api/src/main.py``)
에는 워크플로우 라우트(``/workflow/{workflow_id}/{path:path}`` -> 내부 ``/run/v2``)와는 별개로
코드서빙 전용 라우트가 있다:

    /code_serving/{code_serving_id}/{code_serving_revision_id:int}/{path:path}

``RewritePath`` 가 앞의 두 path 세그먼트(``code_serving_id``/``revision_id``)만 잘라내고 나머지
(``/agents/rag/chat``)를 코드서빙 파드에 그대로 전달하며, "코드서빙 요청 스키마는 사용자 정의이므로
게이트웨이가 body 를 건드리면 안 된다"(dispatcher 주석)는 원칙에 따라 body 는 손대지 않고 그대로
통과한다. 그래서 여기서 보내는 ``trace_id``/``parent_span_id`` 가 02 의 ``RagAgentRequest`` 까지
그대로 도달한다 — 이게 이 예제(langfuse propagation)의 핵심 경로다. ``/run/v2``(워크플로우 Python/
Flowise 스텝 실행용)는 이 경로와 무관하다.

인증은 마스터 자신의 LLM 호출에 쓰는 ``GENOS_BEARER_TOKEN``(``genos_client.py``, 서빙 리소스용)과
별개로, 코드서빙 리소스 전용 Bearer 토큰이 필요하다(``AuthKeyBearer(resource_type=code_serving)``).
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

import requests

GENOS_URL = os.getenv("GENOS_URL", "https://genos.genon.ai")
RAG_SUBAGENT_CODE_SERVING_ID = os.getenv("RAG_SUBAGENT_CODE_SERVING_ID", "")
RAG_SUBAGENT_CODE_SERVING_REVISION_ID = os.getenv("RAG_SUBAGENT_CODE_SERVING_REVISION_ID", "")
RAG_SUBAGENT_BEARER_TOKEN = os.getenv("RAG_SUBAGENT_BEARER_TOKEN", "")
# 02_langfuse_evaluation/src/agents/rag_agent/router.py: APIRouter(prefix="/agents/rag") + "/chat"
RAG_SUBAGENT_PATH = os.getenv("RAG_SUBAGENT_PATH", "/agents/rag/chat")
# 로컬 개발/테스트용 우회로: 실제 GenOS 배포 없이 02 를 로컬에서 직접 띄워
# (예: cd 02_langfuse_evaluation/src && uv run uvicorn main:app --port 8001) 이 base URL 로
# 바로 호출할 수 있게 한다. 값이 있으면 게이트웨이 URL 조립/Bearer 인증을 건너뛴다.
RAG_SUBAGENT_BASE_URL = os.getenv("RAG_SUBAGENT_BASE_URL", "")


def _endpoint_and_headers() -> Tuple[str, Dict[str, str]]:
    if RAG_SUBAGENT_BASE_URL:
        return f"{RAG_SUBAGENT_BASE_URL.rstrip('/')}{RAG_SUBAGENT_PATH}", {}

    if not RAG_SUBAGENT_CODE_SERVING_ID or not RAG_SUBAGENT_BEARER_TOKEN:
        raise RuntimeError(
            "RAG_SUBAGENT_CODE_SERVING_ID / RAG_SUBAGENT_BEARER_TOKEN 환경변수가 필요합니다. "
            "GenOS admin 에서 02_langfuse_evaluation 코드서빙 배포의 code_serving_id 와 발급된 "
            "bearer token 을 확인하거나, 로컬 테스트 시 RAG_SUBAGENT_BASE_URL 을 설정하세요."
        )

    segment = RAG_SUBAGENT_CODE_SERVING_ID
    if RAG_SUBAGENT_CODE_SERVING_REVISION_ID:
        segment = f"{segment}/{RAG_SUBAGENT_CODE_SERVING_REVISION_ID}"
    endpoint = f"{GENOS_URL}/api/gateway/code_serving/{segment}{RAG_SUBAGENT_PATH}"
    return endpoint, {"Authorization": f"Bearer {RAG_SUBAGENT_BEARER_TOKEN}"}


def call_rag_subagent(
    instruction: str,
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """02 RAG 서브에이전트를 호출한다.

    Returns:
        02 ``RagAgentResponse`` 의 ``data`` (text/sourceDocuments/evaluation/tool_call_count/...).
    """
    endpoint, headers = _endpoint_and_headers()

    body: Dict[str, Any] = {"question": instruction, "stream": False}
    if chat_id:
        body["chatId"] = chat_id
    # 게이트웨이가 body 를 그대로 통과시키므로, 여기 실은 trace_id/parent_span_id 가 02 의
    # RagAgentRequest.trace_id/parent_span_id 까지 그대로 도달해 같은 trace 로 이어 붙는다.
    if trace_id:
        body["trace_id"] = trace_id
    if parent_span_id:
        body["parent_span_id"] = parent_span_id

    res = requests.post(endpoint, headers=headers, json=body, timeout=timeout)
    res.raise_for_status()
    payload = res.json()
    return payload.get("data", payload)
