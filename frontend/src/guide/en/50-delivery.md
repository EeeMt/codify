---
title: Delivery
section: User Guide
---

## Branch and commits

![One branch; with or without an MR, the Issue still closes](assets/diagrams/en/delivery-path.svg)

> [!route] **Delivery principle**: every turn on an Issue shares one working branch. The MR switch changes how the result is delivered; execution and commits run the same either way.

The working branch is named `codify/issue-{id}`, where `id` is Codify's internal Issue id, not the GitLab issue IID. The name is stored on the Issue once and passed into every container of that Issue, so all of its Tasks share it.

Nothing creates the branch in advance. The worker creates it locally on the first run that needs it: it checks out the local branch when one exists, otherwise a branch of that name from the remote, otherwise a new branch from the base branch. The branch appears on the remote only when the first successful publish creates it. The base branch is the Issue's **Starting Branch** when it has one, otherwise the target branch, otherwise the project's default branch.

The **Branch Config** panel on a task names three roles:

| Role | Label |
|---|---|
| Source | **Base branch** |
| Working | **Working branch** |
| Merge target | **Target branch** |

One Issue owns one branch and one workspace. Every Task commits to that branch, and a later Task picks up the checkout the previous Task left behind instead of cloning the repository again, so it starts from those commits. The workspace persists between Tasks, including uncommitted work a previous Task left behind. Tasks in **Analysis** mode discard their changes instead of committing them, and such a Task still completes successfully.

You and Codify write to the same branch. If you push your own commits to the working branch, the next Task fast-forwards onto them and builds on top; it never rewrites or rebases history. Preparation refuses instead of overwriting when the remote branch moved while the persistent workspace still holds uncommitted changes, and it refuses as well when the two histories have diverged or the remote branch was rewound. Reconcile the branch in GitLab so that the remote matches the workspace, or continue the work from a new Issue, whose workspace starts fresh.

The **Commit Record** section lists what the Task produced. Commits added by the current Task are grouped separately from commits recovered from previous Tasks, so a re-run that finds earlier uncommitted work does not claim it as new:

- **This task commits ({count})**: commits created by this run.
- **Previous task commits ({count})**: commits from earlier runs that were picked up.
- Each row shows its **Commit** SHA along with the message.

Publishing is a compare-and-swap against the remote tip the run observed. The push carries `--force-with-lease`, so the branch moves only if it is still where the run last saw it; a plain force push is never used. The first publish asserts that the branch does not exist yet.

The push result is recorded as one of:

| State | Meaning |
|---|---|
| **Pushed** | The branch was pushed successfully |
| **Already on remote** | The commits were already present remotely |
| **Nothing to deliver** | The run produced no new commits |
| **Push not attempted** | Delivery was not reached |
| **Delivery failed — not confirmed** | The push failed and delivery is not confirmed |

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

The raw error text appears next to the result verbatim, so it is not translated. A Task that fails before the worker commits its leftovers leaves that dirty worktree behind: the next turn starts with those files still in the workspace and may commit them along with its own change, so the next Task's diff can include work it did not produce.

Whether the result becomes a Merge Request depends on how the Issue was configured:

- **Will create MR**: the default. Commits are pushed and a Merge Request is opened or updated.
- **No MR**: the Issue was created without **Create Merge Request**, so only the branch is pushed.
- **Direct Push** and **Manual** appear on the branch panel for tasks whose branch flow does not go through the automated MR path.

The **Branch Config** panel names the mode next to the branch roles, so a task's MR intent is visible without opening the Issue.

## Merge request

One Merge Request serves the whole Issue. Codify creates it as a draft MR when the branch first needs one, labelled `Codify`, authored as the requester, and updated with the run summary afterwards.

The **Task overview** panel carries the Merge Request state for the Issue:

- Once the MR exists, the **Merge Request** row links to it and shows `!{iid}`.
- Before it exists but a merge target is set, the row reads **Will create MR** followed by the target branch.
- When the Issue has no merge target configured, the row reads **No MR**.

The **Branch Config** row above it names **Base branch**, **Working branch**, and **Target branch**, and marks the mode as **Will create MR**, **No MR**, **Direct Push**, or **Manual**.

Each subsequent Task updates the same MR instead of opening a new one, and its description carries a per-task table of status, commit message, and change line counts, plus the Issue context. A failed delivery is marked as failed in the MR body.

Both directions are automatic:

- When the tracked MR is merged, the Issue is closed by webhook. The Issue records this under **Closed Via** as **Auto-closed (MR Merged)**, **Manually Closed**, or **Auto-closed (Worker Profile disabled)**.
- When the Issue is closed, the working branch is deleted unless the Issue was configured to keep it. The Issue's advanced settings describe the toggle as: the AI working branch will be deleted when an MR merge webhook auto-closes this issue, or will be kept. Badges read **Webhook auto-close deletes branch** and **Webhook auto-close keeps branch**.

Closing an Issue by hand asks first and offers the branch choice: **Close and Keep Branch** or **Close and Delete Branch**, with the prompt naming the branch. A branch can also be deleted from the Issue page with **Delete Branch** after confirmation; an already deleted branch reports **Branch already deleted**.

**MR pipeline failure auto-repair** is opt-in per Issue. When enabled, Codify creates a repair task if the tracked MR pipeline fails; when disabled, pipeline failures are still recorded but no repair task is created automatically. The Issue page tracks this under **CI Automation** with the pipeline, repair tasks, failed jobs, and the processing timeline. Auto-created repair tasks are capped per MR; once the cap is reached, further failures are recorded as **Max attempts reached** and ignored.

## Change and usage statistics

Statistics answer two questions: how much code changed, and what it cost. Change statistics come from the Git delivery record:

| Field | Label |
|---|---|
| Lines added | **Additions** |
| Lines removed | **Deletions** |
| New files | **{count} new file(s)** |
| Modified files | **{count} modified file(s)** |
| Deleted files | **{count} deleted file(s)** |

A run that changed nothing reports **No net file changes**; a run whose statistics could not be collected is marked **Change stats not collected** instead of showing zeros. The Issue overview aggregates the same data across its Tasks as **Changes** (with `+additions` and `-deletions` detail), alongside **Total Duration** and a combined **Tokens** figure.

Token usage is captured per Task as input and output tokens. The **Run Statistics** panel on the Task Result shows a **Token Usage** total with **Input** and **Output** breakdowns. Analytics adds derived metrics over a time window:

- **Total Tokens**, annotated as `In {input} / Out {output}` for the tasks that reported token data.
- **Avg Tokens / Task** across tasks that have token data, with **Max {value}**.
- **Avg Tokens / Sec**: computed from output tokens only, so it is not directly comparable with the other token metrics.
- **Avg Tokens / Changed Line** and **Avg Sec / Changed Line**.

Statistics cover finished work only. Tasks still running are excluded from the finished-task aggregates, and the finished-task line breaks them down as completed, failed, and cancelled.

## Run archive

The **Runtime Archive** panel on a Task offers **Download runtime archive**: a gzip tar of the run's evidence, named `task-{id}-runtime-archive.tar.gz`. The container seals it from the run's scratch directory `/tmp/codify-runtime` as the run exits, so every terminated run produces one, whether it completed, failed, was cancelled, or timed out. The backend then streams the sealed file into the archive store on the control-plane host, `/opt/codify-archives`. Nothing is available to download while the Task is still running.

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

The panel's description names the common subset: console.log and repository-preparation.json, plus event.jsonl and runtime.json for runs that reached AI execution.

The rest of the run's scratch files stay out: the prompt files, the artifact policy, the pre and post scripts, the orchestration bundle, and the timeout marker. Neither the workspace nor the Git repository is packaged, and neither are the Harness state directories on the `claude/` and `shared/` mounts; the archive only carries what the run wrote into its own scratch directory.

The archive has a hard cap of 640 MiB. When sealing fails, or when adding `artifacts/` would push the archive past the cap, that subtree is omitted and `artifacts-validation.json` records the omission and the reason. The artifact budget applied while sealing defaults to 200 MiB in total, 100 MiB per file, and 5,000 entries, and an administrator can change those values.

Notes:

- Archives are kept for 30 days by default, counted from the age of the archive's record rather than of the file. Once cleanup has removed the file, the panel shows **File expired** and explains that the runtime archive file has been cleaned up and is no longer available for download. The Task itself is never deleted by archive cleanup.
- The archive also holds the full logs: when the browser truncates a very large log, the panel points you here for the complete output.

If the same file is available as a structured payload (for example a tool call's input or output), the process panel can load it directly; that path reports **Failed to load payload** when the payload is no longer retrievable, and shows a loading state while an archived payload is fetched.
