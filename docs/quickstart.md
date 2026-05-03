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

Parallel steps share the same `context.state` dict in v0.1. If two branches
write the same key, the last write wins.

## Optional Real LLM Calls

`Agent` uses LiteLLM only when you install the optional extra:

```bash
pip install "orchflow[litellm]"
```

Core tests and examples run offline with `orchflow.testing.MockAgent`.
