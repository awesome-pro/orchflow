from __future__ import annotations

from .models import FlowResult


class FlowExecutionError(RuntimeError):
    """Raised when a flow fails and raise_on_error is enabled."""

    def __init__(
        self,
        failed_step: str,
        original_error: BaseException,
        result: FlowResult,
    ) -> None:
        self.failed_step = failed_step
        self.original_error = original_error
        self.result = result
        super().__init__(f"Flow failed at step '{failed_step}': {original_error}")
