from __future__ import annotations

import json

import pytest

from orchflow import (
    CheckpointError,
    Flow,
    JsonCheckpointStore,
    StepContext,
    condition,
    step,
)


def read_checkpoint(store: JsonCheckpointStore) -> dict:
    return json.loads(store.path.read_text(encoding="utf-8"))


async def test_checkpointed_run_writes_completed_checkpoint(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path / "checkpoint.json")

    @step
    async def first(input: str, context: StepContext) -> str:
        context.state["topic"] = input
        return "first"

    @step
    async def second(input: str, context: StepContext) -> dict[str, str]:
        return {"previous": context.previous}

    result = await Flow([first, second], name="checkpoint-demo").run(
        "agents",
        checkpoint=store,
    )
    payload = read_checkpoint(store)

    assert result.success is True
    assert payload["version"] == 1
    assert payload["status"] == "completed"
    assert payload["flow_name"] == "checkpoint-demo"
    assert payload["original_input"] == "agents"
    assert payload["next_step_index"] == 2
    assert payload["previous"] == {"previous": "first"}
    assert payload["state"] == {"topic": "agents"}
    assert [trace["step_name"] for trace in payload["traces"]] == [
        "first",
        "second",
    ]
    assert "completed_at" in payload


async def test_failed_checkpointed_run_resumes_from_last_success(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path / "checkpoint.json")
    calls = {"first": 0, "flaky": 0}

    @step
    async def first(input: str, context: StepContext) -> str:
        calls["first"] += 1
        context.state["seed"] = input
        return "first-output"

    @step
    async def flaky(input: str, context: StepContext) -> str:
        calls["flaky"] += 1
        context.state["flaky_mutation"] = calls["flaky"]
        if calls["flaky"] == 1:
            raise RuntimeError("temporary failure")
        return f"recovered from {context.previous}"

    @step
    async def final(input: str, context: StepContext) -> str:
        return f"final: {context.previous}"

    flow = Flow([first, flaky, final], name="resume-demo")
    failed = await flow.run("topic", checkpoint=store, raise_on_error=False)
    failed_payload = read_checkpoint(store)

    assert failed.success is False
    assert failed_payload["status"] == "failed"
    assert failed_payload["next_step_index"] == 1
    assert failed_payload["previous"] == "first-output"
    assert failed_payload["state"] == {"seed": "topic"}
    assert failed_payload["error"] == "temporary failure"

    resumed = await flow.resume(store)

    assert resumed.success is True
    assert resumed.output == "final: recovered from first-output"
    assert calls == {"first": 1, "flaky": 2}
    assert resumed.state["seed"] == "topic"
    assert resumed.state["flaky_mutation"] == 2
    assert [trace.step_name for trace in resumed.traces] == [
        "first",
        "flaky",
        "flaky",
        "final",
    ]
    assert read_checkpoint(store)["status"] == "completed"


async def test_condition_checkpoint_resumes_after_selected_branch(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path / "checkpoint.json")
    calls = {"classify": 0, "technical": 0, "after": 0}

    @step
    async def classify(input: str, context: StepContext) -> str:
        calls["classify"] += 1
        return "technical"

    @step
    async def technical(input: str, context: StepContext) -> str:
        calls["technical"] += 1
        return "technical draft"

    @step
    async def after(input: str, context: StepContext) -> str:
        calls["after"] += 1
        if calls["after"] == 1:
            raise RuntimeError("pause")
        return f"after {context.previous}"

    flow = Flow(
        [
            classify,
            condition(
                when=lambda ctx: ctx.previous == "technical",
                then=technical,
            ),
            after,
        ]
    )

    await flow.run("topic", checkpoint=store, raise_on_error=False)

    payload = read_checkpoint(store)
    assert payload["status"] == "failed"
    assert payload["next_step_index"] == 2
    assert payload["previous"] == "technical draft"

    result = await flow.resume(store)

    assert result.output == "after technical draft"
    assert calls == {"classify": 1, "technical": 1, "after": 2}


async def test_failed_parallel_group_reruns_whole_group_on_resume(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path / "checkpoint.json")
    calls = {"left": 0, "right": 0}

    @step
    async def seed(input: str, context: StepContext) -> str:
        return "seed"

    @step
    async def left(input: str, context: StepContext) -> str:
        calls["left"] += 1
        return f"left-{calls['left']}"

    @step
    async def right(input: str, context: StepContext) -> str:
        calls["right"] += 1
        if calls["right"] == 1:
            raise RuntimeError("right failed")
        return f"right-{calls['right']}"

    @step
    async def combine(input: str, context: StepContext) -> dict[str, str]:
        return context.previous

    flow = Flow([seed, [left, right], combine])
    await flow.run("topic", checkpoint=store, raise_on_error=False)

    failed_payload = read_checkpoint(store)
    assert failed_payload["status"] == "failed"
    assert failed_payload["next_step_index"] == 1
    assert failed_payload["previous"] == "seed"

    result = await flow.resume(store)

    assert result.output == {"left": "left-2", "right": "right-2"}
    assert calls == {"left": 2, "right": 2}
    assert [trace.step_name for trace in result.traces].count("left") == 2


async def test_checkpoint_resume_rejects_invalid_checkpoints(tmp_path) -> None:
    missing = JsonCheckpointStore(tmp_path / "missing.json")

    @step
    async def only(input: str, context: StepContext) -> str:
        return "done"

    flow = Flow([only])
    with pytest.raises(CheckpointError, match="does not exist"):
        await flow.resume(missing)

    invalid = JsonCheckpointStore(tmp_path / "invalid.json")
    invalid.path.write_text("{", encoding="utf-8")
    with pytest.raises(CheckpointError, match="Invalid checkpoint JSON"):
        await flow.resume(invalid)

    unsupported = JsonCheckpointStore(tmp_path / "unsupported.json")
    unsupported.path.write_text('{"version": 999}', encoding="utf-8")
    with pytest.raises(CheckpointError, match="Unsupported checkpoint version"):
        await flow.resume(unsupported)


async def test_resume_rejects_completed_and_mismatched_checkpoints(tmp_path) -> None:
    completed_store = JsonCheckpointStore(tmp_path / "completed.json")

    @step
    async def first(input: str, context: StepContext) -> str:
        return "first"

    await Flow([first]).run("topic", checkpoint=completed_store)
    with pytest.raises(CheckpointError, match="completed"):
        await Flow([first]).resume(completed_store)

    mismatch_store = JsonCheckpointStore(tmp_path / "mismatch.json")

    @step
    async def broken(input: str, context: StepContext) -> str:
        raise RuntimeError("boom")

    await Flow([first, broken]).run(
        "topic",
        checkpoint=mismatch_store,
        raise_on_error=False,
    )

    @step
    async def different(input: str, context: StepContext) -> str:
        return "different"

    with pytest.raises(CheckpointError, match="signature"):
        await Flow([first, different]).resume(mismatch_store)


async def test_non_json_serializable_checkpoint_payload_raises(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path / "checkpoint.json")

    @step
    async def bad_state(input: str, context: StepContext) -> str:
        context.state["items"] = {"not-json"}
        return "done"

    with pytest.raises(CheckpointError, match="state"):
        await Flow([bad_state]).run("topic", checkpoint=store)


async def test_checkpoint_events_emit_saved_and_loaded(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path / "checkpoint.json")
    calls = 0

    @step
    async def flaky(input: str, context: StepContext) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")
        return "ok"

    flow = Flow([flaky])
    failed_events = [
        event
        async for event in flow.events(
            "topic",
            checkpoint=store,
            raise_on_error=False,
        )
    ]

    assert failed_events[-2].type == "checkpoint_saved"
    assert failed_events[-2].metadata["status"] == "failed"

    resumed_events = [event async for event in flow.resume_events(store)]

    assert resumed_events[0].type == "checkpoint_loaded"
    assert any(event.type == "checkpoint_saved" for event in resumed_events)
    assert resumed_events[-1].type == "flow_completed"
