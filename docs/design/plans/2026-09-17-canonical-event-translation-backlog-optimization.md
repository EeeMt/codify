# Canonical Event 翻译积压优化方案（Task 690）

日期：2026-09-17

状态：P0 已实施；开发环境验收通过；P1 未触发。

相关文档：

- [Worker Canonical Event v1](../architecture/worker-canonical-event-v1.md)
- [Open-Harness V2 Phase 3 OpenCode 一级 Harness](../architecture/open-harness-v2-phase3-opencode-design.md)
- [Open-Harness V2 四 Harness Subagent 适配方案](../architecture/open-harness-v2-subagent-adaptation.md)

## 1. 结论

Task 690 不是模型、OpenCode Server 或 Scheduler 卡死，而是 OpenCode 原生事件已经接近结束后，
Adapter 仍在逐条翻译大量文本增量。当前每条 canonical 事件都会启动一次 Python writer；writer
又会在锁内重新读取整个 `event.jsonl`，最后逐条 `fsync`。大量 `message.delta` 把固定开销和
全量扫描放大成分钟级 terminal drain，页面因此长时间停留在 `RUNNING`。

本次采用两项最小修复：

1. 在 OpenCode Adapter 内合并同一消息、同一 agent 的连续文本增量，保留有界实时预览。
2. 将 Canonical Event writer 的普通事件检查从全量扫描改为读取首条、末条记录；只有生命周期
   边界事件才扫描完整历史。

保留原始事件归档、Canonical Event 合同、文件锁和持久化语义。不新增数据库字段、配置开关、
后台队列、writer daemon 或前端状态。

## 2. 事故证据与影响范围

### 2.1 Task 690

开发环境 Task 690 的最终事实为：

| 项目 | 结果 |
|---|---|
| Harness | OpenCode，包含 subagent 输出 |
| 最终状态 | `COMPLETED` |
| 总耗时 | 13 分 27 秒 |
| Worker 退出码 | `0` |
| 错误 | 无 |
| 代码变更 | 0 |
| 运行归档 | 已落盘，约 433 KB |
| `message.delta` | 5,309 条 |

排查期间观察到：

- OpenCode 原始事件文件已经停止或低速增长，原生 subagent 已记录为 completed。
- Adapter 只以每秒少量记录的速度推进，Worker 持续高 CPU。
- 活跃子进程反复执行 `events.py message.delta ...`。
- 积压排空后 Worker 正常退出，Canonical Event terminal、任务终态和归档全部落盘。

因此这次问题应定义为“事件翻译积压导致的假性卡住”，不能通过缩短 Task 超时、自动取消或
前端改文案处理。

### 2.2 四 Harness 边界

四个 Python Adapter 都通过 `subprocess.run` 调用同一个 Canonical Event writer，但输入密度不同：

| Harness | 当前行为 | 已知风险 |
|---|---|---|
| OpenCode | 文本 delta 逐条生成 `message.delta` | Task 690 已确认分钟级积压 |
| Pi | 文本 delta 逐条生成 `message.delta` | 近期任务有 1,500–2,700 条，存在同类压力；尚未证明与 Task 690 相同的 terminal drain |
| Claude | 部分消息逐增量映射 | 当前样本量较小，存在结构性风险但未复现同等级积压 |
| Codex | 文本增量在 Adapter 内累积，完成时输出 | 文本路径风险最低；其他事件仍使用公共 writer |

P0 只改变已确认问题的 OpenCode 文本路径，并优化所有 Harness 共用的 writer 普通事件路径。
Pi、Claude 的增量合并在 P0 验收后按证据决定，不在本次预先扩面。Codex 保持现状。

## 3. 当前链路与根因

当前链路为：

```text
OpenCode SSE / durable event
  -> opencode_events.py translate()
  -> 每条事件 subprocess.run(events.py)
  -> events.py 获取文件锁
  -> 从头解析 event.jsonl，推导 seq / terminal 状态
  -> 追加一条 JSON，flush + fsync
  -> WorkerEventProjector 接收并投影
  -> TaskLog / SSE / 页面
```

### 3.1 一对一 delta 放大

[OpenCode Adapter](../../../deploy/worker-entrypoint/harness/adapters/opencode_events.py) 将多个原生文本事件族
的一小段文本直接映射为一条 `message.delta`。Canonical Event 合同只要求增量可以按顺序拼接，
不要求保持上游 token 或原生事件的粒度，因此一对一映射没有业务收益。

### 3.2 每条事件启动进程

`opencode_events.py::_emit()` 每次通过 `subprocess.run` 启动 `events.py`。进程创建、解释器启动、
模块导入和 JSON 序列化都成为逐事件固定成本。Claude、Codex 和 Pi Adapter 使用相同模式。

### 3.3 Writer 普通路径为 O(n)

[Canonical Event writer](../../../deploy/worker-entrypoint/harness/events.py) 当前在每次 append 前读取并解析
全部历史记录，以得到首条身份、末条类型、序号和是否已出现 Harness terminal。一次包含 `n` 条事件
的运行累计接近 `O(n²)`；事件越多，后面的单条写入越慢。

### 3.4 持久化和下游开销被同步放大

每条 canonical 事件都执行一次 `flush + fsync`，后端也会为每条事件保存收据并执行投影。后端
[WorkerEventProjector](../../../backend/app/core/worker_event_projector.py) 已经把同一 agent 的文本增量
合并到一条流式 `TaskLog`，因此在源头合并 delta 不会改变最终页面数据模型，反而减少整条链路的
无效工作。

## 4. 目标与非目标

### 4.1 目标

- 大量文本输出不再造成分钟级 terminal drain。
- 页面继续获得有界延迟的流式预览，最终文本与当前实现完全一致。
- root 与 subagent 的消息归属、全局事件顺序和 terminal 顺序保持不变。
- `event.jsonl` 的 `seq` 连续，文件仍是恢复后的唯一序号事实来源。
- 原始 Harness 事件继续逐条、脱敏归档，Canonical Event 只优化投影粒度。
- 变更同时降低 Worker CPU、文件 I/O 和后端 canonical receipt 数量。

### 4.2 非目标

- 不修改 Canonical Event schema 或 `message.delta` 语义。
- 不新增数据库迁移、API、前端 Harness 分支或“疑似卡住”状态。
- 不取消文件锁，不降低 terminal 校验，不把内存计数器当作恢复事实。
- P0 不移除逐批 `fsync`，不增加异步队列、writer daemon 或 group commit。
- 不为历史 Task 重写事件；Task 690 保持原始证据。

## 5. P0 设计

### 5.1 合并 OpenCode 连续文本增量

在 `opencode_events.py` 增加一个进程内 pending delta，不新增通用框架。pending 状态至少包含：

```text
agent identity
message identity
concatenated text
first raw line
last raw line
first monotonic timestamp
```

只合并连续且同时满足以下条件的增量：

- 事件类型都是 `message.delta`；
- 属于同一 assistant message；
- `payload.agent` 相同；
- 中间没有工具、思考、控制、usage、完成或 terminal 事件。

刷新规则：

1. 每个 message/agent 的第一段非空 delta 立即输出，用于尽快创建页面流式行。
2. 后续连续文本先进入 pending buffer。
3. pending 文本达到 1 KiB 时输出。
4. pending 存续达到 250 ms 且仍有原生事件进入时输出；使用 `time.monotonic()`，不创建 timer 线程。
5. agent/message 切换前输出旧 buffer。
6. 任何非 `message.delta` canonical 事件之前先输出 buffer，保证事件顺序。
7. `message.completed`、Harness terminal、取消、失败和 EOF 之前必须输出 buffer。

1 KiB 和 250 ms 是代码常量，不增加运行时配置。当前阶段的目标是控制事件数量并保留实时反馈，
没有多租户或按模型调参需求。

合并后的 canonical `raw_ref` 指向该批最后一条原始记录。完整范围仍可在原始归档中还原；本次不扩展
`raw_ref` schema。`message.completed` 继续携带完整最终文本，是最终内容的权威来源。

### 5.2 保持 agent 与消息隔离

OpenCode 的 root 与多个直接 subagent 事件可能交错。合并只能发生在连续的同归属增量之间：

```text
root.delta(A) -> child.delta(B) -> root.delta(C)
```

必须输出为三个有序批次，不能将 `A + C` 跨过 child 事件合并。现有 `_CURRENT_AGENT` 仍是
canonical agent attribution 的唯一入口；buffer 保存入队时的 agent 快照，刷新时不能读取已经变化的
全局 agent。

### 5.3 优化 Writer 普通事件检查

在文件锁内增加小型 stream-state 读取函数：

1. 空文件保持现有 `run.started` 首条规则。
2. 从文件开头读取第一条非空、完整 JSON 记录，用于校验 Harness 身份。
3. 从文件末尾反向读取最后一条非空、完整 JSON 记录，取得 `seq` 和 `type`。
4. 下一序号为 `last_event.seq + 1`；`seq` 缺失、非正整数或末条 JSON 不完整时 fail closed。
5. 普通事件不再解析中间记录。
6. 只有以下生命周期边界需要扫描完整历史以判断 Harness terminal 是否已出现：
   - `harness.completed` / `harness.failed`
   - `delivery.*`
   - `worker.finalization`
   - `run.completed` / `run.failed`

末条类型仍负责现有的“Task terminal 后不可追加”“finalization 后只能跟 Task terminal”等相邻顺序
约束。完整扫描只发生在少量生命周期边界，不影响大规模 delta 热路径。

该实现不新增 `.event-seq` 或状态 sidecar。容器/进程恢复后，序号仍从已 `fsync` 的末条 canonical
记录推导；现有 state-loss 恢复测试继续成立。

### 5.4 错误和取消

- buffer 刷新失败时保持 fail closed，Adapter 不吞掉 writer 错误。
- OpenCode 已知的“共享 canonical 流已关闭”判断继续适用，只丢弃 terminal 后迟到的翻译事件。
- 取消或失败必须先刷新已经观测到的文本，再发 reasoning/tool 中断和 Harness terminal。
- 不允许为了完成 buffer 刷新而越过已写入的 Task terminal。
- 原始事件文件的写入与清洗规则不变。

## 6. P1 条件触发项

只有 P0 在新 Task 上仍未达到第 9 节门槛时，才继续以下工作。

### 6.1 去除 Python Adapter 的逐事件子进程

让长期运行的 Python Adapter 直接调用公共 `events.emit()`，Shell Runner 和 finalizer 继续使用
`events.py` CLI。直接调用必须保留同一文件锁、错误传播、stderr preview、terminal 约束和恢复语义。

不先实现常驻 writer 子进程：Adapter 本身已经是长期 Python 进程，增加第二套进程协议没有必要。

### 6.2 将 delta 合并扩展到 Pi、Claude

满足以下任一条件再扩展：

- 新鲜 Pi/Claude Task 的 `message.delta` 超过 1,000 条；
- 最后一条原始 Harness 事件到 Harness terminal 超过 5 秒；
- Worker 在原生执行结束后仍因 translator 持续高 CPU。

扩展时沿用 OpenCode 已验收的顺序、agent/message 隔离和刷新规则。Codex 已经聚合文本，保持现状。

### 6.3 仍不默认采用的方案

即使进入 P1，也不默认取消 `fsync`、批量提交数据库事务或新增异步 writer 队列。这些改动会改变
故障恢复和实时投影边界，只有在 P1 仍有实测瓶颈时另行设计。

## 7. 文件范围

P0 预计只修改：

| 文件 | 变更 |
|---|---|
| `deploy/worker-entrypoint/harness/adapters/opencode_events.py` | 连续文本 delta 合并、刷新边界、计数测试 seam |
| `deploy/worker-entrypoint/harness/events.py` | 首/末记录热路径、生命周期边界全量校验 |
| `backend/tests/unit/test_opencode_harness_adapter.py` | 文本、顺序、subagent、取消/EOF 回归 |
| `backend/tests/unit/test_claude_harness_adapter.py` | 公共 writer 顺序、恢复和 malformed tail 回归 |

不修改：

- `backend/app/core/worker_event_projector.py`
- Canonical Event schema 与文档
- 数据库模型和 migration
- API、SSE 与前端组件
- Worker Kit 内的 OpenCode CLI 版本

## 8. 自动化验证

### 8.1 OpenCode Adapter

新增聚焦测试：

1. 5,000 个单字符连续 delta 合并后 writer 调用数量下降至少 95%。
2. 合并后的文本按顺序拼接，与原始文本逐字一致。
3. 第一段 delta 立即输出，达到大小/时间阈值后刷新。
4. `message.completed` 前刷新 pending 文本，最终正文不重复、不缺失。
5. `message.delta -> tool.started -> message.delta` 不跨工具事件合并。
6. root/child 交错流不串 agent，不改变全局顺序。
7. 多个 child 即使复用原生 message/part ID 也按 agent 隔离。
8. `session.idle`、失败、取消和 EOF 均不会遗留 pending buffer。
9. writer 失败仍使 translator 失败；terminal 后迟到事件保持现有安全丢弃规则。

CI 不使用墙钟性能断言。性能回归通过固定输入下的 writer 调用次数和 canonical 事件数量判断，避免
不同 Runner 的调度抖动造成假失败。

### 8.2 Canonical Event writer

新增或保持以下测试：

- 末条 `seq` 推导出的下一序号连续。
- 删除 lock 和旧 sidecar 后仍能从 stream 恢复。
- 并发调用在文件锁下得到唯一连续序号。
- 空流首条必须是 `run.started`。
- Harness 身份变化、重复 Harness terminal、delivery 越界、finalization/Task terminal 顺序继续拒绝。
- 末条 JSON 截断或非法时 fail closed，不覆盖、不跳号。
- 普通 `message.delta` 路径不调用全文件扫描 helper。

### 8.3 聚焦命令

```bash
backend/.venv/bin/python -m pytest \
  backend/tests/unit/test_opencode_harness_adapter.py \
  backend/tests/unit/test_claude_harness_adapter.py -q

git diff --check
```

若 P1 修改其他 Adapter，再加入对应 Pi、Claude、Codex Adapter 测试；P0 不为未修改路径扩大测试面。

## 9. 开发环境验收

### 9.1 验收前提

- 按现有流程重建并重启承载 Runtime Bundle 源码的 backend/scheduler。
- 验证两项服务健康、运行镜像身份和容器内实际部署源码。
- 必须创建新的 OpenCode Task；Runtime Bundle 是不可变快照，重试 Task 690 不能验证新实现。
- 验收 Task 使用 subagent 和足量文本输出，确保原始 delta 数量接近或超过 Task 690 的量级。

### 9.2 门槛

| 指标 | 通过门槛 |
|---|---|
| 文本正确性 | 最终 `message.completed`、页面正文与原始输出一致 |
| delta 压缩 | 5,000 个小 delta 对应的 canonical `message.delta` 至少下降 95% |
| 实时反馈 | 持续有原始事件时，页面更新间隔不超过约 500 ms |
| terminal drain | 最后一条原始 Harness 事件或 `session.idle` 到 Harness terminal 不超过 5 秒 |
| Worker | 原生执行结束后不再持续高 CPU 排空翻译队列 |
| 协议 | `seq` 从 1 连续；唯一 Harness terminal、`worker.finalization` 和 Task terminal，Task terminal 最后 |
| 归档 | raw/canonical/result/console 归档完整且可解析 |
| 任务结果 | Worker exit 0；Task `COMPLETED`；状态、DB、归档一致 |
| subagent | root/child 文本、工具、reasoning 归属正确，不串归属、不重复 |

另外各创建一个低输出 OpenCode Task 和取消 Task，确认 batching 没有让短回复延迟到不可见，也没有
改变取消终态。

## 10. 实施顺序与完成定义

实施顺序：

1. 增加 OpenCode delta 合并及其单测。
2. 优化 writer 普通事件读取路径并补协议回归。
3. 运行聚焦测试和 `git diff --check`。
4. 重建开发环境运行时来源，并核对实际部署源码。
5. 创建新的 OpenCode 高 delta、低输出和取消 Task，记录 DB、归档、容器与页面证据。
6. 达到全部 P0 门槛即停止；未达到时用证据决定是否进入 P1。

完成定义：

- [x] Task 690 量级的 OpenCode 输出不再产生分钟级翻译积压。
- [x] 文本、agent attribution、工具/reasoning 顺序和最终状态无回归。
- [x] Canonical Event 恢复、连续序号和 terminal 不变量全部通过。
- [x] 新 Runtime Bundle 的真实 Task、归档、DB 和页面证据一致。
- [x] 没有为未出现的瓶颈引入 P1/P2 机制。

## 11. 实施结果（2026-09-17）

### 11.1 代码与部署

- `opencode_events.py` 已对同一 agent、同一消息的连续文本 delta 做 1 KiB / 250 ms 有界合并；首段即时输出，消息、工具、agent、终态和 EOF 边界先刷新 pending。
- `events.py` 普通路径改为读取首条与末条记录，生命周期边界保留全量扫描；末条 `seq` 非法或截断时 fail closed。
- 聚焦回归测试：`169 passed`；变更文件 `ruff check`、`python -m py_compile` 与 `git diff --check` 通过。
- 开发环境已重建 backend/scheduler；Profile 4 `verify-runtime` 通过，四个 Harness 均验证为 ready，Kit `0.6.19`。

### 11.2 真实 Task 证据

| Task | 场景 | 结果 |
|---|---|---|
| 692 | 高输出 OpenCode + subagent | `COMPLETED`，Worker exit 0；原始文本 delta 19,790 条，canonical `message.delta` 161 条，压缩 99.19%；canonical 481 条事件的 `seq` 为 1..481；连续文本批次最大间隔 436.7 ms；最后 raw `session.idle` 对应的 canonical 收口链路从 `message.completed` 到 `harness.completed` 为 289.7 ms；21 条消息最终正文与 raw 最终文本一致；页面真实 DOM 显示 `Completed`、Subagent、结果正文和运行统计。 |
| 693 | 低输出 OpenCode | `COMPLETED`；251 input / 5 output tokens；18 条 canonical 事件，序号连续并以 `run.completed` 收口。 |
| 695 | Worker 已写入运行日志后的取消 | `CANCELLED`；archive 可解析，7 条 canonical 事件，序号连续，`harness.failed → worker.finalization → run.failed` 完整收口。 |

P0 门槛已满足，因此不进入 P1：未移除逐批 `fsync`，未添加异步队列、sidecar、daemon 或其他未被证据触发的机制。
