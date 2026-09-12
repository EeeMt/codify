# Codify Runtime Bundle: pinned `pi-subagents`

Upstream: [`pi-subagents`](https://github.com/nicobailon/pi-subagents) `0.67.0`,
MIT. This directory is the **pin + policy** record; the extension itself is
installed from the pinned npm tarball at Kit build time
([`install.sh`](install.sh), lockfile-pinned, `--ignore-scripts`). Nothing here
is fetched or installed while a Task runs.

```
pin.json          audited artifacts: version, integrity, tarball sha256, entry
package.json      exact dependency pin (pi-subagents 0.67.0)
package-lock.json resolved closure, the actual install input
config.json       Codify capability ceiling (plugin config)
settings.json     Pi settings fragment: builtins disabled, no scan dirs
agents/*.md       the only four agent definitions the ceiling opens
LICENSE.pi-subagents  upstream MIT license
install.sh        build-time install into the Kit payload
```

## Status: wired, with one bounded vendor patch

`pi-run.sh` loads this extension with `--no-extensions -e <payload>` whenever the
Kit ships it, the adapter applies the ceiling into the Pi CLI home, and
`pi_events.py` projects the `subagent` tool as per-child delegation rows.

`vendor/force-foreground.patch` is the only deviation from upstream, and it has
two parts:

1. a depth-0 override that rewrites a launch to the foreground path, and
2. a hard guard at the tool entry that **rejects** `async: true` at depth 0 with
   a message telling the model to retry without it.

The guard exists because a Model-chosen async launch was still observed after
(1) alone — the workflow dispatch has its own detached route. Verified on the
Kit payload: `async: true` → rejected; the model retries with `async: false` →
foreground run with 2 children and 2 results in the tool payload. No async
launch can therefore originate from a Codify Task.

For reference, the failure mode the patch removes: an async launch returns an
**empty** child inventory (probe: `mode: workflow`, `children: []`,
`results: []`), so the parent stream would carry no child identity, usage or
tool trace at all.

## Probe evidence (target Worker environment, 2026-09-12)

Probe: Pi `0.84.2` (Kit payload) + `pi-subagents 0.67.0`, RPC mode, real
OpenAI/Anthropic-compatible Provider, one root asking for a two-child
`workflowScript` fan-out.

| Observation | Result |
|---|---|
| Extension load on `0.84.2` | loads; `subagent` tool registered and callable |
| Peer versions in the pinned closure | `pi-server 0.85.0`, `pi-ai/pi-agent-core 0.85.1` |
| Delegation API | `workflowScript` with `runs.run` / `runs.all`; top-level `chain`/`tasks`/`parallel` are unsupported |
| Ceiling enforced | spawn budget reported `2/4 used, 4 remaining` (config `maxSubagentSpawnsPerSession`/`PerRun = 4`) |
| Codify agents used | the four bundled definitions resolved; children ran their assigned commands and returned `marker-alpha` / `marker-beta` |
| Child identity | run ids / child processes owned by the plugin, surfaced through tool results |
| `asyncByDefault: false` | **did not** make a `workflowScript` call block: the tool returned "the async run is detached and running in the background" |

## Settled semantics (probe, both paths)

`agent_settled` is not emitted while background subagent work is pending. Two
probes with the ceiling applied:

| Launch | Behaviour |
|---|---|
| foreground (`async: false`, or the patched default) | tool blocks ~7.6 s, returns both markers inline, then `agent_settled` |
| async, before the patch | tool returns "detached", `bg_wait` is disabled by the ceiling, the model polls `subagent status`, and `agent_settled` still arrives **after** both children finished |

So a child can never end the Task, which is what §5.5 requires. The patch is
needed for *observability* (child identity/usage/tool trace in the tool result),
not for terminal safety.

## Unresolved before `subagents: true`

1. **Cancel convergence.** No probe yet proves that cancelling the parent turns
   every spawned child process tree into a terminated one (§8, §10.6).
2. **Model-protocol coverage.** Only `anthropic_messages` was exercised end to
   end; `openai_responses` and `openai_chat_completions` still need a real Task.
3. **Usage authority.** `usage.final` must be shown to match the provider total
   with children present (§5.6); the child detail is currently display-only.
