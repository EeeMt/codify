---
title: Techniques
section: User Guide
tier: tips
---

## Context belongs to the Issue

Every Task belongs to an Issue, and the Issue owns the three things that carry state from one round to the next: its workspace, its AI session, and the working branch `codify/issue-{id}`. An appended Task reuses all three.

What an appended Task inherits, and what it does not:

| Carried forward | Behaviour |
|---|---|
| Workspace | The same issue-scoped working copy on the same branch. Nothing is cloned again between rounds. |
| Session | The Harness conversation, while the Task keeps the default **Continue session** mode and the Issue's lineage still has a session recorded. The task page reports this in the **Session mode** row. |
| Previous-task summaries | A file describing earlier Tasks on the Issue, mounted for every run. The model sees it only if the run instruction asks for it. |
| Prompt and run instruction | New for every Task, never inherited. |

**Run in a new session** is the control that cuts the conversation while everything else stays. Its hint reads: "Do not inherit the current conversation context. The workspace, Git branch, and previous session records are preserved." Use it when the Issue has moved on to a different question and you no longer want that conversation carried forward, or when you need a different Harness, since a continue-session Task must keep the one it started with.

The same choice comes up on retry, through **Session lineage**, which offers **Continue current session** and **Start a new session generation**. When the retry source belongs to an older session lineage than the current queue tail, Codify asks for a fresh session instead of continuing a conversation that no longer matches.

A new Issue is the only way to get a separate workspace, a separate branch, and a separate session lineage. Append when the next round should build on the code and the conversation you have now; otherwise create a new Issue.

## Look without touching the branch

**Analysis** mode runs against a live branch without moving it. The run discards its changes when it ends, and the Task still completes successfully: an analysis Task is not expected to produce commits, `require_changes` is fixed to false, and Codify collects no commit or Merge Request.

Use it for questions you want answered against the real code, such as what the current implementation does or where a failure comes from. The branch stays where it was, so an Implementation Task on the same Issue afterwards starts from the same tip.

## Mixing the task modes

Task Mode is stored per Task, so one Issue can run different modes across its rounds.

| Mode | Run instruction | Changes at the end of the run | Delivery |
|---|---|---|---|
| **Implementation** | The mode's default template, or a template you supply | Committed by the worker | Branch pushed, Merge Request created or reused |
| **Analysis** | The mode's default template, or a template you supply | Discarded | None |
| **Freeform** | Fixed to `{{user_prompt}}` | Whatever the Harness produced | A Merge Request only when the run produced a commit |

Freeform rejects any template other than `{{user_prompt}}`, so the Harness receives your requirement without a wrapper. Use it when the Harness should decide whether to answer, analyse, or edit, and accept that the run may end with nothing to merge; with **Require Changes** off, that outcome is a success. **Require Changes** exists for Implementation only, where turning it on fails a Task that produced no commits.

Run Analysis first to pin down the problem and the intended change, then append an Implementation Task to carry it out on the same branch. Switching mode in the form asks whether to take the new mode's default template, so a template you edited under the previous mode does not carry over by accident.

## Previous-task summaries in context

Codify writes a summaries file for every run and mounts it at `/tmp/codify-runtime/previous-task-summaries.md`, exposed to run instructions as `{{previous_task_summaries_path}}`. The built-in Implementation and Analysis templates never reference it, so the file goes unread unless you add the placeholder yourself.

To do that, open **Advanced** in the task form, edit the **Run Instruction Template** of an Implementation or Analysis Task, place `{{previous_task_summaries_path}}` where the instruction should consult the earlier rounds, and check the result in **Preview**. The rendered prompt is stored on the Task, so you can confirm afterwards what the Harness received. Freeform does not accept the placeholder, since its template has to be `{{user_prompt}}`.

The file holds one entry per earlier Task on the Issue, with its status, goal, commit, and execution summary. It is a summary of the earlier rounds; for the conversation itself, use **Continue session**.

## Continuing across Issues

**Starting Branch** lists every branch in the project, with no filtering, so another Issue's `codify/issue-{id}` can be selected there. The new Issue's branch is then created from that branch at its current tip: the first Task clones the chosen branch and runs `git checkout -b` against its remote tip. The source Issue does not need to be merged or closed: nothing in the flow reads its status, and a source that has never run works just as well.

What does not come across:

- **Only commits carry over.** The new Issue gets its own workspace, its own session lineage, and its own task history.
- **No link between the Merge Requests.** Each Issue keeps its own MR, keyed by its own branch.

What goes wrong:

- **The source branch is gone.** If the branch no longer exists when the new Issue's first Task runs, Codify logs a warning, falls back to the project's default branch, and the Task succeeds from there with the intended work missing. Closing the source Issue with **Close and Delete Branch** before the new Issue has ever run is the usual way to reach that state; run the new Issue once before cleaning up the old branch.
- **The Merge Target points at the default branch.** The field prefills to the project's default branch, so an MR from the new Issue carries the source Issue's unmerged commits into that branch, since they are ancestors of the new branch. If those commits should not land in the default branch, point the target at the source branch or merge the source Issue first.
- **Push rights belong to GitLab.** Codify manages no protected branches. A protected-branch rule matching `codify/*` blocks the push for the bot and for you.

## Sharing the branch with Codify

`codify/issue-{id}` is an ordinary remote branch, and your commits belong on it as much as the worker's. Codify accepts a remote that is ahead of its workspace: the workspace fast-forwards to your tip, and the next run continues from there. At delivery Codify observes the remote tip again and uses it as the `--force-with-lease` lease, so a push of yours that lands mid-run is rejected rather than overwritten.

The history has to stay a straight line. A diverged local and remote, a remote that was rewound, a remote branch deleted while the workspace still remembers it, and a workspace whose uncommitted changes meet a remote that has moved on are each refused: preparation fails before the Harness starts, and neither side is overwritten. Under a shallow clone some ancestry cannot be proven, and that is refused in the same way. Adding commits on top is fine; rewriting the branch is not.

To move work to a different branch, Codify offers nothing: there is no cherry-pick and no cross-branch copy. Those commits are ordinary git history, so cherry-pick them from that branch in your own clone when you need them elsewhere. Inside Codify, work moves forward by pushing at the tip and letting the next Task build on it.
