---
title: Worker 运行时
section: Admin Guide
tier: deep
---

## Worker 文件系统

每台 Docker 主机会按需求保留一份目录，里面是代码检出、跨任务保留的 Harness 状态和清理元数据。单次运行的证据位于容器临时目录，容器退出前会封装成归档。

### 宿主机目录结构

根路径由 `WORKER_WORKSPACE_HOST_PATH` 提供，对应 `worker_workspace_host_path`，默认是 `/opt/codify-workspaces`。每台 Docker 主机都必须使用同一路径。

~~~text
{worker_workspace_host_path}/project-{project_id}/issue-{issue_id}/
  repo/
  claude/
  shared/
  meta/
~~~

配置页面不能修改该路径。要修改环境变量并重建 Backend 与 Scheduler。

### 容器内挂载

需求上的每个任务都会得到以下四个读写挂载：

| 容器路径 | 持久化内容 |
|---|---|
| `/workspace` | 代码检出和前序任务提交 |
| `/home/codify/.claude` | Claude 会话与 CLI 状态 |
| `/opt/codify-issue-shared` | 需求共享状态及其他 Harness 目录 |
| `/opt/codify-issue-meta` | `workspace.json`、所有权和删除保护元数据 |

挂载会跨容器保留，因此追加任务可以复用代码检出和会话。

### 各 Harness 的状态目录

| Harness | 跨任务保留 | 每次运行重建 |
|---|---|---|
| Claude | `/home/codify/.claude` | `.claude.json` 和本次运行提示词 |
| Codex | `shared/codex-home` 下的 `CODEX_HOME` | `/tmp/codify-runtime` 下的备用 home |
| Pi | `shared/pi-home/sessions` 下的 `PI_HOME` | `/home/codify/.pi/agent` 下的设置和 Skills |
| OpenCode | `shared/opencode-data` 下的 `XDG_DATA_HOME` | `/tmp/codify-runtime/opencode` 下的 HOME 和 XDG 目录 |

只有 `/home/codify` 下的 Claude 子目录是直接挂载的，其他内容下次运行会重建。

### Worker Kit

挂载模式的 Worker Kit 以只读方式放在 `/opt/codify-kit`，其中的 Nix store 放在 `/nix/store`，容器通过 `/opt/codify-kit/launcher` 启动。Kit 安装在 Docker 主机的内容寻址目录中。

Profile 的自定义挂载不能覆盖工作区、Harness 状态、元数据、临时目录、Kit 或 Nix store 挂载。这些保护避免 Profile 替换运行时或覆盖其他需求的状态。

### 任务临时目录

`/tmp/codify-runtime` 只存在于容器内，每条任务重新创建。里面有归一化事件、Harness 原始事件、控制台日志、Harness 结果、用户制品和冻结的编排包。容器退出时从这里生成归档，再传到 `/opt/codify-archives`。

### 生命周期与回收

保留期来自系统配置，实际取值可能随部署变化：

| 对象 | 配置项 | 回收条件 |
|---|---|---|
| Issue workspace | `worker_workspace_retention_days` | 没有活跃任务占用，且闲置超过保留期 |
| 运行归档 | `worker_runtime_archive_retention_days` | 归档记录超过保留期 |
| CI 失败证据包 | 跟随 Workspace 保留期 | 证据包超过保留期 |

任务创建、完成或取消时会刷新工作区使用时间。清理前检查 `meta/owner`，若目录属于其他需求或 Profile 就拒绝删除。调度器每 6 小时扫描工作区、每小时扫描归档；崩溃恢复会清理孤儿容器，但不会删除工作区。
