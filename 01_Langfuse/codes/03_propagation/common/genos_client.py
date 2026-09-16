"""GenOS 게이트웨이 chat.completions 호출 클라이언트 (마스터 에이전트 자신의 LLM 호출용).

``02_langfuse_evaluation/src/common/genos_client.py`` 와 동일하다 — 마스터 에이전트도 같은
GenOS 서빙(LLM 게이트웨이)을 통해 자기 자신의 tool-calling 루프를 실행한다. 서브에이전트(02)
호출은 이 파일이 아니라 ``common/subagent_client.py`` 가 담당한다(서로 다른 GenOS 리소스이자
별도 인증 체계 — 이건 LLM 서빙, 그건 코드서빙).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

GENOS_URL = os.getenv("GENOS_URL", "https://genos.genon.ai")
GENOS_SERVING_ID = os.getenv("GENOS_SERVING_ID", "1009")
GENOS_MODEL = os.getenv("GENOS_MODEL", "z-ai/glm-5.2")


def _reasoning_extra_body(enabled: bool) -> Dict[str, Any]:
    return {
        "reasoning": {"enabled": enabled},
        "chat_template_kwargs": {"enable_thinking": enabled},
    }


def call_genos_chat(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Any] = None,
    model: Optional[str] = None,
    no_reasoning: bool = True,
) -> Dict[str, Any]:
    """GenOS 게이트웨이의 chat.completions 엔드포인트를 호출한다.

    Returns:
        OpenAI 호환 chat.completions 응답 JSON (``choices[0].message`` 에 ``tool_calls`` 포함 가능).
    """
    token = os.getenv("GENOS_BEARER_TOKEN")
    if not token:
        raise RuntimeError(
            "GENOS_BEARER_TOKEN 환경변수가 설정되어 있지 않습니다. "
            "GenOS 서빙 배포에서 발급받은 bearer token을 export 하세요."
        )

    endpoint = f"{GENOS_URL}/api/gateway/rep/serving/{GENOS_SERVING_ID}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {token}"}
    body: Dict[str, Any] = {
        "model": model or GENOS_MODEL,
        "messages": messages,
    }
    if tools:
        body["tools"] = tools
    if tool_choice is not None:
        body["tool_choice"] = tool_choice
    body.update(_reasoning_extra_body(enabled=not no_reasoning))

    res = requests.post(endpoint, headers=headers, json=body, timeout=60)
    res.raise_for_status()
    return res.json()
