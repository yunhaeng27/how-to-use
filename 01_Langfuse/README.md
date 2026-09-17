# Langfuse 매뉴얼

> [!IMPORTANT]
> GenOS에서 "Langfuse"라고 하면 크게 두 가지를 가리킴.
>
> - GenOS 자체가 내부적으로 사용하는 Langfuse. GenOS에서 서빙이 실행될 때마다 로깅. —&gt; [GenOS Langfuse](#genos-langfuse)
> - Code Serving 등 개발 과정에서 사용자가 직접 외부 Langfuse를 연결해 로깅하는 것. —&gt; [외부 Langfuse 연동](#외부-langfuse-연동)

## GenOS Langfuse

GenOS는 서빙(모델&amp;코드)의 이용 로그를 `langfuse`로 보여줌.

이용 로그는 다음과 같이 볼 수 있음. 

1. `서빙` &gt; `코드 서빙(또는 모델 서빙)` 클릭 &gt; 보려는 서빙 더블클릭

*코드 서빙 &gt; 보려는 서빙 더블클릭*

![코드 서빙 > 보려는 서빙 더블클릭](assets/images/genos_code_serving.png)

2. `이용 로그` &gt; 목록 중 보려는 로그 클릭

*이용 로그 &gt; 목록 중 보려는 로그 클릭*

![이용 로그 > 목록 중 보려는 로그 클릭](assets/images/genos_code_serving_log.png)

3. langfuse 형태의 로그 화면 확인

*GenOS langfuse log 화면*

![GenOS langfuse log 화면](assets/images/genos_langfuse_log.png)

## 외부 Langfuse 연동

GenOS 상에서 개발 시 외부 langfuse 연동 방법에 대한 내용은 아래 내용들 확인.

코드 서빙 프로젝트 자체의 구조(진입점, 자동 노출 라우트, 커스텀 앱 구성)가 궁금하면 [99_GenOS/00_code_serving.md](../99_GenOS/00_code_serving.md) 먼저 확인.

## 빠른 시작

"코드 서빙에 Langfuse trace만 우선 붙이고 싶다"면 아래 2단계만 하면 됨.

1. **환경 변수 3개 설정** (langfuse 가입 후 발급): `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
2. **계측하려는 함수에 `@observe` 데코레이터 부착**

```python
from langfuse import observe

@observe(as_type="span", name="rag-pipeline")   # 최상위 호출 -> trace 루트가 된다
def run_rag_pipeline(question: str) -> str:
    ...
```

`@observe`는 함수의 인자/반환값을 그대로 input/output으로 캡처하는 방식이라, 콜백/이벤트 핸들러처럼 입출력이 함수 경계로 깔끔히 떨어지지 않는 경우에는 맞지 않음. 

이때는 [01_langfuse_예제](01_langfuse_예제.md)의 Context Manager(`with client.start_as_current_observation(...)`) 또는 Manual Lifecycle(`start_observation()` + `.update()`/`.end()`) 방식을 확인.

필요에 따라 아래로 확장:

- 데코레이터말고 다른 연결 방식이 궁금하다 -&gt; [01_langfuse_예제](01_langfuse_예제.md)
- 멀티턴 대화를 하나의 세션으로 묶고 싶다 -&gt; [04_langfuse_session](04_langfuse_session.md)
- 멀티 에이전트 간 trace를 전파하고 싶다 -&gt; [03_langfuse_propagation](03_langfuse_propagation.md)
- Langfuse Score로 응답 품질을 평가하고 싶다 -&gt; [02_langfuse_평가](02_langfuse_평가.md)

## 전체 가이드 목록

- [00_langfuse_개요](00_langfuse_개요.md) — Langfuse 개념
- [01_langfuse_예제](01_langfuse_예제.md) — RAG 파이프라인 계측 예제 코드
- [02_langfuse_평가](02_langfuse_평가.md) — Langfuse Score 기반 평가
- [03_langfuse_propagation](03_langfuse_propagation.md) — 멀티 에이전트 trace 전파
- [04_langfuse_session](04_langfuse_session.md) — Langfuse session과 GenOS 세션 연동

