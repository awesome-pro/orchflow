from __future__ import annotations

import asyncio

from orchflow import Flow, StepContext, step


@step
async def plan(input: str, context: StepContext) -> str:
    return "compare options"


@step(name="web_research")
async def web_research(input: str, context: StepContext) -> str:
    await asyncio.sleep(0.1)
    context.state["last_source"] = "web"
    return f"web notes for {input}"


@step(name="docs_research")
async def docs_research(input: str, context: StepContext) -> str:
    await asyncio.sleep(0.05)
    context.state["last_source"] = "docs"
    return f"docs notes for {input}"


@step
async def synthesize(input: str, context: StepContext) -> dict[str, object]:
    return {
        "original_input": input,
        "research": context.previous,
        "last_source": context.state["last_source"],
    }


async def main() -> None:
    flow = Flow([plan, [web_research, docs_research], synthesize])
    result = await flow.run("agent orchestration frameworks")

    print(result.output)
    print([trace.to_dict() for trace in result.traces])


if __name__ == "__main__":
    asyncio.run(main())
