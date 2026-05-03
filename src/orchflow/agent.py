from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any


@dataclass(slots=True)
class Agent:
    """Stateless, role-based LLM helper backed by optional LiteLLM."""

    name: str
    role: str
    model: str
    temperature: float | None = None
    max_tokens: int | None = None
    tools: Sequence[Callable[..., Any]] = field(default_factory=tuple)

    async def run(self, prompt: str, context: Any | None = None) -> str:
        if self.tools:
            raise NotImplementedError(
                "Agent tool-calling loops are outside Orchflow v0.1. "
                "Call tools inside steps or create an Agent without tools."
            )

        try:
            litellm = import_module("litellm")
        except ImportError as exc:
            raise ImportError(
                "LiteLLM is required for Agent.run(). "
                "Install it with: pip install 'orchflow[litellm]'"
            ) from exc
        acompletion = litellm.acompletion

        messages = [
            {"role": "system", "content": self.role},
            {"role": "user", "content": prompt},
        ]
        kwargs: dict[str, Any] = {}
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        if context is not None:
            kwargs["metadata"] = {"orchflow_context": str(context.metadata)}

        response = await acompletion(
            model=self.model,
            messages=messages,
            **kwargs,
        )
        return _extract_content(response)


def _extract_content(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except AttributeError:
        content = response["choices"][0]["message"]["content"]

    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return str(content)
