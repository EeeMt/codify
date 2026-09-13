---
title: Quick Start
section: User Guide
---

## Prerequisites

Almost everything is arranged before you log in. As a user you need three things:

- A Codify account with the `platform_user` or `platform_admin` role.
- A GitLab project the Codify bot account can see and write to. Codify reaches GitLab through a bot account rather than through your own credentials, so the bot has to be a member of the project — or the project has to be internal or public so the bot can at least see it — and it must be allowed to push a branch and open a Merge Request. Read-only access is not enough: the Task generates the change, then the push and the Merge Request fail. Adding the bot to a project is an administrator or project-owner action.
- A Harness that an administrator has enabled for you — **Claude**, **Codex**, **Pi**, or **OpenCode**.

Administrators set all of these up from **Configuration**. If a page reports that no project or Harness is available, your account is not ready yet; ask an administrator, and see the Admin Guide.

Your sign-in method is decided by whoever runs the platform: a local account, GitLab sign-in, or both. The login page is at `/login`, and a brand-new platform shows a one-time setup screen until the first administrator account exists.

## The three-step loop

Every workflow in Codify follows the same loop: describe the work on an Issue, run a Task against it, then review what the Task delivered.

![Three steps from request to a reviewed change](assets/diagrams/en/three-step-loop.svg)

1. **Create Issue** — pick the project and branches and write the description. The description becomes the default prompt for its tasks.
2. **Create Task** — from the Issue page, choose a Task Mode and priority, then use **Execute Now** or **Schedule**. Codify queues the Task, starts a container, and streams events back.
3. Review the delivery — open the Task to read the process log, the commit record, the change and token statistics, and the Merge Request link.

### Your first task

The shortest path from an empty dashboard to a reviewed change:

1. Open **Issues** and select **Create Issue**. Work through the form — choose **Project**, the **Starting Branch** and **Merge Target**, pick the **Worker**, and describe the outcome you want in **Description**. The Creating an Issue chapter walks the whole form.
2. On the new Issue, select **Create Task**. Leave **Task Mode** on **Implementation** and priority on the default unless you have a reason to change them.
3. Leave **Execute Now** selected and submit. The Issue appears with **In Progress** and one run in **Current Run**.
4. Open that Task. Watch the **Task Process** panel while it runs; the event stream refreshes on its own.
5. When the status turns **Completed**, read **Task Result** for the commit record and delivery summary, and **Run Statistics** for the change and token figures.

If the Task ends as **Failed**, the **Error** section of **Task Result** gives you the failure reason and its kind before you retry. A **Retry** reuses the same frozen configuration, so you only need to change something when the cause was the prompt, the configuration, or the environment — not the transient failure.

To get more work out of the same Issue, use **Append Task** instead of creating a new Task from scratch: appended tasks share the same workspace, AI session, and Git branch, allowing them to continue from where the previous task left off.

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

The task detail page is the control surface for a single run. **Current execution**, **Task overview**, **Run instruction**, **Task Process**, **Run Statistics**, and **Task Result** all live on that page. Open it from the task table, from a task card on the Dashboard board, or from **View Task #{id}** on the Issue page.

## Where to go next

- Concepts chapter — the vocabulary the rest of the guide assumes: Issue, Task, Harness, workspace, snapshot.
- Creating an Issue chapter — the Issue form field by field: project, content, branch strategy, execution environment, advanced settings, and what happens after creation.
- Creating a Task chapter — Task Modes, priority, scheduling, run-instruction templates, Worker and provider selection.
- Running and Steering chapter — the process log, live steering, follow-up tasks, cancel, retry, and force-finish.
- Delivery chapter — branches, Merge Requests, change and token statistics, and the run archive.
- Scheduling chapter — queue arbitration, concurrency, the per-issue mutex, slot capacity, and timeouts.
- Observability chapter — Dashboard, Analytics, Monitor, Schedule Overview, and Sessions.
