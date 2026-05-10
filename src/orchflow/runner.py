from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeGuard, cast
from uuid import uuid4

from .checkpoint import (
    CheckpointError,
    CheckpointSnapshot,
    JsonCheckpointStore,
    checkpoint_payload,
    json_clone,
)
from .condition import Condition
from .models import FlowEvent, FlowResult, StepTrace
from .retry import RetryPolicy
from .step import FlowInput, Step, StepCallable, StepContext

FlowItem = Step | StepCallable | Condition | list[Any] | tuple[Any, ...]
EventHandler = Callable[[FlowEvent], Awaitable[None] | None]


@dataclass(slots=True)
class _StepFailure(Exception):
    step_name: str
    original_error: BaseException


class FlowRunner:
    def __init__(
        self,
        *,
        steps: Sequence[FlowItem],
        flow_name: str,
        retry_policy: RetryPolicy,
        event_handler: EventHandler | None = None,
    ) -> None:
        self.steps = list(steps)
        self.flow_name = flow_name
        self.retry_policy = retry_policy
        self._event_handler = event_handler
        self.flow_signature = flow_signature(self.steps)

    async def run(
        self,
        input: FlowInput,
        *,
        checkpoint: JsonCheckpointStore | None = None,
    ) -> FlowResult:
        run_id = str(uuid4())
        started_at = datetime.now(UTC)
        return await self._run_from_state(
            original_input=input,
            previous=None,
            state={},
            traces=[],
            run_id=run_id,
            start_step_index=0,
            checkpoint=checkpoint,
            checkpoint_started_at=started_at.isoformat(),
            resumed=False,
        )

    async def resume(self, checkpoint: JsonCheckpointStore) -> FlowResult:
        snapshot = checkpoint.load()
        self._validate_checkpoint(snapshot)
        await self._emit(
            FlowEvent(
                type="checkpoint_loaded",
                run_id=snapshot.run_id,
                flow_name=self.flow_name,
                timestamp=datetime.now(UTC),
                input=snapshot.original_input,
                metadata={
                    "checkpoint_path": str(checkpoint.path),
                    "status": snapshot.status,
                    "next_step_index": snapshot.next_step_index,
                },
            )
        )
        return await self._run_from_state(
            original_input=cast(FlowInput, snapshot.original_input),
            previous=snapshot.previous,
            state=snapshot.state,
            traces=list(snapshot.traces),
            run_id=snapshot.run_id,
            start_step_index=snapshot.next_step_index,
            checkpoint=checkpoint,
            checkpoint_started_at=snapshot.started_at,
            resumed=True,
        )

    async def _run_from_state(
        self,
        *,
        original_input: FlowInput,
        previous: Any,
        state: dict[str, Any],
        traces: list[StepTrace],
        run_id: str,
        start_step_index: int,
        checkpoint: JsonCheckpointStore | None,
        checkpoint_started_at: str,
        resumed: bool,
    ) -> FlowResult:
        started_perf = time.perf_counter()
        started_at = datetime.now(UTC)
        metadata: dict[str, Any] = {
            "run_id": run_id,
            "flow_name": self.flow_name,
            "started_at": started_at.isoformat(),
        }
        if checkpoint is not None:
            metadata["checkpoint_path"] = str(checkpoint.path)
        if resumed:
            metadata["resumed_from_checkpoint"] = True
            metadata["start_step_index"] = start_step_index
        await self._emit(
            FlowEvent(
                type="flow_started",
                run_id=run_id,
                flow_name=self.flow_name,
                timestamp=started_at,
                input=original_input,
                metadata=metadata.copy(),
            )
        )

        failed_step_index = start_step_index
        checkpoint_previous = previous
        checkpoint_state = json_clone(state, label="state") if checkpoint else state

        try:
            for index in range(start_step_index, len(self.steps)):
                item = self.steps[index]
                failed_step_index = index
                checkpoint_previous = previous
                checkpoint_state = (
                    json_clone(state, label="state") if checkpoint else state
                )
                previous = await self._run_item(
                    item=item,
                    original_input=original_input,
                    previous=previous,
                    state=state,
                    traces=traces,
                    run_id=run_id,
                    step_index=index,
                    parallel_group_id=None,
                )
                if checkpoint is not None:
                    status = "completed" if index == len(self.steps) - 1 else "running"
                    await self._save_checkpoint(
                        checkpoint=checkpoint,
                        status=status,
                        run_id=run_id,
                        original_input=original_input,
                        next_step_index=index + 1,
                        previous=previous,
                        state=state,
                        traces=traces,
                        checkpoint_started_at=checkpoint_started_at,
                    )

            if checkpoint is not None and start_step_index >= len(self.steps):
                await self._save_checkpoint(
                    checkpoint=checkpoint,
                    status="completed",
                    run_id=run_id,
                    original_input=original_input,
                    next_step_index=len(self.steps),
                    previous=previous,
                    state=state,
                    traces=traces,
                    checkpoint_started_at=checkpoint_started_at,
                )
        except _StepFailure as failure:
            if checkpoint is not None:
                await self._save_checkpoint(
                    checkpoint=checkpoint,
                    status="failed",
                    run_id=run_id,
                    original_input=original_input,
                    next_step_index=failed_step_index,
                    previous=checkpoint_previous,
                    state=checkpoint_state,
                    traces=traces,
                    checkpoint_started_at=checkpoint_started_at,
                    error=str(failure.original_error),
                )
            duration = time.perf_counter() - started_perf
            result = FlowResult(
                output=previous,
                traces=traces,
                duration_seconds=duration,
                success=False,
                failed_step=failure.step_name,
                state=state,
                metadata=metadata,
                error=str(failure.original_error),
                exception=failure.original_error,
            )
            await self._emit(
                FlowEvent(
                    type="flow_failed",
                    run_id=run_id,
                    flow_name=self.flow_name,
                    timestamp=datetime.now(UTC),
                    output=result.output,
                    error=result.error,
                    result=result,
                    metadata=metadata.copy(),
                )
            )
            return result

        duration = time.perf_counter() - started_perf
        result = FlowResult(
            output=previous,
            traces=traces,
            duration_seconds=duration,
            success=True,
            state=state,
            metadata=metadata,
        )
        await self._emit(
            FlowEvent(
                type="flow_completed",
                run_id=run_id,
                flow_name=self.flow_name,
                timestamp=datetime.now(UTC),
                output=result.output,
                result=result,
                metadata=metadata.copy(),
            )
        )
        return result

    async def _save_checkpoint(
        self,
        *,
        checkpoint: JsonCheckpointStore,
        status: str,
        run_id: str,
        original_input: FlowInput,
        next_step_index: int,
        previous: Any,
        state: dict[str, Any],
        traces: list[StepTrace],
        checkpoint_started_at: str,
        error: str | None = None,
    ) -> None:
        json_clone(original_input, label="original_input")
        json_clone(previous, label="previous")
        json_clone(state, label="state")
        json_clone([trace.to_dict() for trace in traces], label="traces")
        checkpoint.save(
            checkpoint_payload(
                status=status,
                run_id=run_id,
                flow_name=self.flow_name,
                flow_signature=self.flow_signature,
                original_input=original_input,
                next_step_index=next_step_index,
                previous=previous,
                state=state,
                traces=traces,
                started_at=checkpoint_started_at,
                error=error,
            )
        )
        await self._emit(
            FlowEvent(
                type="checkpoint_saved",
                run_id=run_id,
                flow_name=self.flow_name,
                timestamp=datetime.now(UTC),
                input=original_input,
                metadata={
                    "checkpoint_path": str(checkpoint.path),
                    "status": status,
                    "next_step_index": next_step_index,
                },
            )
        )

    def _validate_checkpoint(self, snapshot: CheckpointSnapshot) -> None:
        if snapshot.status == "completed":
            raise CheckpointError("Cannot resume a completed checkpoint")
        if snapshot.flow_name != self.flow_name:
            raise CheckpointError("Checkpoint flow name does not match this flow")
        if snapshot.flow_signature != self.flow_signature:
            raise CheckpointError("Checkpoint flow signature does not match this flow")
        if snapshot.next_step_index < 0 or snapshot.next_step_index > len(self.steps):
            raise CheckpointError("Checkpoint next_step_index is out of range")

    async def _emit(self, event: FlowEvent) -> None:
        if self._event_handler is None:
            return
        maybe_awaitable = self._event_handler(event)
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable

    async def _run_item(
        self,
        *,
        item: FlowItem,
        original_input: FlowInput,
        previous: Any,
        state: dict[str, Any],
        traces: list[StepTrace],
        run_id: str,
        step_index: int,
        parallel_group_id: str | None,
    ) -> Any:
        if isinstance(item, Condition):
            return await self._run_condition(
                condition=item,
                original_input=original_input,
                previous=previous,
                state=state,
                traces=traces,
                run_id=run_id,
                step_index=step_index,
            )

        if _is_parallel_group(item):
            return await self._run_parallel_group(
                items=list(item),
                original_input=original_input,
                previous=previous,
                state=state,
                traces=traces,
                run_id=run_id,
                step_index=step_index,
            )

        return await self._run_step_with_retries(
            step=_ensure_step(item),
            original_input=original_input,
            previous=previous,
            state=state,
            traces=traces,
            run_id=run_id,
            step_index=step_index,
            parallel_group_id=parallel_group_id,
        )

    async def _run_condition(
        self,
        *,
        condition: Condition,
        original_input: FlowInput,
        previous: Any,
        state: dict[str, Any],
        traces: list[StepTrace],
        run_id: str,
        step_index: int,
    ) -> Any:
        context = StepContext(
            previous=previous,
            original_input=original_input,
            state=state,
            metadata={
                "run_id": run_id,
                "flow_name": self.flow_name,
                "step_index": step_index,
                "condition_name": condition.name,
            },
        )
        branch = condition.then if condition.when(context) else condition.otherwise
        if branch is None:
            return previous
        return await self._run_item(
            item=branch,
            original_input=original_input,
            previous=previous,
            state=state,
            traces=traces,
            run_id=run_id,
            step_index=step_index,
            parallel_group_id=None,
        )

    async def _run_parallel_group(
        self,
        *,
        items: list[Any],
        original_input: FlowInput,
        previous: Any,
        state: dict[str, Any],
        traces: list[StepTrace],
        run_id: str,
        step_index: int,
    ) -> dict[str, Any]:
        group_id = str(uuid4())
        steps = [_ensure_step(item) for item in items]
        results = await asyncio.gather(
            *[
                self._run_step_with_retries(
                    step=parallel_step,
                    original_input=original_input,
                    previous=previous,
                    state=state,
                    traces=traces,
                    run_id=run_id,
                    step_index=step_index,
                    parallel_group_id=group_id,
                )
                for parallel_step in steps
            ],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, _StepFailure):
                raise result

        return {
            parallel_step.name: result
            for parallel_step, result in zip(steps, results, strict=True)
        }

    async def _run_step_with_retries(
        self,
        *,
        step: Step,
        original_input: FlowInput,
        previous: Any,
        state: dict[str, Any],
        traces: list[StepTrace],
        run_id: str,
        step_index: int,
        parallel_group_id: str | None,
    ) -> Any:
        policy = step.retry_policy or self.retry_policy
        delay = policy.delay
        last_error: BaseException | None = None

        for attempt in range(1, policy.max_attempts + 1):
            started_at = datetime.now(UTC)
            started_perf = time.perf_counter()
            context = StepContext(
                previous=previous,
                original_input=original_input,
                state=state,
                metadata={
                    "run_id": run_id,
                    "flow_name": self.flow_name,
                    "step_index": step_index,
                    "step_name": step.name,
                    "attempt": attempt,
                    "parallel_group_id": parallel_group_id,
                },
            )
            await self._emit(
                FlowEvent(
                    type="step_started",
                    run_id=run_id,
                    flow_name=self.flow_name,
                    timestamp=started_at,
                    step_name=step.name,
                    step_index=step_index,
                    attempt=attempt,
                    parallel_group_id=parallel_group_id,
                    input=original_input,
                    metadata=context.metadata.copy(),
                )
            )

            try:
                output = await _call_step(step, original_input, context)
            except Exception as exc:  # noqa: BLE001 - traces intentionally capture all failures
                last_error = exc
                ended_at = datetime.now(UTC)
                trace = StepTrace(
                    step_name=step.name,
                    input=original_input,
                    output=None,
                    error=f"{type(exc).__name__}: {exc}",
                    attempt=attempt,
                    parallel_group_id=parallel_group_id,
                    duration_seconds=time.perf_counter() - started_perf,
                    started_at=started_at,
                    ended_at=ended_at,
                )
                traces.append(trace)
                await self._emit(
                    FlowEvent(
                        type="step_failed",
                        run_id=run_id,
                        flow_name=self.flow_name,
                        timestamp=ended_at,
                        step_name=step.name,
                        step_index=step_index,
                        attempt=attempt,
                        parallel_group_id=parallel_group_id,
                        input=original_input,
                        error=trace.error,
                        trace=trace,
                        metadata=context.metadata.copy(),
                    )
                )
                if attempt < policy.max_attempts:
                    await self._emit(
                        FlowEvent(
                            type="retry_scheduled",
                            run_id=run_id,
                            flow_name=self.flow_name,
                            timestamp=datetime.now(UTC),
                            step_name=step.name,
                            step_index=step_index,
                            attempt=attempt,
                            parallel_group_id=parallel_group_id,
                            input=original_input,
                            error=trace.error,
                            retry_delay=delay,
                            trace=trace,
                            metadata=context.metadata.copy(),
                        )
                    )
                    if delay:
                        await asyncio.sleep(delay)
                    delay *= policy.backoff
                    continue
                raise _StepFailure(step_name=step.name, original_error=exc) from exc

            ended_at = datetime.now(UTC)
            trace = StepTrace(
                step_name=step.name,
                input=original_input,
                output=output,
                error=None,
                attempt=attempt,
                parallel_group_id=parallel_group_id,
                duration_seconds=time.perf_counter() - started_perf,
                started_at=started_at,
                ended_at=ended_at,
            )
            traces.append(trace)
            await self._emit(
                FlowEvent(
                    type="step_completed",
                    run_id=run_id,
                    flow_name=self.flow_name,
                    timestamp=ended_at,
                    step_name=step.name,
                    step_index=step_index,
                    attempt=attempt,
                    parallel_group_id=parallel_group_id,
                    input=original_input,
                    output=output,
                    trace=trace,
                    metadata=context.metadata.copy(),
                )
            )
            return output

        raise _StepFailure(
            step_name=step.name,
            original_error=last_error
            or RuntimeError("step failed without an exception"),
        )


async def _call_step(step: Step, input: FlowInput, context: StepContext) -> Any:
    if inspect.iscoroutinefunction(step.func):
        return await step.func(input, context)

    result = await asyncio.to_thread(step.func, input, context)
    if inspect.isawaitable(result):
        return await result
    return result


def _ensure_step(item: Any) -> Step:
    if isinstance(item, Step):
        return item
    if callable(item):
        name = getattr(item, "__name__", item.__class__.__name__)
        return Step(func=item, name=name)
    raise TypeError(f"Expected a step function, got {type(item).__name__}")


def _is_parallel_group(item: Any) -> TypeGuard[list[Any] | tuple[Any, ...]]:
    return isinstance(item, list | tuple)


def flow_signature(items: Sequence[FlowItem]) -> list[dict[str, Any]]:
    return [_item_signature(item) for item in items]


def _item_signature(item: Any) -> dict[str, Any]:
    if isinstance(item, Condition):
        return {
            "type": "condition",
            "name": item.name,
            "then": _item_signature(item.then),
            "otherwise": (
                _item_signature(item.otherwise) if item.otherwise is not None else None
            ),
        }

    if _is_parallel_group(item):
        return {
            "type": "parallel",
            "items": [_item_signature(branch) for branch in item],
        }

    step = _ensure_step(item)
    return {"type": "step", "name": step.name}
