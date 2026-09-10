from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


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
    result = subprocess.run(
        [sys.executable, str(EVENT_WRITER), event_type, "--payload", json.dumps(payload or {})],
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
