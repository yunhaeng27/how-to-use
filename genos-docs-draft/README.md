# GenOS Langfuse 연동 가이드 초안 (genos-docs 이관용)

이 디렉토리는 `01_Langfuse`, `99_GenOS`의 내용 중 GenOS 화면/기능과 직접 연결되는 부분만 골라 `genos-docs`(GitBook 공식 사용자 문서) 이관 포맷에 맞게 재작성한 초안이다.

**아직 실제 `genos-docs` 저장소에는 반영되지 않았다.** 이 저장소(`refactor-gitbook-style`)의 별도 디렉토리에만 존재하며, 실제 이관 시에는 아래 내용을 `genos-docs` 저장소로 그대로 복사해 넣는 것을 전제로 경로를 맞춰 두었다(`genos-docs-draft/advanced-tutorials/...` → `genos-docs/advanced-tutorials/...`).

적용한 지침:

- 포맷/구조: [docs/genos-docs-migration/01-format-structure.md](../docs/genos-docs-migration/01-format-structure.md)
- 콘텐츠 선별/문체: [docs/genos-docs-migration/02-content-curation.md](../docs/genos-docs-migration/02-content-curation.md)
- 실제 이관 절차: [docs/genos-docs-migration/03-workflow-governance.md](../docs/genos-docs-migration/03-workflow-governance.md)

---

## 배치 위치와 이유

`advanced-tutorials/guides/observability/` 아래에 새 섹션으로 배치했다.

- Langfuse 연동은 Code Serving 개발자가 자신의 계측 코드를 GenOS 이용 로그(trace)에 연결하는 절차를 다루므로, 개발자 대상 심화 콘텐츠가 모이는 `advanced-tutorials`가 `basic-tutorials`보다 적합하다.
- `admin-management`는 관리자 전용(`admin-only`) 사이트에만 노출되는데, 이 내용은 일반 개발자도 봐야 하므로 `admin-management` 밑에는 넣지 않았다.
- `advanced-tutorials` 아래에 두면 `default`·`client-basic` 사이트 모두에 노출된다.
- 기존 `advanced-tutorials/guides/serving/api-log.md`(서빙 이용 로그·인증키 확인)와 인접하지만 다루는 내용이 다르므로(전자는 API 호출 인증키 확인, 이 초안은 코드 trace 연결) 같은 폴더에 합치지 않고 형제 섹션(`observability/`)으로 분리했다.

---

## 포함/제외 판단 요약

| 소스 문서 | 처리 | 근거 |
|-----------|------|------|
| `01_Langfuse/README.md`의 "GenOS Langfuse" 절 | 포함(재구성) → `usage-log.md` | GenOS 화면 조작 절차 |
| `99_GenOS/02_trace.md` | 포함(재구성) → `code-trace-integration.md` 1~4절 | GenOS 자체 Langfuse 환경변수, `traceparent`, `x-genos-trace-id` 무시, parent span 제약 — GenOS 특유의 내용 |
| `01_Langfuse/04_langfuse_session.md`의 "GenOS 세션과 연동하기" 절 | 포함(요약) → `code-trace-integration.md` 5절 | `x-genos-session-id`를 Langfuse session ID로 재사용하는 절차 |
| `01_Langfuse/03_langfuse_propagation.md`의 "GenOS에서 Langfuse Context 전달 방법" 절 | 포함(요약) → `code-trace-integration.md` 6절 | 워크플로우/A2A 호출 방식에 따른 GenOS 특유의 전파 제약 |
| `01_Langfuse/00_langfuse_개요.md` (trace/session/observation 개념) | 제외(A) | GenOS와 직접 연결점이 없는 범용 개념 설명 |
| `01_Langfuse/01_langfuse_예제.md` (SDK 설치, 3가지 계측 방식 코드 전체) | 제외(A) | 범용 SDK 사용법과 예제 구현 세부. GenOS 연동과 무관 |
| `01_Langfuse/02_langfuse_평가.md` (Score/Experiments) | 제외(A) | Langfuse 자체 평가 기능. 문서 자체에도 "GenOS > 평가 메뉴 이야기가 아님"이라고 명시되어 있음 |

제외한 내용은 소스 저장소(`01_Langfuse`)에 그대로 남아 있으므로, genos-docs 독자 중 개발 매뉴얼 접근 권한이 있는 사람은 별도로 확인할 수 있다. genos-docs 쪽에서는 다른 저장소를 직접 링크하지 않는다는 원칙([01-format-structure.md](../docs/genos-docs-migration/01-format-structure.md#링크-규칙)) 때문에 하이퍼링크 대신 "사내 개발 매뉴얼 참고"처럼 텍스트로만 안내했다.

---

## 남은 TODO

- [ ] `usage-log.md`의 스크린샷을 실제 GenOS 화면에서 새로 캡처하고, `.gitbook/assets/`로 옮길 때 문서 식별 접두사를 붙여 저장(`image (3).png` 같은 범용 이름 금지)
- [ ] `metaLinks.alternates`는 실제 GitBook 스페이스 연결 후 채우기(현재는 각 문서에 `icon`만 채우고 TODO 주석으로 남겨둠)
- [ ] 대상 버전 브랜치 확정 후 `SUMMARY.template.md`에 아래 형태로 등록(`SUMMARY.template.md`는 이 저장소가 아닌 `genos-docs` 저장소 파일이므로 실제 작업은 그쪽에서 진행)

```markdown
      * [모델 서빙](advanced-tutorials/guides/serving/README.md)
        * [멀티모달 서빙](advanced-tutorials/guides/serving/multi-modal-serving.md)
        * [멀티테넌시](advanced-tutorials/guides/serving/multitenancy.md)
        * [서빙 로그 확인](advanced-tutorials/guides/serving/api-log.md)
      * [GenOS Langfuse 연동](advanced-tutorials/guides/observability/README.md)
        * [이용 로그에서 Langfuse 로그 확인](advanced-tutorials/guides/observability/usage-log.md)
        * [코드에서 이용 로그에 Trace 연결하기](advanced-tutorials/guides/observability/code-trace-integration.md)
```

- [ ] [03-workflow-governance.md](../docs/genos-docs-migration/03-workflow-governance.md)의 이관 작업 절차 체크리스트에 따라 이슈 생성 → 대상 버전 브랜치 확인 → 이슈 브랜치 생성 → 로컬 빌드 검증 → PR 진행
