# 03 Pi RPC Bridge 与原生事件 —— Code Review

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56`（`dev @ cbad9e56`，工作区与提交一致） |
| 文件 | `deploy/worker-entrypoint/harness/adapters/pi.sh` (+306)<br>`deploy/worker-entrypoint/harness/adapters/pi_bridge.py` (+275)<br>`deploy/worker-entrypoint/harness/adapters/pi_owner.py` (+519)<br>`deploy/worker-entrypoint/harness/adapters/pi_events.py` (+1201)<br>`deploy/worker-entrypoint/harness/runners/pi-run.sh` (+83) |
| 审查方法 | 静态阅读（完整文件 + 跨模块调用方）+ 契约对照（`harness_protocol.py` 校验器、projector、command pump、task_command_gate）+ 与上游 Pi 0.84.2 自带文档/探针 fixture 对账（`deploy/worker-cli/pi/docs/`、`docs/harness-probes/v2/pi/`） |
| 未覆盖 | 未运行真实 Pi CLI（无 linux-x64 运行环境/凭据）；未跑 docker；未执行任何测试（仅阅读 `backend/tests/unit/test_pi_harness_adapter.py`、`test_pi_owner.py` 作为作者意图证据）；Runtime Bundle / Kit / delivery 侧只在与 Pi 的交界处核对 |

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 3 |
| FIX_IF_CHEAP | 1 |
| DEFER | 6 |
| ACCEPT/CLOSE | 5 |

Pi 通道分层清晰（配置/快照 → 命令构造 → 唯一 stdio owner → 单一流式 translator），`delivered = 原生 ACK`、`agent_settled = 真正 settled`、超长行 16MiB 与缺 parent session 启动前 fail-closed 等关键契约都有实现，且与 probe fixture 形状一致。上线后 Pi 是默认 harness，故 Pi 通道即主路径：**FIX_NOW 3 条** —— PI-01（拒绝 ACK 产出非法事件、永久卡死并丢统计投影）、PI-02（初始 `prompt` 被拒时挂到超时且分类失真）、PI-04（表单勾选的 skills 静默不生效）。其余：1 条 FIX_IF_CHEAP（PI-03，摘掉未接线的 `thinking_level`）、6 条 DEFER、5 条 ACCEPT/CLOSE，均按本画像处置。

**本专题触发条件**：

- 需要按命令级 deadline（多人并发 steer）→ PI-INFO-01
- 观察到半行/丢事件，或 Pi 开始输出长 stderr → PI-INFO-04
- 注册表/回滚把 pi 绑 V1 bundle，或接入公网 provider、仓库不可信、Kit 改信任默认值 → PI-INFO-05/06/07

## 2. 问题清单

### PI-01 原生拒绝 ACK 产出的 `control.command.rejected` 缺 `rejection_message`，导致投影 ingest 永久卡死
- **判定**：FIX_NOW
- **状态**：已修复（`7794eb92`）
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi_events.py:603-613`（提交 `cbad9e56`）
- **证据**：
  - 发射端：`pi_events.py:604-613` 用 `"rejection_message": ack.get("rejection_message")` 构造 payload，而 `ack` 是 owner 注入的 metadata，owner 只写 4 个键：`pi_owner.py:356-361`（`command_id` / `sequence_no` / `payload_digest` / `_delivered_at`）。真实路径下该键必然缺失 → `null`。
  - 校验端（本次新增，`git diff` 显示 `_validate_control_event` 为 V2 新增）：`backend/app/core/harness_protocol.py:340-352` 要求 `rejection_message` 必须是 `str`，否则 `raise HarnessProtocolError("control.command.rejected requires rejection_message")`。
  - 消费端：`backend/app/core/worker_event_projector.py:760-786`，`validate_event_by_schema`（772 行）在 `db.begin_nested()` 之前抛出，`cursor.last_offset += processed`（786 行）永不执行；`tail_event_jsonl`（`worker_event_projector.py:791-818`）回滚后 re-raise，`poll_task_artifacts`（`worker_task_artifacts.py:242-262`）每 2s 重试同一 offset ⇒ **永久卡在该记录**。
  - 触发条件：Pi 对 `steer`/`follow_up` 返回 `{"type":"response","success":false,...}`。这是代码显式建模的路径：owner 记 `native_rejected`（`pi_owner.py:383-384`）、pump 有 `DISPATCH_REJECT` 分支（`worker_command_pump.py:752-778`）、单测亦构造该响应（`backend/tests/unit/test_pi_harness_adapter.py:1595-1617`）。上游文档确认该形态存在：`deploy/worker-cli/pi/docs/rpc.md:1347-1358`（失败命令返回 `success:false` 且带 `error`）。
  - 该单测的假 ack（`test_pi_harness_adapter.py:1606-1612`）比 owner 真实 metadata 多一个 `rejection_code`，掩盖了默认值差异。
- **影响**：拒绝事件在流中位于 `agent_settled` 之前（probe 证据：`docs/harness-probes/v2/pi/steer.raw.jsonl` 第 10 行是 ACK、第 104 行才是 `agent_settled`）。ingest 卡死后 `agent_settled` 永不入库 ⇒ `begin_control_drain`（`worker_event_projector.py:459-460`）不执行 ⇒ attempt 停在 `accepting`，pump 不会发 `close`（`worker_command_pump.py:888-900`）⇒ owner 一直等 close（`pi_owner.py:461-482`）⇒ 一次真实成功的 run 以 `TASK_TIMEOUT`（默认 1800s）失败，交付被跳过、日志尾部（含 `harness.completed`）全部缺失。`backfill_event_jsonl_from_archive`（`worker_event_projector.py:820-845`）对同一记录再次抛出且无 catch。
- **最小动作**：`pi_events.py:610`：`rejection_message` 缺省回退 `record.get("error")` 或固定文案（1 行）；不必改 projector 的隔离机制
- **验证**：可用窄范围单测复现——把 `test_pi_rejected_native_ack_maps_control_command_rejected` 的假 ack 改成 owner 真实形状，再用 `validate_event_v2` 校验其 payload，当前必然抛 `HarnessProtocolError`。本次未运行验证（未执行任何测试，结论由源码与校验器静态推出）。

### PI-02 初始 `prompt` 被 Pi 拒绝时只记 diagnostic、不产生 terminal，任务挂到超时
- **判定**：FIX_NOW —— 上线后默认 harness，配置/模型类错误最先撞上且只挂到超时
- **状态**：已修复（`7794eb92`，并新增 model-not-found → `configuration_error` 映射）
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi_events.py:629-634`（提交 `cbad9e56`）
- **证据**：`_handle_response`（`pi_events.py:553-634`）对 `command=="prompt"` 且 `success:false` 落到兜底分支，只发 `diagnostic{"code":"native_command_failed"}`；不设 `_STATE["terminal_failure"]`，此后不会再有 `agent_start`/`agent_end`/`agent_settled`，而 translator 的 terminal 只在 stdin EOF 时产生（`pi_events.py:464-550`），owner 也只在 settled 后结束（`pi_owner.py:461-482`）。owner 侧同样丢弃了握手响应：`pi_owner.py:221-232`（`await response` 后不检查 `success`）。上游文档确认该形态可达：`deploy/worker-cli/pi/docs/rpc.md:65`、`deploy/worker-cli/pi/docs/rpc.md:1347-1358`；`pi.sh:181-183` 的作者注释自己点名了最常见的成因——“`--list-models` 为空、每次 prompt 都以 `Model not found` 失败”。
- **影响**：一次配置/模型解析错误会静默挂起到 `TASK_TIMEOUT`（默认 1800s），最终以 `harness.failed{kind:timeout}`（`runner.sh:150-180`）收尾，真正的 `error` 文本只留在 console log；若 Pi 在该情况下直接退出，则退化为 `protocol_error`（`pi_events.py:510-530`），错误分类同样失真（应为 `configuration_error`）。
- **最小动作**：translator 兜底前单列 `prompt` 且 `success:false` → 置 `terminal_failure`（~4 行）；owner 在 prompt ACK 失败时 `_fail` 收口（~3 行）
- **验证**：构造 `{"type":"response","command":"prompt","success":false,"error":"Model not found: codify/x"}`，跑 `translate()` + `_emit_terminal_at_eof()`，当前不会产出 `harness.completed/harness.failed`。本次未运行验证。

### PI-04 Managed Skills 被物化到 Pi 不会扫描的目录，`task_skills` 静默无效
- **判定**：FIX_NOW —— 上线后默认 harness 的正常路径缺陷（表单可勾选 skills 却静默不生效）
- **状态**：已修复（`7794eb92`，物化到 `${CODIFY_PI_CLI_HOME}/.pi/agent/skills`）
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi.sh:210-229`（提交 `cbad9e56`）
- **证据**：
  - 代码把快照拷到 `${PI_HOME}/skills`（`pi.sh:221-223`），而 `PI_HOME` 是 Codify 自造变量（`pi.sh:84-88`）：`/opt/codify-issue-shared/pi-home` 或 `${CODIFY_RUNTIME_DIR}/pi-home`。
  - Pi 0.84.2 的技能发现路径不含该目录：`deploy/worker-cli/pi/docs/skills.md`（`~/.pi/agent/skills/`、`~/.agents/skills/`、项目 `.pi/skills` / `.agents/skills`、settings `skills`、`--skill <path>`）；Pi 的真实环境变量表也没有 `PI_HOME`（`deploy/worker-cli/pi/docs/environment-variables.md`，配置目录是 `PI_CODING_AGENT_DIR`）。
  - 同一文件自己的注释承认这点：`pi.sh:181-184` 写明 pi 0.84.2 “ignores the PI_HOME env var”，该变量只用于 issue-shared 的 session/skills 持久化；而 CLI 的 HOME 是 `/home/codify`（`pi-run.sh:41-42`），命令行只有 `--mode rpc --provider codify --session-dir --model`（`pi-run.sh:32-35`），没有 `--skill`。
  - 对照实现：codex 拷到 `${CODEX_HOME}/.agents/skills`（CLI 原生位置），`deploy/worker-cli/pi/README.md:595` 提供 `--skill <path>`；pi 两者都没用，且拷贝源是快照根目录整棵树（含 `.claude/skills/`），即使路径可被扫描也会变成 `<dest>/.claude/skills/<name>/SKILL.md`。
- **影响**：manifest 声明 `task_skills: true`，但任何使用 Managed Skills 的 Pi 任务里技能都不会被加载，系统提示词中也没有技能清单，用户侧表现为“技能配置无效且无任何报错”。
- **最小动作**：物化到 Pi 实际扫描位置（`${CODIFY_PI_CLI_HOME}/.pi/agent/skills` 或 `.agents/skills`）或追加 `--skill`；拷贝源与 codex 对齐（~4 行）
- **验证**：需真实 Pi CLI 观察系统提示词中的技能清单（未运行）；本次证据为上游文档 + 本文件注释 + 命令行构造三处一致。

### PI-03 `pi/v1` harness_options 无任何消费者：thinking_level / steering_mode / follow_up_mode 静默失效
- **判定**：FIX_IF_CHEAP —— 无 UI 入口，摘掉 `thinking_level` 即可
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi.sh:206-208`（`pi_adapter_build_command`；整个 adapter 未读 `CODIFY_HARNESS_OPTIONS_JSON`）（提交 `cbad9e56`）
- **证据**：
  - `grep -n HARNESS_OPTIONS deploy/worker-entrypoint/harness/adapters/*.sh deploy/worker-entrypoint/harness/runners/*.sh` 只命中 `codex.sh:123`、`opencode.sh:143`；`pi.sh`/`pi-run.sh` 零命中。
  - 契约侧：`backend/app/core/harness_options.py:41` 把 `pi/v1` 三个字段列为 Task 可覆盖项，`harness_options.py:70-86` 的 `PiV1Options` 默认 `thinking_level="medium"`；`backend/app/core/worker_task_lifecycle.py:675` 把合并后的 options 冻结进容器环境 `CODIFY_HARNESS_OPTIONS_JSON`；manifest 亦声明 `"options_schema": "pi/v1"`。
  - 原生落地手段存在却未被使用：`deploy/worker-cli/pi/README.md:562`（`--thinking <level>`）、`deploy/worker-cli/pi/docs/rpc.md:338-372`（`set_steering_mode` / `set_follow_up_mode`）。
  - 设计文档把三项列为 Profile 默认值：`docs/architecture/open-harness-v2.md:471-480`。
- **影响**：用户/Profile 配置的 `thinking_level` 属于“冻结了但永不生效”的空转配置（`pi.sh:194` 又把每个模型硬编码为 `reasoning:false`，等于彻底关闭 thinking）；`steering_mode`/`follow_up_mode` 目前只允许 `one-at-a-time`（恰好是 Pi 默认值）暂无差异，但一旦放开模式立刻表现为“配置无效”。与 codex/opencode 的实现不对称，说明是遗漏而非取舍。
- **最小动作**：从 `pi/v1` 去掉 `thinking_level`（或映射 `--thinking`）
- **不做**：接 `set_steering_mode`/`set_follow_up_mode` RPC —— schema 只允许一个取值，无差异
- **验证**：`grep` 已证伪“已实现”（本次已做）；端到端需真实 Pi CLI（未运行）。

### PI-05 `pi_adapter_terminate` 既不发原生 abort，也不作用于 Pi/owner 进程
- **判定**：DEFER
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi.sh:285-295`（提交 `cbad9e56`）
- **证据**：`bootstrap.sh:273-274` 传入的是 `CODIFY_HARNESS_ADAPTER_PID`，即 `adapter_run … &` 的 **pi-run.sh** PID（`runner.sh:135`）；`PI_PID` 在全仓库没有任何赋值点（`grep -rn PI_PID deploy` 只命中本文件这一处引用），所以 `local pid="${1:-${PI_PID:-}}"` 拿到的是 wrapper。注释（`pi.sh:286-289`）承诺 “prefer a native abort/close … 回退到给进程组发 TERM”，但代码既没有向 owner 传 abort 请求（owner/translator 也没有发送 `abort` 的路径，`pi_events.py:623-627` 的 abort 分支因此只在手工场景可达），也没有 `kill -- -PGID`；owner 自身没有 SIGTERM handler，Pi 是它的子进程。
- **影响**：取消/超时时被 TERM 的是 wrapper，`pi_owner.py` 与 Pi CLI 变成孤儿并在容器宽限期内继续运行（继续消耗 token / 继续流式请求）；取消路径也不会产出 `stopReason: aborted` 事件，cancelled 映射（`pi_events.py:805-813`）与 probe 的 abort 场景（`docs/harness-probes/v2/pi/abort.raw.jsonl`）在生产取消路径上不可达。注意 `claude_adapter_terminate` 同形状（`claude.sh:222-226`），这是共性结构；pi 侧额外的问题是注释与实现不符。
- **最小动作**：【建议过重】 不做进程组/信号重构；只把与实现不符的注释改对（1 行）
- **验证**：`grep PI_PID` + `bootstrap.sh:273-274`/`runner.sh:135` 的 PID 传递链即可确认（本次已做）；真机进程回收行为未验证。

### PI-06 `message.delta` 的 payload 键与 projector 读取的键不一致（`content` vs `text`）
- **判定**：DEFER —— raw archive 与终态不受影响
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi_events.py:764-768`（提交 `cbad9e56`）
- **证据**：发射端写 `{"content": delta, "role": "assistant"}`；消费端 `backend/app/core/worker_event_projector.py:480-484` 读 `payload.get("text")` → `_text(None)` → 空串；`backend/app/core/harness_protocol.py:219-255` 对 `message.delta` 无 payload 校验，因此不报错，只是累积缓冲恒空。`claude_events.py:280` 用 `{"text": ...}`（可累积），`opencode_events.py:779` 与 pi 一样用 `content`。
- **影响**：`message.completed` 的文本回退路径（`worker_event_projector.py:483-484` 的 `or "".join(self._message_parts)`）在 Pi 上恒为空；只要某条消息以 `text_delta` 流式输出却没有触发 `message.completed`（例如 `message_end` 的 `stopReason` 不在 `("stop","end_turn")` 内，见 `pi_events.py:815-823`），该段助手文本就完全不出现在任务日志。
- **最小动作**：1 行改发 `{"text": delta}`（与 claude 对齐），顺手做
- **验证**：读代码即可确认；可用 `translate()` + 假 writer 断言 projector 的 `_message_parts` 非空（本次未运行）。

### PI-07 原生拒绝的审计码与实际原因不一致（`native_rejected` 不在拒绝码表内）
- **判定**：DEFER
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi_owner.py:383-384`（提交 `cbad9e56`）
- **证据**：owner 把原生 `success:false` 记为 `rejection_code="native_rejected"`（同上），pump 直接落库（`worker_command_pump.py:752-766`；`write_command_rejection` 不做码表校验，`backend/app/core/task_harness_commands.py:348-373`）；但 `backend/app/core/harness_protocol.py:43-56` 的 `REJECTION_CODES` 没有 `native_rejected`，且 owner 的 metadata 里也没有 `rejection_code`（`pi_owner.py:356-361`），canonical 审计事件只能退回默认值 `delivery_outcome_unknown`（`pi_events.py:610`），前端走 `public_rejection` 兜底文案（`task_harness_commands.py:71-78`）。
- **影响**：命令确定被拒绝的场景，事件日志与 UI 显示为“结果未知 / 命令被拒绝（通用）”，数据库行里存的是另一个码，审计口径不一致（不影响终态与投递）。
- **最小动作**：拒绝码表加 `native_rejected` 并透传原生 error（~3 行），或接受现有文案
- **验证**：`grep` 码表 + 读 owner metadata 构造即可确认（本次已做）。

### PI-08 `pi_bridge.PiBridge` 是死代码，且与线上 owner 的策略不同
- **判定**：DEFER
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi_bridge.py:77-236`（提交 `cbad9e56`）
- **证据**：线上命令路径是 `control_client.py` → owner Unix socket → `pi_owner.py:307-388`；`pi.sh:5`/`pi-run.sh:9` 只把 `CODIFY_PI_BRIDGE` 当作定位目录用（`pi-run.sh:60-72` 里 `python3 "${CODIFY_PI_BRIDGE%/*}/pi_owner.py"`），全仓库无 `PiBridge(` 调用点（仅单测 `test_pi_harness_adapter.py:443-560`）。而 `PiBridge.dispatch` 的语义与 owner 不同：它允许 `control_gate == "starting"`（`pi_bridge.py:177-180`）而 owner 直接拒绝（`pi_owner.py:333-334`）；它回传 `__pipayload_for_translator`（`pi_bridge.py:206`）而 owner 注的是 `__command_ack`（`pi_owner.py:252`）。
- **影响**：模块 docstring 自称 “the real Pi bridge”，后续维护者若据此改 RPC 帧或 gate 语义会得到与线上不一致的行为，同时 ACK 关联与超时策略两处实现长期漂移。
- **最小动作**：纯删除 `PiBridge`/`announce_settled` + 其单测（顺手）
- **验证**：`grep -rn "PiBridge" --include="*.py" --include="*.sh" .`（本次已做，仅 `pi_bridge.py` 自身与单测命中）。

### PI-INFO-02 follow-up 重开 accepting 依赖“settled 之后仍会开新 run”，且无兜底
- **判定**：DEFER
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi_owner.py:385-386`
- **证据**：`closing` 窗口内 follow_up ACK 成功后设 `reopen_after`，只在后续 `agent_start`/`turn_start` 上挂 `__pi_reopen_after`（`pi_owner.py:254-259`）→ translator 发 `pi_follow_up_turn_started`（`pi_events.py:1050-1056`）→ projector CAS `closing→accepting`（`task_command_gate.py:29-59`）。但上游文档说 `agent_settled` 之后不再自动继续 queued follow-up（`deploy/worker-cli/pi/docs/rpc.md:884-887`、`deploy/worker-cli/pi/docs/extensions.md:311-314` 的示意图里 settle 之后是 "user sends another prompt"）；probe 只覆盖“settle 之前入队 follow-up”（`docs/harness-probes/v2/pi/followup.raw.jsonl` 第 10 行 ACK、第 142 行才 `turn_start`），未覆盖 settle 之后的 follow-up。
- **影响**：若 Pi 对空闲态的 follow_up 回 `success:true` 却不开新 run，`awaiting_follow_up_turn` 永不清零（`worker_command_pump.py:669-689`、`888-900`），owner 收不到 close，任务挂到超时；当前没有任何“等不到 turn 就强制收口”的兜底。
- **最小动作**：已存在 `request_force_close_after_unknown_follow_up` 兜底钩子，加显式上限（~5 行）；或先补 probe 再定

### PI-INFO-03 JSON 行先 sanitize 再解析，与 `sanitize_json_value` 的既有约定相悖
- **判定**：DEFER —— 单改 Pi 反而制造不对称
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi_events.py:1143`
- **证据**：`input_text = sanitize(raw_input)` 先作用于整条序列化 JSON 再 `json.loads`；同目录 `sanitize.py:92-99` 的 `sanitize_json_value` docstring 明确写“对序列化后的 JSON 直接做字符串 sanitize 会吃掉转义引号/换行，必须解析后再按值清洗”。当前靠 `_lenient_loads`（`pi_events.py:44-112`）与 `_lenient_agent_end`（`pi_events.py:114-137`）兜底，最坏情况整条记录被丢弃（只留 `non_json_raw_line` diagnostic，`pi_events.py:1190`），若被丢的是 `agent_end`/`agent_settled` 则退化为 `protocol_error`。
- **影响**：低概率的记录损坏/丢失（claude/codex/opencode 同样如此，属跨模块共性问题）。
- **最小动作**：解析后改 `sanitize_json_value`（~3 行），非必要

### PI-INFO-01 时间窗口刻度 ≥ 默认 TASK_TIMEOUT
- **判定**：ACCEPT/CLOSE —— 见「何时再管」
- **何时再管**：需要按命令级 deadline（多人并发 steer）
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi_owner.py:32`
- **证据**：`NATIVE_COMMAND_ACK_TIMEOUT_SECONDS = 1800`（`pi_owner.py:32`）、`SOCKET_TIMEOUT_SECONDS = 1830`（`control_client.py:33`）、pump 的 `CONTROL_TRANSPORT_TIMEOUT_SECONDS = 1890` / `CONTROL_RESULT_TIMEOUT_SECONDS = 1860`（`worker_command_pump.py:63,69`），而外层 `timeout ${TASK_TIMEOUT:-1800}`（`pi.sh:253`）与 `TASK_TIMEOUT` 默认值同样是 1800（`worker_runtime.py:435`）。
- **影响**：默认超时下这几层窗口永远走不完，命令终局由 timeout 拆除路径决定，而不是 probe README 设想的“等到 turn 边界 ACK”。
- **动作**：不改代码（本阶段书面接受并关闭）

### PI-INFO-04 Pi 的 stderr 与 RPC JSONL 合并到同一管道
- **判定**：ACCEPT/CLOSE —— 见「何时再管」
- **何时再管**：观察到半行/丢事件或 Pi 开始输出长 stderr
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi_owner.py:195`
- **证据**：`stderr=asyncio.subprocess.STDOUT`，owner 按行解析 JSON；非 JSON 行落到 translator 的 `non_json_raw_line`（`pi_events.py:1190`），说明实现已预期混入。单条记录上限 16MiB（`pi_owner.py:22,201`），大记录分块写时与 stderr 写在同一管道上存在交错风险。
- **影响**：理论上可产生半行记录（丢事件或触发 lenient 修复），probe 未观察到。
- **动作**：不改代码（本阶段书面接受并关闭）

### PI-INFO-05 `pi_adapter_normalize_result` 缺少 V2 契约门禁（与 claude/codex 不对称）
- **判定**：ACCEPT/CLOSE —— 见「何时再管」
- **何时再管**：出现把 pi 绑 V1 bundle 的注册表/回滚场景
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi.sh:261-281`
- **证据**：`claude.sh:191-194`、`codex.sh:251-255` 都有 `[ "${CODIFY_RUNTIME_CONTRACT_VERSION:-}" = "codify.worker.harness/v2" ] || return 1`，pi（与 opencode）没有；而 `pi_adapter_metadata` 只把 contract 当默认值输出（`pi.sh:30`），`events.py:328-345` 却按环境变量决定 event schema。
- **影响**：若 pi 被绑到 V1 bundle，canonical 事件会以 v1 schema + 无 `control_transport` 的信封落盘，最终表现为难排查的 `HarnessProtocolError`，而不是“适配器拒绝启动”。当前注册表只给 V2 bundle 配 pi，所以不可达。
- **动作**：不改代码（本阶段书面接受并关闭）

### PI-INFO-06 `--model` 直接使用快照模型 ID，未做 `provider/id[:thinking]` 语法防护
- **判定**：ACCEPT/CLOSE —— Task 421 实证：含 `/`/`:` 的模型 ID 已 completed
- **何时再管**：接入公网/第三方 provider
- **位置**：`deploy/worker-entrypoint/harness/runners/pi-run.sh:32-35`
- **证据**：`pi-run.sh:32-35` 把 `ANTHROPIC_MODEL`/`OPENAI_MODEL` 原样作为 `--model`；上游文档说明该参数支持 `provider/id` 与 `:thinking` 后缀（`deploy/worker-cli/pi/README.md:560,645-651`），且 provider 解析优先级未见文档化。若快照模型 ID 含 `/`（OpenRouter 风格）或 `:`（Ollama 风格），`--provider codify` 是否仍然胜出无法从文档断定。
- **影响**：最坏情况是模型被解析到内置 provider（其 baseUrl 为公网默认值），即“Endpoint 快照被改写”；这是本专题 checklist #8 的残留风险点，本次未能证伪。
- **动作**：不改代码（本阶段书面接受并关闭）

### PI-INFO-07 未显式关闭项目信任，仓库侧 `.pi/settings.json` 的处理依赖环境默认值
- **判定**：ACCEPT/CLOSE —— 见「何时再管」
- **何时再管**：仓库来源变不可信或 Kit 改默认值
- **位置**：`deploy/worker-entrypoint/harness/runners/pi-run.sh:32-45`
- **证据**：Pi 在非交互模式（含 `--mode rpc`）对项目资源按 `defaultProjectTrust` 处理，默认 `ask` = 忽略（`deploy/worker-cli/pi/docs/settings.md` "Project Trust"）；adapter 既没写 `defaultProjectTrust: "never"`，也没传 `--no-approve`。adapter 注释声称 “Harness-specific variables and user config cannot override that Snapshot”（`pi.sh:101-109`）——baseUrl/apiKey 确实只来自 `~/.pi/agent/models.json`（`pi.sh:189-195`），工作区仓库改不到；但 `defaultThinkingLevel`、`skills`、packages 等项目级设置是否被忽略只取决于镜像里的全局默认值。
- **影响**：当前默认下无实际影响；若基础镜像/Kit 把 `defaultProjectTrust` 设为 `always`，克隆仓库里的 `.pi/settings.json` 会参与配置解析。
- **动作**：不改代码（本阶段书面接受并关闭）

## 3. 逐项核查记录（关键不变量/契约）

| # | 检查项 | 结论 | 依据 |
|---|---|---|---|
| 1 | JSONL framing：只按 LF 分行、不误用 Unicode 分隔符 | 通过 | owner 用 `asyncio.StreamReader.readline()`（只切 `\n`，`pi_owner.py:243`），与 `deploy/worker-cli/pi/docs/rpc.md` "Framing" 一致；行尾 `\r` 由 `json.loads` 容忍 |
| 2 | 超大行 / 部分读 fail-closed | 通过 | `limit=PI_RPC_STREAM_LIMIT`（16MiB，`pi_owner.py:22,201`）；超限时 `readline()` 抛 `ValueError`，被 `pi_owner.py:289` 捕获 → `_fail` → 非零退出，不静默截断 |
| 3 | 不假设 Pi 会按 request id 原生去重 | 通过 | owner 自建 `pending`/`command_metadata`（`pi_owner.py:249-253,347-361`），同一 `command_id` 二次投递先查 journal：已有 response → 回放，只有 request → 回 `unknown` 且绝不重发（`pi_owner.py:335-346`） |
| 4 | stdin 断开 / 中断流处理 | 通过 | 未 settled 时 stdout EOF → `_fail("Pi stdout ended before agent_settled")`（`pi_owner.py:291-292`）；translator 在 stdin EOF 出唯一 terminal（`pi_events.py:464-550`）；`finish()` 先关 Pi stdin、等/杀 Pi、再关 translator stdin（`pi_owner.py:418-434`），`agent_settled` 必在 close 之前被写入 translator 管道 |
| 5 | `delivered` = 原生 ACK，不当作“模型已消费” | 通过 | `pi_events.py:592-602` 只发 `control.command.delivered` 且带 `delivered_at`；真正 settled 走 `agent_settled`（`pi_events.py:1029-1038` 发 canonical，`pi_owner.py:278` 置本地 event）；pump 仅按 ACK 落 `delivered` 终态（`worker_command_pump.py:738-751`） |
| 6 | RPC success 仅代表 accepted/queued/handled | 部分通过（失败分支见 PI-02） | 上游语义 `deploy/worker-cli/pi/docs/rpc.md:76`；`pi_owner.py:377-384` 只在 `success:true` 时给 `ack` |
| 7 | steering/follow_up 文本按 request id 关联、不按文本猜 ID | 通过 | 只按 owner 自己的 request id 关联 `__command_ack`（`pi_owner.py:248-253`）；`queue_update` 只按 `steering[i]`/`followUp[i]` 序号投影（`pi_events.py:826-841`），字段形状与 fixture 一致（`docs/harness-probes/v2/pi/steer.raw.jsonl` 第 9 行 `{"steering":[...],"followUp":[]}`，`deploy/worker-cli/pi/docs/rpc.md:1028-1038`） |
| 8 | 多 steer 的 one-at-a-time 与顺序 | 通过 | owner 用 `dispatch_lock` 串行化除 `close` 外的全部帧（`pi_owner.py:295-305`），pump 侧严格按 `sequence_no` 取队首且不允许 SKIP LOCKED 越过队首（`worker_command_pump.py:532-554`） |
| 9 | settled → closing → 排空 → 唯一 harness terminal | 部分通过 | `agent_settled` → `begin_control_drain`（`worker_event_projector.py:459-460`，CAS 见 `task_command_gate.py:20-27`）；排空后 close IPC（`worker_command_pump.py:888-900`）→ owner ack（`pi_owner.py:312-328`）→ translator 在 EOF 出唯一 terminal（`pi_events.py:464-550`）。缺陷：PI-01 可使 drain 永不发生；PI-INFO-02 的重开路径无兜底 |
| 10 | 不提前发 canonical terminal | 通过 | terminal 仅在 EOF 产生；`harness.completed` 之前先 `usage.final`（`pi_events.py:437-441` 对比 `pi_events.py:536-543`），未见中途发 terminal 的分支 |
| 11 | 进程管理：pid/租约/清理/孤儿 | 部分通过 | owner 是唯一 stdio owner（`pi_owner.py:185-232`），异常路径 finally 兜底关进程（`pi_owner.py:489-500`）；缺陷见 PI-05、PI-INFO-04 |
| 12 | crash 后不隐式回退 transport | 通过 | 全链路无“RPC 失败改走 CLI”分支；`pi.sh:64-71` 仅对版本差异做 advisory 告警，`pi-run.sh` 始终 `--mode rpc` |
| 13 | session 捕获与 resume | 通过 | 取**最新** `get_state` 的 `sessionId`（`pi_events.py:172-200`）；resume 用 `new_session`+`parentSession` 路径（`pi_owner.py:221-227`），与 `deploy/worker-cli/pi/docs/rpc.md:178-200` 一致；文件名 `<timestamp>_<uuid>.jsonl` 与 `stem.endswith("_"+id)` 匹配（`deploy/worker-cli/pi/docs/session-format.md:8`、`pi_owner.py:176-183`） |
| 14 | 跨 harness resume / 缺 parent 的 fail-closed | 通过 | 缺 session 目录或文件即 `RuntimeError`（`pi_owner.py:171-183`），非 Pi 的 session id 找不到文件即失败；task/attempt 帧校验 `pi_owner.py:308-311` |
| 15 | attempt 内 harness identity 不可变 | 通过 | identity 来自导出环境（`pi.sh:27-37`、`result_builder.py:19-38`），events.py 对首事件之后的 identity 变化直接报错（`events.py:346-347`） |
| 16 | 事件映射与去重（text/thinking/tool/usage/model/settled） | 部分通过 | text/thinking/tool/usage 映射齐全且做了去重与占位配对（`pi_events.py:725-783`、`887-948`、`464-550`）；键名问题见 PI-06；`reasoning_summary.interrupted` 必带非空 `reasoning_id`（`pi_events.py:444-462`）满足 `harness_protocol.py:231-243` 的 fail-closed 校验 |
| 17 | 工具失败 vs 模型错误区分 | 通过 | `tool.completed.error/isError/exit_code`（`pi_events.py:887-947`）；模型错误走 `message_end.stopReason/errorMessage` → `terminal_failure`（`pi_events.py:785-812`） |
| 18 | 三模型协议分支完整性 | 通过 | `pi.sh:128-172` 覆盖 anthropic_messages/openai_responses/openai_chat_completions 并做各 SDK 路径归一；`pi-run.sh:25-31` 按协议取模型，非法协议显式退出；`pi.sh:110-125` 校验 manifest 的 `model_protocols` 声明 |
| 19 | Endpoint 快照强制覆盖 | 通过（残留 PI-INFO-06/07） | 只写 `providers.codify`（`pi.sh:189-195`），不读任何既有 models.json；`--provider codify` + `--model` 由 `pi-run.sh:32-35` 固定；CLI HOME 固定为 `/home/codify`（`pi-run.sh:41-42`）；`CODIFY_*`/`PI_*` 命名空间在自定义环境变量中被整体保留拒绝（`worker_environment_variables.py:94-111`），任务/仓库无法重定向配置目录 |
| 20 | 凭据与日志 | 通过 | key 只落 `~/.pi/agent/models.json`（`chmod 600`，`pi.sh:189-201`），不进 argv/命令行；raw archive 经 `sanitize()`（`pi_events.py:1143,1179-1188`）；runtime archive 只收 `CODIFY_RUNTIME_DIR` 内文件，不含 `/home/codify`（`bootstrap.sh:204-217`） |
| 21 | 与 probe 证据的一致性 | 通过（有缺口） | `queue_update` 字段、`agent_end`→`agent_settled` 顺序、prompt/steer/follow_up ACK 时机、`get_state.data.sessionId` 均与 `docs/harness-probes/v2/pi/*.raw.jsonl` 及上游文档对得上；缺口是 abort fixture 无 `response abort` 记录（`abort.raw.jsonl` 仅 12 行）与“settle 之后送 follow-up”未覆盖（PI-INFO-02） |

## 4. 局限与未验证项

- **无真实 Pi CLI 可运行**：`deploy/worker-cli/pi/pi` 是 linux-x64 制品，本机为 macOS/arm64，且真实运行需要 provider 凭据与网络。因此以下判断为静态推理 + 上游文档/探针对账：PI-02 的触发形态（`prompt success:false` 是否必然出现、Pi 是否会在该情况退出）、PI-03 的 `--thinking` 映射效果、PI-04 的技能发现路径、PI-INFO-06 的 `provider/id` 解析优先级。
- **未执行任何测试**：本次未运行 `pytest`（含单文件）与 docker；PI-01/PI-02/PI-06 的复现方式写在“验证”列但未实际运行，close IPC、terminate、archive 等容器路径均未实测。
- **跨模块结论只做到调用方一级**：pump 的 lease/严格顺序、projector 的 gate 状态机、delivery 生命周期属 T01/T02/T11 专题，本文只在与 Pi 的交界处引用其行为。
- **两处 probe 缺口**：`docs/harness-probes/v2/pi/abort.raw.jsonl` 未包含 `response abort` 记录，abort ACK 分支（`pi_events.py:623-627`）没有 fixture 支撑；“settle 之后送 follow_up”无 fixture，导致 PI-INFO-02 无法闭环。
- **未覆盖的原生事件**：`pi_events.py` 中的 `summarization_retry_*`、`extension_error`、`bash_execution_update`、`compaction_*`、`auto_retry_*` 映射无 probe 覆盖（probe README 自述未复现 compaction/retry），仅按上游文档字段推断。
