# 07 公共 Runner / Bridge 基础设施与 harness manifest —— Code Review

> 审查日期：2026-09-12 · 审查目标：`dev @ cbad9e56`（基线 `8081c946^` = `7b253fbf`）
> 专题范围：worker 侧共享层 —— 公共 Runner（`runner.sh`/`common.sh`）、控制通道（`bridge.py`/`control_client.py`）、
> canonical event writer（`events.py`）、冻结 manifest（`manifest.json`）、共享 result/sanitize 助手。

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `git diff 8081c946^..cbad9e56`（本专题切片：9 文件 +1,111/−72） |
| 文件（+/-） | `harness/runner.sh`(+169/-2)、`harness/common.sh`(+302/-47)、`harness/control_client.py`(+130)、`harness/manifest.json`(+116/-21)、`harness/events.py`(+216/-2)、`harness/bridge.py`(+93)、`harness/adapters/result_builder.py`(+56)、`harness/adapters/sanitize.py`(+19/-2)、`deploy/worker-kit/bridge-selfcheck.sh`(+10) |
| 参照（本专题未改动，但被 manifest/契约变更直接影响） | `worker-entrypoint/codegraph.sh`、`worker-entrypoint/main.sh`、`worker-entrypoint/bootstrap.sh`、`worker-entrypoint/git-delivery.py`、`worker-entrypoint/harness/runners/claude-run.sh`、`backend/app/core/harness_protocol.py`、`backend/app/core/harness_registry.py`、`backend/app/core/worker_command_pump.py`、`backend/app/core/worker_runtime_bundle.py` |
| 审查方法 | 静态阅读 HEAD 完整文件（含调用方/消费方）+ 跨边界契约常量对照（shell↔python↔backend）+ 4 组只读实验：① `events.py` 终态/顺序不变量实测；② jq capability 判定实测；③ `sanitize()` 输入输出实测；④ bash「EXIT trap 内 errexit / 重复 TERM」语义实测 |
| 未覆盖 | 各 harness adapter 内部实现（`claude.sh`/`codex.sh`/`pi.sh`/`opencode.sh`、`*_events.py`、`*_bridge.py`、`runners/*`；属 03/04/05/06 专题）；Model Endpoint / provider_options 代理语义（10 专题）；Runtime Bundle 冻结与 Kit 制品（08/09 专题）；**未在真实容器/Docker 内启动任何脚本**（本机无 Docker、无 Claude/Codex/Pi/OpenCode CLI） |

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 2 |
| FIX_IF_CHEAP | 0 |
| DEFER | 4 |
| ACCEPT/CLOSE | 3 |

公共 runner 的终态纪律（flock + 由流推导 seq）把「唯一 harness terminal → delivery 只能在其后 → 唯一 `worker.finalization` → 唯一 task terminal」做成硬约束，实测 8 条拒绝路径全部生效；控制通道 framing、门禁词表、超时层级与「worker 不发明 command 状态」也都成立。**FIX_NOW 是 RUN-01 与 RUN-02**：前者让 V2 下 claude 的模型化 commit message / MR summary 与 CodeGraph 永久失效，后者让单条 payload 超 128 KiB 时 canonical writer `execve` 失败——两者都在主路径上静默丢掉交付，修复各只需个位数行。其余 DEFER 4 项不改变对外行为，ACCEPT/CLOSE 3 项按画像书面接受（过度防御、正常路径不可达）。

## 2. 问题清单

### RUN-01 V2 manifest 收窄 capability 词表后，`run_text`/`codegraph` 判定永久失效
- **判定**：FIX_NOW —— 修复 2 行、零 schema 改动
- **位置**：`deploy/worker-entrypoint/harness/manifest.json:29-35`（claude）、`:90-96`（pi）；消费方 `deploy/worker-entrypoint/harness/runner.sh:94-99,194-200`、`deploy/worker-entrypoint/codegraph.sh:73-79`、`deploy/worker-entrypoint/main.sh:155,235`（提交 `cbad9e56`）
- **证据**：
  1. V2 manifest 的 `adapters.claude.capabilities` 只有 `resume/task_skills/usage_tokens/steering/follow_up`（`manifest.json:29-35`）；V1 基线同一处声明了 `"run_text": true, "codegraph": true`（`git show 8081c946^:deploy/worker-entrypoint/harness/manifest.json`）。
  2. `CODIFY_HARNESS_CAPABILITIES` 的唯一来源就是该对象：`claude_adapter_detect_capabilities()` = `claude_adapter_metadata | jq -ce '.capabilities'`（`adapters/claude.sh:106-108`；metadata 取自 manifest 的 `.adapters.claude`，`claude.sh:25-50`）→ `runner.sh:48-54`。
  3. `codify_harness_run_text()` 先要求 `.["run_text"] == true`（`runner.sh:194-200`），`prepare_codegraph()` 同样要求 `.["codegraph"] == true`（`codegraph.sh:73-79`）。实测（`jq -e --arg capability <k> '.[$capability] == true' <(jq -c '.adapters.claude.capabilities' manifest.json)`）：`run_text` → exit 1，`codegraph` → exit 1。
  4. manifest 侧**无法**恢复：后端 `HARNESS_CAPABILITY_KEYS = {resume,task_skills,usage_tokens,steering,follow_up}`（`backend/app/core/harness_protocol.py:647-649`），`_validate_manifest_adapter` 对未知 capability 键 fail closed（`harness_protocol.py:836-843`）→ 失效点在消费方判定，而不在数据。
  5. 作者意图是 run_text 在 V2 下继续工作：本 patch 新增的注释 `runner.sh:186-188` 明确写「the harness also serves the commit-message and MR-summary run_text calls during delivery」。
- **影响**：V2 claude（默认 harness）任务中，(a) commit message 恒走 `main.sh:159-166` 的硬编码兜底文案（日志 `Harness commit message generation failed with exit code …; using fallback`）；(b) MR overall summary 恒为 `main.sh:247` 的 "keeping previous MR summary"；(c) `delivery.sh:190` 的 summary 修复路径同样不可用；(d) 即使 Worker Profile 打开 `CODIFY_CODEGRAPH_ENABLED`，`codegraph.sh:75-78` 也会打印 "unsupported by the frozen Harness Adapter" 并静默停用 CodeGraph。`claude_adapter_run_text`（`claude.sh:215-222`）仍然存在且可用，即实现与判定脱节。
- **最小动作**：① `runner.sh:194-200` 的能力判定 `codify_harness_capability_enabled "run_text"` → `declare -F adapter_run_text`（4 个 adapter 都定义了该函数；不支持的 codex 版返回非零，自然回落，与今天行为一致）。② `codegraph.sh:73-79` 的 capability 分支 → 按 `[ "${CODIFY_HARNESS_KEY}" = claude ]` 判定（codegraph 只 `--target=claude`；`command -v codegraph` 已有独立检查）
- **验证**：已实际验证（jq 判定 + 两侧读码交叉核对 + V1/V2 manifest 对比）；未在容器内跑真实任务。

### RUN-02 canonical event writer 只接受 argv 传 payload，超 ~128 KiB 即整条链路失败
- **判定**：FIX_NOW —— 触发面 ≪1% 任务，但修复代价近乎零
- **位置**：`deploy/worker-entrypoint/harness/events.py:369-376`；写入方 `deploy/worker-entrypoint/harness/common.sh:17-24`、`deploy/worker-entrypoint/harness/adapters/claude_events.py:134-149`（提交 `cbad9e56`）
- **证据**：
  1. writer 的唯一 payload 入口是 `--payload "$2"`（`events.py:371-376`）；shell 侧 `codify_emit_event()` 用 `python3 "$writer" "$type" --payload "$payload"`（`common.sh:17-24`），四个 adapter 全部用 `subprocess.run([python, writer, type, "--payload", json.dumps(payload)], check=True)`（`claude_events.py:134-149`、`codex_events.py:150-160`、`pi_events.py:259-270`、`opencode_events.py:296-310`）。
  2. Linux 对**单个** argv 元素有硬上限 `MAX_ARG_STRLEN = 32 × PAGE_SIZE`（4 KiB 页 = 131,072 B）；超限时 `execve` 返回 `E2BIG`，python 侧抛 `OSError: [Errno 7] Argument list too long`，shell 侧 `exec` 失败（126/127）。
  3. payload 无任何上限：`claude_events.py:305-320` 把 `message.completed.text` 与 `tool.started.input` 原样写入（Claude Code 的 `Write` 工具 input 含**整份文件内容**）；`common.sh:356-367` 的 `worker.finalization` 携带 `git_delivery`，其 `commits`/`recovered_commits` 由 `git-delivery.py:385-392` 无界收集（`_list_commits` 不设条数上限）。
  4. 同仓库已承认该约束：`runners/claude-run.sh:875-877` 明确因为 "hits OS ARG_MAX limit" 把大字段从 `--arg/--argjson` 改为 `--slurpfile`。
- **影响**：两条独立后果。(a) **adapter 侧**：`claude_events.main()` 逐行 `translate()` 无 per-record 兜底（`claude_events.py:383-428`），`OSError` 直接逸出 → translator 进程死 → 不再写 `CODIFY_HARNESS_RESULT_FILE` → `claude_adapter_normalize_result` 失败（`claude.sh:188-213`）→ runner 记 `harness.failed` → `main.sh:50-53` 提前 `exit`，**已完成的代码改动不提交、不推送、不建 MR**（写大文件是完全常规的编码行为）。(b) **shell 侧**：`codify_emit_event` 失败若发生在 EXIT trap 的 finalizer 内，本机实验证实 bash 的 errexit 在 trap 内仍然生效（`set -e` 下 trap 内命令失败会终止 trap 函数）→ finalizer 在 `common.sh:369` 的 `worker.finalization` 处中断，`run.completed`/`run.failed` 永不写出（`bootstrap.sh:313-315` 的 `|| true` 只保护 trap 本身）→ 后端按 "canonical attempt is missing a Task terminal" 记 `protocol_error`（`backend/app/core/worker_results.py:526-529`），成功任务被标记失败。
- **最小动作**：`events.py` 增 `--payload-stdin`（`main()` 里 `json.loads(sys.stdin.read())`，~4 行）；`common.sh:17-24` 的 `codify_emit_event` 与 4 个 adapter 的 `_emit` 改为 `input=payload` 传 stdin（各 1 行）。无 payload 大小上限、无截断、无共享常量、无临时文件
- **验证**：**未在 Linux 容器内实测**（本机 darwin 的 `ARG_MAX=1 MiB`、单参数上限更高，400 KB 参数仍成功，故本地无法复现 E2BIG）；结论基于内核常量 + 调用链静态推理。`check=True`/无兜底、errexit-in-trap 两项已分别读码与本机实验证实。

### RUN-04 `bridge.py` stub 的 30s 超时与其自身文档/真实 ACK 语义矛盾（当前无生产调用方）
- **判定**：DEFER
- **位置**：`deploy/worker-entrypoint/harness/bridge.py:24,57-70`（提交 `cbad9e56`）
- **证据**：`try_dispatch` 用 `subprocess.run(..., timeout=30)`（`:64`）并只处理 `returncode != 0` 与 JSON 解析失败；`subprocess.TimeoutExpired` 未被捕获会逸出函数，与模块 docstring「Outcome `status` is one of `ack` | `reject` | `unknown`」「Real adapters replace the *body*, never the frame contract」相矛盾。真实控制面的 ACK 到 owner 的下一个 turn 边界才产生：客户端 socket 超时 1830 s（`control_client.py:33`）、owner 窗口 1800 s、pump 结果轮询 1860 s / 外层 1890 s（`worker_command_pump.py:51-69`）。另 `CONTROL_CLIENT = "control_client.py"`（`:24`）是相对路径，`sys.executable` + 相对路径要求 cwd == harness 目录。
- **影响**：现网无调用方（仅 `backend/tests/unit/test_control_client.py:142-155` 以模块方式 import 做 capability 断言），因此今天无功能影响；但该文件随 Runtime Bundle 进入容器，且是 `open-harness-v2-phase1-design.md §2.4` 指定的 Bridge 控制端点，任何按文档接线的人都会在每个 `steer` 上撞 30 s 超时并把异常抛出（而非按契约返回 outcome）。
- **最小动作**：顺手 3 行：捕获 `TimeoutExpired` → `{"status":"unknown",...}`；`CONTROL_CLIENT` 用 `Path(__file__).with_name(...)` 绝对化。或从 bundle 删掉该 stub（更懒）
- **验证**：已实际验证（读码 + 与 `control_client.py`/`worker_command_pump.py` 常量比对）；未运行 `bridge.py`。

### RUN-INFO-02 timeout marker 与 `run.completed` 的窄竞态会让终态事件携带 `failure.kind=timeout`
- **判定**：DEFER
- **位置**：`deploy/worker-entrypoint/harness/events.py:258-273`、`deploy/worker-entrypoint/harness/common.sh:372-377`（提交 `cbad9e56`）
- **证据**：`events.py:258-273` 对 `HARNESS_TERMINAL_TYPES | TASK_TERMINALS` 一律注入 `failure={kind:"timeout",…}`（只对 `run.failed` 改写 `status/success`）；实测 marker 存在时 `run.completed` 被写成 `{"status":"completed","success":true,"failure":{"kind":"timeout",…}}`。而 `common.sh:372-377` 选择 `run.completed` 的判据是 `exit_code==0 && CODIFY_CANCELLED!=1 && 存在 harness.completed`，**不看 marker**；`codify_harness_ensure_result` 却在 marker 存在时把归档 result 改写为 `status=failed / failure.kind=timeout`（`common.sh:54-73`）。
- **影响**：只有「marker 写入落在 `ensure_result` 与 `run.completed` 之间（毫秒级窗口）」时才出现「task 记 COMPLETED 而归档 result 记 timeout」的观感不一致；后端还有 `exit_code`/`finalization exit_code` 与 v2 result 两道校验兜底（`worker_results.py:530-541`），未发现数据损坏或错误投递，故仅登记待确认。
- **最小动作**：不动；若日后统一判据，`run.completed` 分支加 1 行 `codify_harness_timeout_requested` 判断
- **验证**：已实测事件注入行为（构造 `.codify-timeout` 后发 `run.completed`）；竞态本身未在容器内复现。

### RUN-INFO-04 双次初始化会启动第二个 model proxy，第一个 PID 被覆盖后泄漏
- **判定**：DEFER
- **位置**：`deploy/worker-entrypoint/harness/runner.sh:58,285,327`、`deploy/worker-entrypoint/main.sh:4-11`（提交 `cbad9e56`）
- **证据**：`main.sh:4-11` 在第一次 `codify_harness_initialize` 失败后会调用 `codify_harness_run`，而后者内部再次 `codify_harness_initialize`（`runner.sh:106`）；去重标记 `CODIFY_HARNESS_INITIALIZED=1` 只在函数**末尾**置位（`runner.sh:91`）。若失败点位于 `codify_model_proxy_start`（`:58`）之后（如 `adapter_prepare_config`/`adapter_materialize_skills`/`adapter_build_command` 失败），第二次初始化会再起一个 proxy 并覆盖 `CODIFY_MODEL_PROXY_PID`（`:285`），第一个 proxy 不再被 `codify_model_proxy_stop` 引用。
- **影响**：容器剩余生命周期内保留一个 loopback 监听进程（容器随后即退出，实际影响很小）；不会串号（两个代理都读同一份冻结 options 与同一 upstream）。
- **最小动作**：`codify_model_proxy_start` 开头加 `[ -z "${CODIFY_MODEL_PROXY_PID}" ] || return 0`（1 行）
- **验证**：读码推导；未在容器内制造 init 失败场景。

### RUN-INFO-05 [V1 遗留] `append_runtime_event` 是无锁直写 `event.jsonl` 的残留助手，已无调用方
- **判定**：DEFER —— 仅清理价值
- **位置**：`deploy/worker-entrypoint/runtime.sh:16-21`（本 patch 未改动该文件）
- **证据**：全仓 grep（含 `backend/`、`scripts/`、`docs/`）只有定义处 `runtime.sh:16`，另有已归档设计文档出现；V2 全部事件改为 `events.py`（flock + 由流推导 seq + fsync），复用该助手会绕过锁与 seq 规则。
- **影响**：当前无影响（死代码）；属「V2 取代后遗留」的锁外写入埋点。
- **最小动作**：清理时一并删 `runtime.sh:16-21`
- **验证**：已全仓 grep 确认无调用方。

### RUN-03 控制客户端文本上限用码点计数，与冻结契约的 UTF-16 单位不一致
- **判定**：ACCEPT/CLOSE —— 内网可信同事场景，无需字节级契约对齐
- **位置**：`deploy/worker-entrypoint/harness/control_client.py:69-74`（提交 `cbad9e56`）
- **证据**：worker 侧 `if len(text) > 4000` 按 Python 码点计数；冻结契约按 **UTF-16 code unit** 计数并额外拒绝孤立代理：`command_text_utf16_code_units(t) = len(t.encode("utf-16-le")) // 2`、`is_valid_command_text()`（`backend/app/core/harness_protocol.py:657-690`），错误码 `payload_too_large`。含 emoji/增补平面字符时同一字符串在两侧判定不同（4000 码点最多 8000 单元）；孤立代理（`\ud800`）worker 侧放行、backend 侧拒绝。
- **影响**：正常路径不可达 —— 命令在写入/派发前已由 backend `validate_command` 拒绝（`harness_protocol.py:744-748`），因此不改变对外行为；只有绕过 pump 直接 `docker exec` 调用 `control_client.py`（运维/调试）时，超限 frame 会被判为可投递并回 `ack`。属 defence-in-depth 与冻结契约漂移。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：已实际验证（两侧实现读码 + 计数差异可直接推导）；未构造真实 frame 投递。

### RUN-INFO-01 worker 侧 `sanitize()` 词表落后于 backend 同一用途的清洗器（未证明可造成 V2 新增可见泄露）
- **判定**：ACCEPT/CLOSE —— 能读归档者本就有仓库/网络权限，属画像降权风险
- **位置**：`deploy/worker-entrypoint/harness/adapters/sanitize.py:25-60`（提交 `cbad9e56`）
- **证据**：实测 `sanitize.sanitize()`（`python3` 直接 import）：`AIzaSy…`、`ghp_…`、`hf_…`、`xoxb-…` 原样返回；`sk-or-v1-…`/`sk-proj-…`/`glpat-…`/Bearer/`api_key=` 正常替换。backend 对同类凭据有更全的清单：`AIza`/`ghp_`/`hf_`/`xox[baprs]-`/`PRIVATE-TOKEN`（`backend/app/core/worker.py:134-140`）。events.py 的 console 预览同样只经 worker 侧清洗器（`events.py:97-115,236-243`）。
- **影响**：未能证明 V2 引入新的用户可见泄露 —— 投影到 `TaskLog` 时会再过 backend 的 `sanitize_sensitive_data`（`worker_event_projector.py:693-716`），`task_failure_details._clean_fragment` 同样用 backend 清洗器（`task_failure_details.py:57-66`），而 `console.log`（→ `TaskRawLogChunk` 原样入库，`task_log_payloads.py:33-52`）自 V1 起就是 CLI 原始输出的未脱敏镜像。残留面是归档的 canonical event 流本身（`event.jsonl` / `harness-events/*.jsonl`）会保留这四个前缀；与 13-security 专题可能重叠，此处仅登记一致性缺口。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：已实际验证清洗器输入/输出；未验证任何界面是否会展示这四个前缀。

### RUN-INFO-03 `CODIFY_HARNESS_MODEL_PROTOCOLS` 逗号切分未 trim（当前不可达，但会 fail closed）
- **判定**：ACCEPT/CLOSE —— 无需为「未来有人写空格」保持契约级严格性
- **位置**：`deploy/worker-entrypoint/harness/events.py:335-338`、`deploy/worker-entrypoint/harness/common.sh:99-104`、`deploy/worker-entrypoint/harness/adapters/result_builder.py:52-55`（提交 `cbad9e56`）
- **证据**：三处都是 `p.strip()` 只用于**过滤空元素**、不回写元素；实测 `CODIFY_HARNESS_MODEL_PROTOCOLS="anthropic_messages, openai_responses"` → 事件 `harness.model_protocols = ["anthropic_messages"," openai_responses"]`。后端 `_validate_v2_harness` 要求每个元素 ∈ `MODEL_PROTOCOLS`，否则整个事件被拒（`harness_protocol.py:321-336`）。
- **影响**：当前不可达 —— 唯一写入方是各 adapter，均不含空格（`pi.sh:113-125` / `opencode.sh:200-212` 的 `join(",")`、`claude.sh:121`、`codex.sh:118`），且该 env 是保留键、Profile 无法注入（`worker_environment_variables.py:43`）。属未来改动踩坑点（事件与 result 两处必须同步 trim，否则 attempt 内 identity 校验会拒绝后续所有事件）。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：已实测（构造含空格的 env 后读事件 JSON）。

## 3. 逐项核查记录

| # | 不变量/契约（对应任务清单项） | 结论 | 依据 |
|---|---|---|---|
| 1 | manifest schema 自洽：`schema/maturity/contract_version/event_schema/command_schema/result_schema/adapters/files` 齐全（清单 1） | 通过 | `manifest.json:1-8,132`；后端 `validate_manifest` 要求同一集合（`harness_protocol.py:757-790`）；`files: []` 是**模板**，绑定时被替换为受控源清单（`worker_runtime_bundle.py:439-475`），容器侧逐条校验 size/sha256 并要求 `entrypoint.sh` 在册（`entrypoint.worker.sh:18-60`） |
| 2 | manifest 各 harness 的 control transport / model protocols 与代码实现、后端 allowlist 一致（清单 1） | 通过 | `manifest.json:22-28,51-56,81-86,113-118` vs `HARNESS_PROTOCOL_MATRIX`（`harness_protocol.py:635-646`）逐项相同；adapter 侧导出同值（`claude.sh:117-121`、`codex.sh:114-118`、`pi.sh:121-125`、`opencode.sh:206-212`） |
| 3 | manifest 各 harness 的 capabilities 与运行时消费一致（清单 1） | **不通过 → RUN-01（FIX_NOW）** | `manifest.json:29-35` vs `runner.sh:194-200`、`codegraph.sh:73-79`；后端只认 5 键（`harness_protocol.py:647-649,836-843`） |
| 4 | manifest 不暴露不该暴露的字段（清单 1） | 通过 | 对外 catalog 只投影 key/display_name/support_tier/control_transport/model_protocols/capabilities/options_schema（`harness_registry.py:463-497`），`source.repository`/`artifact_sha256`/宿主路径不外泄；`_current_manifest()` 只读该文件（`harness_catalog.py:271-289`） |
| 5 | adapter 版本冻结值 == adapter 运行时自报版本（否则 `codify_harness_initialize` fail hard） | 通过 | 四个 adapter 的 `*_adapter_metadata` 都取 `.version // .adapter.version`（`claude.sh:44`、`codex.sh:43`、`pi.sh:33`、`opencode.sh:34`）；launcher manifest 把嵌套版本拍平到顶层 `version`（`worker_runtime_bundle.py:555-576`），后端注入 `CODIFY_ADAPTER_VERSION` 时读的是嵌套 `adapter.version`（`worker_profiles.py:1004-1024`），两者同值 |
| 6 | 唯一 task terminal：`worker.finalization` 只出现一次、其后紧随唯一 `run.completed`/`run.failed`（清单 2） | 通过（实测） | `events.py:296-320` 的 5 条规则；实测：`harness.completed` 先于 `run.started` → 拒；`delivery.*` 先于 harness terminal → 拒；`worker.finalization` 先于 harness terminal → 拒；第二个 `harness.completed`/`harness.failed` → 拒；task terminal 之后任何事件 → 拒；seq 实测 1,2,3,4 连续 |
| 7 | delivery 严格在 harness settled 之后（清单 2） | 通过 | `events.py:305-308` 强制 `delivery.*` 需见 harness terminal；`main.sh:56` 只在 `codify_harness_run` 返回 0 时 `codify_harness_mark_delivery_started`，而 `runner.sh:184` 把「exit 0 但存在 `harness.failed`」强制降为 1 |
| 8 | 「有且仅有一个 task terminal」在异常路径同样成立（清单 2） | 通过（除 RUN-02(b) 的 emit 失败路径） | `common.sh:302-320` 在 `CODIFY_HARNESS_TERMINAL_SEEN==0` 时按 timeout/cancelled/protocol_error 补唯一 `harness.failed`；`bootstrap.sh:323` 单次 EXIT trap 调用 finalizer（`bootstrap.sh:313-315` 带 `|| true`）；`events.py:296-297` 拒绝在 task terminal 后追加 |
| 9 | 控制通道 framing：frame_version/类型/门禁词表两端一致（清单 3） | 通过 | `control_client.py:24-31,53-60` vs `worker_command_pump.py:51`（`CONTROL_FRAME_VERSION="1"`）、`harness_protocol.py:657`（`{steer,follow_up}`）；门禁 `accepting/starting/closing` 与 DB 词表（`models.py:620-672`、`task_command_gate.py:21-22,100`）一致；`close` 帧只在 `closing` 下转发（`control_client.py:57-60`） |
| 10 | 控制通道超时/重试/错误码层级自洽（清单 3） | 通过 | owner 1800 s < client socket 1830 s（`control_client.py:28-33`）< pump 结果轮询 1860 s < 外层 1890 s（`worker_command_pump.py:55-69`）；`retry`（owner socket 不存在）由 pump 显式分支处理并保留队首（`worker_command_pump.py:773-777`），不会被静默丢弃；`control_request_id` 回显用于防止旧结果被误认（`control_client.py:120-124` vs pump `:367-372`） |
| 11 | `dispatching → delivered/rejected/outcome_unknown` 语义：worker 不发明状态、状态只由 pump CAS 写（清单 3） | 通过 | worker 侧只回 `ack/reject/unknown/retry`（`control_client.py:36-127`、`pi_owner.py:309-384`）；DB 迁移只由 pump 触发（`worker_command_pump.py:714-790`）；projector 对 `control.*` 事件只写 TaskLog，明确不写回 command 行（`worker_event_projector.py:702-730`） |
| 12 | 控制端点鉴权边界（清单 3「loopback token?」） | 通过（OS 权限替代 token） | Pi owner socket 以 `0o600` 建在 `/tmp/codify-pi-<task_id>.sock`（`pi_owner.py:414`），owner 以 root 运行，未提权的 workspace 用户无法连接；socket 路径两端一致（`runners/pi-run.sh:52,60` vs `control_client.py:85`） |
| 13 | shell 健壮性：命令替换失败传播、未定义变量、路径引号（清单 4/8） | 通过 | `runner.sh:35,47-48,58-61` 的 `$(…) || return 1`、`${VAR:-}` 缺省、`common.sh:17-24` 的引号完备；`main.sh`/`bootstrap.sh` 均以 `set -e` 进入 EXIT trap（本机实测 trap 内 errexit 生效）；两文件逐行检查未发现未加引号的路径/通配符展开 |
| 14 | 进程 reap 与 trap 清理（清单 4） | 通过 | adapter 以 `&`+`wait` 启动（`runner.sh:134-140`）以让 TERM 立即生效；model proxy 的 stop/kill/wait 有界（`runner.sh:322-341`）；proxy 在 console tee 排空**之前**停止（`bootstrap.sh:301-317` 顺序），避免 FIFO writer 拖死归档 |
| 15 | 事件写出：seq 分配、并发写、原子追加、权限（清单 5） | 通过 | seq 由**流本身**推导（`events.py:279-296,340-348`）+ `flock(LOCK_EX)` 包住「读全量→校验→追加→flush→fsync」（`events.py:277-362`）；`.event.lock` 在初始化时按需重置（`runner.sh:75-79`）；事件文件 root:root 0644、写者均为 root（`bootstrap.sh:107-125`），`opencode_events.py:327-352` 以 `LOCK_SH` 判定流已封口 |
| 16 | 非法 JSON / 超长行处理（清单 5） | 通过（fail closed，符合契约） | `events.py:290` 对不可解析行抛错（不静默跳过）；`opencode_events.py:327-352` 把「部分尾行」当未封口处理；`common.sh:26-31` 的 `codify_event_type_exists` 在解析失败时退化为「不存在」，由 `ensure_result` 合成 canonical result（`common.sh:46-155`） |
| 17 | V2/V1 兼容：schema 与 harness 信封按契约切换（清单 5） | 通过 | `events.py:320-347`（V2 才加 `control_transport`/`model_protocols`，`CODIFY_EVENT_SCHEMA` 可覆盖）、`result_builder.py:19-27,46-55`、`common.sh:46-155`（V1 扁平 / V2 嵌套）；与 `validate_result_v2` 的 required 集合一致（`harness_protocol.py:571-614`） |
| 18 | `result_builder` 与 `events.py` 的 harness 块取值一致（清单 7） | 通过 | 两处默认值一致（`kind` 默认 `rpc_stdio`、`protocol` 缺省 null、`model_protocols` 同切分规则）：`result_builder.py:46-55` vs `events.py:332-338` |
| 19 | result 字段完整性 vs projector/校验器期望（清单 7） | 通过 | `codify_harness_ensure_result` 合成的 V2 result 含 schema/status/success/result/harness/session_id/model/usage/failure/capability_warnings（`common.sh:106-155`），满足 `validate_result_v2`（含 `success == (status=="completed")` 与「成功不得带 failure」）；`harness.cli_version` 与事件信封不会分歧（adapter 在 `run.started` 之前就设好 `CODIFY_CLI_VERSION`，`claude.sh:69-88`） |
| 20 | 清洗失败是否 fail closed（清单 6） | 通过 | 预览路径整体包 try/except，失败不影响事件写入（`events.py:236-243`）；`sanitize()` 为纯正则替换，无失败模式 |

## 4. 局限与未验证项

- **无容器/无 CLI**：本机没有 Docker、没有 Claude/Codex/Pi/OpenCode CLI，也没有 Runtime Bundle 归档，因此没有任何一条路径是在真实容器内跑通的；所有 adapter↔runner 交互结论来自读码 + 契约常量对照。
- **RUN-02 未在 Linux 实测**：`MAX_ARG_STRLEN` 数值（≈128 KiB on 4 KiB pages）基于内核常量推导，本机（darwin，`ARG_MAX=1 MiB`、单参数上限更高）无法复现 E2BIG；16 KiB 页的 Linux 触发阈值更高但依然存在（且 `ARG_MAX` 总量 2 MiB 仍是另一道上限）。建议在 Linux 容器内用 200 KiB payload 直接复现：`python3 events.py message.completed --payload "$(python3 -c 'print("x"*200000)')"`。
- **重复 TERM/trap 语义**：已在本机 bash 3.2 实测「handler 内 `trap - TERM` 后连续 TERM 不会打断脚本」，但容器使用 Kit 自带 bash 5.x，未验证；`bootstrap.sh:258-261` 注释声称「重复 TERM 不得中断 finalizer」，实现是 `trap - TERM INT`（恢复默认处置）而非 `trap '' TERM INT`（忽略），在 bash 5 上是否等价未验证 —— 若不等价，第二次 TERM（用户重复取消 / docker stop 重试）可能在 finalizer 中途终止 shell 并丢掉 task terminal。建议单独确认。
- **RUN-INFO-03 的前提**（`CODIFY_HARNESS_MODEL_PROTOCOLS` 不含空格）由当前四处写入方保证，无运行时断言；若后端将来改为注入 manifest 全量列表，RUN-INFO-03 会立即变成 fail-closed 的事件拒收。
- **未运行任何测试**（按要求未执行全量 pytest/vitest/构建）；§3 中「实测」均为只读的一次性脚本实验（`events.py` 写临时目录、jq 判定、`sanitize` 直接 import、bash 信号语义），未改动仓库任何文件。
- adapter 侧是否存在 `_TOOL_OUTPUT_MAX_CHARS` 之外的 input 上限由 03/04/05/06 专题覆盖；RUN-02 的触发面可能被那些专题进一步收窄或扩大。
