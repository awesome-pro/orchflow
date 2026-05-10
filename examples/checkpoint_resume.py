from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from orchflow import Flow, JsonCheckpointStore, StepContext, step


@step
async def collect(input: str, context: StepContext) -> str:
    context.state["topic"] = input
    return f"notes for {input}"


def make_flaky_step():
    failed_once = False

    @step
    async def draft(input: str, context: StepContext) -> str:
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise RuntimeError("temporary drafting issue")
        return f"draft from {context.previous}"

    return draft


@step
async def publish(input: str, context: StepContext) -> str:
    return f"published: {context.previous}"


async def main() -> None:
    with TemporaryDirectory() as directory:
        checkpoint_path = Path(directory) / "orchflow-checkpoint.json"
        store = JsonCheckpointStore(checkpoint_path)
        flow = Flow([collect, make_flaky_step(), publish])

        failed = await flow.run(
            "checkpointed agent pipelines",
            checkpoint=store,
            raise_on_error=False,
        )
        print(f"first run success: {failed.success}")
        print(f"checkpoint: {checkpoint_path}")

        resumed = await flow.resume(store)
        print(resumed.output)


if __name__ == "__main__":
    asyncio.run(main())
