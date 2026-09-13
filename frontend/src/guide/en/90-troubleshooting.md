---
title: Troubleshooting
section: Admin Guide
---

## Task failed

A failed task shows the status **Failed** on the Task page. The failure reason is stored on the task itself, so open the task before looking anywhere else: the detail view returns the message plus the failure kind reported by the harness, and the same message is written into the task log.

Read the message by shape. Plain text is a human-readable cause. A JSON object is a structured rejection and names its own code.

| Message | What it means |
| --- | --- |
| `Task timed out after {timeout_seconds}s` followed by the log tail | The task exceeded the timeout it selected when it entered RUNNING |
| `Task {task_id} is RUNNING without execution_timeout_seconds` | The task reached running state without a frozen timeout; the record is inconsistent |
| `Task {task_id} is RUNNING without started_at` | Same class of problem: the timeout anchor is missing |
| `Task {task_id} execution_timeout_seconds must be between 60 and 28800 seconds` | The frozen timeout is outside the supported range |
| `protocol_error: canonical attempt is missing a Task terminal` | The harness stream ended without a terminal event |
| `protocol_error: run.completed conflicts with the worker process exit state` | The harness reported success while the process exited abnormally |
| `protocol_error: worker.finalization git_delivery rejected: ...` | The finalization payload was rejected while delivering the branch |
| `protocol_error: unknown Task terminal ...` | A terminal event the platform does not recognise |
| `{"code": "worker_runtime_unavailable", ...}` | The Worker runtime could not be prepared |
| `{"code": "harness_cli_unavailable", "harness_key": ..., "reason_code": ...}` | The selected harness CLI is absent from the Worker Kit |
| `{"code": "worker_runtime_check_failed", ...}` | The Worker Kit runtime check failed before the container was dispatched |
| `{"code": "execution_contract_mismatch", ...}` | The task's frozen execution contract cannot be honoured |
| `{"reason": "usage_limit_exceeded", ...}` | A usage limit was exceeded before execution; see the detailed sections |
| `Worker failed to start: ...` | The worker container could not be started |
| `Container disappeared during resume: ...` | A resumed session lost its container |
| `Task was running when scheduler restarted (container not found)` | Scheduler restart found the task running but its container gone |
| `Task worker container was not runnable after scheduler recovery (status=...)` | Recovery found the container in a non-runnable state |

Two related outcomes are not failures. A user cancellation ends as **Cancelled** with the message that the task was cancelled by the user, and a cancellation confirmed during recovery records that the worker container is confirmed absent.

### Timeouts

The task detail exposes `execution_timeout_seconds`, `execution_deadline_at`, and `started_at`. Compare them before changing anything: a timeout means the frozen limit was too small for the work, not that the scheduler stopped the task early. The limit is selected once, when the task enters RUNNING, from the peak or off-peak window configured on the Configuration page. Raising the peak or off-peak value affects tasks that start after the change, not the task that already timed out.

### Missing logs

If the container is gone, the log view falls back to the raw log chunks persisted during execution, so a finished or failed task keeps its output. A task that failed before any output was captured has nothing to show. For failed and cancelled tasks the archived harness copy may append a safe provider error line, and repeated certificate noise is collapsed into a suppression marker rather than left in the output.

Stored logs and error messages are sanitized before they are written: GitLab personal access tokens and Anthropic API keys are masked, so a log excerpt is safe to paste into a ticket but may therefore be incomplete.

### Retrying

A task can be retried only from **Failed** or **Cancelled**. The retry creates a new task with `is_retry` set and a reference to the original one, and it starts from **Pending**; the original keeps its error state, which makes the pair easy to compare. A second retry is refused while an active retry of the same task already exists.

## Container and scheduling anomalies

Worker containers are named from the configured container prefix plus the task and issue ids, in the form `{prefix}-{task_id}-issue{issue_id}`; the prefix defaults to `codify`. Everything below depends on that mapping between a container and a task.

### The Monitor page

**Monitor** reports the alignment between running tasks and live containers. Its two headline counts are **Orphan containers** — running containers without a matching running task — and **Task/container gaps** — running tasks with no visible running container. When a Docker target cannot be reached, the page warns that some Docker targets are unavailable and names the failing target instead of silently reporting zero containers.

Each container row shows its **Relation**:

| Relation | Meaning |
| --- | --- |
| **Linked** | A running container maps to a running task |
| **Unmapped** | The container carries no task mapping |
| **Task missing** | The container's task is not in the latest sample |
| **Container outlived task** | The container still runs while its task is no longer running |
| **Task still marked running** | The task is running but its container is not |
| **Historical** | A finished container kept for reference |

The page derives these from separate task and container samples, so a mismatch can be a transient sampling artifact. If a gap or an orphan persists across refreshes, the scheduler process is not running or cannot reach the daemon: the scheduler owns reconciliation, and nothing in the UI stops containers directly.

### What the scheduler does on restart

Crash recovery runs at scheduler startup and reconciles the database against the actual containers:

- A task still running with a live container is resumed.
- A task still running whose container is confirmed absent is terminalized — as cancelled when a cancellation was requested, otherwise failed with the restart message.
- A container with no matching task is removed as an orphan; the container's state decides whether the removal is forced.
- When a Docker target is unreachable, recovery for its tasks is deferred and retried in the background; the tasks stay running in the meantime.

A finished task that still holds a container reference blocks its issue until the container is reconciled. If an issue stays locked with nothing running, look for that retained container rather than assuming the queue is broken.

### Task stuck in Pending or Queued

**Pending** means the task has not been promoted for this cycle. **Queued** means it is promoted and waiting for capacity. Check, in order:

1. Is the scheduler process running, and is its health endpoint reporting the expected execution mode?
2. Is the task's scheduled time in the future? A scheduled task remains pending until its window opens.
3. Is the issue already holding a running task? The scheduler serializes work per issue.
4. Is **Max Concurrency** saturated by other projects, and is the hourly slot full when **Enforce Slot Limit** is on?
5. Was the task parked because its worker runtime is unavailable? That transition is recorded and the task returns to pending until the runtime is healthy.
6. Is a usage limit exceeded? The task fails at execution rather than waiting in the queue.

### Scheduled time rejected

When a schedule is refused, the error name tells you which rule applied: earlier than the previous task's floor, later than the next task's ceiling, no valid window for the issue queue, or a lineage mismatch when the selected session does not belong to the issue's current tail. A sequence that needs manual repair is reported as such — fix the issue queue before scheduling again.

### Cancelling a stuck task

Cancellation is confirmed before the task leaves the active state. If the worker container has not been published yet, or the Docker daemon is unavailable, or the container state cannot be determined, the request returns a message saying the cancellation was recorded but the task remains active. Retry the cancellation once the container state is known; do not assume the task stopped.

### Reading the deployment

The operational checks in `docs/ops/DEPLOYMENT.md` cover the same ground from the host:

```bash
cd deploy
docker-compose logs -f backend
docker-compose logs -f scheduler
```

```sql
SELECT id, status, error_message FROM tasks ORDER BY id DESC LIMIT 10;
```

```sql
SELECT task_id, level, message, created_at FROM task_logs ORDER BY id DESC LIMIT 20;
```

Keep both backend and scheduler on the same image. They share it, and a rollout that restarts only one of them can leave the two processes running different code.

## Permission and login problems

### The dashboard refuses access

An expired or revoked session returns to the sign-in page with an explanation: the session expired, the session was revoked, or access was denied for the required permissions. Signing in again resolves the first two. If a permission was revoked, the action itself is what needs to change — a platform user cannot reach an admin page.

Two page-level causes are worth checking before assuming a bug:

- The read-only pages **Monitor**, **Schedule Overview**, **Analytics**, and **OIDC Diagnostics** are admin-only until the matching switch under **Shared Page Access** is enabled for platform users.
- A disabled account is rejected on every request, with the message that the dashboard account is disabled. Re-enable the account on **Access Management** if that was not intended.

### OIDC sign-in fails or loops

Start with the **OIDC Diagnostics** checks rather than the environment files. They run against the effective configuration and report **OK**, **Warning**, or **Error** per item:

| Symptom | Likely cause reported by the diagnostics |
| --- | --- |
| **OIDC login is disabled** when opening the sign-in route | **Enable OIDC Login** is off; the dashboard is in bypass mode |
| Discovery check fails | The issuer URL is unreachable or does not serve discovery metadata |
| An endpoint check fails | The discovery document is missing or has an invalid authorization, token, or userinfo endpoint |
| Redirect URI check warns | The redirect URI does not end with `/api/auth/callback` |
| Sign-in completes at GitLab but no session is created | Redirect URI or scheme does not match the registered application, or cookie policy conflicts with it |
| Cookies are dropped in local testing | `COOKIE_SECURE=true` with an `http` redirect URI |
| Session lost on every request | `Cookie SameSite` set to `none` without secure cookies |

The diagnostics also warn when the session TTL is longer than 24 hours, and when group-based admin bootstrap is enabled while GitLab does not return groups in the claims or userinfo response. The OAuth application must allow the scopes `openid profile email read_api`; the **Required scopes** section lists them and the authorization URL preview shows the request that will be sent.

If OIDC configuration worked before and stopped after a redeploy, check whether the database volume and the encryption key both survived. Persisted secrets are only readable with the same key that wrote them; a changed key makes every stored secret undecryptable, and the fix is to enter the secrets again.

### Group-based admin access does not apply

Administrators are granted by username or by GitLab group. Group grants only work when the login response actually carries groups; otherwise the grants silently do not apply and the condition is logged with the breakdown of where groups were expected. Verify with the diagnostics warning and with the identity provider's scope and claim configuration.

### The emergency administrator path

Break-glass login is enabled only when all three environment values for it are present. When it is not fully configured, the request is refused and the sign-in page states that break-glass login is not enabled. When it is enabled, the sign-in page warns that it must be used only for OIDC recovery or administrator lockout. The emergency account is created on first successful use and is marked with the **Break-glass** role source; a username that already belongs to a different dashboard user is rejected as a conflict instead of being taken over.

Keep the path disabled during normal operation. It exists so that a broken OIDC configuration cannot lock every administrator out, and it should be closed again as soon as normal sign-in works.

## Frequently asked questions

**Why is a task still Pending while the queue is empty?**
The scheduler has not promoted it. Check that the scheduler process is running and healthy, that the scheduled time has arrived, and that the issue does not already own a running task.

**Why did a failed task produce no container logs?**
The container is gone, so the log view falls back to the raw chunks captured while it ran. A task that failed before its container started has nothing to show; its reason is in the error message instead.

**Why can I not delete an AI provider?**
The last remaining provider cannot be deleted, and a provider referenced by a pending, queued, or running task cannot be deleted. Delete is also blocked when removing the default provider would leave no enabled provider to promote.

**Why can I not delete a Worker Profile?**
A profile must be disabled first, must not be the default, and must not be assigned to any issue. A profile with open issues must be force-disabled, which closes those issues.

**Why can I not disable a Worker Profile?**
While the profile is assigned to open issues, plain disable is refused. Force disable closes those issues and disables the profile in one step.

**Why did my configuration change not affect an existing task?**
Task execution is frozen in a Task Snapshot and Runtime Bundle at creation time. Profile edits, shared script changes, Skill changes, and provider changes apply only to tasks created afterwards.

**Why can a platform user not open Monitor?**
The page is admin-only until **Allow Monitor for platform users** is enabled under **Shared Page Access**. The same applies to Schedule Overview, Analytics, and OIDC Diagnostics.

**Why is a project flagged as Needs attention in the webhook overview?**
Its hook is missing, or it is missing SSL verification, merge request events, or pipeline events. Re-run the project webhook setup, then refresh the statuses.

**Why did a task fail instead of waiting for its quota window to reset?**
Quota is checked when the task is created and again before execution. An exceeded limit does not delay the task; it rejects creation, or fails the queued task before a container starts.

**Can a deleted task be restored?**
No. Data deleted before the coverage start cannot be recovered, deleted records appear as sanitized snapshots without detail links, and cleanup removes the task's logs, archives, and workspace. Treat cleanup as irreversible.
