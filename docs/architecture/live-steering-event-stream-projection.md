# 实时引导事件流展示优化方案

> 状态：Implemented（开发环境验收记录：`docs/reviews/2026-09-11-live-steering-event-stream-projection-dev-verification.md`；§10.1 后端回归、§10.2 前端回归、§10.3 真实 Task 验收均通过）
>
> 日期：2026-09-11
>
> 范围：Task 详情页事件流、`TaskHarnessCommand` 到 `TaskLog` 的产品投影

## 1. 结论

实时引导在事件流中应展示为一条可读的“用户动作”，而不是三条底层传输记录：

```text
[转向] Harness 已接收                              08:44:55
完成后简要总结即可
#1
```

实现采用现有数据和事件，不新增协议、表或状态：

1. `TaskHarnessCommand` 继续作为命令类型、文本和状态的唯一事实源。
2. `control.command.delivered` / `control.command.rejected` 仍由 Harness 原生 ACK 经
   `WorkerEventProjector` 生成唯一一条可见 `TaskLog`。
3. Projector 在写入该 `TaskLog` 时，用当前 attempt、序号和 payload digest 精确关联命令，补充
   已脱敏的 `command_type` 与 `text`。
4. `control.queue.updated` 继续持久化和归档，但不进入默认用户事件流。
5. UI 主信息展示类型、状态和消息；命令 UUID 从默认视图移除，仅保留序号。

## 2. 现场基线与问题

2026-09-11 在开发环境 Task `#570` 核对到同一条命令的两种投影：

| 数据源 | 已有内容 |
|---|---|
| `task_harness_commands` | `sequence_no=1`、`command_type=steer`、`status=delivered`、`text=完成后简要总结即可` |
| 第一条 `control.queue.updated` | `queue=[{"id":"steering[0]","text":"完成后简要总结即可"}]` |
| `control.command.delivered` | `sequence_no=1`、脱敏后的 `command_id=<UUID:...>`、`payload_digest`，没有类型和文本 |
| 第二条 `control.queue.updated` | `queue=[]`，表示队列排空 |

因此当前页面出现“两条控制队列已更新 + 一条已送达”，但只有右侧实时引导历史能显示
“转向 + 完成后简要总结即可”。两条 queue update 分别是入队和排空，不代表用户发送了两次命令。

现有前端其实已经准备了类型和正文的展示分支：

- [`taskProcessUtils.ts`](../../frontend/src/components/task-process/taskProcessUtils.ts) 会从
  `TaskLog.metadata.command_type` 和 `text` 解析控制事件；
- [`TaskProcessControlEventRow.vue`](../../frontend/src/components/task-process/TaskProcessControlEventRow.vue)
  会在字段存在时展示类型与正文；
- [`TaskSteeringPanel.vue`](../../frontend/src/components/TaskSteeringPanel.vue) 通过 commands API
  已能展示完整命令历史。

缺口位于产品投影：[`worker_event_projector.py`](../../backend/app/core/worker_event_projector.py)
目前把 Canonical Event payload 基本原样写入 `TaskLog`，而 Pi 的 ACK payload 按合同本来就不重复携带
命令类型和文本。

## 3. 目标

- 用户能在事件发生的位置看见引导类型、实际消息、状态、序号和时间。
- 一条用户命令只有一条可见结果事件，不重新制造 ACK 重复记录。
- `steer`、`follow_up`、`delivered`、`rejected` 和 `outcome_unknown` 使用统一展示合同。
- 命令正文继续经过现有凭据脱敏逻辑，不能从队列文本或时间戳猜测归属。
- 刷新页面后展示不依赖前端内存或发送该命令的浏览器会话。

## 4. 非目标

- 不修改 `codify.worker.event/v1` / V2 Canonical Event 字段要求。
- 不让 Pi Adapter 在 ACK 中重复发送正文。
- 不新增 `control.command.queued`、`consumed` 或 `applied` 状态。
- 不把 queue 排空解释为“模型已执行”或“引导已生效”。
- 不新增数据库字段、迁移、配置开关或单独的事件聚合服务。
- 不在首版回填已有 `TaskLog`；Task `#570` 是问题证据，不是历史改写目标。
- 不改变 OpenCode、Claude、Codex 当前未声明实时引导能力的事实。

## 5. 数据所有权与事件链

```text
用户发送 steer / follow_up
        │
        ▼
TaskHarnessCommand
  类型、正文、序号、digest、状态的事实源
        │
        ▼
Command Pump ─────► Pi control endpoint
                         │
                         ├─ queue_update      ─► control.queue.updated
                         └─ native ACK        ─► control.command.delivered/rejected
                                                    │
                                                    ▼
                                           WorkerEventProjector
                                           精确关联命令并补全
                                                    │
                                                    ▼
                                            TaskLog + SSE + UI
```

边界保持如下：

- Command Pump 负责命令行状态 `queued → dispatching → delivered|rejected|outcome_unknown`。
- Harness 原生 ACK 是 `delivered/rejected` 可见事件的唯一来源。
- `control.queue.updated` 是 attempt 级传输审计；Pi 原生 queue update 没有 Codify command ID。
- `TaskLog` 是面向产品 UI 的稳定投影，可以包含从同库命令事实补充的可读字段。

这与 [`open-harness-v2-schemas.md`](./open-harness-v2-schemas.md) 的控制面边界一致：
Canonical Event 保留可验证的传输证据，commands API/数据库保留完整命令事实。

## 6. 产品投影合同

### 6.1 可见命令事件

Projector 写入的 `TaskLog.log_metadata` 目标形态：

```json
{
  "type": "control.command.delivered",
  "command_id": "<UUID:...>",
  "sequence_no": 1,
  "payload_digest": "...",
  "delivered_at": "2026-09-11T00:44:54.340481+00:00",
  "command_type": "steer",
  "text": "完成后简要总结即可"
}
```

`command_type` 与 `text` 是产品投影字段，不加入 Canonical Event 合同。

### 6.2 精确关联

收到 `control.command.delivered` 或 `control.command.rejected` 后：

1. 使用 `task_id` 和 `ingest.attempt.attempt_id` 限定当前 Task/attempt。
2. 使用 payload 中的 `sequence_no` 查询 `TaskHarnessCommand`。
3. 同时校验 `payload_digest` 完全一致。
4. 仅在全部匹配时复制 `command_type` 和经过 `sanitize_sensitive_data()` 的 `payload.text`。
5. 关联失败时保留原有身份/状态事件并记录服务端警告；不猜测类型或正文，也不让展示增强导致 Task 失败。

不使用 `command_id` 做数据库关联。Canonical Event 归档会把真实 UUID 稳定脱敏为 `<UUID:...>`，而
`task_harness_commands.command_id` 保存原始 UUID，两者不能直接相等。

不解析 `queue[].id` 中的 `steering[0]` / `followUp[0]` 来推断类型。这是 Pi 原生队列的位置标识，
不是稳定命令身份，也不能扩展到未来其他 Harness。

### 6.3 `outcome_unknown`

`control.command.outcome_unknown` 没有 Harness 原生 ACK，仍由现有后端命令路径产生。所有产生路径应
写入同一组公共展示字段：

```text
sequence_no, command_type, sanitized text, code
```

不得为了统一展示而让 Command Pump 重新写 `delivered/rejected`，否则会恢复重复 ACK 问题。

## 7. 默认事件流展示

| 事件 | 默认事件流 | 展示语义 |
|---|---:|---|
| `control.command.delivered` | 是 | `Harness 已接收`；不承诺模型已消费或执行 |
| `control.command.rejected` | 是 | `已拒绝`，并展示公共拒绝原因 |
| `control.command.outcome_unknown` | 是 | `结果未知`；不自动重投 |
| `control.queue.updated` | 否 | 仅保留在持久化审计、运行归档或后续技术详情中 |
| `agent_settled` | 否 | 维持当前内部控制信号边界 |

首版直接在 `normalizeTaskProcessRows()` 中过滤 `control.queue.updated`。不增加“显示系统事件”开关；
只有出现明确的日常排障需求后再增加。

## 8. UI 合同

### 8.1 行布局

送达：

```text
[转向] Harness 已接收                              08:44:55
完成后简要总结即可
#1
```

拒绝：

```text
[续接指令] 已拒绝                                  08:44:55
完成当前步骤后继续检查测试
原因：任务正在收尾，不再接收新命令
#2
```

规则：

- 类型是主视觉标签，不能只作为灰色技术元数据。
- 中文映射为 `steer → 转向`、`follow_up → 续接指令`；代码值保持不变。
- 不在实时引导上下文使用“追加任务”，避免与创建新的 Codify Task 混淆。
- 正文保留换行并允许断词；首版沿用当前最大 4,000 UTF-16 code units，不新建 payload/展开机制。
- 默认只展示 `#sequence_no`；`cmd <UUID:...>` 不提供用户决策价值，从主视图移除。
- 时间使用现有事件时间展示。
- “已送达”统一为“Harness 已接收”，与现有说明文字的 ACK 语义一致。

### 8.2 状态语义

`delivered` 只表示 Harness 原生接口返回成功 ACK。页面不得显示“已执行”“已采用”“已生效”等更强
结论，也不能根据后续 `queue=[]` 推断模型消费。现有说明文字继续保留：

> “Harness 已接收”仅表示接口确认收到，不保证模型已消费该消息。

## 9. 实施范围

### 9.1 后端

- [`worker_event_projector.py`](../../backend/app/core/worker_event_projector.py)
  - 对 `delivered/rejected` 做 attempt + sequence + digest 的精确命令关联；
  - 写入公共展示字段；
  - 关联失败时 fail closed，不影响 Canonical Event 收据和 Task 生命周期。
- [`worker_command_pump.py`](../../backend/app/core/worker_command_pump.py) 与
  [`task_command_gate.py`](../../backend/app/core/task_command_gate.py)
  - 仅对 `outcome_unknown` 的现有产生路径补齐相同展示字段；
  - 保持不写 native `delivered/rejected` 事件。

### 9.2 前端

- [`taskProcessUtils.ts`](../../frontend/src/components/task-process/taskProcessUtils.ts)
  - 继续读取顶层 `command_type` / `text`；
  - 从默认事件流过滤 `control.queue.updated`。
- [`TaskProcessControlEventRow.vue`](../../frontend/src/components/task-process/TaskProcessControlEventRow.vue)
  - 提升类型标签和消息正文；
  - 隐藏默认 command ID，保留序号、状态和时间。
- 中英文 i18n
  - `follow_up` 在实时引导上下文改为“续接指令”；
  - `delivered` 改为“Harness 已接收”；
  - 英文保持 `Steer`、`Follow-up`、`Harness accepted`。

### 9.3 明确不改

- Harness Adapter 与 Worker Kit event schema；
- `TaskHarnessCommand` 表结构和 commands API；
- TaskLog 表结构与 SSE 协议；
- Runtime Bundle / Worker Profile capability；
- 历史数据。

### 9.4 落地补充：本地拒绝的可见投影

实施 §10.3「closing 后拒绝」验收时确认：Pi 不会在原生 ACK 中拒绝命令——Task 609 在 attempt 已
`closing`、Pi 已 `agent_settled` 之后投递的 `steer` 仍返回 `success:true`（命令 `delivered`），开发库
历史上也从未产生过 `control.command.rejected` 收据。也就是说，§7 要求的可见拒绝无法只靠原生 ACK。

因此为「已入队、但未送到 Harness 就被后端确定性拒绝」的命令补齐同一套产品投影：

- `close_control_gate` / `request_force_close_after_unknown_follow_up` 的 `queued → rejected`
  （`control_gate_closed`）；
- Command Pump 的 `DISPATCH_REJECT`（owner/bridge 在原生请求之前拒绝：进程已退出、attempt 不匹配、
  gate 非 `accepting|closing`）。

这两类路径上原生请求根本没有发出，因此不存在原生 ACK，补齐投影不会与 §1.2 / §9.1 的「不重复制造
ACK 记录」冲突；每条被拒命令仍然只有一条可见结果事件。Command Pump 只在 `native_sent_at` 为空
（即原生请求确实没有发出）时才投影本地拒绝：一旦原生已发送，拒绝事件由 Harness ACK 独占。
拒绝原因按 commands API 的同一份公共映射投影（`PUBLIC_REJECTION_MESSAGES`），不暴露
bridge/transport 诊断文本；该映射因此从 `app/api/task_command_routes.py` 移入
`app/core/task_harness_commands.py`，HTTP 与事件流共用一份。

## 10. 验证与验收

### 10.1 后端回归

1. 精确匹配的 delivered 事件只生成一条 `TaskLog`，包含 `steer` 和脱敏正文。
2. 精确匹配的 rejected 事件包含类型、脱敏正文和公共拒绝原因。
3. digest 或 attempt 不匹配时不补正文、不串到其他命令，Canonical Event 仍正常落收据。
4. 正文中的凭据模式在事件流中被脱敏。
5. `outcome_unknown` 的所有入口都包含类型和脱敏正文。
6. 保留现有“Command Pump 不重复写 native ACK 事件”的回归。

### 10.2 前端回归

1. delivered/rejected/outcome_unknown 行显示类型、状态、正文、序号和时间。
2. `control.queue.updated` 不计入可见事件行和事件数量。
3. command ID 不出现在默认行；缺少补充字段的旧事件仍能安全显示状态和序号。
4. `steer` 与 `follow_up` 使用不同且正确的本地化标签。
5. 长文本、换行和脱敏占位符不破坏事件流宽度。

### 10.3 真实 Task 验收

在同一冻结 Git SHA、Backend/Nginx image 和 Worker Kit/Bundle composition 上验证：

| 场景 | 必须看到 |
|---|---|
| Pi 运行中发送 steer | 一条“转向 · Harness 已接收”，正文与命令历史一致 |
| Pi 当前轮结束前发送 follow_up | 一条“续接指令 · Harness 已接收”，下一轮按原生语义开始 |
| closing 后拒绝 | 一条“已拒绝”，类型、正文和公共原因正确 |
| 页面刷新 | 展示保持一致，不依赖发送页面内存 |
| 查看运行归档 | queue update 和 ACK 原始审计仍存在 |

送达场景每条命令必须只有一条可见结果事件。queue update 不出现在默认事件流，但不能从归档和数据库
审计中删除。

## 11. 发布与历史边界

本改动是展示投影增强，不需要停机迁移。部署后新摄取的控制事件获得完整字段；此前已经写入的
`TaskLog` 保持原样，实时引导历史面板仍通过 commands API 展示正确的类型、文本和最终状态。

首版不增加读时 join、一次性 SQL 或历史回填脚本。只有确认历史 Task 的事件流也必须修复时，才单独
设计基于 `task_id + sequence_no + payload_digest` 的受控回填，并在执行前验证匹配唯一性。

## 12. 完成定义

以下条件全部满足后，本方案才算完成：

- 源码和回归测试通过；
- 开发环境使用同一不可变 composition 完成 steer、follow-up、拒绝和刷新验收；
- 每条命令只有一个用户可见结果事件；
- 默认事件流不再出现无解释价值的“控制队列已更新”；
- 页面没有把 ACK 表述为模型已经执行；
- 没有数据库迁移、Canonical Event 合同变更或历史回填。
