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

Each result below was taken on a Kit built from this branch (all four harness
CLIs), with Profile `v2-canary-four-harness` re-verified against that Kit and
Tasks created through the real API. The first passes ran while the manifest
still declared `subagents: false`; the capability was flipped to `true` only
after every §10 combination had passed, and the final artifact set
(Kit `b5427d36336f`, Runtime Bundle 258) re-ran the two Pi ceiling cases
(Tasks 644 and 645). Results, all reproducible:

### Claude `2.1.153` — resolved: `--bare` replaced by explicit isolation

The frozen runner used to pass `--bare`. On `2.1.153`, `--bare` sets
`CLAUDE_CODE_SIMPLE=1`, which removes the `Agent` tool entirely, so a Codify
Claude Task could never delegate (Task 616: the model answered *"There is no
`Agent` tool in my available toolset — I only have `Bash`, `Edit`, and `Read`"*).

Isolated on the Kit's own binary, same prompt, three flag combinations:

| Invocation | tools the model actually got |
|---|---|
| `--bare --allowedTools "Bash,Read,Edit,Write,Agent"` | `Bash` |
| `--allowedTools "Bash,Read,Edit,Write,Agent"` (no `--bare`) | **`Agent`, `Bash`** |
| `--bare --dangerously-skip-permissions` | `Bash` |

The main run path now expresses the same boundary with explicit flags instead of
`--bare` (`runners/claude-run.sh`): `--setting-sources ""`,
`--strict-mcp-config`, `--disable-slash-commands`. `Agent` is appended to the
allow-list, because a Profile that pins its own `ALLOWED_TOOLS` would otherwise
drop delegation again.

What the flags keep, and what they do not:

- no user/project/local settings load, so repository hooks and permissions stay
  inert — the planted-hook control fired in **none** of the three combinations
  above, including the unisolated one, because an untrusted workspace never
  loads project settings;
- no MCP servers beyond an explicit `--mcp-config`, which Codify never passes;
- no skills from discovery; task Skills still resolve through the materialized
  snapshot;
- residual difference from `--bare`: `CLAUDE_CODE_SIMPLE=1` additionally skipped
  LSP, plugin sync, attribution, auto-memory, background prefetches and
  CLAUDE.md auto-discovery. Probes showed no extra workspace files and no
  CLAUDE.md context in either mode, and the worker authenticates with
  `ANTHROPIC_API_KEY` against a task-local HOME, so there is no keychain to read.

Live evidence: Task 623 (`harness=claude`, `anthropic_messages`) produced two
delegation rows plus child rows. This substitution changes **every** Claude Task,
not only delegation-capable ones.

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
did not cross-pair. Served browser (`/tasks/621`) renders one contiguous display
block per direct child:

```text
Subagent · general #1   [Completed]
  ├─ [Subagent · general #1] Thinking
  ├─ [Subagent · general #1] Bash
  └─ [Subagent · general #1] AI  marker-alpha
Subagent · general #2   [Completed]
  ├─ [Subagent · general #2] Thinking
  ├─ [Subagent · general #2] Bash
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


### Pi `0.84.2` + `pi-subagents 0.67.0` — resolved: three background routes closed

The plugin offered three ways to leave the foreground path, each of which loses
the child inventory; all three are closed by the vendor patch, together with the
repository-controlled agent discovery described below. The routes, the
patch and the final live evidence are in the
[ceiling enforcement](#ceiling-enforcement-on-the-pinned-plugin) section below
and in
[deploy/worker-cli/pi-subagents/README.md](../../../../deploy/worker-cli/pi-subagents/README.md).

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
`Completed`, each delegation followed by its own indented child `shell`/`AI`
rows carrying the matching badge, and
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
tokens), each followed by its own indented child rows carrying the matching badge, and
`scrollWidth == clientWidth == 1512`.

### §10 criterion 5 — usage authority (verified, children included)

§5.6 requires the attempt total to include every child when the native root
total does not, and the first acceptance pass got that wrong: the root's own
number was published while the children were kept as row detail only. The live
numbers prove the root total never contained them — Task 627's root reported
3241 input against 3836 for its two children, Task 623's root 23501 against
12574 per child, Task 621's 171 against 688 + 698.

All four adapters now add each child's leaf usage into the single `usage.final`
(per key monotonic, so a re-reported cumulative snapshot cannot double count),
the per-delegation detail stays on the row, and the backend still never sums it.
Task 650 shows the shape: `usage.final` output 548 = root 95 + child 235 + 218,
with both children's rows showing 235 / 218 tokens.

A child whose own result carries no text is a separate matter: the plugin
reports `outputState: "absent"` and `finalOutput: ""` (Task 648, child beta),
so the timeline has no message row and no output to expand. Nothing is
fabricated, and the plugin's artifact/session paths are deliberately not read
(§4 non-goal: no side-channel event source).

### §10 criterion 10 — delegation rows end in place (verified through the UI)

Cancelling a Task kills the harness process group, so an adapter can be dead
before it can close a running delegation (Task 653 cancelled with two open
rows: both stayed without a status). The projector now settles every delegation
row that still has no `subagent.status` when the attempt reaches
`run.failed` — the attempt terminal is authoritative — and the adapters settle
their own open rows on the paths they do reach. Cancelling Task 654 from the
served UI shows both rows turning `Cancelled` in place.

A delegation row and its child rows also publish no `output` field when the
plugin reported no text, and the projector stores no output payload for it, so
the panel no longer offers an expander that can only render empty.

### §10 criterion 6 — cancel convergence (verified)

Every harness was probed the same way: a Task launches two children, each
sleeping, and the Task is cancelled through the public API while both are in
flight. The required shape is one `harness.failed kind=cancelled`, then
`worker_finalization` (exit 143), then exactly one
`run.failed status=cancelled`, with the container gone and no surviving
root/child process on the Host. The provider-request criterion follows from
that: the container that owns every child process is reaped.

| Harness | Evidence |
|---|---|
| Claude | Task 646 cancelled with two `Agent` children in flight: `harness.failed kind=cancelled` → `worker_finalization exit_code=143` → one `run.failed status=cancelled`; container exited 143 and no `claude` process survives |
| Codex | Task 647 cancelled with two child threads in flight: same three terminal rows, container exited 143, and the only `codex` processes on the Host are the Host's own dev tooling (22 h and 12 d old), none from the Task |
| Pi | foreground child shares the parent process group; `SIGTERM` to the group reaps parent (exit 143) and child within 5 s, no leftovers |
| OpenCode | Task 628 cancelled mid-delegation: one `harness.failed kind=cancelled`, then `worker_finalization`, then exactly one `run.failed status=cancelled`; the container is gone and no `opencode serve` / `sleep` process survives on the Host |

Criterion 6 is therefore verified live for all four harnesses.

### Net result

All four harnesses pass the core of the §10 matrix end to end on the development
Host — Kits, canonical events, `TaskLog` metadata and the served browser — one
model protocol each (Claude `anthropic_messages`, Codex `openai_responses`,
OpenCode `anthropic_messages`, Pi `anthropic_messages`).

The Runtime Manifest now declares `subagents: true` for all four harnesses, on
this evidence (all eight §10 combinations):

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
backend never re-sums child detail), §10.6 cancellation (live for all four
harnesses: single `harness.failed kind=cancelled` → finalization → single
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

## Child event-type coverage (audited per harness)

Every type §5.3 lists as attributable was checked against what each harness
actually reports on its own stream. "Projected" means the adapter emits it with
`payload.agent` and the projector stores it as an indented child row.

| Type | Pi | Claude | Codex | OpenCode |
|---|---|---|---|---|
| delegation `tool.started` / `tool.completed` (+ `subagent`) | yes | yes | yes | yes |
| child `message.completed` | yes (plugin `finalOutput`) | yes (child assistant text) | yes (child `agentMessage`) | yes |
| child `message.delta` | n/a: children are separate processes | n/a: partial stream events are root-only (probe) | n/a | yes, through the shared current-agent seam |
| child `tool.started` / `tool.completed` | yes, command text only | yes | yes | yes |
| child `reasoning_summary.*` | not available: the plugin redacts child thinking | yes, when a child reports thinking | yes, when a child thread reports reasoning | yes |
| child `context.compacted` | n/a | yes (attributed by `parent_tool_use_id`) | yes (by `threadId`) | yes (by session id) |
| child `diagnostic` | yes (raw archive only, no timeline row) | yes | yes | yes |

Pi-specific upstream limitation and Codify fix:

1. **Pi child tool output is now carried by the bounded result summary.** The
   Codify vendor patch pairs the plugin's own child `assistant.toolCall` and
   `toolResult` messages by native `toolCallId` while compacting the result.
   `toolCalls[]` therefore carries bounded `toolCallId`/`toolName`, output,
   error and optional native timestamps; the adapter projects those fields
   directly and never reads `transcriptPath` or `artifactPaths.outputPath`.
   A result without a matching native `toolResult` keeps the command row but
   omits output, rather than copying the child's final answer into a tool row.
2. **Pi child thinking is redacted upstream** (`<HIDDEN_REASONING_OMITTED>`), so
   no child reasoning row can exist without violating §5.7.

Projection gaps that were real and are now fixed: a delegation whose child
identity is enriched between start and completion (projector falls back to the
unique `(agent, tool_id)` row), a plain single-agent launch that reports
`results[]` with no inventory (the call's own terminal now settles its child,
and a provisional index-only identity no longer opens a throwaway row), and
`context.compacted` emitted without attribution.

One more settle rule came out of a UI report about confusing durations (Task
662). The plugin aborts a workflow's children when that workflow's script
throws, and the terminal record of such a call can arrive with an **empty
inventory** even though the children had already reached a native state in the
earlier updates (Task 664: both children completed, then the script failed).
Settling only at the attempt terminal reported a 28 s duration for a call that
ended after ~3 s, and it marked completed children as cancelled. The adapter now
remembers each child's last observed state and output, and every call terminal
settles that call's children from those facts — so an abandoned child ends as
`cancelled` where its call failed, and a child that finished keeps
`completed` with its own duration.

## Ceiling enforcement on the pinned plugin

The ceiling has to make background delegation impossible at depth 0, because a
detached launch returns no child inventory: the parent stream would carry no
child identity, usage or output. Three distinct plugin routes bypassed a
foreground-only configuration, and all three are now closed by the vendor patch
(`deploy/worker-cli/pi-subagents/vendor/force-foreground.patch`, three files,
seven hunks):

| Route | Plugin decision | Closed by |
|---|---|---|
| Explicit `async: true` | `async-execution.ts` background runner | Rejected at the tool entry with a retry hint (`Background delegation is disabled …`) |
| Single/parallel launch with a default `asyncByDefault` | `executeWithSingleDispatchGuard` | Depth-0 override rewrites the dispatch params |
| `workflowScript` without an explicit `async` | `const asyncWorkflow = requestParams.async !== false` | Depth-0 override applied at the entry of `execute()`, before that branch reads `async` |

The third route was found by a real Task (643): the workflow detached, the parent
stream saw `mode: workflow` with an empty `results` array, and the two children
only surfaced later through a `status` inventory with empty outputs. After the
fix, the same prompt runs in the foreground and both children report their
native usage and final output.

Live evidence on the final artifacts (Kit `a40d66420c10`, Runtime Bundle 262/263):

| Task | Prompt | Observed |
|---|---|---|
| 644 | `workflowScript`, no `async` | 2 delegation rows, per-child usage, outputs carry `marker-alpha` / `marker-beta`, no childless row |
| 645 | `async: true` | One bare `Subagent` row with `error: true` carrying the refusal text, then the model's foreground retry |
| 643 (pre-fix) | `workflowScript`, no `async` | Detached: no child rows, only a bare "async run is detached" row |

### The repository cannot inject agents (verified)

The ceiling alone could not express one restriction the spec requires: agent
definitions, project settings and package-provided subagents are read from the
cloned workspace, so a repository shipping `.pi/agents/*.md` could shadow a
bundled agent, re-enable the plugin's own builtins through `.pi/settings.json`
(`disableBuiltins: false`, `agentScanDirs`, provider/model/thinking overrides,
`defaultExtensions`), or add package agents.

Upstream already documents half of the switch: `agentScope`
(`user | project | both`, default `both`) is a launch parameter that propagates
to workflow children (`docs/agents.md`, `docs/tool-reference.md` in the pinned
package). The ceiling therefore pins every depth-0 launch to
`agentScope: "user"` in the same one-line override that pins `async: false`,
which keeps project and package agent *definitions* out of every launch path.

The other half is not expressible that way, and a live Task proved it: with
`agentScope: "user"` alone, the workspace `.pi/settings.json` still applied —
all four bundled agents came back with `Model: planted-model` and the plugin's
builtins reappeared in the management listing. Project settings supply
`defaultModel`/`defaultProvider`/`defaultThinking`/`defaultExtensions`,
`agentOverrides` and `disableBuiltins`, and they are read outside the launch
scope, so the patch hides that one settings path while the ceiling is active
(`CODIFY_PI_SUBAGENT_ISOLATED`, exported by the Pi adapter).

Measured on the pinned 0.67.0 inside the runtime image, with
`.pi/agents/planted-probe.md` and a project `.pi/settings.json`
(`disableBuiltins: false`, `agentScanDirs: [".pi/agents"]`,
`defaultModel: planted-model`) planted in the task workspace, by calling the
plugin's own `discoverAgents(cwd, scope)`:

| Condition | Result |
|---|---|
| upstream default | 14 agents: `planted-probe(project)` plus every builtin |
| `agentScope: "user"` only | 4 definitions, but all four carry `planted-model` and builtins reappear in the management listing |
| Codify ceiling | 4 agents (`delegate`, `reviewer`, `scout`, `worker`), `Model: inherits current session`, no builtins |

The vendor patch is therefore four files and eight hunks: the documented
`async`/`agentScope` pins, the tool-entry rejection of an explicit background
launch, and the single settings gate.

A launched Task confirms it end to end: the plugin's own `action: "list"` in
that workspace answers with exactly those four names.

Live Task probe on the Kit: with `.pi/agents/opencode-probe.md` and
`.pi/settings.json` (`disableBuiltins: false`, `agentScanDirs: [".pi/agents"]`)
planted in the task workspace, the plugin's own `action: "list"` answered

```text
User agents
- delegate (user) ...
- reviewer (user) ...
- scout (user) ...
- worker (user) ...
```

i.e. exactly the four Codify agents and nothing from the repository.

A refused or management call is projected as exactly one bare `Subagent` tool
row: it keeps the native message and `error` flag, and never fabricates a
delegation. The input is captured from the start record because the plugin's
terminal record repeats only the tool name and result.
