---
title: Running and Steering
tier: core
section: User Guide
---

## Task lifecycle

A Task moves through six states. The state and the queue message on the Task page are the best guide to the next action.

![Six states, and which of them you can act on](assets/diagrams/en/task-lifecycle.svg)

| State | Meaning |
|---|---|
| **Pending** | Created, but waiting for its scheduled time or for **Execute Now** |
| **Queued** | Eligible to run, waiting for a Worker slot or an earlier Task on the Issue |
| **Running** | A Worker is executing it; the event stream updates as work arrives |
| **Completed** | The run ended successfully; result, commits, and delivery data are available |
| **Failed** | The run ended with an error; read the Error card before retrying |
| **Cancelled** | Execution was stopped; its events and logs remain available |

The queue message distinguishes the reason for waiting. A non-head Task may show **Queued #{position} · waiting for Task #{blockedBy}**. The head may be waiting for its schedule or for a Worker. An unverified runtime leaves a Task **Pending** with **Cannot schedule: Worker runtime unavailable** until an administrator repairs and rechecks it.

Only the task owner or an administrator can operate a Task. Other users can still read its details.

## Live process log

![Observe a run first, then choose steering, continuation, retry, or archive](assets/diagrams/en/run-and-steer.svg)

Use **Events** to follow the run and **Raw Logs** to investigate the container.

| View | Use it for |
|---|---|
| **Events** | Assistant text, thinking, tool calls and their payloads, context compression, subagents, and delivery events |
| **Raw Logs** | The captured container output, especially startup and runtime failures |

The panel shows **Task not started**, **No events yet**, or **No logs available** when the corresponding data does not exist. It also records thinking and subagent status, tool input and output, context compression, and Skill usage. Long output is truncated in the browser; download the runtime archive after the run for the complete log.

## Steering a running task

When the frozen Harness advertises a control channel, the Task page shows **Live steering**. The current runtime exposes it for Pi; other Harnesses keep the controls unavailable.

| Command | When to use it |
|---|---|
| **Steer** | Send an instruction while the current run is still active |
| **Follow-up** | Queue an instruction for the next turn after the current one finishes |

Commands move through **Queued**, **Dispatching**, **Harness accepted**, **Rejected**, or **Outcome unknown**. The control gate is **Starting**, **Accepting commands**, **Draining**, or **Closed**. **Harness accepted** confirms the interface received the command; it does not prove that the model has acted on it. Check the event stream for the effect.

## Appending a follow-up task

Use **Append Task** when the next round should continue the same Issue. It reuses the Issue workspace, branch, and session when you keep **Continue session**, then joins the tail of the Issue queue. The new prompt and run instruction are still its own.

Choose **Run in a new session** when the old conversation is no longer useful or when you need another Harness. The workspace, branch, and previous session records remain. Continue-session Tasks must keep the current Harness.

CI-created follow-ups are marked **CI auto-repair**. User-created follow-ups and retries keep their own trigger source in the Task metadata.

### When to start a fresh session {tips}

Start fresh after a wrong diagnosis, a long unproductive run, a change of topic, or a Harness change. You keep the code; you reset the conversation.

## Cancel, retry, and force-finish

The **Actions** area shows only actions allowed by the current state.

- **Cancel** is available for **Pending**, **Queued**, and **Running** Tasks. It removes a queued Task or asks a running container to stop, while keeping the record and logs.
- **Retry** is available for **Failed** and **Cancelled** Tasks. It creates a new Task with the source prompt, branch settings, frozen snapshot, and session lineage. The original Task remains unchanged. **Schedule Retry** puts the new Task at a future time.
- **Execute** is available for a **Pending** Task and removes its schedule wait. It still cannot skip an earlier Task on the same Issue.
- **Reschedule Task** changes the time of a pending scheduled or queued Task. The new time must be in the future and inside the Issue queue window.
- **Mark as Failed** and **Mark as Completed** correct a terminal status. The optional override reason is stored for audit; code, logs, and delivery artifacts do not change.

If a retry source is older than the current queue tail, Codify asks whether to start a new session generation. If a Task has already got an active retry, the page reports **Retry Task Exists**.

On a failed Task, read **Failure reason** and its failure type first. **Show full output** expands the raw message when the summary is not enough.
