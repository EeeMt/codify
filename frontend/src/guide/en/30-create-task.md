---
title: Creating a Task
tier: core
section: User Guide
---

## Where a task starts

A Task always belongs to an Issue. On the Issue page, **Create Task** starts the first turn and **Append Task** continues the work. The latest Task also offers **Append a Follow-up Task**; failed or cancelled Tasks can be retried. The Create Issue page can start the first Task, and the old `/create-task` path redirects to `/issues/create`.

The drawer has **Task Content** and **Execution Settings**. The **Prompt** is the input for this turn. When the Issue has a description, the field starts with that text and you can rewrite it. **Use Requirement Template** replaces the current text after confirmation.

Project and branch settings belong to the Issue. When a Task is created, its Worker and model-service identity are stored in a **frozen snapshot**, so later configuration edits do not change this run.

| The Issue decides | The Task decides |
|---|---|
| Project, starting branch, working branch, merge target, Worker, and MR strategy | Prompt, Task Mode, priority, and execution time |
| The workspace and branch relationship | Whether to continue a session and which allowed defaults to override |

## Task modes

![The mode decides whether code changes are expected, and the schedule decides when the task enters the queue](assets/diagrams/en/task-mode-choice.svg)

Choose a mode before the full form opens:

| Mode | Use it for | Code changes |
|---|---|---|
| **Implementation** | Inspecting the project, changing files, and committing a result | You can require a commit |
| **Analysis** | Answering a question, investigating the project, or producing a proposal | No file changes |
| **Freeform** | Sending the prompt to the Harness and letting it choose how to handle it | No commit is promised |

**Require Changes** only applies to Implementation. When it is on, a run without code commits fails; new Tasks start with it off. Analysis and Freeform turn it off automatically. The mode is frozen on the Task, retries keep the source mode, and CI auto-repair Tasks always use Implementation with Require Changes on.

## Write the task prompt

Write the work for this turn. Start with the result, then add scope, constraints, acceptance criteria, and verification. Name known files, interfaces, and error messages. Keep one Task focused on one checkable result and use a follow-up for the next piece.

| Part | Question to answer |
|---|---|
| Goal | What result should this turn produce? |
| Scope | Which files, modules, or interfaces may it inspect or change? |
| Constraints | What behavior must stay unchanged? |
| Acceptance criteria | What observable condition means it is done? |
| Verification | Which tests, commands, or checks should run? |

```text
Goal for this turn:

Allowed changes:

Keep unchanged:

Acceptance criteria:

Verification:
```

Keep durable background in the Issue description and this turn's work in the Task prompt. [Complete example](/guide/12-complete-example) shows the same fields filled in. For Analysis, state the question, investigation scope, and desired output. For Implementation, include the code result and verification. For Freeform, describe the desired outcome and any acceptable approach.

### How the prompt reaches the Harness

![From Issue context to the final run prompt received by the Harness](assets/diagrams/en/prompt-pipeline.svg)

The Task prompt enters the Run Instruction Template through `{{user_prompt}}`. The template may add `{{issue_title}}`, `{{branch_name}}`, and other context. When the Task is saved, Codify renders the template as **Final Run Prompt** and freezes it with the Task. If a custom template omits `{{user_prompt}}`, the page warns that the Task prompt will not be included automatically.

## Priority

Priority chooses between eligible Issue queues. It does not reorder turns inside one Issue. New Tasks start at P1:

| Value | Meaning | Good fit |
|---|---|---|
| **P0** | Urgent | A release blocker or urgent incident |
| **P1** | Normal | Feature and improvement work |
| **P2** | Low | Refactors and work that can wait |

The scheduler considers the head Task of each Issue in ascending priority order. A P2 head waits while another Issue has a ready P0 or P1 head. Tasks that are still **Pending** or **Queued** can have their priority changed with **Edit Task**.

## Run now or schedule

**Execute Now** enters the queue after creation. **Schedule at** enters it at the selected future time, shown in UTC+8.

When slot capacity is configured, the **Schedule Load (7 days)** view shows existing load. Darker cells contain more scheduled work. Near capacity produces a warning; an enforced full slot blocks creation, and rescheduling checks the slot again.

Scheduling does not bypass the Issue queue. A scheduled Task that is not the Issue head waits for its predecessors even after its time arrives. A pending Task can be moved to immediate execution or rescheduled from its own controls.

## Run instruction and variables

The **Run Instruction Template** is under **Advanced**. It assembles the Task prompt and context into the first instruction the Harness receives. The editor has **Instruction** and **Preview** tabs, supports variable insertion, refresh, and **Restore Default Run Instruction**. The rendered result is stored as **Final Run Prompt** on the Task.

The available variables are:

| Variable | Meaning |
|---|---|
| `user_prompt` | The prompt entered for this Task |
| `issue_title` | The current Issue title |
| `project_path` | The full GitLab repository path |
| `branch_name` | The working branch used by the Task |
| `base_branch` | The source branch used to create the working branch |
| `target_branch` | The Merge Request target branch |
| `task_mode` | The current mode: `execute` or `plan` |
| `require_changes` | Whether code changes are required: `true` or `false` |
| `previous_task_summaries_path` | Runtime path to previous Task summaries |
| `ci_failure_context_path` | Runtime path to CI failure context |

Freeform uses the built-in `{{user_prompt}}` template and hides the editor. Unknown placeholders block saving or previewing. A custom template without `{{user_prompt}}` does not pass the current Task prompt into the Final Run Prompt.

### Carrying previous Task summaries into context {tips}

`{{previous_task_summaries_path}}` reaches the Harness only when you put it in the template. The built-in Implementation and Analysis templates do not reference it, and Freeform is fixed to `{{user_prompt}}`. See [Techniques](/guide/78-techniques) for the recipe.

## Provider and Worker settings

The execution environment combines Issue defaults with Task choices:

- The Worker is fixed by the Issue and cannot be changed when creating a Task.
- The Provider follows the Issue default unless you choose a Task-level override.
- Harness availability comes from the Worker configuration and Runtime Bundle. A continuing Task keeps the current Harness; enable **Run in a new session** to switch.
- **Create Merge Request** is an Issue setting. When it is off, the Task pushes the working branch without creating an MR.

Confirm that the Worker runtime is verified before submitting. A disabled profile, unverified runtime, or Harness missing from the Runtime Bundle is shown with a reason and cannot be used. Daily and weekly usage limits can also refuse submission.

## Skills and MCP

Skills can follow Worker defaults or be selected explicitly for this Task. An explicit selection replaces the defaults; clearing it runs without managed Skills. Skills require a mounted Worker Kit at the minimum version listed in [Platform reference](/guide/96-platform-reference); the baked-image mode does not support them.

Skill versions are frozen in the Task snapshot. If the catalogue changes later, the Task page marks an older or unavailable version and can apply the current version. MCP is not selected per Task. CodeGraph comes from the Worker Profile and is frozen into the same snapshot.

Before starting a Task, make sure the Worker runtime says **Verified**. If it is still being verified, finish that check in **Configuration** → **Worker**.
