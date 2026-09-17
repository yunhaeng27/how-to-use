# GenOS 이용 로그 Trace 연동

> [!NOTE]
> 이 문서는 "GenOS 자체 이용 로그"에 내 코드의 trace를 남기는 방법을 다룬다. Langfuse trace/span 개념 자체는 [00_langfuse_개요.md](../01_Langfuse/00_langfuse_개요.md), 서로 다른 에이전트끼리 trace를 이어받는 방법(멀티 에이전트 propagation)은 [03_langfuse_propagation.md](../01_Langfuse/03_langfuse_propagation.md)에서 다룬다.

## GenOS 이용 로그란

GenOS는 서빙(모델&코드)이 호출될 때마다 자체 Langfuse에 trace를 기록하고, 이를 `서빙` > `코드 서빙` > `이용 로그`에서 보여준다([01_Langfuse/README.md#genos-langfuse](../01_Langfuse/README.md#genos-langfuse) 참고).

코드서빙 안에서 별도로 계측을 붙이면 이 GenOS 자체 trace 안에 자식 span으로 이어 붙일 수 있다. 이 문서는 그 방법과 한계를 정리한다.

## 필요한 것: GenOS 자체 Langfuse 환경변수

Trace가 이용 로그 화면에 나타나려면, 코드가 기록하는 곳이 "GenOS가 이용 로그를 보여주는 바로 그 Langfuse 프로젝트"여야 함.

즉 코드에서 쓰는 `LANGFUSE_HOST`/`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`가 개발자가 개인적으로 만든 외부 Langfuse 프로젝트 값이 아니라, GenOS가 내부적으로 쓰는 Langfuse 프로젝트 값이어야 함.

> [!IMPORTANT]
> 이 값은 코드나 설정 파일에서 알아낼 수 없음. GenOS 인프라/플랫폼 담당자에게 문의해서 발급받아야 함.

발급받은 값은 코드에 하드코딩하지 말고 코드서빙 배포 환경변수로만 등록. 외부 Langfuse 값을 그대로 쓰면 trace 자체는 정상적으로 기록되지만, GenOS 이용 로그와는 별개인 외부 프로젝트에 쌓여서 이용 로그 화면에서는 보이지 않음.

## trace를 이어 붙이는 방법: `traceparent` 헤더

GenOS는 코드서빙을 호출하기 전에 이미 이용 로그용 trace를 하나 열어 두고, 표준 [W3C trace context 스펙의 traceparent 헤더](https://www.w3.org/TR/trace-context/#traceparent-header)로 그 trace_id/parent span id를 실어 보낸다.

형식: `<version>-<trace-id 32hex>-<parent-id 16hex>-<flags>`. 예: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`.

코드에서 이 헤더를 파싱해 `langfuse_trace_id`/`langfuse_parent_observation_id`로 넘기면 새 trace를 만드는 대신 GenOS가 이미 열어 둔 그 trace 안에 자식 span으로 이어 붙는다. 이용 로그 화면에서 하나의 trace로 확인 가능.

```python
traceparent = request.headers.get("traceparent")
```

trace_id/parent_span_id 형식 검증 규칙은 [03_langfuse_propagation.md의 형식 검증 규칙](../01_Langfuse/03_langfuse_propagation.md#형식-검증-규칙)과 동일하게 적용됨.

## `x-genos-trace-id`는 신경 쓰지 말 것

GenOS 게이트웨이는 `x-genos-trace-id` 헤더도 함께 보내지만 코드서빙 입장에서는 무시해도 됨.

겉보기엔 이 헤더가 trace_id를 실어 전파해주는 것처럼 보이지만, 실제로는 최외곽 진입점에서만 root trace_id를 시딩하는 용도로 잠깐 쓰일 뿐 genportal-api/gateway-api 내부 홉들이 이 값을 보존하지 않음. 코드서빙까지 실제로 도달하는 배포 경로에서는 이 헤더 값이 항상 비어 있고, 안정적으로 전달되는 건 `traceparent` 뿐임.

## 제약: parent span은 하나뿐, 원하는 위치에 붙일 수 없음

`traceparent`는 parent-id 슬롯이 하나뿐인 규격이고, GenOS도 아직 "이 span 밑에 붙여줘"처럼 이용 로그 trace 트리 안의 특정 위치를 골라 지정해주는 기능을 제공하지 않음.

그래서 코드가 받는 parent span은 항상 GenOS가 그 호출을 위해 미리 열어 둔 정해진 span 하나뿐(대개 코드서빙 호출을 감싸는 최상위 span). 마스터 에이전트 -> 서브 에이전트처럼 내 코드 안에서 여러 단계를 거치더라도, 그 단계들을 GenOS 트리 내부의 서로 다른 span 아래에 나눠 붙이는 것은 불가능함. GenOS가 열어준 이 하나의 자리 밑에서 내가 원하는 만큼 자식 span을 쌓는 방식으로만 계측할 수 있음.

## 예제 코드

- `traceparent` 헤더를 읽어 GenOS 자체 이용 로그 trace에 이어 붙이는 예: [`03_propagation`](../01_Langfuse/codes/03_propagation)의 master 에이전트(`router.py`에서 헤더 추출, `agents/master_agent/service.py`의 `_parsed_traceparent`/`handle_turn`에서 파싱·이어붙이기)
