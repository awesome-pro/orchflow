from __future__ import annotations

import asyncio
import builtins
import inspect
from collections.abc import Awaitable, Callable
from typing import TypeAlias

from .step import FlowInput, Step, StepContext

HumanInputProvider: TypeAlias = Callable[[str, StepContext], str | Awaitable[str]]
HumanPrompt: TypeAlias = str | Callable[[StepContext], str]


def human_input(
    prompt: HumanPrompt,
    *,
    name: str = "human_input",
    provider: HumanInputProvider | None = None,
) -> Step:
    """Create a step that asks a human for text input."""

    async def ask_human(input: FlowInput, context: StepContext) -> str:
        prompt_text = prompt(context) if callable(prompt) else prompt
        if provider is None:
            return await asyncio.to_thread(builtins.input, prompt_text)

        response = provider(prompt_text, context)
        if inspect.isawaitable(response):
            return await response
        return response

    ask_human.__name__ = name
    return Step(func=ask_human, name=name)
