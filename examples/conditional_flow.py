from __future__ import annotations

import asyncio

from orchflow import Flow, StepContext, condition, step


@step
async def classify(input: str, context: StepContext) -> str:
    if "api" in input.lower() or "python" in input.lower():
        return "technical"
    return "general"


@step
async def technical_writer(input: str, context: StepContext) -> str:
    return f"Technical brief for: {input}"


@step
async def general_writer(input: str, context: StepContext) -> str:
    return f"Plain-language brief for: {input}"


async def main() -> None:
    flow = Flow(
        [
            classify,
            condition(
                when=lambda ctx: ctx.previous == "technical",
                then=technical_writer,
                otherwise=general_writer,
            ),
        ]
    )
    result = await flow.run("Python API orchestration")

    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
