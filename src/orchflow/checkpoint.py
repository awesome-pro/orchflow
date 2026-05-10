from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import StepTrace

CHECKPOINT_VERSION = 1


class CheckpointError(RuntimeError):
    """Raised when checkpoint persistence or resume validation fails."""


@dataclass(slots=True)
class CheckpointSnapshot:
    status: str
    run_id: str
    flow_name: str
    flow_signature: list[dict[str, Any]]
    original_input: Any
    next_step_index: int
    previous: Any
    state: dict[str, Any]
    traces: list[StepTrace]
    started_at: str
    updated_at: str
    error: str | None = None


class JsonCheckpointStore:
    """Local JSON checkpoint store."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> CheckpointSnapshot:
        if not self.path.exists():
            raise CheckpointError(f"Checkpoint file does not exist: {self.path}")

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CheckpointError(f"Invalid checkpoint JSON: {self.path}") from exc
        except OSError as exc:
            raise CheckpointError(f"Could not read checkpoint: {self.path}") from exc

        return _snapshot_from_payload(payload)

    def save(self, payload: dict[str, Any]) -> None:
        payload = _json_clone(payload)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_name(f"{self.path.name}.tmp")
        try:
            temporary_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
        except OSError as exc:
            raise CheckpointError(f"Could not write checkpoint: {self.path}") from exc


def checkpoint_payload(
    *,
    status: str,
    run_id: str,
    flow_name: str,
    flow_signature: list[dict[str, Any]],
    original_input: Any,
    next_step_index: int,
    previous: Any,
    state: dict[str, Any],
    traces: list[StepTrace],
    started_at: str,
    error: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "version": CHECKPOINT_VERSION,
        "status": status,
        "run_id": run_id,
        "flow_name": flow_name,
        "flow_signature": flow_signature,
        "original_input": original_input,
        "next_step_index": next_step_index,
        "previous": previous,
        "state": state,
        "traces": [trace.to_dict() for trace in traces],
        "started_at": started_at,
        "updated_at": now,
        "error": error,
    }
    if status == "completed":
        payload["completed_at"] = now
    return payload


def json_clone(value: Any, *, label: str) -> Any:
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError) as exc:
        raise CheckpointError(f"Checkpoint {label} must be JSON serializable") from exc


def _json_clone(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(json.dumps(payload))
    except (TypeError, ValueError) as exc:
        raise CheckpointError("Checkpoint payload must be JSON serializable") from exc


def _snapshot_from_payload(payload: Any) -> CheckpointSnapshot:
    if not isinstance(payload, dict):
        raise CheckpointError("Checkpoint payload must be a JSON object")
    if payload.get("version") != CHECKPOINT_VERSION:
        raise CheckpointError("Unsupported checkpoint version")

    try:
        status = payload["status"]
        run_id = payload["run_id"]
        flow_name = payload["flow_name"]
        flow_signature = payload["flow_signature"]
        original_input = payload["original_input"]
        next_step_index = payload["next_step_index"]
        previous = payload["previous"]
        state = payload["state"]
        trace_payloads = payload["traces"]
        started_at = payload["started_at"]
        updated_at = payload["updated_at"]
    except KeyError as exc:
        raise CheckpointError(f"Missing checkpoint field: {exc.args[0]}") from exc

    if status not in {"running", "failed", "completed"}:
        raise CheckpointError(f"Unsupported checkpoint status: {status}")
    if not isinstance(flow_signature, list):
        raise CheckpointError("Checkpoint flow_signature must be a list")
    if not isinstance(next_step_index, int):
        raise CheckpointError("Checkpoint next_step_index must be an integer")
    if not isinstance(state, dict):
        raise CheckpointError("Checkpoint state must be an object")
    if not isinstance(trace_payloads, list):
        raise CheckpointError("Checkpoint traces must be a list")

    try:
        traces = [StepTrace.from_dict(trace) for trace in trace_payloads]
    except (KeyError, TypeError, ValueError) as exc:
        raise CheckpointError("Invalid checkpoint trace data") from exc

    return CheckpointSnapshot(
        status=status,
        run_id=run_id,
        flow_name=flow_name,
        flow_signature=flow_signature,
        original_input=original_input,
        next_step_index=next_step_index,
        previous=previous,
        state=state,
        traces=traces,
        started_at=started_at,
        updated_at=updated_at,
        error=payload.get("error"),
    )
