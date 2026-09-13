---
title: Delivery
section: User Guide
---

## Branch and commits

Delivery is per Issue, not per Task. Every Task on an Issue commits to the same working branch. The branch is named when the Issue is created and is cut from the Issue's **Starting Branch** when the first run pushes to it. The Branch Config panel on a task names all three roles:

| Role | Label |
|---|---|
| Source | **Base branch** |
| Working | **Working branch** |
| Merge target | **Target branch** |

The working branch is generated as `codify/issue-{id}`, so it is stable for the whole life of the Issue.

Whether the result becomes a Merge Request depends on how the Issue was configured:

- **Will create MR** — the default. Commits are pushed and a Merge Request is opened or updated.
- **No MR** — the Issue was created without **Create Merge Request**, so only the branch is pushed.
- **Direct Push** and **Manual** appear on the branch panel for tasks whose branch flow does not go through the automated MR path.

The **Branch Config** panel names the mode next to the branch roles, so a task's MR intent is visible without opening the Issue.

The **Commit Record** section lists what the Task actually produced. Commits added by the current Task are grouped separately from commits recovered from previous Tasks, so a re-run that finds earlier uncommitted work does not silently claim it:

- **This task commits ({count})** — commits created by this run.
- **Previous task commits ({count})** — commits from earlier runs that were picked up.
- Each row shows its **Commit** SHA along with the message.

Push state is reported honestly rather than optimistically:

| State | Meaning |
|---|---|
| **Pushed** | The branch was pushed successfully |
| **Already on remote** | The commits were already present remotely |
| **Nothing to deliver** | The run produced no new commits |
| **Push not attempted** | Delivery was not reached |
| **Delivery failed — not confirmed** | The push failed and delivery is not confirmed |

## Merge request

One Merge Request serves the whole Issue. Codify creates it as a draft MR when the branch first needs one, labelled `Codify`, authored as the requester, and updated with the run summary afterwards.

The **Task overview** panel carries the Merge Request state for the Issue:

- Once the MR exists, the **Merge Request** row links to it and shows `!{iid}`.
- Before it exists but a merge target is set, the row reads **Will create MR** followed by the target branch.
- When the Issue has no merge target configured, the row reads **No MR**.

The **Branch Config** row above it names **Base branch**, **Working branch**, and **Target branch**, and marks the mode as **Will create MR**, **No MR**, **Direct Push**, or **Manual**.

Each subsequent Task updates the same MR instead of opening a new one, and its description carries a per-task table of status, commit message, and change line counts, plus the Issue context. A failed delivery is marked as such in the MR body rather than being presented as a normal commit.

Closing the loop is automatic in both directions:

- When the tracked MR is merged, the Issue is closed by webhook. The Issue records this as **Closed Via** / **Auto-closed (MR Merged)**, as opposed to **Manually Closed** or **Auto-closed (Worker Profile disabled)**.
- When the Issue is closed, the working branch is deleted — unless the Issue was configured to keep it. The toggle is described in the Issue's advanced settings as: the AI working branch will be deleted when an MR merge webhook auto-closes this issue, or will be kept. Badges read **Webhook auto-close deletes branch** and **Webhook auto-close keeps branch**.

Closing an Issue by hand asks first, and gives you the branch choice explicitly: **Close and Keep Branch** or **Close and Delete Branch**, with the prompt naming the branch. A branch can also be deleted from the Issue page with **Delete Branch** after confirmation; an already deleted branch reports **Branch already deleted**.

**MR pipeline failure auto-repair** is opt-in per Issue. When enabled, Codify creates a repair task if the tracked MR pipeline fails; when disabled, pipeline failures are still recorded but no repair task is created automatically. The Issue page tracks this under **CI Automation** with the pipeline, repair tasks, failed jobs, and the processing timeline. Auto-created repair tasks are capped per MR; once the cap is reached, further failures are recorded as **Max attempts reached** and ignored.

## Change and usage statistics

Statistics answer two different questions: how much code changed, and what it cost.

Change statistics come from the Git delivery record:

| Field | Label |
|---|---|
| Lines added | **Additions** |
| Lines removed | **Deletions** |
| New files | **{count} new file(s)** |
| Modified files | **{count} modified file(s)** |
| Deleted files | **{count} deleted file(s)** |

A run that changed nothing reports **No net file changes**; a run whose statistics could not be collected is marked **Change stats not collected** rather than showing zeros. The Issue overview aggregates the same data across its Tasks as **Changes** — with `+additions` and `-deletions` detail — alongside **Total Duration** and a combined **Tokens** figure.

Token usage is captured per Task as input and output tokens. The **Run Statistics** panel on the Task Result shows a **Token Usage** total with **Input** and **Output** breakdowns. Analytics adds derived metrics over a time window:

- **Total Tokens**, annotated as `In {input} / Out {output}` for the tasks that reported token data.
- **Avg Tokens / Task** across tasks that have token data, with **Max {value}**.
- **Avg Tokens / Sec** — computed from output tokens only, so it is not directly comparable with the other token metrics.
- **Avg Tokens / Changed Line** and **Avg Sec / Changed Line**.

Statistics only ever describe work that finished. Tasks still running are excluded from the finished-task aggregates, and the finished-task line breaks them down as completed, failed, and cancelled.

## Run archive

The **Runtime Archive** panel on a Task offers **Download runtime archive** — a gzip archive with the run's artifacts. Its description states exactly what is inside: console.log and repository-preparation.json always, and event.jsonl plus runtime.json for runs that reached AI execution.

Practical notes:

- The archive is assembled for completed runs. If the run failed before producing files, the download reports that no archive is available.
- Archives expire. Once cleanup has removed the file, the panel shows **File expired** and explains that the runtime archive file has been cleaned up and is no longer available for download. The Task itself is never deleted by archive cleanup.
- The archive is the authoritative source for logs too: when the browser truncates a very large log, the panel points you here for the complete output.

If the same file is available as a structured payload — for example a tool call's input or output — the process panel can load it directly; that path reports **Failed to load payload** when the payload is no longer retrievable, and indicates loading state while an archived payload is fetched.
