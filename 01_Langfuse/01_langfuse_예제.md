# Langfuse 연동 예제

GenOS code-serving 환경에서 동일한 RAG 파이프라인(`input-guardrail` → `retrieve-documents` → `rag-agent`(`rerank-documents` → `generate-answer`) → `output-guardrail`)을 Langfuse로 계측하는 3가지 방식의 예제 코드임.

[langfuse 예시(링크)](https://us.cloud.langfuse.com/project/cmu0rgd3m00g0ad0fcm8ahch3/traces/8126c48244c46e3e10cb131c4f0f4bb7?observation=955df6f6910eddb3)

세 예제 모두 trace 구조(observation 트리)는 동일하고, observation을 생성·관리하는 방식만 다름. 코드는 [`codes/01_rag_pipeline`](codes/01_rag_pipeline) 폴더에 파일명으로 구분되어 있음.

| 방식 | 설명 | 코드 |
| --- | --- | --- |
| Context Manager | `with client.start_as_current_observation(...)`로 각 span/generation을 직접 열고, 블록이 끝나면 자동으로 닫는 기본 방식 | [`service.py`](codes/01_rag_pipeline/service.py) |
| Decorator | `@observe(as_type=...)`를 함수에 붙이면 자동으로 span/generation이 생성되고, 함수의 인자/반환값이 input/output으로 자동 캡처됨. 호출 스택 그대로 부모-자식 span 관계가 만들어짐 | [`service_decorator.py`](codes/01_rag_pipeline/service_decorator.py) |
| Manual Lifecycle | `start_observation()`으로 observation 객체만 생성해두고, 필요한 시점에 명시적으로 `.update()` / `.end()`를 호출하는 저수준 방식. `with` 블록으로 묶기 어려운 콜백/이벤트 핸들러 등에 적합 | [`service_manual_lifecycle.py`](codes/01_rag_pipeline/service_manual_lifecycle.py) |

&nbsp;
