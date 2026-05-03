# API Reference

## `Flow`

`Flow(steps, name="flow", retry_policy=None)` orchestrates step execution.

```python
result = await flow.run(input, raise_on_error=True)
```

By default, failed flows raise `FlowExecutionError`. Use
`raise_on_error=False` to receive `FlowResult(success=False)`.

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

Tool-calling loops, MCP, memory, and durability are outside v0.1.
