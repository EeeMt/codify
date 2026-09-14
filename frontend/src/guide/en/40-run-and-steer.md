---
title: Running and Steering
tier: core
section: User Guide
---

## Task lifecycle

A Task passes through a fixed set of states. The task page names each one and explains what to do in it.

![Six states, and which of them you can act on](assets/diagrams/en/task-lifecycle.svg)

| State | Title on the task page | What it means |
|---|---|---|
| **Pending** | Task is waiting to run | The task is ready and will enter the scheduling queue at its scheduled time or when run immediately |
| **Queued** | Task is waiting for a worker | The task is eligible to run and will start automatically when concurrency capacity is available |
| **Running** | A worker is executing the task | The event stream updates continuously. Use raw logs to investigate container or runtime problems |
| **Completed** | Task completed | The execution outcome, commit record, and delivery summary are available |
| **Failed** | Task failed | Review the failure and event stream before choosing an immediate or scheduled retry |
| **Cancelled** | Task cancelled | Execution stopped. Existing events and logs remain available for diagnosis or retry |

A Queued Task that is not at the head of its Issue shows its position as **Queued #{position} · waiting for Task #{blockedBy}**; a Queue head shows **Queue head · waiting for scheduled time** or **Queue head · waiting for worker**. If the Worker runtime could not be verified, the Task stays pending under **Cannot schedule: Worker runtime unavailable** until an administrator restores and rechecks the runtime, or until the Task is cancelled.

Every action depends on the user's permissions and on the Task's state: only admins or the task owner can run actions on a Task, and other users can review the details but cannot operate it.

## Live process log

![Observe a run first, then choose steering, continuation, retry, or archive](assets/diagrams/en/run-and-steer.svg)

The **Task Process** panel is where you watch a run. While the task is active, the header carries a **Real-time** tag, an elapsed timer, and the **Container** in use. The panel splits the data into two tabs:

| Tab | Content |
|---|---|
| **Events** | The structured stream: assistant text, thinking blocks, tool calls with their captured inputs and outputs, context compaction markers, and subagent groups |
| **Raw Logs** | The raw container output, used to investigate container or runtime problems rather than to follow the work |

**Task not started** appears while the Task is still pending or queued, and **No events yet** when a run produced no structured events. **No logs available** means nothing was captured at all.

Other elements in the panel:

- Thinking blocks are labelled **Thinking** while in progress, with an elapsed time, and **Thinking interrupted** if the model was cut off mid-thought.
- Subagent rows are tagged **Subagent · {name}** and report **Running**, **Completed**, **Failed**, or **Cancelled**, each with its own **{count} tokens**.
- Tool calls show their captured input and output; content that had to be fetched from the archive reports **Loading archived input…** or **Loading archived output…**, and missing content is labelled **No input captured**, **No output captured**, or **Failed to load payload**. **Full text** expands a truncated value.
- Context compaction is marked inline as **Context compressed**; the **Run Statistics** card on the task page summarises it as **Context Compression** with a count of how many times it happened.
- **Run Statistics** also carries **Skill Usage**, the number of times managed skills were used in the run.
- Navigation buttons jump to the top or the latest entry, which helps once a long run has scrolled past the part you were reading.

Very large logs are truncated in the browser: only the latest output is shown, and the panel tells you to download the run archive after completion for the complete logs.

> [!info] **Read the state before acting**: use **Events** to understand what the run did and **Raw Logs** to investigate the container.

## Steering a running task

**Live steering** sends a command into a Task that is already running, without cancelling it. The panel offers two command types:

| Type | Label | Purpose |
|---|---|---|
| Steer | **Steer** | Send a mid-run instruction to the harness, with the placeholder "Send a mid-run instruction to the harness..." |
| Follow-up | **Follow-up** | Queue the next instruction to be consumed when the current turn is done |

Each type is enabled only when the frozen runtime supports it: a Harness that does not advertise steering leaves **Steer** disabled, and one that does not support follow-ups leaves **Follow-up** disabled. When neither is supported the whole panel is left out, which is why the other Harnesses show no command box at all: live steering needs a control channel, and today only Pi provides one.

Codify queues every command and tracks its delivery; each command reports one of these states:

- **Queued**: accepted by Codify, not yet sent.
- **Dispatching**: being handed to the harness.
- **Harness accepted**: the interface acknowledged the command.
- **Rejected**: refused, with **Reason: {message}**.
- **Outcome unknown**: Codify could not confirm delivery.

The command gate is shown while a run is in progress: **Starting**, **Accepting commands**, **Draining**, and **Closed**. While the gate is **Starting** you see "Waiting for the harness control endpoint to become ready..."; while it is **Draining** you see that the run is finishing and no new commands are accepted.

**Harness accepted** does not guarantee that the model has consumed the command yet. Use the process log to confirm the effect.

## Appending a follow-up task

When a run finishes and you want more work on the same Issue, append a Task instead of creating an unrelated one:

- On the Issue page, **Append Task** explains that appended tasks share the same workspace, AI session, and Git branch, so they continue from where the previous task left off.
- On the latest Task of an Issue, **Append a Follow-up Task** says this is the latest task on the issue and that appending here continues from this run. Use **Append Task** to open the form.
- A completed Task also links **Continue on This Issue**, which explains that you can append a follow-up task on the issue page to continue where this task left off.

Follow-up Tasks are appended to the tail of the Issue queue, so they run after everything already queued. If the conversation should not carry over, enable **Run in a new session** while creating the follow-up: the workspace, Git branch, and previous session records are preserved, but a new conversation generation starts. The next turn continues from the working branch, including commits you pushed yourself; the Delivery chapter covers the branch rules.

A follow-up created by CI auto-repair shows its trigger source as **CI auto-repair**, alongside **Retry** and **Follow-up**.

### When to start a fresh session {tips}

Reach for **Run in a new session** once the Issue's conversation has stopped helping: a long run that chased the wrong diagnosis, a round that concerns a different part of the codebase, or a move to another Harness, which a continuing session does not allow. The workspace and the branch are kept, so starting the conversation over loses no code.

## Cancel, retry, and force-finish

The task page shows only the actions that are valid for the current state, and each button has a tooltip explaining what it does.

**Cancel**: the **Cancel** button is offered for tasks in **Pending**, **Queued**, or **Running**, and its tooltip reads: stop execution for the current task while keeping the latest status and logs available for review. Cancelling a queued task removes it from the queue; cancelling a running task asks the container to stop, and the Task ends as **Cancelled** once the container has converged.

**Retry**: **Retry** is offered for **Failed** and **Cancelled** tasks. It re-queues the work as a new Task with the same prompt and branch configuration, reusing the frozen snapshot and the session lineage. The original Task keeps its error state; its record on the Issue page points forward with **Retried →**, and the new Task reports the source in its **Retry of** row.

- If a retry already exists, the panel reports **Retry Task Exists**: this task already has an active retry task.
- **Schedule Retry** picks a future time for the retry instead of queuing it immediately.
- **Session lineage** controls which conversation the retry continues. **Continue current session** is the default. If the retry source belongs to an older session lineage than the current queue tail, Codify asks for confirmation with **Retry with a new session?**, explaining that the retry source is older than the current queue tail and offering **Use source config and start new session**, alongside the alternative **Start a new session generation**.

**Execute now**: **Execute** removes scheduling delay and sends the task straight to execution as soon as the worker is available. It is offered for **Pending** tasks. If the task is behind predecessors in its Issue queue, the panel says so up front.

**Reschedule**: **Reschedule Task** updates the reserved execution time without recreating the Task, and is offered for a **Pending** task that has a scheduled time and for **Queued** tasks. The new time must be in the future and inside the Issue's queue window, no earlier than the earliest execution of the earlier Task and no later than the latest execution of the later one. The panel names the window when it is constrained.

**Force-finish**: when the system's assessment is wrong, an operator can correct a terminal status. On a **Completed** task the action is **Mark as Failed**; on a **Failed** task it is **Mark as Completed**. Codify confirms first with "Are you sure you want to mark this task as failed? This will affect analytics and issue status.", then offers a **Reason for override (optional)** field so the correction is auditable. An override changes the reported outcome; the code, logs, and delivery artifacts are untouched.

On a failed task, the **Error** section of **Task Result** shows **Failure reason** together with the failure type; the page translates the kinds it knows, for example **Timeout**, **Authentication failed**, **Rate limited**, or **Sandbox failure**, and shows an unrecognized kind verbatim. **Show full output** expands the raw error text when the summary is not enough.
