from __future__ import annotations

import asyncio

from orchflow import Flow, StepContext, condition, human_input, step


@step
async def draft(input: str, context: StepContext) -> str:
    text = f"Draft for {input}: keep orchestration readable and observable."
    context.state["draft"] = text
    return text


review = human_input(
    lambda ctx: (
        "\nReview this draft:\n"
        f"{ctx.previous}\n\n"
        "Type 'approve' to publish, or write feedback for revision: "
    ),
    name="human_review",
)


@step
async def publish(input: str, context: StepContext) -> str:
    return f"Published: {context.state['draft']}"


@step
async def revise(input: str, context: StepContext) -> str:
    return f"Revision requested: {context.previous}"


async def main() -> None:
    flow = Flow(
        [
            draft,
            review,
            condition(
                when=lambda ctx: str(ctx.previous).strip().lower() == "approve",
                then=publish,
                otherwise=revise,
            ),
        ],
        name="human-review-demo",
    )
    result = await flow.run("human-in-the-loop pipelines")
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
