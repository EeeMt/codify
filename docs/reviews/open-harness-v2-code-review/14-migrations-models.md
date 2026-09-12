# 14 Alembic 迁移与数据模型 —— Code Review

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56`（`dev @ cbad9e56`，2026-09-12） |
| 迁移文件（全部新增，+424/-0） | `backend/alembic/versions/074_open_harness_v2.py` (+198)、`075_pi_command_dispatch_journal.py` (+68)、`076_v2_worker_image_identity.py` (+30)、`077_v2_worker_kit_identity.py` (+40)、`078_remove_provider_driver.py` (+27)、`079_task_execution_timeout.py` (+61) |
| 模型/契约文件 | `backend/app/models.py` (+165/-13)、`backend/app/api/task_schemas.py` (+11)、`backend/app/api/_validators.py` (+18/-3)、`backend/app/api/analytics_queries.py` (+1/-1)、`backend/app/api/analytics_responses.py` (+3/-3) |
| 交叉核查文件（只读引用，非本文档归属） | `backend/app/core/task_harness_commands.py`、`worker_command_pump.py`、`task_command_gate.py`、`harness_attempts.py`、`worker_task_lifecycle.py`、`worker_shared_configuration.py`、`worker_kit.py`、`runtime_config.py`、`config.py`、`api/providers.py`、`api/task_update_service.py`、`deploy/docker-compose.yml`、`deploy/scripts/run-migration-owner.sh`、`docs/superpowers/plans/2026-08-21-open-harness-v2-implementation-plan.md` §4.1/§8.6 |
| 审查方法 | ① 静态阅读 HEAD 完整文件（非仅 diff）+ 全表列级 ORM↔迁移逐条比对；② 迁移链/契约对照（计划 §4.1、§8.6、`open-harness-v2-phase1-design.md`、timeout 设计规格 §10）；③ **真实 PostgreSQL 验证**：在开发库 `192.168.50.129:5432` 上创建一次性库执行 `alembic upgrade head`（001→079）、`compare_metadata` 列级比对、`pg_constraint`/`pg_indexes` 转储、CHECK 触发探针、079 旧配置转移探针、ORM/裸 SQL 双路径插入探针，脚本置于 `/tmp`（仓库零改动），库已全部 `DROP`；④ 窄范围单测（仅迁移相关文件） |
| 实际运行的命令 | `cd backend && .venv/bin/python -m pytest tests/unit/test_075_migration.py tests/unit/test_077_migration.py tests/unit/test_078_migration.py tests/unit/test_079_migration.py -q` → **11 passed**；`... tests/unit/test_074_migration.py -q -rs` → **5 passed in 15.71s**（真实 PG，073→074 升级 + 每例回退重挂）；`/tmp/parity*.py`（真实 PG，见 §3.2 各条） |
| 未覆盖 | V1 期迁移（≤073，仅在被 V2 依赖时引用）、迁移运行时代码的功能正确性（命令泵/投影/readiness 算法属 T01/T02/T08）、部署编排与 preflight 归属（T15）、前端（T12）、全量测试与构建（本次不运行） |

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 0 |
| FIX_IF_CHEAP | 1 |
| DEFER | 3 |
| ACCEPT/CLOSE | 2 |

V2 迁移层结构正确、契约自洽：6 个新迁移构成单头线性链（HEAD 仅 `079_task_execution_timeout`），真实 PostgreSQL 上 `alembic upgrade head` 一次通过且重复执行幂等，CHECK/唯一约束/索引逐条落位，破坏性重命名与 roll-forward-only 降级拒绝同计划/架构文档一致。本轮 **FIX_NOW 为 0**；唯一 **FIX_IF_CHEAP** 是 MIG-01（ORM 声明 `server_default=0` 而 076/077 已删该默认值）。6 项按「硬切可停机、数据可重跑、内网 3 人」画像处置：3 项 DEFER、2 项书面接受并关闭（079 不回填历史 RUNNING Task，078 的缺口属文档而非缺陷）。

**本专题触发条件**：
- 出现绕过 ORM 写入 `worker_profiles` 的数据脚本（MIG-02 的 `runtime_mode` 默认值倒挂）

## 2. 问题清单

### MIG-01 ORM 声明 `server_default=0`，但 076/077 迁移已把该默认值删除
- **判定**：FIX_IF_CHEAP —— 只影响绕过 ORM 的写入，本项目 Profile 全走 ORM/API
- **位置**：`backend/app/models.py:1056-1058`、`backend/app/models.py:1067-1069`（提交 `cda8e6ee`/`b1cf4488`）与 `backend/alembic/versions/076_v2_worker_image_identity.py:26`、`backend/alembic/versions/077_v2_worker_kit_identity.py:34`
- **证据**：ORM 声明 `v2_worker_image_identity_generation` / `worker_kit_identity_generation` 为 `Integer, nullable=False, default=0, server_default=text("0")`；迁移则在同一 revision 内先加列带 `server_default="0"`（回填历史行），随后 `op.alter_column(..., server_default=None)` 显式 `DROP DEFAULT`。真实 PG（`alembic upgrade head` 后）`information_schema.columns.column_default` 中这两列**没有任何默认值**，而 `worker_profiles.runtime_mode`、`harness_options`、`task_harness_attempts.control_state` 等有。后果在真实库上可复现：
  - ORM 插入 `WorkerProfile(name, image)` → `mounted_kit` / generation `0 0`（Python 侧默认生效，正常）；
  - 裸 SQL `INSERT INTO worker_profiles (name, image) VALUES (...)` → `asyncpg.exceptions.NotNullViolationError: null value in column "v2_worker_image_identity_generation"`；
  - 仓库自己的 PG 测试因此必须显式列出两列：`backend/tests/unit/test_task_harness_commands.py:126-127`（该文件 fixture 对一次性库执行 `command.upgrade(cfg, "head")`，见同文件 `:98-104`）。
  同类“加列带默认→回填→删默认”手法在 075 的 `awaiting_follow_up_turn`/`force_close_requested` 上也存在，但那两列 ORM 只声明 `default=False`、**没有** `server_default`，因此 ORM 与 DB 是一致的；只有 076/077 的两列出现“ORM 声称有、DB 实际没有”。
- **影响**：`Base.metadata.create_all` 建出的 schema（单测用，如 `backend/tests/unit/test_worker_profile_verification_pg.py:63`）与迁移后的生产 schema 不一致：前者有 `DEFAULT 0`，后者没有。任何不经 ORM 的 INSERT（运维 SQL、一次性数据脚本、未来的数据迁移）在当前生产 schema 上会直接 NOT NULL 失败，而同类写法在 ORM 建的测试 schema 上却通过——属于“测试通过、生产失败”的隐性偏差，且 `alembic.ini`/`env.py` 未开启 `compare_server_default`，`--autogenerate` 不会把它暴露出来。
- **最小动作**：删掉 `models.py` 两处 `server_default=text("0")`（纯删除 2 行）；不要新增 revision 去恢复 DEFAULT
- **验证**：本次已在真实 PG 复现（命令 `/tmp/parity5.py`，输出见 §3.2 #6）。修复后可用同一探针断言两列在迁移库上无默认值、且 ORM `create_all` 与迁移 schema 的 `column_default` 一致。

### MIG-02 ORM 把 `runtime_mode` 默认值改为 `mounted_kit`，数据库默认值仍是 `baked_image`（无对应迁移）
- **判定**：DEFER —— 正常路径显式传值，修复需新增 revision，收益不抵（`[V1 遗留 + V2 放大]`）
- **位置**：`backend/app/models.py:1020`（`WorkerProfile.runtime_mode`，提交 `2c3b95c7`；同 commit 另改 `:935` `WorkerSharedConfiguration`、`:1270` `TaskWorkerProfileSnapshot`），DB 默认值来源 `backend/alembic/versions/056_worker_profile_mounted_kit.py:28`
- **证据**：ORM 现为 `String(32), nullable=False, default="mounted_kit"`；056 建立的 `server_default="baked_image"` 从未被 074–079 修改（`pg_constraint`/`information_schema` 转储显示 `worker_profiles.runtime_mode` 的默认值仍是 `'baked_image'::character varying`）。真实 PG 复现：ORM 插入 → `runtime_mode = mounted_kit`；裸 SQL（补上 generation 两列后）`INSERT INTO worker_profiles (name, image, …) VALUES (...)` → `runtime_mode = baked_image`。而 V2 只允许 `mounted_kit` 作为可执行模式：`backend/app/core/worker_kit.py:16-19`（`WORKER_RUNTIME_MODES = frozenset({MOUNTED_KIT_MODE})`）、`backend/app/core/worker_shared_configuration.py:295-303`（`validate_effective_configuration` 对非 `mounted_kit` 抛错），该方法在任务快照构建路径上被调用：`backend/app/core/worker_profiles.py:866-867`（`snapshot_from_profile`）。
- **影响**：任何不经 ORM 建立的 Profile 行会静默变成 `baked_image`，随后任务创建/执行在快照阶段 fail-closed（`runtime_mode must be one of: mounted_kit`）。该行可通过 API 修复（`backend/app/api/worker_profiles.py:1397-1405` 在请求显式给出 `runtime_mode=mounted_kit` + Kit 路径时会写入新值），因此不是数据损坏，而是“ORM 默认值语义与库默认值语义相反”的隐性陷阱：同一段插入代码在测试 schema（ORM `create_all`）与生产 schema（迁移）上得到不同的运行模式。另注意 V1 期就已存在的 `baked_image` 历史行同样在 V2 下不可执行，这是硬切计划已接受的结果（`docs/superpowers/plans/2026-08-01-multi-harness-engine-roadmap.md:197` 记录“禁用旧 Profile 1（baked_image）与 12”），本文不重复计为缺陷。
- **最小动作**：下次动迁移时顺手 `op.alter_column(..., server_default="mounted_kit")`；触发：出现非 ORM 写入的数据脚本
- **验证**：本次已在真实 PG 复现两条插入路径的差异（`/tmp/parity5.py`）。修复后断言 `column_default = 'mounted_kit'` 且两条插入路径结果一致。

### MIG-INFO-03 Scheduler 启动即 `alembic upgrade head`，硬切 runbook 的“指定 revision + 唯一迁移 owner”门禁在正常启动路径上不生效
- **判定**：DEFER —— 团队有意收敛（部署编排归属 T15），风险只在下一次破坏性迁移到货时兑现
- **位置**：`deploy/docker-compose.yml:90-93`（Scheduler `AUTO_MIGRATE=true`，提交 `5bd12616`）
- **证据**：Scheduler 容器以 `command: ["python3","-m","app.scheduler_service"]` 启动，`backend/app/scheduler_service.py:37` 调 `run_migrations()`，`backend/app/migrations.py:37-44` 执行 `alembic upgrade head`；同一 patch 把 Backend 的 `AUTO_MIGRATE` 从 `true` 改为 `false`（同一文件 diff），因此不存在两个进程竞争迁移。计划要求的是一次性、由唯一 owner 指定**具体 revision** 执行并在维护窗口内完成（`docs/superpowers/plans/2026-08-21-open-harness-v2-implementation-plan.md:646-658`），`deploy/scripts/run-migration-owner.sh:7-13,68-80` 也强制目标不得是 `head` 且不得是当前 revision 的祖先；但正常启动路径走的是 `head`。开发环境实际是“先用迁移 owner 完成 077→078，再把拓扑收敛为 Scheduler 自动迁移”（`docs/superpowers/evidence/2026-09-09-open-harness-v2-r4.6-dev-hard-cut.md:52-55`），属有意收敛。
- **影响**：任何一次携带新镜像的 Scheduler 重启都会自动应用等待中的迁移，包括 roll-forward-only、含 DELETE 的 078 与 079 的配置搬运，而未经 runbook 的“备份 + 确认命中行数 + 排空 Task”前置步骤。
- **最小动作**：发布 checklist 加一行“携带新迁移发布前，先用 maintenance profile 按具体 revision 迁移”；不改 compose
- **验证**：静态阅读 compose/entrypoint/`migrations.py` 与 runbook；本次未执行 docker compose。

### MIG-INFO-04 `_validators.py` 与 `config_runtime.py` 各有一份 `_validate_config_value`，单测只覆盖非生产副本
- **判定**：DEFER —— 两份当前一致，纯维护性债务，不产生交付风险（`[V1 遗留，V2 同步扩展]`）
- **位置**：`backend/app/api/_validators.py:19-45`（本次修改的分支）与 `backend/app/api/config_runtime.py:230-280`（同一逻辑的第二份副本）
- **证据**：生产调用点是 `backend/app/api/config_runtime.py:471`（`normalized[key] = _validate_config_value(key, value)`），而 `_validators._validate_config_value` 在 `backend/app/` 内**无调用者**，只有测试引用（`backend/tests/unit/test_config_api.py:12,65-105`、`backend/tests/unit/test_validators.py`）。本 patch 在两侧都补了 `task_timeout_peak_seconds/off_peak_seconds`（整数 + 60–28800）与 `task_timeout_peak_start/end`（严格 `HH:mm`）分支，两份实现目前一致（`_validators.py:28-45` vs `config_runtime.py:249-280`）。重复本身在基线之前已存在（`3c8cf14c refactor(config): extract shared validators`），V2 只是被迫同时维护两份。
- **影响**：新校验分支若只在其中一份修 bug，另一份不会同步；`test_config_api.py`/`test_validators.py` 的断言对象是死代码副本，不能证明生产路径行为（端点级覆盖另有 `backend/tests/unit/test_config_runtime_api.py`，因此本次只列 DEFER，不当作缺陷）。
- **最小动作**：下次改配置校验时删死副本，把 `test_config_api.py`/`test_validators.py` 改为导入生产实现
- **验证**：静态阅读两份实现与调用点；未运行相关测试。

### MIG-INFO-01 079 只搬运 DB 覆盖值，历史 RUNNING Task 与仅环境变量配置的旧 `TASK_TIMEOUT` 不迁移
- **判定**：ACCEPT/CLOSE —— 「硬切+可停机」画像下的正确取舍，review 也只要求 runbook 加检查
- **位置**：`backend/alembic/versions/079_task_execution_timeout.py:20-28`（新增 nullable 列，无回填）、`:30-55`（仅 `system_config.task_timeout` 搬运）
- **证据**：设计规格已显式声明该边界——`docs/superpowers/specs/2026-09-09-peak-off-peak-task-timeout-design.md:341-343`：“迁移前必须确认没有 RUNNING Task；不为跨版本运行中 Task 增加双读或兼容恢复路径”“不为历史 Task 猜测执行快照”；部署侧要求把旧的 `TASK_TIMEOUT` 环境变量显式替换为四个新变量（同文件 `:344-350`）。与之对应的运行时行为是硬失败：`backend/app/core/worker_task_lifecycle.py:1001-1006`（resume 时 `frozen_task_timeout_seconds` 为 NULL 即把 Task 置 FAILED）、`:189-191`（已是 RUNNING 且无冻结值时直接抛 `TaskTimeoutError`）、`:1144`（monitor 再次读取冻结值）。若只通过环境变量配置过旧超时，`Settings` 的 `extra="ignore"`（`backend/app/config.py:102-106`）会静默忽略遗留的 `TASK_TIMEOUT`，超时回落到新默认 `1800/3600`（`backend/app/config.py:275-278`）。
- **影响**：升级时若未按 runbook 排空 RUNNING Task，这些 Task 会被判 FAILED 且无法从数据库恢复其原先的超时时长；仅靠环境变量配置的部署会静默换用新默认值。两者都被设计文档承认为运维前提，只留作发布检查表条目。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态比对设计规格与实现（079 无 `UPDATE tasks` 语句）；本次未构造跨版本 RUNNING Task 场景（需要停机窗口语义）。

### MIG-INFO-02 078 的数据删除绕过了 Provider API 的四项删除不变式（有意决策，但迁移文档未写明删除语义）
- **判定**：ACCEPT/CLOSE —— 风险是「文档缺口」而非缺陷
- **位置**：`backend/alembic/versions/078_remove_provider_driver.py:18-22`
- **证据**：`op.execute("DELETE FROM ai_providers WHERE provider_kind = 'openai_compatible' AND model_protocol = 'anthropic_messages'")`，而 API 删除路径有四道保护：`backend/app/api/providers.py:708-715`（不允许删除最后一个 Provider）、`:717-729`（不允许删除被 PENDING/QUEUED/RUNNING Task 引用的 Provider）、`:731-745`（删除默认 Provider 时重新选举 `is_default`）、`:747-755`（对 `credential_ref` 调 `soft_retire_credential`）。迁移里的 DELETE 全部绕过，`tasks.provider_id`/`issues.default_provider_id` 由 `ON DELETE SET NULL` 清空。该删除是**有意决策且已备份**：`docs/superpowers/plans/2026-08-23-open-harness-v2-stage-summary-and-remaining-plan.md:167-181`（§6 明确列出删除条件、23 条历史 Task 引用、外键置 NULL、拒绝 downgrade）与 `docs/superpowers/evidence/2026-09-04-open-harness-v2-r4.5-security-release-audit.md:436-455`（真实数据上的只读事务审计 + 备份）。但 078 的 docstring 只写了“Remove the unused provider driver field”，未提及会删除用户配置行。
- **影响**：被删行的 Provider 配置（含内联加密 `api_key`）不可恢复；若被删行恰好是唯一/默认 Provider，升级后系统处于 API 自身禁止进入的状态（无 Provider、无默认），需管理员重新录入。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态核对 SQL 与 API 保护逻辑；未在真实数据上执行该 DELETE（避免动到开发库 Provider/Task 数据）。

## 3. 逐项核查记录

### 3.1 本次全部迁移清单（6 个，全部新增）

| 文件 | revision | down_revision | 涉及表 | 操作 | 风险/备注 |
|---|---|---|---|---|---|
| `074_open_harness_v2.py` (+198) | `074_open_harness_v2` | `073_task_freeform_mode` | `ai_providers`、`worker_profiles`、`task_harness_attempts`、`task_harness_commands`(新) | 列重命名 `wire_protocol→model_protocol`；加 `compat_profile`、`harness_options`(NOT NULL 默认 `{}`)、`control_state`(NOT NULL 默认 `disabled`)、`next_command_sequence`(NOT NULL 默认 `1`)、dispatch lease 两列；2 个 CHECK；建表（PK/唯一/6 CHECK/2 CASCADE FK/3 索引） | 破坏性 RENAME，V1 二进制不兼容，只能 roll forward（与计划一致）；CHECK 与索引非 `CONCURRENTLY`，需维护窗口（runbook 已要求停机） |
| `075_pi_command_dispatch_journal.py` (+68) | `075_pi_command_dispatch_journal` | `074_open_harness_v2` | `task_harness_attempts`、`task_harness_commands` | 加 follow-up/force-close 4 列、command 5 个时间/ID 列；重建 `status` CHECK（扩到 5 值）与 `queued` 一致性 CHECK；新增 `outcome_unknown` 一致性 CHECK；对 2 个 bool 列删 server_default | `status` 取值集合扩大后由新谓词保证一致性（真实库已验证）；downgrade 拒绝 |
| `076_v2_worker_image_identity.py` (+30) | `076_v2_worker_image_identity` | `075_pi_command_dispatch_journal` | `worker_profiles` | 加 2 个 JSON 列 + generation 列（NOT NULL，回填 0 后删默认） | 删默认导致 ORM/DB 漂移（见 MIG-01）；downgrade 拒绝 |
| `077_v2_worker_kit_identity.py` (+40) | `077_v2_worker_kit_identity` | `076_v2_worker_image_identity` | `worker_profiles`、`worker_runtime_readiness` | 加 `worker_kit_identity` + generation（同上）+ 2 个 readiness JSON 列 | 同 MIG-01；downgrade 拒绝 |
| `078_remove_provider_driver.py` (+27) | `078_remove_provider_driver` | `077_v2_worker_kit_identity` | `ai_providers` | **数据删除**（`openai_compatible + anthropic_messages`）+ 删列 `provider_driver` | 不可逆删除用户配置；有意决策 + 备份（见 MIG-INFO-02）；downgrade 拒绝 |
| `079_task_execution_timeout.py` (+61) | `079_task_execution_timeout` | `078_remove_provider_driver` | `tasks`、`system_config` | 加 nullable `execution_timeout_seconds` + 范围 CHECK；把旧 `task_timeout` 覆盖值复制为 peak/off-peak 两键并删除旧键 | CHECK 会全表校验 `tasks`；历史 RUNNING Task 不回填（见 MIG-INFO-01）；downgrade 拒绝 |

### 3.2 关键不变量/契约核对

| # | 不变量 / 契约 | 结论 | 依据（文件:行号 / 命令结果） |
|---|---|---|---|
| 1 | 迁移链单一 head、编号连续、无分叉、revision/down_revision 正确 | 通过 | 六个迁移的 `revision/down_revision` 逐条连续（074→079）；`001_initial` 是唯一 base；`tests/unit/test_077_migration.py::test_077_heads_the_migration_chain` 断言 `set(get_heads()) == {"079_task_execution_timeout"}`（**已运行，11 passed**）；真实 PG 升级后 `SELECT version_num FROM alembic_version` = `079_task_execution_timeout` |
| 2 | `wire_protocol→model_protocol` 是破坏性重命名，且与 roll-forward-only 声明一致 | 通过 | 074:36-45 用 `op.alter_column(new_column_name=)`（纯 RENAME，值不变，无旧别名）；075:67-68、076:29-30、077:39-40、078:26-27、079:58-61 的 `downgrade()` 均 `raise RuntimeError("roll-forward-only")`，与计划 `:172,648-658`、`docs/architecture/open-harness-v2.md:687` 一致；074 自身保留可执行 downgrade（供测试重挂，实测通过），但因 075+ 拒绝降级而在运维上不可达，两者不矛盾 |
| 3 | 历史行回填对空表/非空表都正确；`server_default` 为常量 → PG 快速路径；不重写 V1 数据 | 通过（有两处默认值漂移，见 MIG-01/02） | 074:63,67 常量 `DEFAULT 'disabled'/'1'`（PG 11+ 不重写表）；074:49-58 `harness_options NOT NULL DEFAULT '{}'`；真实 PG 上 `test_074_migration.py` 5 例通过：在 073 库预置 provider/attempt 后升级 074，`model_protocol` 值不变、`control_state='disabled'`、`next_command_sequence=1`、lease 为 NULL、`harness_options={}`；真实库转储确认 `control_state='disabled'`、`next_command_sequence=1`、`harness_options='{}'`、`status='queued'`、`delivery_attempts=0` 的 DB 默认值存在；079 不 `UPDATE tasks`（无历史改写） |
| 4 | `task_harness_commands` 唯一约束/外键级联/CHECK、`payload_digest` 非空、`sequence_no>=1`；pump 查询有索引 | 通过 | `pg_constraint` 转储：`ck_task_harness_command_sequence_no`、`…_type`（steer/follow_up）、`…_status`（5 值）、`…_queued_consistency`、`…_delivered_consistency`、`…_rejected_consistency`、`…_unknown_consistency` + `uq_task_harness_command_attempt_seq(attempt_id, sequence_no)` + PK(command_id) + `task_id`/`attempt_id` 两个 `confdeltype='c'`（CASCADE）外键；`pg_indexes`：`ix_task_harness_commands_task_id`、`…_attempt_id`、`…_attempt_status`；触发探针（真实 PG，合法 attempt 行存在）：合法 `queued/delivered/outcome_unknown` 三行**接受**，`sequence_no=0`、`command_type='abort'`、`status='delivered'` 无 `delivered_at`、`status='queued'` 带 `delivered_at`、`status='outcome_unknown'` 无时间戳、`(attempt_id,sequence_no)` 重复、`command_id` 重复全部**被拒绝**（`CheckViolationError`/`IntegrityError`）。pump 侧查询全部以 `task_id`/`attempt_id` 为等值条件（`worker_command_pump.py:200-215,537-549,207-257`），命中上述索引，无全表扫描 |
| 5 | downgrade 是否与文档一致 | 通过 | 见 #2；`deploy/scripts/run-migration-owner.sh:68-80` 只允许“目标不是当前 revision 祖先”的升级路径，不会触发 downgrade 分支 |
| 6 | ORM 与迁移的列类型/可空性/默认值一致；JSON vs JSONB；时间戳时区 | 部分通过（2 处默认值漂移 → MIG-01/MIG-02；其余一致） | 真实 PG 上 `compare_metadata(compare_type=True)` 对全库比对**无列级差异**（无新增/缺失列、无类型/可空性/长度差异）；19 条 index/constraint 表示差异均为基线前既有（如 `ix_worker_shared_environment_variables_config_id` 命名、`ix_task_harness_attempts_harness_key` 模型未声明），其中唯一涉及 V2 表的 `ix_task_harness_attempts_harness_key` 由基线前 067 引入，非本次改动。JSON 列统一 `sa.JSON`（与全仓既有约定一致，未引入 JSONB）；所有 `DateTime` 均为 naive-UTC + `backend/app/core/utcnow.py:11-13`，且 `grep datetime.utcnow backend/app` = 0 命中，无 aware/naive 混用 |
| 7 | 迁移幂等/重入、DDL+DML 同事务 | 通过 | 079:30-55 两处 INSERT 前先 `SELECT 1 … WHERE key=:key` 存在性判断，DELETE 幂等；`alembic/env.py:63-67`（`do_run_migrations` 内）用 `context.begin_transaction()` 单事务执行，PG 事务性 DDL 使 074→079 全链要么整体提交要么整体回滚；真实 PG 上重复 `command.upgrade(cfg, "head")` 为 no-op（无报错、无重复行）；非空 `system_config` 探针：旧 `task_timeout=5400` → 两新键均为 `5400`、旧键消失（仅此 2 行） |
| 8 | analytics 统计口径变更与前端展示一致 | 通过 | `analytics_queries.py:310`（`sum(...).label("total_execution_seconds")`）与 `analytics_responses.py:344-350`（同名字段、None 安全）成对；前端 `frontend/src/api/index.ts:596`、`Analytics.vue:915-919`、i18n `en.ts:1535`/`zh-CN.ts:1513`（“Total runtime for finished tasks each day”/“每日已结束任务的总运行时长”）均已改为 total；trend 查询无 JOIN（`analytics_queries.py:291-321` + `apply_analytics_filters:60-71`）故 sum 不会重复计数；`project`/`initiator` 表仍同时展示 total 与 avg（`Analytics.vue:1166-1171,1238-1243`），语义未混用 |
| 9 | 跨边界取值一致性：`status`/`command_type`/`control_state` 的 DB CHECK ↔ API ↔ 前端 | 通过 | DB：`status ∈ {queued,dispatching,delivered,rejected,outcome_unknown}`、`command_type ∈ {steer,follow_up}`、`control_state ∈ {disabled,starting,accepting,closing,closed}`（074:77-86,108-127 + 075:48-64）；API：`task_command_routes.py:40-45` 两个集合与之逐一相同（未知值 `ProjectionError` 而非静默丢弃，`:96-108`）；前端联合类型与状态标签覆盖全部 5 个 status（`frontend/src/api/tasks.ts:699`、`TaskSteeringPanel.vue:139-142`）；`execution_timeout_seconds` 的 CHECK 60–28800（079:24-28）与 `core/task_timeout.py:11-12` 常量一致，实测 59/28801/30 拒绝、60/28800/NULL 接受 |
| 10 | 新增 NOT NULL 列/索引的锁与重写行为 | 通过（需维护窗口） | 074:63,67 为常量默认（PG 快速路径）；`tasks` 的 CHECK 校验（079:24-28）与 `task_harness_attempts` 的 CHECK/索引创建会短暂持表锁并对既有行做一次校验扫描；runbook 要求先停止 Backend/Scheduler 再做（计划 §8.6:646-658），本次不构成缺陷 |
| 11 | `UpdateTaskRequest.harness_options` 语义（显式新增字段） | 通过 | `task_schemas.py:143-149` 拒绝显式 null；消费方 `api/task_update_service.py:98-107` 以 `"harness_options" in updated_fields` 判定后再 `validate_task_overrides`，省略该键不会清空既有覆盖；创建路径 `task_creation_service.py:510` 对 None 返回 `{}`（`harness_options.py:185-191`） |

## 4. 局限与未验证项

- **未做**：全量测试与构建（按审查纪律不运行）；未在真实**生产**数据库上执行迁移。
- **已做但需说明边界**：真实 PG 验证在开发库 `192.168.50.129:5432` 上以一次性库（`codify_parity_*`/`codify_cstr_*`/`codify_chk_*`）执行 `alembic upgrade head`、约束探针与 079 非空 `system_config` 探针，全部库已 `DROP`（复核 `pg_database` 仅剩既有的 `codify_test`、`codify_shared_lock_*`），脚本在 `/tmp`，未改动仓库任何文件。
- 076/077 的“删默认值”行为只在**空表**（新库）与 074 测试的**少量历史行**上验证；未在数十万行规模的 `worker_profiles` 上测锁/耗时。
- 078 的 DELETE 未在真实数据上执行（会动到开发库的 Provider/Task 引用）；其命中行数与 `provider_id → NULL` 的影响只能引用证据文档（`docs/superpowers/evidence/2026-09-04-open-harness-v2-r4.5-security-release-audit.md:441-451`）而非本次复现。
- 未审查 V1 期迁移（≤073）与 V2 运行时代码的功能正确性（命令泵状态机、投影、readiness 算法分别属 T01/T02/T08）；`TASK_TIMEOUT` 环境变量契约、`AUTO_MIGRATE` 拓扑与 preflight 的完整审查属 T15，本文只给出交叉引用，不重复记账。
- 未验证 `alembic revision --autogenerate` 在当前 schema 上的输出（未开启 `compare_server_default`，且 `json` 列会使 PG 的默认值比较报 `operator does not exist: json = unknown`，属基线前既有现象）。
