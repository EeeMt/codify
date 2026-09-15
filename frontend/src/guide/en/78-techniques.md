---
title: Techniques
section: User Guide
tier: tips
---

## Context belongs to the Issue

An Issue carries the workspace, AI session, and working branch `codify/issue-{id}` from one Task to the next.

| Carries forward | Does not carry forward |
|---|---|
| Workspace and branch | New Task prompt |
| Continue-session conversation | New Task run instruction |
| Previous-task summary file, when the instruction references it | Mode-specific input |

Choose **Run in a new session** when the conversation is no longer useful or you need another Harness. The workspace, branch, and old session records remain. A continued Task must keep the current Harness.

Retries make the same choice through **Session lineage**. If the source is older than the current queue tail, Codify may require a new session generation. A new Issue is the only way to get a separate workspace, branch, and session lineage.

## Look without touching the branch

**Analysis** mode inspects the live branch and discards its changes when the run ends. It completes without a commit and always uses Require Changes off. Use it to understand an implementation, investigate a failure, or compare options before an Implementation Task.

## Mixing the task modes

Modes are stored per Task, so one Issue can use all three:

| Mode | Expected result | Delivery |
|---|---|---|
| **Implementation** | Worker commits the change | Branch and MR delivery |
| **Analysis** | Worker reports without changing the branch | No push |
| **Freeform** | Harness decides whether to answer, inspect, or edit | MR only when it creates a commit |

Freeform's run instruction is fixed to `{{user_prompt}}`. With **Require Changes** off, a run that produces no commit still succeeds. A common sequence is Analysis first, then Implementation on the same branch.

## Previous-task summaries in context

Every Issue run writes `/tmp/codify-runtime/previous-task-summaries.md` and exposes its path as `{{previous_task_summaries_path}}`. Built-in Implementation and Analysis templates do not reference it, so add the placeholder yourself when earlier-round summaries are useful. Freeform cannot add it because its template is fixed.

Open **Advanced**, edit the mode's **Run Instruction Template**, add the placeholder, and check **Preview**. The rendered prompt is stored on the Task. The file contains the Issue title and description plus earlier Task status, goal, commit message, and execution summary.

## Continuing across Issues

Select any existing project branch in **Starting Branch**, including another Issue's `codify/issue-{id}`. The new Issue gets a new workspace, session lineage, and Task history; only the branch's commits carry over.

Watch for three cases:

- If the source branch is deleted before the new Issue's first run, preparation falls back to the project default branch and logs a warning. Run the new Issue once before cleaning up the source.
- The new Issue's Merge Target defaults to the project default branch. Point it at the source branch when the source commits should not enter the default branch yet.
- Codify does not manage GitLab protected-branch rules. A rule matching `codify/*` can block both the bot and your own push.

## Sharing the branch with Codify

The working branch is an ordinary remote branch. Your commits can be used by the next Task; Codify fast-forwards the workspace when the remote is ahead.

Codify rechecks the remote before delivery and uses it as the `--force-with-lease` value. A push that lands during the run is rejected rather than overwritten. Diverged or rewound history, a deleted remote branch, an unverifiable shallow history, or uncommitted local work meeting a moved remote is also refused.

Codify has no cross-branch copy action. Move commits with normal Git commands, such as cherry-pick, in your own clone.
