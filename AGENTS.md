# AGENTS.md - Orchflow Project Guide

This document is the source of truth for Orchflow. Code follows this document,
not the other way around.

## What Is Orchflow?

Orchflow is a lightweight Python framework for readable multi-agent pipelines.
It sits between plain Python function chaining and graph-heavy agent runtimes.

The goal for v0.3 is a small, reliable workflow microframework that makes
sequential, parallel, and conditional agent pipelines easy to write, test,
inspect, observe, and pause for lightweight human input.

One-line pitch:

> The simplest way to build readable multi-agent pipelines in Python.

## Scope For v0.3

Included:

- Sequential flows
- Parallel step groups
- Conditional branching
- Retry policy
- Shared mutable state
- Flat structured traces
- Live flow lifecycle events
- Lightweight human input gates
- Public `Agent`
- Offline tests and examples
- Optional LiteLLM-backed real-agent example
- Updated README, quickstart, and this `AGENTS.md`

Out of scope:

- Streaming
- Checkpointing and resume
- Memory
- Tool-calling loops
- MCP tools
- Visual trace UI
- Durable agent state

Validation:

- Empty flows are invalid and raise `ValueError`.
- Step names must be unique within a flow.
- Parallel step groups must contain at least one step.
- Nested parallel step groups are invalid and raise `TypeError`.

## Public API

Top-level exports from `orchflow`:

- `Agent`
- `Flow`
- `step`
- `condition`
- `StepContext`
- `RetryPolicy`
- `FlowResult`
- `StepTrace`
- `FlowEvent`
- `human_input`
- `FlowExecutionError`

Testing helpers live under `orchflow.testing` only:

- `MockAgent`
- `CallableAgent`

## Core Concepts

### Agent

An `Agent` is a stateless, role-based LLM helper. It keeps the common multi-agent
case simple while leaving orchestration in the `Flow`.

The core `Agent.run(prompt, context=None)` API supports prompt-only calls through
optional LiteLLM integration. LiteLLM is not a required runtime dependency.

Tool-calling loops, MCP tools, memory, and durable agent state are not part of
v0.3.

### Step

A `Step` is a single unit of work in a flow. Users define steps with the `@step`
decorator.

The step function signature stays:

```python
async def my_step(input: str | dict, context: StepContext) -> str | dict:
    ...
```

Important behavior:

- The first `input` argument is always the original `flow.run(...)` input
  throughout the flow.
- Previous step output is accessed through `context.previous`.
- Shared run state is accessed through `context.state`.
- Steps may be async or sync. Sync steps are run in a worker thread.

### Flow

A `Flow` orchestrates steps. It accepts a list containing step functions,
parallel step groups, and conditions.

Sequential example:

```python
flow = Flow([research_step, write_step, edit_step])
result = await flow.run("AI agents in 2026")
```

Parallel example:

```python
flow = Flow([
    collect_input,
    [research_web, research_docs],
    synthesize,
])
```

Conditional example:

```python
flow = Flow([
    classify,
    condition(
        when=lambda ctx: ctx.previous == "technical",
        then=technical_writer,
        otherwise=general_writer,
    ),
])
```

### State

`context.state` is one shared mutable dictionary for the run.

Parallel branches share the same state dict in v0.3. If multiple branches write
the same key, the behavior is last-write-wins. There is no deep-copy isolation
and no state conflict error in v0.3.

### Human Input

`human_input(...)` creates a normal `Step` that pauses a flow and returns text
from a human reviewer.

```python
review = human_input(
    lambda ctx: f"Review this draft:\n{ctx.previous}\nDecision: ",
    name="review",
)
```

Behavior:

- `human_input(...)` returns a `Step`.
- The first step argument remains the original `flow.run(...)` input.
- The prompt may be a string or a callable that receives `StepContext`.
- The returned human response becomes the step output.
- `context.previous`, `context.state`, and metadata are available while building
  the prompt and inside custom providers.
- If no provider is passed, the helper reads from stdin using
  `asyncio.to_thread(input, prompt_text)`.
- Custom providers may be sync or async.
- Provider and stdin failures are normal step failures and use existing retry,
  trace, and event behavior.

v0.3 human input is intentionally text-only. It does not include structured
approval objects, abort-on-reject behavior, durable resume, or a web UI.

## Tracing

Every executed step creates one flat `StepTrace`.

Parallel steps produce separate trace entries. Those trace entries share the same
`parallel_group_id`. Trace format is never nested.

Failed attempts are traceable. Each attempt records:

- `step_name`
- `input`
- `output`
- `error`
- `attempt`
- `parallel_group_id`
- `duration_seconds`
- `started_at`
- `ended_at`

## Events

`Flow.events(input)` runs the same engine as `Flow.run(input)` and yields live
`FlowEvent` objects.

Event types:

- `flow_started`
- `step_started`
- `step_completed`
- `step_failed`
- `retry_scheduled`
- `flow_completed`
- `flow_failed`

`Flow.events()` streams orchestration lifecycle events, not LLM tokens.

`Flow.run()` behavior must remain unchanged.

## Failure Behavior

Retries are configured with `RetryPolicy` or step-level retry settings.

By default, `Flow.run()` raises `FlowExecutionError` after the final failed
attempt. The exception includes the failed step, original exception, and partial
`FlowResult`.

When `Flow.run(..., raise_on_error=False)` is used, the flow returns
`FlowResult(success=False)` instead.

## Package And Tooling

- Public package and import name: `orchflow`
- Python support: 3.11+
- Runtime dependencies for core: none
- Optional model extra: `orchflow[litellm]`
- Dev tooling: `uv`, `pytest`, `pytest-asyncio`, `ruff`, `pyright`
- Packaging: `pyproject.toml`
- License: MIT

## Release Policy

- TestPyPI publishes manually through `.github/workflows/publish-testpypi.yml`.
- Real PyPI publishes from Git tags through `.github/workflows/publish-pypi.yml`.
- Release tags use `vMAJOR.MINOR.PATCH`, for example `v0.1.1`.
- The tag must match `project.version` in `pyproject.toml`.
- `src/orchflow/__init__.py` `__version__` must also match.
- PyPI versions are immutable; never try to republish an existing version.

## Roadmap

### 0.1.1 - Release Polish And DX

- Tag-based PyPI publishing.
- Publishing documentation.
- Changelog.
- Stronger README examples.
- Package metadata and badge polish.
- Built-wheel import test.
- GitHub issue templates.

### 0.2.0 - Events And Streaming

- Add a flow event iterator for live observability.
- Emit step lifecycle, retry, and flow lifecycle events.
- Keep `Flow.run()` behavior unchanged.

### 0.3.0 - Human Review

- Add `human_input(...)` step helper with callback and stdin support.
- Keep human review text-only; users route with `condition(...)`.
- Reuse existing trace, retry, and event behavior without new event types.

### 0.4.0 - Checkpoints

- Add lightweight JSON checkpoint and resume support.

## Test Requirements

The test suite must verify:

- Original input is passed as the first argument to every step.
- `context.previous` changes after each step.
- Sequential flows work.
- Parallel groups work.
- Conditional branching works.
- Retry success and retry failure work.
- Parallel traces are flat and share `parallel_group_id`.
- Shared state uses last-write-wins behavior in parallel branches.
- `human_input(...)` returns provider/stdin text as normal step output.
- Human input prompts can use `StepContext`.
- Sync and async human input providers work.
- Human input provider failures are traced and retried like normal step
  failures.
- Human input emits normal step lifecycle events.
- `MockAgent` and `CallableAgent` import from `orchflow.testing`.
- Optional LiteLLM behavior skips cleanly when the dependency is missing.

## Implementation Order

1. Update this `AGENTS.md`.
2. Implement `human_input(...)` as a normal `Step`.
3. Add top-level export and version bump.
4. Add human input tests.
5. Add stdin example and docs.
6. Run tests, quality checks, and package build.
