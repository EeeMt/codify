---
title: Creating a Task
tier: core
section: User Guide
---

## Where a task starts

A Task always belongs to an Issue, so every entry point goes through one:

- **Issue page**: open **Issues**, pick an Issue, and use **Create Task**. Use **Append Task** when the Issue already has runs and you want to continue from the latest one; this is the usual way to add work.
- **Task detail page**: a finished task offers **Append a Follow-up Task** when it is the latest task of its Issue, and **Retry** when it failed or was cancelled.
- **New Issue**: on the Dashboard or the Issues page you create an Issue and start its first Task from the same form, where the project and branches are chosen. The older `/create-task` path redirects to `/issues/create`.

The task form opens as a drawer titled **Create Task** and is organised into **Task Content** ("Describe the goal and choose how to handle it") and **Execution Settings** ("Set the task priority and execution time"). In edit mode the same drawer is titled **Edit Task** and narrows to priority and content.

The **Prompt** field is the input for this Task. If the Issue has a description, the field starts with that text, and you can rewrite it for the current turn. It also carries **Use Requirement Template**, which opens the **Select Template** drawer; templates are filtered by tag. Picking one replaces the text you have written, after the **Current description will be replaced by the template. Continue?** banner is confirmed.

Project and branch settings belong to the Issue, not to an individual Task:

| Control | Label | Notes |
|---|---|---|
| Project | **Project** | Filtered by **Search projects...**, with a **Recent** list |
| Source | **Starting Branch** | AI checks out this branch and creates a new working branch on top of it |
| Target | **Merge Target** | The MR target; use **Use starting branch** to copy the source |

The branch flow is previewed in place as **AI Working Branch (auto-generated)**, which states where the AI checks out from and which branch the MR merges into. Source and target can be the same, which is the ordinary case when work starts from and merges back into the project's default branch. Choose different branches only when the work should start from one branch and land in another.

Every Task on the Issue works on the same branch, generated as `codify/issue-{id}`.

> [!tip] **Snapshot boundary**: when a Task is created, its Worker and model-service identity are frozen. Later profile or provider edits affect later Tasks, not this Task.

## Task modes

![Two choices decide a run: how it works and when it starts](assets/diagrams/en/task-mode-choice.svg)

The **Task Mode** selector determines how the Harness treats your prompt. Open **Choose a task mode** and pick one of three:

| Mode | Description shown in the UI |
|---|---|
| **Implementation** | Codify analyses the project, implements code changes, and commits them |
| **Analysis** | Codify answers questions, analyses requirements, or outputs a proposal based on the actual project; no files are modified |
| **Freeform** | Send only the task prompt to the Harness. It decides whether to answer, analyze, or modify code; the task may complete without code changes |

Each mode keeps its own run instruction template, so the template you edit under **Implementation** is still there when you come back to it, and a mode you have never opened starts from its default. `require_changes` is fixed to false for **Analysis** and **Freeform**, because those modes are not expected to produce commits.

**Require Changes** is the Implementation-mode guard: when enabled, the task is considered failed if no code commits are produced. It starts off for a new Task; leave it off for work that may legitimately produce none, such as a spike or a question that still touches files.

The mode is frozen on the Task and shown in the **Task Mode** row of the task page. A retry keeps the source Task's mode, and a task created by CI auto-repair always runs as **Implementation** with **Require Changes** on.

## Writing the task prompt

The Task prompt describes this turn's work. When the Issue has a description, Create Task starts with that text in the Prompt field; when it is empty, the prompt starts empty. You can rewrite it for this Task, and the edit does not change the Issue description. [Complete example](/guide/12-complete-example) shows the same fields filled in.

Keep context that applies across Tasks in the Issue description. Use the Task prompt for this turn's goal, scope, constraints, acceptance criteria, and verification. A short request such as "handle this" or a repeated title gives the Harness little to work with. State what it should do now, how far it may go, and how to check the result.

A useful order is action and result first, followed by scope, constraints, and verification. Name known files, interfaces, or error messages directly, and leave unknown details for the Harness to inspect. Keep one Task focused on one verifiable result; use a follow-up Task for the next piece of work.

| Part | What to write |
|---|---|
| Goal | The result this turn should produce |
| Scope | The files, modules, or interfaces it may inspect or change |
| Constraints | Behavior that must stay stable and areas to leave alone |
| Acceptance criteria | Observable conditions that mean the Task is done |
| Verification | Tests, commands, or checks to run |

You can copy this outline:

```text
Goal for this turn:

Allowed changes:
-

Keep unchanged:
-

Acceptance criteria:
-

Verification:
-
```

For **Analysis**, include the question, investigation scope, and desired output. For **Implementation**, include the code result and verification. For **Freeform**, describe the desired outcome and any acceptable approach; the Harness chooses whether to answer, analyze, or modify code.

### How the prompt reaches the Harness

![From Issue context to the Final Run Prompt the Harness receives](assets/diagrams/en/prompt-pipeline.svg)

The Task prompt enters the Run Instruction Template through `{{user_prompt}}`. The template can add context variables such as `{{issue_title}}` and `{{branch_name}}`. When the Task is saved, Codify renders the template for the current context and stores the result as **Final Run Prompt**; this is the text the Harness runs with.

| Layer | Role |
|---|---|
| Issue description | Optional durable context; default content for a new Task prompt |
| Task prompt | Current-turn input you can edit |
| Run Instruction Template | Places `{{user_prompt}}` and context variables into the instruction |
| Final Run Prompt | Rendered and frozen text used by the Harness |

When the current Task needs the prompt to reach the Harness, a custom template that omits `{{user_prompt}}` leaves it out of the Final Run Prompt, and the page warns you. The next section explains how to edit the template.

## Priority

**Priority** is a field in the **Execution Settings** section. It orders work between Issues only; it does not reorder the turns inside one Issue.

| Priority | Option label | Shown description |
|---|---|---|
| `0` | **P0** | **Urgent** |
| `1` | **P1** | **Normal** |
| `2` | **P2** | **Low** |

The task table and Monitor show the same three levels as bare labels, so a task listed as **P0** there is an urgent one. New tasks start on P1.

Priority orders work between Issues in ascending order: every eligible P0 head is picked before any P1, and every P1 before any P2. Only the head of each Issue queue competes for a worker, so priority decides which Issue runs next, and an Issue whose head is P2 keeps waiting while any P0 or P1 head is ready.

Use P0 for work that must not wait behind anything else, P1 for normal feature and improvement work, and P2 for refactors and nice-to-haves that can absorb a delay. **Edit Task** on the task page changes the priority of a task that is still **Pending** or **Queued**.

## Run now or schedule

**Schedule** decides when the task enters the execution queue:

| Option | Label | Behaviour |
|---|---|---|
| Immediate | **Execute Now** | Enter the execution queue after creation |
| Absolute | **Schedule at** | Enter the queue at a specific time |

The same pair appears wherever a run is queued: the task drawer, the retry drawer on the Issue page, and the **Schedule Retry** dialog on the task page. An absolute time must be in the future before the form accepts it, and the confirmation line reports what will happen, for example that the task will run at a specific time (UTC+8).

If an administrator has configured slot capacity, the picker checks the hour of the time you chose and warns before you submit the form with **Time slot {start}–{end} is near/at capacity ({count}/{max} tasks).** An enforced full slot blocks creation outright, and the same check runs again when a task is rescheduled. The **Schedule Load (7 days)** preview lets you click a cell to select that hour; darker cells mean more tasks are already scheduled.

Scheduling does not bypass the Issue queue: a scheduled Task that is not the head of its Issue still waits for its predecessors, and **Execute** on such a task only clears its own delay.

## Run instruction and variables

The **Run Instruction Template** lives under **Advanced** and assembles the Task prompt and context variables into the first instruction the Harness receives. The editor is described as: Customize the run instruction and preview the final prompt.

Controls on the template editor:

- **Instruction** and **Preview** tabs; switching to **Preview** renders the final prompt against the current task context without saving anything, and **Refresh** regenerates it. The result is also kept on the Task, so the task page shows it later as **Final Run Prompt**.
- **Insert variable** with the **Available variables** list; selecting one inserts it at the cursor.
- **Restore Default Run Instruction** to reload the mode's default template.
- **Prompt Only** appears where the platform defaults are edited, under **Configuration**, **Worker**, **Run Instructions**; it replaces the template with `{{user_prompt}}`.

Variables use `{{name}}` syntax. The full catalogue offered by the editor:

| Variable | Meaning |
|---|---|
| `user_prompt` | The task prompt entered by the user |
| `issue_title` | The title of the current issue |
| `project_path` | The full GitLab repository path |
| `branch_name` | The working branch used by this task |
| `base_branch` | The source branch used to create the working branch |
| `target_branch` | The merge request target branch |
| `task_mode` | The current task mode: execute or plan |
| `require_changes` | Whether code changes are required: true or false |
| `previous_task_summaries_path` | Runtime path to previous task summaries |
| `ci_failure_context_path` | Runtime path to the CI failure context directory |

**Freeform** mode is fixed to the built-in `{{user_prompt}}` template, so the form hides the run-instruction editor for it and the API rejects any other template. If your template drops `user_prompt`, the UI warns that the current run instruction will not automatically include the requirement. Unknown placeholders are reported by name, and the API refuses to save or preview a template that contains one.

The rendered prompt is stored on the Task, so you can still inspect what the Harness received after the template is edited.

### Carrying previous task summaries {tips}

`{{previous_task_summaries_path}}` points at a file listing the earlier Tasks on the same Issue with their status, goal, commit message, and execution summary. The built-in Implementation and Analysis templates never reference it, so the summaries reach the Harness only if you put the placeholder into the template yourself. Freeform has no room for it, because its template is fixed to `{{user_prompt}}`. [Techniques](/guide/78-techniques) works through the recipe.

## Provider and worker profile

**Execution Environment** controls where and with which model the Task runs:

- **Worker** is fixed by the Issue and cannot be changed per task. The hint reads: Worker is fixed by the issue; AI provider can be overridden. The drawer repeats the constraint for the Worker Kit.
- **Default AI Provider** defaults to **Follow issue default**, meaning the Task uses the Issue's provider unless you pick an override. A Task-level choice is shown as **Task override**, and **Restore defaults** returns to **Following issue default**.
- **Harness** is pinned to the Task snapshot. Continue-session Tasks must reuse the current Harness; to switch, create the Task with **Run in a new session**.

The Harness selector shows every option with its availability. Each choice is annotated as **available**, **unavailable**, **not verified**, **enabled**, or **disabled**, with a reason such as **worker profile disabled**, **Worker Kit unavailable**, **runtime not verified**, **explicit host mount**, or **fixed by task snapshot**. Only a Harness the Runtime Bundle provides can be selected; [Harness Support](/guide/65-harness-support) explains the availability reasons. If no enabled AI Provider speaks the protocol a Harness needs, the form says so and points you to AI Providers in Configuration. When a Harness requires a specific protocol and the current provider cannot serve it, Codify switches the provider automatically and adds a hint.

Whether an MR is created at all is an Issue-level choice, made in the Issue form with **Create Merge Request**; the form confirms the current setting as **MR will be created** or **No MR**. Tasks inherit it. When the Issue is configured without an MR, Codify pushes the branch only.

If your account is over its quota, submission is refused with **Usage limit exceeded**, showing the metric, the window (**Daily** or **Weekly**), the amount **Used**, and when the limit **Resets**.

## Skills and MCP

**Skills** are packaged capabilities the run can use. The task form offers **Follow Worker defaults** or an explicit **Select one or more skills** override:

- **Follow Worker defaults** uses the enabled default skills from the Worker Profile.
- An explicit selection fully replaces the profile defaults; clearing it runs the task without managed skills.
- Skills require the **Mounted worker kit** delivery mode at the minimum version listed in [Platform reference](/guide/96-platform-reference); **Baked image (deprecated)** does not support them.

Skill versions are frozen into the Task snapshot. If the global catalogue later changes, the task page says the Skill snapshot or the profile Skill selection changed, and offers **Apply current available versions** to refresh. A snapshot that cannot be resolved is shown as **unavailable**, with an older frozen version marked as **older version**.

MCP extensions are not selected per task. They come from the Worker Profile: a profile can enable CodeGraph, described in Configuration as "Enables the local CodeGraph MCP server and project index for tasks using this profile." Because the profile is frozen into the Task snapshot, changing that option affects only Tasks created afterwards.
