---
title: Observability
section: User Guide
tier: deep
---

## Dashboard {core}

![Five pages, five questions: pick the one you are asking](assets/diagrams/en/observability-map.svg)

Choose the page by the question: **Dashboard** for your work, **Analytics** for trends, **Monitor** for live operations, and **Schedule Overview** for future load.

Dashboard is the personal view. Its six summary panels cover current Issue and Task status plus the last 90 days of changed lines, tokens, completed-task activity, and trends. **My Work Board** groups your accessible work by status and can auto-refresh. A truncated column tells you how many items remain and links to the full list.

The **Tasks** page is the full table view for records you can access. Its counters describe the visible scope, not just the current table filters. Select a row to open its Task page.

## Analytics

Analytics uses a 7-, 30-, or 90-day window with project and initiator filters. It reports workload, changed lines, execution duration, queue wait, status distribution, success rate, and failure categories.

The **Overview** tab includes daily trends and breakdowns by project and initiator. The **Providers** tab compares finished Tasks attributed to each Provider or model.

Remember three limits on the numbers:

- Initiator analytics begin when initiator tracking was introduced; project analytics include historical Tasks.
- Average Tokens / Sec uses output tokens only.
- Missing token or change data is excluded from the relevant aggregate.

Running Tasks are not part of finished-task duration and success aggregates. Access may be restricted to administrators or enabled for platform users through Configuration.

## Monitor

Monitor is the operational view. It combines the latest visible Task sample, global Task statistics, and the current container inventory.

| Tab | Main question |
|---|---|
| **Runtime Overview** | What is running, ready, or waiting? |
| **Container Debugging** | Do Tasks and Docker containers still match? |
| **Health Signals** | Is the platform showing queue, container, reliability, or duration pressure? |

The active queue is ordered by priority, due time, schedule, and FIFO, with waiting predecessors shown separately. Container relations include **Linked**, **Task missing**, **Unmapped**, **Container outlived task**, **Task still marked running**, and **Historical**. Unreachable Docker targets are reported as unavailable, not as empty.

Health rolls up as **Healthy**, **Watch**, or **Attention**. It checks queue pressure, Worker alignment, failures or cancellations in the last 24 hours, and Tasks running for more than 30 minutes. Monitor is normally an operator page and may be shared through Configuration.

## Schedule overview

Schedule Overview shows active scheduled Tasks in **Pending**, **Queued**, or **Running**. It answers when the platform has planned work.

| View | What it shows |
|---|---|
| **Next 24 Hours** | Scheduled count by hour |
| **Busy & Idle Windows** | The busiest and quietest upcoming windows |
| **7-Day Heatmap** | Load by hour; configured capacity appears as count over limit |
| **Selected Time Window** | Tasks in one hour and their editable schedules |

The page also reports ready work, later backlog, and full slots. The **My Tasks Only** filter changes the scope. Times use the configured business display timezone, currently UTC+8 in the page.

Only administrators can change schedules from this page when sign-in is enabled, and only pending scheduled Tasks can be edited. The new time must be in the future and inside the Issue queue window.

## Sessions {core}

**Sessions** manages dashboard login sessions, not AI conversations. It lists the current browser session and saved sessions with creation, last-seen, expiry, refresh support, token-presence state, and IP when available.

Use **Reload sessions** to refresh the list and **Revoke** to invalidate a session immediately. Revoking the current session signs the browser out. A session without a refresh token may require a new GitLab sign-in when its access token expires.
