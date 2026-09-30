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

### Worker 镜像、Kit 与 Runtime Bundle 如何配合

三者共同组成任务的执行环境，但不是同一个制品：

| 制品 | 提供什么 | 任务中的作用 |
|---|---|---|
| Worker 镜像 | 操作系统和项目工具链，例如 Java、Maven 或 Playwright | 作为容器的基础环境 |
| Worker Kit | launcher、Nix 运行时工具，以及 Kit inventory 中可用的 Harness CLI | 校验运行身份并启动编排入口；为编排脚本和 Harness 提供工具 |
| Runtime Bundle | Codify 的编排入口、Harness Adapter 和 Bridge | 决定仓库准备、Harness 调用及事件处理等 Codify 流程 |

创建任务时，Codify 冻结 Task Snapshot，并绑定 Worker 镜像、Kit 和 Runtime Bundle 的身份。执行时，Backend 基于冻结的 Worker 镜像创建容器，把 Kit 和 Bundle 挂载进去。Kit launcher 校验 Kit manifest、Bundle digest 及契约兼容性，然后运行 Bundle 的入口脚本。入口脚本使用 Kit 的运行时工具，并调用选定 Harness 的 Adapter 和 CLI；CLI 来自 Kit inventory 或 Profile 配置的只读挂载。Harness 在 `/workspace` 中完成任务，运行事件再写回 Codify。

![Worker 镜像、Kit 与 Runtime Bundle 在一次任务中的分工和启动顺序](assets/diagrams/zh-CN/worker-runtime-bundle.svg)

因此，只修改 Bundle 中的编排脚本通常只需生成并绑定新 Bundle；修改 launcher、Nix 工具或 Kit 中的 CLI 才需要发布新 Worker Kit。两者由冻结身份和契约关联，已有任务继续使用创建时绑定的身份。

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
