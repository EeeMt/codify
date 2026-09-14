---
title: Admin Governance
section: Admin Guide
tier: core
---

## Access management and roles

**Access Management** (`/access-management`) lists every dashboard user with the current role, state, session activity, and last sign-in. The page subtitle lists what it covers: managing dashboard users, explicit admin overrides, disabled accounts, and active sessions.

### Roles, sources, and states

A dashboard user has exactly one role, `platform_admin` or `platform_user`, shown as **Platform admin** and **Platform user**. The state is either **Active** or **Disabled**. The page groups users into **Known Users**, **Platform Admins**, and **Disabled Users**, and shows where the role came from:

| Source | Meaning |
| --- | --- |
| **Bootstrap** | Granted by the admin username or admin group rule on the Configuration page |
| **Manual override** | Set explicitly on this page |
| **Break-glass** | The environment-controlled emergency administrator account |

Two rules apply here: **Manual role changes override bootstrap username/group rules for that user. Disabling a user immediately revokes their active sessions.** Once a role is set manually, later logins no longer recompute it from the bootstrap lists.

The first administrator is created by the bootstrap flow on a fresh installation. Later administrators normally come from the OIDC bootstrap rules under **Admin Usernames** and **Admin GitLab Groups** on the Configuration page.

### Changing access

Use **Filter by role** and **Filter by state**, or search by username, display name, or email. Each row shows the role selector, the state selector, **Active sessions**, and **Last seen**, and marks you with **Current user**.

- **Save access** applies the role and state in one operation.
- **Revoke sessions** invalidates every active session of that user immediately; the row reports how many sessions were revoked, or that none were found.
- Your own row is read-only: **Your own role and state are read-only here to avoid accidental lockout.** Change your own role from another administrator's session, and use the normal logout flow for your own session instead of revoking it here.

Two guards protect the platform from losing its administration:

- The last active platform admin cannot be demoted or disabled. The request is refused so that an administrator can always sign in.
- Disabling an account revokes its sessions in the same transaction, and an already-issued session is rejected on its next request with the message that the dashboard account is disabled.

## Usage management

![Quota stops work twice: at creation and before the run](assets/diagrams/en/quota-gates.svg)

> [!warning] **Quota checks happen twice**: the creation check prevents a Task from being stored, while the pre-run check prevents an over-limit Task from claiming a Worker. When a request is refused, identify whether the task or token window is full.

**Usage Management** (`/usage-management`) shows system defaults and per-user usage, and manages quota overrides. The page intro explains the model: **Usage is tracked at task granularity. Limits can inherit, override, or be set to unlimited.**

### Quotas and modes

Four dimensions are tracked for every user:

| Dimension | Window |
| --- | --- |
| **Daily tokens** | Current business day |
| **Weekly tokens** | Current business week, starting Monday |
| **Daily tasks** | Current business day |
| **Weekly tasks** | Current business week, starting Monday |

Usage is recorded when a task finishes, so a task counts against the window it completed in. The page shows the current totals and the **Daily reset** and **Weekly reset** timestamps for the next boundary.

Each dimension is configured independently, with a system default and an optional per-user override:

- **Inherit** (per-user only) uses the system default for that dimension.
- **Custom** uses a positive numeric limit that you provide. Saving a custom mode without a positive value is refused.
- **Unlimited** removes the limit for that dimension; the UI displays **Unlimited**.

System defaults offer only **Custom** and **Unlimited**. Overrides accept all three modes.

### Where limits are enforced

The refusal is the same in both places: the structured reason `usage_limit_exceeded`, naming each exceeded dimension with its used value, limit, and reset time. A task that fails at start keeps that reason on its own record, so a retry or a support ticket can quote it.

The check is a strict comparison against the recorded total, so a window at exactly its limit still allows work; the next task that pushes the total over the limit is blocked.

The header shows the signed-in user's current status: **Usage within limits**, **Usage nearing limits** when any dimension has reached 80 percent of its limit, and **Usage over limits** when a limit is exceeded.

### Reading the page

**System defaults** is the first card; **User overrides** lists every tracked user. The summary counters are **Tracked Users**, **Users with Overrides**, and **Users Over Limit**, and the filter switches between all users, users with overrides, and users without overrides. Rows whose override differs from the default are tagged **Overridden**. Use **Save defaults** for the system card and **Save override** for an individual user.

## System statistics

**System Statistics** (`/system-statistics`) reports operational statistics across the full system lifecycle: retained data plus data archived through the standard deletion paths since the coverage start. It is a reference view for operations, not a billing, audit, or capacity basis.

The page has a **Refresh** action and shows the last refresh time and the reporting timezone (Asia/Shanghai).

### Current running state and lifetime totals

**Current Running State** is a live snapshot computed from the current business tables: **Pending**, **Queued**, **Running**, **Long Running**, **Active Issues**, **Avg Queue Wait**, and the number of **Samples** behind that average.

**Lifetime Cumulative** combines retained data with data archived through the standard deletion paths: **Total Tasks**, **Total Issues**, **Completed**, **Failed**, **Cancelled**, **Finished**, **Success Rate**, **Failure Rate**, **Issues with MR**, **Known Tokens**, **Known Code Changes**, **Known Execution Time**, **Avg Execution Time**, **Execution Samples**, **Deleted Tasks**, **Deleted Issues**, and **Deleted Before Terminal**.

### Coverage, trends, and breakdowns

**Data Coverage** reports how complete the token and code-change records are among eligible finished tasks: **Eligible**, **Complete**, **Partial**, **Missing**, **Recorded**, and **Coverage Rate**. Unknown values are excluded from averages and totals and shown separately here, so a lifetime total can be lower than the sum of individual runs.

**Basic Trends** buckets counts in the reporting timezone: tasks created, tasks finished, tasks deleted, and issues created. **Basic Breakdown** groups lifecycle metrics by project, provider, harness, and task mode, with the largest groups shown when a dimension has many values.

### Retained versus deleted data

Two selectors narrow the scope:

- **Trend time range**: **All**, **Last 90 days**, or **Last 1 year**.
- **Data state**: **All**, **Retained**, or **Deleted**.

Deleted data is only included after the deletion coverage guarantee is enabled for your installation. Until that point the page reports **Deletion coverage guarantee is not enabled yet** and states that deleted data is not included; data deleted before the coverage start cannot be recovered.

Deleted records are shown as sanitized snapshots only and provide no detail links, so a deleted task can never be opened from this page.

## Data cleanup

**System Data Cleanup** on the **Maintenance** tab deletes old issue-scoped system records together with their task data.

Two inputs control the operation:

- **Clean data older than N days**: required, minimum `1` day. The cutoff is applied to the age of the issue, not to the age of its tasks.
- **Force cleanup active tasks**: when enabled, also deletes pending, queued, and running tasks when their state is stale. A warning is shown while it is on: **Force cleanup deletes active task records and attempts to stop running containers.**

**Clean system data** asks for confirmation first. Without force, the confirmation is **Clean eligible issue data? This cannot be undone.**; with force it is **Force clean eligible issue data, including active tasks? Running containers will be stopped best-effort.**

What the operation does:

- Issues older than the cutoff with no active task are deleted, along with their tasks and the task-scoped records that belong to them.
- Issues that still have active tasks are skipped, and the count of skipped issues is reported. Their data is left untouched.
- With force enabled, the running containers of the selected tasks are stopped and removed on a best-effort basis. A container that cannot be stopped causes its issue to be skipped rather than deleted.
- Issue workspaces and run archives for the deleted records are cleaned up; an archive file that is already missing is counted rather than treated as an error.

The result is reported as `Cleanup finished: {issues} issue(s), {tasks} task(s) deleted, {skipped} active issue(s) skipped.` Configuration and file cleanup problems are collected and returned with the response instead of aborting the whole run, so a partial cleanup should be re-run after the reported cause is fixed.

## Maintenance

The **Maintenance** tab holds two page-wide actions under **Actions**. Its subtitle says they reload the current values or reset every section back to env or defaults.

- **Reload** re-reads the effective configuration and discards nothing else.
- **Reset to env/defaults** deletes every persisted override across all sections, returning every value to its installation default. It first asks **Reset all configuration sections to their environment variable / default values? Unsaved changes will be lost.** The summary tags on the configuration page then show **env fallback** or **default fallback** instead of **DB override**.

Some values are set when Codify is installed and are deliberately not editable here. The worker workspace path is fixed at installation time, and the key material used to encrypt stored secrets must not change. A reset that returns secret fields to their stored installation values is the supported way to recover when a persisted secret can no longer be decrypted; if the encryption key itself changed, every stored secret must be entered again.
