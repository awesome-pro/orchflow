from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeAlias, overload

from .retry import RetryPolicy

FlowInput: TypeAlias = str | dict[str, Any]
StepOutput: TypeAlias = Any
StepReturn: TypeAlias = Any
StepCallable: TypeAlias = Callable[..., Any]


@dataclass(slots=True)
class StepContext:
    """Runtime context passed to every step."""

    previous: Any
    original_input: FlowInput
    state: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Step:
    """Internal wrapper around a user step function."""

    func: StepCallable
    name: str
    retry_policy: RetryPolicy | None = None

    @property
    def __name__(self) -> str:
        return self.name

    def __call__(self, input: FlowInput, context: StepContext) -> StepReturn:
        return self.func(input, context)


@overload
def step(func: StepCallable) -> Step: ...


@overload
def step(
    func: None = None,
    *,
    name: str | None = None,
    retry: int | None = None,
    retry_delay: float = 0.0,
    backoff: float = 1.0,
) -> Callable[[StepCallable], Step]: ...


def step(
    func: StepCallable | None = None,
    *,
    name: str | None = None,
    retry: int | None = None,
    retry_delay: float = 0.0,
    backoff: float = 1.0,
) -> Step | Callable[[StepCallable], Step]:
    """Decorate a function as an Orchflow step."""

    def decorate(target: StepCallable) -> Step:
        step_name = name or target.__name__
        retry_policy = None
        if retry is not None:
            retry_policy = RetryPolicy(
                max_attempts=retry,
                delay=retry_delay,
                backoff=backoff,
            )
        return Step(func=target, name=step_name, retry_policy=retry_policy)

    if func is None:
        return decorate
    return decorate(func)
