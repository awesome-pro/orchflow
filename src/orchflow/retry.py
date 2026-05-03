from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry settings for a flow or step."""

    max_attempts: int = 1
    delay: float = 0.0
    backoff: float = 1.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.delay < 0:
            raise ValueError("delay must be greater than or equal to 0")
        if self.backoff < 1:
            raise ValueError("backoff must be greater than or equal to 1")
