from __future__ import annotations

import asyncio
import os

from orchflow import Agent, Flow, StepContext, step

writer = Agent(
    name="writer",
    role="You write concise technical explanations.",
    model=os.getenv("ORCHFLOW_MODEL", "gpt-4o-mini"),
    temperature=0.2,
)


@step
async def draft(input: str, context: StepContext) -> str:
    return await writer.run(f"Explain this in three bullets: {input}", context=context)


async def main() -> None:
    flow = Flow([draft], name="litellm-demo")
    result = await flow.run("why small workflow frameworks are useful")

    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
