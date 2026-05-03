from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeGuard
from uuid import uuid4

from .condition import Condition
from .models import FlowResult, StepTrace
from .retry import RetryPolicy
from .step import FlowInput, Step, StepCallable, StepContext

FlowItem = Step | StepCallable | Condition | list[Any] | tuple[Any, ...]


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
    ) -> None:
        self.steps = list(steps)
        self.flow_name = flow_name
        self.retry_policy = retry_policy

    async def run(self, input: FlowInput) -> FlowResult:
        run_id = str(uuid4())
        state: dict[str, Any] = {}
        traces: list[StepTrace] = []
        previous: Any = None
        started_perf = time.perf_counter()
        started_at = datetime.now(UTC)
        metadata = {
            "run_id": run_id,
            "flow_name": self.flow_name,
            "started_at": started_at.isoformat(),
        }

        try:
            for index, item in enumerate(self.steps):
                previous = await self._run_item(
                    item=item,
                    original_input=input,
                    previous=previous,
                    state=state,
                    traces=traces,
                    run_id=run_id,
                    step_index=index,
                    parallel_group_id=None,
                )
        except _StepFailure as failure:
            duration = time.perf_counter() - started_perf
            return FlowResult(
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

        duration = time.perf_counter() - started_perf
        return FlowResult(
            output=previous,
            traces=traces,
            duration_seconds=duration,
            success=True,
            state=state,
            metadata=metadata,
        )

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

            try:
                output = await _call_step(step, original_input, context)
            except Exception as exc:  # noqa: BLE001 - traces intentionally capture all failures
                last_error = exc
                ended_at = datetime.now(UTC)
                traces.append(
                    StepTrace(
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
                )
                if attempt < policy.max_attempts:
                    if delay:
                        await asyncio.sleep(delay)
                    delay *= policy.backoff
                    continue
                raise _StepFailure(step_name=step.name, original_error=exc) from exc

            ended_at = datetime.now(UTC)
            traces.append(
                StepTrace(
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
