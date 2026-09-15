---
title: Harness Support
section: User Guide
tier: deep
---

## What a Harness is

A Harness is the coding-agent CLI that runs a Task inside a Worker container.

| Key | Display name |
|---|---|
| claude | Claude |
| codex | Codex |
| pi | Pi |
| opencode | OpenCode |

Each key has an adapter and uses the v2 contract family: `codify.worker.harness/v2` for the Harness, plus v2 contracts for events, results, and commands. The current execution mode is v2 only, so a v1 bundle is readable but cannot run.

The adapter resolves the CLI from `CODIFY_HARNESS_CLI_BIN` or the Worker Kit manifest. If neither provides it, runtime verification fails with `<X> CLI is not available from the Worker Kit inventory`. A Profile records whether the binary comes from the Worker Kit or an absolute read-only host mount. Host-mounted binaries must declare the v2 contract and may pin a version and digest.

## What every Harness shares

Task Mode is independent of the Harness: **Implementation**, **Analysis**, and **Freeform** correspond to execute, plan, and freeform. Session mode is **Continue** or **Fresh**, and a continued Task must keep the Harness that owns the session.

All four Harnesses support session resume and Task Skills. Each adapter puts Skills in the location expected by its CLI. All four report final usage through `usage.final`, which supplies input and output token totals; cost is not stored on the Task.

Timeout, scheduling, the per-Issue mutex, and Git delivery are shared. The failure vocabulary is also shared: `configuration_error`, `authentication_error`, `rate_limited`, `sandbox_error`, `protocol_error`, `timeout`, `cancelled`, `engine_error`, `crash`, and `settled_race`.

## Where the Harnesses differ {core}

| Harness | Protocols | Steering / follow-up | Session resume | Skills | Max turns |
|---|---|---|---|---|---|
| Claude | anthropic_messages | No | Yes | Yes | Enforced |
| Codex | openai_responses | No | Yes | Yes | Not enforced |
| Pi | All three | Yes | Yes | Yes | Not enforced |
| OpenCode | All three | No | Yes | Yes | Not enforced |

Steering and follow-up are currently available only for Pi. The frozen bundle's capability flags control whether its command panel appears. A command accepted by the interface may still be waiting for the model to consume it.

Claude is the only Harness that exports the helper used for model-written commit messages and MR summaries. Codex, Pi, and OpenCode use the fixed commit-message fallback; they keep the previous MR summary where applicable. **Max Turns** reaches the Claude CLI only.

### State, sessions, and Skills

Session state is namespaced by Harness. A session id cannot move from one Harness to another.

| Harness | State kept across Tasks | Skill location during a run |
|---|---|---|
| Claude | /home/codify/.claude on the Issue mount | Read from the Task snapshot through --add-dir |
| Codex | CODEX_HOME on /opt/codify-issue-shared/codex-home | CODEX_HOME/.agents/skills |
| Pi | PI_HOME on /opt/codify-issue-shared/pi-home/sessions | /home/codify/.pi/agent/skills |
| OpenCode | XDG_DATA_HOME on /opt/codify-issue-shared/opencode-data | Per-run config, checked with opencode debug skill --pure |

See [Worker Runtime](/guide/92-worker-runtime) for the complete directory map.

## Model protocol pairing

| Harness | Accepted protocols |
|---|---|
| Claude | anthropic_messages |
| Codex | openai_responses |
| Pi | anthropic_messages, openai_responses, openai_chat_completions |
| OpenCode | anthropic_messages, openai_responses, openai_chat_completions |

Provider Kind and Wire Protocol must match:

| Provider Kind | Wire Protocol | Compatible Harnesses |
|---|---|---|
| anthropic_compatible | anthropic_messages | Claude, Pi, OpenCode |
| openai_compatible | openai_responses | Codex, Pi, OpenCode |
| openai_compatible | openai_chat_completions | Pi, OpenCode |

The API rejects a mismatched pair when the Provider is saved. If no enabled Provider speaks the protocol required by a Harness, task creation reports that condition.

## Harness-specific options

Options live in `harness_options` on the Worker Profile. A Task can override only the supported subset.

| Harness | Options |
|---|---|
| Codex | `reasoning_effort`: minimal, low, medium, high, xhigh, ultra |
| Pi | `thinking_level`; `steering_mode` and `follow_up_mode`: one-at-a-time |
| OpenCode | `agent`: build, plan, general, explore; `command`: codify; `model_variant`: up to 64 characters |

Profiles may also constrain `max_turns`, `sandbox_mode`, `network_enabled`, and `timeout_seconds`. OpenCode's Agent, Command, and Model variant are pinned in the Task snapshot and checked against the allowlist.

## Availability and versions

A Harness is usable only when its payload exists, the Profile enables it, and runtime verification passes. The Kit manifest reports a key outside the selected CLI set as absent/not_selected and a selected key without a payload as absent/missing_payload. Payloads are checked by size and SHA-256.

The Profile lists enabled Harnesses and a Default Harness. Runtime verification reports each selected key as available or unavailable and records the reason. Task creation also checks the frozen Profile and Provider compatibility.

The accepted ranges in the current manifest are:

| Harness | Accepted range | Enforcement |
|---|---|---|
| Claude | >=2.1.33 <3.0.0 | The adapter enforces the 2.1.33 floor |
| Codex | >=0.146.0 <0.160.0 | Warning |
| Pi | >=0.84.2 <0.85.0 | Warning |
| OpenCode | >=1.18.19 <1.19.0 | Warning |

Use the Worker validation result and Task snapshot when diagnosing a particular run; the Profile can change after the Task was created.

## What changes in the interface {core}

- The **Harness** selector shows availability and the reason. A continued Task must reuse its frozen Harness; switching requires a fresh session.
- The live command panel follows the frozen steering and follow-up capabilities, so it appears only for supported runtimes.
- Commit records and MR summaries follow the Harness's result helper. Claude can supply model-written text; the other three use the fallback rules above.
- Failure types use the shared vocabulary, while each adapter maps its own CLI signals into it.
