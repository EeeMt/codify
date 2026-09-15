---
title: 平台参考
section: Admin Guide
tier: deep
---

## 先看数据来源

平台当前取值看「系统配置」，某条任务实际使用的值看 Task Snapshot，能否执行看 Worker 运行时验证。

| 要确认什么 | 去哪里看 |
|---|---|
| 当前超时、容量和保留期 | 「系统配置」 |
| 某条任务用了什么值 | 任务详情页的 Task Snapshot |
| 哪个 Worker Kit、镜像或 Harness 可用 | 「Worker」验证结果和 Task Snapshot |
| 宿主机路径和密钥在哪里设置 | 部署环境和 Docker 主机 |

下面的默认值和范围来自当前代码；某个实例可能已经用数据库覆盖值替换它们。

## 容量、超时与保留期

| 配置项 | 默认值 | 规则 |
|---|---:|---|
| MAX_CONCURRENCY | 3 | 同时运行 1–20 条任务 |
| TASK_TIMEOUT_PEAK_SECONDS | 1800 秒 | 60–28800 秒，任务开始时冻结 |
| TASK_TIMEOUT_OFF_PEAK_SECONDS | 3600 秒 | 60–28800 秒，任务开始时冻结 |
| TASK_TIMEOUT_PEAK_START / END | 09:00 / 18:00 | 业务时区 HH:mm，开始包含、结束不包含 |
| SCHEDULER_INTERVAL | 5 秒 | 1–60 秒 |
| worker_workspace_retention_days | 14 天 | 0–365 天，0 表示关闭普通工作区清理 |
| worker_runtime_archive_retention_days | 30 天 | 1–3650 天，不删除任务记录 |
| SLOT_MAX_TASKS | 0 | 每小时 0–100 条任务，0 表示不限制 |
| SLOT_MAX_TASKS_ENFORCE | false | 开启时满载拒绝创建，关闭时只警告 |

任务进入「执行中」时只选择一次高峰或低峰档位。判断单条任务时，以任务记录的「本次超时上限」和「执行截止时间」为准。

## Worker Kit 与运行时边界

| 能力 | 最低条件 |
|---|---|
| 浅克隆和延迟下载历史文件内容 | 挂载 Worker Kit 0.3.0 或更高 |
| Skills | 挂载 Worker Kit 0.3.5 或更高 |
| Harness 执行 | Profile 已选择 Harness 且运行时验证通过 |
| Worker Kit 路径 | Docker 主机上的绝对路径，通常挂载到 /opt/codify-kit |

镜像内置交付方式已过时且不支持 Skills。实际 Kit、镜像和 Harness 版本属于 Profile 与部署环境。Runtime Bundle 不可变，替换主机 Kit 不会改变已有任务。

## 归档与制品上限

运行归档硬上限为 640 MiB。默认用户制品预算为总计 200 MiB、单文件 100 MiB、5,000 个条目；可配置范围为总量和单文件 1–512 MiB、条目 1–100,000 个。单文件上限不能超过总上限。

超过制品预算或归档上限时，Codify 会省略用户制品目录，并把原因写进 artifacts-validation.json；事件和任务记录仍保留。工作区清理与归档清理相互独立，都不会删除任务记录。
