# Langfuse Evaluation Example

02_langfuse_평가.md의 예제 코드

## 로컬 실행

1. 가상환경 생성 및 의존성 설치

```bash
cd 01_Langfuse/codes/02_evaluation
uv venv
uv pip install -r requirements.txt
```

2. 환경 변수 설정

`.env.example`을 복사해 `.env`를 만들고 값을 채운다.

```bash
cp .env.example .env
```

| 환경변수 | 설명 | 비고 |
| --- | --- | --- |
| `GENOS_BEARER_TOKEN` | GenOS 모델 서빙 인증키 | 사용하려는 모델 서빙의 인증키 |
| `GENOS_URL` | 사용하는 GenOS 주소 | 예: `https://genos.genon.ai` |
| `GENOS_SERVING_ID` | 호출하려는 모델 serving id | GenOS 모델 서빙에서 확인 가능 |
| `GENOS_MODEL` | 호출하려는 모델명 | |
| `LANGFUSE_HOST` / `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | 외부 Langfuse 연동 값(선택) | 세 값 모두 넣어야 trace/score 계측이 켜짐 |

3. 서버 실행

```bash
uv run uvicorn main:app --port 8000
```

4. 동작 확인

`/agents/rag/chat`에 질문을 보내 응답과 함께 groundedness score가 기록되는지 확인.

```bash
curl -X POST http://localhost:8000/agents/rag/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "질문 내용"}'
```

연결한 Langfuse 프로젝트에서 `rag-agent-turn` span에 `groundedness` score가 기록됐는지 확인. `LANGFUSE_*` 값을 채우지 않았으면 score는 계산되지만 Langfuse로는 전송되지 않는다.

## GenOS 코드 서빙

1. 코드 스페이스 생성 > 코드 서빙 생성하여 git url 생성 > 코드 스페이스에 레포 복사 > 해당 예제 코드 전체를 해당 serving id 하위로 복사
2. 변경 사항 git commit & push
3. GenOS에서 코드 서빙 > 해당 커밋 해시 기반 리비전 생성
4. 리비전 상세 페이지 > 환경 변수 설정에서 `.env.example`의 값들을 모두 추가 > 리비전 배포
5. 배포가 정상 상태가 되면 GenOS 채팅에서 해당 에이전트를 연결해 질문을 보내고 응답 확인. 연결한 Langfuse 프로젝트에서 `rag-agent-turn` span에 `groundedness` score가 기록됐는지 확인.

> [!NOTE]
> 이 에이전트를 [`03_propagation`](../03_propagation) 예제처럼 다른 마스터 에이전트가 워크플로우(서브에이전트)로 호출하게 하려면, 리비전 상세 > 컨테이너 서비스에서 `워크플로우로 사용`을 켜고 전용 Bearer 토큰을 발급해야 함. 자세한 절차는 [`03_propagation/README.md`](../03_propagation/README.md)의 "2. 02를 워크플로우로 전환 + 토큰 발급" 참고.
