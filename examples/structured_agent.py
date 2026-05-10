from __future__ import annotations

import asyncio

from orchflow import Agent, AgentConfig, Flow, StepContext, step

extractor = Agent(
    name="extractor",
    role="Extract structured data. Return only JSON.",
    config=AgentConfig(
        model="gpt-4o-mini",
        temperature=0,
    ),
)

person_schema = {
    "title": "person",
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "company": {"type": "string"},
    },
    "required": ["name", "company"],
}


@step
async def extract_person(input: str, context: StepContext) -> dict:
    return await extractor.run_structured(input, schema=person_schema, context=context)


async def main() -> None:
    result = await Flow([extract_person], name="structured-agent-demo").run(
        "Ada works at OpenAI."
    )
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
