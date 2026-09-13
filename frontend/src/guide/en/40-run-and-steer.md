---
title: Running and Steering
section: User Guide
---

## Task lifecycle

A Task moves through a small state machine. The task page names each state and explains what to do in it.

![Task lifecycle](assets/diagrams/en/task-lifecycle.svg)

| State | Title on the task page | What it means |
|---|---|---|
| **Pending** | Task is waiting to run | The task is ready and will enter the scheduling queue at its scheduled time or when run immediately |
| **Queued** | Task is waiting for a worker | The task is eligible to run and will start automatically when concurrency capacity is available |
| **Running** | A worker is executing the task | The event stream updates continuously. Use raw logs to investigate container or runtime problems |
| **Completed** | Task completed | The execution outcome, commit record, and delivery summary are available |
| **Failed** | Task failed | Review the failure and event stream before choosing an immediate or scheduled retry |
| **Cancelled** | Task cancelled | Execution stopped. Existing events and logs remain available for diagnosis or retry |

A Queued Task that is not the head of its Issue reports its position instead of pretending to be ready: **Queued #{position} · waiting for Task #{blockedBy}**, **Queue head · waiting for scheduled time**, or **Queue head · waiting for worker**. If the Worker runtime could not be verified, the Task stays pending under **Cannot schedule: Worker runtime unavailable** until an administrator restores and rechecks the runtime or the Task is cancelled.

Every action is gated by permission and by state: only admins or the task owner can run actions for a task, and other users can review the details but cannot operate it.

## Live process log

The **Task Process** panel is where you watch a run. While the task is active the header carries a **Real-time** tag, an elapsed timer, and the **Container** in use. Two tabs split the data:

| Tab | Content |
|---|---|
| **Events** | The structured stream: assistant text, thinking blocks, tool calls with their captured inputs and outputs, context compaction markers, and subagent groups |
| **Raw Logs** | The raw container output, used to investigate container or runtime problems rather than to follow the work |

Empty states explain themselves. **Task not started** appears while the task is still pending or queued, **No events yet** when a run produced no structured events, and **No logs available** when nothing was captured at all.

Details worth knowing while reading a run:

- Thinking blocks are labelled **Thinking** while in progress, with an elapsed time, and **Thinking interrupted** if the model was cut off mid-thought.
- Subagent rows are tagged **Subagent · {name}** and report **Running**, **Completed**, **Failed**, or **Cancelled**, each with its own **{count} tokens**.
- Tool calls show their captured input and output; content that had to be fetched from the archive reports **Loading archived input…** or **Loading archived output…**, and missing content is labelled **No input captured**, **No output captured**, or **Failed to load payload**. **Full text** expands a truncated value.
- Context compaction is marked inline as **Context compressed**, and summarised as **Context Compression** with a count of how many times it happened.
- **Skill Usage** reports how many times managed skills were used in the run.
- Navigation buttons jump to the top or the latest entry, which matters once a long run has scrolled well past the interesting part.

Very large logs are truncated in the browser: only the latest output is shown, and the panel tells you to download the run archive after completion for the complete logs.

## Steering a running task

**Live steering** sends a command into a Task that is already running, without cancelling it. Two command types are offered:

| Type | Label | Purpose |
|---|---|---|
| Steer | **Steer** | Send a mid-run instruction to the harness, with the placeholder "Send a mid-run instruction to the harness..." |
| Follow-up | **Follow-up** | Queue the next instruction to be consumed when the current turn is done |

Each type is enabled only when the frozen runtime supports it. A Harness that does not advertise steering leaves **Steer** disabled; one that does not support follow-ups leaves **Follow-up** disabled. When neither is supported, the panel hides its send controls.

Commands are queued and tracked rather than fired blind. A command reports one of these delivery states:

- **Queued** — accepted by Codify, not yet sent.
- **Dispatching** — being handed to the harness.
- **Harness accepted** — the interface acknowledged the command.
- **Rejected** — refused, with **Reason: {message}**.
- **Outcome unknown** — Codify could not confirm delivery.

The gate itself is shown while a run is in progress: **Starting**, **Accepting commands**, **Draining**, and **Closed**. While the gate is **Starting** you see "Waiting for the harness control endpoint to become ready..."; while it is **Draining** you see that the run is finishing and no new commands are accepted.

One caveat is stated in the UI and worth repeating: "Harness accepted" means the interface acknowledged the command — it does not guarantee the model has consumed it yet. Use the process log to confirm the effect.

## Appending a follow-up task

When a run finishes and you want more work on the same Issue, append a Task instead of creating an unrelated one:

- On the Issue page, **Append Task** states that appended tasks share the same workspace, AI session, and Git branch, allowing them to continue from where the previous task left off.
- On the latest Task of an Issue, **Append a Follow-up Task** says this is the latest task on the issue and that appending here continues from this run. Use **Append Task** to open the form.
- A completed Task also links **Continue on This Issue**, explaining that you can append a follow-up task on the issue page to continue where this task left off — all tasks share the same workspace, AI session, and Git branch.

Follow-up Tasks are appended to the tail of the Issue queue, so they run after everything already queued. If the conversation should not carry over, enable **Run in a new session** while creating the follow-up: the workspace, Git branch, and previous session records are preserved, but a new conversation generation starts.

A follow-up created by CI auto-repair is distinguished in the UI: its trigger source is shown as **CI auto-repair**, alongside **Retry** and **Follow-up**.

## Cancel, retry, and force-finish

The task page shows only the actions that are valid for the current state, and each action button explains itself in a tooltip before you click it.

**Cancel** — **Cancel Task** is offered for tasks in **Pending**, **Queued**, or **Running**. Its description is: stop execution for the current task while keeping the latest status and logs available for review. Cancelling a queued task removes it from the queue; cancelling a running task asks the container to stop, and the Task ends as **Cancelled** once the container has converged.

**Retry** — **Retry Task** is offered for **Failed** and **Cancelled** tasks. It re-queues the task with the same prompt and branch configuration to run it again, as a new Task that reuses the frozen snapshot and the session lineage. The original Task is preserved with its error state and is linked as **Retried →** from the new one.

- If a retry already exists, the panel reports **Retry Task Exists**: this task already has an active retry task.
- **Schedule Retry** picks a future time for the retry instead of queuing it immediately.
- **Session lineage** controls which conversation the retry continues. **Continue current session** is the default. If the retry source belongs to an older session lineage than the current queue tail, Codify asks for confirmation — **Retry with a new session?** — explaining that the retry source is older than the current queue tail and offering **Use source config and start new session**, alongside the alternative **Start a new session generation**.

**Execute now** — **Execute Now** removes scheduling delay and sends the task straight to execution as soon as the worker is available. It is available for **Pending** and **Queued** tasks. If the task is behind predecessors in its Issue queue, the panel says so up front rather than implying it jumped the queue.

**Reschedule** — **Reschedule Task** updates the reserved execution time for a pending or scheduled task without recreating it. The new time must be in the future and must stay inside the Issue's queue window: not earlier than the earliest execution of the earlier Task and not later than the latest execution of the later one. The panel names the window when it is constrained.

**Force-finish** — when the system's assessment is wrong, an operator can correct a terminal status. On a **Completed** task the action is **Mark as Completed**; on a **Failed** task it is **Mark as Failed**. Codify confirms first — "Are you sure you want to mark this task as failed? This will affect analytics and issue status." — and offers a **Reason for override (optional)** field so the correction is auditable. An override changes the reported outcome, which is why the confirmation warns that analytics and Issue status are affected; the code, logs, and delivery artifacts are untouched.

Failed tasks report why. The **Error** section of **Task Result** shows **Failure reason** together with a kind drawn from a fixed set: **Timeout**, **Protocol error**, **Cancelled**, **Authentication failed**, **Rate limited**, **Sandbox failure**, and **Harness error**. **Show full output** expands the raw error text when the summary is not enough.
