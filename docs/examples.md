# Examples

Run the offline examples:

```bash
uv run python examples/basic_sequential.py
uv run python examples/parallel_steps.py
uv run python examples/conditional_flow.py
uv run python examples/live_events.py
uv run python examples/human_review.py
uv run python examples/checkpoint_resume.py
```

Run the optional LiteLLM example after installing the extra and configuring a
provider API key:

```bash
uv sync --extra dev --extra litellm
uv run python examples/litellm_agent.py
uv run python examples/structured_agent.py
```
