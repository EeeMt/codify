---
title: Troubleshooting
section: User Guide
tier: core
---

## Start by locating the problem

Start with the Task status and the message on its page. Use **Events** for the structured run, **Raw Logs** for container output, and [Platform troubleshooting](/guide/90-troubleshooting) for Worker, Docker, OIDC, or system failures.

![Route by symptom: a Task problem you can handle, or a platform problem for an administrator](assets/diagrams/en/troubleshooting-split.svg)

| Symptom | First check |
|---|---|
| **Failed** Task | The **Error** card and failure type |
| **Pending** or **Queued** Task | Schedule, predecessor, capacity, and the queue message |
| Missing or off-target prompt | Task prompt and Run Instruction Template, especially {{user_prompt}} |
| Sign-in, 403, or missing project | The access table below |
| Missing container or unavailable runtime | [Platform troubleshooting](/guide/90-troubleshooting) |

## What to read when a Task fails

Read the Error card first. Then collect **Events**, **Raw Logs**, and the runtime archive if it exists.

| Message shape | Likely cause | Next action |
|---|---|---|
| Task timed out after &lt;n&gt;s | The timeout frozen when the run started was reached | Split the work or ask an administrator to adjust later Tasks |
| usage_limit_exceeded | A task or token quota blocked creation or execution | Read the exceeded scope and reset time; ask an administrator about **Usage Management** |
| Code delivery was not confirmed... | Push was refused or could not be verified | Give the project, branch, and error to the project owner or administrator |
| protocol_error: ... | Harness events and process state disagree | Retry once; preserve the archive if it repeats |
| worker_runtime_unavailable / harness_cli_unavailable | The frozen Worker or Harness is unavailable | Do not keep retrying; ask an administrator to restore and revalidate it |
| Worker failed to start: ... | The container did not start | Send the Task id and Error card to an administrator |
| Cancelled by user | The run was deliberately cancelled | Append a Task or run it again if the work is still needed |

An empty raw log is possible when the container failed before its first output. The Error card remains the source of truth. An expired archive cannot be downloaded.

## When a Task has not started

**Pending** and **Queued** do not mean failure.

| Queue message | Meaning |
|---|---|
| Future schedule | Wait, or use **Execute Now** |
| Waiting for a predecessor | The Issue runs one Task at a time |
| Waiting for a Worker | Other Issues use all concurrency slots |
| Worker Runtime unavailable | A platform condition; contact an administrator |
| Every Task waits | Check the scheduler, Workers, and system health with an administrator |

A schedule only makes a Task eligible; it cannot bypass turn order. While a Task is pending or queued, use the available edit action to change its schedule, priority, or content. Once it is running, those edits do not change the current run.

## Sign-in, project, and delivery access

| Symptom | Check first | If it continues |
|---|---|---|
| Sign-in loops | Session expiry and site cookies | Sign in again; then ask an administrator to inspect OIDC |
| Admin access required | Whether the page is administrator-only | Ask for the right role or a shared-page permission |
| Project is missing | Your account's project access and the bot's project visibility | Ask an administrator to refresh access and the project cache |
| Task cannot push or create an MR | Bot push/MR permissions and protected-branch rules | Give the error and project path to the owner or administrator |
| Shared page is blocked | Monitor, Schedule Overview, or Analytics access setting | Ask an administrator to enable it under **Configuration** |

Dashboard access and GitLab write access are separate. Seeing a project does not prove that the bot can push to it. Never put tokens in a Task prompt or log.

## What you can do

| Need | Action |
|---|---|
| Run with the same frozen setup | **Retry** |
| Continue from the current code | **Append Task** |
| Keep code but clear the conversation | Append with **Run in a new session** |
| Change project, branches, merge target, or Worker | Create a new Issue |

Every appended Task still needs its own goal, scope, and verification. Use the Issue description for durable context and the Task prompt for one-off work.

## Frequently asked questions

### Why did the Task fail without raw logs?

It may have been rejected before the container started or exited before its first output. Read the Error card, then the archive if one exists.

### Why did a configuration edit not change an existing Task?

Worker, Provider, Harness, Run Instruction, Skills, and Runtime Bundle identity are frozen when a Task is created. A new Task is required to test the new configuration.

### Is a Task waiting because the prompt is wrong?

Usually not. Check the schedule, the earlier Task on the Issue, concurrency, and runtime availability first.

### The result is correct, but there is no Merge Request. Why?

The Issue may have been created with **Create Merge Request** off. That choice cannot be changed later; use a new Issue when an MR is required.

### When should I contact an administrator?

When the error mentions Worker, Docker, Runtime Bundle, OIDC, encryption keys, platform restart, or every Task fails. Include the Task id, Error card, and archive when available.
