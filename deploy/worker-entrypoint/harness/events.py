#!/usr/bin/env python3
"""Standalone Canonical Event writer used inside Worker containers."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

_ADAPTERS_DIR = Path(__file__).with_name("adapters")
if str(_ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(_ADAPTERS_DIR))

from sanitize import sanitize as _sanitize_preview  # noqa: E402

SCHEMA = "codify.worker.event/v1"
V2_CONTRACT = "codify.worker.harness/v2"
TASK_TERMINALS = {"run.completed", "run.failed"}
HARNESS_TERMINAL_TYPES = {"harness.completed", "harness.failed"}
KNOWN_TYPES = {
    "run.started",
    "model.resolved",
    "message.delta",
    "message.completed",
    "reasoning_summary.delta",
    "reasoning_summary.completed",
    "reasoning_summary.interrupted",
    "reasoning_summary.started",
    "tool.started",
    "tool.completed",
    "context.compacted",
    "provider.retry",
    "usage.updated",
    "usage.final",
    "harness.completed",
    "harness.failed",
    "delivery.started",
    "delivery.completed",
    "delivery.failed",
    "worker.finalization",
    "run.completed",
    "run.failed",
    "control.command.delivered",
    "control.command.rejected",
    "control.queue.updated",
    "agent_settled",
    "diagnostic",
}

_PREVIEW_SKIP_TYPES = {
    "message.delta",
    "reasoning_summary.delta",
    "usage.updated",
    "diagnostic",
    "agent_settled",
}
_TOOL_PREVIEW_MAX_CHARS = 500
_TEXT_PREVIEW_MAX_CHARS = 2000
_WHITESPACE = re.compile(r"\s+")


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for canonical event emission")
    return value


def _paths() -> tuple[Path, Path]:
    runtime_dir = Path(_required_env("CODIFY_RUNTIME_DIR"))
    return runtime_dir / "event.jsonl", runtime_dir / ".event.lock"


def _outer_timeout_requested(runtime_dir: Path) -> bool:
    """Return whether the backend requested a wall-clock timeout stop."""
    return (runtime_dir / ".codify-timeout").is_file()


def _normalize_payload(event_type: str, payload: dict) -> dict:
    if event_type in {"usage.updated", "usage.final"}:
        source = payload.get("usage") or {}
        payload["usage"] = {
            "input_tokens": source.get("input_tokens"),
            "cached_input_tokens": source.get("cached_input_tokens"),
            "output_tokens": source.get("output_tokens"),
            "reasoning_tokens": source.get("reasoning_tokens"),
            "cost": source.get("cost"),
            "currency": source.get("currency"),
            "engine_fields": source.get("engine_fields") or {},
        }
    return payload


def _preview_value(value: object, *, limit: int) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = str(value)
    text = _sanitize_preview(text)
    text = _WHITESPACE.sub(" ", text.replace("\r", " ").replace("\n", " ")).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…(truncated, {len(text)} chars total)"


def _timestamp(event: dict) -> str:
    try:
        return datetime.fromisoformat(str(event["occurred_at"]).replace("Z", "+00:00")).strftime(
            "%H:%M:%S"
        )
    except (KeyError, TypeError, ValueError):
        return datetime.now(UTC).strftime("%H:%M:%S")


def format_event_preview(event: dict) -> str | None:
    """Render one persisted Canonical Event as a bounded, safe log line."""
    event_type = event.get("type")
    if event_type in _PREVIEW_SKIP_TYPES:
        return None
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    category = "harness"
    text = ""

    if event_type == "run.started":
        text = "started"
    elif event_type == "model.resolved":
        text = "model resolved"
        model = _preview_value(payload.get("model"), limit=_TEXT_PREVIEW_MAX_CHARS)
        if model:
            text += f" model={model}"
    elif event_type and event_type.startswith("reasoning_summary."):
        category = "thinking"
        text = event_type.split(".", 1)[1]
        summary = _preview_value(
            payload.get("summary") or payload.get("text") or payload.get("reason"),
            limit=_TEXT_PREVIEW_MAX_CHARS,
        )
        if summary:
            text += f" {summary}"
    elif event_type == "message.completed":
        category = "assistant"
        text = _preview_value(payload.get("text"), limit=_TEXT_PREVIEW_MAX_CHARS) or "completed"
    elif event_type == "tool.started":
        category = "tool"
        name = _preview_value(payload.get("name") or payload.get("tool"), limit=120)
        tool_input = _preview_value(
            payload.get("input") or payload.get("arguments"), limit=_TOOL_PREVIEW_MAX_CHARS
        )
        text = name or "started"
        if tool_input:
            text += f" {tool_input}"
    elif event_type == "tool.completed":
        category = "tool"
        status = "failed" if payload.get("error") or payload.get("success") is False else "completed"
        text = status
        if payload.get("exit_code") is not None:
            text += f" exit={payload['exit_code']}"
        output = _preview_value(
            payload.get("output") or payload.get("error_message"),
            limit=_TOOL_PREVIEW_MAX_CHARS,
        )
        if output:
            text += f" output={output}"
    elif event_type == "context.compacted":
        text = "compacted"
    elif event_type == "provider.retry":
        text = "retry"
        attempt = payload.get("attempt")
        reason = _preview_value(
            payload.get("failure_kind") or payload.get("reason"), limit=_TEXT_PREVIEW_MAX_CHARS
        )
        if attempt is not None:
            text += f" attempt={attempt}"
        if reason:
            text += f" reason={reason}"
    elif event_type == "usage.final":
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        fields = []
        for key, label in (
            ("input_tokens", "input"),
            ("cached_input_tokens", "cached"),
            ("output_tokens", "output"),
            ("reasoning_tokens", "reasoning"),
            ("cost", "cost"),
        ):
            if usage.get(key) is not None:
                fields.append(f"{label}={_preview_value(usage[key], limit=80)}")
        if not fields:
            return None
        category = "usage"
        text = " ".join(fields)
    elif event_type in {"control.command.delivered", "control.command.rejected"}:
        category = "control"
        action = event_type.rsplit(".", 1)[-1]
        command_type = _preview_value(payload.get("command_type") or payload.get("kind"), limit=120)
        text = action if not command_type else f"{command_type} {action}"
    elif event_type == "control.queue.updated":
        category = "control"
        text = "queue updated"
    elif event_type and (
        event_type.startswith("harness.")
        or event_type.startswith("delivery.")
        or event_type.startswith("run.")
        or event_type == "worker.finalization"
    ):
        if event_type.startswith("delivery."):
            category = "delivery"
        elif event_type == "worker.finalization":
            category = "worker"
        text = event_type.rsplit(".", 1)[-1]
        failure = payload.get("failure") if isinstance(payload.get("failure"), dict) else {}
        detail = _preview_value(
            failure.get("message") or failure.get("kind"), limit=_TEXT_PREVIEW_MAX_CHARS
        )
        if event_type == "worker.finalization" and payload.get("exit_code") is not None:
            detail = f"exit={payload['exit_code']}" + (f" {detail}" if detail else "")
        if detail:
            text += f" {detail}"
    else:
        return None

    harness = event.get("harness") if isinstance(event.get("harness"), dict) else {}
    harness_key = _preview_value(harness.get("key"), limit=64) or "unknown"
    seq = event.get("seq", "?")
    return f"[{_timestamp(event)}][{harness_key}][#{seq}][{category}] {text}"


def _write_event_preview(event: dict) -> None:
    """Best-effort mirror; a logging failure must never fail event emission."""
    try:
        line = format_event_preview(event)
        if line:
            sys.stderr.write(line + "\n")
            sys.stderr.flush()
    except Exception:
        return


def emit(event_type: str, payload: dict, raw_ref: dict | None) -> dict:
    if event_type not in KNOWN_TYPES:
        if event_type.startswith("run."):
            raise RuntimeError(f"unknown Task terminal event: {event_type}")
        payload = {
            "code": "unknown_event_type",
            "original_type": event_type,
            "raw_ref": raw_ref,
        }
        event_type = "diagnostic"
    event_path, lock_path = _paths()
    if event_type in HARNESS_TERMINAL_TYPES | TASK_TERMINALS and _outer_timeout_requested(
        event_path.parent
    ):
        # Docker uses SIGTERM/143 for both user cancellation and the backend's
        # wall-clock timeout. The marker is written immediately before the
        # backend calls Docker stop, so every terminal emitted after that point
        # carries the authoritative timeout taxonomy.
        payload = dict(payload)
        failure = payload.get("failure")
        failure = dict(failure) if isinstance(failure, dict) else {}
        failure["kind"] = "timeout"
        failure["message"] = "Task timed out"
        payload["failure"] = failure
        if event_type == "run.failed":
            payload["status"] = "failed"
            payload["success"] = False
    event_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        # seq is derived from the stream itself: the fsync'd event append is the
        # single source of truth. A crash between an append and any auxiliary
        # state can therefore never make a recovered container regenerate a
        # divergent seq for the same record.
        first_event = None
        last_type = None
        last_seq = 0
        harness_terminal_seen = False
        if event_path.exists():
            for line in event_path.read_text(encoding="utf-8", errors="strict").splitlines():
                if not line.strip():
                    continue
                parsed = json.loads(line)
                first_event = first_event or parsed
                last_type = parsed.get("type")
                last_seq += 1
                if last_type in HARNESS_TERMINAL_TYPES:
                    harness_terminal_seen = True
            if last_type in TASK_TERMINALS:
                raise RuntimeError("cannot append an event after the Task terminal")
        if last_seq == 0 and event_type != "run.started":
            raise RuntimeError(
                f"run.started must be the first canonical event; got {event_type}"
            )
        if event_type == "run.started" and last_seq > 0:
            raise RuntimeError("run.started appears more than once")
        if event_type in HARNESS_TERMINAL_TYPES and harness_terminal_seen:
            raise RuntimeError("harness terminal appears more than once")
        if event_type.startswith("delivery.") and not harness_terminal_seen:
            raise RuntimeError("delivery event appears before harness terminal")
        if event_type == "worker.finalization":
            if not harness_terminal_seen:
                raise RuntimeError("worker.finalization appears before harness terminal")
            if last_type == "worker.finalization":
                raise RuntimeError("worker.finalization appears more than once")
        if event_type in TASK_TERMINALS:
            if not harness_terminal_seen:
                raise RuntimeError("task terminal appears before harness terminal")
            if last_type != "worker.finalization":
                raise RuntimeError("Task terminal must immediately follow worker.finalization")
        if last_type == "worker.finalization" and event_type not in TASK_TERMINALS:
            raise RuntimeError("only the Task terminal may follow worker.finalization")
        harness = {
            "key": _required_env("CODIFY_HARNESS_KEY"),
            "adapter_version": _required_env("CODIFY_ADAPTER_VERSION"),
            "cli_version": _required_env("CODIFY_CLI_VERSION"),
        }
        # V2 attempts carry the control transport and the model protocols under
        # the harness envelope; the frozen manifest (or the adapter-exported
        # env) supplies them. Default to the V1 envelope when unset.
        contract = os.getenv("CODIFY_RUNTIME_CONTRACT_VERSION", "").strip()
        if contract == V2_CONTRACT:
            # Reuse the V2 schema when the adapter declares it.
            harness["control_transport"] = {
                "kind": os.getenv("CODIFY_HARNESS_CONTROL_TRANSPORT_KIND", "rpc_stdio"),
                "protocol": os.getenv("CODIFY_HARNESS_CONTROL_TRANSPORT_PROTOCOL"),
            }
            protocols = os.getenv("CODIFY_HARNESS_MODEL_PROTOCOLS", "")
            harness["model_protocols"] = [
                p for p in protocols.split(",") if p.strip()
            ] or [os.getenv("CODIFY_HARNESS_MODEL_PROTOCOL", "anthropic_messages")]
        schema = SCHEMA
        event_schema_env = os.getenv("CODIFY_EVENT_SCHEMA", "")
        if event_schema_env:
            schema = event_schema_env
        elif contract == V2_CONTRACT:
            schema = "codify.worker.event/v2"
        if first_event is not None and first_event.get("harness") != harness:
            raise RuntimeError("Harness identity changed inside one canonical attempt")
        seq = last_seq + 1
        event = {
            "schema": schema,
            "event_id": str(uuid.uuid4()),
            "attempt_id": _required_env("CODIFY_ATTEMPT_ID"),
            "seq": seq,
            "occurred_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "type": event_type,
            "task_id": int(_required_env("TASK_ID")),
            "harness": harness,
            "payload": _normalize_payload(event_type, payload),
        }
        if raw_ref is not None:
            event["raw_ref"] = dict(raw_ref)
        with event_path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            output.flush()
            os.fsync(output.fileno())
    _write_event_preview(event)
    return event


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("event_type")
    parser.add_argument("--payload", default="{}")
    parser.add_argument("--raw-stream")
    parser.add_argument("--raw-line", type=int)
    args = parser.parse_args()
    payload = json.loads(args.payload)
    if not isinstance(payload, dict):
        raise ValueError("canonical event payload must be an object")
    raw_ref = None
    if args.raw_stream is not None or args.raw_line is not None:
        if args.raw_stream is None or args.raw_line is None or args.raw_line < 1:
            raise ValueError("raw stream and positive raw line must be provided together")
        raw_ref = {"stream": args.raw_stream, "line": args.raw_line}
    emitted = emit(args.event_type, payload, raw_ref)
    print(json.dumps(emitted, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"canonical event emission failed: {exc}", file=sys.stderr)
        raise
