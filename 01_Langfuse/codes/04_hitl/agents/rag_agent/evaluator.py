"""LLM-judge 기반 groundedness 평가.

에이전트가 만든 답변이 검색된 문서에 얼마나 근거하는지 별도 LLM 호출로 채점한다.
채점 결과를 trace 의 score 로 남기는 것은 service.py 의 몫이다(여기서는 evaluator span +
그 안의 llm-call generation span 만 남긴다).
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from common.genos_client import call_genos_chat
from common.langfuse_utils import get_client, observe

from .tools import get_documents_by_ids

JUDGE_SYSTEM_PROMPT = (
    "당신은 RAG 답변 평가자입니다. 주어진 질문, 검색된 문서 원문, 답변을 보고 "
    "답변이 문서 내용에 얼마나 근거하는지(groundedness) 1~5 점으로 채점하세요. "
    '마크다운 코드블록이나 다른 텍스트 없이, 반드시 {"score": <1-5 정수>, "reasoning": "<한 문장 이유>"} '
    "형태의 순수 JSON 한 줄만 출력하세요."
)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _parse_judge_output(content: str) -> Dict[str, Any]:
    cleaned = _JSON_FENCE_RE.sub("", content.strip()).strip()
    try:
        parsed = json.loads(cleaned)
        return {"score": float(parsed["score"]), "reasoning": str(parsed["reasoning"])}
    except Exception:
        match = re.search(r"([1-5](?:\.\d+)?)", content)
        score = float(match.group(1)) if match else 0.0
        return {"score": score, "reasoning": content.strip()[:300]}


@observe(as_type="generation", name="llm-call")
def _call_judge_model(messages: List[Dict[str, Any]]) -> str:
    response = call_genos_chat(messages=messages)
    get_client().update_current_generation(
        model=response.get("model"),
        usage_details=response.get("usage") or {},
    )
    return response["choices"][0]["message"].get("content") or ""


@observe(as_type="evaluator", name="groundedness-eval")
async def evaluate_groundedness(query: str, retrieved_documents: List[str], answer: str) -> Dict[str, Any]:
    unique_doc_ids = list(dict.fromkeys(retrieved_documents))
    documents = get_documents_by_ids(unique_doc_ids)
    context = "\n".join(f"[{doc['doc_id']}] {doc['title']}: {doc['text']}" for doc in documents)
    judge_input = f"질문: {query}\n검색된 문서:\n{context}\n답변: {answer}"
    content = _call_judge_model(
        [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": judge_input},
        ]
    )
    return _parse_judge_output(content)
