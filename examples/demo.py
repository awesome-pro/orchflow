from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from orchflow import Flow, FlowEvent, JsonCheckpointStore, StepContext, condition, step


@step(name="plan")
async def plan(input: str, context: StepContext) -> dict[str, Any]:
    context.state["topic"] = input
    return {
        "topic": input,
        "audience": "AI engineering teams",
        "sections": ["positioning", "proof", "risk"],
    }


@step(name="market_research")
async def market_research(input: str, context: StepContext) -> dict[str, Any]:
    await asyncio.sleep(0.4)
    return {
        "angle": "Developers want agent workflows they can debug quickly.",
        "signal": "Readable Python beats hidden graph configuration for small teams.",
    }


@step(name="technical_research")
async def technical_research(input: str, context: StepContext) -> dict[str, Any]:
    await asyncio.sleep(0.6)
    return {
        "mechanics": [
            "sequential steps",
            "parallel fan-out",
            "conditional routing",
            "live events",
            "JSON checkpoints",
        ],
        "implementation_note": "Each step is a normal Python function.",
    }


def make_risk_review() -> Any:
    failed_once = False

    @step(name="risk_review", retry=2, retry_delay=0.2)
    async def risk_review(input: str, context: StepContext) -> dict[str, Any]:
        nonlocal failed_once
        await asyncio.sleep(0.2)
        if not failed_once:
            failed_once = True
            raise RuntimeError("temporary reviewer timeout")
        return {
            "risk": "A pipeline can look successful while hiding failed branches.",
            "mitigation": "Flat traces and live events make every attempt visible.",
            "score": 0.91,
        }

    return risk_review


def make_synthesize(*, fail_once: bool = False) -> Any:
    failed_once = False

    @step(name="synthesize")
    async def synthesize(input: str, context: StepContext) -> dict[str, Any]:
        nonlocal failed_once
        if fail_once and not failed_once:
            failed_once = True
            raise RuntimeError("provider returned malformed JSON")

        research = context.previous
        brief = {
            "headline": f"{context.state['topic']} without orchestration clutter",
            "positioning": research["market_research"]["angle"],
            "proof": research["technical_research"]["mechanics"],
            "risk": research["risk_review"]["risk"],
            "mitigation": research["risk_review"]["mitigation"],
            "quality_score": 0.93,
        }
        context.state["brief"] = brief
        return brief

    return synthesize


@step(name="publish")
async def publish(input: str, context: StepContext) -> str:
    brief = context.previous
    return (
        f"Published launch brief: {brief['headline']}\n"
        f"Why it matters: {brief['positioning']}\n"
        f"Proof: {', '.join(brief['proof'])}"
    )


@step(name="revise")
async def revise(input: str, context: StepContext) -> str:
    return f"Revision requested for: {context.previous['headline']}"


def build_flow(*, fail_synthesize_once: bool = False) -> Flow:
    return Flow(
        [
            plan,
            [market_research, technical_research, make_risk_review()],
            make_synthesize(fail_once=fail_synthesize_once),
            condition(
                when=lambda ctx: ctx.previous["quality_score"] >= 0.9,
                then=publish,
                otherwise=revise,
            ),
        ],
        name="orchflow-video-demo",
    )


def print_event(event: FlowEvent) -> None:
    label = event.type
    if event.step_name:
        label += f" | step={event.step_name}"
    if event.attempt:
        label += f" | attempt={event.attempt}"
    if event.parallel_group_id:
        label += f" | parallel={event.parallel_group_id[:8]}"
    if event.error:
        label += f" | error={event.error}"
    print(label)


async def show_live_events() -> None:
    print("\n=== Live flow with parallel branches, retry, condition, and traces ===")
    flow = build_flow()
    final_output: Any = None

    async for event in flow.events("Orchflow launch demo"):
        print_event(event)
        if event.result:
            final_output = event.result.output

    print("\nFinal output:")
    print(final_output)


async def show_checkpoint_resume() -> None:
    print("\n=== Checkpoint + resume after a failed step ===")
    with TemporaryDirectory() as directory:
        checkpoint_path = Path(directory) / "orchflow-checkpoint.json"
        store = JsonCheckpointStore(checkpoint_path)
        flow = build_flow(fail_synthesize_once=True)

        print("\nInitial run:")
        async for event in flow.events(
            "Orchflow launch demo",
            checkpoint=store,
            raise_on_error=False,
        ):
            print_event(event)

        print("\nCheckpoint snapshot:")
        print(json.dumps(json.loads(checkpoint_path.read_text()), indent=2)[:900])
        print("...")

        print("\nResumed run:")
        async for event in flow.resume_events(store, raise_on_error=False):
            print_event(event)
            if event.result:
                print("\nResumed output:")
                print(event.result.output)


async def main() -> None:
    await show_live_events()
    await show_checkpoint_resume()


if __name__ == "__main__":
    asyncio.run(main())
