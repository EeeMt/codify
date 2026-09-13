---
title: Creating an Issue
section: User Guide
---

## When you create an issue

An Issue is the container for a piece of work in Codify. Everything else hangs off one: its description becomes the default prompt for the Tasks you run, its branch strategy decides where the change lands, its execution environment decides where it runs, and every Task you launch or append to it belongs to it.

- **Fixed when you submit:** the project, the starting branch, the merge target, the **Worker** — its hint reads "Fixed after creation; tasks run on this Worker." — and the repository clone settings, which cannot be changed afterwards.
- **Still editable later** from the Issue page: the title, the description, the **MR pipeline failure auto-repair** switch, and the **Default AI Provider**.
- **The form itself, in five parts:** **Project**, **Issue content**, **Branch Strategy**, **Execution environment**, and the collapsed **Advanced settings**. **Reset** returns every field to its default, **Create Issue** submits, and **Cancel** in the header leaves without saving.
- **Scope:** every value here belongs to the Issue, not to one Task. Task Mode, priority, schedule, and run instruction live in the Task form.

Open **Issues** and select **Create Issue**, or go straight to `/issues/create`. A Task takes its execution environment from the Issue and freezes what it inherited into its own snapshot, so changing the Issue later reaches only the Tasks created after the change.

## Form fields

![Five parts, one Issue: some values fixed, some editable](assets/diagrams/en/create-issue-form.svg)

The tables below list every field the form renders, grouped the way the form groups them. **Default** is what a freshly opened form contains. **Applies to** states whether the value is stored on the Issue or belongs to a single Task — in this form, always the Issue.

### Project

| Label | What it controls | Default | Applies to |
|---|---|---|---|
| **Project** | The GitLab repository the Issue works in, chosen from a card grid. **Search projects...** filters by name, namespace path, or description, and your most recent projects are listed first with a **Recent** pill. An empty result reads **No projects found**. | Nothing selected. Required — the form reports **Please select a project**. | Issue, and fixed: the project is not editable afterwards. |

### Issue content

| Label | What it controls | Default | Applies to |
|---|---|---|---|
| **Title** | The Issue name, shown in lists and available to Task prompts as the issue title. Typing suggests titles you used recently. | Empty. Required. | Issue |
| **Description** | The requirement text. It is stored on the Issue and becomes the default prompt of every Task created on it. | Empty; optional. | Issue. Every Task inherits it as its default requirement. |

### Branch Strategy

| Label | What it controls | Default | Applies to |
|---|---|---|---|
| **Starting Branch** | The branch the AI checks out before it starts changing anything. The hint reads "AI will check out this branch and create a new working branch on top of it." Placeholder: **Select starting branch**. | Set to the project's default branch as soon as the project is chosen and that branch is in the list. Required. | Issue, and fixed afterwards. |
| **Create Merge Request** | Whether a Merge Request is opened for the Issue at all. The switch reports its state as **MR will be created** or **No MR**, and is disabled until a project is selected. | On. | Issue. It also gates **Merge Target** and the CI auto-repair switch. |
| **Merge Target** | The branch the working branch is merged into. Disabled while the switch is off, where it shows **No MR**; **Use starting branch** copies the Starting Branch into it. Placeholder: **Select merge target branch**. | The project's default branch, when the switch is on. | Issue, and fixed afterwards. |

### Execution environment

The section carries the hint "Worker is required and fixed for this issue; AI Provider can use the system default."

| Label | What it controls | Default | Applies to |
|---|---|---|---|
| **Worker** | The Worker Profile that runs the Issue. Only enabled profiles are offered. Hint: "Fixed after creation; tasks run on this Worker." | Nothing selected. Required — the form reports **Please select a worker**. | Issue, and fixed after creation. |
| **Default AI Provider** | The model service Tasks on this Issue use. Hint: "Default model service for tasks; can be changed later on the issue detail page." Clearing the selection falls back to the system default. | The system default provider, preselected. Placeholder when cleared: **System Default**. | Issue default. A Task may override it, and the Issue page can change it later. |
| **Default Harness** | Which Harness new sessions start with. Hint: "Changeable for new-session tasks; leave empty to follow the Worker default." Options are limited to the selected Worker's enabled harnesses. | Set from the Worker's own default harness as soon as you pick one; if the profile names none, its first enabled harness is used. | Issue default for Tasks that do not choose one. A continuing session keeps the harness it started with. |

### Advanced settings

The whole section is a collapsed disclosure, closed by default. Its summary always shows the current state, so an unusual configuration is visible without opening it: **Repository clone:** with **Full clone** or **Shallow · depth {depth}**, **File contents:** with **On demand** when deferral is on, **Branch cleanup:** with **Auto-delete** or **Keep branch**, and **MR pipeline auto-repair:** with **On**, **Off**, **Checking**, or **Unavailable**.

**Repository preparation** holds the clone controls:

| Label | What it controls | Default | Applies to |
|---|---|---|---|
| **Repository clone mode** | **Full clone** fetches the complete history for tasks that need blame, merge-base, or older commits; **Shallow clone** fetches only the recent commits and reduces large-repository startup time. | **Full clone** | Issue, and fixed after creation; it decides how every Task's container clones the repository. |
| **History depth** | How many recent commits a shallow clone fetches. Only shown while **Shallow clone** is selected. | 50, set when you switch to **Shallow clone**. Accepts an integer from 1 to 10000. | Same as the clone mode. |
| **Defer historical file contents** | When on, the clone uses `blob:none` and downloads missing file contents on demand instead of fetching them up front. | Off | Same as the clone mode. |

**Shallow clone** and **Defer historical file contents** need a Worker that uses the mounted worker kit, with worker-kit 0.3.0 or newer. A Worker that does not qualify shows the reason instead of the option ("Shallow clone and deferred file contents require a mounted worker kit; baked-image workers are not supported." or "This worker kit does not support shallow clone or deferred file contents. Upgrade to worker-kit 0.3.0 or newer."), and submitting such a combination is rejected.

Two automation cards follow:

| Label | What it controls | Default | Applies to |
|---|---|---|---|
| **Branch cleanup** | Whether the working branch is deleted when an MR merge webhook auto-closes the Issue. The card states which of the two will happen. | On — "AI working branch will be deleted when an MR merge webhook auto-closes this issue". | Issue |
| **MR pipeline failure auto-repair** | Whether Codify creates a repair task when the tracked Merge Request's pipeline fails. | Off, and disabled unless **Create Merge Request** is on and the project's webhook is healthy. When the webhook cannot be used, the card shows **Unavailable** followed by the reason, such as the webhook not being configured, a missing verification secret, disabled SSL verification, or disabled merge request or pipeline events. | Issue |

## Writing the description

The description is the default requirement of every Task on the Issue — the Task form's requirement box opens prefilled from it and tells you so: "Enter task requirement (defaults to issue description)". Write it as the brief you would hand to a colleague: the outcome, the scope, the constraints, and what must not change. A thin description is not fatal, because you can rewrite the requirement on any individual Task, but it does become the starting point for all of them.

Plain text is enough, and `{{variable}}` placeholders are supported. **Use Requirement Template** opens a **Select Template** drawer listing the shared requirement templates. Each entry shows its name, tags, and a preview; **Filter by tags** narrows the list, and the empty states read **No requirement templates available** and **No templates match the selected tags**. Picking a template replaces the whole description, so if you had already written something the drawer asks "Current description will be replaced by the template. Continue?" first, and you confirm or cancel.

Placeholders a template leaves unfilled are not expanded for you. While the description still contains them, the editor warns **Please replace template variables** and names each one, and anything you leave in place is sent on to the model as written.

## Branch and delivery settings

The branch panel previews the whole flow before you commit to it:

- **AI checks out from** the **Starting Branch**.
- **AI Working Branch (auto-generated)** is the branch the AI actually commits to. Codify always generates it as `codify/issue-{id}`; you never name it, and every Task on the Issue — including appended ones — works on that same branch.
- **MR merges into** the **Merge Target**, but only while **Create Merge Request** is on.

**Starting Branch** and **Merge Target** answer different questions, which is why they are two fields. The starting branch is the state of the repository the work begins from. The merge target is where that work is meant to land. Leaving both on the project's default branch is the ordinary case; **Use starting branch** sets the target to match the source in one click. They only need to differ when the work should start from one branch and be merged into another.

**Create Merge Request** decides whether a Merge Request exists at all, and with it whether the delivery is reviewable:

- **On** — Codify opens one draft Merge Request for the Issue against the **Merge Target**, labelled `Codify`, and reuses it for every later Task. The Issue page then links the Merge Request, and the Delivery chapter covers what happens to it during a run.
- **Off** — the **Merge Target** field is disabled and reads **No MR**, the CI auto-repair switch is turned off and disabled, and the Task pushes the working branch without opening a Merge Request.

The switch is disabled until a project is chosen, because the branch list and the default branch used to prefill both fields come from the project.

The clone controls explain themselves through their hints. Reach for **Shallow clone** and **History depth** when a large repository makes startup slow and the work does not need deep history. Reach for **Defer historical file contents** when the repository is large mostly because of old file contents and the tasks touch only a small part of it — file contents are then downloaded only when a task actually needs them.

## After creation

Submitting validates the form first. If a field is rejected, the page scrolls to it, opens **Advanced settings** when the offending field is hidden inside the collapsed section, and focuses the control. Otherwise the Issue is created, a confirmation toast appears, and you are taken to the Issue page.

The new Issue starts as **Open**, with no runs yet — the run history says there is nothing to show and points you at the first Task. The working branch name `codify/issue-{id}` is already assigned, but nothing has been cloned or pushed yet; the branch appears in GitLab when the first Task delivers it. The project you used is remembered in the **Recent** list and the title is remembered for the title suggestions, both stored in your browser rather than on the server.

From here the next step is **Create Task** — or **Create First Task** while the Issue is empty. That is where Task Mode, priority, and the choice between **Execute Now** and a schedule are made. The Issue page is also where you can later edit the title, the description, the CI auto-repair switch, and the **Default AI Provider** through **Edit Issue**; the **Worker** is displayed there but cannot be changed.

Closing the Issue asks what should happen to the working branch — **Close and Keep Branch** or **Close and Delete Branch** — and an MR merge webhook closes the Issue on its own, applying whatever **Branch cleanup** was set to. Only one Task per Issue runs at a time, so a second Task waits for the first to finish, or you use **Append Task** to continue in the same workspace, session, and branch.

## Common mistakes

- **Leaving the Worker unset.** It is required, and it cannot be changed later; you would have to close the Issue and create a new one.
- **Disabling a Worker that an open Issue uses.** A profile assigned to open Issues refuses a plain disable, and force-disabling it closes those Issues.
- **Choosing a Worker that cannot do what you asked for.** **Shallow clone** and **Defer historical file contents** require the mounted worker kit at 0.3.0 or newer. Pick a different Worker or leave the clone mode on **Full clone**.
- **Expecting an MR after switching it off.** With **Create Merge Request** off there is no Merge Target, no Merge Request, and no pipeline auto-repair — the branch is pushed and nothing else happens.
- **Reading the collapsed Advanced settings as "nothing to see".** Full clone of a very large repository is the default and is the usual reason a Task takes a long time to start. The summary line always shows the clone mode, the branch cleanup behaviour, and the repair switch.
- **Forgetting the Merge Target.** With the switch on it prefills from the project's default branch, so on a repository whose default branch is not where you want the change to land, set it explicitly before submitting.
- **Leaving template placeholders in the description.** They are not filled in for you and are passed to the model verbatim.
- **Treating the Issue description as disposable.** It is the default prompt of every Task on the Issue; a vague description produces a vague starting point for all of them.
- **Looking for the project in the picker when it is not there.** The picker only lists projects the account behind it can see, and a project that is listed is not necessarily writable. See the Troubleshooting chapter.
