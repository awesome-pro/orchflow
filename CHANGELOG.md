# Changelog

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
