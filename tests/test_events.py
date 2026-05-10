from __future__ import annotations

import json

import pytest

from orchflow import Flow, FlowEvent, FlowExecutionError, RetryPolicy, step


async def test_events_emit_flow_and_step_lifecycle() -> None:
    @step
    async def first(input, context):
        return "first-output"

    @step
    async def second(input, context):
        return {"previous": context.previous}

    events = [event async for event in Flow([first, second], name="demo").events("in")]

    assert [event.type for event in events] == [
        "flow_started",
        "step_started",
        "step_completed",
        "step_started",
        "step_completed",
        "flow_completed",
    ]
    assert all(isinstance(event, FlowEvent) for event in events)
    assert {event.run_id for event in events if event.run_id}
    assert events[0].flow_name == "demo"
    assert events[0].input == "in"
    assert events[-1].result is not None
    assert events[-1].result.output == {"previous": "first-output"}


async def test_events_emit_retry_scheduled_between_failed_attempts() -> None:
    calls = 0

    @step
    async def flaky(input, context):
        nonlocal calls
        calls += 1
        if calls < 2:
            raise ValueError("not yet")
        return "ok"

    events = [
        event
        async for event in Flow(
            [flaky],
            retry_policy=RetryPolicy(max_attempts=2, delay=0.0),
        ).events("in")
    ]

    assert [event.type for event in events] == [
        "flow_started",
        "step_started",
        "step_failed",
        "retry_scheduled",
        "step_started",
        "step_completed",
        "flow_completed",
    ]
    retry = next(event for event in events if event.type == "retry_scheduled")
    assert retry.step_name == "flaky"
    assert retry.attempt == 1
    assert retry.retry_delay == 0.0
    assert retry.trace is not None
    assert retry.trace.error == "ValueError: not yet"


async def test_events_emit_flow_failed_without_raising_by_default() -> None:
    @step
    async def broken(input, context):
        raise RuntimeError("boom")

    events = [event async for event in Flow([broken]).events("in")]

    assert [event.type for event in events] == [
        "flow_started",
        "step_started",
        "step_failed",
        "flow_failed",
    ]
    assert events[-1].result is not None
    assert events[-1].result.success is False
    assert events[-1].result.failed_step == "broken"
    assert events[-1].error == "boom"


async def test_events_can_raise_after_emitting_failure_event() -> None:
    @step
    async def broken(input, context):
        raise RuntimeError("boom")

    seen: list[str] = []

    with pytest.raises(FlowExecutionError):
        async for event in Flow([broken]).events("in", raise_on_error=True):
            seen.append(event.type)

    assert seen == [
        "flow_started",
        "step_started",
        "step_failed",
        "flow_failed",
    ]


async def test_parallel_events_share_group_id() -> None:
    @step(name="left")
    async def left(input, context):
        return "L"

    @step(name="right")
    async def right(input, context):
        return "R"

    events = [event async for event in Flow([[left, right]]).events("in")]
    parallel_events = [
        event
        for event in events
        if event.step_name in {"left", "right"}
        and event.type in {"step_started", "step_completed"}
    ]

    group_ids = {event.parallel_group_id for event in parallel_events}
    assert len(group_ids) == 1
    assert None not in group_ids
    assert events[-1].result is not None
    assert events[-1].result.output == {"left": "L", "right": "R"}


async def test_event_serialization_is_json_safe() -> None:
    @step
    async def first(input, context):
        return {"value": input}

    events = [event async for event in Flow([first]).events("hello")]
    payload = [event.to_dict() for event in events]
    decoded = json.loads(json.dumps(payload))

    assert decoded[0]["type"] == "flow_started"
    assert decoded[-1]["type"] == "flow_completed"
    assert decoded[-1]["result"]["output"] == {"value": "hello"}
    assert decoded[2]["trace"]["step_name"] == "first"


async def test_event_stream_can_be_stopped_early() -> None:
    @step
    async def first(input, context):
        return "done"

    seen: list[str] = []
    async for event in Flow([first]).events("in"):
        seen.append(event.type)
        break

    assert seen == ["flow_started"]
