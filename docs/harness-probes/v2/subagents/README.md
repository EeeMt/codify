# V2 Subagent Phase 0 probe evidence (2026-09-12)

Native subagent captures taken **inside the target Worker environment** with the
frozen binaries, then redacted. These are the only source for the field
mappings in [open-harness-v2-subagent-adaptation.md](../../../../architecture/open-harness-v2-subagent-adaptation.md)
§6: no value below is inferred from documentation or from prompt text.

Every sample here is captured the same way: one root agent asked to spawn
**two parallel children**, each running exactly one shell command and returning
a different marker (`marker-alpha` / `marker-beta`). Credentials and repository
content never enter these files; `scripts/harness-probes/v2/secret-scan.py`
validates the tree (`findings=0`).

| Harness | Frozen version | Transport | Capture | File |
|---|---|---|---|---|
| Claude | `2.1.153` | `cli_stream_json` | `-p --output-format stream-json --verbose --include-partial-messages` | [claude/delegation.jsonl](claude/delegation.jsonl) |
| Codex | `0.146.0` | `rpc_stdio` (`codex app-server --stdio`) | JSON-RPC notifications on the root subscription | [codex/collab-items.jsonl](codex/collab-items.jsonl) |
| OpenCode | `1.18.19` | `server_http` (`GET /event` SSE) | Server-global SSE during one `task` delegation | [opencode/child-session.jsonl](opencode/child-session.jsonl) |

## Claude `2.1.153`

- Delegation is the **`Agent`** tool (`tool_use.name == "Agent"`); its tool_use
  id is also the child's `parent_tool_use_id`, so one native id identifies both
  the delegation row and every child event.
- Child records (`assistant`, `user`) carry `parent_tool_use_id` **plus**
  `subagent_type` and `task_description`. Partial `stream_event` records are
  **root-only** — child text and thinking therefore arrive only as complete
  records, so the adapter must not expect a child partial lifecycle.
- Native lifecycle signals (all `type == "system"`):
  | subtype | fields | use |
  |---|---|---|
  | `task_started` | `tool_use_id`, `subagent_type`, `description`, `task_type`, `prompt` | role + delegation identity |
  | `task_progress` | `tool_use_id`, `usage{total_tokens,tool_uses,duration_ms}`, `last_tool_name` | child progress detail |
  | `task_notification` | `tool_use_id`, `status`, `summary`, `usage` | alternate child terminal |
- A child's terminal is therefore reported **twice** (the `Agent` tool result and
  `task_notification`); the adapter settles the row on the first one only.
- Child `assistant.usage` repeats the child's own cumulative request usage, so
  the adapter keeps it monotonic per key instead of summing.

## Codex `0.146.0`

- The root subscription **does** receive child-thread items directly: every
  `item/started` / `item/completed` notification carries `params.threadId`, and
  child `userMessage` / `reasoning` / `agentMessage` / `commandExecution` items
  arrive with the child thread id. No rollout/session file is read.
- `child turn/completed` notifications also arrive for child threads, so only
  the root thread's turn may settle the attempt.
- Delegation is the `collabAgentToolCall` item (`item/tool` in camelCase:
  `spawnAgent`, `wait`, `closeAgent`, …) with:
  | field | meaning |
  |---|---|
  | `id` | delegation tool id |
  | `tool` | `spawnAgent` / `wait` / `closeAgent` … |
  | `senderThreadId` | delegating (root) thread |
  | `receiverThreadIds` | child thread ids; **empty on `item/started`, filled on `item/completed`** |
  | `prompt` | delegated task text |
  | `model`, `reasoningEffort` | child's inherited model/effort |
  | `agentsStates` | `{childThreadId: {status, message}}`; terminal `status` + final `message` |
- `agentsStates[*].status` observed: `pendingInit` (running), `completed`.
  Unknown states are never treated as terminal.
- `multi_agent` is a stable `0.146.0` feature and is enabled by default; the
  adapter freezes `features.multi_agent = true` in the task-private
  `config.toml`. `default_subagent_model` was **not** honored by the probe (the
  child inherited the thread model), so Codify deliberately writes no subagent
  model override — inheritance is the required behavior.
- Depth/concurrency limit keys could not be verified on this binary, so nested
  delegation is refused by the event adapter (`subagent_depth_unsupported`)
  instead of by an unverified config key.

## OpenCode `1.18.19`

- Children are **native sessions**: `session.created` for a child carries
  `info.parentID` = the root session id (the root's own `session.created` is not
  emitted because the Bridge creates it over HTTP before subscribing).
- `session.idle` fires for the root **and every child** in the same run, so
  admission plus root-only settled logic are both mandatory.
- Delegation is the root session's `task` tool part:
  | field | meaning |
  |---|---|
  | `part.callID` | delegation tool id |
  | `state.metadata.sessionId` | child session id (the delegation target) |
  | `state.metadata.parentSessionId` | root session id |
  | `state.input.subagent_type` | child role (`general`) |
  | `state.status` | `pending` → `running` → `completed` |
  | `state.output` | `<task id="ses_..." state="completed"><task_result>…</task_result></task>` |
- Child session events carry `sessionID` at the envelope, inside `part`, or
  inside `info` depending on the event family — the translator must check all
  three, exactly like the Bridge's admission filter does.
- The root session is published to the translator explicitly by the Bridge
  (`codify.root_session` control record) rather than inferred from "first
  session seen".
