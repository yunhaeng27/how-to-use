# Langfuse 개요

## Langfuse란?

Agent 개발 시 에이전트의 플로우를 로깅, 모니터링, 평가 등등 할 수 있도록 해주는 도구임.

예를 들어 내가 간단한 바닐라 RAG Agent를 개발했다고 한다면, 분명 채팅 입력 -&gt; retrieve -&gt; prompt 생성 -&gt; LLM 답변 생성 -&gt; 출력 정도의 기본적인 flow가 있을건데,

langfuse를 사용하면 retrieve를 통해 어떤 문서들이 가져와졌고, 실제 LLM에 들어간 입력값은 어떻게 되고, 출력은 어떻게 되었으며, LLM이 에이전트라면 도구호출의 입력값과 출력값 등에 대한 것들도 모두 개별적으로 확인할 수 있음.

그에 더해 단순히 개발 상세 로그들만 확인할 수 있는 것이 아니라, 만들어진 에이전트를 그래프형태로 확인하고, 플로우 형태로 따라가면서 모니터링 및 로그 확인이 가능함.

[langfuse 예시(링크)](https://us.cloud.langfuse.com/project/cmu0rgd3m00g0ad0fcm8ahch3/traces/8126c48244c46e3e10cb131c4f0f4bb7?observation=955df6f6910eddb3)

*langfuse 에이전트 그래프*

![langfuse 에이전트 그래프](assets/images/graph_01.png)

langfuse의 주요 단어 및 로깅 방식에 대해 이해할 수 있어야 제대로된 로그 기록이 가능함.

`trace`:  워크플로우가 1회 실행하여 결과를 얻기까지의 경과(GenOS의 개념으로 보면 1턴)

`session`: Trace들의 모음. 에이전트가 멀티턴 등을 지원할때 해당 대화들을 저장한다고 생각하면 됨.

`observation`: 개별 동작 1회. 예: 리트리브, LLM 생성, 에이전트 동작 등. 개발에서는 함수 단위라고 보면 편할 듯. 동작 1회의 개념

*trace / session / observation 관계*

![trace / session / observation 관계](assets/images/observations-traces-sessions.png)

*observation 타입(span 종류)*

![observation 타입(span 종류)](assets/images/span_types.png)

방식별 실제 연동 방법은 [01_langfuse_예제.md](01_langfuse_예제.md)에서 확인할 수 있다.

