# Roadmap

Orchflow should grow in small, portfolio-friendly releases. Each release should
ship one clear layer of value and remain easy to explain.

## 0.1.1 - Release Polish And DX

Goal: make the published package feel professional and frictionless.

- Add tag-based PyPI release workflow.
- Add publishing documentation.
- Add changelog.
- Add richer README examples for sequential, parallel, conditional, retries, and
  traces.
- Add package metadata improvements: repository topics, badges, and project
  URLs.
- Add tests for package import from built wheel.
- Add issue templates for bugs and feature requests.

## 0.2.0 - Events And Streaming

Goal: make flow execution observable while it runs.

- Add `flow.events(input)` async iterator. Shipped in 0.2.0.
- Emit step started, step completed, step failed, retry scheduled, and flow
  completed events. Shipped in 0.2.0.
- Keep `flow.run()` behavior unchanged. Shipped in 0.2.0.
- Add examples for live terminal progress. Shipped in 0.2.0.

## 0.3.0 - Human Review

Goal: support simple human-in-the-loop gates without durable workflow machinery.

- Add `human_input(...)` step helper. Shipped in 0.3.0.
- Support callback-based input for tests and applications. Shipped in 0.3.0.
- Support stdin-based input for local demos. Shipped in 0.3.0.
- Reuse existing retry, trace, and event behavior without new event types.
  Shipped in 0.3.0.
- Keep review text-only; users route with `condition(...)`. Shipped in 0.3.0.

## 0.4.0 - Checkpoints

Goal: add lightweight resume for practical workflows.

- Add JSON checkpoint adapter. Shipped in 0.4.0.
- Support resume from top-level item boundaries. Shipped in 0.4.0.
- Keep state serialization explicit and inspectable. Shipped in 0.4.0.
- Emit checkpoint saved and loaded events. Shipped in 0.4.0.

## 0.5.0 - Agent Adapter Upgrade

Goal: make `Agent` more useful without turning Orchflow into a full agent SDK.

- Add `AgentConfig` provider configuration. Shipped in 0.5.0.
- Add `Agent.run_structured(...)`. Shipped in 0.5.0.
- Support JSON schema dictionaries and optional Pydantic model classes.
  Shipped in 0.5.0.
- Defer tool execution to a later release.

## 0.6.0 - Tool Execution

Goal: evaluate one-turn tool execution without adding a durable agent loop.

- Add a small tool schema helper.
- Support one model-requested tool execution followed by a final model response.
- Keep long-running tool loops and MCP out of scope.
