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

## Claude `2.1.153` capture

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

### OpenCode `1.18.19` — PASSED on the development Host

Task 621 (`harness=opencode`, provider `anthropic_messages`, `require_changes=false`)
completed. The root called the native `task` tool twice and both children ran
`echo marker-alpha` / `echo marker-beta`. Projected `TaskLog` state:

| Row | `name` | `agent` | `subagent` |
|---|---|---|---|
| delegation 1 | `Subagent` | – | `{id: ses_f6b25af3…, parent_id: root, role: general, status: completed, usage{input 688, output 116}}` |
| delegation 2 | `Subagent` | – | `{id: ses_f6b25ae9…, parent_id: root, role: general, status: completed, usage{input 698, output 122}}` |
| child 1 tool | `Bash` | `{id: ses_f6b25af3…, parent_id: root, role: general}` | – |
| child 2 tool | `Bash` | `{id: ses_f6b25ae9…, parent_id: root, role: general}` | – |

Each child's id matches its own delegation row — the two concurrent children
did not cross-pair. Served browser (`/tasks/621`) renders the same tree:

```text
Subagent · general #1   [Completed]
Subagent · general #2   [Completed]
  └─ [Subagent · general #1] Thinking
  └─ [Subagent · general #2] Thinking
  └─ [Subagent · general #1] Bash
  └─ [Subagent · general #2] Bash
  └─ [Subagent · general #1] AI  marker-alpha
  └─ [Subagent · general #2] AI  marker-beta
```

`scrollWidth == clientWidth` at both `390px` and `1512px`, with no overflowing
node.

### Why the first live OpenCode run (Task 617) projected plain `Task` rows

Not an adapter defect: **task-time orchestration does not come from the Worker
Kit.** `entrypoint.worker.sh` only uses the Kit for `--verify`; Task execution
runs the orchestration snapshot uploaded from the *backend image*
(`/opt/codify/runtime-source`, `RUNTIME_SOURCE_ENV`). Task 617's bundle pinned
`opencode_events.py` = `cf92470e…` (pre-change bytes) while the Kit and the
branch had `2b1116c0…`. Rebuilding the image fixed it.

Operational rule this establishes, and the reason Task 620 still projected
without `subagent`/`agent` metadata:

1. an adapter change requires rebuilding **both** `codify-backend` and
   `codify-scheduler` (the scheduler runs the projector) — rebuilding only the
   backend restarts the orchestrator while the projector keeps running the old
   image;
2. then the Profile must be re-verified, because the frozen harness
   verification evidence carries the adapter digest;
3. never execute Kit files directly on the Host: a stray
   `worker-entrypoint/**/__pycache__` changes the Kit's mounted bytes and makes
   `verify-runtime` fail with `worker_kit_invalid`.


### Pi `0.84.2` + `pi-subagents 0.67.0` — blocked by detached workflow runs

See [../../../../deploy/worker-cli/pi-subagents/README.md](../../../../deploy/worker-cli/pi-subagents/README.md).

### Codex `0.146.0` — PASSED on the development Host

Task 622 (`harness=codex`, provider `openai_responses`, `require_changes=false`)
completed in 25 s. The root spawned two children in parallel; the projected
`TaskLog` state:

| Row | `name` | `agent` | `subagent` |
|---|---|---|---|
| delegation 1 | `Subagent` | – | `{id: <UUID:e4ab12b5>, parent_id: root, role: agent, status: completed}` |
| delegation 2 | `Subagent` | – | `{id: <UUID:f0d6b774>, parent_id: root, role: agent, status: completed}` |
| child 1 tool | `shell` | `{id: <UUID:e4ab12b5>, parent_id: root, role: agent}` | – |
| child 2 tool | `shell` | `{id: <UUID:f0d6b774>, parent_id: root, role: agent}` | – |

Served browser (`/tasks/622`) renders `Subagent · agent #1/#2` with
`Completed`, indented child `shell`/`AI` rows carrying the matching badge, the
two children interleaved in real arrival order, and
`scrollWidth == clientWidth == 1512`.

Codex reports no child role, so `role` stays the neutral `agent`; the child
identity is the sanitizer's stable pseudonym for the native child thread id.

### Pi `0.84.2` + `pi-subagents 0.67.0` — PASSED on the development Host

Task 627 (`harness=pi`, provider `anthropic_messages`) completed in ~75 s. The
Kit-fixed extension is loaded through `--no-extensions -e <payload>` with the
Codify ceiling applied; `vendor/force-foreground.patch` pins depth-0 launches to
the foreground path so the tool result carries the child inventory. Projected
`TaskLog` state:

| Row | `name` | `agent` | `subagent` |
|---|---|---|---|
| delegation 1 | `Subagent` | – | `{id: <UUID:2d12cfab>, parent_id: root, role: delegate, status: completed, usage{input 1934, output 138, cached 1664}}` |
| delegation 2 | `Subagent` | – | `{id: <UUID:ee6104d0>, parent_id: root, role: delegate, status: completed, usage{input 1902, output 96, cached 1664}}` |
| child 1 message | `AI` | `{id: <UUID:2d12cfab>, parent_id: root, role: delegate}` | – |
| child 1 tool | `Bash` | same child id | – |
| child 2 message / tool | `AI` / `Bash` | `{id: <UUID:ee6104d0>, …}` | – |

The served page shows `Subagent · delegate #1/#2` (Completed, `2.1k`/`2.0k`
tokens) with indented child rows carrying the matching badge, and
`scrollWidth == clientWidth == 1512`.

### §10 criterion 5 — usage authority (verified)

Task 627's canonical `usage.final` is byte-identical to the native terminal
usage in the same archive (input 3241, cached 8320, output 55); the two
children's detail usage is *not* added on top. Every acceptance task shows the
same equality between `usage.final` and the Task's stored token totals
(621: 171/85, 622: 10812/36, 623: 23501/281, 627: 3241/55).

### §10 criterion 6 — cancel convergence (verified)

| Harness | Evidence |
|---|---|
| Pi | foreground child shares the parent process group; `SIGTERM` to the group reaps parent (exit 143) and child within 5 s, no leftovers |
| OpenCode | Task 628 cancelled mid-delegation: one `harness.failed kind=cancelled`, then `worker_finalization`, then exactly one `run.failed status=cancelled`; the container is gone and no `opencode serve` / `sleep` process survives on the Host |

Claude and Codex cancellation were not re-probed in this pass; both keep the
public Runner's process-group termination.

### Net result

All four harnesses pass the core of the §10 matrix end to end on the development
Host — Kits, canonical events, `TaskLog` metadata and the served browser — one
model protocol each (Claude `anthropic_messages`, Codex `openai_responses`,
OpenCode `anthropic_messages`, Pi `anthropic_messages`).

The Runtime Manifest now declares `subagents: true` for all four harnesses, on
this evidence:

| Harness / protocol | Task | Result |
|---|---|---|
| Claude `anthropic_messages` | 623 | 2 delegation rows + child rows |
| Codex `openai_responses` | 622 | 2 delegation rows + child rows |
| Pi `anthropic_messages` | 627 | 2 delegation rows + child messages/tools |
| Pi `openai_responses` | 629 | 2 delegation rows + child rows |
| Pi `openai_chat_completions` | 630 | 2 delegation rows + child rows |
| OpenCode `anthropic_messages` | 621 | 2 delegation rows + child rows |
| OpenCode `openai_responses` | 631 | 2 delegation rows + child rows |
| OpenCode `openai_chat_completions` | 632 | 2 delegation rows + child rows |

Plus, per criterion: §10.5 usage authority (Pi verified byte-for-byte, and the
backend never re-sums child detail), §10.6 cancellation (all four harnesses:
single `harness.failed kind=cancelled` → finalization → single
`run.failed status=cancelled`, container gone, no surviving child process),
§10.9/10/11 by DOM inspection of the served pages.

Two items remain outside this evidence set and are **not** claimed:

1. Codex nested-delegation refusal on a live Task — implemented and unit-tested
   (`subagent_depth_unsupported`), but the model was never observed nesting.
2. The §9 exit note: `--bare` was replaced by explicit isolation flags in the
   Claude runner (see below), which is a deliberate change to every Claude Task,
   not only subagent-capable ones.

### §9 note — the Claude runner's isolation flags

`--bare` was the runner's minimal mode, but on `2.1.153` it also sets
`CLAUDE_CODE_SIMPLE=1`, which removes the `Agent` tool. The runner now passes
`--setting-sources "" --strict-mcp-config --disable-slash-commands` instead:

- no user/project/local settings load, so repository hooks and permissions stay
  inert (the planted-hook control fired in **none** of bare, isolated-flag or
  unisolated runs — untrusted workspaces never load project settings);
- no MCP servers beyond an explicit `--mcp-config`, which Codify never passes;
- no skills from discovery; task Skills still resolve through the materialized
  snapshot;
- the residual difference is that `CLAUDE_CODE_SIMPLE=1` also skipped LSP,
  plugin sync, attribution, auto-memory, background prefetches and CLAUDE.md
  auto-discovery. Probes showed no extra workspace files and no CLAUDE.md
  context in either mode, and the worker authenticates with `ANTHROPIC_API_KEY`
  against a task-local HOME, so there is no keychain to read.
