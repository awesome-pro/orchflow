from __future__ import annotations

import importlib.util
from types import SimpleNamespace

import pytest

import orchflow
from orchflow import Agent, AgentConfig, StructuredOutputError
from orchflow.testing import CallableAgent, MockAgent


async def test_testing_helpers_are_not_top_level_exports() -> None:
    assert not hasattr(orchflow, "MockAgent")
    assert not hasattr(orchflow, "CallableAgent")

    agent = MockAgent(["one", "two"])
    assert await agent.run("first") == "one"
    assert await agent.run("second") == "two"
    assert agent.prompts == ["first", "second"]


async def test_callable_agent_supports_sync_callable() -> None:
    agent = CallableAgent(lambda prompt, context: prompt.upper())

    assert await agent.run("hello") == "HELLO"
    assert agent.prompts == ["hello"]


async def test_callable_agent_supports_async_callable() -> None:
    async def respond(prompt, context):
        return f"async:{prompt}"

    agent = CallableAgent(respond)

    assert await agent.run("hello") == "async:hello"


async def test_agent_explains_missing_litellm_dependency() -> None:
    if importlib.util.find_spec("litellm") is not None:
        pytest.skip("LiteLLM is installed in this environment")

    agent = Agent(name="writer", role="Write clearly.", model="gpt-4o-mini")

    with pytest.raises(ImportError, match=r"orchflow\[litellm\]"):
        await agent.run("Draft a sentence")


async def test_agent_rejects_tool_calling_in_v05() -> None:
    agent = Agent(
        name="tool-agent",
        role="Use tools.",
        model="gpt-4o-mini",
        tools=[lambda: "tool-result"],
    )

    with pytest.raises(NotImplementedError, match="outside Orchflow v0.5"):
        await agent.run("Use the tool")


async def test_agent_run_uses_fake_litellm_and_returns_text(monkeypatch) -> None:
    calls: list[dict] = []

    async def acompletion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": "hello"}}]}

    monkeypatch.setitem(
        __import__("sys").modules,
        "litellm",
        SimpleNamespace(acompletion=acompletion),
    )

    agent = Agent(name="writer", role="Write clearly.", model="fake/model")
    result = await agent.run("Draft")

    assert result == "hello"
    assert calls[0]["model"] == "fake/model"
    assert calls[0]["messages"] == [
        {"role": "system", "content": "Write clearly."},
        {"role": "user", "content": "Draft"},
    ]


async def test_agent_config_merges_kwargs_with_direct_overrides(monkeypatch) -> None:
    calls: list[dict] = []

    async def acompletion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": "configured"}}]}

    monkeypatch.setitem(
        __import__("sys").modules,
        "litellm",
        SimpleNamespace(acompletion=acompletion),
    )

    agent = Agent(
        name="writer",
        role="Write clearly.",
        model="direct/model",
        temperature=0.2,
        config=AgentConfig(
            model="config/model",
            temperature=0.8,
            max_tokens=50,
            api_base="https://example.test",
            api_key="secret",
            timeout=30,
            extra={"drop_params": True},
        ),
    )

    assert await agent.run("Draft") == "configured"

    call = calls[0]
    assert call["model"] == "direct/model"
    assert call["temperature"] == 0.2
    assert call["max_tokens"] == 50
    assert call["api_base"] == "https://example.test"
    assert call["api_key"] == "secret"
    assert call["timeout"] == 30
    assert call["drop_params"] is True


async def test_run_structured_parses_json_schema_output(monkeypatch) -> None:
    calls: list[dict] = []

    async def acompletion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": '{"name": "Ada"}'}}]}

    monkeypatch.setitem(
        __import__("sys").modules,
        "litellm",
        SimpleNamespace(acompletion=acompletion),
    )

    agent = Agent(
        name="extractor",
        role="Extract JSON.",
        config=AgentConfig(model="fake/model"),
    )
    parsed = await agent.run_structured(
        "Extract name",
        schema={
            "title": "person",
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    )

    assert parsed == {"name": "Ada"}
    assert calls[0]["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "person",
            "schema": {
                "title": "person",
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    }


async def test_run_structured_supports_pydantic_style_model(monkeypatch) -> None:
    class FakeModel:
        def __init__(self, name: str) -> None:
            self.name = name

        @classmethod
        def model_validate_json(cls, content: str):
            assert content == '{"name": "Ada"}'
            return cls("Ada")

    calls: list[dict] = []

    async def acompletion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": '{"name": "Ada"}'}}]}

    monkeypatch.setitem(
        __import__("sys").modules,
        "litellm",
        SimpleNamespace(acompletion=acompletion),
    )

    agent = Agent(name="extractor", role="Extract JSON.", model="fake/model")
    parsed = await agent.run_structured("Extract name", schema=FakeModel)

    assert isinstance(parsed, FakeModel)
    assert parsed.name == "Ada"
    assert calls[0]["response_format"] is FakeModel


async def test_run_structured_invalid_json_raises(monkeypatch) -> None:
    async def acompletion(**kwargs):
        return {"choices": [{"message": {"content": "not-json"}}]}

    monkeypatch.setitem(
        __import__("sys").modules,
        "litellm",
        SimpleNamespace(acompletion=acompletion),
    )

    agent = Agent(name="extractor", role="Extract JSON.", model="fake/model")

    with pytest.raises(StructuredOutputError, match="not valid JSON"):
        await agent.run_structured("Extract", schema={"type": "object"})


async def test_run_structured_empty_content_raises(monkeypatch) -> None:
    async def acompletion(**kwargs):
        return {"choices": [{"message": {"content": ""}}]}

    monkeypatch.setitem(
        __import__("sys").modules,
        "litellm",
        SimpleNamespace(acompletion=acompletion),
    )

    agent = Agent(name="extractor", role="Extract JSON.", model="fake/model")

    with pytest.raises(StructuredOutputError, match="empty"):
        await agent.run_structured("Extract", schema={"type": "object"})


async def test_run_structured_validation_failure_raises(monkeypatch) -> None:
    class FakeModel:
        @classmethod
        def model_validate_json(cls, content: str):
            raise ValueError("bad shape")

    async def acompletion(**kwargs):
        return {"choices": [{"message": {"content": "{}"}}]}

    monkeypatch.setitem(
        __import__("sys").modules,
        "litellm",
        SimpleNamespace(acompletion=acompletion),
    )

    agent = Agent(name="extractor", role="Extract JSON.", model="fake/model")

    with pytest.raises(StructuredOutputError, match="validation failed"):
        await agent.run_structured("Extract", schema=FakeModel)


async def test_run_structured_rejects_unsupported_schema(monkeypatch) -> None:
    async def acompletion(**kwargs):
        return {"choices": [{"message": {"content": "{}"}}]}

    monkeypatch.setitem(
        __import__("sys").modules,
        "litellm",
        SimpleNamespace(acompletion=acompletion),
    )

    agent = Agent(name="extractor", role="Extract JSON.", model="fake/model")
    BadSchema = type("BadSchema", (), {})

    with pytest.raises(StructuredOutputError, match="JSON schema dict"):
        await agent.run_structured("Extract", schema=BadSchema)
