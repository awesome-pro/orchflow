from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .step import StepContext


@dataclass(frozen=True, slots=True)
class Condition:
    """Route to one flow item or another based on the current context."""

    when: Callable[[StepContext], bool]
    then: Any
    otherwise: Any | None = None
    name: str | None = None


def condition(
    *,
    when: Callable[[StepContext], bool],
    then: Any,
    otherwise: Any | None = None,
    name: str | None = None,
) -> Condition:
    return Condition(when=when, then=then, otherwise=otherwise, name=name)
