---
title: Delivery Internals
section: User Guide
tier: deep
---

Use this page when a push result is unclear or you need the complete evidence for a run. [Delivery](/guide/50-delivery) covers the routine branch, MR, and statistics flow.

## Publish rule

Publishing compares the remote tip fetched immediately before the push. Codify uses `--force-with-lease`, so it publishes only when the remote is still at that tip. It never falls back to a plain force push. The first publish also asserts that the remote branch does not already exist.

## Push failures

A refused or unconfirmed push fails the Task, but leaves its commits in the workspace.

| Code | Meaning |
|---|---|
| `remote_diverged` | Local and remote histories moved apart |
| `remote_rewound` | The remote no longer contains the run's starting commit |
| `remote_deleted` | The remote branch disappeared during the run |
| `remote_changed` | The remote changed again while the refused push was checked |
| `branch_changed` | The local branch moved during finalization |
| `history_rewritten` | The branch no longer matches its recorded starting point |
| `history_unverifiable` | Local history is too shallow to prove ancestry, so no push was attempted |
| `push_failed` | Push was refused while the remote tip stayed unchanged |
| `remote_unconfirmed` | Codify could not observe the remote state after pushing |

The raw Git error appears beside the result. If the Task failed before committing leftovers, those uncommitted files remain in the workspace and may be included by the next Task. Inspect the working tree before continuing.

## Run archive

After a container exits, Codify seals its run evidence from `/tmp/codify-runtime` into `task-{id}-runtime-archive.tar.gz` and stores it on the control-plane host. The download action appears for **Completed** and **Failed** Tasks and uses the same project permission check as the Task page. Cancelled and timed-out runs can still have archives even when the action is unavailable.

Entries exist only when the run produced them:

| Entry | Contents |
|---|---|
| `event.jsonl` | Normalized stream used by **Events** |
| `harness-events/` | Raw stream for the Harness used by the run |
| `console.log` | Raw container output |
| `harness-result.json` | Harness final result |
| `runtime.json` | Runtime and model details; written by Claude runs |
| `repository-preparation.json` | Repository preparation telemetry |
| `delivery-summary.md` | Delivery summary |
| `delivery-summary-validation.json` | Delivery-summary validation |
| `artifacts-validation.json` | Artifact collection and sealing result |
| `artifacts/` | User artifacts that fit the configured budget |
| `opencode-http-audit.jsonl` | OpenCode HTTP audit records |

The archive excludes the prompt files, artifact policy, scripts, orchestration bundle, timeout marker, repository, workspace mounts, and Harness state directories. It contains only files written into the run scratch directory.

The hard cap, artifact budget, and retention values are in [Platform reference](/guide/96-platform-reference). If the budget or sealing limit is exceeded, Codify omits the user-artifact subtree and records the reason in `artifacts-validation.json`. Archive cleanup uses the archive record's age and never deletes the Task.

When a browser log is truncated, use the archive for the full output. Structured tool payloads may load directly in the process panel; unavailable payloads show **Failed to load payload**.
