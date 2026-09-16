"""GenOS 예제 에이전트 모음 FastAPI 앱.

에이전트를 추가할 때마다 ``agents/<name>/router.py`` 를 만들고 여기서 ``include_router``
한다.
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()  # common/genos_client.py, common/langfuse_utils.py 가 import 시점에 env를 읽으므로 가장 먼저 실행

from fastapi import FastAPI

from agents.rag_agent.router import router as rag_agent_router

app = FastAPI(title="GenOS Agent Examples")
app.include_router(rag_agent_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
