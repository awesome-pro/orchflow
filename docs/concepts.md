# Concepts

## Agent

An `Agent` is a stateless role plus model. It is intentionally small in v0.1:
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
and use last-write-wins behavior for v0.1.

## Trace

Every step attempt creates one flat `StepTrace`. Parallel traces share a
`parallel_group_id`; traces are never nested.
