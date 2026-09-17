"""Langfuse 데코레이터(``@observe``) 계측 공용 유틸.

``01_langfuse_base/examples/service_decorator.py`` 의 계측 방식(파이프라인 각 단계를
함수로 쪼개고 ``@observe(as_type=...)``)을 여러 에이전트 모듈이 공유할 수 있도록
분리했다. ``LANGFUSE_HOST``/``LANGFUSE_PUBLIC_KEY``/``LANGFUSE_SECRET_KEY`` 가
전부 주입되어 있고 ``langfuse`` 가 정상 import 될 때만 실제 SDK를 쓰고, 그 외에는
동일한 이름의 no-op 대체 구현으로 전환해 "Langfuse 없이도 동작"을 보장한다.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

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

        def flush(self) -> None:
            pass

    def get_client():  # type: ignore[no-redef]
        return _NoopObservation()

    @contextmanager
    def propagate_attributes(**_kwargs: Any):  # type: ignore[no-redef]
        yield


LANGFUSE_ENABLED = _LANGFUSE_ENABLED
