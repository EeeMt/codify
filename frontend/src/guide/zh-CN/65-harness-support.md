---
title: Harness 支持
section: User Guide
tier: deep
---

## 什么是 Harness

Harness 是执行 Task 的编码代理。Codify 按 key 区分它们：

| Key | 显示名 |
|---|---|
| `claude` | Claude |
| `codex` | Codex |
| `pi` | Pi |
| `opencode` | OpenCode |

Worker 按 key 加载适配器 `${CODIFY_ORCHESTRATION_DIR}/worker-entrypoint/harness/adapters/${CODIFY_HARNESS_KEY}.sh`，并对每个适配器调用同一组操作：`metadata`、`verify_runtime`、`detect_capabilities`、`prepare_config`、`build_command`、`materialize_skills`、`stream_events`、`normalize_result`、`terminate` 和 `run`。

四者使用同一份契约版本。Harness 契约是 `codify.worker.harness/v2`，事件、结果与命令分别是 `codify.worker.event/v2`、`codify.worker.result/v2` 和 `codify.worker.command/v2`。执行模式只有 `v2_only`，v1 bundle 只能读取，不能执行。

CLI 不来自镜像的 `PATH`。适配器从 `CODIFY_HARNESS_CLI_BIN` 或 Kit manifest 中的 `harness_inventory[key].path` 解析可执行文件，两者都没有时以 `<X> CLI is not available from the Worker Kit inventory` 失败。

Worker Profile 用 `harness_runtimes[key].source` 记录每个 Harness 的来源，取值为 `worker_kit` 或 `host_mount`。host mount 需要绝对路径 `executable_path`，可以固定 `version` 与 `binary_digest`，其 `contract_version` 必须等于 `codify.worker.harness/v2`。Codex 是文档中支持这种方式的 Harness：以只读方式挂载的主机二进制，离线包把格式写成 `harness_key | host_path | container_path | version | sha256`。Kit 挂载在 `/opt/codify-kit`，其中的 store 挂载在 `/nix/store`，两者都是只读。

## 各 Harness 的共有行为

任务模式属于 Task，与 Harness 无关：`execute`、`freeform` 和 `plan`，界面上的标签分别是 **实施模式**、**自由模式** 和 **分析模式**。会话模式同样是共有的 `continue` 与 `fresh`；提示词渲染也只看任务模式与触发来源。

会话续接四个都支持。会话记录按 Harness 划分命名空间，因此续跑任务必须沿用被续接那次运行使用的 Harness。

任务 Skills 四个都支持，各自把 Skill 包放到本 CLI 期望的位置。

权威的用量事件是 `usage.final`，四个 Harness 一致，写入 `task.input_tokens` 与 `task.output_tokens`。信封里可以携带费用与币种，但 Task 不保存它们。

超时策略同样共有：可配置 60 到 28800 秒，任务进入 RUNNING 时确定高峰或低峰档位，每个适配器还会在 `timeout ${TASK_TIMEOUT:-1800}` 之下运行 CLI。

失败类型是同一份清单：`configuration_error`、`authentication_error`、`rate_limited`、`sandbox_error`、`protocol_error`、`timeout`、`cancelled`、`engine_error`、`crash` 和 `settled_race`。事件词表也共用，包括 `run.started`、`model.resolved`、`message.delta`、`tool.started`、`tool.completed`、`context.compacted`、`usage.updated`、`usage.final`、`harness.completed`、`run.completed`、`delivery.*` 系列与 `diagnostic`。

调度、优先级、需求互斥、时段容量与整条 Git 交付链路也不按 Harness 分支：提交、推送、Merge Request 与交付摘要的产生方式相同，只有 `run_text` 辅助函数存在差异。

## 各 Harness 的差异 {core}

| Harness | 模型协议 | 引导与续接 | 会话续接 | 任务 Skills | 用量事件 | 提交信息与 MR 摘要 | 最大轮次 |
|---|---|---|---|---|---|---|---|
| Claude | `anthropic_messages` | 否 | 是 | 是 | `usage.final` | 由模型生成 | 生效 |
| Codex | `openai_responses` | 否 | 是 | 是 | `usage.final` | 按设计失败并回退 | 不生效 |
| Pi | 三种都支持 | 是 | 是 | 是 | `usage.updated`、`usage.final` | 未导出并回退 | 不生效 |
| OpenCode | 三种都支持 | 否 | 是 | 是 | `usage.updated`、`usage.final` | 未导出并回退 | 不生效 |

四个 key 都允许子代理，但冻结 bundle 必须声明该能力才会启用。

- 引导与续接只有 Pi 支持。控制门由冻结 bundle 的 `capabilities.steering` 决定，因此 Claude、Codex 与 OpenCode 的控制门从禁用开始，「转向」与「续接指令」保持不可用。
- 即使命令送达 OpenCode 的 bridge，也会被确定性地以 `control_gate_closed` 拒绝。
- 由模型生成的提交信息或 MR 摘要只在 Claude 上存在。Codex 的 `run_text` 实现按设计返回非零，Pi 与 OpenCode 根本不导出该实现，这三者的运行会写入固定的回退提交信息，并保留此前的 MR 摘要。

> [!warning] **最大轮次只约束 Claude**：该值以 `CLAUDE_MAX_TURNS` 传给 CLI，其他适配器不读取它。

### 状态、会话与 Skills

每个 Harness 把自己的会话状态放在各自的目录里，会话 id 只在同一个 Harness 内可续接：续跑任务必须沿用原 Harness，切换 Harness 需要新开会话。

| Harness | 会话状态 | 任务 Skills |
|---|---|---|
| Claude | `/home/codify/.claude`，落在需求的持久挂载上 | 直接从本次运行的快照目录通过 `--add-dir` 读取，不复制 |
| Codex | `CODEX_HOME` 落在需求的共享挂载上，即 `/opt/codify-issue-shared/codex-home` | 复制到 `CODEX_HOME/.agents/skills` |
| Pi | `PI_HOME` 落在需求的共享挂载上，即 `/opt/codify-issue-shared/pi-home` 下的 `sessions/` | 复制到 `/home/codify/.pi/agent/skills`，容器不会保留该目录 |
| OpenCode | `XDG_DATA_HOME` 落在需求的共享挂载上，即 `/opt/codify-issue-shared/opencode-data` | 复制到本次运行的配置目录，并用 `opencode debug skill --pure` 验证可被发现 |

完整的目录布局，以及哪些内容会跨任务保留，见《Worker 运行时》。

## 模型协议配对

| Harness | 可用协议 |
|---|---|
| Claude | `anthropic_messages` |
| Codex | `openai_responses` |
| Pi | `anthropic_messages`、`openai_responses`、`openai_chat_completions` |
| OpenCode | `anthropic_messages`、`openai_responses`、`openai_chat_completions` |

Provider 侧会进一步收窄：「Provider 类型」为 `anthropic_compatible` 时搭配「Wire 协议」`anthropic_messages`，`openai_compatible` 搭配 `openai_responses` 或 `openai_chat_completions`。这一组合在保存 Provider 时校验，不匹配会在保存阶段被拒绝，而不是等到容器内才失败。

Provider 的选择跟随 Harness。Codify 在服务端按这份矩阵计算兼容 Harness，存在可用 Provider 时自动切换到协议匹配的那个并给出提示；一个都没有时，任务表单会提示当前 Harness 没有可用的配套协议 Provider，并指向「AI 模型服务」。

## Harness 专属选项

选项放在 Worker Profile 的 `harness_options` 中，Task 可以覆盖其中的一部分。

| Harness | Schema | 选项 |
|---|---|---|
| Codex | `codex/v1` | `reasoning_effort`：`minimal`、`low`、`medium`、`high`、`xhigh`、`ultra` |
| Pi | `pi/v1` | `thinking_level`；`steering_mode` 与 `follow_up_mode`，取值只有 `one-at-a-time` |
| OpenCode | `opencode/v1` | `agent`：`build`、`plan`、`general`、`explore`；`command`：`codify`；`model_variant`：不超过 64 个字符的标识符 |

任务级覆盖是 Profile 选项的子集。Profile 还可以按 Harness 约束四个键：`max_turns`、`sandbox_mode`、`network_enabled` 和 `timeout_seconds`。

OpenCode 的这些选择在任务表单里显示为「OpenCode 选项」，并固化到任务快照，包含「Agent」「Command」和「模型 variant」；只有 allowlist 内的 Agent、Command 与 variant 会发送给已固化的 OpenCode Server。

## 可用性与版本要求

Harness 可用需要三件事同时成立：payload 存在、Worker Profile 启用了该 key、运行时验证确认通过。

Kit manifest 会记录全部四个 key，即使只准备了部分 payload。构建时选择 CLI 集合，默认是 `pi,opencode`，不在集合内的 key 记为 `absent/not_selected`，在集合内但缺少 payload 的记为 `absent/missing_payload`。已有的 payload 会按大小与 SHA-256 校验。只有挂载模式的 Worker Kit 才提供 Harness 选择。

Profile 上的「Harness」列出已启用的 key，「默认 Harness」指定新任务预选的那个，未改动时为 `claude`。Profile 运行时验证会把每个 key 标为「可用」或「不可用」，原因是「未选择」「缺少 payload」或「原因未知」；任务表单用的清单更长：「可用」「不可用」「未验证」「已启用」「已禁用」，以及「Worker 配置已禁用」「Worker 配置未启用」「Worker 配置不可用」「Worker Kit 不可用」「运行时未验证」「显式主机挂载」「已由任务快照固定」和「原因不可用」。

manifest 为每个 Harness 固定了可接受的版本范围：

| Harness | 可接受范围 | 越界时的行为 |
|---|---|---|
| Claude | `>=2.1.33 <3.0.0` | 上报，并由适配器执行 2.1.33 硬性下限 |
| Codex | `>=0.146.0 <0.160.0` | 仅警告 |
| Pi | `>=0.84.2 <0.85.0` | 仅警告 |
| OpenCode | `>=1.18.19 <1.19.0` | 仅警告 |

Kit 构建把 `claude` 固定在 2.1.153、`codex` 固定在 0.146.0、`pi` 固定在 0.84.2、`opencode` 固定在 1.18.19。对 Claude，runner 会在任务使用 Skills 时再检查一次 2.1.33 下限。

## 界面上的可见差异 {core}

- 任务表单的「Harness」选择器列出全部四个 key，并标注可用性与原因。「Harness」属于任务快照，续跑任务必须沿用；要切换必须开新会话。
- 「实时引导」只在冻结 bundle 声明 `steering` 时出现，目前只有 Pi 的 bundle 声明了它，因此面板只出现在 Pi 任务上；「转向」与「续接指令」按能力分别启用。
- 提交记录与 MR 正文取决于 `run_text` 的结果：Claude 上写入模型生成的内容，Codex、Pi 与 OpenCode 上提交使用回退信息，MR 保留此前的摘要。
- 失败时任务结果展示共享清单中的失败类型，具体取值由各适配器按自己的信号判定：Claude 把会话丢失映射为 `protocol_error`，Codex 映射 401、429、沙箱与引擎错误，Pi 在模型不存在时补上 `configuration_error`，OpenCode 的 bridge 会补上 `cancelled` 与 `crash`。引擎错误在任务结果里显示为「Harness 错误」。
