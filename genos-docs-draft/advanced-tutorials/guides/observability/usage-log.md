---
icon: sim-card
# TODO: 실제 GitBook 스페이스 연결 후 metaLinks.alternates 채우기
---

# 이용 로그에서 Langfuse 로그 확인

GenOS는 서빙(모델 서빙, 코드 서빙)이 호출될 때마다 자체 Langfuse에 요청 로그를 기록하고, 이 로그를 **이용 로그** 화면에서 Langfuse 형태로 보여줍니다.

> 아래 스크린샷은 실제 GenOS 화면으로 교체되어야 하는 자리표시자입니다. 캡처 후 `.gitbook/assets/`에 문서를 식별할 수 있는 접두사(`genos-langfuse-usage-log-*`)를 붙여 저장하세요.

## 이용 로그 확인 절차

1. **서빙 > 코드 서빙**(또는 모델 서빙) 메뉴에서 확인하려는 서빙을 더블 클릭합니다.

<figure><img src="../../../.gitbook/assets/genos-langfuse-usage-log-01-serving-detail.png" alt="코드 서빙 상세 화면 진입"><figcaption><p>서빙 상세 화면 진입</p></figcaption></figure>

2. **이용 로그** 탭에서 목록 중 확인하려는 로그를 클릭합니다.

<figure><img src="../../../.gitbook/assets/genos-langfuse-usage-log-02-log-list.png" alt="이용 로그 목록 화면"><figcaption><p>이용 로그 목록에서 로그 선택</p></figcaption></figure>

3. Langfuse 형태의 로그 화면에서 trace 상세 내용을 확인합니다.

<figure><img src="../../../.gitbook/assets/genos-langfuse-usage-log-03-trace-detail.png" alt="Langfuse 형태 trace 상세 화면"><figcaption><p>Langfuse 형태의 trace 상세 화면</p></figcaption></figure>

Code Serving 안에서 직접 계측 코드를 추가하면 이 화면의 trace 안에 자식 span으로 이어 붙일 수 있습니다. 방법은 [코드에서 이용 로그에 Trace 연결하기](code-trace-integration.md) 문서를 참고하세요.

서빙 API를 호출한 인증키 확인 등 이용 로그 화면의 다른 활용법은 [서빙 로그 확인](../serving/api-log.md) 문서를 참고하세요.
