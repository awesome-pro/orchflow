from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class StepTrace:
    """Flat trace entry for one step attempt."""

    step_name: str
    input: Any
    output: Any | None
    error: str | None
    attempt: int
    parallel_group_id: str | None
    duration_seconds: float
    started_at: datetime
    ended_at: datetime

    @property
    def success(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "input": self.input,
            "output": self.output,
            "error": self.error,
            "attempt": self.attempt,
            "parallel_group_id": self.parallel_group_id,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "success": self.success,
        }


@dataclass(slots=True)
class FlowResult:
    """Result returned by a completed or captured failed flow run."""

    output: Any
    traces: list[StepTrace]
    duration_seconds: float
    success: bool
    failed_step: str | None = None
    state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    exception: BaseException | None = field(default=None, repr=False, compare=False)

    @property
    def duration(self) -> float:
        return self.duration_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "output": self.output,
            "traces": [trace.to_dict() for trace in self.traces],
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "failed_step": self.failed_step,
            "state": self.state,
            "metadata": self.metadata,
            "error": self.error,
        }


@dataclass(slots=True)
class FlowEvent:
    """Live execution event yielded by Flow.events()."""

    type: str
    run_id: str
    flow_name: str
    timestamp: datetime
    step_name: str | None = None
    step_index: int | None = None
    attempt: int | None = None
    parallel_group_id: str | None = None
    input: Any | None = None
    output: Any | None = None
    error: str | None = None
    retry_delay: float | None = None
    trace: StepTrace | None = None
    result: FlowResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "run_id": self.run_id,
            "flow_name": self.flow_name,
            "timestamp": self.timestamp.isoformat(),
            "step_name": self.step_name,
            "step_index": self.step_index,
            "attempt": self.attempt,
            "parallel_group_id": self.parallel_group_id,
            "input": self.input,
            "output": self.output,
            "error": self.error,
            "retry_delay": self.retry_delay,
            "trace": self.trace.to_dict() if self.trace else None,
            "result": self.result.to_dict() if self.result else None,
            "metadata": self.metadata,
        }
