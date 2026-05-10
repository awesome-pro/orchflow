# API Reference

## `Flow`

`Flow(steps, name="flow", retry_policy=None)` orchestrates step execution.

```python
result = await flow.run(input, raise_on_error=True)
```

By default, failed flows raise `FlowExecutionError`. Use
`raise_on_error=False` to receive `FlowResult(success=False)`.

Pass a `JsonCheckpointStore` to persist top-level progress:

```python
result = await flow.run("topic", checkpoint=store, raise_on_error=False)
if not result.success:
    result = await flow.resume(store)
```

`Flow.events(input, raise_on_error=False, checkpoint=None)` runs the same flow
and yields live `FlowEvent` objects. `Flow.resume_events(store)` does the same
for resumed runs:

```python
async for event in flow.events("topic", checkpoint=store):
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
- `checkpoint_saved`
- `checkpoint_loaded`

`flow.events(..., raise_on_error=True)` yields the failure event first, then
raises `FlowExecutionError`.

## `JsonCheckpointStore`

`JsonCheckpointStore(path)` stores inspectable JSON checkpoints for
`Flow.run(..., checkpoint=store)` and `Flow.resume(store)`.

```python
from orchflow import Flow, JsonCheckpointStore

store = JsonCheckpointStore("orchflow-checkpoint.json")
flow = Flow([collect, draft, publish])
result = await flow.run("topic", checkpoint=store, raise_on_error=False)
```

Checkpoints are saved after completed top-level flow items. Payloads must be JSON
serializable. Missing files, invalid JSON, completed checkpoints, unsupported
versions, and flow signature mismatches raise `CheckpointError`.

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

`Agent` is a stateless, role-based helper for LiteLLM-backed calls.

```python
agent = Agent(name="writer", role="Write clearly.", model="gpt-4o-mini")
text = await agent.run("Explain orchestration")
```

Use `AgentConfig` for typed provider configuration:

```python
agent = Agent(
    name="extractor",
    role="Extract structured data.",
    config=AgentConfig(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=500,
    ),
)
```

Use `run_structured(...)` for JSON schema or optional Pydantic outputs:

```python
person = await agent.run_structured(
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

`run_structured(...)` returns parsed JSON for schema dictionaries and a Pydantic
model instance for Pydantic model classes. Invalid JSON and validation failures
raise `StructuredOutputError`.

LiteLLM is optional:

```bash
pip install "orchflow[litellm]"
```

Tool-calling loops, MCP, memory, and cloud durability are outside v0.5.
