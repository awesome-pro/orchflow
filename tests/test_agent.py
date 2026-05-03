from __future__ import annotations

import importlib.util

import pytest

import orchflow
from orchflow import Agent
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


async def test_agent_rejects_tool_calling_in_v01() -> None:
    agent = Agent(
        name="tool-agent",
        role="Use tools.",
        model="gpt-4o-mini",
        tools=[lambda: "tool-result"],
    )

    with pytest.raises(NotImplementedError, match="outside Orchflow v0.1"):
        await agent.run("Use the tool")
