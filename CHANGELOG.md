# Changelog

## 0.4.0

- Add `JsonCheckpointStore` for local JSON checkpoints.
- Add `Flow.run(..., checkpoint=store)` and `Flow.resume(store)`.
- Add checkpoint support to `Flow.events(...)` and new `Flow.resume_events(...)`.
- Emit `checkpoint_saved` and `checkpoint_loaded` lifecycle events.
- Add strict JSON serialization checks and `CheckpointError`.
- Add checkpoint/resume tests, example, and documentation.

## 0.3.0

- Add `human_input(...)` step helper for lightweight human review gates.
- Support stdin fallback for local demos.
- Support sync and async provider callbacks for tests and applications.
- Reuse existing retry, trace, and event behavior for human input steps.
- Add human review example and documentation.

## 0.2.0

- Add `Flow.events(input)` async iterator for live flow observability.
- Add public `FlowEvent` model with JSON-safe `to_dict()`.
- Emit flow started, step started, step completed, step failed, retry scheduled,
  flow completed, and flow failed events.
- Keep `Flow.run()` behavior unchanged.
- Add live events example and event tests.

## 0.1.0

- Initial public release.
- Add sequential, parallel, and conditional flows.
- Add retry policies, shared state, flat traces, and optional LiteLLM-backed
  `Agent`.
