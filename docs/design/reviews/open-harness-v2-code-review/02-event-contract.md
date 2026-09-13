# 02 事件契约与投影 —— Code Review

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56`（基线 `7b253fbf`，2026-08-20；当前 `dev @ cbad9e56`） |
| 主要文件 | `backend/app/core/harness_protocol.py`(+409/-7)、`worker_event_projector.py`(+452/-18)、`worker_results.py`(+267/-6)、`task_failure_details.py`(+231)、`task_failure_summary.py`(+4/-1)、`worker_task_outcomes.py`(+16/-3)、`backend/app/api/task_log_stream.py`(+36) |
| 一起读的依赖上下文 | `backend/app/core/harness_attempts.py`(+201)、`task_command_gate.py`、`task_harness_commands.py`、`worker_task_artifacts.py`(+73)、`worker_task_lifecycle.py`（终态段）、`backend/tests/fixtures/harness_events_v2/`（9 个 V2 fixture）与 `harness_events/`（V1 对照）、worker 侧 `deploy/worker-entrypoint/harness/events.py` 与 `adapters/{pi,claude,codex,opencode}_events.py`、`pi_owner.py`、`pi_bridge.py` |
| 审查方法 | 静态阅读**当前完整文件**（含调用方）+ 冻结契约对照（`open-harness-v2-schemas.md` §3/§4/§5、`worker-canonical-event-v1.md`、`open-harness-v2.md` §6.2/§9.3、`implementation-plan` §4.3、`live-steering-event-stream-projection.md` §9.4）+ 生产者/消费者字段逐一核对 + 窄范围单测 + 独立最小复现 |
| 未覆盖 | 四个 adapter 对上游 CLI/Server 的逐行翻译语义（T04/T05/T06）、命令投递泵与 gate 状态机实现细节（T01）、前端呈现（T12）、清洗器模式表本身（T13）、迁移（T14） |

本次实际执行的验证：

| 命令/操作 | 结果 |
|---|---|
| `.venv/bin/python -m pytest tests/unit/test_harness_protocol.py tests/unit/test_harness_events_v2.py tests/unit/test_task_event_archive.py tests/unit/test_task_failure_details.py -q` | 83 passed |
| `.venv/bin/python -m pytest tests/unit/test_harness_attempts.py -q` | 10 passed |
| `.venv/bin/python -m pytest tests/unit/test_worker_payload_storage.py -q` | 24 passed |
| 独立复现（纯函数，无 DB）：`iter_complete_jsonl_records` 对 U+2028/U+2029/U+0085 的切分行为 | 见 EVT-INFO-01 |
| 独立复现（无 DB）：用 V2 fixture 构造 `control.command.rejected` + `rejection_message=null` 后 `validate_event_v2` | `HarnessProtocolError: control.command.rejected requires rejection_message`（见 EVT-02） |
| 未运行 | 全量 pytest、任何 Docker/真实 Harness 场景、前端 `npm run build`、任何需要 Postgres/网络的集成路径 |

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 1 |
| FIX_IF_CHEAP | 3 |
| DEFER | 3 |
| ACCEPT/CLOSE | 3 |

V2 事件契约层整体是**收紧**而非放松：V1 常量与 `validate_event()` 原样保留、按事件自带 `schema` 分发且强制与 `attempt.event_schema` 一致，幂等/唯一/唯一 terminal 等不变量在「增量校验 + 全量 replay」两处实现，窄范围测试全部通过。FIX_NOW 只有 EVT-02（Pi 回 `success:false` 时产出被后端 schema 拒绝的 `rejection_message=null`，修法 1 行）。ACCEPT/CLOSE 三项按本部署 profile 书面接受：内网、3 用户、无可用性要求，唯一硬约束是保住统计口径的历史数据，补齐均属过度防御。

## 2. 问题清单

### EVT-02 `control.command.rejected` 生产者可产出 `rejection_message=null`，被后端 schema 拒绝
- **判定**：FIX_NOW —— 修法 1 行
- **状态**：已修复（`7794eb92`，与 PI-01 同一处代码）：rejected 事件补齐 `rejection_message`
- **位置**：`backend/app/core/harness_protocol.py:346-354`（提交 `72140882`），生产者 `deploy/worker-entrypoint/harness/adapters/pi_events.py:604-613`（提交 `e7f8c020`）、`deploy/worker-entrypoint/harness/adapters/pi_owner.py:356-361`
- **证据**：后端强制 `rejection_message` 必须是字符串：

```python
elif event_type == "control.command.rejected":
    for key in ("command_id", "payload_digest", "sequence_no", "rejection_code"):
        if payload.get(key) is None:
            raise HarnessProtocolError(f"control.command.rejected requires {key}")
    if not isinstance(payload.get("rejection_message"), str):
        raise HarnessProtocolError("control.command.rejected requires rejection_message")
```

  生产者侧：`pi_events._handle_response()` 在 `command in {steer, follow_up}` 且 `success` 为假时发出该事件，`rejection_message: ack.get("rejection_message")`；`ack` 来自 `pi_owner.command_metadata[native_id]`（`pi_owner.py:356-361`），该 dict **只**包含 `command_id/sequence_no/payload_digest/_delivered_at`，既无 `rejection_message`，也无 `rejection_code`（于是恒回落到默认 `delivery_outcome_unknown`，即使 `pi_owner.py:384` 已把真实原因记为 `native_rejected`）。`success = bool(record.get("success"))`（`pi_events.py:556`），因此任何 `success:false`（或缺少 `success`）的 steer/follow_up 响应都会走到这一支；该分支是**有意实现且有测试**的（`backend/tests/unit/test_pi_harness_adapter.py:1595-1617`，测试只断言 `command_id/sequence_no`，未校验 payload 是否通过 V2 schema）。
  最小复现（本次已运行，无 DB）：取 `tests/fixtures/harness_events_v2/pi/rejected.v2.jsonl` 的第 2 条事件，把 `payload.rejection_message` 置为 `null`（即上述代码会产出的形状）后调用 `validate_event_v2` → `HarnessProtocolError: control.command.rejected requires rejection_message`。
- **影响**：该记录一旦进入 `event.jsonl`，`ingest_event_records_from_chunk` 会在循环内抛错整块回滚（见 EVT-03），游标不前进 → 之后所有事件（含 Harness terminal、`worker.finalization`、`run.completed`）都投影不到，Task 最终被 `parse_task_result` 判为 `protocol_error: canonical attempt is missing a Task terminal`（`worker_results.py:526-529`），而容器实际可能已成功完成。触发条件明确：Pi 对 steer/follow_up 返回 `success:false`（`live-steering-event-stream-projection.md` §9.4 记载开发库历史未出现过，故为潜在缺陷而非已知线上事故）。
- **最小动作**：`pi_events._handle_response` rejected 分支：`rejection_message: ack.get("rejection_message") or "Harness rejected the control command"`
- **验证**：本次已用 `validate_event_v2` 复现拒绝；修复后应以同样的最小复现断言通过，并补一条「pi_events 产出的 rejected payload 通过 `validate_event_v2`」的测试。

### EVT-03 单条非法记录使整条事件流永久卡死，Task 被误判为缺少终态
- **判定**：FIX_IF_CHEAP
- **位置**：`backend/app/core/worker_event_projector.py:770-789`（提交 `72140882` 引入字段级 schema 分发，整块失败结构为 V1 遗留）
- **证据**：`ingest_event_records_from_chunk()` 在循环内 `validate_event_by_schema(record)` / `decode_event_line(raw)`，任何一条抛错都会在 `cursor.last_offset += processed` **之前**中断整个 chunk：

```python
for raw in records:
    record = decode_event_line(raw)
    normalized = validate_event_by_schema(record)
    ...
    processed += len((raw + "\n").encode("utf-8"))
cursor.last_offset += processed   # 只有全部成功后才会执行
```

  `tail_event_jsonl` 捕获后 `await db.rollback()` 再 `raise`（`:800-818`），游标因回滚保持原值 → 下一次轮询从同一字节偏移重读 → 同一条记录再次失败，**永久**卡在同一条记录上。上层 `poll_task_artifacts` 以 `logger.debug` 吞掉该异常并每 2 秒重试（`worker_task_artifacts.py:249-262`），因此线上表现为「静默无进展」；`flush_task_artifacts` 的归档回填（`worker_task_artifacts.py:343`）同样从该偏移开始，也必然再抛。最终 `parse_task_result` 找不到 `run_result` 日志 → `TaskStatus.FAILED` + `protocol_error: canonical attempt is missing a Task terminal`（`worker_results.py:526-529`）。V2 把审计类事件（`control.*`、`agent_settled`）纳入同一条 fail-closed 路径，而契约反复声明这些类型「只用于审计/日志和投影展示」「不影响 Canonical Event 收据和 Task 生命周期」（`open-harness-v2-schemas.md:180`、`live-steering-event-stream-projection.md` §9.1），即审计事件的消息体错误不应决定 Task 终态。
- **影响**：单条「审计事件字段不全 / JSON 非法 / `unknown run.*` 之外的解析异常」会让一个实际成功（或已明确失败）的 Task 丢失真实终态、错误信息与后续全部日志与用量投影，且无自愈路径（只能人工改游标）。EVT-02 就是可产出此类记录的具体生产者分支。
- **最小动作**：chunk 循环内对 `V2_AUDIT_EVENT_TYPES` 校验失败降级为 1 条 diagnostic 并继续推进游标（复用已有常量，~4 行），canonical 事件仍 fail-closed；顺手把 `poll_task_artifacts` 吞错日志 debug→warning
- **验证**：未实际验证（需 DB 与游标）。静态核对抛错点与游标推进顺序、回滚点、上层吞错点与终态兜底点。

### EVT-05 `WorkerEventProjector` 类 docstring 与实现不符
- **判定**：FIX_IF_CHEAP —— 见证据
- **位置**：`backend/app/core/worker_event_projector.py:90-100`（提交 `72140882`）
- **证据**：类 docstring 仍写 `"""Validate and project only ``codify.worker.event/v1`` records."""`，而同一个类在 `ingest_event_record`（`:450`）与 `ingest_event_records_from_chunk`（`:772`）都改用 `validate_event_by_schema()`，V2 fixture（`harness_events_v2/*.jsonl`）也确实走 V2 校验路径。
- **影响**：仅文档误导；审阅者/后续维护者可能据此误判 V2 事件未接入投影。
- **最小动作**：1 行 docstring
- **验证**：静态核对，无需运行。

### EVT-INFO-01 `[V1 遗留]` JSONL 解析用 `str.splitlines()`，Unicode 行分隔符会切碎单条记录
- **判定**：FIX_IF_CHEAP —— 改成只按 `\n` 切比现在更简单
- **位置**：`backend/app/core/worker_event_projector.py:770-789`（消费者）；根因在 `backend/app/core/task_event_archive.py:34-38`
- **证据**：worker 侧 `events.py:365` 以 `json.dumps(..., ensure_ascii=False)` 写事件，`json.dumps` **不会**转义 U+2028/U+2029/U+0085；消费者用 `str.splitlines(keepends=True)` 切分，而 `splitlines` 会在这三个字符处断行。本次用逐字复制的 `iter_complete_jsonl_records` 复现（无 DB）：

  ```
  0x2028 nrecs=2 first='b"}}' byte_match=False
  0x2029 nrecs=2 first='b"}}' byte_match=False
  0x85  nrecs=2 first='b"}}' byte_match=False
  ```

  即记录头部被丢弃、`recs[0]` 是残片 → `decode_event_line` 抛 `JSONDecodeError`（或触发 `:788-789` 的 `event stream byte accounting mismatch`）。worker 侧自己的 `events.py:94` 同样用 `splitlines()` 重读事件流，存在同类风险。
- **影响**：任一事件字符串值含 U+2028/U+2029/U+0085（例如从网页复制的模型输出/工具输出）即可使该 Task 的事件流卡死（后果同 EVT-03）。
- **最小动作**：`iter_complete_jsonl_records` 用 `buffer.split("\n")` + remainder（worker 侧 `events.py` 同改）
- **验证**：已用独立脚本复现切分行为（命令见 §0）；未在真实 Task 上验证。

### EVT-06 OpenCode 不产出 `model.resolved`，V2 fixture 却断言了它
- **判定**：DEFER —— 缺失只影响展示（`system_statistics_queries.py:94-98`）
- **位置**：`deploy/worker-entrypoint/harness/adapters/opencode_events.py`（V2 新增文件，全文无 `model.resolved` 发出点）与 `backend/tests/fixtures/harness_events_v2/opencode/success.v2.jsonl:2`（提交 `72140882`）；消费者 `backend/app/core/worker_results.py:374-377`、投影 `backend/app/core/worker_event_projector.py:469-480`
- **证据**：全仓库检索 `model.resolved` 的发出方只有 `deploy/worker-entrypoint/harness/adapters/{pi_events.py:216-220, claude_events.py:251-255, codex_events.py:270-274}`（以及 `events.py` 的类型表/预览分支），`opencode_events.py` **没有任何** `model.resolved` 发出点（仅有状态键 `"model_resolved": False`，`:146`）。而两个 OpenCode V2 fixture（`success.v2.jsonl:2`、`abort.v2.jsonl:2`）都含 `model.resolved`。后端 `task.model_name` 的**唯一**写入点是 `parse_task_result()` 读取 `log_type="system_init"` 的日志（`worker_results.py:374-377`），而该日志只由 `model.resolved` 投影产生（`worker_event_projector.py:469-480`）。
- **影响**：OpenCode Task 的 `model_name` 恒为空 → `_serialize_task`（`task_helpers.py:86`）、`task_runtime_summary_routes.py:84,108` 的 `actual_model` 缺失（Pi/Claude/Codex 正常）；同时 `harness_events_v2/opencode/*` fixture 认证了一个 adapter 从不产出的事件形状，V2 fixture 套件对该 Harness 提供的是**假一致性**（现有 `test_harness_events_v2.py` 只做 schema/replay 校验，不校验 adapter parity）。
- **最小动作**：删掉或标注 `opencode/*.v2.jsonl` 里的 `model.resolved`；真拿 OpenCode 做用量统计时再补发事件
- **验证**：未在真实 OpenCode Task 上验证。静态核对：三处发出方 + `opencode_events.py` 全文检索无命中 + fixture 含该事件 + `task.model_name` 唯一写入点。

### EVT-INFO-02 `[V1 遗留]` tool 输入存在「同一字段两条清洗强度」的写法
- **判定**：DEFER —— 可信内网 + 无恶意租户
- **位置**：`backend/app/core/worker_event_projector.py:280-296`
- **证据**：`input_payload_id` 指向的正文经过 `self._sanitize_sensitive_data(...)`，但同一 `log_metadata` 的 `"input": payload.get("input") or {}` 直接落库（该行自基线未变，V2 只新增了相邻的 `started_at`）。`task_log_stream` 会把 `log_metadata` 原样推给前端。
- **影响**：取决于 worker 侧 `sanitize()` 与后端 `sanitize_sensitive_data()` 的模式差异；worker 侧 `pi_events._tool_input` 已做嵌套清洗与命令级脱敏，因此本次未观察到可复现的泄露路径，仅记为不一致。
- **最小动作**：下次改该处时让 `log_metadata.input` 复用同一份清洗结果
- **验证**：未运行验证（需要真实含密钥的 tool 调用）。

### EVT-INFO-04 归档读取在事件循环内同步解压整个 tar.gz
- **判定**：DEFER —— 无 SLA、停机可接受
- **位置**：`backend/app/core/worker_results.py:275-303`（`_read_archived_harness_result`，本 diff 新增）与 `backend/app/core/task_failure_details.py:24-56`
- **证据**：两处都在 async 上下文中直接 `tarfile.open(..., "r:gz")` + `getmembers()`（gzip 需读完整流才能枚举成员），没有 `asyncio.to_thread`。归档上限为 `WORKER_RUNTIME_ARCHIVE_MAX_BYTES`（640 MiB，见 `worker_results.py:110-118` 的校验）。
- **影响**：每个 Task 终态解析会同步阻塞事件循环；大归档（含 console.log 与 raw events）下可能造成秒级停顿与其它请求抖动。未量化。
- **最小动作**：顺手改成 `asyncio.to_thread`（1 行），不排期
- **验证**：未运行验证（无大归档样本）。

### EVT-01 投影路径写入 `task_harness_commands.status`，违反冻结的单写者契约
- **判定**：ACCEPT/CLOSE —— 删掉会重开永久 queued 窗口（见 `harness_attempts.py:272-273`）
- **位置**：`backend/app/core/worker_event_projector.py:459-466`（提交 `0a012fd2`）
- **证据**：projector 在 ingest 到 Task terminal 时直接调用 `close_control_gate()`：

```python
if event_type == "agent_settled":
    await begin_control_drain(db, attempt=ingest.attempt)
elif event_type in {"run.completed", "run.failed"}:
    await close_control_gate(
        db,
        attempt=ingest.attempt,
        reason="harness reached terminal event",
    )
```

  而 `task_command_gate.close_control_gate()`（`backend/app/core/task_command_gate.py:98-160`）把 `queued` 命令逐条 `write_command_rejection()`（`task_harness_commands.py:348-377`，写 `status/rejected_at/rejection_code/rejection_message`）并把 `dispatching` 命令写成 `write_command_outcome_unknown()`，即**改 command 行状态**。冻结契约明确禁止：
  - `implementation-plan §4.3:257`：「Projector 只做审计/日志展示，**绝不写** `task_harness_commands.status`。」
  - `open-harness-v2.md:561,569`：「pump 是 command 行的唯一状态迁移 writer」「projector 不参与这些状态迁移」。
  - `open-harness-v2-schemas.md:178,180`：「command pump 是唯一状态 writer」「Canonical control event、projector、SSE 日志不参与 command 行状态写入」。
- **影响**：控制面状态机失去单一 writer：`run.completed/run.failed` 被 ingest（含 `backfill_event_jsonl_from_archive` 归档回填路径）时，命令行会在 pump 的 dispatch lease 之外被终态化。正常时序下 pump 已在 Harness terminal 前排空队列，故实际多数情况是无操作；但一旦存在遗留 `queued`/`dispatching` 行（pump 进程中断、恢复窗口），状态由 ingest 路径决定而非 pump，与该契约想排除的「事件回放反向改控制面」风险同类。另外该调用与 `worker_task_lifecycle.py:1284` 的 `close_task_control_gates()`、`scheduler.py:2144/2582/2700/2833` 的恢复路径重复。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：未实际验证（需 DB/pump 场景）。静态核对三处契约文本与两处调用点；修复后可用「存在 queued 命令 + 直接 ingest `run.failed`」的单测断言 command 行未被 ingest 路径改写。

### EVT-04 result v2 的 `raw_archive` 定位字段端到端缺失，且 `validate_result_v2` 不校验
- **判定**：ACCEPT/CLOSE —— 3 用户部署下补产出与校验属凭空造需求
- **位置**：`backend/app/core/harness_protocol.py:571-615`（提交 `25c5b0d8`）
- **证据**：`open-harness-v2-schemas.md:242,249`（§5 冻结要点）要求 result v2「显式携带 Session、usage、model、outcome、failure category 与 **raw archive locator**」，示例中为 `"raw_archive": {"stream": "harness-events/pi/…", "attempt_id": "…"}`；`implementation-plan §4.3` 同样把该项列为必须完成项。但：
  - `validate_result_v2()` 的 `required` 集合只含 `schema/status/success/result/harness/session_id/model/usage/failure/capability_warnings`，不含也不校验 `raw_archive`；
  - 全仓库检索 `raw_archive`（含 `deploy/worker-entrypoint/harness/adapters/result_builder.py` 与四个 adapter 的 `_write_result`）只有文档与测试名出现，**没有任何生产者写入、没有任何消费者读取**。
- **影响**：契约/实现不一致：`_v2_result_validation_error()`（`worker_results.py:309-320`）自称覆盖「V2 形状结果从未被校验」的缺口，但对一个按 spec 必须存在的字段完全不设防，缺失或格式错误的 result v2 仍被接受；同时契约承诺的原始事件回放定位能力实际不可用。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：未实际验证（未运行四个 harness 的真实容器）。静态核对 `required` 集合与全仓库 `raw_archive` 检索结果；四个 adapter 的 v2 result 目前由 `tests/unit/test_{claude,codex,pi,opencode}_harness_adapter.py` 的 `validate_result_v2` 断言覆盖（本次未单独运行这些文件）。

### EVT-INFO-03 `[V1 遗留]` `assert_attempt_complete()`（文档称权威完整性校验）在生产路径无调用方
- **判定**：ACCEPT/CLOSE
- **位置**：`backend/app/core/harness_attempts.py:346-358`
- **证据**：全仓库检索只有 `tests/unit/test_harness_attempts.py:181,194` 调用；生产仅有增量校验（`_validate_incremental_event_order`）与 `parse_task_result` 的「缺终态」兜底。该函数与 `_load_replay` 在基线 `7b253fbf` 已存在（V2 未新增）。
- **影响**：缺少一次「attempt 级整体一致性」断言；实际缺 terminal 的场景仍会被 `parse_task_result` 判 FAILED，故影响有限。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态检索调用方。

## 3. 逐项核查记录

| # | 不变量 / 契约 | 结论 | 依据 |
|---|---|---|---|
| 1 | V2 常量不覆盖 V1；V1 历史读取器仍可读 V1 | 通过 | `harness_protocol.py:20-30`（V1 常量原样保留，V2 另增）；`validate_event()` 保留（`:362-366`），`validate_event_by_schema()` 按事件 `schema` 分发（`:376-383`）；`runner`/适配器测试仍用 `validate_event()` 校验 V1 输出（`tests/unit/test_claude_harness_adapter.py:394,432`）；V1 fixture 回归 `tests/unit/test_harness_event_fixtures.py:98-145` 通过（本次 83 passed 含该目录之外的 4 个文件） |
| 2 | projector 按 attempt 的 `event_schema` 选择解析器 | 通过（更强） | projector 用 `validate_event_by_schema()`（`worker_event_projector.py:450,772`），`ingest_canonical_event()` 额外强制 `attempt.event_schema == event["schema"]`（`harness_attempts.py:287-289`），因此不会出现 V1/V2 混用 |
| 3 | `(attempt_id, seq)` 幂等、从 1 连续；重复 ingest 不产生重复投影 | 通过 | 收据主键 `(attempt_id, seq)` 且同 seq 同 digest 返回 `duplicate=True`（`harness_attempts.py:295-305`）；projector 在 `duplicate` 时提前返回、不再写日志/不再累计（`worker_event_projector.py:452-455`）；`expected_seq = attempt.last_seq + 1`（`harness_attempts.py:170-176`）；`tests/unit/test_harness_attempts.py` 10 passed |
| 4 | `event_id` 唯一；attempt 内 harness identity 不可变 | 通过 | `event_id` 集合校验（`harness_attempts.py:306-316`）+ DB 唯一约束（`models.py:692`）；key/adapter/cli 冻结（`harness_attempts.py:275-286`），`control_transport`/`model_protocols` 与首条收据比对（`:196-213`） |
| 5 | 缺 init / 缺 Harness terminal / 缺 Task terminal / 双 terminal / 序号缺口 = protocol_error | 通过（失败粒度见 EVT-03） | 全量 replay：`harness_protocol.py:438-507`（`ingest`）+ `:509-521`（`finish`）（`missing_init`/`missing_harness_terminal`/`missing_task_terminal`/`duplicate_event`/`sequence_gap`/`after_terminal`）；增量等价实现 `harness_attempts.py:160-260`；`tests/unit/test_harness_protocol.py`（含 `terminal_must_be_last_event`）通过 |
| 6 | `worker.finalization` 之后只允许唯一最后的 `run.completed|run.failed` | 通过 | replay：`harness_protocol.py:474-478`（finalization 之后只允许 Task terminal）与 `:493-504`（finalization 只允许一次 + Task terminal 必须晚于 finalization）；增量：`harness_attempts.py:186-193,241-260`；worker 侧同规则 `deploy/worker-entrypoint/harness/events.py:308-319`；`agent_settled` 自身不是 terminal（`harness_protocol.py:31-35`、`worker_event_projector.py:727-739` 仅记审计） |
| 7 | `harness.*`/`delivery.*` 不决定 Task 终态 | 通过 | 仅 `run.completed/run.failed` 进入 `TASK_TERMINAL_TYPES`（`harness_protocol.py:98`）；`parse_task_result` 的终态只读 `run_result` 的 `type`（`worker_results.py:355-359`），缺终态分支 `:526-529`；`delivery.*` 仅被顺序校验（`harness_attempts.py:234-240`），projector 无投影分支（V1 同） |
| 8 | 三个 control event 的 schema、必填字段 | 通过（生产者一处不满足，见 EVT-02） | `_validate_control_event()`：delivered 要求 `command_id/payload_digest/sequence_no/delivered_at`；rejected 要求前四者 + `rejection_code ∈ REJECTION_CODES` + `rejection_message: str`；queue.updated 只要求 `queue` 数组（`harness_protocol.py:340-359`）；`REJECTION_CODES` 8 项与 `open-harness-v2-schemas.md:187-196` 一致 |
| 9 | projecto 不按文本反推 command_id；queue update 不要求 ID | 通过 | `control.queue.updated` 分支只做 sanitize 与记录（`worker_event_projector.py:703-728`），不解析文本；delivered/rejected 的展示字段用 `(task_id, attempt_id, sequence_no)` + `payload_digest` 精确匹配命令行，注释显式说明「never a text guess」（:379-436）；fixture `pi/success.v2.jsonl` 的 queue 项只有 `{id,text}` |
| 10 | projector 不写 command 行 | **不通过** | 见 EVT-01 |
| 11 | `delivered` 仅表示原生 ACK，不等于 settled | 通过 | 语义注释 `harness_protocol.py:31-35`、`live-steering…md` §3.3；projector 对 delivered 只记 `control_event` 日志（`worker_event_projector.py:703-728`），gate 迁移只由 `agent_settled` 触发（`:459-460`） |
| 12 | `worker.finalization → worker_results` 字段一一对应 | 通过 | 生产者 `deploy/worker-entrypoint/harness/common.sh:357-369`（含 `exit_code/commit_sha/commit_message/diff/git_delivery`）；消费者读同名键（`worker_results.py:383-420,517-519`）；`usage.final` 生产者统一包在 `payload.usage`（`events.py:85-97`、四 adapter 均 `{"usage": …}`），projector 写 `log_type=usage_final`（`worker_event_projector.py:665-674`），消费端读 `.get("usage")`（`worker_results.py:361-372`）；`model.resolved` 的 `model/session_id` 由 pi/claude/codex 三 adapter 发出（`pi_events.py:216-220`、`claude_events.py:251-255`、`codex_events.py:270-274`），**OpenCode adapter 不发出该事件**（见 EVT-06） |
| 13 | 未知 event type 处理（fail closed vs forward-compatible） | 通过 | 未知非 `run.*` 降级为 `diagnostic` 且带 `raw_ref`，未知 `run.*` 抛错（`harness_protocol.py:191-217`）；与 `worker-canonical-event-v1.md`「未知对象字段忽略」一致（`_validate_event_core` 保留未知名段） |
| 14 | 清洗覆盖：thinking / tool 输入输出 / 嵌套字段 | 基本通过（含 EVT-INFO-02） | `_payload_log`/`_finalize_thinking_row` 对 thinking 文本清洗（`worker_event_projector.py:109-146,211-256`）；tool 输入输出正文清洗（`:263-290,342-347`）；control.queue 逐条清洗 `text`（`:706-716`）；`harness.*`/`run.*` 的 `log_metadata` 不再清洗，依赖 worker 侧 `pi_events._failure_message`（`sanitize`+`clean_message`）等生产者先清洗——`claude_events.py:370-373` 的 `failure.message` 直接取 `record.get("result")`，未见同等清洗（属 T06/T13 范围，未计入问题） |
| 15 | 幂等 receipt 与时序：乱序/重复 ingest | 通过 | 同 seq 不同 `event_id`/digest → `duplicate_conflict`（`harness_attempts.py:296-305`）；乱序 → `expected_seq` 报错；`control.*` 重复回放不改 command 行（投影分支无写操作） |
| 16 | 日志流多 attempt/断线重连/游标边界 | 通过（内存有界） | `task_log_stream.py:42-104`（`cursor=since_id` 增量、`pending_tool_calls`/`pending_thinking_rows` 只存 id、成对 discard）+ `:150-160`（thinking 按 status 收敛，空块也收敛）；前端对「任务已终态但 thinking 仍 in_progress」有兜底显示（`frontend/src/components/task-process/TaskProcessTextRow.spec.ts:204-230`） |

## 4. 局限与未验证项

- **未运行**：全量 `pytest`、`docker-compose`/真实四 Harness 容器、前端 `npm run build`、任何需要 Postgres/网络的集成路径。所有涉及 DB 事务、游标推进、pump/gate 竞态的结论均为静态推理。
- **未实际复现**：EVT-01 的运行时影响（需要 queued/dispatching 行 + ingest 并发场景）、EVT-03 的卡死链路（需要 DB 与 Tailer）、EVT-04 的真实 result v2 容器产出。
- **仅 EVT-02、EVT-INFO-01 有最小复现**（无 DB 的纯函数/校验层），命令与输出见 §0 与对应条目。
- **未覆盖的相邻实现**：OpenCode adapter 除 `model.resolved` 缺失（EVT-06）外的逐行翻译逻辑；`claude_events.py` 失败消息的清洗强度、`worker-failure` 分类到 `FailureKind` 的映射（`_failure_kind`）只在验证器层面核对，未逐 Harness 复核分类正确性；`harness.catalog`/registry 侧对 V1 manifest 的兼容（`validate_runtime_bundle_manifest` 仅接受 V1 常量）目前在生产无调用方，未计入问题。
- **书面接受项的复核口径**：EVT-01、EVT-04、EVT-INFO-03 已按当前部署 profile 接受关闭，本次不再跟进；其中 EVT-01 若日后命令平面要回归「projector 不写 control gate」的单写者契约，需先确认 `worker_task_lifecycle`/scheduler 恢复路径能在 pump 中断时收敛遗留 `queued` 行（`live-steering…md` §9.4 只授权「本地拒绝投影」，未授权 projector 作为调用点）。EVT-03 的修复粒度仍需与契约负责人确认「审计类事件的 schema 错误是否允许降级」，这是三项 FIX_IF_CHEAP 中唯一需要跨专题对齐的一项。
