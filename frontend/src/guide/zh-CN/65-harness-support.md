---
title: Harness 支持
section: User Guide
tier: deep
---

## 什么是 Harness

Harness 是在 Worker 容器里执行任务的编码代理 CLI。

| Key | 显示名 |
|---|---|
| claude | Claude |
| codex | Codex |
| pi | Pi |
| opencode | OpenCode |

每个 key 都有自己的适配器，并使用 v2 契约族：`codify.worker.harness/v2` 用于 Harness，事件、结果和命令也各有对应的 v2 契约。当前执行模式是 v2 only，v1 bundle 可以读取但不能执行。

适配器从 `CODIFY_HARNESS_CLI_BIN` 或 Worker Kit manifest 解析 CLI。两处都没有时，运行时验证会以 `<X> CLI is not available from the Worker Kit inventory` 失败。Profile 会记录 CLI 来自 Worker Kit，还是来自绝对路径的只读主机挂载；主机挂载必须声明 v2 契约，也可以固定版本和摘要。

## 各 Harness 的共有行为

任务模式与 Harness 无关：「实施模式」「分析模式」「自由模式」分别对应 execute、plan 和 freeform。会话模式只有「继续」和「新开」；续接任务必须沿用拥有该会话的 Harness。

四个 Harness 都支持会话续接和任务 Skills，各自把 Skill 放到 CLI 期望的位置。四个 Harness 都通过 `usage.final` 上报最终用量，记录输入和输出 Token；费用不会存到 Task 上。

超时、调度、需求互斥和 Git 交付链路共用一套行为。失败类型也共用：`configuration_error`、`authentication_error`、`rate_limited`、`sandbox_error`、`protocol_error`、`timeout`、`cancelled`、`engine_error`、`crash` 和 `settled_race`。

## 各 Harness 的差异 {core}

| Harness | 协议 | 引导 / 续接 | 会话续接 | Skills | 最大轮次 |
|---|---|---|---|---|---|
| Claude | anthropic_messages | 否 | 是 | 是 | 生效 |
| Codex | openai_responses | 否 | 是 | 是 | 不生效 |
| Pi | 三种都支持 | 是 | 是 | 是 | 不生效 |
| OpenCode | 三种都支持 | 否 | 是 | 是 | 不生效 |

当前只有 Pi 提供实时引导和续接指令。冻结 bundle 中的能力标记决定控制面板是否出现；接口显示「Harness 已接收」时，模型仍可能尚未消费命令。

只有 Claude 导出用于生成提交信息和 MR 摘要的辅助函数。Codex、Pi 和 OpenCode 使用固定的提交信息回退；适用时保留之前的 MR 摘要。「最大轮次」只会传给 Claude CLI。

### 状态、会话与 Skills

会话状态按 Harness 分开保存，一个 Harness 的会话 id 不能迁移到另一个 Harness。

| Harness | 跨任务保留的状态 | 本次运行的 Skill 位置 |
|---|---|---|
| Claude | 需求挂载中的 /home/codify/.claude | 通过 --add-dir 从任务快照读取 |
| Codex | /opt/codify-issue-shared/codex-home 下的 CODEX_HOME | CODEX_HOME/.agents/skills |
| Pi | /opt/codify-issue-shared/pi-home/sessions 下的 PI_HOME | /home/codify/.pi/agent/skills |
| OpenCode | /opt/codify-issue-shared/opencode-data 下的 XDG_DATA_HOME | 本次运行配置目录，并用 opencode debug skill --pure 检查 |

完整目录见[《Worker 运行时》](/guide/92-worker-runtime)。

## 模型协议配对

| Harness | 支持的协议 |
|---|---|
| Claude | anthropic_messages |
| Codex | openai_responses |
| Pi | anthropic_messages、openai_responses、openai_chat_completions |
| OpenCode | anthropic_messages、openai_responses、openai_chat_completions |

Provider 类型和 Wire 协议必须匹配：

| Provider 类型 | Wire 协议 | 兼容 Harness |
|---|---|---|
| anthropic_compatible | anthropic_messages | Claude、Pi、OpenCode |
| openai_compatible | openai_responses | Codex、Pi、OpenCode |
| openai_compatible | openai_chat_completions | Pi、OpenCode |

保存 Provider 时会校验这组关系，配对错误直接拒绝。如果没有启用的 Provider 能说 Harness 所需协议，创建任务时会明确提示。

## Harness 专属选项

选项位于 Worker Profile 的 `harness_options` 中，Task 只能覆盖受支持的部分。

| Harness | 选项 |
|---|---|
| Codex | `reasoning_effort`：minimal、low、medium、high、xhigh、ultra |
| Pi | `thinking_level`；`steering_mode` 与 `follow_up_mode`：one-at-a-time |
| OpenCode | `agent`：build、plan、general、explore；`command`：codify；`model_variant`：不超过 64 个字符 |

Profile 还可以按 Harness 约束 `max_turns`、`sandbox_mode`、`network_enabled` 和 `timeout_seconds`。OpenCode 的 Agent、Command 和 Model variant 会固化到 Task Snapshot，并按 allowlist 校验。

## 可用性与版本要求

Harness 可用要同时满足：payload 存在、Profile 已启用、运行时验证通过。Kit manifest 会把未选入 CLI 集合的 key 记为 absent/not_selected，把已选但缺 payload 的 key 记为 absent/missing_payload，并校验 payload 的大小和 SHA-256。

Profile 会列出已启用 Harness 和默认 Harness。运行时验证报告每个 key 的可用性和原因；创建任务时还会检查冻结 Profile 与 Provider 的协议兼容性。

当前 manifest 接受的范围为：

| Harness | 可接受范围 | 越界处理 |
|---|---|---|
| Claude | >=2.1.33 <3.0.0 | 适配器执行 2.1.33 下限 |
| Codex | >=0.146.0 <0.160.0 | 告警 |
| Pi | >=0.84.2 <0.85.0 | 告警 |
| OpenCode | >=1.18.19 <1.19.0 | 告警 |

排查具体任务时，以 Worker 验证结果和 Task Snapshot 为准；Profile 可能在任务创建后发生变化。

## 界面上的可见差异 {core}

- 任务表单的「Harness」选择器显示可用性和原因。续接任务必须沿用冻结的 Harness，要切换就开启新会话。
- 实时命令面板跟随冻结的引导与续接能力，只在运行时支持时出现。
- 提交记录和 MR 摘要取决于 Harness 的结果辅助函数；Claude 可提供模型生成的文本，其他三个使用上面的回退规则。
- 失败类型使用统一词表，各适配器负责把自己的 CLI 信号映射进去。
