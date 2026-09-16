"""
code-serving Langfuse 계측 예제 — 수동 lifecycle(start/end) 버전.

`service.py` 는 `with client.start_as_current_observation(...)` 로 span 을 열고
블록이 끝나면 자동으로 닫는다. 이 파일은 그 대신 `start_observation()` 으로
observation 객체만 생성해두고, 필요한 시점에 명시적으로 `.update()` / `.end()`
를 호출하는 저수준(manual) 방식을 보여준다.

- `client.start_observation(...)` / `parent.start_observation(...)` 은 observation
  을 만들 뿐 "현재 활성 observation" 으로 설정하지 않는다. 즉 콜백/이벤트 핸들러처럼
  생성과 종료가 서로 다른 함수·스레드에 걸쳐 있어 `with` 블록 하나로 묶기 어려운
  경우에 적합하다.
- 부모/자식 관계는 `client.start_observation(...)` 대신 `parent.start_observation(...)`
  을 호출해서 만든다 (`start_as_current_observation` 이 하던 자동 중첩을 수동으로 구성).
- 끝나는 시점을 명시적으로 관리해야 하므로, 예외가 나도 span 이 열린 채로 남지
  않도록 각 observation 마다 try/finally 로 `.end()` 를 보장한다.

trace 구조는 `service.py` 와 동일하다:

    rag-pipeline                (span, root)
    ├─ input-guardrail          (guardrail)
    ├─ retrieve-documents       (retriever)   question -> 추출된 문서 목록
    ├─ rag-agent                (agent)       question + 추출된 문서를 input 으로 받음
    │  ├─ rerank-documents      (tool)
    │  └─ generate-answer       (generation)
    └─ output-guardrail         (guardrail)

전부 더미 로직이며(실제 벡터DB/LLM 미사용), env 미주입 시에는 계측 없이 동일한
파이프라인만 실행된다 (`langfuse_manual_tracing: false`).
"""

from __future__ import annotations

import json
import os
import time
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


def _get_langfuse_client():
    if not _LANGFUSE_ENABLED:
        return None
    try:
        from langfuse import Langfuse

        return Langfuse()
    except Exception:
        # langfuse_manual_tracing 이 계속 False 로 나오면 여기서 삼켜진 예외가 원인일 수 있으니 로그로 남긴다
        # (예: requirements.txt 에 langfuse 가 빠져 있어 ModuleNotFoundError 가 나는 경우).
        import traceback

        traceback.print_exc()
        return None


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


def _check_input_guardrail(user_message: str) -> dict[str, Any]:
    time.sleep(0.02)
    hit = next((kw for kw in _INPUT_BLOCKLIST if kw in user_message), None)
    return {
        "passed": hit is None,
        "reason": f"차단 키워드 감지: {hit}" if hit else "이상 없음",
    }


def _retrieve_documents(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    time.sleep(0.05)
    ranked = sorted(_KNOWLEDGE_BASE, key=lambda d: d["score"], reverse=True)
    return ranked[:top_k]


def _rerank_documents(
    query: str, documents: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    time.sleep(0.03)
    return sorted(
        documents, key=lambda d: d["score"] + len(query) * 0.001, reverse=True
    )


def _generate_answer(query: str, documents: list[dict[str, Any]]) -> str:
    time.sleep(0.08)
    context = "; ".join(f"[{d['doc_id']}] {d['title']}" for d in documents)
    return f"'{query}' 에 대한 답변: {len(documents)}개 문서({context})를 근거로 생성한 응답"


def _check_output_guardrail(answer: str) -> dict[str, Any]:
    time.sleep(0.02)
    hit = next((kw for kw in _OUTPUT_BLOCKLIST if kw in answer), None)
    return {
        "passed": hit is None,
        "reason": f"민감정보 감지: {hit}" if hit else "이상 없음",
    }


def _run_pipeline_untraced(user_message: str) -> dict[str, Any]:
    input_check = _check_input_guardrail(user_message)
    if not input_check["passed"]:
        return {
            "answer": f"[guardrail] 요청이 차단되었습니다: {input_check['reason']}",
            "guardrail_blocked": True,
            "retrieved_documents": [],
        }

    documents = _retrieve_documents(user_message)
    reranked = _rerank_documents(user_message, documents)
    answer = _generate_answer(user_message, reranked)

    output_check = _check_output_guardrail(answer)
    if not output_check["passed"]:
        answer = f"[guardrail] 응답이 차단되었습니다: {output_check['reason']}"

    return {
        "answer": answer,
        "guardrail_blocked": not output_check["passed"],
        "retrieved_documents": [d["doc_id"] for d in reranked],
    }


# ---------------------------------------------------------------------------
# 진입점 — start_observation()/.end() 로 수동 lifecycle 관리.
# `with` 블록이나 `@observe` 데코레이터 없이, 각 observation 을 변수에 담아
# try/finally 로 직접 종료한다.
# ---------------------------------------------------------------------------


async def service(config: dict[str, Any], data: Any):
    data = _coerce_data(data)
    user_message = str(data.get("message", data))
    session_id = data.get("session_id")
    user_id = data.get("user_id")

    client = _get_langfuse_client()

    if client is None:
        result = _run_pipeline_untraced(user_message)
        return {**result, "langfuse_manual_tracing": False}

    from langfuse import propagate_attributes

    with propagate_attributes(
        session_id=session_id, user_id=user_id, metadata={"config": config}
    ):
        root_span = client.start_observation(
            as_type="span", name="rag-pipeline", input=user_message
        )
        try:
            input_guard = root_span.start_observation(
                as_type="guardrail",
                name="input-guardrail",
                input={"message": user_message},
            )
            try:
                input_check = _check_input_guardrail(user_message)
                input_guard.update(
                    output=input_check,
                    level="WARNING" if not input_check["passed"] else "DEFAULT",
                    status_message=input_check["reason"],
                )
            finally:
                input_guard.end()

            if not input_check["passed"]:
                blocked_answer = (
                    f"[guardrail] 요청이 차단되었습니다: {input_check['reason']}"
                )
                root_span.update(output=blocked_answer, level="WARNING")
                return {
                    "answer": blocked_answer,
                    "guardrail_blocked": True,
                    "retrieved_documents": [],
                    "langfuse_manual_tracing": True,
                }

            retriever_span = root_span.start_observation(
                as_type="retriever",
                name="retrieve-documents",
                input={"query": user_message},
            )
            try:
                documents = _retrieve_documents(user_message)
                retriever_span.update(
                    output={"documents": documents, "count": len(documents)},
                    metadata={"top_k": len(documents)},
                )
            finally:
                retriever_span.end()

            agent_span = root_span.start_observation(
                as_type="agent",
                name="rag-agent",
                input={"question": user_message, "documents": documents},
            )
            try:
                rerank_span = agent_span.start_observation(
                    as_type="tool", name="rerank-documents", input=documents
                )
                try:
                    reranked = _rerank_documents(user_message, documents)
                    rerank_span.update(output=reranked)
                finally:
                    rerank_span.end()

                generation_span = agent_span.start_observation(
                    as_type="generation",
                    name="generate-answer",
                    model="dummy-gpt-4o-mini",
                    model_parameters={"temperature": 0.2, "max_tokens": 256},
                    input={"question": user_message, "context": reranked},
                )
                try:
                    answer = _generate_answer(user_message, reranked)
                    generation_span.update(
                        output=answer,
                        usage_details={
                            "prompt_tokens": 128,
                            "completion_tokens": 64,
                            "total_tokens": 192,
                        },
                    )
                finally:
                    generation_span.end()

                agent_span.update(output=answer)
            finally:
                agent_span.end()

            output_guard = root_span.start_observation(
                as_type="guardrail", name="output-guardrail", input={"answer": answer}
            )
            try:
                output_check = _check_output_guardrail(answer)
                output_guard.update(
                    output=output_check,
                    level="WARNING" if not output_check["passed"] else "DEFAULT",
                    status_message=output_check["reason"],
                )
            finally:
                output_guard.end()

            final_answer = (
                answer
                if output_check["passed"]
                else f"[guardrail] 응답이 차단되었습니다: {output_check['reason']}"
            )
            root_span.update(output=final_answer)
        finally:
            root_span.end()

    client.flush()

    return {
        "answer": final_answer,
        "guardrail_blocked": not output_check["passed"],
        "retrieved_documents": [d["doc_id"] for d in reranked],
        "langfuse_manual_tracing": True,
    }


if __name__ == "__main__":
    import asyncio

    result = asyncio.run(
        service(
            config={},
            data={"message": "GenOS code-serving 에서 Langfuse trace 는 어떻게 남아?"},
        )
    )
    print(result)
