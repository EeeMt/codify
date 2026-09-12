from __future__ import annotations

import errno
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
EVENT_WRITER = REPO_ROOT / "deploy/worker-entrypoint/harness/events.py"


def _env(runtime_dir: Path) -> dict[str, str]:
    return {
        **os.environ,
        "CODIFY_RUNTIME_DIR": str(runtime_dir),
        "CODIFY_ATTEMPT_ID": "preview-attempt",
        "TASK_ID": "7",
        "CODIFY_HARNESS_KEY": "codex",
        "CODIFY_ADAPTER_VERSION": "preview",
        "CODIFY_CLI_VERSION": "0.146.0",
    }


def _emit(runtime_dir: Path, event_type: str, payload: dict | None = None) -> str:
    # Payloads travel over stdin, exactly like the shell helper (common.sh) and
    # the adapters (_emit) do: a single argv element cannot exceed the kernel
    # per-argument limit, which large tool inputs / message texts hit.
    result = subprocess.run(
        [sys.executable, str(EVENT_WRITER), event_type, "--payload-stdin"],
        input=json.dumps(payload or {}),
        env=_env(runtime_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stderr


def test_preview_is_bounded_sanitized_and_emitted_for_all_harness_events(tmp_path: Path):
    previews = []
    for event_type, payload in (
        ("run.started", {}),
        ("model.resolved", {"model": "deepseek-v4-flash", "session_id": "secret-session"}),
        ("reasoning_summary.started", {"reasoning_id": "r1"}),
        (
            "tool.started",
            {"name": "Bash", "input": {"command": "echo sk-ant-secret1234567890"}},
        ),
        ("tool.completed", {"error": False, "output": "x" * 700, "exit_code": 0}),
        ("message.completed", {"text": "done\nwith a second line"}),
        ("usage.final", {"usage": {"input_tokens": 12, "output_tokens": 3}}),
        ("harness.completed", {"result": "done", "session_id": "secret-session"}),
        ("worker.finalization", {"exit_code": 0}),
        ("run.completed", {"status": "completed", "success": True}),
    ):
        previews.append(_emit(tmp_path, event_type, payload))

    output = "".join(previews)
    assert "[codex][#1][harness] started" in output
    assert "[codex][#4][tool] Bash" in output
    assert "[codex][#5][tool] completed exit=0" in output
    assert "[codex][#6][assistant] done with a second line" in output
    assert "[codex][#7][usage] input=12 output=3" in output
    assert "[codex][#8][harness] completed" in output
    assert "sk-ant-secret1234567890" not in output
    assert "secret-session" not in output
    assert "truncated, 700 chars total" in output


def test_high_frequency_events_are_persisted_without_preview(tmp_path: Path):
    _emit(tmp_path, "run.started")
    assert _emit(tmp_path, "message.delta", {"text": "partial"}) == ""
    assert _emit(tmp_path, "usage.updated", {"usage": {"input_tokens": 1}}) == ""
    events = [json.loads(line) for line in (tmp_path / "event.jsonl").read_text().splitlines()]
    assert [event["type"] for event in events] == ["run.started", "message.delta", "usage.updated"]


def test_preview_failure_does_not_lose_durable_event(tmp_path: Path, monkeypatch):
    spec = importlib.util.spec_from_file_location("canonical_events", EVENT_WRITER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("CODIFY_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("CODIFY_ATTEMPT_ID", "preview-attempt")
    monkeypatch.setenv("TASK_ID", "7")
    monkeypatch.setenv("CODIFY_HARNESS_KEY", "codex")
    monkeypatch.setenv("CODIFY_ADAPTER_VERSION", "preview")
    monkeypatch.setenv("CODIFY_CLI_VERSION", "0.146.0")

    class BrokenStderr:
        def write(self, _value):
            raise OSError("stderr unavailable")

        def flush(self):
            raise OSError("stderr unavailable")

    monkeypatch.setattr(module.sys, "stderr", BrokenStderr())
    event = module.emit("run.started", {}, None)
    assert event["seq"] == 1
    assert (tmp_path / "event.jsonl").read_text().count("run.started") == 1


# 2 MB exceeds every per-argument limit in play (Linux MAX_ARG_STRLEN is 32
# pages ≈ 128 KiB; the Darwin ARG_MAX block is 1 MiB), so the argv form cannot
# carry a payload this size on any platform the worker targets.
_OVERSIZED_TEXT = "y" * 2_000_000


def test_oversized_payload_is_accepted_over_stdin(tmp_path: Path):
    # A large Write tool input / long assistant message used to kill the
    # translator with E2BIG before the durable event could be appended, losing
    # the whole attempt's result. The payload now travels on stdin, which the
    # kernel does not size-limit per argument.
    _emit(tmp_path, "run.started")
    stderr = _emit(tmp_path, "message.completed", {"text": _OVERSIZED_TEXT})

    events = [json.loads(line) for line in (tmp_path / "event.jsonl").read_text().splitlines()]
    assert [event["type"] for event in events] == ["run.started", "message.completed"]
    assert events[-1]["payload"]["text"] == _OVERSIZED_TEXT
    # The stderr mirror stays bounded (2000-char text cap) even for a multi-MB
    # payload, so a big event never turns into a big log write.
    assert f"truncated, {len(_OVERSIZED_TEXT)} chars total" in stderr
    assert len(stderr) < 4096


def test_oversized_payload_cannot_travel_in_argv(tmp_path: Path):
    # Documents *why* the writer takes its payload on stdin. The point where a
    # single argv element stops fitting is OS-dependent (Linux caps one element
    # at MAX_ARG_STRLEN, Darwin caps the argv+env block at ARG_MAX), but no
    # supported worker kernel carries 2 MB in one argument. Where a kernel does
    # accept it, the argv path is merely slow rather than broken, so skip
    # instead of asserting a limit this test cannot guarantee.
    _emit(tmp_path, "run.started")
    payload = json.dumps({"text": _OVERSIZED_TEXT})
    try:
        subprocess.run(
            [sys.executable, str(EVENT_WRITER), "message.completed", "--payload", payload],
            env=_env(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
    except OSError as exc:
        assert exc.errno == errno.E2BIG
        return
    pytest.skip("kernel accepted a 2 MB argv element; argv size limit not enforced here")

