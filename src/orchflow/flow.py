from __future__ import annotations

from collections.abc import Sequence

from .errors import FlowExecutionError
from .models import FlowResult
from .retry import RetryPolicy
from .runner import FlowItem, FlowRunner
from .step import FlowInput


class Flow:
    """Orchestrates sequential, parallel, and conditional step pipelines."""

    def __init__(
        self,
        steps: Sequence[FlowItem],
        *,
        name: str = "flow",
        retry_policy: RetryPolicy | None = None,
    ) -> None:
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
