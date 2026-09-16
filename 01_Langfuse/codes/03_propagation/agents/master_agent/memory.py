"""세션 ID 기반 초간단 인메모리 대화 기록 (예제 코드용).

비영속(프로세스 재시작 시 소실)이고, uvicorn 을 --workers 2 이상으로 띄우면 워커 프로세스마다
별도로 관리된다(공유 안 됨) — 데모/단일 워커 실행을 전제로 한다. 프로덕션에서는 Redis 등 외부
저장소가 필요하다.

무한정 커지는 것만 막기 위해 두 가지 캡을 둔다:
- 세션당 최근 MAX_TURNS_PER_SESSION 턴만 보관
- 전체 세션 수가 MAX_SESSIONS 를 넘으면 가장 오래전에 쓰인 세션부터 버린다
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Dict, List, Optional

MAX_TURNS_PER_SESSION = 10
MAX_SESSIONS = 100

_store: "OrderedDict[str, List[Dict[str, str]]]" = OrderedDict()


def get_history(session_id: Optional[str]) -> List[Dict[str, str]]:
    """session_id 가 없으면 항상 빈 기록(새 대화처럼 동작)."""
    if not session_id:
        return []
    return _store.get(session_id, [])


def append_turn(session_id: Optional[str], question: str, answer: str) -> None:
    """session_id 가 없으면 아무것도 하지 않는다."""
    if not session_id:
        return

    turns = _store.pop(session_id, [])
    turns.append({"question": question, "answer": answer})
    _store[session_id] = turns[-MAX_TURNS_PER_SESSION:]  # 최근 N턴만 유지 + 맨 뒤로 이동(최근 사용 순)

    while len(_store) > MAX_SESSIONS:
        _store.popitem(last=False)  # 가장 오래전에 쓰인 세션부터 제거
