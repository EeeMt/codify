---
title: Quick Start
section: User Guide
tier: core
---

## Issues and tasks

An Issue is the long-lived work item. A Task is one execution on it. The Issue owns the workspace, session history, and working branch `codify/issue-{id}`; its Tasks run in order and share that branch and, when enabled, one Merge Request.

Append a Task for another pass. Create a new Issue when the project, starting branch, merge target, or Worker changes.

![One Issue, many turns, one Merge Request](assets/diagrams/en/issue-loop.svg)

## Complete your first task

You need a signed-in account, an accessible GitLab project, and a Worker with an enabled Harness. If the form has no project or Worker, ask an administrator to check [Configuration](/guide/80-admin-configuration) and the bot account's GitLab access.

Follow these steps to produce a change you can review:

1. Open [Create Issue](/issues/create). Choose the project, starting branch, merge target, and Worker. Put durable context in the description; put this turn's goal, scope, and acceptance checks in the Task prompt.
2. Submit the Issue and select **Create Task**. Choose **Implementation** when code should be changed and committed. P1 is a sensible default for ordinary work.
3. Leave **Execute Now** selected and submit. The Task enters the queue and starts when capacity is available.
4. Follow **Events** on the Task page. Open **Raw Logs** when you need container output.
5. When it is **Completed**, review the commits, delivery result, and run statistics, then inspect the Merge Request.

[Creating an Issue](/guide/15-create-issue) explains the fields and frozen settings. [Creating a Task](/guide/30-create-task) covers Task Modes and scheduling.

## Choose the next action

| Current situation | Next action |
|---|---|
| The result is ready | Review and merge the Merge Request. The Issue closes after the merge webhook arrives. |
| The code needs another change or more tests | Use **Append Task** on the same Issue. |
| A transient service problem caused failure | Retry. The retry uses the source Task's frozen configuration. |
| The prompt or environment was wrong | Fix the cause, then retry or append a clearer Task. |
| The project, branch strategy, or Worker must change | Create a new Issue. These settings are fixed after creation. |
| The Task has not started | Read its queue message, then check [Running and Steering](/guide/40-run-and-steer) and [Scheduling](/guide/60-scheduling). |

An appended Task starts from the code already on the Issue. Enable **Run in a new session** when you need another Harness or the old conversation is no longer useful; the workspace and branch stay in place.

## Find the right chapter

| Question | Chapter |
|---|---|
| Can I see one complete example from Issue creation to review? | [Complete example](/guide/12-complete-example) |
| How do Issues, Tasks, workspaces, sessions, and snapshots relate? | [Concepts](/guide/20-concepts) |
| Should I create an Issue or append a Task, and which branches should I choose? | [Creating an Issue](/guide/15-create-issue) |
| Which Task Mode, priority, and run instruction should I use? | [Creating a Task](/guide/30-create-task) |
| How do I follow a run, steer it, cancel it, or retry it? | [Running and Steering](/guide/40-run-and-steer) |
| Where are the commits, Merge Request, and run statistics? | [Delivery](/guide/50-delivery) |
| Why is a Task waiting, and how do schedules and timeouts work? | [Scheduling](/guide/60-scheduling) |
| What does each Harness support? | [Harness Support](/guide/65-harness-support) |
| How do I manage context, combine Task Modes, or share a branch? | [Techniques](/guide/78-techniques) |
| How do I configure providers, Workers, and sign-in? | [Configuration](/guide/80-admin-configuration) |
| How do I investigate failures, access problems, or containers? | [Troubleshooting](/guide/55-troubleshooting) |
