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

- Add `flow.events(input)` async iterator.
- Emit step started, step completed, step failed, retry scheduled, and flow
  completed events.
- Keep `flow.run()` behavior unchanged.
- Add examples for live terminal progress.

## 0.3.0 - Human Review

Goal: support simple human-in-the-loop gates without durable workflow machinery.

- Add `human_input(...)` step helper.
- Support callback-based input for tests and applications.
- Support stdin-based input for local demos.

## 0.4.0 - Checkpoints

Goal: add lightweight resume for practical workflows.

- Add JSON checkpoint adapter.
- Support resume from last successful step.
- Keep state serialization explicit and inspectable.

## 0.5.0 - Agent Adapter Upgrade

Goal: make `Agent` more useful without turning Orchflow into a full agent SDK.

- Add structured response parsing.
- Add simple provider configuration.
- Evaluate basic one-turn tool-call support as an optional adapter feature.
