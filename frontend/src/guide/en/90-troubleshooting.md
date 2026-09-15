---
title: Platform troubleshooting
section: Admin Guide
tier: core
---

## Platform triage path

Record the Task id, Issue id, Worker, Docker target, and time. Collect evidence in this order: **Error card**, **Events**, **Raw Logs**, then the runtime archive.

![Platform triage starts at the Error card, then checks events, logs, and the runtime archive](assets/diagrams/en/failure-triage.svg)

> [!warning] Preserve the container, workspace, and archive before cleaning anything. Delivery and restart problems often depend on those records.

| Symptom | Check first |
|---|---|
| protocol_error | Canonical events, raw Harness events, and process exit code |
| worker_runtime_unavailable | Task Snapshot's Worker Kit, Runtime Bundle, and Docker target |
| harness_cli_unavailable | Whether the Kit inventory contains the frozen Harness CLI |
| worker_runtime_check_failed | Profile Kit path, image, mounts, and Harness selection |
| execution_contract_mismatch | Task Snapshot, attempt schema, and Runtime Bundle identity |
| Worker failed to start | Docker target, image, mounts, and entrypoint |
| Code delivery was not confirmed | Remote branch before and after push, bot access, and delivery result |

Stored errors and logs are sanitized, including tokens matching glpat-* or sk-ant-*. The sanitized record is suitable for support, but it is not the original byte-for-byte output.

## Worker, container, and scheduling checks

Monitor separates queue, container alignment, and health. A mismatch that disappears on refresh may be sampling lag; a persistent mismatch needs investigation.

| Signal | Meaning | First admin action |
|---|---|---|
| Running Task has no container | Task/container gap | Check target reachability, inventory, and Task events |
| Running container has no Task | Orphan candidate | Confirm the Task did not just finish, then apply cleanup policy |
| Task is Running but container exited | Recovery gap | Preserve exit details and archive; let recovery finalize the Task |
| Container outlived its Task | Finalization or cleanup is still running | Check the Task timeline and target |
| Docker target unavailable | The target could not be sampled | Restore the connection; do not interpret it as zero containers |

For a Task stuck in **Pending** or **Queued**, check schedule, Issue predecessor, Max Concurrency, slot capacity, Worker Runtime, and scheduler health. Only an Issue head competes for dispatch.

## Platform restart and state reconciliation

After a restart, recovery compares the durable Task record with the container:

1. A live container for a Running Task is adopted and its events continue.
2. An exited container is drained and its result finalizes the Task.
3. A container without a matching running Task is cleaned as an orphan.
4. A Running Task whose container is gone becomes **Failed**, or **Cancelled** when cancellation was already requested.
5. An unreachable Docker target keeps its Tasks owned while recovery retries.

Recovery does not reorder turns. If an Issue stays locked, check for a retained container or unfinished finalization before changing state. Missing started time, timeout data, or turn sequence is a data-consistency issue; preserve the record and archive while repairing it.

## Sign-in, OIDC, and encryption keys

Start sign-in investigations in **OIDC Diagnostics**. Check discovery, endpoints, redirect URI, required scopes, and cookie policy. The OAuth application needs openid, profile, email, and read_api, and group bootstrap needs groups in claims or userinfo.

Common warnings are a redirect outside /api/auth/callback, an HTTP and Cookie Secure mismatch, SameSite=None without secure cookies, an overlong session TTL, or group bootstrap without groups.

If a secret cannot be decrypted, verify that CONFIG_ENCRYPTION_KEY or the non-default SESSION_SECRET is the same key used to encrypt it. Restore the original key or enter the secrets again. Use break-glass login only for OIDC recovery or administrator lockout, then disable it.

## Configuration, providers, and cleanup

Task identity is frozen at creation. Compare the Task Snapshot with current Worker, Provider, Harness, Skills, Run Instruction, and Runtime Bundle settings before assuming a configuration edit was ignored.

Provider deletion is guarded by active Tasks, the default Provider, and the last enabled Provider. A Worker Profile must be disabled and unused before deletion. Force-disabling a Profile closes its open Issues.

Use [Admin Governance](/guide/85-admin-governance) for historical cleanup and enable force cleanup only when the active Task state is known to be stale. Use [Worker Runtime](/guide/92-worker-runtime) for paths, mounts, Harness state, and scratch space. Revalidate the Profile after changing an image or Kit.
