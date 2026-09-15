---
title: 交付内部
section: User Guide
tier: deep
---

推送结果不清楚，或需要一次运行的完整证据时，查这页。日常的分支、MR 和统计流程见[《交付》](/guide/50-delivery)。

## 推送规则

推送前，Codify 会先获取远端分支位置，再以这一次获取到的位置作比对。它使用 `--force-with-lease`，只有远端仍停在该位置时才会推送，永远不会退回普通强制推送。第一次推送还会确认远端分支不存在。

## 推送失败

推送被拒绝或结果无法确认时，任务失败，但提交仍保留在工作区。

| 错误码 | 含义 |
|---|---|
| `remote_diverged` | 本地与远端历史已经分叉 |
| `remote_rewound` | 远端不再包含本次运行的起始提交 |
| `remote_deleted` | 运行期间远端分支被删除 |
| `remote_changed` | 推送被拒绝后，复查时远端又发生变化 |
| `branch_changed` | 收尾期间本地分支发生变化 |
| `history_rewritten` | 分支历史不再符合记录的起点 |
| `history_unverifiable` | 本地历史太浅，无法证明祖先关系，因此没有尝试推送 |
| `push_failed` | 推送被拒绝，但远端位置没有变化 |
| `remote_unconfirmed` | 推送后无法观察远端状态 |

界面会在结果旁显示原始 Git 错误。任务如果在提交残留改动前失败，这些未提交文件会留在工作区，下一条任务可能把它们一起提交；继续之前先检查工作区。

## 运行归档

容器退出后，Codify 从 `/tmp/codify-runtime` 封装本次运行证据，生成 `task-{id}-runtime-archive.tar.gz` 并存到控制面主机。只有「已完成」和「失败」任务显示下载入口，下载权限与任务页相同。取消或超时的运行也可能有归档，只是界面入口不可用。

文件只有在运行确实产生时才会出现：

| 文件 | 内容 |
|---|---|
| `event.jsonl` | 「事件流」使用的归一化事件 |
| `harness-events/` | 本次 Harness 的原始事件 |
| `console.log` | 容器原始输出 |
| `harness-result.json` | Harness 最终结果 |
| `runtime.json` | 运行时与模型信息，Claude 运行会写入 |
| `repository-preparation.json` | 仓库准备遥测数据 |
| `delivery-summary.md` | 交付摘要 |
| `delivery-summary-validation.json` | 交付摘要校验结果 |
| `artifacts-validation.json` | 制品收集与封装结果 |
| `artifacts/` | 在预算内的用户制品 |
| `opencode-http-audit.jsonl` | OpenCode HTTP 审计记录 |

归档不包含提示词文件、制品策略、脚本、编排用 Runtime Bundle、超时标记、仓库、工作区挂载和 Harness 状态目录。它只收录本次运行写入临时目录的内容。

整包硬上限、制品预算和保留期见[《平台参考》](/guide/96-platform-reference)。超过预算或封装上限时，Codify 会省略用户制品目录，并把原因写进 `artifacts-validation.json`。清理按归档记录时间计算，不会删除任务。

浏览器日志被截断时，用归档取得完整输出。结构化工具数据可以直接在进程面板中加载；数据不可用时会显示「加载内容失败」。
