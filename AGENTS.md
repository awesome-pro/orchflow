# AGENTS.md - Orchflow Project Guide

This document is the source of truth for Orchflow. Code follows this document,
not the other way around.

## What Is Orchflow?

Orchflow is a lightweight Python framework for readable multi-agent pipelines.
It sits between plain Python function chaining and graph-heavy agent runtimes.

The goal for v0.5 is a small, reliable workflow microframework that makes
sequential, parallel, and conditional agent pipelines easy to write, test,
inspect, observe, pause for lightweight human input, and resume from JSON
checkpoints. v0.5 also improves `Agent` for structured AI workflows.

One-line pitch:

> The simplest way to build readable multi-agent pipelines in Python.

## Scope For v0.5

Included:

- Sequential flows
- Parallel step groups
- Conditional branching
- Retry policy
- Shared mutable state
- Flat structured traces
- Live flow lifecycle events
- Lightweight human input gates
- JSON checkpoint and resume support
- Structured agent outputs
- Typed agent provider configuration
- Public `Agent`
- Offline tests and examples
- Optional LiteLLM-backed real-agent example
- Updated README, quickstart, and this `AGENTS.md`

Out of scope:

- Streaming
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
- `JsonCheckpointStore`
- `CheckpointError`
- `AgentConfig`
- `StructuredOutputError`
- `FlowExecutionError`

Testing helpers live under `orchflow.testing` only:

- `MockAgent`
- `CallableAgent`

## Core Concepts

### Agent

An `Agent` is a stateless, role-based LLM helper. It keeps the common
multi-agent case simple while leaving orchestration in the `Flow`.

The core `Agent.run(prompt, context=None)` API returns plain text through
optional LiteLLM integration. LiteLLM is not a required runtime dependency.

`AgentConfig` provides typed provider configuration:

```python
agent = Agent(
    name="extractor",
    role="Extract structured data.",
    config=AgentConfig(
        model="openai/gpt-5-mini",
        temperature=0,
    ),
)
```

Existing direct `Agent` fields remain backward compatible. If direct fields and
`config` both provide a value, the direct field wins.

`Agent.run_structured(prompt, schema=...)` returns parsed structured output:

```python
parsed = await agent.run_structured(
    "Extract name and company from: Ada at OpenAI",
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

Structured output behavior:

- JSON schema dictionaries return parsed JSON values.
- Pydantic model classes are supported when Pydantic is already installed by the
  user.
- Pydantic is not a core Orchflow dependency.
- `StructuredOutputError` is raised for invalid JSON, validation failures,
  missing schema support, or empty structured content.

Tool-calling loops, MCP tools, memory, streaming LLM tokens, provider-specific
routing, and durable agent state are not part of v0.5. Users should call tools
inside normal steps until a later release adds dedicated tool support.

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

Parallel branches share the same state dict in v0.5. If multiple branches write
the same key, the behavior is last-write-wins. There is no deep-copy isolation
and no state conflict error in v0.5.

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

Human input remains text-only in v0.5. It does not include structured
approval objects, abort-on-reject behavior, durable resume, or a web UI.

### Checkpoints

`JsonCheckpointStore` persists inspectable JSON checkpoints for a flow run.

```python
store = JsonCheckpointStore("orchflow-checkpoint.json")

result = await flow.run("AI agents in 2026", checkpoint=store)
result = await flow.resume(store)
```

Behavior:

- `Flow.run(input, checkpoint=store)` saves after each completed top-level flow
  item.
- `Flow.resume(store)` loads the checkpoint and resumes from
  `next_step_index`.
- `Flow.events(input, checkpoint=store)` and `Flow.resume_events(store)` emit
  checkpoint lifecycle events.
- Checkpoint event types are `checkpoint_saved` and `checkpoint_loaded`.
- Checkpoint JSON stores `version`, `status`, `run_id`, `flow_name`,
  `flow_signature`, `original_input`, `next_step_index`, `previous`, `state`,
  `traces`, timestamps, and failure error when present.
- A completed top-level item may be a single step, a selected condition branch,
  or a complete parallel group.
- Failed top-level parallel groups resume by rerunning the whole group. v0.5
  does not resume individual parallel branches.
- Checkpoint payloads must be JSON serializable. Non-JSON inputs, outputs,
  state, or traces raise `CheckpointError`.
- Successful flows keep the checkpoint file and mark it `status="completed"`.
- `Flow.resume(...)` rejects completed checkpoints, missing files, invalid JSON,
  unsupported checkpoint versions, and flow signature mismatches with
  `CheckpointError`.

v0.5 checkpointing remains local and JSON-only. It does not include
cloud stores, pickle serialization, custom codecs, partial parallel resume,
checkpoint encryption, or a durable human-review UI.

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
- `checkpoint_saved`
- `checkpoint_loaded`

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
- Save after completed top-level flow items.
- Add checkpoint lifecycle events.
- Keep checkpoint payloads JSON-only and inspectable.

### 0.5.0 - Agent Adapter Upgrade

- Add `AgentConfig` for typed provider configuration.
- Add `Agent.run_structured(prompt, schema=...)`.
- Support JSON schema dictionaries and optional Pydantic model classes.
- Keep tool execution out of scope and point users to normal steps.

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
- Fresh runs write checkpoints and mark them completed on success.
- Failed checkpointed runs can resume from the next item after the last
  successful checkpoint.
- Resumed runs preserve original input, previous output, shared state, and
  stored traces while appending new traces.
- Conditions and parallel groups checkpoint at top-level item boundaries.
- Completed checkpoints, missing files, invalid JSON, unsupported versions, and
  flow signature mismatches raise `CheckpointError`.
- Non-JSON-serializable checkpoint payloads raise `CheckpointError`.
- Checkpointed event streams emit `checkpoint_saved` and `checkpoint_loaded`.
- `Agent.run(...)` remains backward compatible and returns plain text.
- `AgentConfig` merges provider options correctly.
- `Agent.run_structured(...)` parses JSON schema outputs.
- Pydantic-style model parsing works without making Pydantic a core dependency.
- Invalid JSON and validation failures raise `StructuredOutputError`.
- Missing LiteLLM dependency errors still mention `orchflow[litellm]`.
- `MockAgent` and `CallableAgent` import from `orchflow.testing`.
- Optional LiteLLM behavior skips cleanly when the dependency is missing.

## Implementation Order

1. Update this `AGENTS.md`.
2. Implement `AgentConfig` and `StructuredOutputError`.
3. Add `Agent.run_structured(prompt, schema=...)` with JSON and Pydantic-style
   parsing.
4. Add structured agent tests.
5. Add structured agent example, docs, changelog, and version bump.
6. Run tests, quality checks, and package build.
