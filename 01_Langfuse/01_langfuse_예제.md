# Langfuse 연동

trace/session/observation 등 기본 개념이 낯설면 [00_langfuse_개요.md](00_langfuse_개요.md) 먼저 확인.

## Langfuse 연동 방법

langfuse에 로그를 남기려면 아래 순서를 따름.

**Langfuse(cloud 혹은 self-hosting)에서** 

1. langfuse 가입
2. 가입한 langfuse에서 key 발급(public_key &amp; secret key)

**코드 쪽에서는** 

3. Langfuse 필수 환경 변수 설정
4. SDK 패키지 설치
5. 코드 작성 후 로깅

1, 2번은 계정 가입 및 발급이므로 별도 설명은 생략함.

## 3. 환경 변수 설정

langfuse 연동을 위해서는 아래 3가지 환경 변수 설정이 필수임. `LANGFUSE_PUBLIC_KEY`와 `LANGFUSE_SECRET_KEY`는 langfuse에서 발급받아야 함.


| 환경 변수                 | 설명                                                              |
| --------------------- | --------------------------------------------------------------- |
| `LANGFUSE_HOST`       | langfuse host url (self-host, cloud 등 사용 중인 langfuse의 BASE URL) |
| `LANGFUSE_PUBLIC_KEY` | langfuse에서 발급받는 public key                                      |
| `LANGFUSE_SECRET_KEY` | langfuse에서 발급받는 secret key                                      |


## 4. SDK 패키지 설치

[langfuse SDK 설치 가이드(링크)](https://langfuse.com/docs/observability/get-started#ingest-your-first-trace)

해당 링크를 통해 확인할 수 있지만, 사용하고자 하는 언어에 맞춰 SDK 패키지를 설치하면 됨.

예를 들어, python의 경우 pip 등을 통해 다음과 같이 설치할 수 있음.

```cli
pip install langfuse
```



## 5. 코드 적용

langfuse는 연동 방법을 크게 3가지로 지원하고 있음.

구현을 하다보면 3가지 방법을 섞어쓰게 되므로 모두 알아두면 좋음.


| 방식               | 설명                                                                                                                                    | 코드                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Context Manager  | `with client.start_as_current_observation(...)`로 각 span/generation을 직접 열고, 블록이 끝나면 자동으로 닫는 기본 방식                                      | [`service.py`](codes/01_rag_pipeline/service.py)                                   |
| Decorator        | `@observe(as_type=...)`를 함수에 붙이면 자동으로 span/generation이 생성되고, 함수의 인자/반환값이 input/output으로 자동 캡처됨. 호출 스택 그대로 부모-자식 span 관계가 만들어짐         | [`service_decorator.py`](codes/01_rag_pipeline/service_decorator.py)               |
| Manual Lifecycle | `start_observation()`으로 observation 객체만 생성해두고, 필요한 시점에 명시적으로 `.update()` / `.end()`를 호출하는 저수준 방식. `with` 블록으로 묶기 어려운 콜백/이벤트 핸들러 등에 적합 | [`service_manual_lifecycle.py`](codes/01_rag_pipeline/service_manual_lifecycle.py) |


예제 코드는 GenOS code-serving 환경에서 동일한 RAG 파이프라인(`input-guardrail` → `retrieve-documents` → `rag-agent`(`rerank-documents` → `generate-answer`) → `output-guardrail`)을 Langfuse로 계측하는 3가지 방식임.

[langfuse 예시(링크)](https://us.cloud.langfuse.com/project/cmu0rgd3m00g0ad0fcm8ahch3/traces/8126c48244c46e3e10cb131c4f0f4bb7?observation=955df6f6910eddb3)

세 예제 모두 trace 구조(observation 트리)는 동일하고, observation을 생성·관리하는 방식만 다름. 코드는 `codes/01_rag_pipeline` 폴더에 파일명으로 구분되어 있음.

## 5.1 Context Manager

입력과 출력 구간이 명확하지 않은 경우 사용. span 구간을 `start_as_current_observation`으로 열고, 내부 관측을 update를 통해 할 수 있음.

해당 span 구간 내부에서 다른 span 구간을 여는 경우, 자동으로 자식 span으로 들어감.

```python
from langfuse import get_client

client = get_client()

with client.start_as_current_observation(
    as_type="span", name="rag-pipeline", input=question
) as root_span:  # 부모 span. span 이름 "rag-pipeline", 입력값은 question으로 로깅. 출력은 나중에 생성되므로 마지막에 추가
    with client.start_as_current_observation(
        as_type="retriever", name="retrieve-documents", input=question
    ) as retriever_span:  # 자식 span 1. retriever span.
        documents = retrieve_documents(question)
        retriever_span.update(output=documents)  # retriever span의 output으로 document를 로깅

    with client.start_as_current_observation(
        as_type="generation", name="generate-answer", model="gpt-4o-mini"
    ) as generation_span:  # 자식 span 2. llm span. type이 generation이므로 model도 넣을 수 있음.
        answer = generate_answer(question, documents)
        generation_span.update(output=answer)  # llm span의 output으로 answer를 로깅

    root_span.update(output=answer)  # 최상위 span의 출력을 answer로 로깅

client.flush()
```

## 5.2 Decorator

입력과 출력이 명확한 경우 사용할 수 있음. (특히 함수)

함수의 입력과 출력이 span의 입,출력이 됨.

함수 중첩 호출 시 부모&amp;자식 관계가 자동으로 생김.

```python
from langfuse import observe

@observe(as_type="span", name="rag-pipeline")   # 최상위 호출 -> trace 루트가 된다
async def run_rag_pipeline(question: str) -> str:
    documents = retrieve_documents(question)  # 자동으로 자식 span
    return generate_answer(question, documents)

@observe(as_type="retriever", name="retrieve-documents")
def retrieve_documents(question: str) -> list: ...

@observe(as_type="generation", name="generate-answer")   # LLM 호출 함수는 generation으로
def generate_answer(question: str, documents: list) -> str: ...
```

## 5.3 Manual Lifecycle

직접 열고 닫는 형태.

```python
from langfuse import get_client

client = get_client()

root_span = client.start_observation(as_type="span", name="rag-pipeline", input=question)
try:
    retriever_span = root_span.start_observation(
        as_type="retriever", name="retrieve-documents", input=question
    )
    try:
        documents = retrieve_documents(question)
        retriever_span.update(output=documents)
    finally:
        retriever_span.end()

    answer = generate_answer(question, documents)
    root_span.update(output=answer)
finally:
    root_span.end()

client.flush()
```

## 실전 체크리스트

> [!NOTE]
> `LANGFUSE_HOST`/`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` 중 하나라도 비어 있으면(또는 `langfuse` 패키지 import 실패 시) SDK 전체가 자동으로 no-op으로 폴백함. `get_client()`, `@observe`, `propagate_attributes`를 코드 그대로 호출해도 에러 없이 계측만 조용히 건너뛰고 나머지 로직은 정상 동작함. 구현은 평가 예제의 [`langfuse_utils.py`](codes/02_evaluation/common/langfuse_utils.py)와 propagation 예제의 [`langfuse_utils.py`](codes/03_propagation/common/langfuse_utils.py)에서 확인 가능.

> [!IMPORTANT]
> 응답을 반환하기 전에 `client.flush()`를 반드시 호출할 것. Langfuse SDK는 trace/span 데이터를 백그라운드에서 배치로 전송하므로, flush 없이 프로세스가 먼저 종료되면(서버리스 환경 등) 아직 전송되지 않은 trace가 유실될 수 있음. 위 3가지 방식 예제(Context Manager, Decorator, Manual Lifecycle) 모두 마지막 줄에서 `client.flush()`를 호출하는 이유가 여기 있음.
