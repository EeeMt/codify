---
title: Creating a Task
section: User Guide
---

## Where a task starts

A Task always belongs to an Issue, so every entry point goes through one:

- **Issue page**: open **Issues**, pick an Issue, and use **Create Task**. Use **Append Task** when the Issue already has runs and you want to continue from the latest one. This is the normal way to add work.
- **Task detail page**: a completed task offers **Append a Follow-up Task** when it is the latest task of its Issue, and **Retry Task** when it failed or was cancelled.
- **New Issue**: on the Dashboard or the Issues page, start a new workflow. The Issue form is where the project and branches are chosen.

The task form opens as a drawer titled **Create Task** and is organised into **Task Content** ("describe the goal and choose how to handle it") and **Execution Settings** ("set the task priority and execution time"). In edit mode the same drawer is titled **Edit Task** and narrows to priority and content.

Project and branch settings belong to the Issue, not to an individual Task:

| Control | Label | Notes |
|---|---|---|
| Project | **Project** | Filtered by **Search projects...**, with a **Recent** list |
| Source | **Starting Branch** | AI checks out this branch and creates a new working branch on top of it |
| Target | **Merge Target** | The MR target; use **Use starting branch** to copy the source |

The branch flow is previewed in place as **AI Working Branch (auto-generated)**, which states where the AI checks out from and which branch the MR merges into. Source and target must differ, otherwise there is nothing to open a Merge Request for.

Every Task on the Issue works on the same branch, generated as `codify/issue-{id}`, so the branch is never a per-task decision.

> [!tip] **Snapshot boundary**: when a Task is created, its Worker and model-service identity are frozen. Later profile or provider edits affect later Tasks, not this one.

## Task modes

![Two choices decide a run: how it works and when it starts](assets/diagrams/en/task-mode-choice.svg)

The **Task Mode** selector determines how the Harness treats your prompt. Open **Choose a task mode** and pick one of three:

| Mode | Description shown in the UI |
|---|---|
| **Implementation** | Codify analyses the project, implements code changes, and commits them |
| **Analysis** | Codify answers questions, analyses requirements, or outputs a proposal based on the actual project — no files are modified |
| **Freeform** | Send only the task prompt to the Harness. It decides whether to answer, analyse, or modify code; the task may complete without code changes |

Mode changes the run instruction as well. Switching modes asks whether to use the new mode's default template, and `require_changes` is fixed to false for **Analysis** and **Freeform**, because those modes are not expected to produce commits.

**Require Changes** is the Implementation-mode guard: when enabled, the task is considered failed if no code commits are produced. Disable it for work that is genuinely optional, such as a spike or a question that might still touch files.

## Priority

Priority is the **Priority** field in the **Execution Settings** section. It arbitrates priority between Issues only, and it does not reorder the turns inside one Issue.

| Priority | Option label | Shown description |
|---|---|---|
| `0` | **P0** | **Urgent** |
| `1` | **P1** | **Normal** |
| `2` | **P2** | **Low** |

The task table and Monitor reuse the same three words, so a task listed as **Urgent** there is a P0 task. Priority orders work between Issues in ascending order: every eligible P0 head is picked before any P1, and every P1 before any P2. A lower-priority Task that is the head of its own Issue's queue is not starved by higher-priority work queued elsewhere.

A rule of thumb that matches the queue order: use P0 for work that must not wait behind anything else, P1 for normal feature and improvement work, and P2 for refactors and nice-to-haves that can absorb a delay.

## Run now or schedule

**Schedule** decides when the task enters the execution queue:

| Option | Label | Behaviour |
|---|---|---|
| Immediate | **Execute Now** | Enter the execution queue after creation |
| Absolute | **Schedule at** | Enter the queue at a specific time |

The same pair appears wherever a run is queued: the task drawer, the retry drawer on the Issue page, and the **Schedule Retry** dialog on the task page. An absolute time must be in the future before the form accepts it, and the confirmation line reports what will happen, for example that the task will run at a specific time (UTC+8).

If an administrator has configured slot capacity, the picker warns before you submit the form: **Time slot {start}–{end} is near/at capacity** is a warning, and an enforced full slot blocks creation outright. The **Schedule Load (7 days)** preview lets you click a cell to select that hour; darker cells mean more tasks are already scheduled.

Scheduling does not bypass the Issue queue. A scheduled Task that is not the head of its Issue still waits for its predecessors, and **Execute Now** on such a task only clears its own delay.

## Run instruction and variables

The **Run Instruction Template** wraps your requirement. It is what the Harness receives, with your prompt rendered into it. It lives under **Advanced**, described as: customize the run instruction and preview the final prompt.

Controls on the template editor:

- **Instruction** and **Preview** tabs; **Preview** renders the final prompt against the current task context without saving anything.
- **Insert variable** with the **Available variables** list; selecting one inserts it at the cursor.
- **Restore Default Run Instruction** to reload the mode's default template, or **Restore Built-in** where the platform exposes it.
- **Prompt Only** to drop the template entirely and send the raw requirement.

Variables use `{{name}}` syntax. The full catalogue offered by the editor:

| Variable | Meaning |
|---|---|
| `user_prompt` | The task requirement entered by the user |
| `issue_title` | The title of the current issue |
| `project_path` | The full GitLab repository path |
| `branch_name` | The working branch used by this task |
| `base_branch` | The source branch used to create the working branch |
| `target_branch` | The merge request target branch |
| `task_mode` | The current task mode: execute or plan |
| `require_changes` | Whether code changes are required: true or false |
| `previous_task_summaries_path` | Runtime path to previous task summaries |
| `ci_failure_context_path` | Runtime path to the CI failure context directory |

**Freeform** mode is fixed to the built-in `{{user_prompt}}` template, so its editor offers only that variable. If your template drops `user_prompt`, the UI warns that the current run instruction will not automatically include the requirement. Unknown placeholders are reported by name rather than silently kept.

The rendered prompt is stored on the Task, so you can still inspect what the Harness received after the template is edited.

## Provider and worker profile

**Execution Environment** controls where and with which model the Task runs:

- **Worker** is fixed by the Issue and cannot be changed per task. The hint reads: Worker is fixed by the issue; AI provider can be overridden. The drawer also states that the Worker and Worker Kit are fixed by the issue and cannot be changed for this task.
- **Default AI Provider** defaults to **Follow issue default**, meaning the Task uses the Issue's provider unless you pick an override. A Task-level choice is shown as **Task override**, and **Restore defaults** returns to **Following issue default**.
- **Harness** is pinned to the Task snapshot. Continue-session Tasks must reuse the current Harness; to switch, create the Task with **Run in a new session**.

The Harness selector shows every option with its availability. Each choice is annotated as **available**, **unavailable**, **not verified**, **enabled**, or **disabled**, with a reason such as **worker profile disabled**, **Worker Kit unavailable**, **runtime not verified**, **explicit host mount**, or **fixed by task snapshot**. If no enabled AI Provider speaks the protocol a Harness needs, the form says so and points you to AI Providers in Configuration. When a Harness requires a specific protocol and the current provider cannot serve it, Codify switches the provider automatically and adds a hint.

Whether an MR is created at all is an Issue-level choice, made in the Issue form with **Create Merge Request**; the form confirms the current setting as **MR will be created** or **No MR**. Tasks inherit it. When the Issue is configured without an MR, Codify pushes the branch only.

If your account is over its quota, submission is refused with **Usage limit exceeded**, showing the metric, the window (**Daily** or **Weekly**), the amount **Used**, and when the limit **Resets**.

## Skills and MCP

**Skills** are packaged capabilities the run can use. The task form offers **Follow Worker defaults** or an explicit **Select one or more skills** override:

- **Follow Worker defaults** uses the enabled default skills from the Worker Profile.
- An explicit selection fully replaces the profile defaults; clearing it runs the task without managed skills.
- Skills require the **Mounted worker kit** delivery mode (0.3.5 or newer); the **Baked image (deprecated)** mode does not support them.

Skill versions are frozen into the Task snapshot. If the global catalogue later changes, the task page says the Skill snapshot or the profile Skill selection changed, and offers **Apply current available versions** to refresh. A snapshot that cannot be resolved is shown as **unavailable**, with an older frozen version marked as **older version**.

MCP extensions are not selected per task. They come from the Worker Profile: a profile can enable CodeGraph, described in Configuration as "Enables the local CodeGraph MCP server and project index for tasks using this profile." Because the profile is frozen into the Task snapshot, changing that option affects only Tasks created afterwards.
