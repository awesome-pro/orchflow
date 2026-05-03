from __future__ import annotations

import asyncio
import json

import pytest

from orchflow import Flow, FlowExecutionError, RetryPolicy, condition, step


async def test_original_input_stays_first_argument_and_previous_changes() -> None:
    seen: list[tuple[object, object]] = []

    @step
    async def first(input, context):
        seen.append((input, context.previous))
        return "first-output"

    @step
    async def second(input, context):
        seen.append((input, context.previous))
        return {"previous": context.previous}

    result = await Flow([first, second]).run("original-input")

    assert result.success is True
    assert result.output == {"previous": "first-output"}
    assert seen == [
        ("original-input", None),
        ("original-input", "first-output"),
    ]


async def test_sync_steps_are_supported() -> None:
    @step
    def sync_step(input, context):
        context.state["called"] = True
        return f"{input}:sync"

    result = await Flow([sync_step]).run("hello")

    assert result.output == "hello:sync"
    assert result.state["called"] is True


async def test_condition_routes_with_context_previous() -> None:
    @step
    async def classify(input, context):
        return "technical"

    @step
    async def technical(input, context):
        return f"technical:{context.previous}"

    @step
    async def general(input, context):
        return f"general:{context.previous}"

    flow = Flow(
        [
            classify,
            condition(
                when=lambda ctx: ctx.previous == "technical",
                then=technical,
                otherwise=general,
            ),
        ]
    )

    result = await flow.run("write an article")

    assert result.output == "technical:technical"
    assert [trace.step_name for trace in result.traces] == ["classify", "technical"]


async def test_flow_level_retry_policy() -> None:
    calls = 0

    @step
    async def flaky(input, context):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("not yet")
        return "ok"

    result = await Flow(
        [flaky],
        retry_policy=RetryPolicy(max_attempts=3),
    ).run("input")

    assert result.output == "ok"
    assert calls == 3
    assert [trace.attempt for trace in result.traces] == [1, 2, 3]
    assert [trace.success for trace in result.traces] == [False, False, True]


async def test_step_level_retry_policy_overrides_flow_policy() -> None:
    calls = 0

    @step(retry=2)
    async def flaky(input, context):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("first failure")
        return "recovered"

    result = await Flow(
        [flaky],
        retry_policy=RetryPolicy(max_attempts=1),
    ).run("input")

    assert result.output == "recovered"
    assert [trace.attempt for trace in result.traces] == [1, 2]


async def test_failed_flow_raises_with_partial_result_and_original_error() -> None:
    @step(retry=2)
    async def broken(input, context):
        raise ValueError("boom")

    with pytest.raises(FlowExecutionError) as exc_info:
        await Flow([broken]).run("input")

    exc = exc_info.value
    assert exc.failed_step == "broken"
    assert isinstance(exc.original_error, ValueError)
    assert exc.result.success is False
    assert exc.result.failed_step == "broken"
    assert len(exc.result.traces) == 2
    assert all(trace.error for trace in exc.result.traces)


async def test_failed_flow_can_return_result() -> None:
    @step
    async def broken(input, context):
        raise RuntimeError("boom")

    result = await Flow([broken]).run("input", raise_on_error=False)

    assert result.success is False
    assert result.failed_step == "broken"
    assert result.error == "boom"


async def test_empty_flow_is_invalid() -> None:
    with pytest.raises(ValueError, match="at least one step"):
        Flow([])


async def test_duplicate_step_names_are_invalid() -> None:
    @step(name="duplicate")
    async def first(input, context):
        return "first"

    @step(name="duplicate")
    async def second(input, context):
        return "second"

    with pytest.raises(ValueError, match="Duplicate step name: duplicate"):
        Flow([first, second])


async def test_duplicate_step_names_inside_condition_are_invalid() -> None:
    @step(name="classify")
    async def classify(input, context):
        return "technical"

    @step(name="writer")
    async def writer_a(input, context):
        return "a"

    @step(name="writer")
    async def writer_b(input, context):
        return "b"

    with pytest.raises(ValueError, match="Duplicate step name: writer"):
        Flow(
            [
                classify,
                condition(
                    when=lambda ctx: ctx.previous == "technical",
                    then=writer_a,
                    otherwise=writer_b,
                ),
            ]
        )


async def test_empty_parallel_group_is_invalid() -> None:
    with pytest.raises(ValueError, match="Parallel step groups"):
        Flow([[]])


async def test_nested_parallel_groups_are_invalid() -> None:
    @step
    async def first(input, context):
        return "first"

    @step
    async def second(input, context):
        return "second"

    with pytest.raises(TypeError, match="Nested parallel"):
        Flow([[first, [second]]])


async def test_condition_with_no_otherwise_returns_previous_output() -> None:
    @step
    async def classify(input, context):
        return "general"

    @step
    async def technical(input, context):
        return "technical"

    result = await Flow(
        [
            classify,
            condition(
                when=lambda ctx: ctx.previous == "technical",
                then=technical,
            ),
        ]
    ).run("original")

    assert result.success is True
    assert result.output == "general"
    assert [trace.step_name for trace in result.traces] == ["classify"]


async def test_parallel_group_outputs_traces_and_shared_state() -> None:
    @step(name="left")
    async def left(input, context):
        assert input == "original"
        assert context.previous == "seed"
        context.state["winner"] = "left"
        await asyncio.sleep(0.01)
        return "L"

    @step(name="right")
    async def right(input, context):
        assert input == "original"
        assert context.previous == "seed"
        await asyncio.sleep(0.02)
        context.state["winner"] = "right"
        return "R"

    @step
    async def seed(input, context):
        return "seed"

    @step
    async def combine(input, context):
        return context.previous

    result = await Flow([seed, [left, right], combine]).run("original")

    assert result.output == {"left": "L", "right": "R"}
    assert result.state["winner"] == "right"

    parallel_traces = [
        trace for trace in result.traces if trace.step_name in {"left", "right"}
    ]
    assert len(parallel_traces) == 2
    group_ids = {trace.parallel_group_id for trace in parallel_traces}
    assert len(group_ids) == 1
    assert None not in group_ids


async def test_parallel_failure_records_failed_attempts() -> None:
    @step
    async def good(input, context):
        return "good"

    @step(retry=2)
    async def bad(input, context):
        raise ValueError("bad branch")

    result = await Flow([[good, bad]]).run("input", raise_on_error=False)

    assert result.success is False
    assert result.failed_step == "bad"
    bad_traces = [trace for trace in result.traces if trace.step_name == "bad"]
    assert [trace.attempt for trace in bad_traces] == [1, 2]
    assert all(trace.parallel_group_id for trace in bad_traces)


async def test_trace_and_result_serialization_are_flat_and_json_safe() -> None:
    @step
    async def first(input, context):
        context.state["topic"] = input
        return {"draft": "hello"}

    @step
    async def second(input, context):
        return {"final": context.previous["draft"]}

    result = await Flow([first, second], name="serialize-demo").run("original")

    payload = result.to_dict()
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)

    assert decoded["success"] is True
    assert decoded["output"] == {"final": "hello"}
    assert decoded["state"] == {"topic": "original"}
    assert decoded["metadata"]["flow_name"] == "serialize-demo"
    assert isinstance(decoded["traces"], list)
    assert [trace["step_name"] for trace in decoded["traces"]] == ["first", "second"]
    assert all("traces" not in trace for trace in decoded["traces"])
    assert all("parallel_group_id" in trace for trace in decoded["traces"])
    assert all(isinstance(trace["started_at"], str) for trace in decoded["traces"])
