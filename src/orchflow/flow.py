from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import suppress
from typing import Any

from .checkpoint import JsonCheckpointStore
from .condition import Condition
from .errors import FlowExecutionError
from .models import FlowEvent, FlowResult
from .retry import RetryPolicy
from .runner import FlowItem, FlowRunner
from .step import FlowInput, Step


class _EventsDone:
    pass


_EVENTS_DONE = _EventsDone()


class Flow:
    """Orchestrates sequential, parallel, and conditional step pipelines."""

    def __init__(
        self,
        steps: Sequence[FlowItem],
        *,
        name: str = "flow",
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        _validate_flow_items(steps)
        self.steps = list(steps)
        self.name = name
        self.retry_policy = retry_policy or RetryPolicy()

    async def run(
        self,
        input: FlowInput,
        *,
        raise_on_error: bool = True,
        checkpoint: JsonCheckpointStore | None = None,
    ) -> FlowResult:
        runner = FlowRunner(
            steps=self.steps,
            flow_name=self.name,
            retry_policy=self.retry_policy,
        )
        result = await runner.run(input, checkpoint=checkpoint)
        _raise_if_failed(result, raise_on_error=raise_on_error)
        return result

    async def resume(
        self,
        checkpoint: JsonCheckpointStore,
        *,
        raise_on_error: bool = True,
    ) -> FlowResult:
        runner = FlowRunner(
            steps=self.steps,
            flow_name=self.name,
            retry_policy=self.retry_policy,
        )
        result = await runner.resume(checkpoint)
        _raise_if_failed(result, raise_on_error=raise_on_error)
        return result

    async def events(
        self,
        input: FlowInput,
        *,
        raise_on_error: bool = False,
        checkpoint: JsonCheckpointStore | None = None,
    ) -> AsyncIterator[FlowEvent]:
        async def run_with_events(emit) -> FlowResult:
            runner = FlowRunner(
                steps=self.steps,
                flow_name=self.name,
                retry_policy=self.retry_policy,
                event_handler=emit,
            )
            return await runner.run(input, checkpoint=checkpoint)

        async for event in self._event_stream(
            run_with_events,
            raise_on_error=raise_on_error,
        ):
            yield event

    async def resume_events(
        self,
        checkpoint: JsonCheckpointStore,
        *,
        raise_on_error: bool = False,
    ) -> AsyncIterator[FlowEvent]:
        async def run_with_events(emit) -> FlowResult:
            runner = FlowRunner(
                steps=self.steps,
                flow_name=self.name,
                retry_policy=self.retry_policy,
                event_handler=emit,
            )
            return await runner.resume(checkpoint)

        async for event in self._event_stream(
            run_with_events,
            raise_on_error=raise_on_error,
        ):
            yield event

    async def _event_stream(
        self,
        run_with_events,
        *,
        raise_on_error: bool,
    ) -> AsyncIterator[FlowEvent]:
        queue: asyncio.Queue[FlowEvent | _EventsDone] = asyncio.Queue()
        result: FlowResult | None = None
        unexpected_error: BaseException | None = None

        async def emit(event: FlowEvent) -> None:
            await queue.put(event)

        async def run_flow() -> None:
            nonlocal result, unexpected_error
            try:
                result = await run_with_events(emit)
            except Exception as exc:  # noqa: BLE001 - surfaced after queued events
                unexpected_error = exc
            finally:
                await queue.put(_EVENTS_DONE)

        task = asyncio.create_task(run_flow())
        completed = False

        try:
            while True:
                event = await queue.get()
                if isinstance(event, _EventsDone):
                    completed = True
                    break
                yield event
        finally:
            if not completed and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

        if not completed:
            return
        await task
        if unexpected_error is not None:
            raise unexpected_error
        if result is not None:
            _raise_if_failed(result, raise_on_error=raise_on_error)

    def __repr__(self) -> str:
        return f"Flow(name={self.name!r}, steps={len(self.steps)})"


def _validate_flow_items(steps: Sequence[FlowItem]) -> None:
    if not steps:
        raise ValueError("Flow requires at least one step")

    seen_names: set[str] = set()
    for item in steps:
        _collect_step_names(item, seen_names=seen_names, inside_parallel=False)


def _collect_step_names(
    item: Any,
    *,
    seen_names: set[str],
    inside_parallel: bool,
) -> None:
    if isinstance(item, Condition):
        _collect_step_names(
            item.then,
            seen_names=seen_names,
            inside_parallel=inside_parallel,
        )
        if item.otherwise is not None:
            _collect_step_names(
                item.otherwise,
                seen_names=seen_names,
                inside_parallel=inside_parallel,
            )
        return

    if isinstance(item, list | tuple):
        if inside_parallel:
            raise TypeError("Nested parallel step groups are not supported")
        if not item:
            raise ValueError("Parallel step groups require at least one step")
        for branch in item:
            _collect_step_names(
                branch,
                seen_names=seen_names,
                inside_parallel=True,
            )
        return

    step_name = _step_name(item)
    if step_name in seen_names:
        raise ValueError(f"Duplicate step name: {step_name}")
    seen_names.add(step_name)


def _step_name(item: Any) -> str:
    if isinstance(item, Step):
        return item.name
    if callable(item):
        return getattr(item, "__name__", item.__class__.__name__)
    raise TypeError(f"Expected a step function, got {type(item).__name__}")


def _raise_if_failed(result: FlowResult, *, raise_on_error: bool) -> None:
    if not result.success and raise_on_error:
        raise FlowExecutionError(
            failed_step=result.failed_step or "unknown",
            original_error=result.exception
            or RuntimeError(result.error or "flow failed"),
            result=result,
        )
