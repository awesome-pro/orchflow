from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .condition import Condition
from .errors import FlowExecutionError
from .models import FlowResult
from .retry import RetryPolicy
from .runner import FlowItem, FlowRunner
from .step import FlowInput, Step


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
    ) -> FlowResult:
        runner = FlowRunner(
            steps=self.steps,
            flow_name=self.name,
            retry_policy=self.retry_policy,
        )
        result = await runner.run(input)
        if not result.success and raise_on_error:
            raise FlowExecutionError(
                failed_step=result.failed_step or "unknown",
                original_error=result.exception
                or RuntimeError(result.error or "flow failed"),
                result=result,
            )
        return result

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
