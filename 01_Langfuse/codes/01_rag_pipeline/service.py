"""
code-serving Langfuse 계측 테스트 에이전트 (RAG + Guardrail + Retriever 버전).

목적: GenOS 게이트웨이가 자동으로 만드는 `code_serving` span 하나만으로는
내부 단계(guardrail → retriever → agent → generation)가 안 보인다는 걸 확인하고,
LANGFUSE_HOST/LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY 가 배포 시 주입됐을 때
langfuse v3 SDK(`start_as_current_observation(as_type=...)`)로 직접 만든 하위 span 이
얼마나 풍부하게 남는지 비교하기 위한 샘플이다.

trace 구조 (env 주입 시):

    rag-pipeline                (span, root)
    ├─ input-guardrail          (guardrail)   입력 안전성 체크. 위반 시 여기서 종료.
    ├─ retrieve-documents       (retriever)   question -> 검색된 문서 목록 (input/output 로 확인)
    ├─ rag-agent                (agent)       질문 + 검색된 문서를 받아 최종 답변까지 담당
    │  ├─ rerank-documents      (tool)        검색 결과 재정렬 (agent 내부 tool 호출 예시)
    │  └─ generate-answer       (generation)  문서를 컨텍스트로 답변 생성 (더미 LLM 호출)
    └─ output-guardrail         (guardrail)   생성된 답변에 대한 안전성 체크

전부 더미 로직이며(실제 벡터DB/LLM 미사용), 목적은 Langfuse trace 트리 구조와
retriever/guardrail/agent observation 타입이 UI 에서 잘 구분되어 보이는 것이다.

env 미주입 시에도 동일한 파이프라인이 실행되지만 계측 없이 동작한다
(langfuse_manual_tracing=False 로 표시) — no-op.
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


# ---------------------------------------------------------------------------
# 더미 지식 베이스 / 가드레일 규칙
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
# 파이프라인 단계 (전부 더미 구현)
# ---------------------------------------------------------------------------


def _check_input_guardrail(user_message: str) -> dict[str, Any]:
    time.sleep(0.02)
    hit = next((kw for kw in _INPUT_BLOCKLIST if kw in user_message), None)
    return {
        "passed": hit is None,
        "reason": f"차단 키워드 감지: {hit}" if hit else "이상 없음",
    }


def _retrieve_documents(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    time.sleep(0.05)
    # 더미: 실제로는 embedding + vector DB 유사도 검색이 들어갈 자리.
    ranked = sorted(_KNOWLEDGE_BASE, key=lambda d: d["score"], reverse=True)
    return ranked[:top_k]


def _rerank_documents(
    query: str, documents: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    time.sleep(0.03)
    # 더미 재정렬: query 길이를 기반으로 한 점수 보정 흉내.
    boosted = sorted(
        documents, key=lambda d: d["score"] + len(query) * 0.001, reverse=True
    )
    return boosted


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


# ---------------------------------------------------------------------------
# 계측 없는 파이프라인 (env 미주입 시)
# ---------------------------------------------------------------------------


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
# 진입점
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
        with client.start_as_current_observation(
            as_type="span", name="rag-pipeline", input=user_message
        ) as root_span:

            with client.start_as_current_observation(
                as_type="guardrail",
                name="input-guardrail",
                input={"message": user_message},
            ) as input_guard:
                input_check = _check_input_guardrail(user_message)
                input_guard.update(
                    output=input_check,
                    level="WARNING" if not input_check["passed"] else "DEFAULT",
                    status_message=input_check["reason"],
                )

            if not input_check["passed"]:
                blocked_answer = (
                    f"[guardrail] 요청이 차단되었습니다: {input_check['reason']}"
                )
                root_span.update(output=blocked_answer, level="WARNING")
                client.flush()
                return {
                    "answer": blocked_answer,
                    "guardrail_blocked": True,
                    "retrieved_documents": [],
                    "langfuse_manual_tracing": True,
                }

            with client.start_as_current_observation(
                as_type="retriever",
                name="retrieve-documents",
                input={"query": user_message},
            ) as retriever_span:
                documents = _retrieve_documents(user_message)
                retriever_span.update(
                    output={"documents": documents, "count": len(documents)},
                    metadata={"top_k": len(documents)},
                )

            with client.start_as_current_observation(
                as_type="agent",
                name="rag-agent",
                input={"question": user_message, "documents": documents},
            ) as agent_span:

                with agent_span.start_as_current_observation(
                    as_type="tool", name="rerank-documents", input=documents
                ) as rerank_span:
                    reranked = _rerank_documents(user_message, documents)
                    rerank_span.update(output=reranked)

                with agent_span.start_as_current_observation(
                    as_type="generation",
                    name="generate-answer",
                    model="dummy-gpt-4o-mini",
                    model_parameters={"temperature": 0.2, "max_tokens": 256},
                    input={"question": user_message, "context": reranked},
                ) as generation_span:
                    answer = _generate_answer(user_message, reranked)
                    generation_span.update(
                        output=answer,
                        usage_details={
                            "prompt_tokens": 128,
                            "completion_tokens": 64,
                            "total_tokens": 192,
                        },
                    )

                agent_span.update(output=answer)

            with client.start_as_current_observation(
                as_type="guardrail", name="output-guardrail", input={"answer": answer}
            ) as output_guard:
                output_check = _check_output_guardrail(answer)
                output_guard.update(
                    output=output_check,
                    level="WARNING" if not output_check["passed"] else "DEFAULT",
                    status_message=output_check["reason"],
                )

            final_answer = (
                answer
                if output_check["passed"]
                else f"[guardrail] 응답이 차단되었습니다: {output_check['reason']}"
            )
            root_span.update(output=final_answer)

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
