#!/usr/bin/env python3
"""Translate one Claude stream-json record to Canonical Event v1 records."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from result_builder import is_v2_contract, result_schema, v2_harness_block
from sanitize import redact_hidden_reasoning, sanitize

_REAL_SESSION_ID: str = ""


def _capture_real_session_id(raw_text: str) -> None:
    """Keep the unmasked session id before sanitization so resume stays possible.

    UUIDs are redacted to stable ``<UUID:...>`` placeholders in events and raw
    streams, but the harness result must carry the real session id so the backend
    persists ``output_session_id`` and ``--resume`` receives a valid value. The
    translator is one streaming process reading stdin to EOF, so the value lives
    in memory; the first real id seen wins.
    """
    global _REAL_SESSION_ID
    if _REAL_SESSION_ID:
        return
    try:
        record = json.loads(raw_text)
    except json.JSONDecodeError:
        return
    session_id = record.get("session_id")
    if isinstance(session_id, str) and session_id and "<" not in session_id:
        _REAL_SESSION_ID = session_id


def _session_id(record: dict) -> str | None:
    """Real session id when captured, else the (possibly masked) record value.

    The backend projects ``output_session_id`` from canonical events, so the
    resume capability requires the real value here; other UUIDs stay masked.
    """
    if _REAL_SESSION_ID:
        return _REAL_SESSION_ID
    value = record.get("session_id")
    return value if isinstance(value, str) and value else None


# Per-stream state for the partial-message thinking lifecycle
# (--include-partial-messages). The translator is one streaming process per
# attempt (stdin to EOF), so this state naturally resets between attempts.
# Partial stream events identify every thinking block by its native message id
# plus the content index; the full assistant records that follow must not
# re-map the same block (plan §4.1).
#
# Subagent adaptation: Claude marks every child-native record with the
# delegation's ``parent_tool_use_id``. All lifecycle state below is therefore
# keyed by agent, so two concurrent children can never interrupt, close or
# overwrite each other's message and thinking blocks
# (open-harness-v2-subagent-adaptation.md §6.1).
ROOT_AGENT_KEY = "root"
# Mirrors harness_protocol.AGENT_ATTRIBUTED_EVENT_TYPES: delegation and the
# review/tool lifecycle may carry an agent, terminals and usage may not.
_AGENT_ATTRIBUTED_EVENT_TYPES = frozenset(
    {
        "message.delta",
        "message.completed",
        "reasoning_summary.started",
        "reasoning_summary.delta",
        "reasoning_summary.completed",
        "reasoning_summary.interrupted",
        "tool.started",
        "tool.completed",
        "context.compacted",
        "diagnostic",
    }
)
_PARTIAL_MESSAGE_ID: dict[str, str] = {}          # agent key -> latest message id
_PARTIAL_THINKING_STARTED: set[str] = set()       # agents whose current message opened thinking
_OPEN_REASONING: dict[str, dict] = {}             # agent key -> content index -> reasoning_id
_AGENT_ROLES: dict[str, str] = {}                 # delegation tool id -> display role
_AGENT_USAGE: dict[str, dict] = {}                # delegation tool id -> child detail usage
_SETTLED_DELEGATIONS: set[str] = set()            # delegation tool ids that already ended


def _agent_id(record: dict) -> str | None:
    """Native delegation identity: the ``Agent`` tool_use id, or None for root."""
    value = record.get("parent_tool_use_id")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _agent_key(agent_id: str | None) -> str:
    return agent_id or ROOT_AGENT_KEY


def _agent_ref(agent_id: str | None) -> dict | None:
    """Canonical ``payload.agent`` for a child-native record (None for root)."""
    if agent_id is None:
        return None
    return {"id": agent_id, "parent_id": "root", "role": _AGENT_ROLES.get(agent_id, "agent")}


def _reasoning_id(agent_key: str, message_id: str, index: int) -> str:
    """Agent-scoped reasoning identity: a child may reuse a native message id."""
    if agent_key == ROOT_AGENT_KEY:
        return f"claude-think-{message_id}-{index}"
    return f"claude-think-{agent_key}-{message_id}-{index}"


def _interrupt_open_reasoning(reason: str, raw_line: int, agent_key: str | None = None) -> None:
    """Interrupt open thinking blocks that never received their own end.

    Only blocks whose started was observed are closed here; blocks that ended
    normally are already gone from the set (plan §4.1.5). With an explicit
    agent key only that agent's blocks are closed, so one child ending cannot
    interrupt another agent's in-flight thinking.
    """
    agent_keys = [agent_key] if agent_key is not None else list(_OPEN_REASONING)
    for key in agent_keys:
        ref = _agent_ref(None if key == ROOT_AGENT_KEY else key)
        for reasoning_id in _OPEN_REASONING.get(key, {}).values():
            _emit(
                "reasoning_summary.interrupted",
                {"reasoning_id": reasoning_id, "reason": reason},
                raw_line,
                agent=ref,
            )
        _OPEN_REASONING.pop(key, None)


def _handle_message_start(event: dict, raw_line: int, agent_key: str) -> None:
    """Begin a new native message: reset that agent's per-message state.

    Content indexes restart at 0 on message_start, and a new message means the
    previous one ended. Any thinking block the previous message left open
    (stream truncated mid-block) is interrupted here — for this agent only.
    """
    _interrupt_open_reasoning("message_ended", raw_line, agent_key=agent_key)
    message = event.get("message") if isinstance(event.get("message"), dict) else {}
    message_id = message.get("id")
    _PARTIAL_MESSAGE_ID[agent_key] = message_id if isinstance(message_id, str) else ""
    _PARTIAL_THINKING_STARTED.discard(agent_key)


def _handle_content_block_start(event: dict, raw_line: int, agent_key: str) -> None:
    """Open the reasoning placeholder for a thinking content block."""
    block = event.get("content_block") if isinstance(event.get("content_block"), dict) else {}
    if block.get("type") != "thinking":
        # tool_use/text blocks stay driven by the full assistant/user records;
        # their partial starts only feed console rendering, not canonical events.
        return
    index = event.get("index")
    message_id = _PARTIAL_MESSAGE_ID.get(agent_key, "")
    if not isinstance(index, int) or not message_id:
        # Without a native message identity there is no stable reasoning_id;
        # leave the full assistant record to its legacy diagnostic handling.
        return
    _PARTIAL_THINKING_STARTED.add(agent_key)
    open_blocks = _OPEN_REASONING.setdefault(agent_key, {})
    if index in open_blocks:
        return  # duplicate start for one block: keep the first placeholder
    reasoning_id = _reasoning_id(agent_key, message_id, index)
    open_blocks[index] = reasoning_id
    _emit(
        "reasoning_summary.started",
        {"reasoning_id": reasoning_id},
        raw_line,
        agent=_agent_ref(None if agent_key == ROOT_AGENT_KEY else agent_key),
    )


def _handle_content_block_stop(event: dict, raw_line: int, agent_key: str) -> None:
    """Close the reasoning placeholder for that block's content index.

    Thinking content is never projected (sanitize/redact boundaries), so the
    completion carries no text even when deltas were observed; an empty block
    still closes its placeholder (plan §4.1.3).
    """
    index = event.get("index")
    if not isinstance(index, int):
        return
    reasoning_id = _OPEN_REASONING.get(agent_key, {}).pop(index, None)
    if reasoning_id is None:
        return  # a stop for a text/tool_use block or an unknown index
    _emit(
        "reasoning_summary.completed",
        {"reasoning_id": reasoning_id, "client": "claude"},
        raw_line,
        agent=_agent_ref(None if agent_key == ROOT_AGENT_KEY else agent_key),
    )


def _emit(event_type: str, payload: dict, raw_line: int, agent: dict | None = None) -> None:
    writer = os.environ["CODIFY_CANONICAL_EVENT_WRITER"]
    if agent is not None and event_type in _AGENT_ATTRIBUTED_EVENT_TYPES:
        payload = {**payload, "agent": agent}
    subprocess.run(
        [
            sys.executable,
            writer,
            event_type,
            "--payload-stdin",
            "--raw-stream",
            "harness-events/claude.jsonl",
            "--raw-line",
            str(raw_line),
        ],
        input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(),
        check=True,
        stdout=subprocess.DEVNULL,
    )


def _usage(record: dict) -> dict:
    source = record.get("usage") if isinstance(record.get("usage"), dict) else {}
    return {
        "input_tokens": source.get("input_tokens"),
        "cached_input_tokens": source.get("cache_read_input_tokens"),
        "output_tokens": source.get("output_tokens"),
        "reasoning_tokens": None,
        "cost": record.get("total_cost_usd"),
        "currency": "USD" if record.get("total_cost_usd") is not None else None,
        "engine_fields": {
            key: value
            for key, value in source.items()
            if key not in {"input_tokens", "cache_read_input_tokens", "output_tokens"}
        },
    }


def _write_result(record: dict, *, success: bool, usage: dict) -> None:
    result_path = Path(os.environ["CODIFY_HARNESS_RESULT_FILE"])
    usage = _attempt_usage(usage)
    failure = None
    if not success:
        kind = _failure_kind(record)
        failure = {
            "kind": kind,
            "message": record.get("result") or record.get("subtype") or "AI execution failed",
        }
    result = {
        "schema": result_schema(),
        "status": (
            "completed"
            if success
            else "cancelled"
            if failure and failure["kind"] == "cancelled"
            else "protocol_error"
            if failure and failure["kind"] == "protocol_error"
            else "failed"
        ),
        "success": success,
        "result": record.get("result") or "",
        "session_id": _session_id(record),
        "model": os.environ.get("ANTHROPIC_MODEL") or None,
        "usage": usage,
        "failure": failure,
        "capability_warnings": [],
    }
    if is_v2_contract():
        # Nested harness block matching the event envelope so the archived
        # result passes validate_result_v2 (flat shape is rejected outright).
        result["harness"] = v2_harness_block()
    else:
        result.update(
            {
                "harness_key": "claude",
                "adapter_version": os.environ.get("CODIFY_ADAPTER_VERSION", "1.0.1"),
                "cli_version": os.environ.get("CODIFY_CLI_VERSION", "unknown"),
            }
        )
    temp_path = result_path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, result_path)


def _failure_kind(record: dict) -> str:
    text = " ".join(
        str(record.get(key) or "") for key in ("subtype", "result", "error")
    ).lower()
    if any(marker in text for marker in ("authentication", "unauthorized", "invalid api key", "401")):
        return "authentication_error"
    if any(marker in text for marker in ("rate limit", "rate_limit", "too many requests", "429")):
        return "rate_limited"
    if any(marker in text for marker in ("sandbox", "permission denied", "approval required")):
        return "sandbox_error"
    if any(marker in text for marker in ("timed out", "timeout")):
        return "timeout"
    if any(marker in text for marker in ("cancelled", "canceled", "sigterm", "interrupted")):
        return "cancelled"
    if any(marker in text for marker in ("invalid session", "session not found", "no conversation found")):
        return "protocol_error"
    return "engine_error"


def _retry_failure_kind(record: dict) -> str:
    status = record.get("error_status")
    error = str(record.get("error") or "").lower()
    if status == 401 or "auth" in error:
        return "authentication_error"
    if status == 429 or "rate" in error:
        return "rate_limited"
    return "engine_error"


def _settle_open_delegations(raw_line: int) -> None:
    """End every delegation that never reported its own terminal.

    A cancelled or failed attempt stops the CLI, so an in-flight child can no
    longer report anything. Leaving its row open would show a permanent spinner
    and contradict the delegation contract (§10.10): the row ends in place as
    completed/failed/cancelled.
    """
    for delegation_id in list(_AGENT_ROLES):
        if delegation_id in _SETTLED_DELEGATIONS:
            continue
        _settle_delegation(delegation_id, status="cancelled", output="", raw_line=raw_line)


def _tool_result_text(value: object) -> str:
    """Flatten Anthropic text blocks for tool output and child summaries."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_tool_result_text(part) for part in value)
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        return _tool_result_text(value.get("content"))
    return ""


def _settle_delegation(
    delegation_id: str, *, status: str, output: object, raw_line: int
) -> None:
    """End one delegation row in place; the first native terminal wins.

    Claude reports a child's end twice (the ``Agent`` tool result and a
    ``system/task_notification``); emitting both would double-project the row.
    """
    if delegation_id in _SETTLED_DELEGATIONS:
        return
    _SETTLED_DELEGATIONS.add(delegation_id)
    subagent = {
        "id": delegation_id,
        "parent_id": "root",
        "role": _AGENT_ROLES.get(delegation_id, "agent"),
        "status": status,
    }
    child_usage = _AGENT_USAGE.get(delegation_id)
    if child_usage:
        subagent["usage"] = child_usage
    # Any block this child left open will never receive its own end.
    _interrupt_open_reasoning("delegation_ended", raw_line, agent_key=delegation_id)
    completed: dict = {
        "tool_id": delegation_id,
        "name": "Subagent",
        "error": status == "failed",
        "subagent": subagent,
    }
    if isinstance(output, str) and output:
        completed["output"] = output
    _emit("tool.completed", completed, raw_line)


def _delegation_role(block: dict) -> str:
    """Display role from the native ``Agent`` tool input, never from text."""
    source = block.get("input") if isinstance(block.get("input"), dict) else {}
    for key in ("subagent_type", "agent_type", "agent"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "agent"


def _accumulate_agent_usage(agent_id: str, message: dict) -> None:
    """Keep the child's own native usage for its delegation row.

    Each child assistant record carries that child's cumulative usage for its
    own request, and the probe shows the same value repeated, so each key is
    kept monotonic instead of summed. The same record is the child's leaf
    usage, which the attempt total must add: a child runs its own provider
    requests and the root's ``result`` usage does not contain them (Task 623:
    root 23501 input while the two children alone reported 12574 each).
    """
    usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
    if not usage:
        return
    totals = _AGENT_USAGE.setdefault(agent_id, {})
    for source_key, target_key in (
        ("input_tokens", "input_tokens"),
        ("output_tokens", "output_tokens"),
        ("cache_read_input_tokens", "cached_input_tokens"),
    ):
        value = usage.get(source_key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            totals[target_key] = max(totals.get(target_key, 0), value)


def _attempt_usage(root_usage: dict) -> dict:
    """Root terminal usage plus every child's leaf usage (plan §5.6)."""
    if not root_usage:
        return root_usage
    combined = dict(root_usage)
    for usage in _AGENT_USAGE.values():
        for key, value in usage.items():
            current = combined.get(key)
            if isinstance(current, int) and not isinstance(current, bool):
                combined[key] = current + value
            else:
                combined[key] = value
    return combined


def translate(record: dict, raw_line: int) -> None:
    record_type = record.get("type")
    subtype = record.get("subtype")
    agent_id = _agent_id(record)
    agent_key = _agent_key(agent_id)
    agent = _agent_ref(agent_id)
    if record_type == "system" and subtype == "init":
        _emit(
            "model.resolved",
            {"model": record.get("model"), "session_id": _session_id(record)},
            raw_line,
        )
    elif record_type == "system" and subtype == "compact_boundary":
        # A child may compact its own context; the record identifies it through
        # `parent_tool_use_id`, so the row must not be attributed to root
        # (plan §5.3 lists context.compacted among the attributable types).
        _emit("context.compacted", {"session_id": _session_id(record)}, raw_line, agent=agent)
    elif record_type == "system" and subtype == "task_started":
        # The native delegation start names the child's role; caching it here
        # keeps the role available even when the Agent tool_use block itself
        # was not observed in this stream.
        tool_use_id = record.get("tool_use_id")
        if isinstance(tool_use_id, str) and tool_use_id:
            _AGENT_ROLES.setdefault(tool_use_id, _delegation_role(record))
    elif record_type == "system" and subtype == "task_notification":
        # Native child terminal (status + summary). The Agent tool result is
        # the primary signal; this settles an aborted/never-returned child so
        # its row cannot keep spinning.
        tool_use_id = record.get("tool_use_id")
        if isinstance(tool_use_id, str) and tool_use_id:
            native_status = str(record.get("status") or "").lower()
            if native_status == "completed":
                status = "completed"
            elif native_status in {"failed", "error"}:
                status = "failed"
            else:
                status = "cancelled"
            _settle_delegation(
                tool_use_id,
                status=status,
                output=record.get("summary"),
                raw_line=raw_line,
            )
    elif record_type == "system" and subtype == "task_progress":
        # The child's own progress tick. Its facts (tool count, tokens,
        # duration) arrive again with the child's terminal, so the canonical
        # stream carries the delegation row instead of one diagnostic per tick.
        return
    elif record_type == "system" and subtype == "api_retry":
        _emit(
            "provider.retry",
            {
                "attempt": record.get("attempt"),
                "max_attempts": record.get("max_retries"),
                "failure_kind": _retry_failure_kind(record),
                "status_code": record.get("error_status"),
                "retry_delay_ms": record.get("retry_delay_ms"),
            },
            raw_line,
        )
    elif record_type == "stream_event":
        event = record.get("event") if isinstance(record.get("event"), dict) else {}
        event_type = event.get("type")
        if event_type == "message_start":
            _handle_message_start(event, raw_line, agent_key)
        elif event_type == "content_block_start":
            _handle_content_block_start(event, raw_line, agent_key)
        elif event_type == "content_block_delta":
            delta = event.get("delta") if isinstance(event.get("delta"), dict) else {}
            if delta.get("type") == "text_delta":
                _emit("message.delta", {"text": delta.get("text", "")}, raw_line, agent=agent)
            # thinking_delta/signature_delta are never projected as content and
            # must not drop the open block: the matching content_block_stop
            # still closes it.
        elif event_type == "content_block_stop":
            _handle_content_block_stop(event, raw_line, agent_key)
        elif event_type in {"error", "abort"}:
            # A native error/abort ends the current message without per-block
            # end signals: interrupt only the blocks that are still open.
            reason = "stream_error"
            if event_type == "abort":
                reason = "aborted"
            else:
                error = event.get("error") if isinstance(event.get("error"), dict) else {}
                error_type = error.get("type")
                if isinstance(error_type, str) and error_type:
                    reason = error_type[:200]
            _interrupt_open_reasoning(reason, raw_line, agent_key=agent_key)
        # message_delta/message_stop/ping carry no canonical projection.
    elif record_type == "assistant":
        message = record.get("message") if isinstance(record.get("message"), dict) else {}
        if agent_id is not None:
            _accumulate_agent_usage(agent_id, message)
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text" and block.get("text"):
                _emit(
                    "message.completed",
                    {"message_id": message.get("id"), "text": block.get("text")},
                    raw_line,
                    agent=agent,
                )
            elif block_type == "tool_use":
                if block.get("name") == "Agent":
                    # A delegation: the tool_use id is also the child's
                    # ``parent_tool_use_id``, so the same identity flows through
                    # the delegation row and every child event (plan §6.1).
                    delegation_id = block.get("id")
                    if not isinstance(delegation_id, str) or not delegation_id:
                        continue
                    if agent_id is not None:
                        # A child asked for its own subagent. The first version
                        # supports root-level delegation only, so the fact is
                        # kept in the raw archive plus one diagnostic and never
                        # becomes a second delegation layer (plan §5.5).
                        _emit(
                            "diagnostic",
                            {
                                "code": "subagent_depth_unsupported",
                                "tool_id": delegation_id,
                            },
                            raw_line,
                            agent=agent,
                        )
                        continue
                    _AGENT_ROLES.setdefault(delegation_id, _delegation_role(block))
                    _emit(
                        "tool.started",
                        {
                            "tool_id": delegation_id,
                            "name": "Subagent",
                            "input": block.get("input") or {},
                            "subagent": {
                                "id": delegation_id,
                                "parent_id": "root",
                                "role": _AGENT_ROLES[delegation_id],
                            },
                        },
                        raw_line,
                    )
                    continue
                _emit(
                    "tool.started",
                    {
                        "tool_id": block.get("id"),
                        "name": block.get("name"),
                        "input": block.get("input") or {},
                    },
                    raw_line,
                    agent=agent,
                )
            elif block_type == "thinking":
                # Partial-message mode already mapped this message's thinking
                # lifecycle from content_block_start/stop; the full record must
                # not create a second placeholder or completion (plan §4.1.4).
                # Without a partial lifecycle keep the legacy diagnostic-only
                # behavior.
                if not (
                    agent_key in _PARTIAL_THINKING_STARTED
                    and message.get("id") == _PARTIAL_MESSAGE_ID.get(agent_key)
                ):
                    _emit(
                        "diagnostic",
                        {"code": "hidden_reasoning_omitted", "message": "AI thinking omitted"},
                        raw_line,
                        agent=agent,
                    )
    elif record_type == "user":
        message = record.get("message") if isinstance(record.get("message"), dict) else {}
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                tool_id = block.get("tool_use_id")
                failed = bool(block.get("is_error", False))
                if isinstance(tool_id, str) and tool_id in _AGENT_ROLES:
                    # Delegation end: the row settles in place, exactly once,
                    # with the child's status and its detail usage.
                    # ``error=true`` ends the delegation only; the root decides
                    # what happens next (plan §5.5).
                    _settle_delegation(
                        tool_id,
                        status="failed" if failed else "completed",
                        output=_tool_result_text(block.get("content")),
                        raw_line=raw_line,
                    )
                    continue
                _emit(
                    "tool.completed",
                    {
                        "tool_id": tool_id,
                        "output": _tool_result_text(block.get("content")),
                        "error": failed,
                    },
                    raw_line,
                    agent=agent,
                )
    elif record_type == "result":
        usage = _attempt_usage(_usage(record))
        _emit("usage.final", {"usage": usage}, raw_line)
        success = subtype == "success" and record.get("is_error") is not True
        payload = {
            "result": record.get("result") or "",
            "session_id": _session_id(record),
        }
        if success:
            _settle_open_delegations(raw_line)
            _emit("harness.completed", payload, raw_line)
        else:
            # A failed turn never delivers the remaining block-end signals:
            # interrupt every block that is still open before the harness
            # terminal event.
            reason = (
                str(subtype)[:200]
                if isinstance(subtype, str) and subtype and subtype != "success"
                else "harness_failed"
            )
            _settle_open_delegations(raw_line)
            _interrupt_open_reasoning(reason, raw_line)
            payload["failure"] = {
                "kind": _failure_kind(record),
                "message": record.get("result") or subtype or "AI execution failed",
            }
            _emit("harness.failed", payload, raw_line)
        _write_result(record, success=success, usage=usage)
    else:
        _emit(
            "diagnostic",
            {"code": "unknown_raw_event"},
            raw_line,
        )


def _reset_stream_state() -> None:
    """One process serves exactly one attempt; never inherit another's agent state."""
    _PARTIAL_MESSAGE_ID.clear()
    _PARTIAL_THINKING_STARTED.clear()
    _OPEN_REASONING.clear()
    _AGENT_ROLES.clear()
    _AGENT_USAGE.clear()
    _SETTLED_DELEGATIONS.clear()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-file", required=True, type=Path)
    args = parser.parse_args()
    args.raw_file.parent.mkdir(parents=True, exist_ok=True)

    line_no = 0
    _reset_stream_state()
    with args.raw_file.open("a", encoding="utf-8") as handle:
        for raw_input in sys.stdin:
            raw_input = raw_input.rstrip("\n")
            if not raw_input.strip():
                continue
            _capture_real_session_id(raw_input)
            input_text = sanitize(raw_input)
            if not input_text:
                continue
            try:
                record = json.loads(input_text)
            except json.JSONDecodeError:
                record = None
                raw_text = input_text
            else:
                record = redact_hidden_reasoning(record)
                raw_text = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            handle.write(raw_text + "\n")
            handle.flush()
            line_no += 1
            if record is None:
                _emit(
                    "diagnostic",
                    {"code": "non_json_raw_line", "text": raw_text[:500]},
                    line_no,
                )
                continue
            if not isinstance(record, dict):
                _emit("diagnostic", {"code": "non_object_raw_event"}, line_no)
                continue
            translate(record, line_no)
    # The native stream ended. When a turn dies mid-thinking no error/result
    # signal follows, so interrupt whatever blocks are still open before the
    # runner synthesizes the harness terminal (plan §4.1.5).
    _interrupt_open_reasoning("stream_error", line_no)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
