---
title: Worker Runtime
section: Admin Guide
tier: deep
---

## Worker filesystem

Each Docker host keeps one persistent directory per Issue. The directory contains the checkout, cross-Task Harness state, and cleanup metadata. A run's evidence lives in the container scratch directory and is archived before the container is removed.

### Host layout

The root is `WORKER_WORKSPACE_HOST_PATH`, exposed as `worker_workspace_host_path`, and defaults to `/opt/codify-workspaces`. It must use the same path on every Docker host.

~~~text
{worker_workspace_host_path}/project-{project_id}/issue-{issue_id}/
  repo/
  claude/
  shared/
  meta/
~~~

The Configuration page cannot change this path. Change the environment value and recreate Backend and Scheduler.

### Container mounts

Every Task on an Issue receives these four read-write mounts:

| Container path | Persistent content |
|---|---|
| `/workspace` | Checkout and commits from earlier Tasks |
| `/home/codify/.claude` | Claude session and CLI state |
| `/opt/codify-issue-shared` | Shared Issue state, including other Harness directories |
| `/opt/codify-issue-meta` | `workspace.json`, ownership, and delete-guard metadata |

The mounts survive the container, so a follow-up Task reuses the checkout and session.

### Where each Harness keeps its state

| Harness | Kept across Tasks | Rebuilt for each run |
|---|---|---|
| Claude | `/home/codify/.claude` | `.claude.json` and the run prompt |
| Codex | `CODEX_HOME` under `shared/codex-home` | Fallback home under `/tmp/codify-runtime` |
| Pi | `PI_HOME` under `shared/pi-home/sessions` | Agent settings and Skills under `/home/codify/.pi/agent` |
| OpenCode | `XDG_DATA_HOME` under `shared/opencode-data` | HOME and XDG directories under `/tmp/codify-runtime/opencode` |

Only the Claude subdirectory is mounted directly under `/home/codify`. Other files under that home are rebuilt.

### Worker Kit

Mounted Worker Kits are read-only at `/opt/codify-kit`, with the Kit's Nix store at `/nix/store`. The container starts through `/opt/codify-kit/launcher`. Kits are installed on the Docker host under a content-addressed directory.

### How the Worker image, Kit, and Runtime Bundle fit together

These three artifacts make up a Task's execution environment, but they are separate:

| Artifact | What it provides | Role in a Task |
|---|---|---|
| Worker image | Operating system and project toolchains such as Java, Maven, or Playwright | Base environment for the container |
| Worker Kit | Launcher, Nix runtime tools, and Harness CLIs available in the Kit inventory | Validates execution identity and starts orchestration; provides tools to scripts and Harnesses |
| Runtime Bundle | Codify's orchestration entrypoint, Harness Adapters, and Bridges | Defines Codify's repository preparation, Harness invocation, and event handling |

At Task creation, Codify freezes a Task Snapshot and binds the Worker image, Kit, and Runtime Bundle identities. At execution, the Backend creates a container from the frozen Worker image and mounts the Kit and Bundle. The Kit launcher validates the Kit manifest, Bundle digest, and contract compatibility before running the Bundle entrypoint. That entrypoint uses the Kit's runtime tools and invokes the selected Harness Adapter and CLI; the CLI comes from the Kit inventory or a read-only mount configured in the Profile. The Harness works in `/workspace`, and runtime events flow back to Codify.

![Roles and startup sequence for the Worker image, Kit, and Runtime Bundle](assets/diagrams/en/worker-runtime-bundle.svg)

As a result, changing orchestration scripts in a Bundle normally requires building and binding a new Bundle; changing the launcher, Nix tools, or a Kit-provided CLI requires a new Worker Kit release. The frozen identities and contracts connect the two, while existing Tasks keep their original bindings.

Profile volume mounts cannot hide the workspace, Harness-state, metadata, scratch, Kit, or Nix-store mounts. These guards prevent a profile from replacing the runtime or another Issue's state.

### Per-run scratch

`/tmp/codify-runtime` exists only inside the container and is recreated for every Task. It holds the normalized event stream, raw Harness events, console log, Harness result, user artifacts, and the frozen orchestration bundle. On exit, the archive is built from this directory and sent to `/opt/codify-archives`.

### Lifetimes and reclamation

Retention comes from Configuration and may differ by installation:

| Item | Setting | Reclaimed when |
|---|---|---|
| Issue workspace | `worker_workspace_retention_days` | No active Task owns it and it has been idle for the retention window |
| Runtime archive | `worker_runtime_archive_retention_days` | Its archive record is older than the retention window |
| CI failure bundle | Workspace retention | Its bundle is older than the retention window |

Workspace use is refreshed when a Task is created, finished, or cancelled. Cleanup checks the `meta/owner` marker and refuses to delete a directory owned by another Issue or Profile. The scheduler scans workspaces every six hours and archives hourly. Crash recovery cleans orphan containers but does not delete workspaces.
