# Open-Harness V2 Code Review —— 问题汇总与修复优先级

> 审查日期：2026-09-12 · 审查目标：`dev @ cbad9e56` · 基线：`8081c946^` = `7b253fbf`（2026-08-20）
> 范围：`git diff 8081c946^..HEAD` —— 477 commits / 437 files / +74,905 −3,855（open-harness v2 全部改动）
> 明细见同目录 17 份专题文档；分级标准与审查契约见 [README.md](README.md)，进度见 [PROGRESS.md](PROGRESS.md)。

## 1. 总体结论

V2 的架构落地质量高于“内部预览”的常见水平：协议分层、唯一终态、幂等 receipt、命令状态机、Kit 制品
fail-closed、迁移单头线性、硬切门禁（`HARNESS_EXECUTION_MODE` 必须显式配置）都已实现并有真实 PG /
真实容器证据支撑；前端无 XSS 回归，也未发现 V2 引入的数据损坏或越权。

但**交付前的收口不足**，问题集中在两类：

1. **契约两侧不一致**（生产者 / 消费者、写入 / 读取、Backend / Worker 的字段与词表），后果多为静默降级
   或“本该 409 的门禁不生效”，且现有测试因 mock 掉了一侧而全绿；
2. **拒绝 / 失败 / 大负载等异常路径**只做了一侧实现（Pi 的 rejected ACK、OpenCode 的 abort 形状、
   Codex 的 terminate、超 128 KiB 的事件负载），异常路径的终态与归档因此不可信。

这些缺陷不会让“正常成功路径”出错，但会让**失败被误报为成功、成功被误报为失败、配置静默不生效**，
正好覆盖 V2 需要被信任的那部分能力。建议按 §8 的批次收口后再执行 Pi 默认切换与 `v2_only` 硬切。

## 2. 分级统计

### 2.1 各专题原始计数（与各文档 §1 一致）

| 文档 | 专题 | 问题总数 | P1 | P2 | P3 | INFO | 主要作者 |
|---|---|---:|---:|---:|---:|---:|---|
| 01-command-plane.md | 命令平面与并发门禁 | 13 | 0 | 4 | 3 | 6 | T01 |
| 02-event-contract.md | 事件契约与投影 | 10 | 1 | 4 | 1 | 4 | T02 |
| 03-pi-bridge.md | Pi Bridge 与事件 | 15 | 3 | 1 | 4 | 7 | T03 |
| 04-opencode-bridge.md | OpenCode Bridge 生命周期 | 6 | 1 | 1 | 1 | 3 | T04 |
| 05-opencode-events.md | OpenCode 事件映射 | 10 | 1 | 4 | 1 | 4 | T05 |
| 06-claude-codex.md | Claude/Codex V2 迁移 | 6 | 0 | 1 | 2 | 3 | T06 |
| 07-runner-infra.md | 公共 Runner/Bridge 基础设施 | 9 | 2 | 0 | 2 | 5 | T07 |
| 08-runtime-bundle.md | Runtime Bundle/Registry/Options/Readiness | 7 | 1 | 1 | 2 | 3 | T08 |
| 09-worker-kit.md | Worker Kit 制品与校验 | 14 | 0 | 2 | 6 | 6 | T09 |
| 10-model-endpoints.md | Model Endpoint/Provider/请求选项代理 | 6 | 0 | 2 | 2 | 2 | T10 |
| 11-delivery-lifecycle.md | Git 交付与任务生命周期/Scheduler | 7 | 0 | 1 | 4 | 2 | T11 |
| 12-frontend.md | 前端任务执行与交付 UI | 10 | 0 | 3 | 3 | 4 | T12 |
| 13-security.md | 安全与凭据（横切） | 9 | 0 | 2 | 4 | 3 | T13 |
| 14-migrations-models.md | 迁移与数据模型 | 6 | 0 | 0 | 2 | 4 | T14 |
| 15-deploy-ops.md | 部署与离线包 | 17 | 2 | 8 | 1 | 6 | T15 |
| 16-tests.md | 测试质量与覆盖 | 18 | 1 | 7 | 5 | 5 | T16 |
| 17-cross-cutting.md | 横切补充（入口/配置/脚本/卫生） | 7 | 0 | 0 | 5 | 2 | Main |

原始合计：**170 条**（P0 0 / P1 12 / P2 41 / P3 48 / INFO 69）。

### 2.2 归并去重后（跨专题重复只记一次）

| 等级 | 数量 | 说明 |
|---|---:|---|
| P0 阻断 | 0 | 未发现数据损坏、越权、不可恢复迁移或唯一终态被破坏 |
| P1 高 | 10 | 见 §3；建议发布前全部处理或书面接受 |
| P2 中 | 38 | 见 §4；排期修复 |
| P3 低 | 48 | 见 §5；顺手修 |
| INFO | 69 | 各文档 §2 末尾；仅记录观察 |
| **唯一问题合计** | **165** | 170 减去 5 组跨专题重复 |

5 组重复（同一根因被两个专题独立发现，已合并）：

| 组 | 主条目 | 重复条目 | 归并后等级 |
|---|---|---|---|
| 1 | PI-01（03） | EVT-02（02） | P1 |
| 2 | PI-03（03） | RTB-02（08） | P2（T03 记 P1，Main 按“静默不生效、无功能失败”下调） |
| 3 | OPS-02（15） | SEC-02（13） | P1 |
| 4 | OPS-03（15） | TST-01（16） | P2（T16 记 P1，Main 按“仅测试栈、无生产影响”下调） |
| 5 | OCE-05（05） | EVT-06（02） | P2 |

## 3. P1 清单（10 条，含 Main 独立复核）

### OHV2-P1-01 原生拒绝 ACK 产出的 canonical 事件不合法，整条事件流永久卡死
- **来源**：PI-01（`03-pi-bridge.md`）≈ EVT-02（`02-event-contract.md`）；连带 EVT-03
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi_events.py:603-613`、`pi_owner.py:356-361`、
  `backend/app/core/harness_protocol.py:340-354`、`backend/app/core/worker_event_projector.py:770-789`
- **证据**：生产者从 owner 注入的 ack 元数据取 `rejection_message`，而元数据只含
  `command_id/sequence_no/payload_digest/_delivered_at` → 恒为 `null`；V2 校验器要求该字段必须是 `str`
  且 `rejection_code` 必须在枚举内；projector 在**游标推进前**整块校验，任一条非法即 rollback 到同一字节
  偏移，`poll_task_artifacts` 每 2 秒重读同一记录 → 永久卡死，`agent_settled` 投影不到，`begin_control_drain`
  不执行，gate 停在 `accepting`，pump 不发 `close`，最终以 `protocol_error: missing a Task terminal` 失败。
  **Main 复核**：三处代码逐行确认（生产者默认值 `delivery_outcome_unknown`、owner 元数据键集合、校验器
  的 `isinstance(..., str)` 断言）。
- **影响**：任何被 Pi 原生拒绝的 steer/follow_up，都会让一个本来成功的长任务失败且改动不交付。
- **建议**：① 生产者用公共映射兜底补齐 `rejection_code/rejection_message`；② ingest 对审计类事件
  （`control.*`、`agent_settled`）降级为 diagnostic 且**保证游标推进**，canonical 不变量仍 fail closed；
  ③ 补一条“非法审计记录不得阻塞终态”的回归测试。

### OHV2-P1-02 OpenCode abort/error 形状被按成功收敛
- **来源**：OCE-01（`05-opencode-events.md`）
- **位置**：`deploy/worker-entrypoint/harness/adapters/opencode_events.py:1346-1352`（error 分支只关闭
  reasoning）、`:1533-1586`（`session.idle` 成功门）
- **证据**：probe 记录的中止形状是 assistant 消息 `error:true` 且 `session.error` **未复现**
  （`docs/harness-probes/v2/opencode/README.md`「Abort」行与末尾“未复现”清单）；error 分支不置
  `terminal_failure/aborted`，随后 `session.idle` 通过成功门 → 写出 `harness.completed` + `success=true`，
  并携带被中断的部分文本进入交付。
- **影响**：非用户取消来源的中断以成功走完 commit/push/MR，失败被误报为成功。
- **建议**：error 分支置 `terminal_failure`/`aborted` 并在 idle 收敛；或记录 `errored_message_id`，
  idle 时若它仍是最后一条 assistant 消息则收敛为失败。**复核**：Main 已确认代码路径与 probe 证据一致；
  端到端需真实 Server（本次未运行）。

### OHV2-P1-03 OpenCode 状态兜底使用了制品中不存在的路由
- **来源**：OCB-01（`04-opencode-bridge.md`）
- **位置**：`deploy/worker-entrypoint/harness/adapters/opencode_bridge.py:584-586`（消费点 `:806-880`、
  `:1248-1251`）
- **证据**：代码发 `GET /session/{id}/status`；固定制品 `deploy/worker-cli/opencode/opencode`（1.18.19）的
  路由集只有集合级 `/session/status`，**没有** per-session status（**Main 复核**：直接从二进制抽取
  `/session/...` 路由表比对；同函数 docstring 写的正是「poll GET /session/status」）。
- **影响**：SSE 断线 / 流提前结束的“恢复真实状态”路径必然 404 → 分类为 `engine_error` → 已 idle 的回合被
  报为失败，与文档承诺的恢复语义相反（server 已死的分支不受影响）。
- **建议**：改查集合路由并按 `sessionID` 取子文档；`_http_path_template`/`_http_operation` 同步补该模板。

### OHV2-P1-04 manifest capability 词表收窄导致 run_text / codegraph 静默失效
- **来源**：RUN-01（`07-runner-infra.md`）
- **位置**：`deploy/worker-entrypoint/harness/manifest.json:29-35`（claude）、`:90-96`（pi）；消费方
  `harness/runner.sh:194-200`、`worker-entrypoint/codegraph.sh:73-79`、`main.sh:155,235`
- **证据**：V1 基线 manifest 为 claude 声明 `run_text: true, codegraph: true`；V2 manifest 只保留
  `resume/task_skills/usage_tokens/steering/follow_up`（**Main 复核**：`git show 8081c946^:…/manifest.json`
  对比 HEAD，并用 `jq -e '.[$k]==true'` 复现 exit 1）；而 `codify_harness_run_text()` 仍要求该键为 true，
  `claude_adapter_run_text` 实现也仍然存在。
- **影响**：默认 harness（claude）的 commit message / MR summary 恒走硬编码兜底文案；Profile 打开
  CodeGraph 也被静默停用（打印“unsupported by the frozen Harness Adapter”）。
- **建议**：判定改为“adapter 是否导出该能力”（如 `declare -F adapter_run_text`），保持单一词表。

### OHV2-P1-05 canonical 事件 writer 只能经 argv 传 payload，超 ~128 KiB 整条链路失败
- **来源**：RUN-02（`07-runner-infra.md`）
- **位置**：`deploy/worker-entrypoint/harness/events.py:369-376`、`harness/common.sh:17-24`、四个 adapter 的
  `subprocess.run([... "--payload", json.dumps(payload)])`
- **证据**：writer 唯一入口是 `--payload`（argv）；Linux 单参数上限 `MAX_ARG_STRLEN = 32 × PAGE_SIZE`
  （≈128 KiB）→ `E2BIG`；payload 侧无上限（`tool.started.input` 可含整份文件内容、`git_delivery.commits`
  无界收集）。同仓库 `runners/claude-run.sh:875-877` 已因 “hits OS ARG_MAX limit” 改用 `--slurpfile`
  （**Main 复核**：events.py 与 common.sh 的调用路径确认）。
- **影响**：adapter 侧 translator 直接死亡 → 不写 `CODIFY_HARNESS_RESULT_FILE` → `harness.failed` →
  **已完成的代码改动不提交、不推送、不建 MR**（写大文件是完全常规行为）；shell 侧 finalizer 内 emit 失败
  会中断 finalization。
- **建议**：增加 `--payload-file`/stdin 入口（shell 用 mktemp 落文件），并对大字段设统一上限与截断标记。
- **未验证**：本机 darwin 无法复现 `E2BIG`，结论基于内核常量 + 调用链静态推理。

### OHV2-P1-06 readiness 作用域“写入用 A、读取用 B”，创建门禁不生效
- **来源**：RTB-01（`08-runtime-bundle.md`）
- **位置**：读 `backend/app/core/worker_runtime_readiness.py:229-237`（`profile_requires_content_inventory`）
  vs 写 `backend/app/api/worker_profiles.py:845-846`（`requires_v2_identity = bool(eligible_v2_harness_keys(profile))`）
- **证据**：读侧要求 `profile.harness_runtimes[key]["contract_version"] == "codify.worker.harness/v2"`，
  而该字段默认 `'{}'`（迁移 064 默认、API 原样落库、前端从不下发）→ 读到的是**从未写入的裸 locator 作用域**，
  恒为 `unknown`；写侧按“全部 enabled harness”判定为内容清单作用域。**Main 复核**：两侧函数与默认值已逐行确认。
- **影响**：Kit 随后消失 / CLI 被标 `absent` 时，§16.3 要求的 `409 worker_runtime_unavailable` /
  `harness_cli_unavailable` 不触发（任务先 201 创建、后由 Scheduler 门禁 park/失败）；公开 catalog 在成功
  校验后仍对 Harness 报 unknown。
- **建议**：读侧改用同一判定（或 v2_only 下只保留单一严格作用域），并补“写 unavailable 后 create_task 必须 409”测试。

### OHV2-P1-07 git 历史仍含真实凭据，HEAD 清理不等于吊销
- **来源**：OPS-02（`15-deploy-ops.md`）≈ SEC-02（`13-security.md`）
- **位置**：`deploy/.env.test`（HEAD 已替换为占位符）；明文见 `git show 8081c946^:deploy/.env.test`
- **证据**：历史含 `glpat-*`（51 字符、32 个唯一字符）与 `32hex.16base62` 形态的 Provider key；
  `deploy/docker-compose.yml:29-30/82-83/146-147` 以 `env_file: .env.test` 引用该文件（真实部署输入而非示例）；
  `origin/dev`、`origin/codify/issue-42` 均包含该提交。**Main 复核**：只读命令取出并核对形状（未在文档中
  保留明文；13-security.md 中的明文已由 Main 脱敏）。
- **影响**：任何具备仓库读权限者（含 CI、历史 clone）可取得 GitLab bot PAT（对全部受管项目可写）与可用的
  Provider key。
- **建议**：立即轮换/吊销 → 清理历史（filter-repo 或重建仓库）；把 secret-scan 规则扩到 GitLab 新格式 PAT
  后缀与自定义 key 形态；禁止再把真实值写入被追踪的 env 文件（见 OPS-10）。
- **说明**：属 `[历史遗留]`，本区间完成的是正确的 HEAD 清理，残余风险在历史与凭据本体。

### OHV2-P1-08 离线包 `start.sh` 因必填插值变量缺失无法启动
- **来源**：OPS-01（`15-deploy-ops.md`）
- **位置**：`deploy/offline-bundle/docker-compose.yml:30`、`:79`、`:123-128`；模板 `config/.env.offline.example`
- **证据**：**Main 实测** `docker compose --env-file config/.env.offline.example -f docker-compose.yml config`
  → `rc=15`，报 `required variable MIGRATION_TARGET is missing`；该变量在模板与文档中均不存在，补上后同样
  因 `HARNESS_EXECUTION_MODE` 报错。对照 `deploy/docker-compose.yml:153` 用 `${MIGRATION_TARGET:-}` 并注释
  说明 `:?` 会破坏普通 compose 调用。
- **影响**：README/文档指示的离线部署主路径（`scripts/start.sh`）在插值阶段即失败，整栈不可启动。
- **建议**：模板/文档补齐两个键，或改为带默认值的可选插值；同步修 `Makefile:54`（缺 `--env-file`，OPS-05）。

### OHV2-P1-09 投影路径写 `task_harness_commands.status`，违反冻结的单写者契约
- **来源**：EVT-01（`02-event-contract.md`）
- **位置**：`backend/app/core/worker_event_projector.py:459-466` → `backend/app/core/task_command_gate.py:98-166`
- **证据**：契约（`implementation-plan §4.3`、`open-harness-v2.md §6.2`）明确「projector 只做审计/日志展示，
  绝不写 `task_harness_commands.status`」；**Main 复核** `close_control_gate` 确实对 `queued`/`dispatching`
  行做 `rejected`/`outcome_unknown` CAS，且同一函数也被生命周期路径调用（`task_command_gate.py:245`）。
- **影响**：出现第二个状态 writer。事件回放/归档回填可在 pump 持有 dispatch 租约期间把 `dispatching` 行
  终态化，之后真实 ACK 无法落库（被记为 `outcome_unknown`）——不会重复投递，但审计口径错误，且该不变量
  目前只靠 DB CHECK 兜底。
- **建议**：移除 projector 中的 `close_control_gate` 调用（`agent_settled → begin_control_drain` 只改 attempt
  列可保留），command 终态化只留给 pump / 生命周期入口。

### OHV2-P1-10 初始 prompt 被拒绝时不产生终态，任务挂到超时
- **来源**：PI-02（`03-pi-bridge.md`）
- **位置**：`deploy/worker-entrypoint/harness/adapters/pi_events.py:629-634`、`pi_owner.py:221-232`
- **证据**：`prompt` 响应 `success:false` 只落一条 diagnostic；PG 不产生 `agent_start/agent_settled`，
  translator 只在 stdin EOF 写 terminal，而 owner 只在 settled 后退出 → 任务挂到 `TASK_TIMEOUT`，被报为
  `harness.failed{timeout}` 而不是 `configuration_error`（上游文档：`success:false` = 在接受前被拒绝）。
- **影响**：常见的配置类错误（如 `models.json` 未写导致 “Model not found”）表现为超时，排障成本高。
- **建议**：`prompt` 拒绝即置 `terminal_failure`（配置类）并让 owner 退出；owner 顺带检查握手响应 success。

## 4. P2 清单（38 条）

| ID | 文档 | 问题 | 位置 |
|---|---|---|---|
| PI-03 / RTB-02（归并） | 03+08 | pi/v1 harness_options 被校验、冻结并计入摘要，但 worker 侧无任何消费者，thinking_level 等静默不生效 | deploy/worker-entrypoint/harness/adapters/pi.sh:206-208、backend/app/core/harness_options.py:39-43 |
| CMD-01 | 01 | command 状态 helper 的 “CAS” 判定读本会话缓存行，跨会话终态只能靠 CHECK 约束挡下 | backend/app/core/task_harness_commands.py:324-346（另 :348-378、:380-407、:409-427、:429-441、:443-467）、backend/app/database.py:29-35 |
| CMD-02 | 01 | 单 dispatcher 租约 TTL(120s) 远短于 transport/ACK 上限(1890s) 且从不续租 | backend/app/core/worker_command_pump.py:53、:57-71、:183-236 |
| CMD-03 | 01 | retry 结果无上限、无退避、无审计，队首可被无限重试并阻塞整条队列 | backend/app/core/worker_command_pump.py:773-777（另 :94-99、task_harness_commands.py:429-441） |
| CMD-04 | 01 | created_by 列宽 64 < username 上限 255，长用户名使 PUT 直接 500 | backend/app/models.py:737（对照 :1480）、backend/alembic/versions/074_open_harness_v2.py:103、backend/app/api/task_command_routes.py:69-72 |
| EVT-03 | 02 | 单条非法记录使整条事件流永久卡死，Task 被误判为缺少终态 | backend/app/core/worker_event_projector.py:770-789 |
| EVT-04 | 02 | result v2 的 raw_archive 定位字段端到端缺失，且 validate_result_v2 不校验 | backend/app/core/harness_protocol.py:571-615 |
| PI-04 | 03 | Managed Skills 被物化到 Pi 不会扫描的目录，task_skills 静默无效 | deploy/worker-entrypoint/harness/adapters/pi.sh:210-229 |
| OCB-02 | 04 | 快照凭据缺失时静默跳过 provider 配置物化 | deploy/worker-entrypoint/harness/adapters/opencode.sh:240-270 |
| OCE-02 | 05 | delta 去重按后缀比较，静默吞掉真实重复内容 | opencode_events.py:1521（legacy message.part.delta）、:777（durable session.next.text.delta） |
| OCE-03 | 05 | session.idle + 空文本回合被判 protocol_error | opencode_events.py:1559-1570 |
| OCE-04 | 05 | SSE 分片逐块解码，多字节字符被替换成 U+FFFD | deploy/worker-entrypoint/harness/adapters/opencode_bridge.py:639（event_stream；SSE 分帧健壮性属本专题，Server 生命周期结论归 04 专题） |
| OCE-05 | 05 | model 恒为 null、从不发 model.resolved | opencode_events.py:145-147（状态声明）、:1132-1133（写 result） |
| CX-01 | 06 | Claude 每个 text delta 派生一个 canonical 事件子进程，长输出任务线性变慢 | deploy/worker-entrypoint/harness/runners/claude-run.sh:212-216、deploy/worker-entrypoint/harness/adapters/claude_events.py:279-281,134-150、deploy/worker-entrypoint/harness/events.py:247,365 |
| KIT-01 | 09 | 逐 Harness bridge 自检的失败被静默丢弃，该门禁实际不生效 | deploy/worker-kit/verify-runtime.sh:195 |
| KIT-02 | 09 | 两个安装器同源漂移：文档化的离线安装路径缺少模型代理与 harness inventory 的 fail-closed 校验 | deploy/worker-kit/install.sh:120-135、:158-204 |
| MEP-01 | 10 | Backend 与 Worker 对 endpoint 快照字段的归一化不一致，带首尾空格的 Provider 配置会导致任务执行期误报"指纹被篡改" | backend/app/core/model_endpoints.py:125-129 |
| MEP-02 | 10 | provider_options 保留字段契约未覆盖 Task 创建路径：遗留行会让已冻结的保留参数被代理静默丢弃 | backend/app/api/task_creation_service.py:518-527 |
| DEL-01 | 11 | 终态失败原因被归档的 provider 错误覆盖 | backend/app/api/tasks.py:657-668（另见 :709-718） |
| FE-01 | 12 | 英文语言包缺失 config.runtimeFailureDetailsUnavailable，EN 界面显示原始 key | frontend/src/i18n/messages/en.ts:1831 |
| FE-02 | 12 | Steering 命令被拒（409/422/403）时丢弃后端 detail 对象，拒绝原因不可见 | frontend/src/components/TaskSteeringPanel.vue:224-234 |
| FE-03 | 12 | 每次发送都重新生成 command_id，传输失败后的重试会重复投递同一条指令 | frontend/src/api/tasks.ts:750-760 |
| SEC-01 | 13 | 清洗模式覆盖不全：自定义 Provider 密钥形态与 JSON apiKey 字段不被脱敏 | deploy/worker-entrypoint/harness/adapters/sanitize.py:92-108（本 patch 新增的 sanitize_json_value；相关模式表 :25-29、:36-38 未被本 patch 修改）；对照 backend/app/core/worker.py:118-122（本 patch 新增 OpenRouter 形态） |
| OPS-03 | 15 | mock 集成 compose 仍写 dual_canary，backend/scheduler 启动即崩 | backend/tests/mock_integration/docker-compose.mock-test.yml:69（另见 :113） |
| OPS-04 | 15 | E2E compose 的 migration 目标落后 4 个 revision，E2E 数据库 schema 与代码不符 | deploy/docker-compose.e2e.yml:41 |
| OPS-05 | 15 | make worker-runtime-bundle-export 未传 --env-file，文档化的 L3 导出命令直接失败 | Makefile:54 |
| OPS-06 | 15 | SCHEDULER_HEALTH_PORT 端口契约不自洽：非默认值会让 Scheduler 永久 unhealthy | deploy/docker-compose.yml:105-107 |
| OPS-07 | 15 | 离线包 maintenance migrate 绕过 run-migration-owner 的 fail-closed 守卫 | deploy/offline-bundle/docker-compose.yml:128 |
| OPS-08 | 15 | 部署文档仍把 dual_canary 写成合法值，按文档执行会启动失败 | docs/DEPLOYMENT.md:134（另见 :20、:64） |
| OPS-09 | 15 | 多 Harness 上线 runbook 仍以 dual-canary/legacy V1 overlay 为前提，回滚步骤不可执行 | docs/runbooks/multi-harness-rollout.md:34（另见 :11、:132、:211、:280、:286、§8 :259-268） |
| OPS-10 | 15 | 生产密钥仍被引导写入仓库内被追踪的 deploy/.env.test（本次仅加了「不要写」的注释） | deploy/docker-compose.yml:29-30（env_file: .env.test） |
| TST-02 | 16 | 命令平面核心断言只在"可达内网 Postgres"时执行，且无 CI 门禁 | backend/tests/unit/test_task_harness_commands.py:49-52（ADMIN_URL 默认 postgresql+asyncpg://codify:codify_password@192.168.50.129:5432/codify_test）与 :97 pytest.skip(f"command-plane DB unreachable: {exc!r}")；backend/tests/unit/test_worker_command_pump.py:36-38,83 |
| TST-03 | 16 | attempt 租约过期与属主互斥分支无任何测试 | backend/app/core/worker_command_pump.py:220-223（expires_at.is_(None) | expires_at < now | owner == owner）、:259-262（_promote_starting_attempt 同条件）、:517-530（_drop_lease 仅属主可清） |
| TST-04 | 16 | protocol_error 的"缺 init"（缺 run.started）分支无测试 | backend/app/core/harness_protocol.py:485-486（纯 replay 校验）与 backend/app/core/harness_attempts.py:199-217（DB 增量摄入） |
| TST-05 | 16 | 命令 API 没有"路由 → 服务 → DB"的集成覆盖 | backend/tests/unit/test_task_command_routes.py:1-6（文件自述"mocked DB session and patched service functions"）；服务层 backend/tests/unit/test_task_harness_commands.py（真 PG，见 TST-02 可跳过） |
| TST-06 | 16 | execute / schedule / retry 三个入口的 V1 只读门禁无测试 | backend/app/api/task_action_routes.py:418（execute）、:484（schedule）、backend/app/api/task_creation_service.py:142（retry）；对照已覆盖的 :95（cancel）与 backend/app/api/task_update_service.py:94（update） |
| TST-07 | 16 | 前端 steer 发送路径零覆盖 | frontend/src/components/TaskSteeringPanel.spec.ts:13-16（sendHarnessCommand: vi.fn()）对照 frontend/src/components/TaskSteeringPanel.vue:201-235（send()） |
| TST-08 | 16 | 非 Linux 上进程回收断言静默失效 | backend/tests/unit/test_opencode_harness_adapter.py:3230-3233（_proc_start_time 读 /proc/{pid}/stat）、:3255-3257（_assert_process_gone）、用例 :3337/:3349/:3357/:3367 |

（另有归并进 P1/P2 的跨专题重复条目：EVT-02→P1-01、SEC-02→P1-07、TST-01→OPS-03、RTB-02→PI-03、
EVT-06→OCE-05。）

## 5. P3 清单（48 条）

| ID | 文档 | 问题 | 位置 |
|---|---|---|---|
| CMD-05 | 01 | 空文本命令被 API 接受、被容器内 client 拒绝，且公开消息套用错误的 code 文案 | backend/app/core/harness_protocol.py:682-690、deploy/worker-entrypoint/harness/control_client.py:66-71、backend/app/core/task_harness_commands.py:52 |
| CMD-06 | 01 | pump 持久化 native_rejected（非冻结枚举），同一拒绝在 API 与事件流显示不一致 | backend/app/core/worker_command_pump.py:752-762、backend/app/core/task_harness_commands.py:42-59、backend/app/core/harness_protocol.py:43-54 |
| CMD-07 | 01 | _drop_lease 是死代码，租约从不显式释放 | backend/app/core/worker_command_pump.py:517-527 |
| EVT-05 | 02 | WorkerEventProjector 类 docstring 与实现不符 | backend/app/core/worker_event_projector.py:90-100 |
| PI-05 | 03 | pi_adapter_terminate 既不发原生 abort，也不作用于 Pi/owner 进程 | deploy/worker-entrypoint/harness/adapters/pi.sh:285-295 |
| PI-06 | 03 | message.delta 的 payload 键与 projector 读取的键不一致（content vs text） | deploy/worker-entrypoint/harness/adapters/pi_events.py:764-768 |
| PI-07 | 03 | 原生拒绝的审计码与实际原因不一致（native_rejected 不在拒绝码表内） | deploy/worker-entrypoint/harness/adapters/pi_owner.py:383-384 |
| PI-08 | 03 | pi_bridge.PiBridge 是死代码，且与线上 owner 的策略不同 | deploy/worker-entrypoint/harness/adapters/pi_bridge.py:77-236 |
| OCB-03 | 04 | 取消/超时路径的硬停 TERM 到不了 Harness（公共 Runner 机制） | deploy/worker-entrypoint/harness/runner.sh:134-136（adapter_run ... & / CODIFY_HARNESS_ADAPTER_PID=$!）与消费点 deploy/worker-entrypoint/harness/adapters/opencode.sh:407-445、deploy/worker-entrypoint/bootstrap.sh:269-277 |
| OCE-06 | 05 | message.delta 用 content，projector 读 text | opencode_events.py:779、:1402、:1525 |
| CX-02 | 06 | Codex 取消路径未落地：adapter terminate 空实现、runner 无信号 trap，turn/interrupt 不可达 | deploy/worker-entrypoint/harness/adapters/codex.sh:283-285、deploy/worker-entrypoint/harness/runners/codex-run.sh:32,36-50、deploy/worker-entrypoint/bootstrap.sh:258-279 |
| CX-03 | 06 | Codex App Server 的 JSON-RPC 成功响应被记为 unknown_raw_event，响应分支不可达 | deploy/worker-entrypoint/harness/adapters/codex_events.py:397-399,291-313,527-531 |
| RUN-03 | 07 | 控制客户端文本上限用码点计数，与冻结契约的 UTF-16 单位不一致 | deploy/worker-entrypoint/harness/control_client.py:69-74 |
| RUN-04 | 07 | bridge.py stub 的 30s 超时与其自身文档/真实 ACK 语义矛盾（当前无生产调用方） | deploy/worker-entrypoint/harness/bridge.py:24,57-70 |
| RTB-03 | 08 | §13.4 容器错误重探被移除后遗留不可达代码与失效文档 | backend/app/core/worker_task_lifecycle.py:756 |
| RTB-04 | 08 | 共享配置失效只递增 image generation 且不清空 worker_kit_identity | backend/app/api/worker_shared_configuration.py:378 |
| KIT-03 | 09 | LD_LIBRARY_PATH 隔离"硬门禁"可静默跳过，与文档声称的"每对 Kit+镜像都证明"不符 | deploy/worker-kit/verify-runtime.sh:221-229 |
| KIT-04 | 09 | --archive 校验容忍重复的 manifest.json 成员，导致"被校验的 manifest"与"被安装/消费的 manifest"可能不是同一份字节 | deploy/worker-kit/verify-kit-content.py:260-264 |
| KIT-05 | 09 | 归档名缺少 codify-worker-kit- 前缀仍可安装，但后端 receipt 校验要求完全一致 | backend/app/core/worker_kit_inventory.py:398-403 |
| KIT-06 | 09 | Kit 侧校验器与后端 inventory 契约宽严不一致（路径归一化 / 额外字段） | deploy/worker-kit/verify-runtime.sh:77、deploy/worker-kit/install.sh:167 对比 backend/app/core/worker_kit_inventory.py:160-237,239-260 |
| KIT-07 | 09 | 导出归档字节不可复现（gzip 头写入当前时间），同一 Kit identity 每次导出摘要不同 | deploy/worker-kit/export-archive.py:67-68 |
| KIT-08 | 09 | install.sh 的校验和工具回退不完整，无 sha256sum 的主机中途失败 | deploy/worker-kit/install.sh:45-49 与 :130,139,184 |
| MEP-03 | 10 | endpoint_transport_fingerprint() 是死代码，其 docstring 声称的"Provider 重绑定检测"没有任何调用方 | backend/app/core/model_endpoints.py:148-169 |
| MEP-04 | 10 | 重命名未覆盖用户可见术语：Provider 面板与 i18n 仍以 "Wire Protocol / Wire 协议" 展示 model_protocol | frontend/src/components/config/AIProvidersPanel.vue:77,236 |
| DEL-02 | 11 | 交付采集的软失败原因不会进入任何事件或 Task 字段 | deploy/worker-entrypoint/git-delivery.py:397-405（软错误）、:536-540（写入快照）、deploy/worker-entrypoint/main.sh:302-311、deploy/worker-entrypoint/harness/common.sh:325-328,355-358 |
| DEL-03 | 11 | task_timeout 共享 helper 未被生产代码使用，派生值在 API 内各写一遍 | backend/app/core/task_timeout.py:90-92、backend/app/core/task_timeout.py:108-110；重复实现于 backend/app/core/task_helpers.py:38-41、backend/app/api/issues.py:319-322 |
| DEL-04 | 11 | 冻结 harness options 的序列化 helper 被复制成两份 | backend/app/api/task_responses.py:41-47、backend/app/api/task_runtime_summary_routes.py:170-176 |
| DEL-05 | 11 | ci_failure_collector 调用参数意外去缩进 | backend/app/core/ci_failure_collector.py:803 |
| FE-04 | 12 | 思考耗时 tooltip 硬编码英文，未走 i18n | frontend/src/components/task-process/TaskProcessTextRow.vue:13-17 |
| FE-05 | 12 | OpenCode model_variant 输入缺少与后端一致的客户端校验，422 原因被丢弃 | frontend/src/components/TaskFormDrawer.vue:636-645 |
| FE-06 | 12 | 每秒把 nowMs 下发给每一行思考/回复行，长日志下形成 1Hz 全列表重渲染 | frontend/src/components/TaskProcessPanel.vue:314-320 |
| SEC-03 | 13 | 调度器 /health 端口默认发布到所有宿主接口 | deploy/docker-compose.yml:106-107 |
| SEC-04 | 13 | GET /api/harness-catalog 仅校验登录态，worker_profile_id 无范围约束 | backend/app/api/harness_catalog.py:369-395（新增文件，提交 cbad9e56） |
| SEC-05 | 13 | webhook 密钥轮换：DB 与 GitLab 可能永久漂移且无检测手段 | backend/app/api/project_webhooks.py:175-200（本 patch 新增 except ConfigEncryptionError 分支） |
| SEC-09 | 13 | OIDC_ENABLED=false（默认）下所有已登录用户对所有项目不受限，V2 命令平面使其升级为写权限 | backend/app/dependencies/project_access.py:95-96（未随本 patch 改动），被 V2 新端点复用：backend/app/api/task_command_routes.py:230-250 |
| MIG-01 | 14 | ORM 声明 server_default=0，但 076/077 迁移已把该默认值删除 | backend/app/models.py:1056-1058、backend/app/models.py:1067-1069 |
| MIG-02 | 14 | ORM 把 runtime_mode 默认值改为 mounted_kit，数据库默认值仍是 baked_image（无对应迁移） | backend/app/models.py:1020（WorkerProfile.runtime_mode，提交 2c3b95c7；同 commit 另改 :935 WorkerSharedConfiguration、:1270 TaskWorkerProfileSnapshot），DB 默认值来源 backend/alembic/versions/056_worker_profile_mounted_kit.py:28 |
| OPS-11 | 15 | .dockerignore 未排除 .env.*，部署密钥文件进入构建上下文 | .dockerignore:20 |
| TST-09 | 16 | 名不符实的空断言：projector 不写命令状态 | backend/tests/unit/test_harness_events_v2.py:96-105 |
| TST-10 | 16 | 四个 Kit 安装器 fail-closed 用例在非 root 下静默跳过 | backend/tests/unit/test_offline_bundle_export.py:29-31（if os.geteuid() != 0: pytest.skip("Worker Kit installation requires root")），调用点 :930、:1002、:1076 |
| TST-11 | 16 | Dockerfile / verifier 源码子串测试 | backend/tests/unit/test_worker_kit.py:858-866、:869-906 |
| TST-12 | 16 | 新增 PG 测试沿用硬编码内网库与明文口令 | backend/tests/unit/test_task_harness_commands.py:51-52、test_worker_command_pump.py:37-38、test_074_migration.py:36-37、test_worker_profile_verification_pg.py:22-23 |
| TST-13 | 16 | 075/077/078/079 迁移测试只断言 mock 的 SQL 文本 | backend/tests/unit/test_079_migration.py:21-72、test_077_migration.py:27-47、test_078_migration.py:19-36、test_075_migration.py:11-18 |
| XC-01 | 17 | 旧 task_timeout 迁移后可能超出新字段边界，导致 get_effective_settings() 抛错 | backend/alembic/versions/079_task_execution_timeout.py:30-52、backend/app/config.py:275-277、backend/app/config.py:401-406 |
| XC-02 | 17 | V1→V2 回放脚本固化的 Codex control transport 与已发布 manifest 不一致 | scripts/harness-probes/v2/replay_v2.py:44-49 对比 deploy/worker-entrypoint/harness/manifest.json |
| XC-03 | 17 | 构建/验收产物进入版本库且未被忽略 | output/playwright/task-451..459-*.png（8 个二进制，本次新增）、.vite/vitest/results.json |
| XC-04 | 17 | CLAUDE.md 与代码漂移（容器命名、迁移归属） | CLAUDE.md（容器命名 codify-{task_id}-p{project_id}-i{issue_iid}、AUTO_MIGRATE 说明） |
| XC-05 | 17 | 探针与秘密扫描脚本没有任何自动化入口 | scripts/harness-probes/v2/secret-scan.py、replay_v2.py、benchmark.sh、full-chain-driver.sh、scripts/dev-regression.sh |

## 6. INFO 汇总（69 条）

INFO 记录为“观察/建议/需人工确认”，不带缺陷判定，明细在各文档 §2（含 `### …-INFO-xx` 与 `### XX-nn（INFO）` 两种写法）：

| 文档 | 专题 | INFO |
|---|---|---:|
| 01-command-plane.md | 命令平面与并发门禁 | 6 |
| 02-event-contract.md | 事件契约与投影 | 4 |
| 03-pi-bridge.md | Pi Bridge 与事件 | 7 |
| 04-opencode-bridge.md | OpenCode Bridge 生命周期 | 3 |
| 05-opencode-events.md | OpenCode 事件映射 | 4 |
| 06-claude-codex.md | Claude/Codex V2 迁移 | 3 |
| 07-runner-infra.md | 公共 Runner/Bridge 基础设施 | 5 |
| 08-runtime-bundle.md | Runtime Bundle/Registry/Options/Readiness | 3 |
| 09-worker-kit.md | Worker Kit 制品与校验 | 6 |
| 10-model-endpoints.md | Model Endpoint/Provider/请求选项代理 | 2 |
| 11-delivery-lifecycle.md | Git 交付与任务生命周期/Scheduler | 2 |
| 12-frontend.md | 前端任务执行与交付 UI | 4 |
| 13-security.md | 安全与凭据（横切） | 3 |
| 14-migrations-models.md | 迁移与数据模型 | 4 |
| 15-deploy-ops.md | 部署与离线包 | 6 |
| 16-tests.md | 测试质量与覆盖 | 5 |
| 17-cross-cutting.md | 横切补充（入口/配置/脚本/卫生） | 2 |

## 7. 已被文档显式承认的开放项（不计入本次问题）

`docs/architecture/open-harness-v2.md §4.2`、`docs/harness-probes/v2/README.md`、R4.5/R4.6 evidence 已明确
记录为**未完成的发布边界**，本次审查不重复计为缺陷：Claude/Codex 成功 canary、四 Harness 完整发布矩阵、
Pi/OpenCode 三协议完整矩阵、Pi 20-task 质量门禁、`v2_only` hard cut 尚未完成；Phase 0 未退出；真实 Host 上
的 `linux/amd64` 制品 composition 与 DB 绑定已完成。

## 8. 修复批次建议

| 批次 | 目标 | 条目 |
|---|---|---|
| A：发布前必须收口 | 让门禁/终态在异常路径可信 | P1-01、P1-02、P1-03、P1-04、P1-05、P1-06；CMD-02（租约 TTL 120s ≪ transport 1890s）、OPS-03/TST-01（`dual_canary` 使 mock 栈全崩）、OPS-04（E2E 迁移停在 075）、OPS-05、KIT-01（bridge 自检失败被吞）、MEP-01（strip 不一致→执行期误报篡改） |
| B：发布前处理或书面接受 | 安全与运维正确性 | P1-07（凭据轮换，安全，建议立即）、P1-08、P1-09、P1-10；SEC-01、CMD-01、CMD-03、DEL-01、FE-01/02/03、OPS-06/07/08/09/10、RTB-01 同族读取方、OCE-02/03/04/05、CX-01、KIT-02、PI-04 |
| C：排期 | 可维护性与一致性 | 其余 P2 |
| D：顺手 | 卫生与文档漂移 | 全部 P3 + 需落地的 INFO |

## 9. Main 独立复核记录

| # | 复核对象 | 方法 | 结论 |
|---|---|---|---|
| 1 | PI-01/EVT-02 的 `rejection_message` 契约缺口 | 逐行读生产者/owner 元数据/校验器 | 确认 |
| 2 | OCE-01 abort 形状 | 读 error 分支 + idle 成功门 + probe README | 确认（端到端未运行） |
| 3 | OCB-01 状态路由 | 从固定二进制抽取 `/session/*` 路由表 | 确认路由不存在 |
| 4 | RUN-01 capability 词表 | 对比 V1/HEAD manifest + `jq -e` 复现 | 确认 |
| 5 | RUN-02 argv 上限 | 读 events.py 入口 + common.sh + ARG_MAX 既有注释 | 确认（未在 Linux 复现 E2BIG） |
| 6 | RTB-01 作用域不一致 | 读读/写两侧函数与默认值 | 确认 |
| 7 | OPS-01 离线包 | 实跑 `docker compose config` | 复现 rc=15 |
| 8 | OPS-02/SEC-02 历史凭据 | `git show` + 形状统计（不明文回写文档） | 确认（并已脱敏 13-security.md 中的明文） |
| 9 | OPS-03/TST-01 `dual_canary` | grep + 配置校验 | 确认 |
| 10 | OPS-04 E2E 迁移目标 | grep + alembic head（079） | 确认落后 4 个 revision |
| 11 | KIT-01 bridge 自检被吞 | 读 verify-runtime.sh 调用形态（`if ! run_one`） | 确认 errexit 被抑制 |
| 12 | CMD-01 “CAS” 非真 CAS | 依据 SQLAlchemy identity-map 语义复核 T01 推理 | 采信（跨会话终态靠 CHECK 兜底） |
| 13 | FE-01 en 缺键 / FE-03 command_id 每次重生成 | grep 两侧语言包 + 读 api/tasks.ts | 确认 |
| 14 | XC-01 严重度 | 复核 V1 写入侧 60–7200 校验 | 下调为 P3 |
| 15 | T14 的 server_default 漂移 | 采信其真实 PG 探针结论 | 采信 |

## 10. 局限与未验证项（全量汇总）

- **无真实 Harness CLI / 容器运行**：Pi、OpenCode、Claude、Codex 的制品均为 linux-x64 ELF，本机（macOS/arm64）
  无法执行；所有 worker 侧结论为静态推理 + 仓库内 probe 证据对照，未做端到端复现。
- **无 Docker 部署验证**：除离线包 `docker compose config` 外未启动服务；`SCHEDULER_HEALTH_PORT`、
  `AUTO_MIGRATE`、容器清理等结论为静态核查。
- **无 Go 工具链**：`deploy/worker-kit/model-proxy` 未执行 `go test`，Go 侧结论为源码 + 上游行为核对。
- **未跑全量测试/构建**：各专题只运行了窄范围单测（如 `test_pi_harness_adapter.py`、命令平面 PG 用例），
  未运行 `npm run build`、全量 `vitest`、全量 `pytest`。
- **未做真实 PostgreSQL 迁移**（T14 除外：其迁移结论在真实 PG 上验证过）。
- **威胁模型边界**：恶意仓库内容、恶意插件、私密 Key 泄露在本仓 `open-harness-v2.md §3` 中被显式排除在
  威胁模型外；此类观察最多记 INFO/P3。
- **未统计真实数据分布**：如 V1 库中 `provider_options` 含保留键的行数、`harness_runtimes` 为空的 Profile 占比、
  历史越界 `task_timeout` 行是否存在等，影响个别 P2/P3 的实际触发概率。
