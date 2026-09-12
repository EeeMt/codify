#!/usr/bin/env python3
"""Drive one Codex App Server thread over its stdio JSONL protocol.

The bridge deliberately owns one app-server process for one Codify attempt. It
only forwards server messages to the existing Codex event translator; client
requests are kept out of the raw archive. Approval requests fail closed instead
of granting permissions that were not present in the frozen task snapshot.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any


class BridgeError(RuntimeError):
    """Raised when the app-server handshake or turn cannot be completed."""


class AppServerBridge:
    def __init__(self, codex_bin: str, prompt_file: Path, resume_session: str | None) -> None:
        self.codex_bin = codex_bin
        self.prompt_file = prompt_file
        self.resume_session = resume_session
        self.process: subprocess.Popen[str] | None = None
        self.thread_id: str | None = None
        self.turn_id: str | None = None
        self._request_id = 0
        self._interrupt_sent = False

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send(self, message: dict[str, Any]) -> None:
        process = self.process
        if process is None or process.stdin is None or process.poll() is not None:
            raise BridgeError("Codex App Server is not running")
        process.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
        process.stdin.flush()

    def _forward(self, message: str) -> dict[str, Any]:
        # The child protocol is JSONL. Keep the original server line intact so
        # the downstream translator can sanitize and archive the native record.
        sys.stdout.write(message.rstrip("\n") + "\n")
        sys.stdout.flush()
        try:
            parsed = json.loads(message)
        except json.JSONDecodeError as exc:
            raise BridgeError("Codex App Server emitted a non-JSON line") from exc
        if not isinstance(parsed, dict):
            raise BridgeError("Codex App Server emitted a non-object message")
        return parsed

    def _read(self) -> dict[str, Any]:
        process = self.process
        if process is None or process.stdout is None:
            raise BridgeError("Codex App Server stdout is unavailable")
        line = process.stdout.readline()
        if not line:
            code = process.poll()
            raise BridgeError(f"Codex App Server ended before turn completion (exit={code})")
        return self._forward(line)

    def _reply_to_server_request(self, message: dict[str, Any]) -> None:
        """Reject unexpected server requests without widening task permissions."""
        request_id = message.get("id")
        if request_id is None or "method" not in message:
            return
        self._send(
            {
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": "Codify worker bridge does not grant app-server requests",
                },
            }
        )

    def _read_response(self, request_id: int) -> dict[str, Any]:
        while True:
            message = self._read()
            if message.get("id") == request_id and (
                "result" in message or "error" in message
            ):
                if "error" in message:
                    error = message.get("error")
                    if isinstance(error, dict):
                        detail = str(error.get("message") or "Codex App Server request failed")
                    else:
                        detail = "Codex App Server request failed"
                    raise BridgeError(detail)
                return message
            self._reply_to_server_request(message)

    def _sandbox(self) -> str:
        configured = os.environ.get("CODIFY_CODEX_SANDBOX", "").strip()
        if configured:
            return configured
        if os.environ.get("CODIFY_HARNESS_SANDBOX_MODE", "container-boundary") == "sandboxed":
            return "read-only"
        return "danger-full-access"

    def _thread_params(self) -> dict[str, Any]:
        if self.resume_session:
            params: dict[str, Any] = {"threadId": self.resume_session}
        else:
            params = {"cwd": os.getcwd()}
        model = os.environ.get("OPENAI_MODEL", "").strip()
        if model:
            params["model"] = model
        params.update(
            {
                "approvalPolicy": "never",
                "sandbox": self._sandbox(),
            }
        )
        return params

    def _turn_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "threadId": self.thread_id,
            "input": [{"type": "text", "text": self.prompt_file.read_text()}],
        }
        effort = os.environ.get("CODIFY_CODEX_REASONING_EFFORT", "").strip()
        if effort:
            params["effort"] = effort
        return params

    def _launch(self) -> None:
        command = [self.codex_bin, "app-server", "--stdio"]
        launcher = os.environ.get("CODIFY_CODEX_RUN_AS", "").strip()
        if launcher:
            if not launcher.startswith("/") or not os.access(launcher, os.X_OK):
                raise BridgeError("CODIFY_CODEX_RUN_AS must be an executable absolute path")
            command = [
                "env",
                "HOME=/home/codify",
                "USER=codify",
                "LOGNAME=codify",
                launcher,
                "--",
                *command,
            ]
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            bufsize=1,
            env=os.environ.copy(),
        )

    def _send_interrupt(self) -> None:
        if self._interrupt_sent or not self.thread_id or not self.turn_id:
            return
        self._interrupt_sent = True
        try:
            self._send(
                {
                    "id": self._next_request_id(),
                    "method": "turn/interrupt",
                    "params": {"threadId": self.thread_id, "turnId": self.turn_id},
                }
            )
        except (BrokenPipeError, BridgeError):
            return

    def _handle_signal(self, _signum: int, _frame: Any) -> None:
        self._send_interrupt()

    def run(self) -> int:
        self._launch()
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        try:
            initialize_id = self._next_request_id()
            self._send(
                {
                    "id": initialize_id,
                    "method": "initialize",
                    "params": {
                        "clientInfo": {
                            "name": "codify-worker",
                            "title": "Codify Worker",
                            "version": os.environ.get("CODIFY_RUNTIME_BUNDLE_DIGEST", "unknown")[:12],
                        }
                    },
                }
            )
            self._read_response(initialize_id)
            self._send({"method": "initialized", "params": {}})

            thread_request_id = self._next_request_id()
            self._send(
                {
                    "id": thread_request_id,
                    "method": "thread/resume" if self.resume_session else "thread/start",
                    "params": self._thread_params(),
                }
            )
            thread_response = self._read_response(thread_request_id)
            thread = ((thread_response.get("result") or {}).get("thread") or {})
            self.thread_id = thread.get("id") if isinstance(thread, dict) else None
            if not self.thread_id:
                raise BridgeError("Codex App Server did not return a thread id")

            turn_request_id = self._next_request_id()
            self._send(
                {
                    "id": turn_request_id,
                    "method": "turn/start",
                    "params": self._turn_params(),
                }
            )
            turn_response_seen = False
            while True:
                message = self._read()
                if message.get("id") == turn_request_id and "result" in message:
                    turn_response_seen = True
                    result_turn = (message.get("result") or {}).get("turn") or {}
                    if isinstance(result_turn, dict):
                        self.turn_id = result_turn.get("id") or self.turn_id
                    continue
                if message.get("id") == turn_request_id and "error" in message:
                    return 1
                self._reply_to_server_request(message)
                method = message.get("method")
                params = message.get("params")
                if not isinstance(params, dict):
                    continue
                if method == "thread/started":
                    thread = params.get("thread")
                    if isinstance(thread, dict):
                        # Only the task's own thread may become the bridge's
                        # root identity; a child thread must never replace it.
                        self.thread_id = self.thread_id or thread.get("id")
                elif method == "turn/started":
                    turn = params.get("turn")
                    # A spawned child thread starts its own turn; only the root
                    # turn id may be interrupted, otherwise cancel would target
                    # a child (open-harness-v2-subagent-adaptation.md §6.2).
                    if (
                        isinstance(turn, dict)
                        and params.get("threadId") == self.thread_id
                    ):
                        self.turn_id = turn.get("id") or self.turn_id
                elif method == "turn/completed":
                    completed_thread_id = params.get("threadId")
                    if completed_thread_id and completed_thread_id != self.thread_id:
                        continue
                    turn = params.get("turn") or {}
                    status = turn.get("status") if isinstance(turn, dict) else None
                    if status not in {"completed", "failed", "interrupted"}:
                        continue
                    if not turn_response_seen:
                        # The server normally responds to turn/start first, but
                        # the terminal notification is still authoritative.
                        turn_response_seen = True
                    return 0 if status == "completed" else 1
        finally:
            process = self.process
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=3)
                except (subprocess.TimeoutExpired, OSError):
                    process.kill()
                    process.wait()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-bin", required=True)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--resume-session", default=None)
    args = parser.parse_args()
    if not args.prompt_file.is_file() or not args.prompt_file.stat().st_size:
        print(f"Codex prompt file is missing: {args.prompt_file}", file=sys.stderr)
        return 1
    try:
        return AppServerBridge(args.codex_bin, args.prompt_file, args.resume_session).run()
    except (BridgeError, OSError) as exc:
        print(f"Codex App Server bridge failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
