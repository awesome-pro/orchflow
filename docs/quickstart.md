# Quickstart

Orchflow lets you build readable async pipelines with plain Python functions.
Core Orchflow has no required runtime dependencies.

## Install

```bash
pip install orchflow
```

For local development in this repo:

```bash
uv sync --extra dev
```

## A Sequential Flow

```python
import asyncio

from orchflow import Flow, StepContext, step


@step
async def research(input: str, context: StepContext) -> str:
    return f"research about {input}"


@step
async def write(input: str, context: StepContext) -> str:
    return f"article based on {context.previous}"


async def main() -> None:
    flow = Flow([research, write])
    result = await flow.run("agent orchestration")
    print(result.output)


asyncio.run(main())
```

The first argument, `input`, is always the original `flow.run(...)` input.
Use `context.previous` for the previous step output.

## Live Events

Use `flow.events(...)` when you want live observability instead of waiting for
the final `FlowResult`.

```python
async for event in flow.events("agent orchestration"):
    print(event.type, event.step_name, event.attempt)
```

The final event is `flow_completed` on success or `flow_failed` on failure. That
event carries the same `FlowResult` shape used by `flow.run()`.

## Parallel Steps

```python
flow = Flow([
    collect_input,
    [research_web, research_docs],
    synthesize,
])
```

Parallel outputs become a dict keyed by step name:

```python
{"research_web": "...", "research_docs": "..."}
```

Parallel steps share the same `context.state` dict in v0.5. If two branches
write the same key, the last write wins.

## Human Review

Use `human_input(...)` for a lightweight review point:

```python
from orchflow import human_input

review = human_input(
    lambda ctx: f"Review this draft:\n{ctx.previous}\nDecision: ",
    name="review",
)
```

Without a custom provider, the step reads from stdin. In applications and tests,
pass a sync or async `provider(prompt, context)` callback.

## Checkpoint And Resume

Use `JsonCheckpointStore` when a workflow should resume after a failure:

```python
from orchflow import JsonCheckpointStore

store = JsonCheckpointStore("orchflow-checkpoint.json")
result = await flow.run(
    "agent orchestration",
    checkpoint=store,
    raise_on_error=False,
)
if not result.success:
    resumed = await flow.resume(store)
```

Checkpoints are JSON files saved after completed top-level flow items. Completed
checkpoints remain on disk for inspection.

## Optional Real LLM Calls

`Agent` uses LiteLLM only when you install the optional extra:

```bash
pip install "orchflow[litellm]"
```

Core tests and examples run offline with `orchflow.testing.MockAgent`.

For structured outputs:

```python
from orchflow import Agent, AgentConfig

agent = Agent(
    name="extractor",
    role="Extract structured data.",
    config=AgentConfig(model="gpt-4o-mini", temperature=0),
)

data = await agent.run_structured(
    "Ada works at OpenAI.",
    schema={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "company": {"type": "string"},
        },
        "required": ["name", "company"],
    },
)
```
