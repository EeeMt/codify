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

## Live acceptance on the development Host (2026-09-12)

Kit `0.6.17-linux-amd64-8140c93eb09a` (built from this branch, all four harness
CLIs, `subagents: false` in every manifest entry), Profile
`v2-canary-four-harness` re-verified against it, Tasks created through the real
API. Three results, all reproducible:

### Claude `2.1.153` — blocked by the runner's `--bare`

The frozen runner always passes `--bare`. On `2.1.153`, `--bare` removes the
delegation tool entirely, so a Codify Claude Task can never call `Agent`
(Task 616: the model answered *"There is no `Agent` tool in my available
toolset — I only have `Bash`, `Edit`, and `Read`"*).

Isolated on the Kit's own binary, same prompt, three flag combinations:

| Invocation | tools the model actually got |
|---|---|
| `--bare --allowedTools "Bash,Read,Edit,Write,Agent"` | `Bash` |
| `--allowedTools "Bash,Read,Edit,Write,Agent"` (no `--bare`) | **`Agent`, `Bash`** |
| `--bare --dangerously-skip-permissions` | `Bash` |

`Agent` was added to the runner's default allow-list, but that alone cannot
enable delegation: **dropping `--bare` is required**, and `--bare` is what keeps
user/project config, hooks and auto-discovery out of the worker. That
substitution (explicit `--setting-sources`/`--strict-mcp-config` and friends)
has not been designed or verified, so Claude `subagents` stays `false`.

### OpenCode `1.18.19` — ran, delegation row not projected (unresolved)

Task 617 (`harness=opencode`) completed on the new Kit. The root called the
native `task` tool twice and both children returned `marker-alpha` /
`marker-beta`; the canonical stream, however, projected them as plain
`tool.started`/`tool.completed` rows named `Task` with **no** `subagent` detail,
and no child-attributed events.

Replaying that Task's own sanitized raw archive
(`harness-events/opencode.jsonl`) through the **byte-identical** translator
(`sha256 2b1116c0…`) produces the expected `Subagent` rows with
`subagent.id` = the child session id, both with and without the
`codify.root_session` control record. The live/offline difference is therefore
not in the committed code and is still unexplained; it needs one more
instrumented run (the child `session.created` records are also absent from the
live archive, which the offline replay does not reproduce).

### Pi `0.84.2` + `pi-subagents 0.67.0` — blocked by detached workflow runs

See [../../../../deploy/worker-cli/pi-subagents/README.md](../../../../deploy/worker-cli/pi-subagents/README.md).

### Net result

No harness may declare `subagents: true` yet: every manifest entry stays
`false`, which is the contract's fail-closed default. Phases 1–2 (vocabulary,
validation, projection, frontend, and the three adapters) are verified by
fixtures and unit tests; Phase 4 real-Task acceptance is **not** passed.


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
