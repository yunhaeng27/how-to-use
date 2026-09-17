# Langfuse Session

여기서 다루는 "세션"은 Langfuse의 `session`(trace들을 묶는 단위)이다. 

GenOS가 멀티턴 대화를 위해 넘겨주는 `x-genos-session-id`와 이를 이용한 대화 기록 관리는 [99_GenOS/01_session.md](../99_GenOS/01_session.md)에서 다루고,

해당 헤더를 활용해 langfuse session 적용은 아래 내용을 참고.

## Langfuse 복습

[00_langfuse_개요.md](00_langfuse_개요.md)에서 정의했듯 `session`은 trace들의 모음. 하나의 trace가 GenOS 기준 1턴이라면, 세션은 여러 턴(대화 전체)을 묶은 것.

session_id를 태깅해두면 Langfuse UI에서 같은 대화에 속한 trace들을 한 화면에서 이어서 확인할 수 있다.(대화 흐름 파악하기 좋다는 뜻)

멀티턴 에이전트를 디버깅할 때 턴 하나만 보고는 원인을 알기 어려운 경우(이전 턴의 답변이 이번 턴 프롬프트에 잘못 들어간 경우 등) session 단위로 봐야 함.

## session_id 부여하는 방법

session_id는 `langfuse.propagate_attributes`로 부여한다.

```python
from langfuse import propagate_attributes

with propagate_attributes(session_id=session_id):
    # 이 블록 안에서 생성되는 trace/span 전부에 session_id가 태깅됨
    ...
```

이 방식의 핵심은 span/generation을 실제로 만드는 방식(Context Manager / Decorator / Manual Lifecycle. 잘 모르면 [01_langfuse_예제.md](01_langfuse_예제.md#5-코드-적용) 참고)과 무관하다는 것 — `propagate_attributes`는 그 바깥을 한 겹 더 감싸는 역할만 하므로 안쪽 코드가 셋 중 무엇이든 그대로 적용된다.

## GenOS 세션과 연동하기

GenOS는 워크플로우 호출 시 `x-genos-session-id` 헤더로 세션 ID를 넘겨준다([99_GenOS/01_session.md](../99_GenOS/01_session.md) 참고). 

이 값을 그대로 `propagate_attributes(session_id=...)`에 넣으면 GenOS 기준 한 대화가 Langfuse에서도 하나의 session으로 묶인다 — 

즉 같은 ID 하나를 두 군데(GenOS 대화 기록 조회/저장 키 + Langfuse session_id)에 재사용하는 것.

```python
# API 헤더로 부터 세션 ID 추출
session_id = request.headers.get("x-genos-session-id")
return await handle_turn(payload, session_id=session_id)
```

```python
# 추출된 세션 ID를 propagate_attributes로 전달
with propagate_attributes(session_id=session_id):
    agent_result = await run_agent(payload.question, history=history)
```

헤더가 없으면(로컬 curl 등) session_id도 `None`이 되고, `propagate_attributes(session_id=None)`은 아무것도 태깅하지 않으므로 안전하게 no-op.

## 예제 코드

- session_id를 Context Manager / Decorator / Manual Lifecycle 방식별로 부여하는 코드: [`01_rag_pipeline`](codes/01_rag_pipeline)
- GenOS `x-genos-session-id`와 연동한 실제 예: [`03_propagation`](codes/03_propagation)의 master 에이전트(`router.py`, `agents/master_agent/service.py`)

