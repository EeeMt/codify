"""Subagent attribution contract tests (open-harness-v2-subagent-adaptation.md §5).

The public vocabulary is small on purpose: delegation reuses the tool
lifecycle, and child-native events only gain an optional ``payload.agent``.
These tests pin that shape so four adapters cannot drift apart.
"""

from __future__ import annotations

import pytest

from app.core.harness_protocol import (
    CANONICAL_EVENT_SCHEMA_V2,
    HARNESS_CAPABILITY_KEYS,
    HarnessProtocolError,
    deterministic_event_id,
    validate_event_v2,
)
from app.core.harness_registry import (
    V2_SYSTEM_CAPABILITY_UPPER_BOUND,
    validate_v2_manifest_adapter_capabilities,
)

AGENT = {"id": "child-a", "parent_id": "root", "role": "reviewer"}


def _v2_event(event_type: str, payload: dict, seq: int = 2) -> dict:
    return {
        "schema": CANONICAL_EVENT_SCHEMA_V2,
        "event_id": deterministic_event_id("v2-attempt-1", seq),
        "attempt_id": "v2-attempt-1",
        "seq": seq,
        "occurred_at": f"2026-08-01T00:00:{seq:02d}Z",
        "type": event_type,
        "task_id": 7,
        "harness": {
            "key": "claude",
            "adapter_version": "1.0.0",
            "cli_version": "2.1.153",
            "control_transport": {"kind": "cli_stream_json", "protocol": "claude-json"},
            "model_protocols": ["anthropic_messages"],
        },
        "payload": payload,
    }


def test_capability_vocabulary_declares_subagents():
    assert "subagents" in HARNESS_CAPABILITY_KEYS
    for harness_key, bound in V2_SYSTEM_CAPABILITY_UPPER_BOUND.items():
        assert bound["subagents"] is True, harness_key


def test_manifest_may_tighten_subagents_to_false():
    validate_v2_manifest_adapter_capabilities("claude", {"subagents": False})
    validate_v2_manifest_adapter_capabilities("claude", {"subagents": True})


def test_child_message_carries_agent_and_root_message_does_not():
    child = validate_event_v2(
        _v2_event("message.completed", {"text": "done", "agent": AGENT})
    )
    assert child["payload"]["agent"] == AGENT

    root = validate_event_v2(_v2_event("message.completed", {"text": "done"}))
    assert "agent" not in root["payload"]


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "", "parent_id": "root", "role": "reviewer"},
        {"id": "child-a", "parent_id": "", "role": "reviewer"},
        {"id": "child-a", "parent_id": "root", "role": ""},
        {"id": "child-a", "parent_id": "root"},
        {"id": "root", "parent_id": "root", "role": "reviewer"},
        {"id": "child-a", "parent_id": "root", "role": "reviewer", "model": "x"},
    ],
)
def test_invalid_agent_shapes_fail_closed(payload):
    with pytest.raises(HarnessProtocolError):
        validate_event_v2(_v2_event("message.completed", {"text": "x", "agent": payload}))


def test_agent_is_rejected_on_non_attributable_events():
    with pytest.raises(HarnessProtocolError, match="must not carry payload.agent"):
        validate_event_v2(_v2_event("run.started", {"agent": AGENT}))


def test_delegation_start_only_requires_identity():
    event = validate_event_v2(
        _v2_event(
            "tool.started",
            {"tool_id": "tu-1", "name": "Subagent", "input": {"role": "reviewer"}, "subagent": AGENT},
        )
    )
    assert event["payload"]["subagent"] == AGENT


def test_delegation_completion_carries_status_and_detail_usage():
    event = validate_event_v2(
        _v2_event(
            "tool.completed",
            {
                "tool_id": "tu-1",
                "name": "Subagent",
                "output": "summary",
                "error": False,
                "subagent": {
                    **AGENT,
                    "status": "completed",
                    "usage": {"input_tokens": 1200, "output_tokens": 300},
                },
            },
        )
    )
    assert event["payload"]["subagent"]["status"] == "completed"
    assert event["payload"]["subagent"]["usage"] == {
        "input_tokens": 1200,
        "output_tokens": 300,
    }


@pytest.mark.parametrize(
    "subagent",
    [
        {**AGENT, "status": "running"},
        {**AGENT, "status": "completed", "usage": {"input_tokens": -1}},
        {**AGENT, "status": "completed", "usage": {"total_tokens": 3}},
        {**AGENT, "status": "completed", "unknown": 1},
    ],
)
def test_invalid_delegation_detail_fails_closed(subagent):
    with pytest.raises(HarnessProtocolError):
        validate_event_v2(
            _v2_event("tool.completed", {"tool_id": "tu-1", "name": "Subagent", "subagent": subagent})
        )


def test_subagent_detail_is_rejected_on_child_and_root_messages():
    with pytest.raises(HarnessProtocolError, match="must not carry payload.subagent"):
        validate_event_v2(
            _v2_event("message.completed", {"text": "x", "subagent": AGENT})
        )
