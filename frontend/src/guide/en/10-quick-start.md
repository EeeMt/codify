---
title: Quick Start
section: User Guide
tier: core
---

## Prerequisites

Most of the setup happens before you log in. As a user you need three things:

- A Codify account with the `platform_user` or `platform_admin` role. The first sign-in through GitLab creates the account, with `platform_user` unless your username or GitLab groups match the administrator rules configured on the server. An administrator can then change the role or disable the account from **Access Management**.
- A GitLab project the Codify bot account can see and write to. Codify reaches GitLab through a bot account rather than through your own credentials, so the bot must be a member of the project, or the project must be internal or public so the bot can at least see it. The bot also has to be allowed to push a branch and open a Merge Request; read-only access is not enough, because the Task generates the change and then the push and the Merge Request fail. Adding the bot to a project is an administrator or project-owner action.
- A Worker Profile that enables a Harness your tasks can use: **Claude**, **Codex**, **Pi**, or **OpenCode**. Harnesses are enabled per Worker Profile, so check the one you select on the Issue form.

Administrators set up Worker Profiles and model services from **Configuration**, and grant roles and account state from **Access Management**. If a page reports that no project, Worker, or model service is available, the platform is not set up for you yet; ask an administrator, and see the Admin Guide.

> [!tip] **The shortest path:** Create an Issue → create its first Task → watch the event stream → review the commit → append or close from the same Issue. Get this loop working before you move on to administration.

The login page is at `/login`, and the sign-in methods on it are decided by whoever runs the platform. With GitLab sign-in enabled, the page opens on **Continue with GitLab**, with **Sign in with password** behind a toggle; with GitLab sign-in off, the password form is the only way in. A password exists only for the account created on the one-time setup screen, because nothing else sets one. If the operator enabled emergency access, an **Emergency access** block signs in the environment-configured administrator, for OIDC outages and lockouts. A brand-new platform redirects every route to the one-time setup screen instead, until the first administrator account exists.

## The issue loop

An Issue holds one piece of work and outlives any single run. You create it once, and it owns the workspace, the AI session, and one branch; every run after that is a turn on the same Issue. The Issue page's primary button is **Create Task** while the Issue has no task, and **Append Task** afterwards, which continues on the same workspace, session, and branch from where the previous turn stopped. Review each turn before deciding what the next one should be; when the result is good, merge the single Merge Request and the Issue closes.

- Create the Issue once. Pick the project and branches and write the description; it becomes the default prompt for the Issue's tasks. The workspace, session, and branch are created here and reused by every later turn.
- Create or append a Task for the next turn. On the Issue page, choose a Task Mode and priority, then use **Execute Now** or **Schedule**. Codify queues the Task, runs it in an isolated container, and streams events back.
- Review the turn. Open the Task to read the process log, the commit record, the change and token statistics, and the Merge Request link. Steer it while it runs if it drifts, and append a follow-up turn when the work should go further.
- Finish once. Every turn commits to the same branch and feeds the same Merge Request; when you are happy with it, merge it and the Issue is done.

![One Issue, many turns, one Merge Request](assets/diagrams/en/issue-loop.svg)

### Your first task

A first turn means one Issue and one Task on it. The shortest path from an empty dashboard to a reviewed change is:

1. Open **Issues** and select **Create Issue**. Work through the form: choose **Project**, the **Starting Branch** and **Merge Target**, pick the **Worker**, and describe the outcome you want in **Description**. The Creating an Issue chapter walks the whole form.
2. On the new Issue, select **Create Task** and pick a Task Mode on the **Choose a task mode** step. Use **Implementation** when the turn should change and commit code. Priority can stay on its default unless you have a reason to move it.
3. Leave **Execute Now** selected and submit. The Issue appears with **In Progress** and one run in **Current Run**.
4. Open that Task. Watch the **Task Process** panel while it runs; the event stream refreshes on its own.
5. When the status turns **Completed**, read **Task Result** for the commit record, the change figures, and the delivery summary, and **Run Statistics** for the token figures.

If the Task ends as **Failed**, the **Error** section of **Task Result** gives you the failure reason and its kind before you retry. A **Retry** reuses the same frozen configuration, so change something only when the cause was the prompt, the configuration, or the environment; a transient failure needs no change.

One turn rarely finishes the work, and the Issue stays open for the rest of it. Use **Append Task** rather than going back to **Issues** and creating a new one, so the next turn continues from where the previous one stopped and everything still ends in this Issue's single Merge Request.

## Navigating the interface

The left navigation groups pages into **Workspace**, **Insights & Operations**, and **Administration**. Everything a non-admin needs lives in the first two groups.

| Navigation entry | Route | What it shows |
|---|---|---|
| **Dashboard** | `/dashboard` | **My Work Board**, live counters, and the 90-day issue, task, change, and token panels |
| **Issues** | `/issues` | Every Issue; **Create Issue** here starts a new workflow |
| **Tasks** | `/tasks` | The full task table with status, priority, harness, branch, MR, changes, and duration |
| **Sessions** | `/sessions` | Your dashboard sessions, their refresh support, and revoke actions |

Two more controls sit in the top bar rather than the sidebar: the add button, whose tooltip reads **Create a new issue**, opens `/issues/create`; the book button, **View guide**, opens `/guide`.

Under **Insights & Operations**:

| Navigation entry | Route | What it shows |
|---|---|---|
| **Analytics** | `/analytics` | Workload, reliability, queueing, and provider comparisons |
| **Schedule Overview** | `/schedule-overview` | Scheduled queue, next-24-hour load, and the 7-day heatmap |
| **Monitor** | `/monitor` | Runtime overview, container debugging, and health checks |

**Administration** holds Configuration, Access Management, Usage Management, and System Statistics. Those pages are for operators; the Admin Guide covers them.

Analytics, Schedule Overview, and Monitor are shared pages. If your role or the platform policy does not grant access, they are hidden from navigation.

The task detail page is the control surface for a single run: **Current execution**, **Task overview**, **Run instruction**, **Task Process**, **Run Statistics**, and **Task Result**. Open it from the task table, from a task card on the Dashboard board, or from **View Task #{id}** on the Issue page.

## Where to go next

- Concepts chapter: the vocabulary the rest of the guide assumes (Issue, Task, Harness, workspace, snapshot).
- Creating an Issue chapter: the Issue form field by field. It covers project, content, branch strategy, execution environment, advanced settings, and what happens after creation.
- Creating a Task chapter: Task Modes, priority, scheduling, run-instruction templates, and Worker and provider selection.
- Running and Steering chapter: the process log, live steering, follow-up tasks, cancel, retry, and force-finish.
- Delivery chapter: branches, Merge Requests, change and token statistics.
- Delivery Internals chapter: the publish rule, the codes a refused push reports, and everything the run archive holds.
- Scheduling chapter: queue arbitration, concurrency, the per-issue mutex, slot capacity, and timeouts.
- Observability chapter: Dashboard, Analytics, Monitor, Schedule Overview, and Sessions.
- Harness Support chapter: per-Harness differences, steering support, and model protocol pairing.
- Techniques chapter: managing context across Issues, Tasks, and sessions, mixing the Task Modes, and sharing a branch with Codify.
