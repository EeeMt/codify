---
title: Troubleshooting
section: User Guide
tier: core
---

## Start by locating the problem

Read the Task status and its page-level message before opening raw logs. Most problems can be handled from the Task page. Docker, Worker Runtime, platform restart, OIDC, and system configuration problems belong with an administrator.

![Route by symptom: a Task problem you can handle, or a platform problem for an administrator](assets/diagrams/en/troubleshooting-split.svg)

| What you see | Start here |
|---|---|
| The Task is **Failed** | Read the **Error** card, then compare the failure shape below |
| The Task stays **Pending** or **Queued** | Read its queue message and check its schedule, predecessor, and capacity |
| The prompt is missing or the result went in the wrong direction | Check the Task prompt and the Run Instruction Template, especially `{{user_prompt}}` |
| Sign-in loops, a page returns 403, or a project is missing | Use the sign-in and access table below, then contact an administrator if needed |
| A container is missing, Worker Runtime is unavailable, or state changed after a restart | Send it to [Platform troubleshooting](/guide/90-troubleshooting) |

## What to read when a Task fails

Open the **Error** card on the Task page. Its failure kind and message are more useful for choosing an action than the last line of a log. When you need complete evidence, read **Events**, then **Raw Logs**, then the **runtime archive**.

| Message shape | Usually means | Your next action |
|---|---|---|
| `Task timed out after <n>s` | The run used the timeout limit frozen when it entered RUNNING | Check **Execution deadline**; split the work, or ask an administrator to adjust the policy for later Tasks |
| `{"reason": "usage_limit_exceeded", ...}` | A task, token, or window quota stopped creation or execution | Read `scope`, `exceeded_items`, and the reset time; an administrator manages quotas in **Usage Management** |
| `Code delivery was not confirmed...` | The branch push was refused or its result could not be confirmed | Give the project, branch, and error to the project owner or administrator to check bot access |
| `protocol_error: ...` | Harness events and process state disagree | Retry once; if it repeats, attach the runtime archive and use Platform troubleshooting |
| `worker_runtime_unavailable` or `harness_cli_unavailable` | The Worker Runtime or Harness frozen into the Task is not available | Do not keep retrying; ask an administrator to restore and revalidate the Worker |
| `Worker failed to start: ...` | The Worker container did not start successfully | Give the Task id and Error card to an administrator |
| `Cancelled by user` | The run was cancelled deliberately | Nothing is broken; append a Task or run it again if the work is still needed |

Use **Raw Logs** for container output. When the container has exited, the page uses the log chunks captured during execution. If the run failed before producing output, an empty log is expected and the Error card remains the source of truth. The runtime archive only has entries for work that actually ran, and its download control is disabled after the archive expires.

## When a Task has not started

**Pending** and **Queued** do not mean failed. Read the queue text on the Task card, then use this table:

| Status or message | How to read it |
|---|---|
| Pending with a future schedule | Wait for the scheduled time, or use **Execute Now** to clear this Task's schedule wait |
| Waiting for a predecessor | An Issue runs one Task at a time; the current Task waits for the earlier turn to finish |
| Waiting for a Worker | Other Issues are using all available concurrency; wait for a slot |
| Worker Runtime unavailable | This is a platform condition, not a prompt problem; send it to [Platform troubleshooting](/guide/90-troubleshooting) |
| Every Task has not started | Ask an administrator to check the scheduler, Workers, and system health |

A schedule only makes a Task eligible for the queue. It cannot bypass turn order within the Issue. While a Task is still **Pending** or **Queued**, you can edit its priority, schedule, or content; once it is running, those changes do not alter this run.

## Sign-in, project, and delivery access

| Symptom | Check first | If it continues |
|---|---|---|
| Sign-in immediately returns to the sign-in page | Whether the session expired and the browser accepts the site's cookies | Sign in again; repeated loops need an administrator to inspect the sign-in configuration |
| `Admin access required` | Whether you are opening an administrator page | Ask an administrator for the appropriate role, or use a shared page that has been enabled |
| The project picker is empty or misses the project | Whether the signed-in account can access it; platform administrators and local sign-in use the bot account's visible projects | Ask an administrator to confirm bot visibility and refresh the project list |
| A Task is created but cannot push or open a Merge Request | Whether the bot can push branches and create MRs; protected branches may add rules | Give the Task error and project path to the project owner or administrator |
| A shared page is blocked | Whether Monitor, Schedule Overview, or Analytics is enabled for platform users | Ask an administrator to enable the page under **Configuration**, **Runtime and Sharing** |

Codify access and GitLab project access are separate. Being able to open the dashboard does not give the Task permission to push code, and seeing a project does not prove that the bot can write to it. Never put access tokens in a Task prompt or log; administrators should store secrets in Configuration.

## What you can do

| Goal | Action | Use it when |
|---|---|---|
| Run again with the same frozen setup | **Retry** | A transient network, quota, or service condition caused the failure; the retry uses the source snapshot |
| Continue from the current code | **Append Task** | You need a test, a focused fix, or another turn in the same Issue |
| Keep the code but clear the old conversation | Choose **Run in a new session** when appending | The old conversation no longer helps, or you need another Harness |
| Change the project, branches, merge target, or Worker | Create a new Issue | These choices are frozen when the Issue is created |

An appended Task still needs its own goal, scope, and verification. Do not write only "continue". Put cross-turn context in the Issue description and the one-off command or acceptance check in the Task prompt.

## Frequently asked questions

### Why did the Task fail without raw logs?

It may have been rejected before the container started or exited before its first output. Read the Error card first. If a container did run, use Raw Logs or the runtime archive.

### Why did a configuration edit not change an existing Task?

The Worker, Provider, Harness, Run Instruction, and relevant Skills are frozen when a Task is created. Edits apply to later Tasks; create a new Task to test the new configuration.

### Is a Task waiting because the prompt is wrong?

Usually not. Check its schedule, the earlier Task on the Issue, and concurrency first. A Worker Runtime, scheduler, or container message belongs with an administrator.

### The result is correct, but there is no Merge Request. Why?

If **Create Merge Request** was off when the Issue was created, the Task only pushes the working branch. That switch cannot be changed later, so create a new Issue when the work needs an MR.

### When should I contact an administrator?

When the message mentions a Worker, Docker, Runtime Bundle, OIDC, encryption keys, platform restart, or every Task fails at once, stop retrying the same Task. Include the Task id, Error card, and runtime archive if one exists, and send it to [Platform troubleshooting](/guide/90-troubleshooting).
