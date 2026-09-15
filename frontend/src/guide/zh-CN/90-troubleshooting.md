---
title: 平台排障
section: Admin Guide
tier: core
---

## 平台排障路径

先记录任务编号、需求编号、Worker、Docker 目标和时间，再按「错误卡片 → 事件流 → 原始日志 → 运行归档」取证。

![平台排障从错误卡片开始，逐层核对事件、日志和运行归档](assets/diagrams/zh-CN/failure-triage.svg)

> [!warning] 清理前先保留容器、工作区和归档。交付与重启问题通常需要这些记录判断。

| 现象 | 先检查 |
|---|---|
| protocol_error | 规范事件、Harness 原始事件和进程退出码 |
| worker_runtime_unavailable | Task Snapshot 中的 Worker Kit、Runtime Bundle 和 Docker 目标 |
| harness_cli_unavailable | Kit inventory 是否包含冻结的 Harness CLI |
| worker_runtime_check_failed | Profile 的 Kit 路径、镜像、挂载和 Harness 选择 |
| execution_contract_mismatch | Task Snapshot、attempt schema 和 Runtime Bundle 身份 |
| Worker failed to start | Docker 目标、镜像、挂载和入口脚本 |
| Code delivery was not confirmed | 推送前后远端分支、机器人权限和交付结果 |

错误和日志写入前会脱敏，glpat-*、sk-ant-* 等令牌不会出现在记录中。脱敏记录可以交给支持人员，但不等同于原始输出。

## Worker、容器与调度

Monitor 分开展示队列、任务与容器对齐情况，以及健康状态。刷新后立即消失的不一致可能只是采样延迟；持续存在才需要按故障调查。

| 信号 | 含义 | 管理员先做什么 |
|---|---|---|
| 运行中任务没有容器 | 任务/容器缺口 | 检查目标可达性、容器清单和任务事件 |
| 运行中容器没有任务 | 可能是孤儿容器 | 确认任务不是刚结束，再按策略清理 |
| 任务仍运行但容器已退出 | 恢复状态缺口 | 保留退出信息和归档，让恢复流程收敛任务 |
| 容器晚于任务结束 | 仍在收尾或清理 | 检查任务时间线和目标主机 |
| Docker 目标不可用 | 目标无法采样 | 恢复连接，不要把它当成零容器 |

任务长期处于「待处理」或「已入队」时，依次检查预约时间、需求前序任务、最大并发数、时段容量、Worker Runtime 和调度器健康。只有需求队首参与派发。

## 平台重启与数据一致性

重启后，恢复流程会把持久化任务记录与容器现实状态对齐：

1. 运行中的容器仍对应运行中任务时，重新接管并继续收集事件。
2. 容器已经退出时，收齐结果后结束任务。
3. 没有对应运行中任务的容器按孤儿清理。
4. 运行中任务找不到容器时结束为「失败」；已请求取消的结束为「已取消」。
5. Docker 目标不可达时，保留任务归属并等待后台重试。

恢复不会重排回合。如果需求一直被锁定，先检查是否有残留容器或未完成的收尾记录。缺少 started_at、超时数据或回合序号异常属于数据一致性问题，修复时保留原记录和归档。

## 登录、OIDC 与密钥

登录问题先看「OIDC 诊断」：检查 discovery、端点、回调地址、所需 scopes 和 Cookie 策略。OAuth 应用需要 openid、profile、email、read_api；组管理员引导要求 claims 或 userinfo 返回 groups。

常见告警包括回调地址不在 /api/auth/callback 下、HTTP 与 Cookie Secure 不匹配、SameSite=None 没有安全 Cookie、Session TTL 过长，以及组引导没有 groups。

密钥无法解密时，检查 CONFIG_ENCRYPTION_KEY 或非默认 SESSION_SECRET 是否仍是加密时使用的原值。恢复原密钥或重新填写密钥。紧急入口只用于 OIDC 恢复或管理员锁定，正常登录恢复后要关闭。

## 配置、Provider 与清理

任务身份在创建时冻结。怀疑配置修改没有生效时，先把 Task Snapshot 与当前 Worker、Provider、Harness、Skills、运行指令和 Runtime Bundle 对比。

Provider 删除受活跃任务、默认 Provider 和最后一个可用 Provider 保护；Worker Profile 删除前必须停用且没有需求引用。强制停用 Profile 会关闭其未关闭需求。

历史数据清理见[《管理员治理》](/guide/85-admin-governance)，只有确认活跃任务状态已失真时才启用强制清理。路径、挂载、Harness 状态和临时目录见[《Worker 运行时》](/guide/92-worker-runtime)。修改镜像或 Kit 后重新验证 Profile。
