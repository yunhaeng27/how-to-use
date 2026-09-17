"""HITL 대기 상태 저장소.

Flowise 체크포인트 인프라가 없으므로(문서 §7.3) 코드서빙 앱이 직접 pending 상태를
들고 있어야 한다. 이 구현은 데모 목적의 in-memory dict라 프로세스가 여러 워커로
뜨거나 재시작되면 상태가 사라진다 — 실제 서비스에서는 Redis 등 외부 저장소로
교체해야 한다.

상관키(``RagAgentRequest.correlation_key``)를 키로 쓴다: A2A 표면은 ``chatId``,
채팅(워크플로우) 표면은 ``x-genos-session-id`` 헤더 값 — 같은 대화의 다음 요청이
같은 키로 돌아온다는 전제를 그대로 따른다.
"""
from __future__ import annotations

from typing import Dict, Optional

from .agent import PendingInteraction

_PENDING: Dict[str, PendingInteraction] = {}


def store(correlation_key: str, pending: PendingInteraction) -> None:
    _PENDING[correlation_key] = pending


def pop(correlation_key: str) -> Optional[PendingInteraction]:
    """조회 즉시 제거한다 — interactionId의 single-use 규약을 강제한다."""
    return _PENDING.pop(correlation_key, None)
