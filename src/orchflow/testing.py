from __future__ import annotations

import inspect
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MockAgent:
    """Simple async test agent that returns predefined responses."""

    responses: str | Sequence[str]
    prompts: list[str] = field(default_factory=list)
    _index: int = 0

    async def run(self, prompt: str, context: Any | None = None) -> str:
        self.prompts.append(prompt)
        if isinstance(self.responses, str):
            return self.responses
        if not self.responses:
            return ""
        if self._index >= len(self.responses):
            return self.responses[-1]
        response = self.responses[self._index]
        self._index += 1
        return response


@dataclass(slots=True)
class CallableAgent:
    """Test helper that adapts a callable to the Agent-like async run API."""

    func: Callable[..., Any]
    prompts: list[str] = field(default_factory=list)

    async def run(self, prompt: str, context: Any | None = None) -> Any:
        self.prompts.append(prompt)
        result = self.func(prompt, context)
        if inspect.isawaitable(result):
            return await result
        return result
