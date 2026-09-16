"""Langfuse 데코레이터(``@observe``) 계측 공용 유틸.

``02_langfuse_evaluation/src/common/langfuse_utils.py`` 와 동일한 no-op 폴백 방식을 쓰되,
이 예제(langfuse propagation)는 현재 span 의 trace_id/observation_id 를 읽어 서브에이전트
호출 body 에 실어 보내야 하므로 ``get_current_trace_id``/``get_current_observation_id`` 를
``_NoopObservation`` 에도 추가했다(Langfuse 미설정 시 둘 다 None 반환 -> 호출부가 trace_id 없이
서브에이전트를 부르는 기본 동작으로 안전하게 폴백).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Optional

_LANGFUSE_ENABLED = bool(
    os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
)

if _LANGFUSE_ENABLED:
    try:
        from langfuse import get_client, observe, propagate_attributes
    except Exception:
        # langfuse_manual_tracing 이 계속 False 로 나오면 여기서 삼켜진 예외가 원인일 수 있으니 로그로 남긴다
        # (예: requirements.txt 에 langfuse 가 빠져 있어 ModuleNotFoundError 가 나는 경우).
        import traceback

        traceback.print_exc()
        _LANGFUSE_ENABLED = False

if not _LANGFUSE_ENABLED:
    # langfuse 미설치 또는 env 미주입 시 사용할 no-op 대체 구현.
    def observe(*_args: Any, **_kwargs: Any):  # type: ignore[no-redef]
        def _decorator(func):
            return func

        if _args and callable(_args[0]):
            return _args[0]
        return _decorator

    class _NoopObservation:
        def update_current_span(self, **_kwargs: Any) -> None:
            pass

        def update_current_generation(self, **_kwargs: Any) -> None:
            pass

        def score_current_trace(self, **_kwargs: Any) -> None:
            pass

        def get_current_trace_id(self) -> Optional[str]:
            return None

        def get_current_observation_id(self) -> Optional[str]:
            return None

        def flush(self) -> None:
            pass

    def get_client():  # type: ignore[no-redef]
        return _NoopObservation()

    @contextmanager
    def propagate_attributes(**_kwargs: Any):  # type: ignore[no-redef]
        yield


LANGFUSE_ENABLED = _LANGFUSE_ENABLED
