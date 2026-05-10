# Orchflow

Orchflow is a lightweight Python framework for readable multi-agent pipelines.
It gives you sequential, parallel, and conditional orchestration without making
you model everything as a graph.

```python
from orchflow import Flow, StepContext, step


@step
async def research(input: str, context: StepContext) -> str:
    return f"research about {input}"


@step
async def write(input: str, context: StepContext) -> str:
    return f"draft based on {context.previous}"


result = await Flow([research, write]).run("agent orchestration")
print(result.output)
```

Watch the same flow while it runs:

```python
async for event in Flow([research, write]).events("agent orchestration"):
    print(event.type, event.step_name)
```

## Why

Plain Python chaining is easy to read but thin on retries, parallelism, and
tracing. Heavy graph runtimes are powerful but can feel like too much for simple
pipelines. Orchflow aims for the middle: small API, predictable state, useful
traces, and offline-testable agent workflows.

## Features

- Sequential flows
- Parallel step groups
- Conditional routing
- Retry policies
- Shared run state
- Flat structured traces
- Live flow events with `Flow.events(...)`
- Public `Agent` with optional LiteLLM support
- Offline testing helpers under `orchflow.testing`

## Install

[![PyPI version](https://img.shields.io/pypi/v/orchflow.svg)](https://pypi.org/project/orchflow/)
[![Python versions](https://img.shields.io/pypi/pyversions/orchflow.svg)](https://pypi.org/project/orchflow/)
[![CI](https://github.com/awesome-pro/orchflow/actions/workflows/ci.yml/badge.svg)](https://github.com/awesome-pro/orchflow/actions/workflows/ci.yml)

```bash
pip install orchflow
```

Optional LiteLLM-backed agents:

```bash
pip install "orchflow[litellm]"
```

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check
uv run ruff format --check
uv run pyright
```

## Publishing

Publish to TestPyPI first with the manual GitHub Actions workflow in
`.github/workflows/publish-testpypi.yml`. Real PyPI releases are tag-based
through `.github/workflows/publish-pypi.yml`.

See `docs/publishing.md` for the full release process.

## Source Of Truth

Project decisions live in `AGENTS.md`. Implementation follows that document.
