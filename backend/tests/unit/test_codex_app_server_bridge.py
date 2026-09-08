"""Focused tests for the Codex App Server stdio bridge."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BRIDGE = REPO_ROOT / "deploy/worker-entrypoint/harness/adapters/codex_bridge.py"


def test_bridge_completes_one_thread_and_forwards_native_messages(tmp_path: Path) -> None:
    fake_codex = tmp_path / "fake-codex"
    request_log = tmp_path / "requests.jsonl"
    fake_codex.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

for line in sys.stdin:
    message = json.loads(line)
    request_log = os.environ.get("CODEX_REQUEST_LOG")
    if request_log:
        with open(request_log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(message) + "\\n")
    method = message.get("method")
    if message.get("id") == 1:
        print(json.dumps({"id": 1, "result": {"platformOs": "linux"}}), flush=True)
    elif method == "thread/start":
        thread = {"id": "thread-1", "sessionId": "session-1"}
        print(json.dumps({"id": message["id"], "result": {"thread": thread}}), flush=True)
        print(json.dumps({"method": "thread/started", "params": {"thread": thread}}), flush=True)
    elif method == "turn/start":
        turn = {"id": "turn-1", "status": "inProgress"}
        print(json.dumps({"id": message["id"], "result": {"turn": turn}}), flush=True)
        params = {"threadId": "thread-1", "turn": turn}
        print(json.dumps({"method": "turn/started", "params": params}), flush=True)
        item = {"id": "item-r", "type": "reasoning", "summary": [], "content": []}
        print(json.dumps({"method": "item/started", "params": {"item": item, "threadId": "thread-1", "turnId": "turn-1"}}), flush=True)
        print(json.dumps({"method": "item/completed", "params": {"item": item, "threadId": "thread-1", "turnId": "turn-1"}}), flush=True)
        done = {"id": "item-m", "type": "agentMessage", "text": "done"}
        print(json.dumps({"method": "item/completed", "params": {"item": done, "threadId": "thread-1", "turnId": "turn-1"}}), flush=True)
        completed = {"id": "turn-1", "status": "completed", "items": []}
        print(json.dumps({"method": "turn/completed", "params": {"threadId": "thread-1", "turn": completed}}), flush=True)
""",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("inspect the repository", encoding="utf-8")

    result = subprocess.run(
        [
            "python3",
            str(BRIDGE),
            "--codex-bin",
            str(fake_codex),
            "--prompt-file",
            str(prompt),
        ],
        env={
            **os.environ,
            "OPENAI_MODEL": "test-model",
            "CODIFY_CODEX_REASONING_EFFORT": "high",
            "CODEX_REQUEST_LOG": str(request_log),
        },
        capture_output=True,
        text=True,
        check=True,
    )

    messages = [json.loads(line) for line in result.stdout.splitlines()]
    methods = [message.get("method") for message in messages]
    assert "thread/started" in methods
    assert "item/started" in methods
    assert "item/completed" in methods
    assert methods[-1] == "turn/completed"
    requests = [json.loads(line) for line in request_log.read_text().splitlines()]
    turn_start = next(message for message in requests if message.get("method") == "turn/start")
    assert turn_start["params"]["effort"] == "high"
