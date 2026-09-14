---
title: Scheduling
section: User Guide
tier: deep
---

## Queue and priority arbitration {core}

Codify tracks three states between a Task's creation and its run:

- **Pending**: created, not yet eligible to run.
- **Queued**: eligible, waiting for capacity.
- **Running**: claimed by a worker.

Codify looks for work on a fixed interval, set by **Scheduler Interval (seconds)** ("How often the scheduler checks for work."). Each cycle promotes only the legal head of each unlocked Issue from **Pending** to **Queued**, then starts at most one Task. A Task that is not the head of its Issue is never promoted, no matter how high its priority.

![Three gates before a run: turn order, schedule, capacity](assets/diagrams/en/why-a-task-waits.svg)

> [!warning] Waiting is not automatically an error. A Task may be behind another turn, before its scheduled time, or waiting for a free concurrency slot. The task card names which gate is holding it.

Among the eligible heads, Codify picks in this order:

1. Priority ascending: **P0 (Highest)**, then **P1 (High)**, then **P2 (Normal)**.
2. Scheduled Tasks before immediate Tasks, because a user who booked a slot expects it to run near that time.
3. Earlier scheduled times first.
4. Creation order as the final tiebreaker, oldest first.

Monitor prints the same rule in one line: Running → Ready (Priority P0 first, then due scheduled before immediate, then earlier schedule first, then FIFO) → Waiting, with waiting tasks sorted by scheduled time.

Priority arbitrates between Issues only, never between the turns inside one Issue. A queued Task belonging to a busy Issue never becomes a candidate, so it cannot sit at the head of the global order and starve runnable work from other Issues.

The claim is atomic: Codify re-checks the Task's turn number at the moment it moves the Task from **Queued** to **Running**.

## Concurrency and per-issue mutex

Global concurrency is capped by **Max Concurrency**, the maximum number of tasks that can run at the same time. When all slots are taken, eligible Tasks stay **Queued** with the message that they will start automatically when capacity becomes available.

A per-issue mutex allows only one Task per Issue to run at a time. Codify holds the Issue for the whole run and releases it only after the Task is terminal and its isolated container is gone. Two Tasks on the same Issue can never write the same checkout concurrently, which is what keeps the shared workspace and session safe.

An Issue therefore behaves like a long-lived CLI session. You can append as many Tasks as you like and schedule them freely; they execute strictly in turn order, each one seeing the results of the previous turn.

Because of the mutex, a Task that is the head of a busy Issue stays **Queued** while its predecessor runs, and the task page reports the reason, for example that it is waiting for the Task ahead of it to complete, or that it is queued at a specific position.

## Schedule windows and slot capacity

Scheduling a Task has two independent constraints.

**The Issue queue window.** Within one Issue, scheduled times must stay monotonic. A new or rescheduled Task cannot be earlier than the latest scheduled time of any earlier active Task, and cannot be later than the earliest scheduled time of any later active Task. The UI reports the violation as a floor or ceiling constraint naming the Task that causes it, and shows the available window when one exists. If no valid window exists for that Issue's queue, the form says so and refuses the time.

**Slot capacity.** Separately from the queue window, an administrator can cap how much work lands in the same hour:

| Setting | Meaning |
|---|---|
| **Max Tasks per Hour Slot** | Maximum number of tasks that can be scheduled in the same 1-hour window. `0` means unlimited |
| **Enforce Slot Limit** | When enabled, reject task creation if the target hour slot is full. Otherwise, show a warning only |

The task form and the **Schedule Load (7 days)** preview expose this before you commit. Clicking a cell sets that hour as the scheduled time; darker cells mean more tasks are already scheduled there. When a slot fills up you get one of two responses:

- **Time slot {start}–{end} is near/at capacity ({count}/{max} tasks).** This is a warning, and creation can proceed.
- **Time slot {start}–{end} is at full capacity ({count}/{max} tasks). Task creation is blocked.** Enforcement is on and the slot is full.

Schedule Overview renders the same data at platform scale. **Next 24 Hours** counts scheduled tasks per hour, **Busy & Idle Windows** summarises the same window, and the **7-Day Heatmap** marks cells **Light**, **Busy**, or **Full** with the task count in each cell and **{count}/{max}** on hover. Times in these views are shown in UTC+8.

The count covers every Task whose scheduled time falls inside the hour and that is still **Pending**, **Queued**, or **Running**. Slot capacity is a planning guard against landing twenty Tasks on the same hour; it does not throttle runs.

## Timeout policy {core}

Every Task has a maximum execution time, chosen from a two-tier policy configured under **Task Timeout Policy**:

| Setting | Meaning |
|---|---|
| **Peak start time** / **Peak end time** | The daily peak window, in strict 24-hour `HH:mm`. Start is inclusive and end is exclusive |
| **Peak timeout (seconds)** | Limit applied to runs that start inside the window |
| **Off-peak timeout (seconds)** | Limit applied to runs that start outside it |

Both limits must be between 60 and 28800 seconds. The window is evaluated in the business timezone shown next to the policy, labelled **Business timezone: {timezone}**, so the peak window follows human working hours rather than UTC. If the window is configured to wrap past midnight, the peak range is the span from start to end through midnight; setting both ends to the same value is rejected.

The tier is selected once, at the moment the Task enters **Running**, and frozen for that execution: a long run that started at 08:59 does not inherit a new, shorter limit halfway through.

The task page shows the frozen value:

- **Execution deadline**: the absolute time the run must finish by, shown once it has been recorded.
- **Execution timeout**: how many seconds it was given. Before the Task starts the field reads **Determined when execution starts**; an execution that started before the field existed reads **Not recorded for this execution**.

A run that exceeds its limit fails with the failure type **Timeout**. Increase the limits when legitimate work is being cut off; do not read a timeout as a model problem until you have checked the log for progress near the deadline.

## Crash recovery

A run can be interrupted at any moment: the work dies mid-turn, or the platform restarts while Tasks are still in flight. Codify reconciles what it finds.

A Task that was still **Running** when the interruption happened is picked up again: Codify resumes watching it and collects its logs and results. One of three outcomes follows:

| Situation | What you see |
|---|---|
| The interrupted run is still alive | The Task keeps running and its event stream continues |
| The interrupted run is gone | The Task is marked **Failed**, or **Cancelled** if a cancellation had been requested, with the reason recorded |
| Work is left behind with no Task owning it | It is cleaned up as an orphan |

Recovery never silently fails a Task whose outcome it cannot verify: while the answer is unknown the Task stays owned and the check is retried, and the Task is not re-queued. Recovery holds captured logs until it finalizes them, then cleans up the leftover work.

Two related guards affect what you see:

- Leftover work keeps its Issue unavailable until cleanup finishes, so a Task created immediately after a crash may report that it is waiting for its predecessor to clean up the workspace.
- Recovery never resets a Task's turn number or reorders the queue. If an Issue's sequence is found to be inconsistent, Codify repairs it while that Issue is held; while the repair is pending, new scheduling for that Issue is temporarily unavailable and says so.
