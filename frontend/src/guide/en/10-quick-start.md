---
title: Quick Start
section: User Guide
tier: core
---

## Issues and tasks

An Issue is a continuing line of work. A Task is one run within it. The Issue owns the workspace, session history, and working branch `codify/issue-{id}`. Its Tasks run in order and send their commits to the same branch and, when enabled, the same Merge Request.

Append a Task when the result needs another pass. Create a new Issue when the project, starting branch, merge target, or Worker needs to change.

![One Issue, many turns, one Merge Request](assets/diagrams/en/issue-loop.svg)

## Complete your first task

You need an account, a GitLab project you can access, and a Worker with at least one enabled Harness. If the form has no project or Worker to choose, ask an administrator to check [Configuration](/guide/80-admin-configuration) and the GitLab bot account's project access.

Follow these steps to produce a change you can review:

1. Open [Create Issue](/issues/create). Choose the project, starting branch, merge target, and Worker. Use the title for the problem and the description for durable context; put this turn's goal, scope, and acceptance criteria in the Task prompt.
2. Submit the Issue, then select **Create Task** on its detail page. Choose **Implementation** when the Task should change and commit code. The default P1 priority suits ordinary work.
3. Keep **Execute Now** selected and submit. The Task enters the queue and starts when concurrency is available.
4. Open the Task. Read the event stream to follow its work, and switch to the raw log when you need container output.
5. When the status is **Completed**, review the commits, delivery result, and run statistics. Then open the Merge Request and inspect the code.

[Creating an Issue](/guide/15-create-issue) explains the fields and frozen settings. [Creating a Task](/guide/30-create-task) covers Task Modes and scheduling.

## Choose the next action

| Current situation | Next action |
|---|---|
| The result is ready | Review and merge the Merge Request. The Issue closes after the merge webhook arrives. |
| The code needs another change or more tests | Select **Append Task** on the same Issue to keep the workspace, session, and branch. |
| The Task failed because of a transient service problem | Retry it. The retry uses the source Task's frozen configuration. |
| The prompt, configuration, or environment caused the failure | Correct the cause, then retry or append a Task with clearer instructions. |
| The project, branch strategy, or Worker needs to change | Create a new Issue. Those settings cannot be changed after creation. |
| The Task has not started | Read its queue message, then check [Running and Steering](/guide/40-run-and-steer) and [Scheduling](/guide/60-scheduling). |

An appended Task continues from the code already on the Issue. Enable **Run in a new session** when you need another Harness or when the old conversation is getting in the way. The workspace and branch stay in place.

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
