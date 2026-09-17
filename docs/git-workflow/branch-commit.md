## 브랜치 전략

Git Flow 변형 — `develop` 기본 브랜치, `main`은 프로덕션 릴리즈.

| 브랜치 | 용도 |
|--------|------|
| `main` | 프로덕션 릴리즈 |
| `develop` | 통합 기본 브랜치 — PR 대상 |
| `feat/<이슈번호>` | 신규 기능 |
| `fix/<이슈번호>` | 버그 수정 |
| `chore/<설명>` | 빌드·설정·인프라 |
| `refactor/<설명>` | 리팩터링 |
| `docs/<설명>` | 문서 |
| `ds/<설명>` | design-system 전용 |

---

## 커밋 메시지 규칙

```
<타입>: [<범위>] <요약> (#<이슈번호>)
```

### 타입

| 타입 | 설명 |
|------|------|
| `feat` | 신규 기능 |
| `fix` | 버그 수정 |
| `chore` | 빌드·설정·인프라 |
| `refactor` | 동작 변경 없는 코드 정리 |
| `docs` | 문서 추가·수정 |
| `style` | 포맷·공백 (로직 변경 없음) |
| `test` | 테스트 추가·수정 |

### 범위 (선택)

| 범위 | 의미 |
|------|------|
| `[frontend]` | Next.js 클라이언트 |
| `[design-system]` | @gena/design-system |
| `[services]` | Python BE 전체 |
| `[agent-service]` | 에이전트 서비스 |
| `[auth-service]` | 인증 서비스 |

### 예시

```
feat: [frontend] 슬라이드 에디터 폰트 변경 커맨드 추가 (#123)
fix: [design-system] ScrollArea vertical viewport 자식 div 스타일 교정
chore: 윈도우 로컬 풀스택 기동 환경 구축
```

---

## PR 규칙

- **base 브랜치**: `develop`
- **제목**: 커밋 메시지 형식과 동일 (`feat: [범위] 요약`)
- **이슈 연결**: PR 본문에 `Closes #<이슈번호>` 필수
- **리뷰**: 최소 1인 승인 후 머지
- **develop 직접 커밋 금지** — 반드시 PR 경유

---

## 이슈 번호 규칙

- 모든 작업은 GitHub 이슈 선생성 후 시작
- 브랜치명·커밋·PR 모두 이슈 번호 포함
- 이슈 없는 커밋 금지 (추적 불가)
