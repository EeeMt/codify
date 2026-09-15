---
title: Worker 运行时
section: Admin Guide
tier: deep
---

## Worker 文件系统

每台运行任务的 Docker 主机都按部署时固定的根路径，为每个需求保留一份目录。目录里存放代码检出、跨任务保留的 Harness 状态，以及决定工作区能否被回收的记账文件；单次运行产生的证据只存在于容器内，随容器一起丢弃。这套目录布局面向准备 Docker 主机与 Worker Profile 的人员，也便于确认某个会话或某份运行归档存放在哪里。

### 宿主机目录结构

根路径由 `worker_workspace_host_path` 指定，对应环境变量 `WORKER_WORKSPACE_HOST_PATH`，默认 `/opt/codify-workspaces`；它必须在每台 Docker 主机上位于同一路径。根路径下按需求分目录：

```text
{worker_workspace_host_path}/project-{project_id}/issue-{issue_id}/
  repo/
  claude/
  shared/
  meta/
```

这些路径属于部署期配置，配置页不提供修改入口；要改只能更新 `WORKER_WORKSPACE_HOST_PATH`，并重建 Backend 与 Scheduler。

### 容器内挂载

任务只挂载需求目录下的四个子目录，全部以读写方式挂载，并在容器结束后保留：

| 容器内路径 | 宿主机来源 | 存放内容 |
|---|---|---|
| `/workspace` | `repo/` | 代码检出，含之前任务留下的提交 |
| `/home/codify/.claude` | `claude/` | Claude CLI 状态：会话记录、设置与备份 |
| `/opt/codify-issue-shared` | `shared/` | 需求内共享空间，其他 Harness 的状态目录也在这里 |
| `/opt/codify-issue-meta` | `meta/` | 记账文件：`workspace.json`、`ownership` 标记与 `owner` 删除保护标记 |

同一需求的所有任务使用同一套挂载，因此后续任务接着上一份检出与会话继续，不需要重新克隆。

### 各 Harness 的状态目录

四个挂载路径是固定的，但每个 Harness 把自己的 home、配置、缓存与会话目录指向其中不同的一个；只有 Claude 使用 `claude/` 这个挂载。

| Harness | 跨任务保留 | 每次运行重建 |
|---|---|---|
| Claude | `/home/codify/.claude`，即 `claude/` 挂载：会话记录、设置，以及用于恢复 `.claude.json` 的备份 | `/home/codify/.claude.json` 与本次运行的提示词文件 |
| Codex | `CODEX_HOME` 落在 `shared/` 挂载上，即 `/opt/codify-issue-shared/codex-home`：`config.toml`、`execpolicy.rules`、会话记录与 `.agents/skills` | `/tmp/codify-runtime` 下的 `codex-home`，仅在 `shared/` 挂载不可用时使用 |
| Pi | `PI_HOME` 落在 `shared/` 挂载上，即 `/opt/codify-issue-shared/pi-home`，其中存放 `sessions/` | `/home/codify/.pi/agent`：`models.json`、`settings.json`、agent 定义、扩展与 Skills |
| OpenCode | `XDG_DATA_HOME` 落在 `shared/` 挂载上，即 `/opt/codify-issue-shared/opencode-data`，其中存放会话数据 | `/tmp/codify-runtime/opencode` 下的 `HOME`、`XDG_CONFIG_HOME`、`XDG_CACHE_HOME` 与 `XDG_STATE_HOME` |

`/home/codify` 本身不是挂载点，只有它下面的 `.claude` 会随容器保留；Harness 放在这个 home 其他位置的任何内容都会在下次运行时重建。

### Worker Kit

**运行时交付方式** 为 **挂载 Worker Kit** 时，Codify 把 Kit 以只读方式挂载到 `/opt/codify-kit`、把其中的 `nix/store` 挂载到 `/nix/store`，并以 root 身份通过 `/opt/codify-kit/launcher` 启动容器。Kit 在宿主机上的安装根目录是 `/opt/codify/worker-kits/<内容寻址名称>`，由 root 所有且其他用户不可写。

**Profile 存储卷挂载** 不能与上述挂载冲突：自定义挂载不能隐藏 `/workspace`、`/home/codify/.claude` 或 `/opt/codify-issue-shared`，也不能进入已封闭的 `/opt/codify-issue-meta` 与 `/tmp/codify-runtime`；同样的规则保护 `/opt/codify-kit` 与 `/nix/store` 两个 Kit 挂载。

### 任务临时目录

`/tmp/codify-runtime` 只存在于容器内部，每个任务创建一次，随容器一起丢弃。本次运行的证据都在这里：

- 规范化事件流 `event.jsonl`，以及 `harness-events/` 下各 Harness 的原始事件流
- `console.log` 与 Harness 结果 `harness-result.json`
- `artifacts/`，用户产物的暂存目录
- `orchestration/`，运行开始前上传的冻结 Runtime Bundle

容器退出时，运行归档就从这个目录打包，再由 Backend 传输到控制面的归档存储 `/opt/codify-archives`。

### 生命周期与回收

保留期是平台配置，不要把本页的目录说明当成当前实例的取值。默认值和扫描范围集中记录在[《平台参考》](/guide/96-platform-reference)；这里仅说明对象之间的关系。

| 对象 | 配置项 | 当前取值 | 回收条件 |
|---|---|---|---|
| Issue workspace | `worker_workspace_retention_days` | 以系统配置为准 | 没有活跃任务占用，且目录在保留期内未被使用 |
| 运行归档 | `worker_runtime_archive_retention_days` | 以系统配置为准 | 按归档记录的生成时间 |
| CI 失败证据包 | 跟随 `worker_workspace_retention_days` | 以系统配置为准 | 按 `{worker_workspace_host_path}/ci-failures` 下证据包的时间 |

workspace 的使用时间会在创建任务、任务结束和取消时刷新，因此正在使用的需求不会被回收。回收时会启动一个临时维护容器：挂载 workspace 根目录并检查 `meta/owner`，该标记指向其他需求或 Worker Profile 时拒绝删除。调度器每 6 小时扫描一次 workspace，每小时扫描一次运行归档。调度器崩溃恢复会清理中断运行留下的孤儿容器，但不会删除 workspace。
