---
title: 平台排障
section: Admin Guide
tier: core
---

## 平台排障路径

这页给平台管理员和负责部署的同事使用。先记录任务编号、需求编号、Worker、Docker 目标和发生时间，再按「错误卡片 → 事件流 → 原始日志 → 运行归档」取证。用户能在任务页完成的重试、追加任务和提示词修正，不需要在这里处理。

![平台排障从错误卡片开始，逐层核对事件、日志和运行归档](assets/diagrams/zh-CN/failure-triage.svg)

> [!warning] **先保留现场**：不要先删除容器、工作区或运行归档。平台重启、容器缺失和交付未确认等问题需要这些记录来判断状态是否真的收敛。

| 错误或现象 | 先核对什么 | 处理方向 |
|---|---|---|
| `protocol_error: ...` | 规范事件流、Harness 原始流和进程退出码是否一致 | 对照 Runtime Bundle 的事件契约；重复出现时保留归档并检查对应适配器 |
| `worker_runtime_unavailable` | Task Snapshot 指向的 Worker Kit、Runtime Bundle 和 Docker 目标 | 恢复 Kit 或目标后重新验证 Profile，再让任务重新进入调度 |
| `harness_cli_unavailable` | Kit inventory 是否包含快照要求的 Harness CLI | 安装或重建包含该 CLI 的 Worker Kit，并重新验证 Profile |
| `worker_runtime_check_failed` | Profile 的 Kit 路径、镜像、挂载和 Harness 选择 | 修复运行时组合；重试本身不会跳过运行时检查 |
| `execution_contract_mismatch` | Snapshot、attempt schema 和 Runtime Bundle 身份 | 修复 Profile 与 Bundle 组合，后续任务使用新的快照 |
| `Worker failed to start: ...` | Docker 目标连接、镜像拉取、挂载和入口脚本 | 在目标主机保留启动错误，确认容器是否实际创建 |
| `Code delivery was not confirmed...` | 推送前后远端分支、机器人权限和交付摘要 | 对照[《交付内部》](/guide/75-delivery-internals)中的错误码，确认是否应重试 |

错误和日志写入前会脱敏，`glpat-*` 和 `sk-ant-*` 等密钥不会出现在记录中。脱敏后的内容可以交给支持人员，但不要据此推断原始输出完整无缺。

## Worker、容器与调度

**监控** 页面的「运行概览」「容器排障」「健康信号」分别回答容量、容器对应关系和服务健康问题。容器排障中的指标来自独立的任务与 Docker 采样，短暂不一致可能只是采样时差；连续刷新仍存在时才按平台故障处理。

| 关系或提示 | 含义 | 管理动作 |
|---|---|---|
| 任务/容器缺口 | 运行中任务没有可见的运行中容器 | 核对目标可达性、容器列表和任务事件，不要立即手动改任务状态 |
| 孤儿容器 | 运行中容器没有对应的运行中任务 | 先确认任务是否刚结束或目标采样是否延迟，再按清理策略处理 |
| 任务仍标记为运行中 | 任务仍是 RUNNING，但对应容器已退出或消失 | 保留归档和退出信息；恢复流程会将无法接管的任务收敛为失败 |
| 容器晚于任务结束 | 容器仍在运行，但任务已经结束 | 确认是否处于收尾阶段；持续存在时检查清理和目标连接 |
| 部分 Docker 目标当前不可用 | 某个目标无法采样 | 不要把该目标当作零容器，先恢复连接，系统会延迟重试 |

任务长期处于「待处理」或「已入队」时，依次看预约时间、同一需求的前序任务、最大并发数、强制时段容量、Worker Runtime 可用性和调度器健康。只有需求队首参与派发，同一需求同时只能有一个运行中的任务。任务因运行时不可用而回到待处理时，恢复运行时并重新验证 Profile 后才会继续。

## 平台重启与数据一致性

重启恢复按运行记录和容器现实状态重新对齐：

1. 容器仍在运行且任务是「运行中」时，恢复监控并继续收集事件和日志。
2. 容器已退出但任务仍是「运行中」时，先收齐已退出容器的输出，再按这次运行的结果收敛任务。
3. 容器已退出且没有对应的运行中任务时，归类为孤儿并清理，不修改任务记录。
4. 任务仍是「运行中」但容器已经不存在时，任务以「失败」结束，并保留平台重启导致的原因。
5. Docker 目标暂时不可达时，目标上的任务保持运行中，恢复流程在后台等待，不要手动批量标记失败。

如果需求一直被锁定，先看是否还有容器引用或未完成的收尾记录。`RUNNING` 缺少 `started_at`、超时字段缺失、回合序号需要修复等情况属于数据不一致，应保留原记录、事件和归档，再修复数据或重建任务。不要用强制清理替代状态调查。

## 登录、OIDC 与密钥

登录循环或管理员权限异常时，先看「OIDC 诊断」的发现、端点、回调地址、必需 scopes 和 Cookie 策略检查项。常见告警包括：回调地址不是 `/api/auth/callback`、HTTP 与 `Cookie Secure` 不匹配、SameSite=None 没有安全 Cookie、会话 TTL 过长，以及启用了组管理员引导但登录响应没有 groups。

GitLab OAuth 应用需要请求 `openid`、`profile`、`email`、`read_api`，回调地址必须与实际访问地址一致。管理员组引导只有在 claims 或 userinfo 确实返回 groups 时才会生效。共享页面（Monitor、Schedule Overview、Analytics）的开关位于系统配置的「运行与共享」；「OIDC 诊断」没有普通用户开关。

配置保存报加密错误时，检查 `CONFIG_ENCRYPTION_KEY` 或非默认的 `SESSION_SECRET` 是否仍是写入密文时的原值。更换或丢失根密钥会让已存储的 OIDC、GitLab、Provider 和通知密钥无法解密，需要恢复原密钥或重新填写。紧急管理员入口只用于 OIDC 故障或管理员锁定，恢复正常登录后应关闭。

## 配置、Provider 与清理

任务创建时会冻结 Worker、Provider、Harness、Skill、运行指令和 Runtime Bundle 身份。配置改动不会回写已有 Task；排查“改了配置但任务没变化”时，先比较任务快照与当前配置，不要直接判定调度器没有加载。

Provider 删除受活跃任务、默认 Provider 和最后一个可用 Provider 等约束；Worker Profile 删除前必须停用，且不能仍被需求引用。强制停用 Profile 会关闭使用它的未关闭需求，执行前要确认影响范围。

工作区、运行归档和 CI 失败证据包的保留期以系统配置中的 Worker 设置为准，具体默认值和扫描周期集中记录在[《平台参考》](/guide/96-platform-reference)。需要清理历史数据时，优先使用[《管理员治理》](/guide/85-admin-governance)里的系统数据清理；只有确认任务状态已不可信时才启用强制清理活跃任务，并保留清理结果中的跳过与失败原因。

Worker 文件系统、挂载保护、Harness 状态目录和单次运行临时目录见[《Worker 运行时》](/guide/92-worker-runtime)。涉及部署路径、镜像、数据库或密钥的变更，应在维护窗口完成并重新执行 Profile 运行时验证。
