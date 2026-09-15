---
title: Creating an Issue
tier: core
section: User Guide
---

## Choose a new Issue or a follow-up Task

An `Issue` is the container for one line of work. It owns the project, workspace, working branch, Worker, and delivery strategy. A `Task` is one execution turn on that line. A follow-up can continue the current session or start a new one; a new session still stays on the same Issue, workspace, and branch.

| What changed | Choose |
|---|---|
| The project, starting branch, merge target, Worker, clone mode, or MR strategy | New Issue |
| You need an independent working branch or Merge Request | New Issue |
| The project and branch strategy are the same, and you are doing the next piece | Append Task |
| The last result needs a small fix or another verification pass | Append Task |

Codify fixes the project, starting branch, merge target, **Create Merge Request**, **Branch cleanup**, Worker, and repository clone settings when you create the Issue. You can later edit the title, description, **MR pipeline failure auto-repair**, default AI Provider, and default Harness from the Issue page. Existing Tasks keep the values captured when they were created.

> [!warning] **Before you submit:** confirm the project, starting branch, merge target, MR switch, branch cleanup, Worker, and clone mode. They cannot be changed after creation. Create a new Issue when one of these boundaries must change.

Creating an Issue does not create a Task. After submission, open the Issue page and start its first Task. Analysis mode can produce an answer without changing files. See [Creating a Task](/guide/30-create-task) for the next step.

## Fill in the form {deep}

![Five parts, with the boundary and delivery choices made before submission](assets/diagrams/en/create-issue-form.svg)

The form has five parts: Project, Issue content, Branch Strategy, Execution environment, and Advanced settings. Project, Title, Starting Branch, and Worker are required.

| Field | What it controls | After creation |
|---|---|---|
| Project | The GitLab project to change. The picker shows projects available to the current login | Fixed |
| Title | The Issue name and the source for the Merge Request title, usually shown as `Draft: title` | Editable |
| Description | Durable goal, context, and constraints. New Task prompts start with this text | Editable; affects future Tasks only |
| Starting Branch | The baseline that the Worker checks out, normally the project's default branch | Fixed |
| Create Merge Request, Merge Target | Whether to create or update an MR, and which branch receives it. Merge Target is disabled when MR creation is off | Fixed |
| Worker | The Worker Profile that runs this Issue | Fixed |
| Default Provider, Default Harness | Defaults for new Tasks; a Task can override them where allowed | Defaults are editable |
| Advanced settings | Full or shallow clone, `blob:none`, branch cleanup, and CI auto-repair | Clone and cleanup are fixed; CI switch is editable |

Shallow clone and deferred file contents require a mounted Worker Kit at the minimum version listed in [Platform reference](/guide/96-platform-reference). Full clone is the safer default when you do not know whether the work needs old history. CI auto-repair also requires Create Merge Request and a healthy project webhook.

## Write the description

Keep durable context in the Issue description. Put this Task's concrete work in the Task prompt. The Issue description can hold the goal, fixed constraints, rules that apply to every turn, and useful links. The Task prompt should say what to change now, where it may change, what done means, and how to verify it.

The description becomes the initial prompt for a new Task. Editing it later does not rewrite existing Tasks. You can also leave it empty, create the Issue, and write the first prompt from the Issue page.

**Use Requirement Template** fills the description from the template library. `{{variable}}` placeholders are not expanded automatically, so replace them before submitting. Choosing a template replaces the existing description after you confirm the warning.

The title appears in the Issue list and the MR. Write it as a result someone can recognize. Markdown lists are enough for the description and are easier to scan than a long paragraph.

```text
Goal:

Durable constraints:

Done when:
```

Put the file scope, acceptance criteria, and verification commands for this turn in [Creating a Task](/guide/30-create-task).

## Set branches and delivery

The branch path is: `Starting Branch` → `codify/issue-{id}` → `Merge Target`. Codify assigns `codify/issue-{id}` when it creates the Issue. The branch appears in GitLab after the first Task pushes a commit, and every later Task on the Issue uses it.

- **Create Merge Request on:** the Task pushes the working branch and creates or updates an MR aimed at Merge Target.
- **Create Merge Request off:** the Task still pushes the working branch, but no MR is created and Merge Target has no effect.
- **Branch cleanup on:** an MR merge webhook that auto-closes the Issue deletes the working branch. Manual close asks separately whether to keep or delete it.

Starting Branch and Merge Target usually both use the project default branch. Set them differently only when the code should start from one branch and land in another. Shallow clone and deferred file contents reduce repository setup cost, but work that needs blame, merge-base, or old commits should use Full clone.

You can also start from another Issue's `codify/issue-{id}` branch. Only commits carry over. The source workspace and session do not, and the source branch must still exist when the new Issue's first Task runs. See [Techniques](/guide/78-techniques) for the edge cases.

## After creation

After a successful submission, Codify opens the Issue page. The new Issue is **Open** with no Tasks. Its working branch name is assigned, but no repository has been cloned or pushed yet.

1. Select **Create Task**, choose a Task Mode and priority, then run it now or schedule it.
2. Follow status, events, logs, commits, and delivery details from the Issue page.
3. Append a Task when the result needs another pass. Create a new Issue when the project or fixed branch strategy changes.

The Issue page can edit the title, description, CI auto-repair, default Provider, and default Harness. Closing an Issue asks whether to keep or delete its working branch. Deleting the Issue removes its records and cannot be undone.

## Common problems

| Symptom | Check first |
|---|---|
| The project picker is empty | Whether the current login can access a project. A bot login and a GitLab user login may see different projects. See [Troubleshooting](/guide/55-troubleshooting) |
| Branches fail to load | Refresh and retry; persistent failures point to the GitLab connection or token |
| No Worker is available | Whether an administrator has enabled a Worker Profile. Worker is required for every Issue |
| Shallow clone or deferred contents is unavailable | Whether the Worker is mounted and meets the minimum version in [Platform reference](/guide/96-platform-reference) |
| CI auto-repair is unavailable | Whether MR creation is on and the project webhook passes its checks |
| Submission says the Worker or Provider is unavailable | Choose an enabled configuration, or return the Provider to the system default |

If you only need to change the Task Mode, priority, schedule, or this turn's prompt, stay on the same Issue and create or append a Task.
