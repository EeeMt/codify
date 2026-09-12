# 06 Claude / Codex V2 迁移与无回归 —— Code Review

> 审查日期：2026-09-12 ｜ 审查对象：`dev @ cbad9e56` ｜ 专题：Claude / Codex V2 迁移（adapter + events + runner）
> finding 前缀：`CX-`（本文件只覆盖 Claude/Codex 两个 Harness 的迁移面；公共 Runner/Kit/投影的归属见其他专题）

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56`（基线 `7b253fbf`，2026-08-20；V1 对照物：`deploy/ci-claude.sh`（改名而来）、`deploy/worker-entrypoint/legacy/codex-run.sh`（被删除）） |
| Claude 文件 | `deploy/worker-entrypoint/harness/adapters/claude.sh`（+66/−17）、`adapters/claude_events.py`（+150/−14）、`runners/claude-run.sh`（由 `deploy/ci-claude.sh` 改名，仅 +19/−7，共 896 行） |
| Codex 文件 | `deploy/worker-entrypoint/harness/adapters/codex.sh`（+83/−18）、`adapters/codex_bridge.py`（+288，新文件）、`adapters/codex_events.py`（+306/−32）、`runners/codex-run.sh`（+82，新文件；`legacy/codex-run.sh` −90 删除） |
| 参照/依赖 | `adapters/result_builder.py`（+56，新文件）、`harness/events.py`、`harness/runner.sh`、`harness/common.sh`、`harness/manifest.json`（+116/−21）、`bootstrap.sh`、`runtime.sh`、`deploy/worker-kit/*`、`backend/app/core/harness_protocol.py`、`backend/app/core/worker_event_projector.py`、`docs/harness-probes/v2/{claude,codex}/*`、`docs/architecture/open-harness-v2.md`、`docs/architecture/worker-harness-contract-v1.md`、`docs/superpowers/plans/2026-09-04-thinking-event-placeholder-plan.md` |
| 审查方法 | 静态阅读（diff 定位 + 完整文件 + 调用方 + 后端消费端）、契约对照（V2 架构 §6.2/§6.4/§8.3、Harness contract v1 操作表、thinking placeholder plan §3/§4）、V1↔V2 等价性测试实跑、单事件成本实测 |
| 已执行验证 | `cd backend && .venv/bin/python -m pytest tests/unit/test_claude_harness_adapter.py tests/unit/test_codex_harness_adapter.py -q` → **93 passed in 31.65s**（含 16 个 Claude + 17 个 Codex 场景的 V1 fixture 等价性参数化用例）；`python3 deploy/worker-entrypoint/harness/events.py message.delta --payload '{"text":"hello world"}'` ×50 → 4.11s（≈82ms/次，macOS M1 Pro） |
| 未覆盖 | 真实 CLI/Provider 端到端运行（无 docker、无冻结版 `claude`/`codex`、无凭据）；Codex App Server 原生 wire 帧（仓库内无捕获样本）；前端对 `reasoning_summary.*`/`unknown_raw_event` 的渲染（T12）；公共 Runner/Kit/投影的内部实现（T07/T08/T09/T11） |

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 0 |
| FIX_IF_CHEAP | 1 |
| DEFER | 5 |
| ACCEPT/CLOSE | 0 |

两个 Harness 的 V2 迁移是「信封与结果换成 v2、保留既有执行能力」的忠实移植：事件与结果字段未丢失，V1 冻结 fixture 的逐事件等价性测试全部通过，未发现破坏唯一终态或错误交付的缺陷。**没有 FIX_NOW**；唯一 FIX_IF_CHEAP 是 **CX-03**（Codex 协议正常帧被记成 3 条假 WARNING，改 1 个分派条件即修）。其余五项按画像一律 DEFER（性能线性放大、取消进程清理、thinking 分叉都要真实 CLI 或 app-server 帧才能定论），ACCEPT/CLOSE 为 0。

## 2. 问题清单

### CX-03 Codex App Server 的 JSON-RPC 成功响应被记为 `unknown_raw_event`，响应分支不可达

- **判定**：FIX_IF_CHEAP —— 改 1 个分派条件即可
- **位置**：`deploy/worker-entrypoint/harness/adapters/codex_events.py:397-399,291-313,527-531`（提交 `cbad9e56`）
- **证据**：`translate()` 的分派条件是 `if "method" in record or ("error" in record and "id" in record)`（`:398`）；而 `initialize` / `thread/start`(或 `thread/resume`) / `turn/start` 的成功响应形如 `{"id":1,"result":{"thread":{...}}}`——既无 `method` 也无 `error`（真实帧形状见单测 `backend/tests/unit/test_codex_harness_adapter.py:703-706`），且 Bridge 会把每一行原样转发到下游客流（`codex_bridge.py:48-70`）。该记录因此落到 legacy 分支，`record_type = record.get("type")` 为 `None`，输出 `_emit("diagnostic", {"code":"unknown_raw_event","type":None})`（`codex_events.py:527-531`）。这同时使 `_translate_app_server` 内处理响应 `result.thread`/`result.turn` 的代码（`:291-313`）永不执行；真实 thread/turn 身份改由 `thread/started`/`turn/started` 通知（`:314-330`）与 `_capture_real_thread_id`（`:59-91`）提供，因此功能不受影响。
- **影响**：每个 Codex 任务固定多出 3 条 WARNING 级 TaskLog（projector 对 `diagnostic` 一律 `log_level="WARNING"`、`message` 取 `payload.message or payload.code`，`worker_event_projector.py:741-757`），把协议正常帧显示成"未知事件"，同时留下一段不可达代码；终态与投影结果不受影响。
- **最小动作**：`codex_events.py:398` → `if "method" in record or "id" in record:`
- **验证**：未运行；静态阅读 `translate` 分派 + Bridge 转发路径 + 单测输入帧。可用一次 Codex 任务的 canonical 事件流核对 `unknown_raw_event` 是否恰好 3 条。

### CX-01 Claude 每个 text delta 派生一个 canonical 事件子进程，长输出任务线性变慢

- **判定**：DEFER —— 纯性能回归（小流 58.4 ms / 411 行流 59.7 ms）
- **位置**：`deploy/worker-entrypoint/harness/runners/claude-run.sh:212-216`、`deploy/worker-entrypoint/harness/adapters/claude_events.py:279-281,134-150`、`deploy/worker-entrypoint/harness/events.py:247,365`（提交 `cbad9e56`）
- **证据**：
  - 本次 patch 在 Claude runner 的参数中加入 `--include-partial-messages`（`claude-run.sh:215`）；V1 的 `deploy/ci-claude.sh` 没有该参数（`git diff -M 8081c946^..HEAD -- deploy/ci-claude.sh deploy/worker-entrypoint/harness/runners/claude-run.sh` 的功能性新增只有 3 处）。V1 冻结 raw 捕获也印证：`backend/tests/fixtures/harness_events/claude/*/stdout.jsonl` 全部 16 个场景 **0 条** `stream_event`。
  - 打开该参数后，translator 对每个 `content_block_delta(text_delta)` 发一条 canonical 事件（`claude_events.py:279-281`），而 `_emit` 每次都 `subprocess.run([sys.executable, writer, ...], check=True)`（`:134-150`）；`events.py` 每次还要加锁、append、`fsync`（`:247-365`）。
  - 本机实测（macOS M1 Pro，`CODIFY_RUNTIME_DIR=/tmp/evtest`，先写一次 `run.started`）：连续 50 次 `events.py message.delta --payload '{"text":"hello world"}'` 共 4.11s ≈ **82ms/事件**。
  - 真实量级：acceptance evidence 记录 Claude Task #505「总时长约 2m32s、**381 条 `message.delta`**」（`docs/superpowers/evidence/2026-09-08-open-harness-v2-current-bundle-real-task-matrix.md:129`，另见 `:548`）→ 按实测单价约 30s 纯事件写入开销。
- **影响**：Claude 任务的 canonical 事件数量与输出长度线性增长，每个 delta 一次解释器启动 + fsync；translator 是单线程且位于 CLI stdout 下游（`claude-run.sh:38-52` 写 fd 9 → translator 的 FIFO），落后时通过管道反压 CLI 输出，因此开销直接落在任务 wall-clock（真实样本约 20%，长输出按比例放大）。这些事件当前也不产生额外投影价值：projector 只在 `message.completed` 缺 `text` 时用累积 delta 兜底（`backend/app/core/worker_event_projector.py:480-486`），而 Claude 的 `message.completed` 一定携带 assistant 记录的完整 `text`（`claude_events.py:305-312`）。
- **最小动作**：删 `claude_events.py:279-281` 的 `text_delta→message.delta` 投影（2 行）。已核实无人消费：前端 task-process 只渲染 `assistant_text`（来自 `message.completed`）与 thinking 行，`message.delta` 在前端零命中；thinking 占位只依赖 `content_block_start/stop`
- **验证**：单事件成本已实测（命令与结果见 §0）；容器内单价与端到端 wall-clock 影响未实测。修复后可用同一命令计时，并对比真实任务的 `message.delta` 条数与总时长。

### CX-02 Codex 取消路径未落地：adapter `terminate` 空实现、runner 无信号 trap，`turn/interrupt` 不可达

- **判定**：DEFER —— 对照画像「无 SLA、强制关单可接受」不需要
- **位置**：`deploy/worker-entrypoint/harness/adapters/codex.sh:283-285`、`deploy/worker-entrypoint/harness/runners/codex-run.sh:32,36-50`、`deploy/worker-entrypoint/bootstrap.sh:258-279`（提交 `cbad9e56`）
- **证据**：
  - `codex_adapter_terminate() { return 0; }`（`codex.sh:283-285`）是空实现；同 patch 的其他 Adapter 都不是：`claude.sh:222-226` 至少 `kill -TERM "${1}"`、`pi.sh:285-295` 走原生 abort/TERM、`opencode.sh:407-445` 先 HTTP abort 再 2s grace 再 TERM。
  - V2 新增了取消路径上的调用点：`codify_signal_exit()` → `adapter_terminate "${CODIFY_HARNESS_ADAPTER_PID:-}"` → `exit 143`（`bootstrap.sh:258-279`，调用在 `:273-274`）。`docker stop` 只把 SIGTERM 交给容器 PID 1，因此这是 Harness 进程树唯一可能收到取消信号的入口。
  - `codex-run.sh` 的 EXIT trap 只做 `rm -rf "${STREAM_DIR}"`（`:32`），既不终止 `python3 codex_bridge.py`（`:42-50`）也不终止 translator（`:36-40`）；Bridge 的 `turn/interrupt` 只在 Bridge 自身收到 TERM/INT 时才发出（`codex_bridge.py:161-177`，注册于 `:181-182`）。
  - Harness 契约要求 `terminate` = "TERM/grace/KILL of the complete process group with evidence"（`docs/architecture/worker-harness-contract-v1.md` 操作表）；thinking plan §4.3 亦写明 Codex 取消"经 `turn/interrupt` 和既有进程 TERM/KILL 兜底"。
- **影响**：用户取消或后端 wall-clock 超时（两者都是 `docker stop`）时，Codex app-server / Bridge / translator 不会收到任何信号，原生 `turn/interrupt` 及它可能产生的 interrupted 证据在生产路径上不可达，进程只能等容器销毁；canonical 侧的思考收尾退化为公共 finalizer 从事件流反推（`common.sh:230-259`）。任务终态本身仍正确：finalizer 合成 `harness.failed(cancelled|timeout)`（`common.sh:305-320,383-400`），writer 拒绝终态后的第二条 harness terminal（`events.py:293-320`），因此不会产出错误的交付结论。同类根因（`CODIFY_HARNESS_ADAPTER_PID` 是 `adapter_run … &` 的子 shell，信号到不了内层 `timeout`+runner）已由 T04/OCB-03 实测、T03/PI-05 记录；本条补的是 Codex 侧连"伸手去 kill"都没有，且 runner 自身没有清理 trap。
- **最小动作**：顺手 2 行：`codex_adapter_terminate` 对 `$1` 发 TERM；`codex-run.sh` 加 EXIT/TERM trap 杀 Bridge。不必做进程组 TERM/grace/KILL 全套
- **验证**：未运行验证（无 docker/真实 CLI）。依据为上述行号；可在容器内用 `docker stop` 场景核对 raw 归档里是否出现 `turn/interrupt`、以及容器退出前 codex 进程是否仍存活。

### CX-INFO-01 打开 partial messages 后 legacy `tool_calls` 数组双写

- **判定**：DEFER
- **位置**：`deploy/worker-entrypoint/harness/runners/claude-run.sh:443-459,505-522`（提交 `cbad9e56`）
- **证据**：同一 tool_use 块被写两次 stub —— `stream_event/content_block_stop` 分支在 `:450-459` 写一条（`jq -nc ... >> "$TOOL_CALLS_FILE"`），随后完整 `assistant` 记录分支在 `:515-522` 又写一条（同一 `{id,name,input,output:null,error:false}` 形状）。V1 没有 `stream_event`，故该重复是本次打开 partial messages 后才出现的。
- **影响**：最终 stdout 的 `tool_calls: ($tool_calls_data | map(del(.id)))`（`claude-run.sh:883-891`）每条工具出现两次；当前唯一消费者 `read_harness_result_summary`（`delivery.sh:70-88`）只读 `.result`，且 `/tmp/codify-harness-output.json` 不在 runtime archive 候选列表内（`bootstrap.sh:203-213`），因此目前无功能影响。
- **最小动作**：删 `claude-run.sh:450-459`（`content_block_stop` 分支）或 `:515-522` 其中一处 stub 写入（1 行），保留 `assistant` 那条
- **验证**：静态比对两条写入路径；未运行（无真实 CLI 流）。

### CX-INFO-02 Claude thinking 块跨消息交错时会被误判为 interrupted

- **判定**：DEFER
- **位置**：`deploy/worker-entrypoint/harness/adapters/claude_events.py:52-137`（提交 `cbad9e56`）
- **证据**：`_OPEN_REASONING` 只按 content index 建槽，`_handle_message_start` 收到新的 `message_start` 时会 `_interrupt_open_reasoning("message_ended")` 并清空所有未闭合块（`:78-91`）；thinking plan §4.1.2 要求按"当前会话 + `parent_tool_use_id`（存在时）+ 消息 ID"维护块归属，实现未使用 `parent_tool_use_id`，`reasoning_id` 只用消息 ID + 索引（`:109-110`）。
- **影响**：若主/子 agent 消息在同一 attempt 内交错，前一条消息仍打开的 thinking 会被记为 `interrupted` 而非 `completed`，该块的 `content_block_stop` 到达时已无槽位（`:114-133` 直接返回），占位状态与耗时展示因此不准确。是否交错取决于真实 CLI 的转发时序。
- **最小动作**：有实证后按 message_id（必要时叠加 `parent_tool_use_id`）分桶——先别改，属猜测性重写
- **验证**：未验证（需要真实 CLI 的并发/子 agent 流）。

### CX-INFO-03 Codex `reasoning_id` 缺少 turn 维度

- **判定**：DEFER
- **位置**：`deploy/worker-entrypoint/harness/adapters/codex_events.py:97-101,458-486`（提交 `cbad9e56`）
- **证据**：`_reasoning_id(item_id)` 只拼 `thread + item`（`:97-101`），thinking plan §3.2 要求包含 thread/session 与 message/turn 身份；translator 对已 `closed_reasoning` 的 ID 会静默处理（`:458-486` 只在 `open_reasoning` 命中时发 completed，否则落 `reasoning_completed_without_start` 诊断）。
- **影响**：若冻结 app-server 在同一 thread 内跨 turn 复用 item 序号（如每个 turn 从 `item_0` 重新计数），同一 attempt 内第二个同号 reasoning 块会既不新建占位也不重复完成，页面只显示第一个块。当前无真实帧可判定 item id 的单调性。
- **最小动作**：有捕获后 `_reasoning_id` 并入 `turn_id`（1 行）；否则不动
- **验证**：未验证（仓库内无 app-server 真实捕获）。

## 3. 逐项核查记录（已确认无问题的关键不变量）

| # | 不变量 / 契约 | 结论 | 依据 |
|---|---|---|---|
| 1 | V1→V2 事件字段一一保留（会话/模型/用量/结果/错误/工具/压缩） | 通过 | 以 V1 冻结期望逐条比对：`backend/tests/fixtures/harness_events/{claude,codex}/*/expected-canonical.jsonl`（本区间**未改动**，`git diff --stat 8081c946^..HEAD -- backend/tests/fixtures/harness_events/` 为空）；测试 `test_real_claude_fixture_stream_translates_to_safe_canonical_events`（`backend/tests/unit/test_claude_harness_adapter.py:373-433`，16 场景）与 `test_codex_fixture_stream_translates_to_canonical_events`（`test_codex_harness_adapter.py:393-445`，17 场景，含 `success_no_changes` 零变化、`context_compaction` 多轮、`cancelled`/`sigkill`/`timeout`）断言 `type/payload/raw_ref` 完全相等；本次实跑两文件 **93 passed** |
| 2 | result 字段（status/success/result/session_id/model/usage/failure/capability_warnings）不丢失 | 通过 | Claude `_write_result`（`claude_events.py:170-215`）、Codex `_write_result`（`codex_events.py:205-238`）保留 V1 全部字段；V2 只把扁平 `harness_key/adapter_version/cli_version` 换成嵌套 `harness`（`result_builder.py:30-56`），符合后端 `validate_result_v2`（`backend/app/core/harness_protocol.py:571-612`）；`session_id` 仍是真实未脱敏值（`claude_events.py:16-47`、`codex_events.py:53-91`） |
| 3 | `control_transport` / `model_protocols` 齐备且与冻结事实一致 | 通过 | Claude `cli_stream_json`/`claude-json`/`anthropic_messages`（`claude.sh:119-121`）、Codex `rpc_stdio`/`codex-app-server-v2`/`openai_responses`（`codex.sh:116-118`）；`harness/manifest.json` 两段与后端 `HARNESS_PROTOCOL_MATRIX`（`harness_protocol.py:637-643`）逐字一致；事件信封与 result 信封同源（`events.py:326-344`、`result_builder.py:49-56`） |
| 4 | attempt 内 Harness identity 不可变 | 通过 | identity 由 `adapter_prepare_config` 导出（`claude.sh:115-121`、`codex.sh:112-120`），且早于首个事件 `run.started`（`runner.sh:59` 先于 `:81/:85`）；writer 侧二次守卫 `Harness identity changed inside one canonical attempt`（`events.py:326-346`） |
| 5 | 唯一 harness terminal；`worker.finalization` 后唯一且最后的 task terminal | 通过 | 两个 translator 都只在流结束/终态处发一次 harness terminal（Claude `:349-372`；Codex `:242-253` 由 `_emit_terminal_at_eof` 在 EOF 发出，`turn.failed`/`turn.completed` 只记录 `terminal_type`，`:428-434,520-535`）；公共层兜底（`runner.sh:149-186`：缺 terminal 时合成 `harness.failed`；"exit 0 + 存在 harness.failed"→ 强制失败）；task terminal 只由 `common.sh` finalizer 产生（`common.sh:262-420`）；writer 拒绝第二条 harness terminal、禁止 `worker.finalization` 之后追加、要求 task terminal 紧跟 `worker.finalization`（`events.py:293-320`） |
| 6 | adapter 不得自己发 task terminal | 通过 | `grep -rn 'run\.completed\|run\.failed' harness/adapters/{claude.sh,claude_events.py,codex.sh,codex_bridge.py,codex_events.py} harness/runners/{claude-run.sh,codex-run.sh}` 无命中；`harness.*` 由 translator 发，`delivery.*`/`worker.finalization`/`run.*` 由 `common.sh` 发 |
| 7 | 进程退出码不被误当作 task 成功 | 通过 | Claude runner 以 `subtype=success` 决定 exit 0/1（`claude-run.sh` 末尾）；Codex runner 以结果文件 `status` 决定（`codex-run.sh:63-81`：`completed`→0、`failed`→1、否则回落 bridge/translator 退出码）；runner 侧再拦一次（`runner.sh:183-186`） |
| 8 | `wait()` 返回值不被当作成功依据 | 通过 | `codex-run.sh:53-61` 先 `wait` 再读权威结果文件；`bootstrap.sh:110-112` 预置 `{}` 保证"没有结果"必然被 `normalize_result` 的 jq 校验拒绝（`claude.sh:188-215`、`codex.sh:244-266`），随后 `runner.sh:149-171` 按退出码给出 `timeout/cancelled/protocol_error` 分类 |
| 9 | Claude stream-json 健壮性（非 JSON 行、未知记录、警告行混入） | 通过（静态 + 单测） | 非 JSON → `diagnostic(non_json_raw_line)` 并保留原文（`claude_events.py:405-425`）；未知 type → `diagnostic(unknown_raw_event)`（`:374-379`）；纯文本 CLI 错误进 `CLI_STDERR_FILE` 并作为 `cli_error` 结果（`claude-run.sh:856-872`）；单测 `test_translator_records_plain_text_cli_error_with_text`、`test_unknown_raw_event_is_non_terminal_diagnostic`（`test_claude_harness_adapter.py:435-467`） |
| 10 | 工具调用/结果、上下文压缩、resume 语义 | 通过 | tool.started/completed 由 assistant/user 记录驱动（`claude_events.py:299-348`）；`system/compact_boundary` → `context.compacted`（`:252-253`），Codex `thread/compacted` → `context.compacted`（`codex_events.py:389-391`）；resume：后端按 lineage 注入（`backend/app/core/worker_task_lifecycle.py:604-622`、`worker_runtime.py:493-494`），Claude 读 `RESUME_SESSION`（`claude-run.sh:199-207`）、Codex 读 `CODIFY_RESUME_SESSION` 并回退 `RESUME_SESSION`（`codex-run.sh:17,47-49`），与后端只对 `{pi,codex,opencode}` 注入 `CODIFY_RESUME_SESSION`（`worker_task_lifecycle.py:687-688`）一致 |
| 11 | thinking 生命周期无重复/无缺失（started→completed/interrupted） | 通过（单测覆盖，真实时序未验证） | Claude 按 `message_start` 重置、`content_block_start(thinking)` 发 started、`content_block_stop` 发 completed、error/abort/EOF/失败 result 仅中断仍打开的块（`claude_events.py:59-131,282-299,349-372`）；Codex 按 item 身份去重（`open_reasoning`/`closed_reasoning`，`codex_events.py:436-500`）并在 `turn.failed`/`turn.completed`/EOF 收尾（`:428-434,520-535`）；单测 `test_partial_thinking_stream_pairs_started_and_completed_with_stable_id`、`test_failed_result_interrupts_open_thinking_before_harness_terminal`、`test_codex_duplicate_reasoning_snapshots_emit_once`、`test_codex_app_server_reasoning_items_map_to_lifecycle` 全部通过 |
| 12 | Codex 单一运行路径、失败不回退 transport | 通过 | runner 只启动 `python3 codex_bridge.py`（`codex-run.sh:42-50`），Bridge 只执行 `codex app-server --stdio`（`codex_bridge.py:136-142`）；`grep -rn 'codex exec' deploy/worker-entrypoint` 无命中；manifest 只声明 `rpc_stdio`/`codex-app-server-v2` |
| 13 | JSON-RPC framing / 请求 id / 权限 fail closed | 部分通过 | 请求 id 单调自增并配对响应（`codex_bridge.py:41-43,86-100`）；未知 server→client 请求以 `-32000` 拒绝而非放行（`:71-84`，turn 循环内 `:222-224`）；`turn/completed` 的 `status` 决定返回值（`:213-240`）；异常路径 `finally` 终止子进程（`:260-268`）。缺陷见 CX-03；无单请求超时（依赖 `TASK_TIMEOUT`，见 §4） |
| 14 | 取消/超时的权威分类 | 通过 | 外层超时标记优先于 exit code：`events.py:258-270`（terminal 事件改判 `timeout`）、`common.sh:46-120`（已写好的 result 被改判为 timeout，保留 identity/session/usage）、`common.sh:383-400`（`CODIFY_CANCELLED` 与 124/130/137/143 映射）；CX-02 是进程清理缺口，不影响终态分类 |
| 15 | sandbox / 权限参数与 V1 一致 | 通过 | `runtime.sh:3-8`（`SANDBOX_MODE=1`、`CLAUDE_MAX_TURNS=20`）由 `deploy/entrypoint.worker.sh:119-131` 的模块列表加载 `runtime` → Claude 走 `--dangerously-skip-permissions`（`claude-run.sh:218-223`）；Codex 由 `CODIFY_HARNESS_SANDBOX_MODE`（`container-boundary`→`danger-full-access` + git 禁写 execpolicy；`sandboxed`→`read-only`）与 `CODIFY_CODEX_SANDBOX` 覆盖决定（`codex.sh:146-178`），Bridge 的 `_sandbox()` 复刻同一判定（`codex_bridge.py:102-108`），两者不会分叉；该变量只能由 Profile 冻结（`worker_task_lifecycle.py:686`），用户自定义 env 被 `CODIFY_/CODEX_/OPENAI_` 等前缀拒绝（`backend/app/core/worker_environment_variables.py:79-108`） |
| 16 | CLI 路径与 Kit inventory 校验的关系（不符时 fail closed） | 通过（含一处已确认的设计变更） | 两个 adapter 只认 `CODIFY_HARNESS_CLI_BIN` 或 Kit manifest 的 `harness_inventory[key].path`（`claude.sh:5-23`、`codex.sh:7-25`），字段名与 Kit 生成端一致（`deploy/Dockerfile.worker-kit:96-111`）；**运行期** digest 不符由 V1 的 `return 1` 改为 WARNING（`claude.sh:96-104`、`codex.sh:83-91`），但 **Kit 侧**仍在构建期 fail closed（`deploy/worker-kit/verify-cli-payloads.sh:130-172` 版本不符即 `exit 2`；`verify-runtime.sh:163` `check_payload_integrity` + `verify-kit-content.py`），与既定契约"Kit present bytes/SHA 不符整 Kit fail closed、version/SHA 差异只是 advisory warning"一致，故不记为缺陷 |
| 17 | 工作目录 / 权限降级 / host mount | 通过 | Claude 以 `env HOME=/home/codify ... RUN_AS -- bin` 降权（`claude-run.sh:139-152`）；Codex 只对 app-server 子进程降权，Bridge/translator 保持 root 以写审计（`codex_bridge.py:136-158`）；新线程 `cwd=os.getcwd()`（`:110-120`），与 V1 `codex exec` 同 cwd，resume 不传 cwd（与 V1 `exec resume` 一致）；两 adapter 都要求 CLI 为绝对路径且可执行（`claude.sh:54-63`、`codex.sh:59-65`） |
| 18 | 凭据不进入 argv / 日志 / 事件 | 通过 | `codex_bridge` 的 argv 只有 `bin app-server --stdio`（`codex_bridge.py:139-142`），凭据走 env（`config.toml` 只写 `env_key = "OPENAI_API_KEY"`，`codex.sh:177-191`）；Claude 的 prompt 与系统提示走文件/stdin 而非 argv（`claude-run.sh:736-749`、`claude.sh:123-131`）；归档前统一脱敏（`sanitize.py:25-65` 覆盖 `sk-ant-*`/`sk-*`/`glpat-*`/Bearer/cookie），hidden reasoning 按 key 脱敏——该规则同时覆盖新增的部分消息路径（`thinking_delta` 的 `thinking` 键 → `<HIDDEN_REASONING_OMITTED>`，`signature_delta` 的 `signature` 键 → `<REDACTED_SIGNATURE>`，`sanitize.py:109-126`）；`bootstrap.sh:51-76` 只打印 "API Key set: yes/no" |
| 19 | 删除行回归面（V1 已验证的边界处理是否被删） | 通过 | Claude runner 对 V1 的删除行仅 3 处：旧 `_e` 输出、`/usr/local/bin/claude` 默认值、无 partial 参数——**事件去重、超时/grace、结果退出码、resume 回退、进程组回收（`cleanup` trap、watchdog、`terminate_claude_process_group`）全部保留**（`claude-run.sh:323-343,672-733`）；translator 侧删除行只有"老 stream_event 分支"与"硬编码 harness_key/ANTHROPIC_MODEL"，语义被新分支取代（`claude_events.py` diff、`codex_events.py:205-238`）；Codex 旧 runner 被替换后，"共享进程组由 `timeout` 兜底"的假设未在 codex 侧重建 → CX-02 |
| 20 | 与 probe / fixture 的一致性 | 部分通过 | Claude fixture（`docs/harness-probes/v2/claude/success.v2.jsonl:2`）的 `cli_stream_json/claude-json/anthropic_messages` 与实现一致；Codex fixture 与 `replay_v2.py` 仍固化 `cli_jsonl`/adapter `2.0.0`（已由 **XC-02**（`17-cross-cutting.md`）单独立项，本文件不重复）；两个 fixture 都不含 `stream_event`（源自 V1 raw 捕获），因此**不覆盖**新增的 partial 路径——该路径目前只有手工构造的单测覆盖（§4） |
| 21 | 事件流内的 harness terminal 与真实交付结论一致 | 通过 | 交付失败不改写 harness terminal：`delivery.failed` 由 finalizer 依据 git snapshot 追加（`common.sh:328-348`），task terminal 依 exit code 判定；evidence #488 记录该受控 divergence 场景 fail-closed 且任务 `failed`（`docs/superpowers/evidence/2026-09-08-open-harness-v2-current-bundle-real-task-matrix.md:121`） |

## 4. 局限与未验证项

- **未运行真实 CLI/Provider**：本机为 macOS/arm64，仓库内的冻结制品 `deploy/worker-cli/claude` 与 `deploy/worker-cli/codex` 都是 linux-x64 ELF（`file` 输出 `ELF 64-bit LSB … x86-64`），无法在本机执行；真实运行还需要 Provider 凭据与网络。因此以下均为静态推论，未实测：
  - Claude `--include-partial-messages` 在 2.1.153 上是否真的**早于**块结束发出 `message_start`/`content_block_start`（thinking plan §4.1 明确"必须用实际 `claude -p` 输出验证"）；若该 CLI 把思考边界推迟到结束，`reasoning_summary.started` 会缺失，只剩 `interrupted`/诊断。evidence `2026-09-06-four-harness-thinking-probes.md` 中 Claude 一栏当时仍标注"待真实 Provider 任务"，但 #528 的长思考正证据（两个 block 469.5s/213.3s）显示该路径已在真实任务中产出 started/completed。
  - Codex App Server 0.146.0 的原生帧：仓库内没有任何 App-Server wire 捕获（`docs/harness-probes/v2/codex/success.v2.jsonl` 是 V1 `exec --json` 的回放）。因此 `thread/start`(resume) 参数集（`model`/`sandbox`/`approvalPolicy`/`effort`）、通知命名（`item/reasoning/summaryTextDelta`、`thread/tokenUsage/updated`、`thread/compacted`）、reasoning item 的 `summary[].type=summary_text` 结构均未经真实帧验证；evidence 只在真实任务中证明了 `run.started`/`model.resolved`/`provider.retry`/`harness.failed`/`run.failed` 落库（`2026-09-08-...codex-app-server-bridge.md` §2），即 `initialize`/`thread/start`/`turn/start` 与失败终态可用，但**真实 reasoning 生命周期与成功 turn**未覆盖。
  - Codex 多轮/恢复：`_STATE["usage"]` 与 `reasoning_id`（thread+item，缺 turn 维度）在"item id 跨 turn 复用"或 resume 返回历史 item 时的行为未验证（见 CX-INFO-03）。
  - 每个 app-server 请求（`initialize`/`thread/start`/`turn/start`）没有单独超时，`_read_response`（`codex_bridge.py:86-100`）会无限期阻塞；当前只由外层 `timeout TASK_TIMEOUT`（默认 1800s）兜底，卡死场景未实测。
- **未运行 docker 取消/超时 E2E**：CX-02 的影响面（进程是否成为孤儿、`turn/interrupt` 是否真的不出现）为静态推论；`adapter_terminate` 收到的 PID 形状问题已由 T04 实测（`04-opencode-bridge.md` OCB-03）。
- **未做前端/投影侧回归**：`reasoning_summary.started/completed/interrupted` 在 UI 上的占位、耗时与"空内容完成"表现（thinking plan §3.3）由 T12/T05 覆盖，本文件只验证事件契约层面。
- **CX-INFO-01/02/03**（tool_calls 双写、Claude thinking 跨消息交错、Codex reasoning_id 缺 turn 维度）的完整证据与影响见 §2 的 `CX-INFO-*` 条目；三者都需要真实 CLI 流或 app-server 捕获才能闭环。
- **文档级**：`docs/superpowers/plans/2026-09-04-thinking-event-placeholder-plan.md:50,244` 仍指向已迁移的 `deploy/worker-entrypoint/legacy/codex-run.sh`（现为 `harness/runners/codex-run.sh`）；`codex.sh:26-31` 的注释仍称"manifest top-level 在 Phase 5 硬切前保持 V1"，而当前 manifest 已是 `codify.worker.runtime-manifest/v2`。均无功能影响。
