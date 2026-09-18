---
icon: diagram-subtask
# TODO: 실제 GitBook 스페이스 연결 후 metaLinks.alternates 채우기
---

# GenOS Langfuse 연동

GenOS는 서빙(모델 서빙, 코드 서빙)이 호출될 때마다 자체 Langfuse에 요청 trace를 기록하고, 이 내용을 이용 로그 화면에서 Langfuse 형태로 보여줍니다. 

Code Serving을 개발할 때 직접 작성한 계측 코드를 이 GenOS 자체 trace에 이어 붙일 수도 있습니다.

이 섹션에서는 이용 로그 화면에서 Langfuse 형태의 로그를 확인하는 방법과, 코드에서 이 trace에 직접 연결하는 방법을 안내합니다. 

Langfuse 자체의 개념(trace/session/observation)이나 SDK 설치, 범용 계측 방식처럼 GenOS와 무관한 내용은 다루지 않습니다. 

필요하면 Langfuse 공식 가이드를 참고하세요.
