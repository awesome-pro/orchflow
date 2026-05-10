# Concepts

## Agent

An `Agent` is a stateless role plus model. It is intentionally small in v0.3:
prompt in, text out.

## Step

A step is a decorated Python function:

```python
async def step(input, context):
    ...
```

`input` is the original flow input every time. `context.previous` is the output
of the previous step.

## Flow

A flow is the ordered pipeline. It can contain single steps, parallel step lists,
and conditions.

## State

`context.state` is shared mutable run state. Parallel steps share the same dict
and use last-write-wins behavior for v0.3.

## Trace

Every step attempt creates one flat `StepTrace`. Parallel traces share a
`parallel_group_id`; traces are never nested.

## Event

A `FlowEvent` is emitted while a flow runs. Events are useful for terminal
progress, logs, notebooks, and future UI integrations.

`Flow.events(...)` does not stream LLM tokens. It streams orchestration lifecycle
events such as step started, retry scheduled, step completed, and flow completed.

## Human Input

`human_input(...)` is a step helper for lightweight human review. It resolves a
prompt from a string or `StepContext` callable, then returns the human response
as normal step output.

The default provider reads from stdin for local demos. Applications and tests
can pass a sync or async provider callback.
