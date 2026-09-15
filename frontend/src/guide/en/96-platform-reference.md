---
title: Platform reference
section: Admin Guide
tier: deep
---

## Start with the source of truth

Use the current Configuration page for platform values, the Task Snapshot for a Task's frozen identity, and Worker runtime validation for the runtime that can actually run.

| Question | Source |
|---|---|
| What are the current timeout, capacity, and retention values? | **Configuration** |
| What value did this Task use? | **Task Snapshot** |
| Which Worker Kit, image, or Harness is available? | **Worker** validation and the Task Snapshot |
| Where are host paths and keys set? | Deployment environment and Docker host |

The defaults below describe the current code's supported ranges. A database override may change the value on an installation.

## Capacity, timeouts, and retention

| Setting | Default | Rule |
|---|---:|---|
| MAX_CONCURRENCY | 3 | 1–20 concurrent Tasks |
| TASK_TIMEOUT_PEAK_SECONDS | 1800 seconds | 60–28800 seconds; frozen when the Task starts |
| TASK_TIMEOUT_OFF_PEAK_SECONDS | 3600 seconds | 60–28800 seconds; frozen when the Task starts |
| TASK_TIMEOUT_PEAK_START / END | 09:00 / 18:00 | Business-timezone HH:mm; start inclusive, end exclusive |
| SCHEDULER_INTERVAL | 5 seconds | 1–60 seconds |
| worker_workspace_retention_days | 14 days | 0–365 days; 0 disables ordinary workspace cleanup |
| worker_runtime_archive_retention_days | 30 days | 1–3650 days; Task records remain |
| SLOT_MAX_TASKS | 0 | 0–100 Tasks per hour; 0 means unlimited |
| SLOT_MAX_TASKS_ENFORCE | false | Full slots reject creation when enabled; otherwise warn |

Peak or off-peak is selected once when a Task enters **Running**. Use the Task's recorded **Execution timeout** and **Execution deadline** for an individual run.

## Worker Kit and runtime boundaries

| Capability | Minimum condition |
|---|---|
| Shallow clone and deferred historical file contents | Mounted Worker Kit 0.3.0 or newer |
| Skills | Mounted Worker Kit 0.3.5 or newer |
| Harness execution | Harness selected in the Profile and runtime validation passed |
| Worker Kit path | Absolute path on the Docker host, normally mounted at /opt/codify-kit |

Baked-image delivery is deprecated and does not support Skills. The actual Kit, image, and Harness versions belong to the Profile and deployment. A Runtime Bundle is immutable; replacing a host Kit does not alter an existing Task.

## Archive and artifact limits

The runtime archive has a 640 MiB hard cap. The default user-artifact budget is 200 MiB total, 100 MiB per file, and 5,000 entries. Configurable limits are 1–512 MiB for total and per-file size, and 1–100,000 entries. The per-file limit cannot exceed the total.

If the artifact budget or archive cap is exceeded, Codify omits the user-artifact subtree and records the reason in artifacts-validation.json. Events and Task records remain. Workspace cleanup and archive cleanup are independent; neither deletes the Task record.
