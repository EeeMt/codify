---
title: Platform reference
section: Admin Guide
tier: deep
---

## Start with the source of truth

This page collects boundaries that can change with a release or deployment, so the same value does not have to be repeated across the guide. During an incident, use the current Configuration page, the Task snapshot, and the runtime validation result as the source of truth. The tables below describe supported ranges and installation defaults, not the current value of every instance.

| What you need to check | First place to look | Why |
|---|---|---|
| Current timeout, capacity, and retention | **Configuration** | A database override may replace the environment and built-in default |
| The value a Task actually used | **Task Snapshot** on the Task page | It is frozen at creation or execution and is not rewritten by later edits |
| Worker Kit, image, and Harness | **Worker** runtime validation and the Task snapshot | The identity changes with the Profile, host, and Runtime Bundle |
| Host paths and keys | Deployment environment and the host | The page does not expose every deployment constraint |

## Capacity, timeouts, and retention

| Setting | Built-in default | Supported range or rule |
|---|---:|---|
| `MAX_CONCURRENCY` | `3` | `1` to `20`; maximum tasks running at once |
| `TASK_TIMEOUT_PEAK_SECONDS` | `1800` seconds | From 60 to 28800 seconds; frozen when the Task enters RUNNING |
| `TASK_TIMEOUT_OFF_PEAK_SECONDS` | `3600` seconds | From 60 to 28800 seconds; frozen when the Task enters RUNNING |
| `TASK_TIMEOUT_PEAK_START` / `END` | `09:00` / `18:00` | Business-timezone `HH:mm`; start inclusive, end exclusive |
| `SCHEDULER_INTERVAL` | `5` seconds | `1` to `60` seconds; scheduler polling interval |
| `worker_workspace_retention_days` | `14` days | `0` to `365` days; `0` disables ordinary workspace cleanup, which only reclaims idle, unowned workspaces |
| `worker_runtime_archive_retention_days` | `30` days | `1` to `3650` days; cleanup by archive-record age; Task records remain |
| `SLOT_MAX_TASKS` | `0` | `0` to `100` per-hour capacity; `0` means unlimited |
| `SLOT_MAX_TASKS_ENFORCE` | `false` | A full slot rejects creation when enabled; otherwise it warns |

The timeout policy uses the business timezone shown in Configuration. Peak or off-peak is selected once when a Task starts and does not switch at the boundary. The Task's **Execution timeout** and **Execution deadline** are the authoritative values for that run.

## Worker Kit and runtime boundaries

| Capability | Minimum condition | Note |
|---|---|---|
| Shallow clone and deferred historical file contents | Mounted Worker Kit, version `0.3.0` or newer | The Create Issue form disables the options otherwise |
| Skills | Mounted Worker Kit, version `0.3.5` or newer | Baked-image delivery does not support Skills |
| Harness | Selected in the Profile and runtime validation passes | Availability also depends on Kit inventory, Provider protocol, and Runtime Bundle |
| Worker Kit path | An absolute path on the Docker host | The task container normally mounts it at `/opt/codify-kit`; see [Worker Runtime](/guide/92-worker-runtime) |

The guide does not pin a specific Worker Kit release, image tag, or Harness binary version because those values belong to the deployment and Profile. Use the Worker configuration, validation result, and Task snapshot instead. A Runtime Bundle is immutable and derived from the frozen identity; replacing a Kit on the host does not change an existing Task.

## Archive and artifact limits

The runtime archive has a hard cap of `640 MiB`. The default artifact budget is `200 MiB` total, `100 MiB` per file, and `5,000` entries. Worker settings support total and per-file limits from `1 MiB` up to `512 MiB`, and an entry limit from `1` to `100,000`; the per-file limit cannot exceed the total. The archive hard cap still applies. When the budget is exceeded, Codify leaves out the user-artifact subtree and records the reason in `artifacts-validation.json`; the event stream and Task record remain.

Workspace cleanup and runtime-archive cleanup are independent. Cleaning a workspace does not delete a Task, and cleaning an archive does not delete a Task. Read [Admin Governance](/guide/85-admin-governance) before reviewing cleanup results or using force cleanup.
