"""
code-serving Langfuse 계측 예제 — `@observe` 데코레이터 버전.

`service.py` 는 `with client.start_as_current_observation(...)` 컨텍스트 매니저로
모든 span/generation 을 직접 열고 닫는다. Langfuse v3 SDK 는 그 외에도 계측을
전파하는 방법을 제공하는데, 이 파일은 그중 데코레이터 방식을 보여준다:

    @observe(as_type="retriever", name="retrieve-documents")
    def retrieve_documents(query: str, top_k: int = 3): ...

- 함수를 호출하면 자동으로 span/generation 이 생성되고, 함수의 인자가 input, 반환값이
  output 으로 자동 캡처된다 (`capture_input`/`capture_output`, 기본 True).
- 데코레이터가 적용된 함수를 다른 데코레이터 적용 함수 안에서 호출하면, 호출 스택
  그대로 부모-자식 span 관계가 만들어진다 (`retrieve_documents` -> `rag-agent` ->
  `generate-answer` 등 별도의 `with` 블록 없이 자연스럽게 중첩됨).
- 예외가 발생하면 자동으로 `level="ERROR"` 로 기록되고 재발생(raise)된다.
- generation 타입은 `get_client().update_current_generation(...)` 으로, 그 외
  타입은 `get_client().update_current_span(...)` 으로 model/usage/level 등 자동
  캡처되지 않는 값을 현재 활성 observation 에 추가로 기록한다.

trace 구조는 `service.py` 와 동일하다:

    rag-pipeline                (span, root)            @observe(as_type="span")
    ├─ input-guardrail          (guardrail)              @observe(as_type="guardrail")
    ├─ retrieve-documents       (retriever)              @observe(as_type="retriever")
    ├─ rag-agent                (agent)                  @observe(as_type="agent")
    │  ├─ rerank-documents      (tool)                   @observe(as_type="tool")
    │  └─ generate-answer       (generation)             @observe(as_type="generation")
    └─ output-guardrail         (guardrail)              @observe(as_type="guardrail")

전부 더미 로직이며(실제 벡터DB/LLM 미사용), env 미주입 시 또는 `langfuse` 패키지가
설치되어 있지 않을 때는 데코레이터/헬퍼가 아무 동작도 하지 않는 no-op 으로 대체되어
동일한 파이프라인이 계측 없이 실행된다 (`langfuse_manual_tracing: false`).
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from typing import Any

_LANGFUSE_ENABLED = bool(
    os.getenv("LANGFUSE_HOST")
    and os.getenv("LANGFUSE_PUBLIC_KEY")
    and os.getenv("LANGFUSE_SECRET_KEY")
)


def _coerce_data(data: Any) -> dict[str, Any]:
    """GenOS 게이트웨이가 dict 대신 raw bytes/str 을 넘기는 경로가 있어 방어적으로 파싱한다."""
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8", errors="replace")
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {"message": data}
        return parsed if isinstance(parsed, dict) else {"message": parsed}
    if isinstance(data, dict):
        return data
    return {"message": data}


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

        def flush(self) -> None:
            pass

    def get_client():  # type: ignore[no-redef]
        return _NoopObservation()

    @contextmanager
    def propagate_attributes(**_kwargs: Any):  # type: ignore[no-redef]
        yield


# ---------------------------------------------------------------------------
# 더미 지식 베이스 / 가드레일 규칙 (service.py 와 동일)
# ---------------------------------------------------------------------------

_KNOWLEDGE_BASE: list[dict[str, Any]] = [
    {
        "doc_id": "doc-001",
        "title": "GenOS code-serving 배포 가이드",
        "text": "code-serving 은 git 저장소를 배포 단위로 사용하며, service.py 가 /app/src/service/service.py 로 배치된다.",
        "score": 0.91,
    },
    {
        "doc_id": "doc-002",
        "title": "Langfuse 연동 매뉴얼",
        "text": "LANGFUSE_HOST/LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY 환경변수를 주입하면 SDK 계측이 활성화된다.",
        "score": 0.87,
    },
    {
        "doc_id": "doc-003",
        "title": "트러블슈팅 FAQ",
        "text": "trace 가 UI 에 안 보이면 client.flush() 호출 여부와 네트워크 egress 를 먼저 확인한다.",
        "score": 0.74,
    },
    {
        "doc_id": "doc-004",
        "title": "관측 타입 레퍼런스",
        "text": "retriever/agent/guardrail/tool/generation 은 as_type 파라미터로 지정하는 Langfuse observation 타입이다.",
        "score": 0.68,
    },
]

_INPUT_BLOCKLIST = ("폭탄 제조", "해킹 방법", "무기 밀매")
_OUTPUT_BLOCKLIST = ("주민등록번호", "카드번호")


# ---------------------------------------------------------------------------
# 파이프라인 단계 — 각 함수가 곧 하나의 observation.
# 함수 인자(input)/반환값(output)은 @observe 가 자동으로 캡처하므로,
# 여기서는 자동 캡처되지 않는 값(level, status_message, model, usage_details)만
# get_client().update_current_span()/update_current_generation() 으로 추가한다.
# ---------------------------------------------------------------------------


@observe(as_type="guardrail", name="input-guardrail")
def check_input_guardrail(user_message: str) -> dict[str, Any]:
    time.sleep(0.02)
    hit = next((kw for kw in _INPUT_BLOCKLIST if kw in user_message), None)
    result = {
        "passed": hit is None,
        "reason": f"차단 키워드 감지: {hit}" if hit else "이상 없음",
    }

    get_client().update_current_span(
        level="WARNING" if not result["passed"] else "DEFAULT",
        status_message=result["reason"],
    )
    return result


@observe(as_type="retriever", name="retrieve-documents")
def retrieve_documents(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    # 함수 인자 `query` 가 그대로 이 observation 의 input 으로 로그에 남는다.
    time.sleep(0.05)
    ranked = sorted(_KNOWLEDGE_BASE, key=lambda d: d["score"], reverse=True)
    documents = ranked[:top_k]

    get_client().update_current_span(metadata={"top_k": top_k, "count": len(documents)})
    return documents  # 반환값(추출된 문서 목록)이 output 으로 자동 캡처됨


@observe(as_type="tool", name="rerank-documents")
def rerank_documents(
    query: str, documents: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    time.sleep(0.03)
    return sorted(
        documents, key=lambda d: d["score"] + len(query) * 0.001, reverse=True
    )


@observe(as_type="generation", name="generate-answer")
def generate_answer(query: str, documents: list[dict[str, Any]]) -> str:
    time.sleep(0.08)
    context = "; ".join(f"[{d['doc_id']}] {d['title']}" for d in documents)
    answer = f"'{query}' 에 대한 답변: {len(documents)}개 문서({context})를 근거로 생성한 응답"

    get_client().update_current_generation(
        model="dummy-gpt-4o-mini",
        model_parameters={"temperature": 0.2, "max_tokens": 256},
        usage_details={
            "prompt_tokens": 128,
            "completion_tokens": 64,
            "total_tokens": 192,
        },
    )
    return answer


@observe(as_type="agent", name="rag-agent")
def run_rag_agent(user_message: str, documents: list[dict[str, Any]]) -> str:
    # 이 함수의 input 에는 question 뿐 아니라 retriever 가 추출한 documents 가
    # 그대로 찍힌다 -> "검색된 문서와 함께 agent span 으로 전달" 되는 모습이 그대로 로그에 남는다.
    reranked = rerank_documents(user_message, documents)
    return generate_answer(user_message, reranked)


@observe(as_type="guardrail", name="output-guardrail")
def check_output_guardrail(answer: str) -> dict[str, Any]:
    time.sleep(0.02)
    hit = next((kw for kw in _OUTPUT_BLOCKLIST if kw in answer), None)
    result = {
        "passed": hit is None,
        "reason": f"민감정보 감지: {hit}" if hit else "이상 없음",
    }

    get_client().update_current_span(
        level="WARNING" if not result["passed"] else "DEFAULT",
        status_message=result["reason"],
    )
    return result


@observe(as_type="span", name="rag-pipeline")
def run_rag_pipeline(user_message: str) -> dict[str, Any]:
    input_check = check_input_guardrail(user_message)
    if not input_check["passed"]:
        blocked_answer = f"[guardrail] 요청이 차단되었습니다: {input_check['reason']}"
        get_client().update_current_span(output=blocked_answer, level="WARNING")
        return {
            "answer": blocked_answer,
            "guardrail_blocked": True,
            "retrieved_documents": [],
        }

    documents = retrieve_documents(user_message)
    answer = run_rag_agent(user_message, documents)

    output_check = check_output_guardrail(answer)
    final_answer = (
        answer
        if output_check["passed"]
        else f"[guardrail] 응답이 차단되었습니다: {output_check['reason']}"
    )

    return {
        "answer": final_answer,
        "guardrail_blocked": not output_check["passed"],
        "retrieved_documents": [d["doc_id"] for d in documents],
    }


# ---------------------------------------------------------------------------
# 진입점 — service.py 와 동일한 시그니처
# ---------------------------------------------------------------------------


async def service(config: dict[str, Any], data: Any):
    data = _coerce_data(data)
    user_message = str(data.get("message", data))
    session_id = data.get("session_id")
    user_id = data.get("user_id")

    with propagate_attributes(
        session_id=session_id, user_id=user_id, metadata={"config": config}
    ):
        result = run_rag_pipeline(user_message)

    if _LANGFUSE_ENABLED:
        get_client().flush()

    return {**result, "langfuse_manual_tracing": _LANGFUSE_ENABLED}


if __name__ == "__main__":
    import asyncio

    result = asyncio.run(
        service(
            config={},
            data={"message": "GenOS code-serving 에서 Langfuse trace 는 어떻게 남아?"},
        )
    )
    print(result)
