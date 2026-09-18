# Langfuse Propagation

Langfuse를 통해 여러 에이전트 오케스트레이션 전파하는 방법 설명.

*한 개발자가 에이전트를 개발한다고 해보자. 문제는 단일 에이전트가 아니라 여러 에이전트가 합쳐진 에이전트 오케스트레이션 형태로 만들 생각이다.*

*여기에 더해 해당 개발자는 추후 확장성을 고려해 각 서브에이전트를 코드 기반 호출이 아니라 통신 기반 호출을 사용하려고 한다.(호출 방식은...자유롭게. a2a나 api나 mcp나 등등...)*

*에이전트 모니터링을 Langfuse로 한다고 했을 때, 원하는 trace 결과는 아마 다음과 같은 형태일 것이다.*

![Agent Ochestration Langfuse Trace](assets/images/agent_ochestration_trace.png)

*이런 형태로 만들기 위해서는 마스터 에이전트를 Langfuse에 기록할 때 사용한 Trace Context(Trace를 기록하기 위한 정보들)를 서브 에이전트에게 전파할 수 있어야 한다.*

*해당 장에서는 그 방법에 대해 이야기해보자.*

## Trace Propagation 필수 요소

Trace를 깨지지 않고 성공적으로 기록하기 위해서는 두가지 정보가 필수적으로 필요함.

- Trace-ID: 어떤 Trace에 기록할 것인가?
- Parent-Span-ID: 어떤 Span 하위로 들어갈 것인가?

기록될 Trace와 부모 Span이 정해지면, 해당 부모 Span 하위에서 본인 에이전트의 Span을 모두 기록하면 깔끔하게 기록됨.

*parent span & child span*

![parent span & child span](assets/images/span_tree.png)

## 형식 검증 규칙

Langfuse에 전달하는 trace_id/parent_span_id는 정해진 형식을 만족해야 한다.

- **Trace ID**: 32자리의 16진수 문자열(32 hex chars). 예: `abcdef1234567890abcdef1234567890`
- **Observation ID(Parent Span ID)**: 16자리의 16진수 문자열(16 hex chars). 예: `fedcba0987654321`

이 두 값을 헤더로 실어 보낼 땐 `traceparent` 하나의 문자열로 합쳐서 보낸다. [W3C Trace Context 스펙](https://www.w3.org/TR/trace-context/#traceparent-header)이 정한 형식은 다음과 같음.

`<version>-<trace-id>-<parent-id>-<flags>`

- **version**: 2자리 16진수. 스펙상 현재 유효한 값은 `00`뿐 — 그대로 `00`으로 고정해서 씀.
- **trace-id**: 위 Trace ID와 같은 값(32 hex chars). 전부 `0`이면 무효로 취급됨.
- **parent-id**: 위 Observation ID(Parent Span ID)와 같은 값(16 hex chars). 전부 `0`이면 무효로 취급됨.
- **flags**: 2자리 16진수 비트필드. 실무에서 신경 쓸 값은 sampled 비트 하나뿐 — 이 trace를 기록하겠다는 뜻으로 `01`을 씀. 직접 traceparent를 만들 때 `00`을 쓰면 하위 시스템이 이 trace를 안 남겨도 되는 것으로 해석할 수 있으므로, 새로 만들 땐 `01`로 고정.

예: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`

즉 직접 traceparent를 새로 만들 때는(예: 아래 "parent_span_id 교체") version/flags는 `00`/`01` 고정값을 쓰고, trace-id/parent-id 자리만 실제 값으로 갈아끼우면 됨.

## Trace Context 전달 방법

Trace Context를 실제 코드에 적용하는 방법은 크게 2가지임.

## Decorator

데코레이터는 해당 함수에 `langfuse_trace_id`, `langfuse_parent_observation_id`를 넣어주면 적용됨.

> [!IMPORTANT]
> 중요한 것은, 별도로 해당 인자들을 선언해줄 필요 없다는 것. 데코레이터가 인자를 알아서 처리한다.

```python
# Decorator의 경우
from langfuse.decorators import observe

# 데코레이터 적용
@observe()
def process_user_request(input_text):
    # 실제 함수 파라미터에는 langfuse_... 인자를 정의할 필요 없음.
    # 데코레이터가 가로채서 알아서 처리함.
    print(f"처리 중: {input_text}")
    return "완료"

# 외부(예: 프론트엔드, API Gateway 등)에서 전달받은 ID들
external_trace_id = "abcdef1234567890abcdef1234567890"
external_parent_span_id = "1234567890abcdef"

# 함수 호출 시 키워드 인자로 주입 (전파)
process_user_request(
    input_text="Hello",
    langfuse_trace_id=external_trace_id,                      # Trace ID 전파
    langfuse_parent_observation_id=external_parent_span_id    # Parent Span ID 전파
)
```

## Context Manager

Context Manager 방식을 적용할 땐 `trace_context`에 `trace_id`, `parent_span_id` 두 값을 넣어 전달하면 됨.

```python
from langfuse import get_client

langfuse = get_client()

# Use a predefined trace ID with trace_context parameter
with langfuse.start_as_current_observation(
    as_type="span",
    name="my-operation",
    trace_context={
        "trace_id": "abcdef1234567890abcdef1234567890",  # Must be 32 hex chars
        "parent_span_id": "fedcba0987654321"  # Optional, 16 hex chars
    }
) as observation:
    print(f"This observation has trace_id: {observation.trace_id}")
    # YOUR APPLICATION CODE HERE
```

## GenOS에서 Langfuse Context 전달 방법

1. 워크플로우: GenOS Config를 통해 환경변수로 langfuse trace parent를 전달할 수 있는 헤더를 허용 설정 후 헤더에 `traceparent`를 넣어 전달
2. A2A - 불가능: A2A에서는 GenOS가 헤더를 자체적으로 재구성할 수 없음. body도 변환할 수 없음.

워크플로우 경로(코드서빙 게이트웨이 경유 호출 포함)가 가능한 이유는 게이트웨이가 요청 헤더를 body와 마찬가지로 건드리지 않고 그대로 통과시키기 때문임.

헤더를 손대지 않으니 그 안에 실어 보낸 `traceparent`가 상대 에이전트의 라우터까지 그대로 도달함([`subagent_client.py`](codes/03_propagation/common/subagent_client.py) 참고). 더 이상 `trace_id`/`parent_span_id`를 body 필드로 실어 보내지 않음 — 표준 `traceparent` 헤더 하나로만 전파함.

반대로 A2A는 GenOS가 A2A 프로토콜 스펙에 맞춰 헤더/body를 직접 재구성하는 계층임. 그 과정에서 임의로 실은 헤더/body 필드는 사라짐. 그래서 propagation이 불가능함.

## 서브 에이전트를 호출할 때: parent_span_id 교체

받은 `traceparent`를 그대로 서브 에이전트에 넘기면 안 됨. trace_id는 같아야 하지만 parent-id는 지금 이 호출을 하는 자신의 span으로 바꿔야 함. 그대로 넘기면 서브 에이전트가 자신이 받았던 그 부모 span 아래로 붙어버려서, 그 사이에 있는 마스터 에이전트의 처리 과정(도구 호출 등)이 트리에서 빠짐.

그래서 서브 에이전트를 호출하는 시점(예: 도구 호출)의 현재 span에서 trace_id/observation_id를 읽어 parent-id 자리를 이 span의 id로 교체한 새 `traceparent`를 만들어 전달함.

```python
# agents/master_agent/agent.py::_execute_tool
client = get_client()
trace_id = client.get_current_trace_id()
parent_span_id = client.get_current_observation_id()  # 지금 이 tool span 자신의 id
traceparent = f"00-{trace_id}-{parent_span_id}-01" if trace_id and parent_span_id else None
result = _TOOL.run(instruction=instruction, traceparent=traceparent)
```

서브 에이전트는 이렇게 전달받은 `traceparent`를 그대로 `langfuse_trace_id`/`langfuse_parent_observation_id`로 넘기면 됨. 새 trace를 만드는 게 아니라, 전달받은 그 span 바로 아래에 자기 span을 이어붙이는 것.

## 예제 코드

- GenOS 워크플로우 경로로 `traceparent` 헤더를 이어받는 예: [`03_propagation`](codes/03_propagation)의 master 에이전트(`router.py`에서 헤더 추출, `agents/master_agent/service.py`의 `_parsed_traceparent`/`handle_turn`에서 파싱·이어붙이기)
- 서브 에이전트를 호출할 때 parent_span_id를 교체해 `traceparent`를 다시 만들어 전달하는 예: [`03_propagation`](codes/03_propagation)의 `agents/master_agent/agent.py`(`_execute_tool`), `agents/master_agent/tools.py`
- A2A 경유 호출은 위에서 설명했듯 불가능하므로 대응하는 예제 코드 없음.

