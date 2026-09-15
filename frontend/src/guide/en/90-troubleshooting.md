---
title: Platform troubleshooting
section: Admin Guide
tier: core
---

## Platform triage path

This page is for platform administrators and the people who operate deployments. Record the Task id, Issue id, Worker, Docker target, and time first. Then collect evidence in this order: **Error card**, **Events**, **Raw Logs**, and **runtime archive**. A retry, follow-up, or prompt correction that a user can perform on the Task page does not need platform intervention.

![Platform triage starts at the Error card, then checks events, logs, and the runtime archive](assets/diagrams/en/failure-triage.svg)

> [!warning] **Preserve the scene first:** do not delete the container, workspace, or runtime archive before recording the state. Platform restarts, missing containers, and unconfirmed delivery depend on these records.

| Error or symptom | Check first | Direction |
|---|---|---|
| `protocol_error: ...` | Whether the canonical stream, raw Harness stream, and process exit code agree | Compare the Runtime Bundle event contract and the adapter involved; keep the archive if it repeats |
| `worker_runtime_unavailable` | The Worker Kit, Runtime Bundle, and Docker target named by the Task snapshot | Restore the kit or target, revalidate the Profile, then let the Task return to scheduling |
| `harness_cli_unavailable` | Whether the Kit inventory contains the requested Harness CLI | Install or rebuild a Kit with that CLI, then revalidate the Profile |
| `worker_runtime_check_failed` | The Profile's Kit path, image, mounts, and Harness selection | Fix the runtime combination; retrying does not bypass the check |
| `execution_contract_mismatch` | Snapshot, attempt schema, and Runtime Bundle identity | Repair the Profile and Bundle combination; later Tasks get a new snapshot |
| `Worker failed to start: ...` | Docker target, image pull, mounts, and entrypoint | Keep the start error on the target and confirm whether a container was created |
| `Code delivery was not confirmed...` | The remote branch before and after push, bot access, and delivery summary | Use [Delivery Internals](/guide/75-delivery-internals) to interpret the code and decide whether to retry |

Errors and logs are sanitized before they are stored, so values such as `glpat-*` and `sk-ant-*` do not appear. The sanitized record can be shared with support, but it is not a byte-for-byte copy of the original output.

## Worker, container, and scheduling checks

The **Monitor** page's **Run Overview**, **Container Troubleshooting**, and **Health Signals** tabs answer capacity, task-container alignment, and service-health questions. Container relations come from separate task and Docker samples. A mismatch that disappears on the next refresh can be sampling lag; a persistent one is a platform incident.

| Relation or message | Meaning | Admin action |
|---|---|---|
| Task/container gap | A running Task has no visible running container | Check target reachability, the container list, and Task events before changing state |
| Orphan container | A running container has no matching running Task | Confirm that the Task did not just finish and that the target sample is current, then apply cleanup policy |
| Task still marked running | The Task is RUNNING but its container exited or disappeared | Preserve the archive and exit details; recovery will fail the Task if it cannot take over |
| Container outlived Task | A container is still running after its Task ended | Check whether finalization is in progress; persistent cases need cleanup and target checks |
| Some Docker targets are unavailable | A target could not be sampled | Do not treat that target as an empty result; restore the connection and let recovery retry |

For a Task that stays **Pending** or **Queued**, check its schedule, the predecessor on its Issue, Max Concurrency, enforced slot capacity, Worker Runtime availability, and scheduler health in that order. Only an Issue head competes for dispatch, and an Issue has one running Task at a time. When a runtime check sends a Task back to Pending, it will not continue until the runtime is healthy and the Profile has been revalidated.

## Platform restart and state reconciliation

Recovery aligns the run record with the container state:

1. A live container for a **Running** Task is adopted and its events and logs continue.
2. An exited container for a still-**Running** Task is drained, then the Task is closed with that run's result.
3. An exited container with no matching running Task is an orphan and is cleaned up without changing the Task record.
4. A **Running** Task whose container is gone ends as **Failed** with the platform-restart reason.
5. A target that is temporarily unreachable keeps its Tasks Running while recovery waits in the background.

If an Issue remains locked, look for a retained container or unfinished finalization record first. A RUNNING record without `started_at`, a missing frozen timeout, or a turn sequence that needs repair is a data-consistency problem. Keep the original record, events, and archive while repairing it or creating a replacement Task. Do not use force cleanup as a substitute for investigating state.

## Sign-in, OIDC, and encryption keys

For a sign-in loop or an unexpected admin permission result, start with **OIDC Diagnostics**. Check discovery, endpoints, redirect URI, required scopes, and cookie policy. Common warnings are a redirect URI outside `/api/auth/callback`, an HTTP and `Cookie Secure` mismatch, `SameSite=None` without secure cookies, an overlong session TTL, and group-based admin bootstrap without groups in the login response.

The GitLab OAuth application must request `openid`, `profile`, `email`, and `read_api`, and its redirect URI must match the actual access address. Group-based admin bootstrap only works when the claims or userinfo response carries groups. The switches for shared pages, Monitor, Schedule Overview, and Analytics, live under **Configuration**, **Runtime and Sharing**; OIDC Diagnostics has no platform-user switch.

If saving a secret reports an encryption error, check that `CONFIG_ENCRYPTION_KEY` or a non-default `SESSION_SECRET` is the same key that encrypted the stored value. A changed or lost root key makes stored OIDC, GitLab, Provider, and notification secrets unreadable; restore the original key or enter the secrets again. Use the break-glass administrator path only for OIDC recovery or administrator lockout, and disable it after normal sign-in works.

## Configuration, providers, and cleanup

Task creation freezes the Worker, Provider, Harness, Skills, Run Instruction, and Runtime Bundle identity. Configuration edits do not rewrite existing Tasks. When someone reports that a configuration change had no effect, compare the Task snapshot with the current configuration before investigating the scheduler.

Provider deletion is guarded by active Tasks, the default Provider, and the last enabled Provider. A Worker Profile must be disabled before deletion and cannot still be referenced by an Issue. Force-disabling a Profile closes its open Issues, so confirm the impact before using it.

Workspace, runtime-archive, and CI-failure-bundle lifetimes come from the Worker settings. The current defaults and scan intervals are kept in [Platform reference](/guide/96-platform-reference). For historical deletion, use **System Data Cleanup** in [Admin Governance](/guide/85-admin-governance); enable force cleanup only when the Task state is known to be stale, and keep the skipped and failed causes from the result.

Worker filesystem paths, mount guards, Harness state directories, and per-run scratch space are documented in [Worker Runtime](/guide/92-worker-runtime). Changes to deployment paths, images, the database, or encryption keys should happen in a maintenance window, followed by Profile runtime validation.
