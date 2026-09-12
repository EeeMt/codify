# 05 OpenCode 事件/SSE 映射与 settled 判定 —— Code Review

> 审查对象：`dev @ cbad9e56`（未提交改动不参与审查） · finding 前缀 `OCE-` · 2026-09-12

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `git diff 8081c946^..cbad9e56` |
| 主文件 | `deploy/worker-entrypoint/harness/adapters/opencode_events.py`（+1716，新增，本次最大新增文件，逐块通读） |
| 边界文件（只读核查；Server/Bridge 生命周期结论属 04 专题） | `adapters/opencode_bridge.py`（+1293：`parse_sse`/`event_stream`/`_recover_status`）、`adapters/opencode.sh`（+452）、`runners/opencode-run.sh`（+240）、`harness/events.py`（canonical writer 契约）、`backend/app/core/worker_event_projector.py`、`backend/app/core/harness_protocol.py`、`backend/app/core/worker_results.py` |
| 测试 | `backend/tests/unit/test_opencode_harness_adapter.py`（+3373） |
| probe 证据 | `docs/harness-probes/v2/opencode/{README.md,events.wire.sse,events.observed.jsonl}`（+45/+15/+18） |
| 契约依据 | `docs/architecture/open-harness-v2-phase3-opencode-design.md` §3/§4/§6/§9、`docs/architecture/open-harness-v2-schemas.md` §3.2、`docs/architecture/worker-canonical-event-v1.md` |
| 审查方法 | 静态通读 + 契约对照 + 在仓库外用官方 translator/writer 原样驱动复现 3 条 settled/去重路径（`/tmp/ocreview/*.py`，环境变量与测试 `_environment` 一致）+ 运行 `backend/.venv/bin/python -m pytest tests/unit/test_opencode_harness_adapter.py -q`（**96 passed，38.71s**） |
| 未覆盖 | 无真实 OpenCode 1.18.19 Server 与真实模型端点，无法实测 abort / `session.status(retry)` / `session.next.*` durable 家族 / TextPart 全量快照语义；control 平面、Server 生命周期、delivery、任务终态属其他专题 |

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 0 |
| FIX_IF_CHEAP | 4 |
| DEFER | 5 |
| ACCEPT/CLOSE | 1 |

translator 的输入侧纪律整体好：未知/新事件一律落 `diagnostic`（不静默丢）、类型不符不裸抛、reasoning 正文从不进 canonical、快照替换式幂等、tool/reasoning 生命周期有 once 标志、`seq` 交 writer 在文件锁内派生，96 条单测覆盖过这些分支。没有必须立刻修的项（FIX_NOW 0），4 条 FIX_IF_CHEAP 均已复现（OCE-01 settled 规则 4 未落地、OCE-02 后缀去重吞字符、OCE-03 空文本回合判 protocol_error、OCE-04 分片解码产生 U+FFFD），都不在现有单测覆盖面内。其余 5 条 DEFER 属有兜底或需真实样本才能定案、1 条 ACCEPT/CLOSE 防的是未触发路径，按本画像书面接受。

**本专题触发条件**：

- `session.next.*` durable 家族真实出现在流量中，再加内存 cap → OCE-INFO-02

## 2. 问题清单

### OCE-01 abort 形状（assistant `error:true`）被当作成功收敛

- **判定**：FIX_IF_CHEAP
- **位置**：`deploy/worker-entrypoint/harness/adapters/opencode_events.py:1346-1352`（收敛点 `:1533-1586`，提交 `cbad9e56`）
- **证据**：
  - probe 事实（本专题第一证据源）：`docs/harness-probes/v2/opencode/README.md` Abort 行——"`POST /session/{id}/abort` 返回 200 + `true`；随后 assistant 消息 `error:true` 且带 completed 时间戳（操作被中断、**settled 为错误态**）"；同文件事件清单明确"`session.error`**未复现**（列待测）"；`events.observed.jsonl` 尾注同义。即 abort 的**实测形状是 assistant 消息 `error:true`，不是 `session.error`**。
  - 代码：`:1346` `if info.get("error") or properties.get("error"):` 分支只调用 `_interrupt_open_reasoning("message_error", ...)`（`:1352`），**不置 `_STATE["terminal_failure"]`、不置 `aborted`**；成功门在 `:1546` 只检查 `_STATE["terminal_failure"] is None and not _STATE["aborted"]`，随后 `:1577-1585` 发 `message.completed`/`agent_settled` 并 `_finalize_terminal()`（成功分支 `:1191-1205`）。
  - 复现（仓库外，未改仓库）：输入 `session.created` → `session.status(busy)` → `message.updated{info:{id:"m-err",role:"assistant",error:true}}` → `message.part.updated{part:{type:"text",text:"partial output before abort",messageID:"m-err"}}` → `session.idle`，输出 `harness.completed` 且 `harness-result.json` = `{"status":"completed","success":true,"result":"partial output before abort"}`；同一序列去掉文本 part 则退化为 `protocol_error`（见 `OCE-03`）——两种情况都没有 `cancelled`。
  - 契约：design §4 冻结规则 4"Session 状态非 error"、§9 硬切验收项 5"Abort 实机：thinking/tool/idle 三阶段 abort + **后续消息错误态收敛**"。
- **影响**：凡"assistant 消息带原生 error 事实、但未伴随 `session.error`"的回合（probe 实测的 abort；服务端/上游中断同形）都会被投影为 `harness.completed` 且 `result.success=true`，携带被中断的部分文本。用户主动取消时任务级终态仍由 `common.sh:371-373`（`exit_code != 0` 分支）纠正为 `run.failed(cancelled)`，但同一次 attempt 的 canonical 流里同时存在"成功 harness terminal + 成功 result"与"取消任务终态"，审计/回放自相矛盾；**非取消来源的中断（无 SIGTERM）会直接以 success 走完 delivery**。现状单测 `test_opencode_errored_assistant_message_interrupts_its_reasoning`（`test_opencode_harness_adapter.py:1235-1301`）恰好固定了"errored 消息之后仍可成功"的行为，未覆盖"errored 消息就是最后一条 assistant 消息"的形状。
- **最小动作**：记 `errored_message_id`，仅当它仍是最后一条 assistant 消息时收敛失败（~6 行）。【建议过重】 不要按 review 原方案无条件置 `terminal_failure`——会打断“错误后重试成功”的回合
- **验证**：已复现（仓库外驱动官方 translator + 官方 `events.py` writer）。修复后同一 records 应产出 `harness.failed`（`failure.kind=cancelled`）+ `success:false`；建议补 fixture `errored message → idle`。本次未运行修改版测试。

### OCE-02 delta 去重按后缀比较，静默吞掉真实重复内容

- **判定**：FIX_IF_CHEAP
- **位置**：`opencode_events.py:1521`（legacy `message.part.delta`）、`:777`（durable `session.next.text.delta`）
- **证据**：`:1521-1524` `current = state["text"]; if not current.endswith(delta): state["text"] += delta`；`:777` `if delta and not state["text"].endswith(delta):`。注释（`:1474-1476`）说明该守卫本意只是"快照已包含该 delta 时不重复累加"。复现：`message.updated(m1, assistant)` → delta `"line1\n"` → `"\n"` → `"abc"` → `"c"` → `session.idle`，得到 `result = "line1\nabc"`，**期望 `"line1\n\nabcc"`**（第二个 `"\n"` 与末尾 `"c"` 被当"已包含"丢弃）。
- **影响**：assistant 最终文本静默丢字符，且缺口位置随分块/相邻字符变化，肉眼与测试都难发现；该文本同时进入 `message.completed`、`harness-result.json` 的 `result`、以及交付摘要的 `assistant_text` 回退来源。同时 `message.delta`（`:1525`）仍照发，canonical delta 流与最终文本不一致。
- **最小动作**：用快照水位（`snapshot_len`+flag）替代 `endswith` 去重，两处 delta 路径（~6 行）
- **验证**：已复现（仓库外）。

### OCE-03 `session.idle` + 空文本回合被判 `protocol_error`

- **判定**：FIX_IF_CHEAP
- **位置**：`opencode_events.py:1559-1570`
- **证据**：`:1559-1570` `final_text = "".join(_STATE["text_parts"])`，条件 `not isinstance(final_message, dict) or final_message.get("role") != "assistant" or not final_text` 成立即置 `protocol_error`。复现：`session.status(busy)` → tool part（`status:"completed"`）→ `message.updated{info:{id:"m-c",role:"assistant"}}` → `session.idle` ⇒ `harness.failed`，`failure.message="...session.idle without a final assistant message"`，result `success:false`、`result:""`。冻结规则 design §4 规则 3 只要求"最终 assistant message 已到达（message 流收尾，无未消费 part）"，并未要求文本非空；`:1565-1568` 的措辞还把"没有最终消息"和"有消息但无文本"混为一谈。
- **影响**：会话正常 idle、工具全部完成、最后一条 assistant 消息不含 text part 的回合（纯工具回合、命令式 prompt）被判协议错误 → 任务失败，已完成但未交付的仓库改动随 attempt 一起丢弃。触发依赖"最后一条 assistant 消息无 text part"的实际频率，本环境无真实 Server 可证，故判为 FIX_IF_CHEAP 而非 FIX_NOW。
- **最小动作**：文本为空仍成功收敛，只保留“必须是 assistant”校验（~2 行）
- **验证**：已复现（构造形状）；真实频率未验证。

### OCE-04 SSE 分片逐块解码，多字节字符被替换成 U+FFFD

- **判定**：FIX_IF_CHEAP
- **位置**：`deploy/worker-entrypoint/harness/adapters/opencode_bridge.py:639`（`event_stream`；SSE 分帧健壮性属本专题，Server 生命周期结论归 04 专题）
- **证据**：`:636-639` `chunk = resp.read1(8192)` → `buffer += chunk.decode("utf-8", errors="replace")`，每个 chunk 独立解码、无跨块解码状态。复现（仓库外 monkeypatch `urlopen` 分块）：一个真实形状的 `message.part.delta`（`delta:"你好世界"`）的 wire 字节在"你"中间截断，得到记录 `delta="���好世界"`；因 U+FFFD 是合法字符，JSON 仍能解析，**既不报错也不落 diagnostic**，损坏同时写入 raw archive（`opencode.jsonl`）与 canonical payload。测试 `test_opencode_harness_adapter.py:1888-1911` 只覆盖 ASCII 分帧与 CRLF，无多字节跨块用例。
- **影响**：中文/emoji 等非 ASCII 输出在 chunk 边界被静默污染；若该 part 之后没有新的全量快照覆盖（`:1477`），损坏会进入 `message.completed` 与 result。非 ASCII 输出越多概率越高。raw archive 是事后审计的"事实源"，被污染后无法区分。
- **最小动作**：`codecs.getincrementaldecoder("utf-8")` + EOF flush（~3 行）
- **验证**：已复现解码行为；真实长中文输出的命中频率未验证。

### OCE-05 `model` 恒为 null、从不发 `model.resolved`

- **判定**：DEFER
- **位置**：`opencode_events.py:145-147`（状态声明）、`:1132-1133`（写 result）
- **证据**：全文件 grep 中 `model_resolved`/`model_id` 只有初始化与 `_write_result` 的读取，**无任何赋值点**，全文件也无 `model.resolved` 事件；对照 `pi_events.py:210-227`、`codex_events.py:266-271` 均发该事件。消费链：`worker_event_projector.py:468-477` 由 `model.resolved` 生成 `log_type="system_init"`，`worker_results.py:374-377` 是 `task.model_name` 的唯一写入点；前端 `TaskRunMetrics.vue:16` 显示 `task.model_name || '-'`，`task_runtime_summary_routes.py:84/108` 暴露 `actual_model`。离线 fixture 同样脱节：`backend/tests/fixtures/harness_events_v2/opencode/{success,abort}.v2.jsonl` 第 2 条即 `model.resolved`（`payload.model="deepseek-v4-flash"`），但 translator 没有任何产出该事件的路径，回放测试因此给出虚假对等（同目录 `crash`/`invalid`/`session_missing` 无该事件）。`harness_protocol.validate_result_v2:580` 只校验 `model` 键存在，null 被接受，因此不是崩溃而是静默缺失（已由 `OCE-01` 复现输出确认 `"model": null`）。
- **影响**：OpenCode 任务的 `result.model` 与 `task.model_name` 永远为空 → 任务"模型"指标显示 `-`、runtime summary 的 `actual_model` 缺失、按模型统计失真；`model.resolved` 这一 V1 继承事件在 opencode 上永不出现（词汇表 `open-harness-v2-schemas.md:94` 仍列为继承类型）。
- **最小动作**：首个会话/消息事件时 emit `model.resolved`（~5 行，与 Pi/Codex 对齐）
- **验证**：静态证据充分（grep 全文件 + 消费端链路 + fixture 对照 + 复现结果中 `model: null`）；未在真实任务上核对 UI 表现。与 02 专题 `EVT-06` 记录同一事实（此处为 adapter 侧缺失产出，02 为投影侧依赖）。

### OCE-06 `message.delta` 用 `content`，projector 读 `text`

- **判定**：DEFER
- **位置**：`opencode_events.py:779`、`:1402`、`:1525`
- **证据**：三处 `_emit("message.delta", {"content": delta, "role": "assistant"}, raw_line)`；消费端 `worker_event_projector.py:481` 读 `payload.get("text")`（`claude_events.py:280` 也发 `text`），V1 projector 同样读 `text`（`git show 8081c946^:backend/app/core/worker_event_projector.py:236-241`）→ 全仓库无任何代码读 `payload["content"]`。影响被限制：`message.completed` 自带完整 `text`（`:1579`），projector 的 `_message_parts` 只是其缺失时的回退，而 opencode 的失败路径不发 `message.completed`（因此也不受此条影响）；现有单测 `test_opencode_harness_adapter.py:603` 反而把 `content` 固定下来。Pi 沿用同一 V1 形状，故非 V2 新引入的契约破坏。
- **影响**：增量 delta 不进入投影缓冲；若将来某路径的 `message.completed` 不带 `text`（或需要按 delta 增量渲染），回退会得到空文本。
- **最小动作**：1 行改发 `{"text": delta}`（顺手，与 PI-06 同类）
- **验证**：静态（grep + 单测断言），未跑端到端投影。

### OCE-INFO-01 `session.status(retry)` 对通用 rate-limit 标记即刻收敛终态

- **判定**：DEFER
- **位置**：`opencode_events.py:1222-1254`
- **证据**：`:1246-1248` `if _is_rate_limit_reason(reason) or any(marker in lowered for marker in _RATE_LIMIT_MARKERS)` 命中即 `_STATE["terminal_failure"]={"kind":"rate_limited"}` + `_finalize_terminal()`；不参考同一 payload 里的 `attempt`/`maxAttempts`/`next`/`delayMs`。`_RATE_LIMIT_MARKERS`（`:57-68`）含 `"429"`、`"rate limit"`、`"too many requests"`，即"可自愈的瞬时 429"也会即刻失败；而 durable 家族 `session.next.retried`（`:979-1000`）在 `isRetryable != False` 时**清空** `terminal_failure` 继续跑——两条 retry 语义相反。probe 从未观测 retry 状态（`docs/harness-probes/v2/opencode/README.md` 事件清单无样本），现有单测只覆盖 `account_rate_limit`/`quota_exceeded`/`usage-limit-exceeded`（`test_opencode_harness_adapter.py:1427-1467`）。
- **影响（待确认）**：若线上把可恢复的瞬时 429 报为 `session.status(retry)` 且文本/reason 含上述标记，任务会在第一次重试即失败（过早 settled），与 durable 分支行为不一致。
- **最小动作**：要求 `attempt >= maxAttempts`（或 `next` 缺失）才收敛（~3 行）或等样本
- **验证**：未验证（无样本），纯静态对照；未运行任何真实重试场景。

### OCE-INFO-03 `busy` / `idle_seen` 写了不用

- **判定**：DEFER
- **位置**：`opencode_events.py:155-156`、`:1217-1221`、`:1535-1536`
- **证据**：两个字段只在 `session.status`/`session.idle` 分支赋值，全文件无读取点（grep）；design §4 的"多信号组合"实际只用了 idle + 最后一条消息 + 无 error/abort。另：单独出现 `session.status(idle)` 不会收敛，靠 bridge `_recover_status`（`opencode_bridge.py:806-880`）合成 `session.idle` 兜底。
- **影响**：无功能影响（死状态）；但会让审阅者高估"组合判定"的实现程度。
- **最小动作**：删 `busy`/`idle_seen`（2 行），顺手做
- **验证**：静态 grep。

### OCE-INFO-04 part 无 `id` 时多个 text 快照互相覆盖

- **判定**：DEFER
- **位置**：`opencode_events.py:1367-1376`（`_part_id`）、`:1473-1478`
- **证据**：`_part_id` 在既无 `properties.partID` 也无 `part.id` 时，若该 message 已有**恰好一个** part 就直接复用（`:1375-1376`）→ 第二条 text part 的快照 `state["text"] = text` 覆盖第一条，最终 `message.completed` 只留最后一段。probe 样本 `events.observed.jsonl` 的 text part 只有 `type/text/messageID/sessionID`（无 `id`），但该文件经脱敏（"Fields ... are redacted to `<ID>`"），不能据此断定线上是否带 `id`。
- **影响（待确认）**：一条 assistant 消息含 ≥2 个无 id 的 text part 时，前面 part 的文本从 result 中消失。
- **最小动作**：抓一次包；若确不带 id 改用 `__default__` 不复用
- **验证**：未验证（fixture 无 id 且已脱敏）。

### OCE-INFO-02 durable tool input 增量无界累积

- **判定**：ACCEPT/CLOSE —— 见「何时再管」
- **何时再管**：durable 家族真实出现在流量中再加 cap
- **位置**：`opencode_events.py:866-872`、`:884-886`
- **证据**：`lifecycle["input_text"] = lifecycle.get("input_text", "") + delta` 只增不减，`_sanitize_value`（`:418-434`）只在转 canonical 时截断（4000 字符/64 项/深度 6），`input_text` 本身常驻内存；legacy 路径的单帧快照在 `_sanitize_value` 后即被限制。`session.next.*` 家族在 probe 中**完全未观测**。
- **影响（待确认）**：若上游真以增量推送大文件 `write` 输入，内存随输入总量线性增长，容器内存上限下可能 OOM。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：未验证（无真实 `session.next.*` 样本）。

## 3. 逐项核查记录

| # | 不变量/契约 | 结论 | 依据 |
|---|---|---|---|
| 1 | SSE 单行 `data:` 帧 + 空行分帧（probe 实测形状） | 通过 | probe `events.wire.sse`（4 帧真实抓包）与 `opencode_bridge.py:290-360`（`parse_sse`）一致；`test_opencode_parse_sse_from_captured_11819_wire` 通过 |
| 2 | `data:` 后无空格、CRLF、跨 chunk 分帧、空行 | 通过 | `opencode_bridge.py:311-312`（`line.startswith("data:")` / `line[5:].strip()`）、`opencode_bridge.py:733-740`（`_sse_tail`）；测试 `test_opencode_harness_adapter.py:1888-1911` 覆盖 ASCII 分块与 CRLF |
| 3 | 注释行/心跳帧（`server.heartbeat`、`:keepalive`） | 通过（显式忽略） | `opencode_bridge.py:290-360`（`parse_sse`）只识别 `id/type/properties`；translator `:1627-1628` 丢弃 `server.connected/heartbeat` |
| 4 | 多行 `data:` 聚合、命名 `event:` 字段 | 不适用（未实现） | 1.18.19 实测为单行 data 帧；无法识别的帧最终落 `unknown_raw_event`（`:1663`），不静默丢失 |
| 5 | 流中途截断 | 通过 | bridge `IncompleteRead/URLError → ConnectionError`（`opencode_bridge.py:660-665`）→ `_recover_status` 兜底；translator 在 EOF 且未 settled 时收敛 `protocol_error`（`:1705-1711`） |
| 6 | 重连 / `Last-Event-ID` | 不适用（未实现重连） | `event_stream` 单次订阅、不发 `Last-Event-ID`；断开后用 `GET /session/status` 合成 `session.idle`（`opencode_bridge.py:806-880`），与 probe README 的 settled 说明一致 |
| 7 | 单帧超大 payload 的资源占用 | 有界但低效 | 每 chunk 全量重解析 + `_sse_tail` 全量扫描（`opencode_bridge.py:640-652`），单帧 n 字节的代价约 O(n²/chunk)；未见单帧字节上限（未列入问题清单） |
| 8 | 未知/新增事件类型不静默丢弃 | 通过（fail-open + 证据） | `translate` else → `unknown_raw_event`（`:1663`）；durable 未覆盖子类型 → `opencode_durable_event`（`:1026-1031`）；`_IGNORED_KNOWN_EVENTS`（`:112-141`）为显式有文档的 no-op |
| 9 | 增量 delta 与最终消息合并（重复/丢失） | **不通过** | OCE-02（丢内容）、OCE-03（空文本判失败）；快照→delta 顺序两种排列在 `:1474-1477`/`:1521` 已考虑 |
| 10 | 字段缺失/类型不符不得中断事件流 | 通过（未发现裸抛） | `_error_message:234-266`、`_usage:364-388`、`_sanitize_value:418-434`、`_tool_*:436-540`、`_handle_durable_event:748-1031` 全部 `isinstance` 守卫；`translate:1606` 对 `properties` 非 dict 兜底 |
| 11 | settled 三信号共同判定（design §4） | **部分不通过** | 规则 1（idle）见 `:1533-1541`；规则 3 过严（OCE-03）；规则 4 未落地（OCE-01）；`_STATE["message"]`/`_refresh_text` 聚合逻辑正确（`:1326-1354`、`:1387-1395`） |
| 12 | abort/cancel 与 settled 的区分 | **不通过** | OCE-01；`session.error` → `_failure_kind` → `cancelled` 路径本身正确（`:1312-1324`，测试 `:1469-1490`） |
| 13 | `seq` 单调、单 writer 有序 | 通过 | translator 不分配 seq，由 writer 在 `.event.lock` 内按已有行数派生（`events.py:277-300`）；translator 单进程顺序 emit；取消时晚到事件被 `_canonical_stream_closed`（`:327-361`）丢弃，不会破坏终态不可变 |
| 14 | 幂等/重放去重（重连 replay） | 部分通过 | 快照替换式幂等（`:1477`）、tool 生命周期 once 标志（`:618`、`:1107`）、reasoning 块 once（`:663-700`）；delta 无 event-id 级去重（`record["id"]` 即 `evt_…` 未参与判定），且后缀去重会误伤 → OCE-02 |
| 15 | thinking/reasoning 内容处理与截断 | 通过 | 正文从不进 canonical（`:847-852` 丢弃 reasoning delta；`:1406-1470` 只用 `time.start/end` 判生命周期）；raw archive 经 `redact_hidden_reasoning`（`main:1688`）脱敏 |
| 16 | 超长工具输出内存 | legacy 通过 / durable 存疑 | `_tool_output:486-499` 截 2000 字符、`_sanitize_value` 截 4000 字符/64 项；durable `input_text` 无界 → OCE-INFO-02 |
| 17 | 与 probe 原始流逐条一致 | **部分不通过** | 帧形状/事件类型一致（核查 1-3）；abort 形状矛盾 = OCE-01；`events.observed.jsonl` 缺 assistant `message.updated`，但线上任务（`docs/superpowers/evidence/2026-09-04-open-harness-v2-r4.3-r4.4-live-host.md` Task 390：opencode 1.18.19、seq 1–216、`run.completed`）证明该信号真实存在——否则 `:1559-1570` 会让每个任务都 `protocol_error` |

## 4. 局限与未验证项

- **无真实运行环境**：没有 OpenCode 1.18.19 Server、没有模型端点，无法实测 abort 三阶段、"瞬时 429 → retry → 恢复"、`session.next.*` durable 家族、`TextPart` 是否带 `id`、text part 是否始终发全量快照。OCE-01 的触发形状依据 probe 文档（assistant `error:true`、`session.error` 未复现），OCE-02/03/04/05 的代码路径已用仓库外驱动复现，但**触发频率**未验证；OCE-INFO-01/04 为未验证疑点。
- **未运行**：全量测试与构建（按审查纪律）。唯一运行的测试为 `cd backend && .venv/bin/python -m pytest tests/unit/test_opencode_harness_adapter.py -q` → 96 passed（38.71s，2026-09-12）。
- **仓库外复现脚本**（`/tmp/ocreview/probe.py`、`utf8_probe.py`）未入库，仅用官方 `opencode_events.py` + `events.py` + 与测试 `_environment` 相同的环境变量；未修改仓库任何文件（本专题只新增本文档）。
- **专题边界**：04（Server/Bridge 生命周期、`_recover_status`、native abort 编排）、02（writer/projector 契约定义、`model.resolved` 的通用要求）、11（取消/超时的任务终态）的判定不在本文件结论内；本文件仅在跨界处引用其行为作为影响范围依据。
