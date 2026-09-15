---
title: Delivery
section: User Guide
tier: core
---

## Branch and commits

![One branch; with or without an MR, the Issue still closes](assets/diagrams/en/delivery-path.svg)

One Issue uses one working branch, codify/issue-{id}. The id is Codify's Issue id, not GitLab's issue IID. Every Task on the Issue uses this branch and workspace.

Codify creates the branch on the first run that needs it. It uses an existing local or remote branch when available; otherwise it starts from the Issue's **Starting Branch**, then the merge target or project default. The branch appears on the remote after the first successful push.

The Task overview shows **Base branch**, **Working branch**, and **Target branch**. A Task without an Issue shows **Direct Push** and **Manual** instead.

Analysis Tasks discard their changes. Implementation Tasks commit them, and Freeform Tasks deliver a commit when the Harness produced one. A later Task starts from the previous checkout, including uncommitted work left there.

You may commit to the working branch yourself. Codify fast-forwards to a remote tip that is ahead, but refuses a diverged, rewound, or unsafe history. If the remote moved while the workspace has uncommitted changes, reconcile the branch before running again or continue in a new Issue.

The **Commit Record** separates **This task commits ({count})** from **Previous task commits ({count})**. The push result is one of:

| Result | Meaning |
|---|---|
| **Pushed** | The branch was pushed and confirmed |
| **Already on remote** | The remote already has the commits |
| **Nothing to deliver** | The run produced no commit |
| **Push not attempted** | The run did not reach delivery |
| **Delivery failed — not confirmed** | Push failed or its result could not be confirmed |

The comparison and failure codes are in [Delivery Internals](/guide/75-delivery-internals).

## Merge request

When **Create Merge Request** is enabled, Codify pushes the working branch and creates or updates one MR for the Issue. When it is disabled, Codify pushes the branch only. This choice is frozen with the Issue.

The Task overview shows a link to !{iid}, **Will create MR**, or **No MR**. Subsequent Tasks update the same MR. Codify starts it as a draft, applies the Codify label, and removes the draft state after successful delivery. The creator is the initiator when the GitLab admin token permits impersonation; otherwise it is the bot account.

Merging the tracked MR closes the Issue after the GitLab webhook arrives. Closing an Issue by hand offers **Close and Keep Branch** or **Close and Delete Branch**. The Issue's branch-cleanup setting controls whether MR auto-close also deletes the working branch.

**MR pipeline failure auto-repair** is opt-in per Issue. It creates repair Tasks only when enabled, the MR is tracked, and the project webhook has the required events and secret. Further failures stop creating repair Tasks after the configured attempt cap.

## Change and usage statistics

The Task records Git diff facts and Harness token usage.

| Record | Includes |
|---|---|
| **Changes** | Additions, deletions, and new, modified, or deleted files |
| **Token Usage** | Input and output tokens reported by the Harness |
| **Run Statistics** | Duration, tokens, context compression, and Skill usage when available |

No diff reports **No net file changes**. If collection failed, the page reports **Change stats not collected** rather than zero. Issue and Analytics totals include finished Tasks with usable data; missing values are excluded from the corresponding aggregate.

## Run archive

Completed and failed Tasks offer **Download runtime archive**. Its contents, limits, and retention are described in [Delivery Internals](/guide/75-delivery-internals).
