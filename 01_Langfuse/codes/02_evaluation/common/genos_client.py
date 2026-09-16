"""GenOS 게이트웨이 chat.completions 호출 클라이언트.

``chat.py`` 가 보여주는 요청 모양(POST .../v1/chat/completions, Bearer 토큰)을 그대로
따르되, tool calling(``tools``/``tool_choice``)과 멀티턴 호출에 재사용할 수 있도록
함수로 분리했다. ``chat.py`` 자체는 참고용으로 남겨두고 여기서는 새로 구현한다.

reasoning(사고) on/off 는 GenA ``common/utils/llm.py::reasoning_extra_body`` 와 동일한
바디 키(``reasoning.enabled`` + ``chat_template_kwargs.enable_thinking``)로 제어한다.
이 예제의 기본 모델은 ``z-ai/glm-5.2`` 이고 기본값은 no-reasoning(``no_reasoning=True``)이다.
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
