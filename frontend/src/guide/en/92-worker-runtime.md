---
title: Worker Runtime
section: Admin Guide
tier: deep
---

## Worker filesystem

Every Docker host that runs tasks keeps one directory tree per Issue under a root path that is fixed at deployment time. The tree holds what has to survive a container: the checkout, the Harness state that carries over between Tasks, and the bookkeeping that guards cleanup. Evidence from a single run stays inside the container and is discarded with it. The layout below concerns whoever provisions a Docker host or a Worker Profile, and anyone tracing where a session or a run archive is stored.

### Host layout

The root is `worker_workspace_host_path`, read from `WORKER_WORKSPACE_HOST_PATH` and defaulting to `/opt/codify-workspaces`. It must exist at the same path on every Docker host. Codify keeps one directory per Issue inside it:

```text
{worker_workspace_host_path}/project-{project_id}/issue-{issue_id}/
  repo/
  claude/
  shared/
  meta/
```

The Configuration page cannot change the path. Changing it means updating `WORKER_WORKSPACE_HOST_PATH` and recreating Backend and Scheduler.

### Container mounts

A Task does not see the whole workspace directory. It mounts four of its children, all read-write, and all four outlive the container:

| Container path | Host source | What it holds |
| --- | --- | --- |
| `/workspace` | `repo/` | The checkout, including the commits earlier Tasks left behind |
| `/home/codify/.claude` | `claude/` | Claude CLI state: session transcripts, settings, and backups |
| `/opt/codify-issue-shared` | `shared/` | Issue-shared space, including the state directories other Harnesses keep there |
| `/opt/codify-issue-meta` | `meta/` | Root-owned bookkeeping: `workspace.json`, the `ownership` marker, and the `owner` delete guard |

Every Task on an Issue uses the same mount set, so a follow-up Task starts from the previous checkout and session instead of cloning again.

### Where each Harness keeps its state

The four mount paths are fixed, but each Harness puts its own home, config, cache, and session directories on a different one of them, and only Claude uses the `claude/` mount.

| Harness | Kept across Tasks | Built again for each run |
| --- | --- | --- |
| Claude | `/home/codify/.claude`, the `claude/` mount: session transcripts, settings, and the backup that `.claude.json` is restored from | `/home/codify/.claude.json` and the per-run prompt file |
| Codex | `CODEX_HOME` on the `shared/` mount, `/opt/codify-issue-shared/codex-home`: `config.toml`, `execpolicy.rules`, session transcripts, and `.agents/skills` | `codex-home` under `/tmp/codify-runtime`, used when the `shared/` mount is unavailable |
| Pi | `PI_HOME` on the `shared/` mount, `/opt/codify-issue-shared/pi-home`, holding `sessions/` | `/home/codify/.pi/agent`: `models.json`, `settings.json`, agent definitions, extensions, and skills |
| OpenCode | `XDG_DATA_HOME` on the `shared/` mount, `/opt/codify-issue-shared/opencode-data`, holding the session store | `HOME`, `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, and `XDG_STATE_HOME` under `/tmp/codify-runtime/opencode` |

`/home/codify` itself is not a mount. Only its `.claude` subdirectory survives the container, so anything a Harness keeps elsewhere under that home directory is rebuilt on the next run.

### Worker Kit

With **Runtime delivery** set to **Mounted worker kit**, Codify mounts the kit read-only at `/opt/codify-kit` and its `nix/store` at `/nix/store`, then starts the container through `/opt/codify-kit/launcher` as root. Kits live on the host under `/opt/codify/worker-kits/<content-addressed name>`, a root-owned directory that other users cannot write to.

**Profile volume mounts** cannot hide `/workspace`, `/home/codify/.claude`, or `/opt/codify-issue-shared`, and cannot enter the sealed `/opt/codify-issue-meta` or `/tmp/codify-runtime` paths. The same rule protects the kit mounts at `/opt/codify-kit` and `/nix/store`.

### Per-run scratch

`/tmp/codify-runtime` exists inside the container only. Codify creates it for each Task and discards it with the container when the run ends. It holds the evidence the run produces:

- `event.jsonl`, the canonical event stream, plus the raw per-harness streams under `harness-events/`
- `console.log` and the harness result `harness-result.json`
- `artifacts/`, the staging area for user artifacts
- `orchestration/`, the frozen Runtime Bundle uploaded before the run starts

The runtime archive is built from this directory as the container exits, and the Backend streams it to the archive store at `/opt/codify-archives`.

### Lifetimes and reclamation

| Item | Setting | Default | Reclaimed |
| --- | --- | --- | --- |
| Issue workspace | `worker_workspace_retention_days` | 14 days, `0` disables cleanup | Once no active Task owns the Issue and the directory has not been used within the window |
| Runtime archives | `worker_runtime_archive_retention_days` | 30 days | By archive record age |
| CI failure bundles | `worker_workspace_retention_days` | 14 days | By bundle age under `{worker_workspace_host_path}/ci-failures` |

The workspace timestamp is refreshed when a Task is created and again when it finishes or is cancelled, so an Issue in use is not reclaimed. Workspace reclamation goes through a short-lived maintenance container that mounts the workspace root and reads `meta/owner`; the directory is deleted only if that marker still names the Issue and its Worker Profile. The scheduler runs the workspace scan every 6 hours and the archive scan hourly. Scheduler crash recovery cleans up orphan containers from an interrupted run and leaves workspaces alone.
