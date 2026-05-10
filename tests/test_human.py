from __future__ import annotations

import asyncio

import pytest

from orchflow import Flow, RetryPolicy, StepContext, human_input, step


async def test_human_input_provider_output_becomes_previous() -> None:
    seen_prompt: list[str] = []
    seen_previous: list[object] = []

    @step
    async def draft(input: str, context: StepContext) -> str:
        return f"draft about {input}"

    def reviewer(prompt: str, context: StepContext) -> str:
        seen_prompt.append(prompt)
        seen_previous.append(context.previous)
        return "approved with edits"

    @step
    async def finalize(input: str, context: StepContext) -> str:
        return f"final: {context.previous}"

    result = await Flow(
        [
            draft,
            human_input("Review draft: ", name="review", provider=reviewer),
            finalize,
        ]
    ).run("agents")

    assert result.output == "final: approved with edits"
    assert seen_prompt == ["Review draft: "]
    assert seen_previous == ["draft about agents"]
    assert [trace.step_name for trace in result.traces] == [
        "draft",
        "review",
        "finalize",
    ]


async def test_human_input_uses_stdin_when_provider_is_missing(monkeypatch) -> None:
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return "ship it"

    monkeypatch.setattr("builtins.input", fake_input)

    result = await Flow([human_input("Decision: ", name="review")]).run("draft")

    assert result.output == "ship it"
    assert prompts == ["Decision: "]


async def test_human_input_prompt_callable_can_use_context() -> None:
    prompts: list[str] = []

    @step
    async def draft(input: str, context: StepContext) -> str:
        context.state["ticket"] = "OF-3"
        return f"draft for {input}"

    def reviewer(prompt: str, context: StepContext) -> str:
        prompts.append(prompt)
        return f"{context.state['ticket']}: approved"

    result = await Flow(
        [
            draft,
            human_input(
                lambda ctx: f"{ctx.state['ticket']} review {ctx.previous}: ",
                name="review",
                provider=reviewer,
            ),
        ]
    ).run("launch")

    assert result.output == "OF-3: approved"
    assert prompts == ["OF-3 review draft for launch: "]


async def test_human_input_supports_async_provider() -> None:
    async def reviewer(prompt: str, context: StepContext) -> str:
        await asyncio.sleep(0)
        return f"async response to {prompt}"

    result = await Flow(
        [human_input("Review: ", name="async_review", provider=reviewer)]
    ).run("draft")

    assert result.output == "async response to Review: "


async def test_human_input_failure_is_traced_and_retried() -> None:
    calls = 0

    def flaky_reviewer(prompt: str, context: StepContext) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("reviewer unavailable")
        return "approved"

    result = await Flow(
        [human_input("Review: ", name="review", provider=flaky_reviewer)],
        retry_policy=RetryPolicy(max_attempts=2),
    ).run("draft")

    assert result.output == "approved"
    assert calls == 2
    assert [trace.success for trace in result.traces] == [False, True]
    assert result.traces[0].step_name == "review"
    assert result.traces[0].error == "RuntimeError: reviewer unavailable"


async def test_duplicate_human_input_step_names_are_invalid() -> None:
    with pytest.raises(ValueError, match="Duplicate step name: review"):
        Flow(
            [
                human_input("First: ", name="review", provider=lambda p, c: "first"),
                human_input("Second: ", name="review", provider=lambda p, c: "second"),
            ]
        )


async def test_human_input_emits_normal_step_events() -> None:
    events = [
        event
        async for event in Flow(
            [human_input("Review: ", name="review", provider=lambda p, c: "ok")]
        ).events("draft")
    ]

    assert [event.type for event in events] == [
        "flow_started",
        "step_started",
        "step_completed",
        "flow_completed",
    ]
    assert events[1].step_name == "review"
    assert events[2].output == "ok"
    assert events[-1].result is not None
    assert events[-1].result.output == "ok"
