---
title: Concepts
section: User Guide
---

## Issue

An Issue is a persistent requirement container. It owns the workspace, the AI conversation session, and one branch with a single Merge Request lifecycle. Tasks run under the Issue; you cannot run work on an Issue directly.

An Issue is created from **Create Issue** with a project, a starting branch, and a merge target. Its description is stored separately from any task prompt, and it is used as the default prompt when you create the first Task.

> [!info] **A useful mental model**: the Issue is the container, the Task is a turn; the workspace, session, and branch belong to the Issue, while the snapshot and run archive belong to the Task.

| Field | Label in the UI | Meaning |
|---|---|---|
| Title | **Title** | Shown as the Merge Request title later |
| Description | **Description** | Default task prompt and requirement context |
| Project | **Project** | The GitLab project the work targets |
| Source branch | **Starting Branch** | The branch the working branch is cut from |
| Target branch | **Merge Target** | The branch the Merge Request merges into |
| Branch | **Branch** | The AI working branch, generated as `codify/issue-{id}` |
| Creator | **Initiator** | Who owns the Issue and its tasks |

Issues move through four statuses: **Open**, **In Progress**, **In Review**, and **Closed**. Codify sets **In Progress** automatically when a Task on the Issue starts running, and closes the Issue when the tracked Merge Request is merged by webhook.

Every Task on an Issue executes in strict order. Priority and scheduled time arbitrate between different Issues only; they never reorder the turns of a single Issue. Because of that ordering, a follow-up Task is safe to create: it always sees the workspace its predecessor left behind.

## Task and turn

A Task is one round of execution, called a *turn*, in an Issue's ordered stream. Codify allocates the turn number when the Task is created and lists it in creation toasts as `turn #{sequence}`.

A Task carries the fields you set at creation plus the execution identity Codify freezes for it:

| Group | Fields |
|---|---|
| Input | User prompt, Run Instruction template, Task Mode, **Require Changes** |
| Scheduling | Priority, scheduled time, turn number |
| Execution | Worker snapshot, runtime bundle, AI Provider, Harness |
| Session | Session mode (`Continue session` or `Fresh session`), lineage generation |
| Outcome | Status, failure reason, commits, change and token statistics, Merge Request |

Task statuses are **Pending**, **Queued**, **Running**, **Completed**, **Failed**, and **Cancelled**. The status vocabulary is shared across the Dashboard, the task table, Monitor, and Analytics, so a task called `Queued` on one page is in the same state everywhere.

Trigger sources describe where a Task came from: a manual creation, a **Retry**, a **Follow-up**, or a **CI auto-repair**.

## Harness

The Harness is the coding agent CLI that performs the work inside the container. Codify does not run the model itself. It prepares a workspace, renders a prompt, and hands both to a Harness.

Each Harness has an adapter, a wire protocol, and a capability policy. The capability policy decides what a live run accepts: **steering** and **follow-up** commands are gated per Harness, so the steering controls on a task page are enabled only when the frozen runtime supports them.

Harness names appear directly on the task pages: **Claude**, **Codex**, **Pi**, and **OpenCode** are options in the task form and in the task metadata panel. Which ones your platform can run depends on the Worker Profile and the configured AI Providers.

A Task's Harness is part of its execution identity. Continue-session tasks must reuse the current Harness; to switch Harness you create a Task with **Run in a new session**.

## Workspace, session, and branch

Three things persist across the Tasks of one Issue, and they are the reason appending a follow-up Task is cheap:

- **Workspace**: the checked-out repository. Codify keeps a per-Issue workspace so a follow-up Task does not clone from scratch. Stale workspaces are cleaned up on a retention schedule.
- **Session**: the Harness conversation. Each Task records an input session and an output session, so a follow-up continues the same conversation instead of starting cold. `Continue session` inherits the current lineage; `Run in a new session` starts a new generation while keeping the workspace, branch, and history.
- **Branch**: one working branch per Issue, generated as `codify/issue-{id}` from the Issue's **Starting Branch**. Every Task commits to that branch, and the Merge Request targets the Issue's **Merge Target**.

Because all three are shared, appended tasks continue from where the previous task left off, which is what the appended-task hint states.

## Task snapshot and runtime bundle

Creating a Task does not bind it to the Worker Profile as it stands at execution time. Codify resolves the profile at creation instead and freezes an immutable **Task snapshot** that records the execution identity: the Worker Profile it resolved, the Harness and its constraints, the enabled skills, and the run-instruction defaults.

Alongside the snapshot, the Task is bound to a content-addressed **Runtime Bundle**, an immutable artifact identified by digest. The run loads the frozen bundle and the snapshot, so nothing changes underneath a Task that is already running.

This has several consequences:

- Editing a Worker Profile does not affect Tasks that already exist.
- A **Retry** reuses the frozen snapshot and the session lineage, so a retry runs exactly the configuration of the Task it retries.
- Secret values are never returned to the browser; the runtime summary panel reports configured status only.
- If the frozen runtime is not available when the Task is about to run, the Task stays **Pending** and reports that scheduling is blocked until an administrator restores and rechecks it.

## Delivery artifacts

A finished Task produces more than a status change:

| Artifact | Where it appears |
|---|---|
| Commit record | **Commit Record** on the Task Result panel, with commit SHAs and messages |
| Branch and push state | Delivery line: pushed, already on remote, nothing to deliver, or delivery failed |
| Merge Request | **Merge Request** with title, URL, and created/pending/no-MR state |
| Change statistics | Additions, deletions, and new / modified / deleted file counts |
| Token usage | Input and output tokens consumed by the run |
| Delivery summary | AI-written Markdown summary, rendered with Mermaid diagrams where used |
| Run archive | A downloadable gzip archive of the container's runtime files |

Artifacts are per Issue as well as per Task: all Tasks deliver to one branch and one Merge Request, and the Issue page aggregates them into a **Delivery Overview**.

## Object model

Six objects carry a piece of work through Codify. All of them belong to the Issue you create at the start.

![One Issue owns the workspace, the branch and all its tasks](assets/diagrams/en/object-model.svg)

- **Issue**: the requirement container. It owns the workspace, the AI conversation session, and one branch with a single Merge Request lifecycle.
- **Task**: one ordered turn of an Issue. An Issue can have as many Tasks as you append, and they run strictly in turn order.
- **Branch**: one working branch per Issue, generated as `codify/issue-{id}`. Every Task commits to that branch, which is what lets a follow-up Task continue where its predecessor stopped.
- **Merge Request**: one per Issue, created from that branch and targeting the Issue's **Merge Target**. Merging it is what closes the Issue.
- **Task Snapshot**: the configuration frozen when the Task is created, so later edits never change a Task that already exists.
- **Run archive**: one per Task, kept so you can inspect afterwards what a run produced.

None of these belongs to a single run: the Issue is where the branch, the Merge Request, and the aggregated **Delivery Overview** come together.
