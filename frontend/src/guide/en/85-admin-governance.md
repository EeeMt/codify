---
title: Admin Governance
section: Admin Guide
tier: core
---

## Access management and roles

**Access Management** at /access-management lists dashboard users, their role, state, active sessions, and last sign-in.

### Roles, sources, and states

Users have one role, **Platform admin** or **Platform user**, and one state, **Active** or **Disabled**.

| Role source | Meaning |
|---|---|
| **Bootstrap** | Granted by the configured admin username or group |
| **Manual override** | Set explicitly in Access Management; it wins over bootstrap |
| **Break-glass** | Deployment-controlled emergency administrator |

Disabling a user revokes their active sessions. The last active platform admin cannot be demoted or disabled.

### Changing access

Filter or search the table, change the role or state, and select **Save access**. **Revoke sessions** invalidates every active session for that user. Your own role and state are read-only on your own row; use another administrator's session to change them.

## Usage management

![Quota stops work twice: at creation and before the run](assets/diagrams/en/quota-gates.svg)

**Usage Management** shows system defaults and per-user overrides. Quotas are checked when a Task is created and again before it starts, so a Task can be stored successfully and still be stopped later if the window is full.

### Quotas and modes

| Dimension | Window |
|---|---|
| Daily tokens | Business day |
| Weekly tokens | Business week, starting Monday |
| Daily tasks | Business day |
| Weekly tasks | Business week, starting Monday |

Usage is recorded when a Task finishes. System defaults use **Custom** or **Unlimited**. A user override can also **Inherit** the system value. Custom limits must be positive.

### Where limits are enforced

The structured reason is usage_limit_exceeded. It names the exceeded dimension, current use, limit, and reset time. The comparison is strict, so a total exactly at the limit is still allowed; the next task that exceeds it is blocked.

### Reading the page

**System defaults** is the platform baseline. **User overrides** lists per-user changes and shows users over limit. Save the relevant card after changing it.

## System statistics

System Statistics at /system-statistics is a lifecycle report, not a billing or audit source. It combines retained data with snapshots created by the standard deletion path and shows the reporting timezone.

### Current running state and lifetime totals

**Current Running State** is a live view of Pending, Queued, Running, Long Running, Active Issues, and average queue wait. **Lifetime Cumulative** includes task and Issue totals, outcomes, MRs, known tokens, code changes, execution time, and deletion counters.

### Coverage, trends, and breakdowns

**Data Coverage** shows how many eligible finished Tasks have complete or partial token and code-change data. Unknown values stay out of averages and totals.

**Basic Trends** groups created, finished, deleted Tasks and created Issues by day. **Basic Breakdown** groups lifecycle data by project, Provider, Harness, and Task Mode.

### Retained versus deleted data

Use **Trend time range** and **Data state** to select all, retained, or deleted data. Deleted records appear as sanitized snapshots without detail links. If the deletion coverage guarantee is not enabled, the page excludes deleted data and says so.

## Data cleanup

**System Data Cleanup** deletes old Issue-scoped records and their Task data.

- **Clean data older than N days** uses the Issue age, not the age of individual Tasks. N must be at least 1.
- Without force, Issues with active Tasks are skipped.
- **Force cleanup active tasks** also targets pending, queued, and running Tasks and tries to stop their containers. A container that cannot be stopped causes its Issue to be skipped.
- Deleted workspaces and runtime archives are cleaned up best effort. Missing archive files are reported, not treated as a reason to stop the whole operation.

The action is irreversible and asks for confirmation. The result reports deleted Issues and Tasks, skipped active Issues, and cleanup errors. Fix reported causes before running it again.

## Maintenance

The **Maintenance** tab provides:

- **Reload**, which reads the effective configuration again.
- **Reset to env/defaults**, which removes every persisted override, including stored secret overrides, after confirmation. Environment values or built-in defaults apply again; Tasks and user records are not deleted.

The Worker workspace host path, encryption root key, Worker Kit installation, and database structure are deployment concerns. Keep the encryption key stable and revalidate Worker Profiles after changing a Kit or image.
