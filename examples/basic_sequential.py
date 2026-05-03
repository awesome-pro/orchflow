from __future__ import annotations

import asyncio

from orchflow import Flow, StepContext, step
from orchflow.testing import MockAgent

researcher = MockAgent("Research notes: small frameworks are easier to audit.")
writer = MockAgent("Draft: Orchflow keeps agent pipelines readable.")
editor = MockAgent("Final: Orchflow keeps agent pipelines readable and testable.")


@step(name="research", retry=2)
async def research(input: str, context: StepContext) -> str:
    return await researcher.run(f"Research this topic: {input}", context=context)


@step(name="write")
async def write(input: str, context: StepContext) -> str:
    return await writer.run(f"Write from notes:\n{context.previous}", context=context)


@step(name="edit")
async def edit(input: str, context: StepContext) -> str:
    return await editor.run(f"Edit this draft:\n{context.previous}", context=context)


async def main() -> None:
    flow = Flow([research, write, edit], name="content-pipeline")
    result = await flow.run("lightweight agent orchestration")

    print(result.output)
    print([trace.step_name for trace in result.traces])


if __name__ == "__main__":
    asyncio.run(main())
