# Langfuse Score 예제

langfuse를 통해 evaluator를 정의하고 score 평가를 진행하는 방법에 대하여 기술.

GenOS &gt; 평가 &gt; 평가지표 &gt; Langfuse를 이야기하는 것이 아님.

Code Serving 과정에서 Langfuse를 에이전트와 연동하기 위한 가이드 설정.



## Score

Langfuse의 Score는 Span별로 로깅을 진행할 수 있음.

`score_current_trace`를 사용하면 현재 설정된 trace로 scoring를 기록할 수 있음.

```
# 02_evaluation 에이전트 코드 일부
# <tracing 순서>
# 1. @observe데코레이터를 통해 rag-agent-turn이라는 이름으로 span 생성
# 2. run_agent가 실행되며 해당 함수 내부에서 실행되는 @observe 데코레이팅 된 함수들 기반 span 생성
# 3. evaluate_groundedness 함수 실행되며 내부 tracing 생성
# 4. score_current_trace : rag-agent-turn span에 스코어 기록
@observe(as_type="span", name="rag-agent-turn")
async def _run_traced_turn(payload: RagAgentRequest) -> RagAgentResponse:
    agent_result = await run_agent(payload.question)
    eval_result = await evaluate_groundedness(
        payload.question, agent_result.retrieved_documents, agent_result.answer
    )

    get_client().score_current_trace(
        name="groundedness",
        value=eval_result["score"],
        comment=eval_result["reasoning"],
    )
```

해당 방법은 매 agent가 실행될때마다 scoring이 자동으로 기록되므로 운영 배포 시 필요없는 스코어링인 경우에는 어울리지 않을 수 있음.(혹은 비동기 scoring을 사용하거나)

-&gt; 이땐 어떻게 하느냐?

`create_score`를 통해서 원하는 trace에 score를 기록할 수 있음.

```
from langfuse import get_client
langfuse = get_client()

langfuse.create_score(
    name="correctness",
    value=0.9,
    trace_id="trace_id_here",
    observation_id="observation_id_here", # optional
    data_type="NUMERIC", # optional, inferred if not provided
    comment="Factually correct", # optional
)
```

단발성 trace에 대한 score를 생성하는 것이 아니라 데이터셋에 기반하여 에이전트 평가나 실험을 하려면 `experiments`기능을 사용할 것.

## Experiments

데이터셋을 기반으로 Agent를 실행해서 준비한 데이터셋에 대해 Agent 출력값을 생성하거나, Evaluator를 기반으로 test 점수를 기록 및 평가

크게 3단계로 나뉨.

1. langfuse 클라이언트 연결
2. 데이터셋 설정
3. 실험 진행

&lt;데이터셋을 생성하여 실험하는 경우&gt;

```python
from langfuse import get_client
from langfuse.openai import OpenAI

# Initialize client
langfuse = get_client()

# Define your task function
def my_task(*, item, **kwargs):
    question = item["input"]
    response = OpenAI().chat.completions.create(
        model="gpt-4.1", messages=[{"role": "user", "content": question}]
    )

    return response.choices[0].message.content


# Run experiment on local data
local_data = [
    {"input": "What is the capital of France?", "expected_output": "Paris"},
    {"input": "What is the capital of Germany?", "expected_output": "Berlin"},
]

result = langfuse.run_experiment(
    name="Geography Quiz",
    description="Testing basic functionality",
    data=local_data,
    task=my_task,
)

# Use format method to display results
print(result.format())
```

&lt;langfuse에 데이터셋이 있는 경우&gt;

```python
from langfuse import get_client
from langfuse.openai import OpenAI

# Initialize client
langfuse = get_client()

# Define your task function
def my_task(*, item, **kwargs):
    question = item.input # `run_experiment` passes a `DatasetItem` to the task function. The input of the dataset item is available as `item.input`.
    response = OpenAI().chat.completions.create(
        model="gpt-4.1", messages=[{"role": "user", "content": question}]
    )

    return response.choices[0].message.content

# Get dataset from Langfuse
dataset = langfuse.get_dataset("my-evaluation-dataset")

# Run experiment directly on the dataset
result = dataset.run_experiment(
    name="Production Model Test",
    description="Monthly evaluation of our production model",
    task=my_task # see above for the task definition
)

# Use format method to display results
print(result.format())
```

