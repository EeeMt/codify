# Open-Harness V2 Code Review —— 判定汇总与修复顺序

> 审查日期：2026-09-12 · 审查目标：`dev @ cbad9e56` · 基线：`8081c946^` = `7b253fbf`（2026-08-20）
> 范围：`git diff 8081c946^..cbad9e56` —— 477 commits / 437 files / +74,905 −3,855（open-harness v2 全部改动）
> 判定标准与部署画像：[README.md](README.md) §1.1（内网离线 / 3 人 beta / 无 SLA / 上线默认 `v2_only` 且无 canary / 上线后默认 harness 为 Pi / 唯一硬约束=历史统计数据不丢 / 反对过度防御）与 §3
> 明细见同目录 17 份专题文档；进度见 [PROGRESS.md](PROGRESS.md)。

**结果：165 条唯一问题（FIX_NOW 13 / FIX_IF_CHEAP 48 / DEFER 55 / ACCEPT-CLOSE 49）。**

## 1. 总体结论

V2 的架构落地质量高于“内部预览”的常见水平：协议分层、唯一终态、幂等 receipt、命令状态机、Kit 制品
fail-closed、迁移单头线性、执行模式收敛到 `v2_only` 都已实现，且有真实 PG、真实容器与真机任务证据；
前端无 XSS 回归，未发现 V2 引入的数据损坏或越权。

按本阶段画像判定后，**13 条需要现在动手**（其中 10 条阻断主路径或静默丢交付：Pi 成为默认 harness 后
Pi 通道的 3 条也进入主路径），**49 条属于过度防御应书面关闭**（含 canary/双轨回滚与显式硬切门禁），
其余 103 条为错误路径上的顺手项或待触发项。FIX_NOW 的共同点：改动都在个位数行、不引入任何新机制。

执行顺序：10 条主路径项 → 切库前两条 SQL → 其余单行项 → 接受清单书面关闭；各档明细见 §3~§6。

**进展**：Tier-1 的 10 条主路径项已随 `7794eb92` 修复（含 OPS-07/OPS-08 两处延伸项），每条都带复现失败—修复后通过的回归测试；
本批未动的仅剩 OPS-05（`Makefile --env-file`）与 SEC-02（凭据吊销，运维动作）。

## 2. 判定统计

### 2.1 各专题原始计数（与各文档 §1 一致）

| 文档 | 专题 | 问题总数 | FIX_NOW | FIX_IF_CHEAP | DEFER | ACCEPT/CLOSE |
|---|---|---:|---:|---:|---:|---:|
| 01-command-plane.md | 01 命令平面与并发门禁 | 13 | 1 | 3 | 3 | 6 |
| 02-event-contract.md | 02 事件契约与投影 | 10 | 1 | 3 | 3 | 3 |
| 03-pi-bridge.md | 03 Pi RPC Bridge 与原生事件 | 15 | 3 | 1 | 6 | 5 |
| 04-opencode-bridge.md | 04 OpenCode Task-scoped Server / Bridge 生命周期 | 6 | 0 | 2 | 2 | 2 |
| 05-opencode-events.md | 05 OpenCode 事件/SSE 映射与 settled 判定 | 10 | 0 | 4 | 5 | 1 |
| 06-claude-codex.md | 06 Claude / Codex V2 迁移与无回归 | 6 | 0 | 1 | 5 | 0 |
| 07-runner-infra.md | 07 公共 Runner / Bridge 基础设施与 harness manifest | 9 | 2 | 0 | 4 | 3 |
| 08-runtime-bundle.md | 08 Runtime Bundle / Harness Registry / harness_options / Readiness / Kit Inventory | 7 | 0 | 2 | 3 | 2 |
| 09-worker-kit.md | 09 Worker Kit 制品、安装与校验 | 14 | 0 | 5 | 4 | 5 |
| 10-model-endpoints.md | 10 Model Endpoint 重命名、Provider 配置、请求选项出口代理 | 6 | 0 | 2 | 2 | 2 |
| 11-delivery-lifecycle.md | 11 Git/MR 交付、Task 生命周期与终态、Scheduler | 7 | 1 | 1 | 5 | 0 |
| 12-frontend.md | 12 前端任务执行/交付/交互 UI（除 Provider 面板）—— Code Review | 10 | 0 | 3 | 7 | 0 |
| 13-security.md | 13 横切安全与凭据 | 9 | 1 | 4 | 0 | 4 |
| 14-migrations-models.md | 14 Alembic 迁移与数据模型 | 6 | 0 | 1 | 2 | 3 |
| 15-deploy-ops.md | 15 部署编排与离线包 | 17 | 5 | 8 | 1 | 3 |
| 16-tests.md | 16 测试质量与覆盖 | 18 | 1 | 6 | 4 | 7 |
| 17-cross-cutting.md | 17 横切补充与范围外核查 | 7 | 0 | 4 | 0 | 3 |
| **合计** | 17 个专题 | **170** | **15** | **50** | **56** | **49** |

### 2.2 归并去重后（跨专题重复只记一次）

| 判定 | 数量 | 说明 |
|---|---:|---|
| FIX_NOW | 13 | 见 §3；下次真实使用前必须处理 |
| FIX_IF_CHEAP | 48 | 见 §4；顺手修，或与 §3 同批处理 |
| DEFER | 55 | 见 §5；触发条件出现即修 |
| ACCEPT/CLOSE | 49 | 见 §6；本画像下的过度防御，书面接受并关闭 |
| **唯一问题合计** | **165** | 170 减去 5 组跨专题重复 |

5 组重复（同一根因被两个专题独立发现，合并后取更靠前的判定）：

| 组 | 主条目 | 重复条目 | 合并后判定 |
|---|---|---|---|
| 1 | PI-01（3） | EVT-02（2） | FIX_NOW |
| 2 | PI-03（3） | RTB-02（8） | FIX_IF_CHEAP |
| 3 | SEC-02（13） | OPS-02（15） | FIX_NOW |
| 4 | OPS-03（15） | TST-01（16） | FIX_NOW |
| 5 | OCE-05（5） | EVT-06（2） | DEFER |

另有两组「同源/同机制但刻意不合并」，各自独立计数（不影响 165）：SEC-01 × RUN-INFO-01（清洗词表缺口
的两个面）、PI-01 × EVT-03（生产者产出非法事件 vs 消费者不推进游标）。

### 2.3 过度防御集中在五处

| 簇 | 本画像为何不需要 |
|---|---|
| 并发/一致性不变量（租约续期、跨会话 CAS、显式释放、多 dispatcher 顺序） | 生产只有**一个** `codify-scheduler`，owner 串与 task 绑定、重启即重领；command 行不喂统计 |
| 契约纯度与文档字面一致（projector 单写者、raw_archive 定位符、两侧词表字节一致） | 措辞差异；按字面改反而会重开「未发送命令永久 queued」的窗口，正确做法是改文档 |
| 硬切门禁 / canary / 双轨回滚 | 上线默认即 `v2_only`、不做 canary，回滚=重新部署上一版镜像/Kit；「必须显式配置执行模式」与「指定 revision 人工门禁」都是多余机制 |
| 制品可复现与完整供应链门禁 | 离线包一年手工构建/安装几次，identity 取 manifest 摘要；真正的保证是 launcher 与任务期校验 |
| 覆盖纯度与非生产平台断言（全链集成、Dockerfile 子串、非 Linux 进程回收、PG 口令集中治理） | 无 CI、单机开发、生产是 Linux；不改变用户看到的行为 |

## 3. FIX_NOW 清单（13 条，按专题排序）

### CMD-04 `created_by` 列宽 64 < `username` 上限 255，长用户名使 PUT 直接 500

- **位置**（`01-command-plane.md`）：`backend/app/models.py:737`（对照 `:1480`）、`backend/alembic/versions/074_open_harness_v2.py:103`、`backend/app/api/task_command_routes.py:69-72`
- **影响**：GitLab/OIDC 用户名长度 > 64 的用户（自建 GitLab 允许至 255）**完全无法发送命令**，每次 PUT 500；SQLite 不校验长度，故单测不会暴露该问题。
- **最小动作**：`created_by` 放宽到 `String(255)` + 一条迁移（与仓库其它 username 列一致）
- **状态**：已修复（`7794eb92`）

### PI-01 原生拒绝 ACK 产出的 `control.command.rejected` 缺 `rejection_message`，导致投影 ingest 永久卡死

- **位置**（`03-pi-bridge.md` ≈ `02-event-contract.md` EVT-02，同一根因）：`deploy/worker-entrypoint/harness/adapters/pi_events.py:603-613`
- **影响**：拒绝事件在流中位于 `agent_settled` 之前（probe 证据：`docs/harness-probes/v2/pi/steer.raw.jsonl` 第 10 行是 ACK、第 104 行才是 `agent_settled`）。ingest 卡死后 `agent_settled` 永不…
- **最小动作**：`pi_events.py:610`：`rejection_message` 缺省回退 `record.get("error")` 或固定文案（1 行）；不必改 projector 的隔离机制
- **状态**：已修复（`7794eb92`；同一根因的 EVT-02 一并修复）

### PI-02 初始 `prompt` 被 Pi 拒绝时只记 diagnostic、不产生 terminal，任务挂到超时

- **位置**（`03-pi-bridge.md`）：`deploy/worker-entrypoint/harness/adapters/pi_events.py:629-634`
- **影响**：一次配置/模型解析错误会静默挂起到 `TASK_TIMEOUT`（默认 1800s），最终以 `harness.failed{kind:timeout}`（`runner.sh:150-180`）收尾，真正的 `error` 文本只留在 console log；若 Pi 在该情况下直接退出，则退化为…
- **最小动作**：translator 兜底前单列 `prompt` 且 `success:false` → 置 `terminal_failure`（~4 行）；owner 在 prompt ACK 失败时 `_fail` 收口（~3 行）
- **状态**：已修复（`7794eb92`）

### PI-04 Managed Skills 被物化到 Pi 不会扫描的目录，`task_skills` 静默无效

- **位置**（`03-pi-bridge.md`）：`deploy/worker-entrypoint/harness/adapters/pi.sh:210-229`
- **影响**：manifest 声明 `task_skills: true`，但任何使用 Managed Skills 的 Pi 任务里技能都不会被加载，系统提示词中也没有技能清单，用户侧表现为“技能配置无效且无任何报错”。
- **最小动作**：物化到 Pi 实际扫描位置（`${CODIFY_PI_CLI_HOME}/.pi/agent/skills` 或 `.agents/skills`）或追加 `--skill`；拷贝源与 codex 对齐（~4 行）
- **状态**：已修复（`7794eb92`）

### RUN-01 V2 manifest 收窄 capability 词表后，`run_text`/`codegraph` 判定永久失效

- **位置**（`07-runner-infra.md`）：`deploy/worker-entrypoint/harness/manifest.json:29-35`（claude）、`:90-96`（pi）；消费方 `deploy/worker-entrypoint/harness/runner.sh:94-99,194-200`、`deploy/worker-entrypoint/codegraph.sh:73-79`、`deploy/worker-…
- **影响**：当前默认 claude、上线后默认 pi 的任务中（manifest 里 pi 的 capabilities 同样只有 5 键），(a) commit message 恒走 `main.sh:159-166` 的硬编码兜底文案（日志 `Harness commit message generatio…
- **最小动作**：① `runner.sh:194-200` 的能力判定 `codify_harness_capability_enabled "run_text"` → `declare -F adapter_run_text`（4 个 adapter 都定义了该函数；不支持的 codex 版返回非零，自然回落，与今天行为一致）。② `codegraph.sh:73-79` 的 capability 分支 → 按…
- **状态**：已修复（`7794eb92`）

### RUN-02 canonical event writer 只接受 argv 传 payload，超 ~128 KiB 即整条链路失败

- **位置**（`07-runner-infra.md`）：`deploy/worker-entrypoint/harness/events.py:369-376`；写入方 `deploy/worker-entrypoint/harness/common.sh:17-24`、`deploy/worker-entrypoint/harness/adapters/claude_events.py:134-149`
- **影响**：两条独立后果。(a) **adapter 侧**：`claude_events.main()` 逐行 `translate()` 无 per-record 兜底（`claude_events.py:383-428`），`OSError` 直接逸出 → translator 进程死 → 不再写 `CO…
- **最小动作**：`events.py` 增 `--payload-stdin`（`main()` 里 `json.loads(sys.stdin.read())`，~4 行）；`common.sh:17-24` 的 `codify_emit_event` 与 4 个 adapter 的 `_emit` 改为 `input=payload` 传 stdin（各 1 行）。无 payload 大小上限、无截断、无共享…
- **状态**：已修复（`7794eb92`）

### DEL-01 终态失败原因被归档的 provider 错误覆盖

- **位置**（`11-delivery-lifecycle.md`）：`backend/app/api/tasks.py:657-668`（另见 `:709-718`）
- **影响**：两类终态的失败原因与事实不符：(a) 取消的任务 —— canonical/生命周期写入的是 `"Cancelled by user"`（`worker_task_lifecycle.py:1301-1309`），持久化与接口却显示 provider 错误（如 "Pi provider return…
- **最小动作**：仅当 canonical 失败原因为空（legacy Pi 记录才是 raw payload）时才用归档 detail 兜底，且排除 cancelled / timeout / 交付失败；归档 detail 另存字段。改 2 处条件：`api/tasks.py:657-668`（读，含 `:709-718` 的 failure_summary）、`core/worker_results.py:58…
- **状态**：已修复（`7794eb92`）

### SEC-02 git 历史仍含真实凭据（HEAD 已清理但未吊销，仍可完整检出）

- **位置**（`13-security.md` ≈ `15-deploy-ops.md` OPS-02，同一根因）：`deploy/.env.test:6-7`
- **影响**：任何拥有仓库读权限（含 CI、镜像构建上下文、历史 clone）者可取得：① GitLab bot PAT（按 `docs/architecture/open-harness-v2.md` 的部署模型，该 token 对所有受管项目有写权限）；② 一个可用的模型 Provider key；③ 若 …
- **最小动作**：吊销/轮换三类凭据；`CONFIG_ENCRYPTION_KEY` 换新后按需重新录入受影响密文（provider key / webhook secret）。建议过重：`git filter-repo` 清理历史 + 通知所有 clone/CI 重拉没必要（凭据死了即可）
- **状态**：**待运维执行**（吊销/轮换凭据）

### OPS-01 离线包 `start.sh` 因两个必填插值变量缺失无法启动

- **位置**（`15-deploy-ops.md`）：`deploy/offline-bundle/docker-compose.yml:30`（另见 `:79`、`:128`）
- **影响**：按 README/CONFIGURATION 的离线部署步骤在目标主机执行 `./scripts/start.sh`，会在插值阶段直接失败，整栈（含不启用 `maintenance` profile 的默认路径）都起不来；这是离线交付的主路径。要求「必须显式指定执行模式」本身与本画像不符（上线默认即…
- **最小动作**：把 `v2_only` 变成默认——`backend/app/config.py` 的 `harness_execution_mode` 默认 `v2_only`；compose 删除 `${HARNESS_EXECUTION_MODE:?…}` 必填插值（或改 `:-v2_only`）且模板不再需要该键；同时把 `${MIGRATION_TARGET:?...}` → `${MIGRATION_…
- **状态**：已修复（`7794eb92`：默认 `v2_only` + 移除显式配置门禁）

### OPS-03 mock 集成 compose 仍写 `dual_canary`，backend/scheduler 启动即崩

- **位置**（`15-deploy-ops.md` ≈ `16-tests.md` TST-01，同一根因）：`backend/tests/mock_integration/docker-compose.mock-test.yml:69`（另见 `:113`）
- **影响**：`make test-mock-integration`、`make test-mock-integration-parallel`（`Makefile:276/:304`）以及
- **最小动作**：删掉这两处 `HARNESS_EXECUTION_MODE: dual_canary`（默认即 `v2_only`，无需显式配置）
- **状态**：已修复（`7794eb92`；同一行配置的 TST-01 一并修复）

### OPS-04 E2E compose 的 migration 目标落后 4 个 revision，E2E 数据库 schema 与代码不符

- **位置**（`15-deploy-ops.md`）：`deploy/docker-compose.e2e.yml:41`
- **影响**：`docker-compose -f docker-compose.e2e.yml up` 后数据库停在 075，backend 一旦读写 tasks
- **最小动作**：`docker-compose.e2e.yml:41` 默认值改 `${MIGRATION_TARGET:-head}`（1 词）
- **状态**：已修复（`7794eb92`）

### OPS-05 `make worker-runtime-bundle-export` 未传 `--env-file`，文档化的 L3 导出命令直接失败

- **位置**（`15-deploy-ops.md`）：`Makefile:54`
- **影响**：`docs/DEPLOYMENT.md` §10.1 与 `docs/runbooks/multi-harness-rollout.md` §5.1 记载的
- **最小动作**：`Makefile:54` 加 `--env-file $(PROJECT_ROOT)/deploy/.env.test`（1 行）
- **状态**：**待修**

### OPS-08 部署文档仍把 `dual_canary` 写成合法值，按文档执行会启动失败

- **位置**（`15-deploy-ops.md`）：`docs/DEPLOYMENT.md:134`（另见 `:20`、`:64`）
- **影响**：运维照 DEPLOYMENT.md §4.3 / DEVELOPMENT.md 执行，Backend 与 Scheduler 会在启动校验处
- **最小动作**：6 处改为「默认 `v2_only`、无需显式配置」，并删除 canary/双轨叙述
- **状态**：已修复（`7794eb92`）

## 4. FIX_IF_CHEAP 索引（48 条）

只在错误路径或边界触发，且修复 ≤ ~6 行、不引入新机制。空闲时顺手修；否则与 §3 同批处理。

| ID | 文档 | 问题 | 最小动作 |
|---|---|---|---|
| CMD-01 | 01 | command 状态 helper 的 “CAS” 判定读本会话缓存行，跨会话终态只能靠 CHECK 约束挡下 | 只给会与 gate 竞争的 3 处终态写 + `requeue_pre_send_failure` 加 `WHERE status = :exp… |
| CMD-03 | 01 | `retry` 结果无上限、无退避、无审计，队首可被无限重试并阻塞整条队列 | retry 分支加 1 行 `logger.warning`（含 `delivery_attempts`）；不加退避/上限 |
| CMD-06 | 01 | pump 持久化 `native_rejected`（非冻结枚举），同一拒绝在 API 与事件流显示不一致 | `PUBLIC_REJECTION_MESSAGES`（±`REJECTION_CODES`）加 `native_rejected`，2 行 |
| EVT-03 | 02 | 单条非法记录使整条事件流永久卡死，Task 被误判为缺少终态 | chunk 循环内对 `V2_AUDIT_EVENT_TYPES` 校验失败降级为 1 条 diagnostic 并继续推进游标（复用已有常量… |
| EVT-05 | 02 | `WorkerEventProjector` 类 docstring 与实现不符 | 1 行 docstring |
| EVT-INFO-01 | 02 | `[V1 遗留]` JSONL 解析用 `str.splitlines()`，Unicode 行分隔符会切碎单条记录 | `iter_complete_jsonl_records` 用 `buffer.split("\n")` + remainder（worker … |
| PI-03 | 03 | `pi/v1` harness_options 无任何消费者：thinking_level / steering_mod… | 从 `pi/v1` 去掉 `thinking_level`（或映射 `--thinking`） |
| OCB-01 | 04 | Session 状态兜底查询使用了 1.18.19 不存在的路由 | `status()` 改 `GET /session/status` + 三处审计模板 + 按 sessionID 取值（~5 行） |
| OCB-02 | 04 | 快照凭据缺失时静默跳过 provider 配置物化 | 写 `opencode.json` 的三元条件改为显式 fail-closed `return 1` + stderr 说明（~6 行） |
| OCE-01 | 05 | abort 形状（assistant `error:true`）被当作成功收敛 | 记 `errored_message_id`，仅当它仍是最后一条 assistant 消息时收敛失败（~6 行）。【建议过重】 不要按 revi… |
| OCE-02 | 05 | delta 去重按后缀比较，静默吞掉真实重复内容 | 用快照水位（`snapshot_len`+flag）替代 `endswith` 去重，两处 delta 路径（~6 行） |
| OCE-03 | 05 | `session.idle` + 空文本回合被判 `protocol_error` | 文本为空仍成功收敛，只保留“必须是 assistant”校验（~2 行） |
| OCE-04 | 05 | SSE 分片逐块解码，多字节字符被替换成 U+FFFD | `codecs.getincrementaldecoder("utf-8")` + EOF flush（~3 行） |
| CX-03 | 06 | Codex App Server 的 JSON-RPC 成功响应被记为 `unknown_raw_event`，响应分支… | `codex_events.py:398` → `if "method" in record or "id" in record:` |
| RTB-01 | 08 | readiness 作用域判别与 V2 校验写入不一致，创建/切换/CI 门禁失效 | `worker_runtime_readiness.py:472` 的 `profile_requires_content_inventory(… |
| KIT-01 | 09 | 逐 Harness bridge 自检的失败被静默丢弃，该门禁实际不生效 | host_mount 分支**显式跳过**自检（该分支未挂载 `${HARNESS_HOST_PATH}`），其余分支加 `|| return … |
| KIT-03 | 09 | LD_LIBRARY_PATH 隔离"硬门禁"可静默跳过，与文档声称的"每对 Kit+镜像都证明"不符 | 去掉探测命令的 `|| true`，改为 `lib_dir="$(…)" || { echo probe failed; return 1; }… |
| KIT-04 | 09 | `--archive` 校验容忍重复的 `manifest.json` 成员，导致"被校验的 manifest"与"被安… | `seen.add` 前移到 `EXCLUDED_PATHS` 的 `continue` 之前（1 行） |
| KIT-05 | 09 | 归档名缺少 `codify-worker-kit-` 前缀仍可安装，但后端 receipt 校验要求完全一致 | 安装器断言 `basename(ARCHIVE) == codify-worker-kit-*.tar.gz`（1 行；两侧安装器各 1 行） |
| KIT-INFO-03 | 09 | 文档中的 Kit 路径示例仍是不带摘要前缀的旧命名 | 改 `docs/worker-kits.md` 三处示例为 `<version>-linux-<arch>-<12hex>` |
| MEP-01 | 10 | Backend 与 Worker 对 endpoint 快照字段的归一化不一致，带首尾空格的 Provider 配置会导… | `_attr_str` 返回 `value.strip()`（2 行）；先跑 `SELECT id,name FROM ai_providers… |
| MEP-03 | 10 | `endpoint_transport_fingerprint()` 是死代码，其 docstring 声称的"Prov… | 删函数 + `test_model_endpoints.py` 2 条断言（净 -20 行） |
| DEL-INFO-02 | 11 | `[V1 遗留]` 无变更失败在 `error_message` 上只留 `engine_error` | 无内容分支补发 `harness.failed{kind:engine_error,message:"No changes were deliv… |
| FE-01 | 12 | 英文语言包缺失 `config.runtimeFailureDetailsUnavailable`，EN 界面显示原始 … | `en.ts` 在 `runtimeLastChecked` 后补 `runtimeFailureDetailsUnavailable` |
| FE-02 | 12 | Steering 命令被拒（409/422/403）时丢弃后端 `detail` 对象，拒绝原因不可见 | `TaskSteeringPanel.vue:224-234` 的 catch 按 `detail.message ?? detail.code… |
| FE-03 | 12 | 每次发送都重新生成 `command_id`，传输失败后的重试会重复投递同一条指令 | `sendHarnessCommand(taskId, request, commandId = generateCommandId())`，面… |
| SEC-01 | 13 | 清洗模式覆盖不全：自定义 Provider 密钥形态与 JSON `apiKey` 字段不被脱敏 | 补「名字型规则容忍 JSON 引号/空格」+ `glpat` 尾部 / `ghp_` / `AIza` / `hf_` / `xox[baprs… |
| SEC-03 | 13 | 调度器 `/health` 端口默认发布到所有宿主接口 | 端口映射改成 `"127.0.0.1:${SCHEDULER_HEALTH_PORT:-8001}:8001"`（1 行） |
| SEC-05 | 13 | webhook 密钥轮换：DB 与 GitLab 可能永久漂移且无检测手段 | 先 PUT 成功再落库（失败即回滚刚写的 secret 并返回明确错误），~5 行 |
| SEC-INFO-03 | 13 | 默认数据库口令 + 5432 端口发布（`[V1 遗留]`） | `"127.0.0.1:5432:5432"`（1 行，保留宿主 psql）。改口令是可选运维：`ALTER USER` + 同步 3 处 `D… |
| MIG-01 | 14 | ORM 声明 `server_default=0`，但 076/077 迁移已把该默认值删除 | 删掉 `models.py` 两处 `server_default=text("0")`（纯删除 2 行）；不要新增 revision 去恢复 … |
| OPS-06 | 15 | `SCHEDULER_HEALTH_PORT` 端口契约不自洽：非默认值会让 Scheduler 永久 unhealth… | 端口映射与 healthcheck 引用同一变量（2 处），删掉“0=禁用”注释 |
| OPS-07 | 15 | 离线包 maintenance `migrate` 绕过 `run-migration-owner` 的 fail-cl… | offline `migrate.command` 改 `["/usr/local/bin/run-migration-owner"]` + … |
| OPS-10 | 15 | 生产密钥仍被引导写入仓库内被追踪的 `deploy/.env.test`（本次仅加了「不要写」的注释） | `git rm --cached deploy/.env.test`（工作区文件保留，`env_file: .env.test` 照旧）+ 提交… |
| OPS-11 | 15 | `.dockerignore` 未排除 `.env.*`，部署密钥文件进入构建上下文 | `.dockerignore` 加 `.env.*` + `!.env.example` |
| OPS-INFO-02 | 15 | 离线包用可变 tag 加载镜像，且没有校验 `images/SHA256SUMS` | `load-images.sh` 加 `sha256sum -c images/SHA256SUMS` |
| OPS-INFO-03 | 15 | 版本坐标漂移（worker 镜像 tag / Kit 默认版本） | 统一 `.env.test`/`.env.example`/offline example/Makefile/`export.sh` 默认值（4… |
| OPS-INFO-05 | 15 | 离线包没有 execution-mode preflight 等价物，且前置依赖未列 `python3` | 前置条件加 `python3`（1 行）；health-check 内加执行模式校验为可选 |
| TST-04 | 16 | `protocol_error` 的"缺 init"（缺 `run.started`）分支无测试 | `test_harness_protocol.py` 负例表加 `[_event(1,"tool.started")] → missing_in… |
| TST-06 | 16 | execute / schedule / retry 三个入口的 V1 只读门禁无测试 | `test_tasks_api.py:2375` 同款参数化一条，覆盖 execute/schedule/retry 三路由 |
| TST-07 | 16 | 前端 steer 发送路径零覆盖 | 补 2 例：resolve→清空输入+刷新历史；reject→`message.error`+`sending` 复位 |
| TST-09 | 16 | 名不符实的空断言：`projector` 不写命令状态 | 删掉该用例（净减代码） |
| TST-10 | 16 | 四个 Kit 安装器 fail-closed 用例在非 root 下静默跳过 | 改 `_secure_install_root`：monkeypatch `os.geteuid`→0 + 安装根换 tmpdir |
| TST-13 | 16 | 075/077/078/079 迁移测试只断言 mock 的 SQL 文本 | 切库前在正式数据副本上跑两条 SELECT/COUNT：078 受影响任务数、079 越界值；不新增真库测试。建议过重：把 079 纳入 `te… |
| XC-01 | 17 | 旧 `task_timeout` 迁移后可能超出新字段边界，导致 `get_effective_settings()` … | 079 里钳制一行：`value = max(60, min(int(legacy["value"]), 28800))`。建议过重：让 `ge… |
| XC-02 | 17 | V1→V2 回放脚本固化的 Codex control transport 与已发布 manifest 不一致 | 改 2 个字符串常量。建议过重：`replay_v2.py` 直接读 manifest.json（为探针脚本引入新解析耦合） |
| XC-03 | 17 | 构建/验收产物进入版本库且未被忽略 | `.gitignore` 加 `output/`、`.vite/` + `git rm --cached` 这 9 个文件 |
| XC-04 | 17 | `CLAUDE.md` 与代码漂移（容器命名、迁移归属） | 改 CLAUDE.md 两处 + copilot-instructions.md 同名处（共 ~4 行） |

## 5. DEFER 索引（55 条）

真实但本画像可容忍（可停机、可重跑、可手工介入）。触发条件出现时按条目的「最小动作」处理。

| ID | 文档 | 问题 | 何时再管 |
|---|---|---|---|
| CMD-05 | 01 | 空文本命令被 API 接受、被容器内 client 拒绝，且公开消息套用错误的 code 文案 | — |
| CMD-INFO-04 | 01 | `create_task_attempt` 复用已有 attempt 时忽略传入的 `control_state… | — |
| CMD-INFO-06 | 01 | 长会话下的 identity map 陈旧同样作用于 projector 的 gate 判定（CMD-01 同一… | — |
| EVT-INFO-02 | 02 | `[V1 遗留]` tool 输入存在「同一字段两条清洗强度」的写法 | — |
| EVT-INFO-04 | 02 | 归档读取在事件循环内同步解压整个 tar.gz | — |
| PI-05 | 03 | `pi_adapter_terminate` 既不发原生 abort，也不作用于 Pi/owner 进程 | — |
| PI-06 | 03 | `message.delta` 的 payload 键与 projector 读取的键不一致（`content… | — |
| PI-07 | 03 | 原生拒绝的审计码与实际原因不一致（`native_rejected` 不在拒绝码表内） | — |
| PI-08 | 03 | `pi_bridge.PiBridge` 是死代码，且与线上 owner 的策略不同 | — |
| PI-INFO-02 | 03 | follow-up 重开 accepting 依赖“settled 之后仍会开新 run”，且无兜底 | — |
| PI-INFO-03 | 03 | JSON 行先 sanitize 再解析，与 `sanitize_json_value` 的既有约定相悖 | — |
| OCB-03 | 04 | 取消/超时路径的硬停 TERM 到不了 Harness（公共 Runner 机制） | — |
| OCB-INFO-03 | 04 | 子代理（child session）事件被会话过滤丢弃，用量/诊断不完整 | 用 `task` 工具的任务变多且用量要精确 |
| OCE-05 | 05 | `model` 恒为 null、从不发 `model.resolved` | — |
| OCE-06 | 05 | `message.delta` 用 `content`，projector 读 `text` | — |
| OCE-INFO-01 | 05 | `session.status(retry)` 对通用 rate-limit 标记即刻收敛终态 | — |
| OCE-INFO-03 | 05 | `busy` / `idle_seen` 写了不用 | — |
| OCE-INFO-04 | 05 | part 无 `id` 时多个 text 快照互相覆盖 | — |
| CX-01 | 06 | Claude 每个 text delta 派生一个 canonical 事件子进程，长输出任务线性变慢 | — |
| CX-02 | 06 | Codex 取消路径未落地：adapter `terminate` 空实现、runner 无信号 trap，`t… | — |
| CX-INFO-01 | 06 | 打开 partial messages 后 legacy `tool_calls` 数组双写 | — |
| CX-INFO-02 | 06 | Claude thinking 块跨消息交错时会被误判为 interrupted | — |
| CX-INFO-03 | 06 | Codex `reasoning_id` 缺少 turn 维度 | — |
| RUN-04 | 07 | `bridge.py` stub 的 30s 超时与其自身文档/真实 ACK 语义矛盾（当前无生产调用方） | — |
| RUN-INFO-02 | 07 | timeout marker 与 `run.completed` 的窄竞态会让终态事件携带 `failure.k… | — |
| RUN-INFO-04 | 07 | 双次初始化会启动第二个 model proxy，第一个 PID 被覆盖后泄漏 | — |
| RUN-INFO-05 | 07 | [V1 遗留] `append_runtime_event` 是无锁直写 `event.jsonl` 的残留助手… | — |
| RTB-03 | 08 | §13.4 容器错误重探被移除后遗留不可达代码与失效文档 | — |
| RTB-INFO-01 | 08 | 未注册命名空间与非选中 Harness 的 options 被静默接受 | — |
| RTB-INFO-02 | 08 | capability 上界校验只拒绝布尔 `True`，非布尔真值绕过且消费方判定不一致 | — |
| KIT-02 | 09 | 两个安装器同源漂移：文档化的离线安装路径缺少模型代理与 harness inventory 的 fail-clo… | — |
| KIT-06 | 09 | Kit 侧校验器与后端 inventory 契约宽严不一致（路径归一化 / 额外字段） | — |
| KIT-08 | 09 | `install.sh` 的校验和工具回退不完整，无 `sha256sum` 的主机中途失败 | — |
| KIT-INFO-04 | 09 | root-only 的安装器测试与 `install.sh` 新增门禁可能已脱节 | — |
| MEP-02 | 10 | `provider_options` 保留字段契约未覆盖 Task 创建路径：遗留行会让已冻结的保留参数被代理静… | — |
| MEP-04 | 10 | 重命名未覆盖用户可见术语：Provider 面板与 i18n 仍以 "Wire Protocol / Wire … | — |
| DEL-02 | 11 | 交付采集的软失败原因不会进入任何事件或 Task 字段 | — |
| DEL-03 | 11 | `task_timeout` 共享 helper 未被生产代码使用，派生值在 API 内各写一遍 | — |
| DEL-04 | 11 | 冻结 harness options 的序列化 helper 被复制成两份 | — |
| DEL-05 | 11 | `ci_failure_collector` 调用参数意外去缩进 | — |
| DEL-INFO-01 | 11 | `[V1 遗留]` 取消意图会把「已失败的终态」改写成 CANCELLED 并覆盖原因 | — |
| FE-04 | 12 | 思考耗时 tooltip 硬编码英文，未走 i18n | — |
| FE-05 | 12 | OpenCode `model_variant` 输入缺少与后端一致的客户端校验，422 原因被丢弃 | — |
| FE-06 | 12 | 每秒把 `nowMs` 下发给每一行思考/回复行，长日志下形成 1Hz 全列表重渲染 | — |
| FE-INFO-01 | 12 | `control_state='disabled'` 时 gate 徽标渲染为空 | — |
| FE-INFO-02 | 12 | 未知 `push.status` 被渲染为“推送失败” | — |
| FE-INFO-03 | 12 | `showCommitRecord` 在“有 push 结论但无提交列表”时隐藏整张提交记录卡 | — |
| FE-INFO-04 | 12 | `command-delivered` 事件无消费方 | — |
| MIG-02 | 14 | ORM 把 `runtime_mode` 默认值改为 `mounted_kit`，数据库默认值仍是 `baked… | — |
| MIG-INFO-04 | 14 | `_validators.py` 与 `config_runtime.py` 各有一份 `_validate_c… | — |
| OPS-INFO-06 | 15 | 运行时暴露面小结（含 V1 遗留项） | — |
| TST-02 | 16 | 命令平面核心断言只在"可达内网 Postgres"时执行，且无 CI 门禁 | — |
| TST-INFO-01 | 16 | 真实子进程 + 1s 边界等待的潜在 flake | — |
| TST-INFO-02 | 16 | mock_e2e 的 schema 来自 ORM 而非迁移 | — |
| TST-INFO-03 | 16 | 命令测试依赖"module 级共享 DB + 随机 owner"的隐式约定 | — |

## 6. ACCEPT/CLOSE 清单（49 条，按簇）

本画像下属于过度防御：它们要求的不变量在「单 scheduler、内网、无 SLA、`v2_only` 默认无 canary、无 CI」下不需要。
**书面接受并关闭**；出现右侧触发条件时重开。

| 簇 | 条目 | 触发条件 |
|---|---|---|
| 并发/一致性不变量（单 `codify-scheduler` 画像不可达） | CMD-02、CMD-07、CMD-INFO-02、CMD-INFO-03、CMD-INFO-05、TST-03、TST-05 | 出现第二个 scheduler/dispatcher；或要求可用性；或真出现命令永久 `queued` |
| 契约纯度高 / 文档与实现字面不一致（改文字即可） | EVT-01、CMD-INFO-01、EVT-04、EVT-INFO-03、RTB-04、RTB-INFO-03、RUN-03、RUN-INFO-01、RUN-INFO-03、OCB-INFO-02、KIT-INFO-02 | 重写冻结契约文档、放宽 CHECK 约束、或接入公网 provider |
| 不可达，或已被真机证据证伪 | PI-INFO-01、PI-INFO-04、PI-INFO-05、PI-INFO-06、PI-INFO-07、OCB-INFO-01、OCE-INFO-02、KIT-INFO-01、KIT-INFO-05、KIT-INFO-06、MEP-INFO-01、MEP-INFO-02、OPS-INFO-01、OPS-INFO-04、MIG-INFO-01、MIG-INFO-02、TST-INFO-04、TST-INFO-05 | 换基础镜像（slim/busybox）、接入公网 provider、仓库来源变不可信 |
| 硬切门禁 / canary / 双轨回滚（画像不需要） | OPS-09、MIG-INFO-03 | 引入 SLA、要求不停机回滚、或需要灰度发布 |
| 安全加固（内网可信 + 无 SLA） | SEC-04、SEC-09、SEC-INFO-01、SEC-INFO-02 | 出现外部协作者/多团队隔离/启用 OIDC、API 新增 exec/stop、或威胁模型变更 |
| 制品可复现 / 供应链（一年手工几次） | KIT-07 | 引入 CI/合规审计、或需要无人值守发布 |
| 测试覆盖纯度（无 CI、单机开发） | TST-08、TST-11、TST-12、XC-05、XC-INFO-01、XC-INFO-02 | 上 CI、出现第二台开发机、或真出现孤儿进程泄漏 |

## 7. 修复顺序

### Tier-1：10 条主路径项 —— 已修复（`7794eb92`）

| # | 条目 | 最小动作 | 影响面 | 状态 |
|---|---|---|---|---|
| 1 | PI-01（≈ EVT-02） | `pi_events.py` rejected 分支补 `rejection_message` 缺省（1 行） | 事件流永久卡死 + 丢统计投影 | 已修复（`7794eb92`） |
| 2 | PI-02 | `prompt` 被拒即置 `terminal_failure` 并让 owner 收口（~7 行） | 配置类错误挂到超时、错误分类失真 | 已修复（`7794eb92`） |
| 3 | PI-04 | skills 物化到 Pi 实际扫描目录或追加 `--skill`（~4 行） | 表单勾选的技能静默不生效 | 已修复（`7794eb92`） |
| 4 | RUN-02 | `events.py` 加 `--payload-stdin`，`common.sh` 与 4 个 adapter 走 stdin | 大 payload 时成果不提交不推送 | 已修复（`7794eb92`） |
| 5 | RUN-01 | run_text 判定改 `declare -F adapter_run_text`；codegraph 按 harness key 判定（2 行） | commit message / MR summary / CodeGraph 静默失效 | 已修复（`7794eb92`） |
| 6 | DEL-01 | 收窄归档 detail 对 `error_message`/`failure_summary` 的覆盖条件（2 处） | 真实失败原因被 provider 重试错误盖住 | 已修复（`7794eb92`） |
| 7 | CMD-04 | `created_by` 放宽 `String(255)` + 一条迁移 | 长用户名用户无法发命令 | 已修复（`7794eb92`） |
| 8 | OPS-01（含 OPS-07 同处） | `harness_execution_mode` 默认 `v2_only`；compose 去掉 `${HARNESS_EXECUTION_MODE:?…}` 必填插值；`${MIGRATION_TARGET:-}` | 离线包 `start.sh` 插值即失败 | 已修复（`7794eb92`） |
| 9 | OPS-03（≈ TST-01） | 删掉 mock compose 两处 `HARNESS_EXECUTION_MODE: dual_canary` | 无外网依赖的端到端验收整层不可跑 | 已修复（`7794eb92`） |
| 10 | OPS-04 | e2e 迁移目标改 `${MIGRATION_TARGET:-head}` | E2E 必然 `UndefinedColumn` | 已修复（`7794eb92`） |
### Tier-2：其余 FIX_NOW（同上 PR 顺手）

| 条目 | 最小动作 | 状态 |
|---|---|---|
| OPS-05 | `Makefile` 导出目标补 `--env-file`（1 行） | **待修** |
| OPS-08 | 6 处文档改为「默认 `v2_only`、无需显式配置」，删除 canary/双轨叙述 | 已修复（`7794eb92`） |
| SEC-02 | 吊销/轮换 git 历史中的 GitLab PAT、Provider key、`CONFIG_ENCRYPTION_KEY`（0 代码） | **待运维执行** |

### Tier-3 / Tier-4

- **Tier-3**：§4 的 48 条 FIX_IF_CHEAP —— 空闲即修，不进发布门禁。
- **Tier-4**：§5 的 55 条 DEFER 与 §6 的 49 条 ACCEPT/CLOSE —— 记录在案；ACCEPT 项需团队明确「已知并接受」。
## 8. 与「历史统计数据不丢」直接相关的动作（切库前一次，不需要写代码）

1. **078 会 `DELETE FROM ai_providers`**（不可逆，`downgrade` 直接 `RuntimeError`），而 `analytics_queries.py:488`
   对 provider 维度用的是 **inner join**：被删 Provider 关联的历史任务会从 **provider 维度统计**里消失
   （总任务数与 `system_statistics_queries.py` 的快照兜底路径不受影响）。切库前先跑：

   ```sql
   SELECT count(*) FROM tasks t
   JOIN ai_providers p ON p.id = t.provider_id
   WHERE p.provider_kind = 'openai_compatible' AND p.model_protocol = 'anthropic_messages';
   ```

   并备份 `ai_providers` 与 `tasks.provider_id`。

2. **079 会原样搬运旧 `task_timeout`**：越界值会让 `Settings(**data)` 抛错，导致 `get_effective_settings()`
   的调用点（含统计页）返回 500。切库前确认
   `SELECT value FROM system_config WHERE key='task_timeout';` 落在 `[60, 28800]`；或按 XC-01 加一行钳制
   （`value = max(60, min(int(legacy["value"]), 28800))`）。

除此之外，历史数据的保留没有其它风险点：迁移链单头线性、已在真实 PG 上跑通且重复执行幂等。

## 9. 复核记录

| # | 复核对象 | 方法 | 结论 |
|---|---|---|---|
| 1 | PI-01/EVT-02 的 `rejection_message` 契约缺口 | 逐行读生产者/owner 元数据/校验器 | 确认 → FIX_NOW |
| 2 | OCE-01 abort 形状 | 读 error 分支 + idle 成功门 + probe README | 确认（端到端未运行） |
| 3 | OCB-01 状态路由 | 从固定二进制抽取 `/session/*` 路由表 | 确认路由不存在 |
| 4 | RUN-01 capability 词表 | 对比 V1/HEAD manifest + `jq -e` 复现 | 确认（Pi 的 capabilities 同样只有 5 键）→ FIX_NOW |
| 5 | RUN-02 argv 上限 | 读 `events.py` 入口 + `common.sh` + ARG_MAX 既有注释 | 确认（未在 Linux 复现 E2BIG） |
| 6 | RTB-01 作用域不一致 | 读读/写两侧函数与默认值 | 确认（严格 409 前置本非必需） |
| 7 | OPS-01 离线包 | 实跑 `docker compose config` → rc=15（先报 `HARNESS_EXECUTION_MODE`，补上后再报 `MIGRATION_TARGET`） | 复现；按新画像，正解是把 `v2_only` 变成默认而非补变量 |
| 8 | OPS-02/SEC-02 历史凭据 | `git show` + 形状统计（不明文回写文档） | 确认（13-security.md 已脱敏） |
| 9 | OPS-03/TST-01 `dual_canary` | grep + 配置校验 | 确认 → FIX_NOW（删掉该键即可） |
| 10 | OPS-04 E2E 迁移目标 | grep + alembic head（079） | 确认落后 4 个 revision |
| 11 | KIT-01 bridge 自检被吞 | 读 `verify-runtime.sh` 调用形态（`if ! run_one`） | 确认 errexit 被抑制；原建议会破坏 break-glass 分支，最小动作已改写 |
| 12 | CMD-01「CAS」非真 CAS | 依据 SQLAlchemy identity-map 语义复核 T01 推理 | 采信（跨会话终态靠 CHECK 兜底）→ FIX_IF_CHEAP |
| 13 | FE-01 en 缺键 / FE-03 command_id 每次重生成 | grep 两侧语言包 + 读 `api/tasks.ts` | 确认 → FIX_IF_CHEAP |
| 14 | 按画像重判全部 170 条 | 7 组并行复核「现在做不做」 | 全部落到四档判定，见 §2~§6 |
| 16 | 修复后的独立复核（2 名 reviewer 并行过审本批 diff） | 审阅代码 + 实跑端到端 | 采纳 3 项：rejected prompt 的终态被 `finally` 里的 translator SIGTERM 吞掉（已由 translator drain 修复，端到端复现 pre-fix 只剩 `run.started`）、归档兜底漏掉「状态前缀 + JSON/HTML 体」、`require_explicit_harness_execution_mode` 使 mock 栈仍不可启动（已删除该门禁）；mock 栈「无执行模式即失败」一条经实测为误报（默认即 `v2_only`） |
| 15 | 上线形态（默认 `v2_only`、无 canary、默认 harness=Pi） | 按团队确认的部署形态复检受影响条目 | OPS-01/03/07/08 措辞与动作已改写，OPS-09 与 MIG-INFO-03 改判 ACCEPT/CLOSE，PI-02/PI-04 升为 FIX_NOW，RTB-02/PI-03 去掉「Pi 非默认」依据 |

## 10. 局限与未验证项

- **无真实 Harness CLI / 容器运行**：Pi、OpenCode、Claude、Codex 的制品均为 linux-x64 ELF，本机（macOS/arm64）
  无法执行；worker 侧结论为静态推理 + 仓库内 probe 证据对照。Pi 与 OpenCode 已有真机任务（383/390/421）
  作为部分反证，但不是本次逐条复现。
- **无 Docker 部署验证**：除离线包 `docker compose config` 外未启动服务。
- **无 Go 工具链**：`deploy/worker-kit/model-proxy` 未执行 `go test`。
- **未跑全量测试/构建**：各专题只运行了窄范围单测；未运行 `npm run build`、全量 `vitest`、全量 `pytest`。
- **未在真实生产库执行迁移**（T14 在开发库的一次性库上验证过）。
- **威胁模型边界**：恶意仓库内容、恶意插件、私密 Key 泄露在本仓 `open-harness-v2.md §3` 中被显式排除在
  威胁模型外；此类观察最多记 ACCEPT/CLOSE 或 DEFER。
- **判定依赖画像**：README §1.1 的任何一维变化（多 scheduler、要求可用性、引入 CI、对外暴露、用户数上量）
  都会让 §6 的接受项与 §5 的部分 DEFER 项重新变成需要处理的缺陷。
