#!/usr/bin/env python3
"""Translate Codex App Server JSONL (and legacy exec fixtures) to events.

Single streaming process: reads stdin to EOF, keeps all cross-record state in
memory, and emits the single harness terminal at stream end so the LAST
turn-terminal record (turn.completed vs turn.failed) is authoritative.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from result_builder import is_v2_contract, result_schema, v2_harness_block
from sanitize import clean_message, sanitize

# Per-stream in-memory state. The terminal is decided at EOF, so a later
# turn.failed can override an earlier completed turn without colliding with
# the single-terminal canonical invariant.
_STATE: dict = {
    "thread_id": "",
    "session_id": "",
    "turn_id": "",
    "retry_count": 0,
    "model_resolved": False,
    "last_assistant_text": "",
    "message_text": {},
    "usage": {},
    # Open reasoning blocks keyed by canonical reasoning_id (plan §4.3 exec
    # path). Only blocks whose started was observed are ever completed here;
    # closed_reasoning remembers duplicates so replays stay silent.
    "open_reasoning": {},
    "closed_reasoning": set(),
    "terminal_type": None,      # "completed" | "failed"
    "terminal_line": None,
    "terminal_failure": None,   # {"kind": ..., "message": ...}
}


def _configured_model() -> str | None:
    """Return the model injected for Codex's OpenAI-compatible transport."""
    model = os.environ.get("OPENAI_MODEL")
    if not isinstance(model, str):
        return None
    return model.strip() or None


def _capture_real_thread_id(raw_text: str) -> None:
    """Persist the unmasked thread id from the raw (pre-sanitize) line.

    Sanitization turns a real UUID into ``<UUID:...>``; the harness result must
    carry the real value so resume works. Only the first real value wins; a
    masked fixture value is kept as a fallback by thread.started.
    """
    try:
        record = json.loads(raw_text)
    except json.JSONDecodeError:
        return
    thread_id = record.get("thread_id")
    if isinstance(thread_id, str) and thread_id and "<" not in thread_id:
        _STATE["thread_id"] = thread_id
        _STATE["session_id"] = thread_id
    params = record.get("params") if isinstance(record.get("params"), dict) else {}
    thread = params.get("thread") if isinstance(params.get("thread"), dict) else {}
    result = record.get("result") if isinstance(record.get("result"), dict) else {}
    result_thread = result.get("thread") if isinstance(result.get("thread"), dict) else {}
    for candidate in (thread, result_thread):
        candidate_thread_id = candidate.get("id")
        if isinstance(candidate_thread_id, str) and candidate_thread_id and "<" not in candidate_thread_id:
            _STATE["thread_id"] = candidate_thread_id
            session_id = candidate.get("sessionId")
            _STATE["session_id"] = (
                session_id if isinstance(session_id, str) and session_id else candidate_thread_id
            )


def _thread_id(record: dict) -> str | None:
    if _STATE["thread_id"]:
        return _STATE["thread_id"]
    value = record.get("thread_id")
    if isinstance(value, str) and value:
        return value
    params = record.get("params") if isinstance(record.get("params"), dict) else {}
    value = params.get("threadId")
    return value if isinstance(value, str) and value else None


def _session_id() -> str | None:
    return _STATE["session_id"] or _STATE["thread_id"] or None


def _reasoning_id(item_id: str) -> str:
    """Stable per-block identity: thread + item. item ids like ``item_0`` are
    per-thread, so thread alone is not enough; contentIndex-like fields are
    never used alone (plan §3.2)."""
    return f"codex-reason-{_STATE['thread_id'] or 'thread'}-{item_id}"


def _close_open_reasoning(reason: str, raw_line: int) -> None:
    """Interrupt every block that never received its own end (plan §4.3)."""
    for reasoning_id in list(_STATE["open_reasoning"]):
        _emit(
            "reasoning_summary.interrupted",
            {"reasoning_id": reasoning_id, "reason": reason},
            raw_line,
        )
    _STATE["open_reasoning"] = {}


def _failure_kind(message: str) -> str:
    lowered = str(message).lower()
    if any(marker in lowered for marker in ("cancelled", "canceled", "interrupt", "sigterm")):
        return "cancelled"
    if "401" in lowered or "unauthorized" in lowered or "authentication" in lowered:
        return "authentication_error"
    if "429" in lowered or "rate limit" in lowered or "too many requests" in lowered:
        return "rate_limited"
    if "sandbox" in lowered or "permission denied" in lowered:
        return "sandbox_error"
    return "engine_error"


def _emit(event_type: str, payload: dict, raw_line: int) -> None:
    writer = os.environ["CODIFY_CANONICAL_EVENT_WRITER"]
    subprocess.run(
        [
            sys.executable,
            writer,
            event_type,
            "--payload",
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            "--raw-stream",
            "harness-events/codex.jsonl",
            "--raw-line",
            str(raw_line),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def _usage(record: dict) -> dict:
    source = record.get("usage") if isinstance(record.get("usage"), dict) else {}
    if not source:
        params = record.get("params") if isinstance(record.get("params"), dict) else {}
        token_usage = params.get("tokenUsage")
        if isinstance(token_usage, dict):
            source = token_usage.get("last") or token_usage.get("total") or {}
        if not source and isinstance(params.get("usage"), dict):
            source = params["usage"]
    if not source:
        source = _STATE.get("usage") or {}
    def value(*keys: str):
        for key in keys:
            if key in source:
                return source[key]
        return None

    known_keys = {
        "input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens",
        "cost", "currency", "inputTokens", "cachedInputTokens", "outputTokens",
        "reasoningOutputTokens", "totalTokens", "cacheWriteInputTokens",
    }
    return {
        "input_tokens": value("input_tokens", "inputTokens"),
        "cached_input_tokens": value("cached_input_tokens", "cachedInputTokens"),
        "output_tokens": value("output_tokens", "outputTokens"),
        "reasoning_tokens": value("reasoning_output_tokens", "reasoningOutputTokens"),
        "cost": value("cost"),
        "currency": value("currency"),
        "engine_fields": {
            key: value
            for key, value in source.items()
            if key not in known_keys
        },
    }


def _write_result(
    *,
    success: bool,
    result: str,
    usage: dict,
    failure_message: str | None = None,
) -> None:
    result_path = Path(os.environ["CODIFY_HARNESS_RESULT_FILE"])
    failure = None
    if not success:
        message = failure_message or result or "Codex execution failed"
        failure = {"kind": _failure_kind(message), "message": message}
    payload = {
        "schema": result_schema(),
        "status": "completed" if success else "failed",
        "success": success,
        "result": result,
        "session_id": _session_id(),
        "model": _configured_model(),
        "usage": usage,
        "failure": failure,
        "capability_warnings": [],
    }
    if is_v2_contract():
        payload["harness"] = v2_harness_block()
    else:
        payload["harness_key"] = "codex"
        payload["adapter_version"] = os.environ.get("CODIFY_ADAPTER_VERSION", "1.0.0")
        payload["cli_version"] = os.environ.get("CODIFY_CLI_VERSION", "unknown")
    temp_path = result_path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, result_path)


def _emit_terminal_at_eof() -> None:
    """Emit the single harness terminal decided from the last turn-terminal."""
    if _STATE["terminal_type"] == "completed":
        _emit(
            "harness.completed",
            {"result": _STATE["last_assistant_text"], "session_id": _session_id()},
            _STATE["terminal_line"],
        )
    elif _STATE["terminal_type"] == "failed":
        failure = _STATE["terminal_failure"] or {
            "kind": "engine_error",
            "message": "Codex turn failed",
        }
        _emit("harness.failed", {"failure": failure}, _STATE["terminal_line"])


def _set_thread_identity(thread: dict) -> None:
    thread_id = thread.get("id")
    if isinstance(thread_id, str) and thread_id:
        _STATE["thread_id"] = thread_id
        session_id = thread.get("sessionId")
        _STATE["session_id"] = session_id if isinstance(session_id, str) and session_id else thread_id


def _emit_model_resolved(raw_line: int) -> None:
    if _STATE["model_resolved"]:
        return
    _STATE["model_resolved"] = True
    _emit(
        "model.resolved",
        {"model": _configured_model(), "session_id": _session_id()},
        raw_line,
    )


def _app_server_item(item: dict) -> dict:
    normalized = dict(item)
    item_type = normalized.get("type")
    normalized["type"] = {
        "agentMessage": "agent_message",
        "commandExecution": "command_execution",
    }.get(item_type, item_type)
    if "aggregatedOutput" in normalized and "aggregated_output" not in normalized:
        normalized["aggregated_output"] = normalized["aggregatedOutput"]
    if "exitCode" in normalized and "exit_code" not in normalized:
        normalized["exit_code"] = normalized["exitCode"]
    return normalized


def _translate_app_server(record: dict, raw_line: int) -> bool:
    """Map native App Server messages into the existing stream state machine."""
    method = record.get("method")
    if not isinstance(method, str):
        result = record.get("result") if isinstance(record.get("result"), dict) else {}
        thread = result.get("thread") if isinstance(result.get("thread"), dict) else {}
        if thread:
            _set_thread_identity(thread)
        turn = result.get("turn") if isinstance(result.get("turn"), dict) else {}
        if turn.get("id"):
            _STATE["turn_id"] = turn["id"]
        if "error" not in record or "id" not in record:
            return bool(thread or turn or "result" in record)
        error = record.get("error") if isinstance(record.get("error"), dict) else {}
        message = clean_message(str(error.get("message") or "Codex App Server request failed"))
        _close_open_reasoning("request_failed", raw_line)
        _STATE["terminal_type"] = "failed"
        _STATE["terminal_line"] = raw_line
        _STATE["terminal_failure"] = {"kind": _failure_kind(message), "message": message}
        _write_result(success=False, result=message, usage=_usage(record), failure_message=message)
        return True

    params = record.get("params") if isinstance(record.get("params"), dict) else {}
    if method == "thread/started":
        thread = params.get("thread") if isinstance(params.get("thread"), dict) else {}
        _set_thread_identity(thread)
        _emit_model_resolved(raw_line)
        return True
    if method == "turn/started":
        turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
        turn_id = turn.get("id")
        if isinstance(turn_id, str) and turn_id:
            _STATE["turn_id"] = turn_id
        return True
    if method in {"item/started", "item/completed"}:
        item = params.get("item") if isinstance(params.get("item"), dict) else {}
        translate(
            {
                "type": method.replace("/", "."),
                "item": _app_server_item(item),
            },
            raw_line,
        )
        return True
    if method == "item/agentMessage/delta":
        item_id = params.get("itemId")
        delta = params.get("delta")
        if isinstance(item_id, str) and isinstance(delta, str):
            _STATE["message_text"][item_id] = _STATE["message_text"].get(item_id, "") + delta
        return True
    if method == "thread/tokenUsage/updated":
        token_usage = params.get("tokenUsage")
        if isinstance(token_usage, dict):
            _STATE["usage"] = token_usage.get("last") or token_usage.get("total") or {}
        return True
    if method == "turn/completed":
        turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
        status = turn.get("status")
        if status == "completed":
            translate(
                {"type": "turn.completed", "usage": _STATE.get("usage") or {}},
                raw_line,
            )
        else:
            error = turn.get("error") if isinstance(turn.get("error"), dict) else {}
            message = error.get("message") or f"Codex turn {status or 'failed'}"
            translate(
                {
                    "type": "turn.failed",
                    "error": {"message": clean_message(str(message))},
                    "usage": _STATE.get("usage") or {},
                },
                raw_line,
            )
        return True
    if method == "error":
        message = clean_message(str(params.get("message") or "Codex App Server error"))
        if params.get("willRetry"):
            _STATE["retry_count"] += 1
            _emit(
                "provider.retry",
                {
                    "attempt": _STATE["retry_count"],
                    "failure_kind": _failure_kind(message),
                },
                raw_line,
            )
        else:
            _emit("diagnostic", {"code": "app_server_error", "message": message}, raw_line)
        return True
    if method == "thread/compacted":
        _emit("context.compacted", {"evidence": "codex_app_server"}, raw_line)
        return True
    # Status, config, heartbeat, reasoning delta and other notifications are
    # retained in the raw archive but have no canonical event in this contract.
    return True


def translate(record: dict, raw_line: int) -> None:
    if "method" in record or ("error" in record and "id" in record):
        if _translate_app_server(record, raw_line):
            return
    record_type = record.get("type")
    if record_type == "thread.started":
        thread_id = record.get("thread_id")
        if isinstance(thread_id, str) and thread_id and not _STATE["thread_id"]:
            # Masked fixture value kept as a fallback for the session id.
            _STATE["thread_id"] = thread_id
            _STATE["session_id"] = thread_id
        if not _STATE["model_resolved"]:
            _emit_model_resolved(raw_line)
        else:
            _emit(
                "diagnostic",
                {"code": "session_resumed", "session_id": _thread_id(record)},
                raw_line,
            )
    elif record_type == "turn.started":
        return
    elif record_type == "error":
        _STATE["retry_count"] += 1
        _emit(
            "provider.retry",
            {
                "attempt": _STATE["retry_count"],
                "failure_kind": _failure_kind(record.get("message") or ""),
            },
            raw_line,
        )
    elif record_type == "turn.failed":
        _close_open_reasoning("turn_failed", raw_line)
        error = record.get("error") if isinstance(record.get("error"), dict) else {}
        message = clean_message(str(error.get("message") or "Codex turn failed"))
        _STATE["terminal_type"] = "failed"
        _STATE["terminal_line"] = raw_line
        _STATE["terminal_failure"] = {"kind": _failure_kind(message), "message": message}
        _write_result(success=False, result=message, usage=_usage(record), failure_message=message)
    elif record_type == "item.started":
        item = record.get("item") if isinstance(record.get("item"), dict) else {}
        item_type = item.get("type")
        if item_type == "reasoning":
            reasoning_id = _reasoning_id(str(item.get("id") or ""))
            if (
                reasoning_id
                and reasoning_id not in _STATE["open_reasoning"]
                and reasoning_id not in _STATE["closed_reasoning"]
            ):
                _STATE["open_reasoning"][reasoning_id] = True
                _emit("reasoning_summary.started", {"reasoning_id": reasoning_id}, raw_line)
        elif item_type == "command_execution":
            _emit(
                "tool.started",
                {
                    "tool_id": item.get("id"),
                    "name": "shell",
                    "input": {"command": item.get("command") or ""},
                },
                raw_line,
            )
    elif record_type == "item.completed":
        item = record.get("item") if isinstance(record.get("item"), dict) else {}
        item_type = item.get("type")
        if item_type == "reasoning":
            # A reasoning block ends without a body: the completion carries no
            # text and still closes the placeholder. Replays of the same item
            # must not emit a second completion (plan §4.3).
            reasoning_id = _reasoning_id(str(item.get("id") or ""))
            if reasoning_id in _STATE["open_reasoning"]:
                _emit(
                    "reasoning_summary.completed",
                    {"reasoning_id": reasoning_id, "client": "codex"},
                    raw_line,
                )
                del _STATE["open_reasoning"][reasoning_id]
                _STATE["closed_reasoning"].add(reasoning_id)
            elif reasoning_id not in _STATE["closed_reasoning"]:
                # Never started at all: auditable orphan, no fabricated start.
                _emit(
                    "diagnostic",
                    {"code": "reasoning_completed_without_start", "item_id": item.get("id")},
                    raw_line,
                )
        elif item_type == "command_execution":
            _emit(
                "tool.completed",
                {
                    "tool_id": item.get("id"),
                    "output": item.get("aggregated_output") or "",
                    "error": bool(item.get("exit_code") not in (None, 0)),
                    "exit_code": item.get("exit_code"),
                },
                raw_line,
            )
        elif item_type == "agent_message":
            text = item.get("text") or _STATE["message_text"].get(item.get("id"), "")
            _STATE["last_assistant_text"] = text
            _emit(
                "message.completed",
                {"message_id": item.get("id"), "text": text},
                raw_line,
            )
        elif item_type == "error":
            message = clean_message(str(item.get("message") or ""))
            if "compaction" in message.lower():
                _emit(
                    "context.compacted",
                    {"evidence": "cli_compaction_advisory"},
                    raw_line,
                )
            else:
                _emit(
                    "diagnostic",
                    {"code": "capability_warning", "message": message},
                    raw_line,
                )
    elif record_type == "turn.completed":
        # Blocks still open when the turn closes cleanly never saw their own
        # end; close them as interrupted, never as completed (plan §4.3).
        _close_open_reasoning("turn_completed_without_block_end", raw_line)
        usage = _usage(record)
        _emit("usage.final", {"usage": usage}, raw_line)
        _STATE["terminal_type"] = "completed"
        _STATE["terminal_line"] = raw_line
        _write_result(success=True, result=_STATE["last_assistant_text"], usage=usage)
    else:
        _emit("diagnostic", {"code": "unknown_raw_event", "type": record_type}, raw_line)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-file", required=True, type=Path)
    args = parser.parse_args()
    args.raw_file.parent.mkdir(parents=True, exist_ok=True)

    line_no = 0
    with args.raw_file.open("a", encoding="utf-8") as handle:
        for raw_input in sys.stdin:
            raw_input = raw_input.rstrip("\n")
            if not raw_input.strip():
                continue
            _capture_real_thread_id(raw_input)
            input_text = sanitize(raw_input)
            if not input_text:
                continue
            try:
                record = json.loads(input_text)
            except json.JSONDecodeError:
                record = None
                raw_text = input_text
            else:
                raw_text = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            handle.write(raw_text + "\n")
            handle.flush()
            line_no += 1
            if record is None:
                _emit("diagnostic", {"code": "non_json_raw_line", "text": raw_text[:500]}, line_no)
                continue
            if not isinstance(record, dict):
                _emit("diagnostic", {"code": "non_object_raw_event"}, line_no)
                continue
            translate(record, line_no)
    _emit_terminal_at_eof()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
