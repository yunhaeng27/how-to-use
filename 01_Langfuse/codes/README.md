# Langfuse 코드 예제

[01_Langfuse](../) 각 문서에 대응하는 실행 가능한 예제 코드 모음.

> [!IMPORTANT]
> Python 3.10 이상 필요. `langfuse` SDK가 `get_client`, `propagate_attributes`, `@observe` 등 최신 API를 씀. 3.9 이하 환경에서는 이 API가 없는 구버전 SDK가 설치됨. 이 상태로 예제를 실행하면 `from langfuse import ...`에서 조용히 `ImportError`가 남. 각 예제 폴더의 `requirements.txt`(`langfuse>=4.0` 고정)로 설치할 것: `pip install -r requirements.txt`

## 목차

- [01_rag_pipeline](01_rag_pipeline) — [01_langfuse_예제.md](../01_langfuse_예제.md)의 RAG 파이프라인 계측 예제
- [02_evaluation](02_evaluation) — [02_langfuse_평가.md](../02_langfuse_평가.md)의 Langfuse Score 평가 예제
- [03_propagation](03_propagation) — [03_langfuse_propagation.md](../03_langfuse_propagation.md)의 멀티 에이전트 trace 전파 예제. GenOS 배포 절차는 [해당 폴더 README](03_propagation/README.md) 참고
