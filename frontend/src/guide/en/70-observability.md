---
title: Observability
section: User Guide
tier: deep
---

## Dashboard {core}

![Five pages, five questions: pick the one you are asking](assets/diagrams/en/observability-map.svg)

> [!tip] **Choose the page by the question**: use Dashboard for personal progress, Analytics for trends and cost, Monitor for live failures, and Schedule Overview for future load.

**Dashboard** is your personal home page. It shows what is in flight and how your work is trending, and it leaves platform internals out.

The **My Work Board** groups your work into columns; an empty column reads **No items in this status.**, and an empty board reads **No items in this view yet.**. When a column is truncated you see **Showing the first {shown} items out of {total}**, with **View more** to open the full list.

Below the board, six panels summarise the last 90 days:

| Panel | What it counts |
|---|---|
| **Issue Status** | Distribution of your issues by status (open / in progress / in review / closed) |
| **Task Status** | Distribution of your tasks by status (pending / queued / running / completed / failed / cancelled) |
| **Lines Changed** | Total lines added and deleted by your tasks |
| **Tokens Used** | Total input and output tokens consumed by your tasks |
| **Activity** | Number of tasks completed per day |
| **Trend** | Daily trends of task completions, code changes, and token usage |

Each panel carries its definition in its own tooltip. Auto-refresh keeps the page current; the header shows **Just updated**, **Updated {n}s ago**, or **Updated {n}m ago**, and the label **Auto-refresh** marks the control.

The **Tasks** page lists the same work as a table, with ID, prompt, project, initiator, issue, status, priority, harness, branch, MR, changes, duration, and scheduled time, and shows a **Visible Tasks** counter for the current filter. Row actions open the task detail page.

## Analytics

**Analytics** covers workload, reliability, execution speed, queueing pressure, and failure patterns over a selectable window: **Last 7 days**, **Last 30 days**, or **Last 90 days**. It has two tabs, **Overview** and **Providers**, and applies project and initiator filters.

The page prints one caveat: project analytics include historical tasks, while initiator analytics only include tasks created after initiator tracking was introduced.

Overview panels:

| Panel | Content |
|---|---|
| **Task Volume Trend** | Daily task count across the selected window |
| **Changed Lines Trend** | Daily total changed lines (additions + deletions) |
| **Execution Duration Trend** | Total runtime for finished tasks each day |
| **Issue Status Distribution** / **Task Status Distribution** | Current statuses across the window and filters, as **Bar** or **Donut**, with **Expand table** for the numbers |
| **By Project** / **By Initiator** | Success rate and timing performance per project or per tracked initiator |
| **Queue Wait by Priority** | Average and worst-case wait before execution starts |
| **Failure Breakdown** | Failures categorized from failed task error messages, with **Category**, **Failures**, **Share**, and **Example** |

Headline metrics include **Issues**, **Tasks**, **Success Rate**, **Total Duration**, **Avg Duration** with **Max {value}**, **Avg Queue Wait** with **Max {value}**, **Changed Lines** shown as `+{additions} / -{deletions}`, and **Total Tokens**. The completed / failed / cancelled breakdown sits in the note under **Success Rate** and **Total Duration**, and is replaced by **No finished tasks yet** when nothing finished in the window. Other empty results are labelled too: **No execution data yet**, **No queue wait data yet**, and **No issues match the current filters and time window yet.**

The **Providers** tab compares providers and models: **Provider-Covered Finished Tasks**, **Provider-Covered Finished-Task Tokens**, **Provider Success Rate**, and **Provider Comparison**. The comparison chart notes that **Avg Tokens / Sec** uses output tokens only, so its definition differs from the other token metrics; do not compare it against **Avg Tokens / Task** without accounting for that.

Access to Analytics depends on your role, or on an administrator enabling it for non-admin users; if you cannot reach it, ask an operator.

## Monitor

**Monitor** is the operational view. It builds its data from the latest visible task sample, global task stats, and the containers currently in the platform's inventory. The header exposes **Live** and **Clear** (to clear activity highlighting), and **Running Now**, **Queue Pressure**, **Active Containers**, and **System Health** appear as live counters.

The page has three tabs:

| Tab | Purpose |
|---|---|
| **Runtime Overview** | The active task queue and the most recent finished activity |
| **Container Debugging** | Container inventory, running tasks missing containers, and orphan containers |
| **Health Signals** | Health checks, task status breakdown, and recent failures |

**Active Task Queue** is sorted by Running → Ready → Waiting, with the ordering rule printed in the subtitle: priority P0 first, then due scheduled before immediate, then earlier schedule first, then FIFO, with waiting tasks ordered by scheduled time. The queue renders as **Board**, **Timeline**, or **Table**. Board columns are **Running**, **Ready**, and **Waiting**; a Ready card shows either **Immediate** or its due time, while a Waiting card explains itself as **Queued #{position} · waiting for Task #{blockedBy}**, **Waiting for Task #{blockedBy} to clean up the workspace**, or **Sequence repair required**.

**Container Debugging** covers the cases where a Task and its container disagree:

| Signal | Meaning |
|---|---|
| **Linked** | The running container maps cleanly to a live task |
| **Task missing** | A running task with no visible running container |
| **Unmapped** | A running container without a matching running task |
| **Container outlived task** | The container is still present although the task is terminal |
| **Task still marked running** | The task state and container state disagree |
| **Historical** | The container belongs to an older run |

Container rows show **Container ID**, **Docker target**, **Name**, **Status**, **Task ID**, and **Age**; when a Task is not in the sample, the row states **task not in latest sample**. If some targets are unreachable, a banner reports **Some Docker targets are unavailable**; inventory covers only the targets that responded.

**Health Signals** runs four checks:

- **Queue pressure**: how many tasks are waiting outside active execution capacity.
- **Worker alignment**: running task gaps and orphan containers, and whether targets are reachable.
- **Recent reliability**: failed or cancelled tasks created in the last 24 hours.
- **Runtime duration**: tasks running for more than 30 minutes.

The roll-up is **Healthy**, **Watch**, or **Attention**. **Recent Failures** lists the latest failed and cancelled tasks and surfaces the top error line. Monitor is normally an operator page; it may be enabled for all users by configuration.

## Schedule overview

**Schedule Overview** shows only active scheduled tasks (those in **Pending** and **Running**) under **Scheduled Tasks**.

| Panel | Content |
|---|---|
| **Next 24 Hours** | Scheduled task count per hour, in UTC+8 |
| **Busy & Idle Windows** | A summary of the next 24 hours, with **Busiest slots** and **Idle slots** |
| **7-Day Heatmap** | Heavier scheduled load in darker cells; cells are **Light**, **Busy**, or **Full** with a **{count}/{max}** readout |

The header summarises the backlog as **Ready Now** (already due to run), **Next 24 Hours** (upcoming scheduled work), **After 24 Hours** (later backlog), and **Busiest Hour**. Empty states are explicit: **No scheduled work in the next 24 hours.** and **Every upcoming hour already has scheduled work.**

Clicking a non-empty hour column or a colored heatmap cell opens **Selected Time Window**, listing the tasks in that slot with **{count} task(s) in this window**, their **Current schedule**, and a time editor. Only pending scheduled tasks can be edited here. Editing is admin-only: if you are not an administrator the page tells you that only admins can adjust task schedules from Schedule Overview, while still letting you inspect the window. Rescheduling from this page obeys the same rules as rescheduling from a task: the new time must be in the future and inside the Issue queue window.

**Full Slots** lists hours at capacity, with the note **Slot capacity: {capacity} per hour**; when nothing is full you see the same capacity statement followed by **None full**. Filters include **My Tasks Only**, a **Status** filter, and a search across project, branch, and prompt. Like Monitor, this page may be restricted by role or by configuration.

## Sessions {core}

**Sessions** lists your dashboard sign-ins so you can review and revoke them. Its description is: "Review your active dashboard sessions, see whether token refresh is available, and revoke sessions you no longer trust."

| Column | Meaning |
|---|---|
| Session | **Saved session** or **Current browser session**; the active one is marked **Current** |
| **Created**, **Last seen**, **Expires** | Lifetime of the session |
| **Refresh support** | **Available** or **Unavailable** |
| Tokens | **Access token stored** / **Access token missing** and **Refresh token stored** / **Refresh token missing** |
| IP | The source address, or **IP unavailable** |

Counters summarise **Active Sessions** and **Refresh-Capable** sessions, and the known list is under **Known Sessions**. **Reload sessions** refreshes the list.

The refresh caveat is stated on the page: if a session has no refresh token, GitLab access expiry will require a fresh sign-in even if the dashboard cookie still exists. Revoking a session invalidates it immediately; revoking the one you are using signs you out and redirects to login. When you cannot find a session you expected, or you see sessions you do not recognize, revoke them and check the platform's login configuration. Session management is a user-facing control; sign-in policy is configured by an administrator.
