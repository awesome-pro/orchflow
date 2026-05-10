from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, TypeGuard


class StructuredOutputError(RuntimeError):
    """Raised when structured agent output cannot be parsed or validated."""


@dataclass(slots=True)
class AgentConfig:
    """Provider configuration for Agent calls."""

    model: str
    temperature: float | None = None
    max_tokens: int | None = None
    api_base: str | None = None
    api_key: str | None = None
    timeout: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Agent:
    """Stateless, role-based LLM helper backed by optional LiteLLM."""

    name: str
    role: str
    model: str | None = None
    config: AgentConfig | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    tools: Sequence[Callable[..., Any]] = field(default_factory=tuple)

    async def run(self, prompt: str, context: Any | None = None) -> str:
        response = await self._complete(prompt, context=context)
        return _extract_content(response)

    async def run_structured(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | type[Any],
        context: Any | None = None,
    ) -> Any:
        response = await self._complete(
            prompt,
            context=context,
            response_format=_response_format_for_schema(schema),
        )
        content = _extract_content(response)
        if not content:
            raise StructuredOutputError("Structured agent output was empty")
        return _parse_structured_content(content, schema)

    async def _complete(
        self,
        prompt: str,
        *,
        context: Any | None = None,
        response_format: Any | None = None,
    ) -> Any:
        if self.tools:
            raise NotImplementedError(
                "Agent tool execution is outside Orchflow v0.5. "
                "Call tools inside normal steps or create an Agent without tools."
            )

        acompletion = _load_litellm_acompletion()
        kwargs = self._completion_kwargs(context=context)
        if response_format is not None:
            kwargs["response_format"] = response_format

        return await acompletion(
            model=self._resolved_model(),
            messages=[
                {"role": "system", "content": self.role},
                {"role": "user", "content": prompt},
            ],
            **kwargs,
        )

    def _resolved_model(self) -> str:
        model = self.model or (self.config.model if self.config else None)
        if not model:
            raise ValueError("Agent requires a model or AgentConfig model")
        return model

    def _completion_kwargs(self, *, context: Any | None) -> dict[str, Any]:
        kwargs = dict(self.config.extra) if self.config else {}
        temperature = _resolve_option(self.temperature, self.config, "temperature")
        max_tokens = _resolve_option(self.max_tokens, self.config, "max_tokens")
        api_base = _resolve_option(None, self.config, "api_base")
        api_key = _resolve_option(None, self.config, "api_key")
        timeout = _resolve_option(None, self.config, "timeout")

        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if api_base is not None:
            kwargs["api_base"] = api_base
        if api_key is not None:
            kwargs["api_key"] = api_key
        if timeout is not None:
            kwargs["timeout"] = timeout
        if context is not None:
            kwargs["metadata"] = {"orchflow_context": str(context.metadata)}
        return kwargs


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


def _load_litellm_acompletion() -> Callable[..., Any]:
    try:
        litellm = import_module("litellm")
    except ImportError as exc:
        raise ImportError(
            "LiteLLM is required for Agent.run(). "
            "Install it with: pip install 'orchflow[litellm]'"
        ) from exc
    return litellm.acompletion


def _resolve_option(
    direct_value: Any,
    config: AgentConfig | None,
    field_name: str,
) -> Any:
    if direct_value is not None:
        return direct_value
    if config is None:
        return None
    return getattr(config, field_name)


def _response_format_for_schema(schema: dict[str, Any] | type[Any]) -> Any:
    if isinstance(schema, dict):
        if schema.get("type") in {"json_object", "json_schema"}:
            return schema
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema.get("title", "orchflow_schema"),
                "schema": schema,
            },
        }
    if _is_pydantic_model_class(schema):
        return schema
    raise StructuredOutputError(
        "Structured schema must be a JSON schema dict or Pydantic model class"
    )


def _parse_structured_content(content: str, schema: dict[str, Any] | type[Any]) -> Any:
    if _is_pydantic_model_class(schema):
        try:
            return schema.model_validate_json(content)
        except Exception as exc:  # noqa: BLE001 - optional Pydantic validation
            raise StructuredOutputError("Structured output validation failed") from exc

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError("Structured output was not valid JSON") from exc


def _is_pydantic_model_class(schema: Any) -> TypeGuard[type[Any]]:
    return isinstance(schema, type) and callable(
        getattr(schema, "model_validate_json", None)
    )
