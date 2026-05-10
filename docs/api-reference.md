# API Reference

## `Flow`

`Flow(steps, name="flow", retry_policy=None)` orchestrates step execution.

```python
result = await flow.run(input, raise_on_error=True)
```

By default, failed flows raise `FlowExecutionError`. Use
`raise_on_error=False` to receive `FlowResult(success=False)`.

`Flow.events(input, raise_on_error=False)` runs the same flow and yields live
`FlowEvent` objects:

```python
async for event in flow.events("topic"):
    print(event.type, event.step_name)
```

Event types are:

- `flow_started`
- `step_started`
- `step_completed`
- `step_failed`
- `retry_scheduled`
- `flow_completed`
- `flow_failed`

`flow.events(..., raise_on_error=True)` yields the failure event first, then
raises `FlowExecutionError`.

## `@step`

```python
@step(name="research", retry=3, retry_delay=1.0)
async def research(input, context):
    ...
```

Step functions receive the original input as the first argument. Previous output
is available as `context.previous`.

## `condition`

```python
condition(
    when=lambda ctx: ctx.previous == "technical",
    then=technical_writer,
    otherwise=general_writer,
)
```

## `human_input`

`human_input(...)` creates a normal step that pauses a flow and returns human
text.

```python
review = human_input(
    lambda ctx: f"Review this draft:\n{ctx.previous}\nDecision: ",
    name="review",
)
```

By default, the helper reads from stdin. Tests and applications can pass a sync
or async provider:

```python
def reviewer(prompt, context):
    return "approve"


review = human_input("Decision: ", name="review", provider=reviewer)
```

The provider receives the resolved prompt and the current `StepContext`. Provider
failures are normal step failures, so existing retry, trace, and event behavior
applies.

## `Agent`

`Agent` is a stateless, role-based helper for prompt-only LiteLLM calls.

```python
agent = Agent(name="writer", role="Write clearly.", model="gpt-4o-mini")
text = await agent.run("Explain orchestration")
```

LiteLLM is optional:

```bash
pip install "orchflow[litellm]"
```

Tool-calling loops, MCP, memory, and durability are outside v0.3.
