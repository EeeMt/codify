# Open-Harness V2 Code Review —— 判定汇总与修复顺序

> 审查日期：2026-09-12 · 审查目标：`dev @ cbad9e56` · 基线：`8081c946^` = `7b253fbf`（2026-08-20）
> 范围：`git diff 8081c946^..cbad9e56` —— 477 commits / 437 files / +74,905 −3,855（open-harness v2 全部改动）
> 判定标准与部署画像：[README.md](README.md) §1.1（内网离线 / 3 人 beta / 无 SLA / 唯一硬约束=历史统计数据不丢 / 反对过度防御）与 §3
> 明细见同目录 17 份专题文档；进度见 [PROGRESS.md](PROGRESS.md)。

**结果：165 条唯一问题（FIX_NOW 11 / FIX_IF_CHEAP 51 / DEFER 56 / ACCEPT-CLOSE 47）。**

## 1. 总体结论

V2 的架构落地质量高于“内部预览”的常见水平：协议分层、唯一终态、幂等 receipt、命令状态机、Kit 制品
fail-closed、迁移单头线性、硬切门禁都已实现，且有真实 PG、真实容器与真机任务证据；前端无 XSS 回归，
未发现 V2 引入的数据损坏或越权。

按本阶段画像判定后，**11 条需要现在动手（8 条阻断主路径或静默丢交付），47 条属于过度防御应书面关闭**，
其余 107 条为错误路径上的顺手项或待触发项。FIX_NOW 的共同点：改动都在个位数行、不引入任何新机制。

本汇总给出的执行顺序是「8 条阻断 → 切库前两条 SQL → 其余单行项 → 接受清单书面关闭」，而非按抽象
严重度全量收口；各档明细见 §3~§6。

## 2. 判定统计

### 2.1 各专题原始计数（与各文档 §1 一致）

| 文档 | 专题 | 问题总数 | FIX_NOW | FIX_IF_CHEAP | DEFER | ACCEPT/CLOSE |
|---|---|---:|---:|---:|---:|---:|
| 01-command-plane.md | 01 命令平面与并发门禁 | 13 | 1 | 3 | 3 | 6 |
| 02-event-contract.md | 02 事件契约与投影 | 10 | 1 | 3 | 3 | 3 |
| 03-pi-bridge.md | 03 Pi RPC Bridge 与原生事件 | 15 | 1 | 2 | 7 | 5 |
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
| 14-migrations-models.md | 14 Alembic 迁移与数据模型 | 6 | 0 | 1 | 3 | 2 |
| 15-deploy-ops.md | 15 部署编排与离线包 | 17 | 5 | 9 | 1 | 2 |
| 16-tests.md | 16 测试质量与覆盖 | 18 | 1 | 6 | 4 | 7 |
| 17-cross-cutting.md | 17 横切补充与范围外核查 | 7 | 0 | 4 | 0 | 3 |
| **合计** | 17 个专题 | **170** | **13** | **52** | **58** | **47** |

### 2.2 归并去重后（跨专题重复只记一次）

| 判定 | 数量 | 说明 |
|---|---:|---|
| FIX_NOW | 11 | 见 §3；下次真实使用前必须处理 |
| FIX_IF_CHEAP | 51 | 见 §4；顺手修，或与 §3 同批处理 |
| DEFER | 56 | 见 §5；触发条件出现即修 |
| ACCEPT/CLOSE | 47 | 见 §6；本画像下的过度防御，书面接受并关闭 |
| **唯一问题合计** | **165** | 170 减去 5 组跨专题重复 |

5 组重复（同一根因被两个专题独立发现，合并后取更靠前的判定）：

| 组 | 主条目 | 重复条目 | 合并后判定 |
|---|---|---|---|
| PI-01（3）| PI-01 | EVT-02 | FIX_NOW |
| PI-03（3）| PI-03 | RTB-02 | FIX_IF_CHEAP |
| OPS-02（15）| OPS-02 | SEC-02 | FIX_NOW |
| OPS-03（15）| OPS-03 | TST-01 | FIX_NOW |
| OCE-05（5）| OCE-05 | EVT-06 | DEFER |

另有两组「同源/同机制但刻意不合并」，各自独立计数（因此不影响 165 的口径）：

| 组 | 条目 | 不合并的理由 |
|---|---|---|
| 6 | SEC-01（13）× RUN-INFO-01（07） | 同一根因的两个面：SEC-01 覆盖自定义 Provider key 形态与 JSON `apiKey` 字段（含本区间新增的 `sanitize_json_value` 消费路径），RUN-INFO-01 覆盖已知前缀词表（`AIza`/`ghp_`/`hf_`/`xox*`）在归档事件流中的残留；修复动作不同，故分别记录 |
| 7 | PI-01（生产者产出非法 canonical 事件）× EVT-03（消费者不推进游标） | 同一现象的两个独立根因：只修生产者不解除「任何非法记录都能永久卡死 ingest」的脆弱性；只修 ingest 也不能让生产出的 payload 变合法。两者需各自合入并各自回归 |

### 2.3 过度防御集中在四处

| 簇 | 本画像为何不需要 |
|---|---|
| 并发/一致性不变量（租约续期、跨会话 CAS、显式释放、多 dispatcher 顺序） | 生产只有**一个** `codify-scheduler` 容器，owner 串与 task 绑定、重启即重领；command 行不喂统计，坏掉的只是审计标签与一条 ERROR 日志 |
| 契约纯度与文档字面一致（projector 单写者、raw_archive 定位符、两侧词表字节一致） | 这些是冻结文档与实现的措辞差异；按字面改反而会重开「未发送命令永久 queued」的窗口，正确做法是改文档 |
| 制品可复现与完整供应链门禁（归档字节、LD_LIBRARY_PATH 硬门禁、verifier 宽严） | 离线包一年手工构建/安装几次，identity 取 manifest 摘要；真正的保证是 launcher 与任务期校验 |
| 覆盖纯度与非生产平台断言（路由→服务→DB 全链、Dockerfile 子串、非 Linux 进程回收、PG 口令集中治理） | 无 CI、单机开发、生产是 Linux；这些不改变 3 个用户看到的行为 |

安全项同理：可信内网下，catalog 作用域、OIDC 关闭导致的全员不受限、容器内 argv/env 可见凭据，影响面
等于零或已声明接受（见 §6）。

## 3. FIX_NOW 清单（11 条，按专题排序）
### CMD-04 `created_by` 列宽 64 < `username` 上限 255，长用户名使 PUT 直接 500
- **位置**（`01-command-plane.md`）：`backend/app/models.py:737`（对照 `:1480`）、`backend/alembic/versions/074_open_harness_v2.py:103`、`backend/app/api/task_command_routes.py:69-72`
- **影响**：GitLab/OIDC 用户名长度 > 64 的用户（自建 GitLab 允许至 255）**完全无法发送命令**，每次 PUT 500；SQLite 不校验长度，故单测不会暴露该问题。
- **最小动作**：`created_by` 放宽到 `String(255)` + 一条迁移（与仓库其它 username 列一致）

### PI-01 原生拒绝 ACK 产出的 `control.command.rejected` 缺 `rejection_message`，导致投影 ingest 永久卡死
- **位置**（`03-pi-bridge.md` ≈ `02-event-contract.md` EVT-02，同一根因）：`deploy/worker-entrypoint/harness/adapters/pi_events.py:603-613`
- **影响**：拒绝事件在流中位于 `agent_settled` 之前（probe 证据：`docs/harness-probes/v2/pi/steer.raw.jsonl` 第 10 行是 ACK、第 104 行才是 `agent_settled`）。
- **最小动作**：`pi_events.py:610`：`rejection_message` 缺省回退 `record.get("error")` 或固定文案（1 行）；不必改 projector 的隔离机制

### RUN-01 V2 manifest 收窄 capability 词表后，`run_text`/`codegraph` 判定永久失效
- **位置**（`07-runner-infra.md`）：`deploy/worker-entrypoint/harness/manifest.json:29-35`（claude）、`:90-96`（pi）；消费方 `deploy/worker-entrypoint/harness/runner.sh:94-99,194-200`、`deploy/worker-entrypoint/codegraph.sh:73-79`、`deploy/worker-…
- **影响**：V2 claude（默认 harness）任务中，(a) commit message 恒走 `main.sh:159-166` 的硬编码兜底文案（日志 `Harness commit message generation failed with exit code …; usi…
- **最小动作**：① `runner.sh:194-200` 的能力判定 `codify_harness_capability_enabled "run_text"` → `declare -F adapter_run_text`（4 个 adapter 都定义了该函数；不支持的 codex 版返回非零，自然回落，与今天行为一致）。② `codegraph.sh:73-79` 的 capability 分支 → 按…

### RUN-02 canonical event writer 只接受 argv 传 payload，超 ~128 KiB 即整条链路失败
- **位置**（`07-runner-infra.md`）：`deploy/worker-entrypoint/harness/events.py:369-376`；写入方 `deploy/worker-entrypoint/harness/common.sh:17-24`、`deploy/worker-entrypoint/harness/adapters/claude_events.py:134-149`
- **影响**：两条独立后果。
- **最小动作**：`events.py` 增 `--payload-stdin`（`main()` 里 `json.loads(sys.stdin.read())`，~4 行）；`common.sh:17-24` 的 `codify_emit_event` 与 4 个 adapter 的 `_emit` 改为 `input=payload` 传 stdin（各 1 行）。无 payload 大小上限、无截断、无共享…

### DEL-01 终态失败原因被归档的 provider 错误覆盖
- **位置**（`11-delivery-lifecycle.md`）：`backend/app/api/tasks.py:657-668`（另见 `:709-718`）
- **影响**：两类终态的失败原因与事实不符：(a) 取消的任务 —— canonical/生命周期写入的是 `"Cancelled by user"`（`worker_task_lifecycle.py:1301-1309`），持久化与接口却显示 provider 错误（如 "Pi provi…
- **最小动作**：仅当 canonical 失败原因为空（legacy Pi 记录才是 raw payload）时才用归档 detail 兜底，且排除 cancelled / timeout / 交付失败；归档 detail 另存字段。改 2 处条件：`api/tasks.py:657-668`（读，含 `:709-718` 的 failure_summary）、`core/worker_results.py:58…

### SEC-02 git 历史仍含真实凭据（HEAD 已清理但未吊销，仍可完整检出）
- **位置**（`13-security.md` ≈ `15-deploy-ops.md` OPS-02，同一根因）：`deploy/.env.test:6-7`
- **影响**：任何拥有仓库读权限（含 CI、镜像构建上下文、历史 clone）者可取得：① GitLab bot PAT（按 `docs/architecture/open-harness-v2.md` 的部署模型，该 token 对所有受管项目有写权限）；② 一个可用的模型 Provider…
- **最小动作**：吊销/轮换三类凭据；`CONFIG_ENCRYPTION_KEY` 换新后按需重新录入受影响密文（provider key / webhook secret）。建议过重：`git filter-repo` 清理历史 + 通知所有 clone/CI 重拉没必要（凭据死了即可）

### OPS-01 离线包 `start.sh` 因两个必填插值变量缺失无法启动
- **位置**（`15-deploy-ops.md`）：`deploy/offline-bundle/docker-compose.yml:30`（另见 `:79`、`:128`）
- **影响**：按 README/CONFIGURATION 的离线部署步骤在目标主机执行 `./scripts/start.sh`，会在插值阶段直接失败，整栈（含不启用 `maintenance` profile 的默认路径）都起不来；这是离线交付的主路径。
- **最小动作**：`config/.env.offline.example` 加 `HARNESS_EXECUTION_MODE=v2_only`；offline compose 的 `${MIGRATION_TARGET:?...}` → `${MIGRATION_TARGET:-}`（与 OPS-07 同一处改动）

### OPS-03 mock 集成 compose 仍写 `dual_canary`，backend/scheduler 启动即崩
- **位置**（`15-deploy-ops.md` ≈ `16-tests.md` TST-01，同一根因）：`backend/tests/mock_integration/docker-compose.mock-test.yml:69`（另见 `:113`）
- **影响**：`make test-mock-integration`、`make test-mock-integration-parallel`（`Makefile:276/:304`）以及
- **最小动作**：两行 `dual_canary` → `v2_only`

### OPS-04 E2E compose 的 migration 目标落后 4 个 revision，E2E 数据库 schema 与代码不符
- **位置**（`15-deploy-ops.md`）：`deploy/docker-compose.e2e.yml:41`
- **影响**：`docker-compose -f docker-compose.e2e.yml up` 后数据库停在 075，backend 一旦读写 tasks
- **最小动作**：`docker-compose.e2e.yml:41` 默认值改 `${MIGRATION_TARGET:-head}`（1 词）

### OPS-05 `make worker-runtime-bundle-export` 未传 `--env-file`，文档化的 L3 导出命令直接失败
- **位置**（`15-deploy-ops.md`）：`Makefile:54`
- **影响**：`docs/DEPLOYMENT.md` §10.1 与 `docs/runbooks/multi-harness-rollout.md` §5.1 记载的
- **最小动作**：`Makefile:54` 加 `--env-file $(PROJECT_ROOT)/deploy/.env.test`（1 行）

### OPS-08 部署文档仍把 `dual_canary` 写成合法值，按文档执行会启动失败
- **位置**（`15-deploy-ops.md`）：`docs/DEPLOYMENT.md:134`（另见 `:20`、`:64`）
- **影响**：运维照 DEPLOYMENT.md §4.3 / DEVELOPMENT.md 执行，Backend 与 Scheduler 会在启动校验处
- **最小动作**：6 处 `dual_canary` → `v2_only`，并注明该值随 hard cut 删除

## 4. FIX_IF_CHEAP 索引（51 条）

只在错误路径或边界触发，且修复 ≤ ~6 行、不引入新机制。空闲时顺手修；否则与 §3 同批处理。

| ID | 文档 | 问题 | 最小动作 |
|---|---|---|---|
| CMD-01 | 01 | command 状态 helper 的 “CAS” 判定读本会话缓存行，跨会话终态只能靠 CHECK 约束挡下 | 只给会与 gate 竞争的 3 处终态写 + `requeue_pre_send_failure` 加 `WHERE status = :exp… |
| CMD-03 | 01 | `retry` 结果无上限、无退避、无审计，队首可被无限重试并阻塞整条队列 | retry 分支加 1 行 `logger.warning`（含 `delivery_attempts`）；不加退避/上限 |
| CMD-06 | 01 | pump 持久化 `native_rejected`（非冻结枚举），同一拒绝在 API 与事件流显示不一致 | `PUBLIC_REJECTION_MESSAGES`（±`REJECTION_CODES`）加 `native_rejected`，2 行 |
| EVT-03 | 02 | 单条非法记录使整条事件流永久卡死，Task 被误判为缺少终态 | chunk 循环内对 `V2_AUDIT_EVENT_TYPES` 校验失败降级为 1 条 diagnostic 并继续推进游标（复用已有常量… |
| EVT-05 | 02 | `WorkerEventProjector` 类 docstring 与实现不符 | 1 行 docstring |
| EVT-INFO-01 | 02 | `[V1 遗留]` JSONL 解析用 `str.splitlines()`，Unicode 行分隔符会切碎单条记录 | `iter_complete_jsonl_records` 用 `buffer.split("\n")` + remainder（worker … |
| PI-02 | 03 | 初始 `prompt` 被 Pi 拒绝时只记 diagnostic、不产生 terminal，任务挂到超时 | translator 兜底前单列 `prompt` 且 `success:false` → 置 `terminal_failure`（~4 行）… |
| PI-03 | 03 | `pi/v1` harness_options 无任何消费者：thinking_level / steering_mod… | 懒做法：从 `pi/v1` 去掉 `thinking_level`（或映射 `--thinking`）。【建议过重】 review 要求顺带接 … |
| PI-04 | 03 | Managed Skills 被物化到 Pi 不会扫描的目录，`task_skills` 静默无效 | 物化到 Pi 实际扫描位置（`${CODIFY_PI_CLI_HOME}/.pi/agent/skills` 或 `.agents/skills… |
| OCB-01 | 04 | Session 状态兜底查询使用了 1.18.19 不存在的路由 | `status()` 改 `GET /session/status` + 三处审计模板 + 按 sessionID 取值（~5 行） |
| OCB-02 | 04 | 快照凭据缺失时静默跳过 provider 配置物化 | 写 `opencode.json` 的三元条件改为显式 fail-closed `return 1` + stderr 说明（~6 行） |
| OCE-01 | 05 | abort 形状（assistant `error:true`）被当作成功收敛 | 记 `errored_message_id`，仅当它仍是最后一条 assistant 消息时收敛失败（~6 行）。【建议过重】 不要按 revi… |
| OCE-02 | 05 | delta 去重按后缀比较，静默吞掉真实重复内容 | 用快照水位（`snapshot_len`+flag）替代 `endswith` 去重，两处 delta 路径（~6 行） |
| OCE-03 | 05 | `session.idle` + 空文本回合被判 `protocol_error` | 文本为空仍成功收敛，只保留“必须是 assistant”校验（~2 行） |
| OCE-04 | 05 | SSE 分片逐块解码，多字节字符被替换成 U+FFFD | `codecs.getincrementaldecoder("utf-8")` + EOF flush（~3 行） |
| CX-03 | 06 | Codex App Server 的 JSON-RPC 成功响应被记为 `unknown_raw_event`，响应分支… | `codex_events.py:398` → `if "method" in record or "id" in record:` |
| RTB-01 | 08 | readiness 作用域判别与 V2 校验写入不一致，创建/切换/CI 门禁失效 | `worker_runtime_readiness.py:472` 的 `profile_requires_content_inventory(… |
| KIT-01 | 09 | 逐 Harness bridge 自检的失败被静默丢弃，该门禁实际不生效 | host_mount 分支**显式跳过**自检（该分支未挂载 `${HARNESS_HOST_PATH}`），其余分支加 ` |
| KIT-03 | 09 | LD_LIBRARY_PATH 隔离"硬门禁"可静默跳过，与文档声称的"每对 Kit+镜像都证明"不符 | 去掉探测命令的 ` |
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
| OPS-09 | 15 | 多 Harness 上线 runbook 仍以 dual-canary/legacy V1 overlay 为前提，回滚… | 文件头加一行“dual_canary/V1 overlay 段落作废；回滚=回到上一个 V2 release”，删掉 §8 第 7 步 V1 s… |
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

## 5. DEFER 索引（56 条）

真实但本画像可容忍（可停机、可重跑、可手工介入）。触发条件出现时按条目的「最小动作」处理。

| ID | 文档 | 问题 | 何时再管 |
|---|---|---|---|
| CMD-05 | 01 | 空文本命令被 API 接受、被容器内 client 拒绝，且公开消息套用错误的 code 文案 | 前端唯一的发送入口已 `:disabled="!text.trim()"` 且发送前 `trim()`（`TaskSteer… |
| CMD-INFO-04 | 01 | `create_task_attempt` 复用已有 attempt 时忽略传入的 `control_state… | 要“容器存活但 gate 已 closed”才致命，当前无该路径（retry 新建 Task、resume 时 gate 仍… |
| CMD-INFO-06 | 01 | 长会话下的 identity map 陈旧同样作用于 projector 的 gate 判定（CMD-01 同一… | 与 CMD-01 同根因、逐向推演无可证后果，只影响将来新增分支 |
| EVT-INFO-02 | 02 | `[V1 遗留]` tool 输入存在「同一字段两条清洗强度」的写法 | 可信内网 + 无恶意租户，worker 侧已做嵌套清洗，未观察到泄露路径 |
| EVT-INFO-04 | 02 | 归档读取在事件循环内同步解压整个 tar.gz | 终态解析时同步解包，只造成秒级抖动；无 SLA、停机可接受 |
| PI-05 | 03 | `pi_adapter_terminate` 既不发原生 abort，也不作用于 Pi/owner 进程 | 取消时 owner/Pi 成孤儿只多烧几秒额度，容器回收兜底；且与 claude 同形状（非 Pi 特有） |
| PI-06 | 03 | `message.delta` 的 payload 键与 projector 读取的键不一致（`content… | 仅在 `message_end.stopReason` 不在 (stop,end_turn) 时丢日志文本，raw arch… |
| PI-07 | 03 | 原生拒绝的审计码与实际原因不一致（`native_rejected` 不在拒绝码表内） | 只影响审计码与前端兜底文案，终态/交付/统计均不受影响 |
| PI-08 | 03 | `pi_bridge.PiBridge` 是死代码，且与线上 owner 的策略不同 | 死代码不影响运行，只误导后续维护者 |
| PI-INFO-02 | 03 | follow-up 重开 accepting 依赖“settled 之后仍会开新 run”，且无兜底 | 只有“settle 后送 follow_up 且 Pi 假 ACK 不开新 run”才挂，probe 未覆盖、Pi 非默认… |
| PI-INFO-03 | 03 | JSON 行先 sanitize 再解析，与 `sanitize_json_value` 的既有约定相悖 | 与 claude/codex/opencode 同病、probe 从未观察到记录损坏，属跨 harness 加固，单改 Pi… |
| OCB-03 | 04 | 取消/超时路径的硬停 TERM 到不了 Harness（公共 Runner 机制） | 公共 Runner 机制（claude 同样打不到），容器级回收兜底，只多烧几秒额度 |
| OCB-INFO-03 | 04 | 子代理（child session）事件被会话过滤丢弃，用量/诊断不完整 | 用 `task` 工具的任务变多且用量要精确 |
| OCE-05 | 05 | `model` 恒为 null、从不发 `model.resolved` | `task.model_name` 恒 null，但系统统计有 snapshot `configured_model` 兜底… |
| OCE-06 | 05 | `message.delta` 用 `content`，projector 读 `text` | delta 不进投影缓冲，而 `message.completed` 自带完整 `text` → 当前无可见影响（（`[V1… |
| OCE-INFO-01 | 05 | `session.status(retry)` 对通用 rate-limit 标记即刻收敛终态 | 需真实 retry 样本才能定案；瞬时 429 让任务早失败=可重跑，非数据损坏 |
| OCE-INFO-03 | 05 | `busy` / `idle_seen` 写了不用 | 纯清理（两个只写字段），无功能影响 |
| OCE-INFO-04 | 05 | part 无 `id` 时多个 text 快照互相覆盖 | 需要真实 `TextPart` 抓包才能定案（fixture 已脱敏），当前无证据线上不带 `id` |
| CX-01 | 06 | Claude 每个 text delta 派生一个 canonical 事件子进程，长输出任务线性变慢 | 纯性能：本机实测 58.4 ms/事件（小流）/ 59.7 ms（411 行流），381 条 delta ≈ +22s，占 … |
| CX-02 | 06 | Codex 取消路径未落地：adapter `terminate` 空实现、runner 无信号 trap，`t… | 取消/超时终态本来就正确（finalizer 合成 `cancelled/timeout`，writer 拒第二终态）；进程… |
| CX-INFO-01 | 06 | 打开 partial messages 后 legacy `tool_calls` 数组双写 | `tool_calls` 双写但唯一消费者只读 `.result`，且 `/tmp/codify-harness-outpu… |
| CX-INFO-02 | 06 | Claude thinking 块跨消息交错时会被误判为 interrupted | 前提（主/子 agent 消息在同一 attempt 内交错）需要真实 CLI 时序才能证实；影响仅 thinking 占位… |
| CX-INFO-03 | 06 | Codex `reasoning_id` 缺少 turn 维度 | 需 App-Server 真实帧判定 item id 是否跨 turn 复用；仓库内无任何原生帧捕获 |
| RUN-04 | 07 | `bridge.py` stub 的 30s 超时与其自身文档/真实 ACK 语义矛盾（当前无生产调用方） | `bridge.py` 是随 bundle 下发的 stub、现网零调用方（仅单测 import 做 capability … |
| RUN-INFO-02 | 07 | timeout marker 与 `run.completed` 的窄竞态会让终态事件携带 `failure.k… | 毫秒级窗口，且后端有 `exit_code`/finalization/`validate_result_v2` 三重校验兜… |
| RUN-INFO-04 | 07 | 双次初始化会启动第二个 model proxy，第一个 PID 被覆盖后泄漏 | 泄漏的第二个 model proxy 只活在即将退出的容器内，且两个代理读同一份冻结 options、不会串号 |
| RUN-INFO-05 | 07 | [V1 遗留] `append_runtime_event` 是无锁直写 `event.jsonl` 的残留助手… | V1 死代码、全仓无调用方；删了更干净但无功能意义 |
| RTB-03 | 08 | §13.4 容器错误重探被移除后遗留不可达代码与失效文档 | 残留 3 个不可达符号 + 1 个不可达 outcome 分支 + 与 §13.4 矛盾的文档；功能上有 Scheduler… |
| RTB-INFO-01 | 08 | 未注册命名空间与非选中 Harness 的 options 被静默接受 | 冻结快照/digest 携带无效数据（未登记命名空间透传、claude 的 `claude/v1` 无校验器），无运行时漏洞… |
| RTB-INFO-02 | 08 | capability 上界校验只拒绝布尔 `True`，非布尔真值绕过且消费方判定不一致 | 需仓库内把 manifest 写成 `"false"` 这类非布尔值才触发，且 Kit 侧 `validate-runtim… |
| KIT-02 | 09 | 两个安装器同源漂移：文档化的离线安装路径缺少模型代理与 harness inventory 的 fail-clo… | 文档化安装器少两道 fail-closed，但二进制字节已被 content inventory 与任务期 launcher… |
| KIT-06 | 09 | Kit 侧校验器与后端 inventory 契约宽严不一致（路径归一化 / 额外字段） | 只剩“后端拒额外字段、Kit 侧不管”，仓库自产 manifest 两边都匹配 → 无现实影响 |
| KIT-08 | 09 | `install.sh` 的校验和工具回退不完整，无 `sha256sum` 的主机中途失败 | 只在无 coreutils 宿主跑仓库内 install.sh 才触发，且是响亮的 `command not found… |
| KIT-INFO-04 | 09 | root-only 的安装器测试与 `install.sh` 新增门禁可能已脱节 | root-only 参数化测试的合成 Kit 无 `model_proxy`/`harness/`，root 下必然失败；C… |
| MEP-02 | 10 | `provider_options` 保留字段契约未覆盖 Task 创建路径：遗留行会让已冻结的保留参数被代理静… | `provider_options` 是 064 新增列，保留键仅在“064 后、写入校验前”窗口可能写入；命中后任务照跑… |
| MEP-04 | 10 | 重命名未覆盖用户可见术语：Provider 面板与 i18n 仍以 "Wire Protocol / Wire … | 纯文案（“Wire 协议”），不出现在 API/DB/快照，仅面板标签，3 个可信同事看得懂 |
| DEL-02 | 11 | 交付采集的软失败原因不会进入任何事件或 Task 字段 | 只有 issue 显式开了浅克隆/`blob:none`（`issues.git_clone_depth` 默认 NULL… |
| DEL-03 | 11 | `task_timeout` 共享 helper 未被生产代码使用，派生值在 API 内各写一遍 | 死 helper + deadline 公式复制 3 份，零功能影响，本阶段不值得单独一轮改动 |
| DEL-04 | 11 | 冻结 harness options 的序列化 helper 被复制成两份 | 两份逐行相同的 helper，当前输出一致，只是未来漂移风险 |
| DEL-05 | 11 | `ci_failure_collector` 调用参数意外去缩进 | 纯缩进残留，`ast.parse` 与单测均通过 |
| DEL-INFO-01 | 11 | `[V1 遗留]` 取消意图会把「已失败的终态」改写成 CANCELLED 并覆盖原因 | V1 遗留竞态：取消意图把已失败终态改写成 CANCELLED；真实交付原因仍在 `worker_metadata.git_… |
| FE-04 | 12 | 思考耗时 tooltip 硬编码英文，未走 i18n | 悬停 tooltip 硬编码英文，纯文案，不影响操作 |
| FE-05 | 12 | OpenCode `model_variant` 输入缺少与后端一致的客户端校验，422 原因被丢弃 | 表单缺正则校验导致 422 只显示通用文案；FE-02 把 detail 透出后大半自愈，正则属额外代码 |
| FE-06 | 12 | 每秒把 `nowMs` 下发给每一行思考/回复行，长日志下形成 1Hz 全列表重渲染 | 长日志停留「事件流」页签时 1Hz 重渲染，无实测卡顿、不阻塞任何工作 |
| FE-INFO-01 | 12 | `control_state='disabled'` 时 gate 徽标渲染为空 | 当前不可达（需 capability 与 `control_supported` 判定不一致） |
| FE-INFO-02 | 12 | 未知 `push.status` 被渲染为“推送失败” | 未知 `push.status` 兜底成「推送失败」，后端枚举冻结 5 值，当前不可达 |
| FE-INFO-03 | 12 | `showCommitRecord` 在“有 push 结论但无提交列表”时隐藏整张提交记录卡 | 「确认态但无提交列表」组合是否会被 worker 产出未验证；数据仍在 DB，只是 UI 不显示 |
| FE-INFO-04 | 12 | `command-delivered` 事件无消费方 | 删除 `command-delivered` emit（1 行） |
| MIG-02 | 14 | ORM 把 `runtime_mode` 默认值改为 `mounted_kit`，数据库默认值仍是 `baked… | 出现非 ORM 写入的数据脚本 |
| MIG-INFO-03 | 14 | Scheduler 启动即 `alembic upgrade head`，硬切 runbook 的“指定 rev… | Scheduler 启动迁 head 是团队有意收敛（backend 固定 `AUTO_MIGRATE=false`，无并发… |
| MIG-INFO-04 | 14 | `_validators.py` 与 `config_runtime.py` 各有一份 `_validate_c… | `_validators._validate_config_value` 是无人调用的死副本（生产走 `config_run… |
| OPS-INFO-06 | 15 | 运行时暴露面小结（含 V1 遗留项） | 5432 全接口发布、硬编码口令、8001 无鉴权在可信内网 + 无 SLA 下可接受；无日志限额只在长期运行后才可能吃满磁… |
| TST-02 | 16 | 命令平面核心断言只在"可达内网 Postgres"时执行，且无 CI 门禁 | 唯一开发机上内网 PG 可达、50 条断言确实在跑（review 实跑 18+32 passed）；"绿灯但全跳过"需要第二… |
| TST-INFO-01 | 16 | 真实子进程 + 1s 边界等待的潜在 flake | 未观察到失败，仅潜在 flake。 |
| TST-INFO-02 | 16 | mock_e2e 的 schema 来自 ORM 而非迁移 | mock_e2e 用 ORM 建表是 V1 遗留的快速取舍；硬要求由切库时的真迁移保证，不由 mock_e2e 保证。 |
| TST-INFO-03 | 16 | 命令测试依赖"module 级共享 DB + 随机 owner"的隐式约定 | 隐式约定当前自洽（32 passed）。 |

## 6. ACCEPT/CLOSE## 6. ACCEPT/CLOSE 清单（47 条，按簇）

本画像下属于过度防御：它们要求的不变量在「单 scheduler、内网、无 SLA、3 人 beta、无 CI」下不需要。
**书面接受并关闭**；出现右侧触发条件时重开。

| 簇 | 条目 | 触发条件 |
|---|---|---|
| 并发/一致性不变量（单 `codify-scheduler` 画像不可达） | CMD-02、CMD-07、CMD-INFO-02、CMD-INFO-03、CMD-INFO-05、TST-03、TST-05 | 出现第二个 scheduler/dispatcher；或要求可用性；或真出现命令永久 `queued` |
| 契约纯度高 / 文档与实现字面不一致（改文字即可） | EVT-01、CMD-INFO-01、EVT-04、EVT-INFO-03、RTB-04、RTB-INFO-03、RUN-03、RUN-INFO-01、RUN-INFO-03、OCB-INFO-02、KIT-INFO-02 | 重写冻结契约文档、放宽 CHECK 约束、或接入公网 provider |
| 不可达，或已被真机证据证伪 | PI-INFO-01、PI-INFO-04、PI-INFO-05、PI-INFO-06、PI-INFO-07、OCB-INFO-01、OCE-INFO-02、KIT-INFO-01、KIT-INFO-05、KIT-INFO-06、MEP-INFO-01、MEP-INFO-02、OPS-INFO-01、OPS-INFO-04、MIG-INFO-01、MIG-INFO-02、TST-INFO-04、TST-INFO-05 | 换基础镜像（slim/busybox）、接入公网 provider、仓库来源变不可信 |
| 安全加固（内网可信 + 无 SLA） | SEC-04、SEC-09、SEC-INFO-01、SEC-INFO-02 | 出现外部协作者/多团队隔离/启用 OIDC、API 新增 exec/stop、或威胁模型变更 |
| 制品可复现 / 供应链（一年手工几次） | KIT-07 | 引入 CI/合规审计、或需要无人值守发布 |
| 测试覆盖纯度（无 CI、单机开发） | TST-08、TST-11、TST-12、XC-05、XC-INFO-01、XC-INFO-02 | 上 CI、出现第二台开发机、或真出现孤儿进程泄漏 |

## 7. 修复顺序

### Tier-1：8 条阻断项（一次小 PR）

| # | 条目 | 最小动作 | 影响面 |
|---|---|---|---|
| 1 | PI-01（≈ EVT-02） | `pi_events.py` rejected 分支补 `rejection_message` 缺省（1 行） | Pi 通道；事件流永久卡死 + 丢统计投影 |
| 2 | RUN-02 | `events.py` 加 `--payload-stdin`，`common.sh` 与 4 个 adapter 走 stdin（不给 payload 加上限/截断） | 所有 harness；大 payload 时成果不提交不推送 |
| 3 | RUN-01 | `runner.sh` 的 run_text 判定改 `declare -F adapter_run_text`；`codegraph.sh` 按 harness key 判定（2 行） | 默认 harness；commit message / MR summary / CodeGraph 静默失效 |
| 4 | DEL-01 | 收窄归档 detail 对 `error_message`/`failure_summary` 的覆盖条件（2 处） | 所有失败/取消任务；真实失败原因被 provider 重试错误盖住 |
| 5 | CMD-04 | `created_by` 放宽 `String(255)` + 一条迁移 | 命令 API；长用户名用户完全无法发命令 |
| 6 | OPS-01（含 OPS-07 同处） | 离线包模板补 `HARNESS_EXECUTION_MODE=v2_only`；`${MIGRATION_TARGET:?...}` → `${MIGRATION_TARGET:-}` | 内网生产唯一铺装路径；插值阶段即失败 |
| 7 | OPS-03（≈ TST-01） | mock 集成 compose 两处 `dual_canary` → `v2_only` | 无外网依赖的端到端验证入口整层不可跑 |
| 8 | OPS-04 | `docker-compose.e2e.yml` 迁移目标改 `${MIGRATION_TARGET:-head}` | E2E 栈必然 `UndefinedColumn` |

### Tier-2：其余 FIX_NOW（同上 PR 顺手）

| 条目 | 最小动作 |
|---|---|
| OPS-05 | `Makefile` 的导出目标补 `--env-file`（1 行） |
| OPS-08 | 6 处文档 `dual_canary` → `v2_only` |
| SEC-02 | 吊销/轮换 git 历史中的 GitLab PAT、Provider key、`CONFIG_ENCRYPTION_KEY`（0 代码，纯运维） |

### Tier-3 / Tier-4

- **Tier-3**：§4 的 51 条 FIX_IF_CHEAP —— 空闲即修，不进发布门禁。
- **Tier-4**：§5 的 56 条 DEFER 与 §6 的 47 条 ACCEPT/CLOSE —— 记录在案；ACCEPT 项需在团队内明确
  「已知并接受」，触发条件出现时按条目重开。

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
| 2 | OCE-01 abort 形状 | 读 error 分支 + idle 成功门 + probe README | 确认（端到端未运行） → FIX_IF_CHEAP |
| 3 | OCB-01 状态路由 | 从固定二进制抽取 `/session/*` 路由表 | 确认路由不存在 → FIX_IF_CHEAP |
| 4 | RUN-01 capability 词表 | 对比 V1/HEAD manifest + `jq -e` 复现 | 确认 → FIX_NOW |
| 5 | RUN-02 argv 上限 | 读 `events.py` 入口 + `common.sh` + ARG_MAX 既有注释 | 确认（未在 Linux 复现 E2BIG） → FIX_NOW |
| 6 | RTB-01 作用域不一致 | 读读/写两侧函数与默认值 | 确认 → FIX_IF_CHEAP（严格 409 前置本非必需） |
| 7 | OPS-01 离线包 | 实跑 `docker compose config` → rc=15（先报 `HARNESS_EXECUTION_MODE`，补上后再报 `MIGRATION_TARGET`） | 复现 → FIX_NOW |
| 8 | OPS-02/SEC-02 历史凭据 | `git show` + 形状统计（不明文回写文档） | 确认（13-security.md 已脱敏） → FIX_NOW |
| 9 | OPS-03/TST-01 `dual_canary` | grep + 配置校验 | 确认 → FIX_NOW |
| 10 | OPS-04 E2E 迁移目标 | grep + alembic head（079） | 确认落后 4 个 revision → FIX_NOW |
| 11 | KIT-01 bridge 自检被吞 | 读 `verify-runtime.sh` 调用形态（`if ! run_one`） | 确认 errexit 被抑制；原建议「加 `\|\| return 1`」会破坏 break-glass 分支，最小动作已改写 |
| 12 | CMD-01「CAS」非真 CAS | 依据 SQLAlchemy identity-map 语义复核 T01 推理 | 采信（跨会话终态靠 CHECK 兜底）→ FIX_IF_CHEAP（画像下调） |
| 13 | FE-01 en 缺键 / FE-03 command_id 每次重生成 | grep 两侧语言包 + 读 `api/tasks.ts` | 确认 → FIX_IF_CHEAP |
| 14 | 按画像重判全部 170 条 | 7 组并行复核「现在做不做」 | 全部落到四档判定，见 §2~§6 |
| 15 | T14 的 server_default 漂移 | 采信其真实 PG 探针结论 | 采信 → MIG-01 顺手删两行 |

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
