---
title: Scheduling
section: User Guide
tier: deep
---

## Queue and priority arbitration {core}

After creation, a Task is **Pending** until it is eligible, **Queued** until a Worker claims it, and **Running** while the Worker executes it. The scheduler checks on its configured interval. Each cycle promotes eligible Issue heads and starts at most one Task.

![Three gates before a run: turn order, schedule, capacity](assets/diagrams/en/why-a-task-waits.svg)

An Issue's turn order is the first gate. A Task that is not the active head of its Issue cannot be promoted, regardless of priority. Among eligible heads, Codify chooses:

1. Priority: **P0**, then **P1**, then **P2**.
2. Due scheduled Tasks before immediate Tasks.
3. Earlier scheduled time.
4. Earlier creation time, then Task id.

> [!warning] A waiting Task is not necessarily broken. Read its queue message to tell whether it is behind a predecessor, before its schedule, or waiting for capacity.

The claim checks the Task's turn again when it changes from **Queued** to **Running**, so a stale queue view cannot start the wrong turn.

## Concurrency and per-issue mutex

**Max Concurrency** is the platform-wide number of Tasks that may run at once. When all slots are in use, eligible Tasks remain **Queued**.

Codify also holds a mutex per Issue. Only one Task on an Issue can run at a time, and the lock is released after the Task is terminal and its container is gone. This protects the shared workspace and Harness session.

If work should proceed in parallel, use separate Issues. Tasks appended to one Issue always run in turn order.

## Schedule windows and slot capacity

Scheduling has two independent limits:

- **Issue queue window**: inside one Issue, a new or rescheduled time cannot move before an earlier active Task's scheduled time or after a later active Task's scheduled time. The form shows the available floor and ceiling; it rejects the Task when no valid time remains.
- **Slot capacity**: **Max Tasks per Hour Slot** limits how many active scheduled Tasks fall in one hour. 0 means unlimited. **Enforce Slot Limit** rejects a full slot; with it off, the form warns and allows creation.

The creation preview and **Schedule Overview** count Tasks that are still **Pending**, **Queued**, or **Running** and have a scheduled time. Slot capacity helps distribute planned work; it does not throttle running Tasks. Rescheduling still requires a future time and the Issue queue window.

## Timeout policy {core}

The administrator sets separate peak and off-peak limits:

| Setting | Meaning |
|---|---|
| **Peak start / end** | A 24-hour HH:mm window in the business timezone |
| **Peak timeout** | Limit for Tasks that start inside the window |
| **Off-peak timeout** | Limit for Tasks that start outside it |

The tier and limit are selected once when a Task enters **Running**. Crossing the time boundary later does not change that run. The Task page records **Execution timeout** and **Execution deadline** when available. Exceeding the limit ends the Task as **Failed** with type **Timeout**; cancelling it produces **Cancelled**.

Supported ranges and installation defaults are in [Platform reference](/guide/96-platform-reference).

## Crash recovery

When a platform or Worker is interrupted, recovery compares the Task record with the container:

| Situation | Recovery result |
|---|---|
| Running container still exists | Reattach and continue collecting events and logs |
| Container exited while the Task was Running | Drain its result, then finalize the Task |
| Running Task has no container | Mark it **Failed**, or **Cancelled** when cancellation had been requested |
| Container has no matching running Task | Clean it up as an orphan |
| Docker target is temporarily unreachable | Keep the Task owned while recovery retries |

Recovery does not reorder Tasks or reset turn numbers. A following Task waits while an earlier run is being finalized or its workspace is cleaned. If the turn sequence needs repair, scheduling for that Issue is paused until an administrator resolves it.
