from __future__ import annotations

import asyncio

from orchflow import Flow, RetryPolicy, StepContext, step


@step
async def collect(input: str, context: StepContext) -> str:
    return f"notes for {input}"


@step(retry=2)
async def draft(input: str, context: StepContext) -> str:
    if "retried" not in context.state:
        context.state["retried"] = True
        raise RuntimeError("temporary draft issue")
    return f"draft from {context.previous}"


async def main() -> None:
    flow = Flow(
        [collect, draft],
        name="live-events-demo",
        retry_policy=RetryPolicy(max_attempts=1),
    )

    async for event in flow.events("agent observability"):
        if event.step_name:
            print(f"{event.type}: {event.step_name} attempt={event.attempt}")
        else:
            print(event.type)


if __name__ == "__main__":
    asyncio.run(main())
