---
title: Delivery Internals
section: User Guide
tier: deep
---

This chapter covers what Codify does between a run's last commit and the remote branch, along with what a finished run leaves behind. It explains the remote state used for comparison, the codes a rejected push can return, and the contents and retention of the run archive. Read it when a push code does not make the next step clear or when you need the complete logs. [Delivery](/guide/50-delivery) covers the branch, Merge Request, change statistics, and usage statistics used in routine work.

## Publish rule

Publishing is a compare-and-swap against the remote tip the run fetches immediately before the push. The push carries `--force-with-lease`, so the branch moves only if it is still where that fetch saw it, and Codify never falls back to a plain force push. The first publish asserts that the branch does not exist yet.

## Push failures

A refused or unconfirmed push fails the Task, and the commits stay in the workspace. The failure carries one of these codes:

| Code | Meaning |
|---|---|
| `remote_diverged` | The remote branch moved so that neither side contains the other, so Codify refuses instead of merging |
| `remote_rewound` | The remote branch no longer contains the commit the run started from |
| `remote_deleted` | The branch was deleted on the remote after the run started |
| `remote_changed` | The push was refused and the remote tip had changed again by the time it was rechecked |
| `branch_changed` | The local branch moved while the run was finalizing |
| `history_rewritten` | The branch history no longer matches the recorded starting point |
| `history_unverifiable` | Ancestry could not be proven locally, usually because the clone is shallow, so no push was attempted |
| `push_failed` | The push was refused and the remote tip was unchanged |
| `remote_unconfirmed` | The remote state could not be observed after the push, so delivery is not confirmed |

The raw error text is shown next to the result verbatim and is not translated. When a Task fails before the worker commits its leftovers, those files stay in the worktree: the next turn starts with them still in the workspace and may commit them along with its own change, so the next Task's diff can include work it did not produce.

## Run archive

**Download runtime archive** in the **Actions** area of a task hands you a gzip tar of the run's evidence, named `task-{id}-runtime-archive.tar.gz`. The container seals it from the run's scratch directory `/tmp/codify-runtime` as the run exits, so every terminated run produces one, whether it completed, failed, was cancelled, or timed out. The backend then streams the sealed file into the archive store on the control-plane host, `/opt/codify-archives`. Only **completed** and **failed** Tasks show the control, and the download request is checked against the same project access as the task page.

Entries are added only when the run produced them, so an early exit yields a shorter archive:

| Entry | Contents |
|---|---|
| `event.jsonl` | Normalized event stream, the source of the **Events** tab |
| `opencode-http-audit.jsonl` | HTTP audit records, produced by OpenCode runs only |
| `harness-result.json` | Final result reported by the harness |
| `runtime.json` | Runtime information, including the model actually used; the Claude runner writes it, so other Harnesses leave it out |
| `console.log` | Raw container console output |
| `delivery-summary.md` | Delivery summary |
| `delivery-summary-validation.json` | Delivery summary validation result |
| `repository-preparation.json` | Repository clone and preparation telemetry |
| `artifacts-validation.json` | Artifact collection and sealing validation result |
| `harness-events/` | The raw event stream of this run's Harness, named `claude.jsonl`, `codex.jsonl`, `pi.jsonl`, or `opencode.jsonl`. `claude.jsonl` is created for every run and stays empty unless Claude ran |
| `artifacts/` | The run's user artifacts, sealed and copied as they are |

The button's tooltip lists the common entries: `console.log` and `repository-preparation.json`, plus `event.jsonl` and `runtime.json` for runs that reached AI execution.

The rest of the run's scratch files stay out: the prompt files, the artifact policy, the pre and post scripts, the orchestration bundle, and the timeout marker. Neither the workspace nor the Git repository is packaged, and neither are the Harness state directories on the `claude/` and `shared/` mounts; the archive only carries what the run wrote into its own scratch directory.

The hard cap, default artifact budget, and adjustable range are collected in [Platform reference](/guide/96-platform-reference). When sealing fails, or when adding `artifacts/` would push the archive past the cap, Codify leaves that subtree out and records the omission and its reason in `artifacts-validation.json`.

Notes:

- Archives follow the retention setting in Configuration; the default is collected in [Platform reference](/guide/96-platform-reference). Cleanup uses the archive record's age, not the file's age. Once the file is removed, the header's **Download runtime archive** control is disabled and the actions card reports **File expired**. Archive cleanup never deletes the Task itself.
- The archive also holds the full logs: when a log is too large for the browser to render in full, the log panel points you to the archive for the complete output.

If the same file is available as a structured payload (for example a tool call's input or output), the process panel can load it directly. When the payload is no longer retrievable the panel reports **Failed to load payload**, and it shows a loading state while it fetches an archived payload.
