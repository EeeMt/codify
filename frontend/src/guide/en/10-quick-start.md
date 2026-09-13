---
title: Quick Start
section: User Guide
---

## Prerequisites

Most of the setup happens before you log in. As a user you need three things:

- A Codify account with the `platform_user` or `platform_admin` role.
- A GitLab project the Codify bot account can see and write to. Codify reaches GitLab through a bot account rather than through your own credentials, so the bot must be a member of the project, or the project must be internal or public so the bot can at least see it, and it must be allowed to push a branch and open a Merge Request. Read-only access is not enough: the Task generates the change, then the push and the Merge Request fail. Adding the bot to a project is an administrator or project-owner action.
- A Harness that an administrator has enabled for you: **Claude**, **Codex**, **Pi**, or **OpenCode**.

Administrators set all of these up from **Configuration**. If a page reports that no project or Harness is available, your account is not ready yet; ask an administrator, and see the Admin Guide.

> [!tip] **The shortest path:** Create an Issue → create its first Task → watch the event stream → review the commit → append or close from the same Issue. Get this loop working before you move on to administration.

Your sign-in method is decided by whoever runs the platform: a local account, GitLab sign-in, or both. The login page is at `/login`, and a brand-new platform shows a one-time setup screen until the first administrator account exists.

## The issue loop

An Issue holds one piece of work and outlives any single run. You create it once, and it owns the workspace, the AI session, and one branch; every run after that is a turn on the same Issue. The Issue page's primary button is **Create Task** while the Issue has no task, and **Append Task** afterwards. An appended turn shares the workspace, session, and branch, so it continues from where the previous turn stopped. Review each turn before deciding what the next one should be; when the result is good, merge the single Merge Request and the Issue closes.

- **Create the Issue once.** Pick the project and branches and write the description; it becomes the default prompt for the Issue's tasks. The workspace, the session, and the branch start here and are not rebuilt.
- **Create or append a Task for the next turn.** On the Issue page, choose a Task Mode and priority, then use **Execute Now** or **Schedule**. Codify queues the Task, runs it in an isolated container, and streams events back.
- **Review the turn.** Open the Task to read the process log, the commit record, the change and token statistics, and the Merge Request link. Steer it while it runs when it drifts, and append a follow-up turn when the work should go further.
- **Finish once.** Every turn commits to the same branch and feeds the same Merge Request; when you are happy with it, merge it and the Issue is done.

![One Issue, many turns, one Merge Request](assets/diagrams/en/issue-loop.svg)

### Your first task

A first turn means one Issue and one Task on it. The shortest path from an empty dashboard to a reviewed change is:

1. Open **Issues** and select **Create Issue**. Work through the form: choose **Project**, the **Starting Branch** and **Merge Target**, pick the **Worker**, and describe the outcome you want in **Description**. The Creating an Issue chapter walks the whole form.
2. On the new Issue, select **Create Task**. Leave **Task Mode** on **Implementation** and priority on the default unless you have a reason to change them.
3. Leave **Execute Now** selected and submit. The Issue appears with **In Progress** and one run in **Current Run**.
4. Open that Task. Watch the **Task Process** panel while it runs; the event stream refreshes on its own.
5. When the status turns **Completed**, read **Task Result** for the commit record and delivery summary, and **Run Statistics** for the change and token figures.

If the Task ends as **Failed**, the **Error** section of **Task Result** gives you the failure reason and its kind before you retry. A **Retry** reuses the same frozen configuration, so change something only when the cause was the prompt, the configuration, or the environment; a transient failure needs no change.

One turn rarely finishes the work, and the Issue stays open for the rest of it. What normally comes next is another turn on the same Issue: use **Append Task** rather than going back to **Issues** and creating a new one. An appended Task shares the same workspace, AI session, and Git branch, so it continues from where the previous turn stopped, and everything still ends in this Issue's single Merge Request.

## Navigating the interface

The left navigation groups pages into **Workspace**, **Insights & Operations**, and **Administration**. Everything a non-admin needs lives in the first two groups.

| Navigation entry | Route | What it shows |
|---|---|---|
| **Dashboard** | `/dashboard` | **My Work Board**, live counters, and the 90-day issue, task, change, and token panels |
| **Issues** | `/issues` | Every Issue; **Create Issue** here starts a new workflow |
| **Tasks** | `/tasks` | The full task table with status, priority, harness, branch, MR, changes, and duration |
| **Guide** | `/guide` | This guide |
| **Sessions** | `/sessions` | Your dashboard sessions, their refresh support, and revoke actions |

Under **Insights & Operations**:

| Navigation entry | Route | What it shows |
|---|---|---|
| **Analytics** | `/analytics` | Workload, reliability, queueing, and provider comparisons |
| **Schedule Overview** | `/schedule-overview` | Scheduled queue, next-24-hour load, and the 7-day heatmap |
| **Monitor** | `/monitor` | Runtime overview, container debugging, and health checks |

**Administration** holds Configuration, Access Management, Usage Management, and System Statistics. Those pages are for operators; the Admin Guide covers them.

Analytics, Schedule Overview, and Monitor are shared pages. If your role or the platform policy does not grant them, they are hidden from navigation.

The task detail page is the control surface for a single run: **Current execution**, **Task overview**, **Run instruction**, **Task Process**, **Run Statistics**, and **Task Result**. Open it from the task table, from a task card on the Dashboard board, or from **View Task #{id}** on the Issue page.

## Where to go next

- Concepts chapter: the vocabulary the rest of the guide assumes (Issue, Task, Harness, workspace, snapshot).
- Creating an Issue chapter: the Issue form field by field. It covers project, content, branch strategy, execution environment, advanced settings, and what happens after creation.
- Creating a Task chapter: Task Modes, priority, scheduling, run-instruction templates, and Worker and provider selection.
- Running and Steering chapter: the process log, live steering, follow-up tasks, cancel, retry, and force-finish.
- Delivery chapter: branches, Merge Requests, change and token statistics, and the run archive.
- Scheduling chapter: queue arbitration, concurrency, the per-issue mutex, slot capacity, and timeouts.
- Observability chapter: Dashboard, Analytics, Monitor, Schedule Overview, and Sessions.
- Harness Support chapter: per-Harness differences, steering support, and model protocol pairing.
