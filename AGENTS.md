# AGENTS.md - Orchflow Project Guide

This document is the source of truth for Orchflow. Code follows this document,
not the other way around.

## What Is Orchflow?

Orchflow is a lightweight Python framework for readable multi-agent pipelines.
It sits between plain Python function chaining and graph-heavy agent runtimes.

The goal for v0.1 is a small, reliable workflow microframework that makes
sequential, parallel, and conditional agent pipelines easy to write, test, and
inspect.

One-line pitch:

> The simplest way to build readable multi-agent pipelines in Python.

## Scope For v0.1

Included:

- Sequential flows
- Parallel step groups
- Conditional branching
- Retry policy
- Shared mutable state
- Flat structured traces
- Public `Agent`
- Offline tests and examples
- Optional LiteLLM-backed real-agent example
- Updated README, quickstart, and this `AGENTS.md`

Out of scope:

- Human-in-the-loop
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
- Nested parallel step groups are invalid in v0.1 and raise `TypeError`.

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
v0.1.

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

Parallel branches share the same state dict in v0.1. If multiple branches write
the same key, the behavior is last-write-wins. There is no deep-copy isolation
and no state conflict error in v0.1.

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

## Test Requirements

The v0.1 test suite must verify:

- Original input is passed as the first argument to every step.
- `context.previous` changes after each step.
- Sequential flows work.
- Parallel groups work.
- Conditional branching works.
- Retry success and retry failure work.
- Parallel traces are flat and share `parallel_group_id`.
- Shared state uses last-write-wins behavior in parallel branches.
- `MockAgent` and `CallableAgent` import from `orchflow.testing`.
- Optional LiteLLM behavior skips cleanly when the dependency is missing.

## Implementation Order

1. Update this `AGENTS.md`.
2. Add project metadata and package scaffold.
3. Implement models, step decorator, retry policy, conditions, runner, flow, and
   public exports.
4. Implement public `Agent` with optional LiteLLM support.
5. Add testing helpers under `orchflow.testing`.
6. Add offline examples and optional LiteLLM example.
7. Add docs and README.
8. Run tests and quality checks.
