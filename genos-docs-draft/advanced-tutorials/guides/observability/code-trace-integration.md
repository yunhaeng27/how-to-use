---
icon: route
# TODO: 실제 GitBook 스페이스 연결 후 metaLinks.alternates 채우기
---
# 코드에서 이용 로그에 Trace 연결하기

Code Serving 안에서 별도로 Langfuse 계측을 추가하면, 그 결과를 GenOS 자체 이용 로그의 trace 안에 자식 span으로 이어 붙일 수 있습니다. 

## 1. GenOS 이용 로그용 Langfuse 환경 변수 확인

Trace가 이용 로그 화면에 나타나려면, 코드가 기록하는 Langfuse 프로젝트가 GenOS 이용 로그를 보여주는 프로젝트와 같아야 합니다.

즉 코드에서 사용하는 `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` 값이 개인적으로 만든 외부 Langfuse 프로젝트의 값이 아니라, GenOS가 내부적으로 사용하는 Langfuse 프로젝트 값이어야 합니다.

> **중요:** 이 값은 코드나 설정 파일만 봐서는 알 수 없습니다. GenOS 인프라 담당자에게 문의해서 발급받아야 합니다.

발급받은 값은 코드 서빙 배포 환경 변수로 등록하세요. 

외부 Langfuse 값을 그대로 사용하면 연결한 langfuse에 trace 자체는 정상적으로 기록되지만, GenOS 이용 로그와는 별개인 외부 프로젝트에 쌓여 이용 로그 화면에서는 확인할 수 없습니다.

## 2. `traceparent` 헤더로 trace 이어 붙이기

GenOS는 코드 서빙을 호출하기 전에 이미 이용 로그용 trace를 하나 열어 두고, 표준 W3C Trace Context 규격의 `**traceparent**` 헤더로 그 trace ID와 parent span ID를 함께 전달합니다.

형식은 `<version>-<trace-id 32자리 16진수>-<parent-id 16자리 16진수>-<flags>`이며, 예를 들어 `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`와 같은 값입니다.

코드에서 이 헤더를 파싱해 `langfuse_trace_id`/`langfuse_parent_observation_id`로 전달하면, 새 trace를 만드는 대신 GenOS가 이미 열어 둔 trace 안에 자식 span으로 연결할 수 있습니다. 이용 로그 화면에서는 하나의 trace로 확인할 수 있습니다.

```python
traceparent = request.headers.get("traceparent")
```

> Trace ID는 32자리, Parent Span ID는 16자리의 16진수 문자열 형식을 만족해야 합니다.

## 3. `x-genos-trace-id`는 사용하지 않습니다

GenOS 게이트웨이는 `x-genos-trace-id` 헤더도 함께 전달하지만, 코드 서빙에서는 이 값을 사용하지 않아도 됩니다.

이 헤더는 얼핏 trace ID를 전파하는 용도처럼 보이지만, 실제로는 가장 바깥 진입점에서 최초 trace ID를 부여하는 데만 잠깐 사용되고 이후 내부 구간에서는 값이 유지되지 않습니다. 코드 서빙까지 도달하는 실제 호출 경로에서는 이 값이 항상 비어 있으므로, 안정적으로 사용할 수 있는 값은 `traceparent` 뿐입니다.

## 4. 제약 사항: parent span은 하나뿐입니다

`traceparent`는 parent span 자리를 하나만 지정할 수 있는 규격이고, GenOS도 이용 로그 trace 트리 안의 특정 위치를 선택해서 연결하는 기능은 아직 제공하지 않습니다.

따라서 코드가 받는 parent span은 항상 GenOS가 해당 호출을 위해 미리 열어 둔 span 하나뿐입니다(대개 코드 서빙 호출을 감싸는 최상위 span). 마스터 에이전트에서 서브 에이전트로 이어지는 것처럼 코드 내부에서 여러 단계를 거치더라도, 그 단계들을 GenOS 트리 안의 서로 다른 span 아래로 나누어 연결할 수는 없습니다. GenOS가 열어 준 하나의 자리 아래에 원하는 만큼 자식 span을 쌓는 방식으로만 계측할 수 있습니다.

## 5. GenOS 세션과 Langfuse 세션 연동하기

멀티턴 대화를 하나의 Langfuse 세션으로 묶으려면, GenOS가 워크플로우 호출 시 전달하는 `**x-genos-session-id**` 헤더 값을 그대로 Langfuse의 session ID로 재사용합니다.

```python
# 요청 헤더에서 세션 ID 추출
session_id = request.headers.get("x-genos-session-id")
```

```python
# 추출한 세션 ID를 Langfuse에 전파
from langfuse import propagate_attributes

with propagate_attributes(session_id=session_id):
    agent_result = await run_agent(payload.question, history=history)
```

헤더 값이 없으면(로컬 테스트 등) `session_id`가 `None`이 되고, `propagate_attributes(session_id=None)`은 아무것도 태깅하지 않으므로 별도 처리 없이 안전합니다.

## 6. 워크플로우/A2A에 따른 전파 가능 여부

GenOS로 여러 에이전트를 연결한 오케스트레이션을 구성할 때, trace 전파가 가능한지는 호출 방식에 따라 달라집니다.


| 호출 방식                    | trace 전파 가능 여부 | 이유                                                              |
| ------------------------ | -------------- | --------------------------------------------------------------- |
| 워크플로우(코드 서빙 게이트웨이 경유 포함) | 가능             | 게이트웨이가 요청 본문을 그대로 통과시키므로, 본문에 실은 trace 정보가 다음 에이전트까지 그대로 전달됩니다. |
| A2A                      | 불가능            | GenOS가 A2A 프로토콜 규격에 맞춰 헤더/본문을 직접 재구성하는 과정에서 임의로 추가한 필드가 사라집니다.  |


## 관련 문서

- [이용 로그에서 Langfuse 로그 확인](usage-log.md)
- [서빙 로그 확인](../serving/api-log.md)

