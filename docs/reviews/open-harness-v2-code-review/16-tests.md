# 16 测试质量与覆盖 —— Code Review

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56`（审查基线 `dev @ cbad9e56`） |
| 后端测试 | 134 个文件（49 新增 / 83 修改 / 2 重命名），`+28,472 / -1,672`；新增 `def test_` 约 767 处 |
| 前端测试 | 30 个 spec 文件（4 个新增：`TaskSteeringPanel`、`TaskProcessControlEventRow`、`useTaskLogStreams`、`slotError`），`+3,058 / -92`；新增 `it(` 约 133 处 |
| 其它改动 | `backend/tests/mock_e2e/conftest.py`（新增）、`backend/tests/mock_integration/{docker-compose.mock-test.yml,Dockerfile.backend-test,mock_server/Dockerfile,fake_claude/*}`、`backend/tests/fixtures/harness_events_v2/*`（9 个 JSONL）、`backend/tests/unit/conftest.py`、`backend/tests/e2e/tests/test_config_tabs.py` |
| 审查方法 | `git diff` 定位改动 → 读当前完整文件/调用方/被测实现 → 契约比对（见 §3 矩阵）；用 `grep`/AST 反证"无测试"；窄范围实跑 3 个文件（见 §4） |
| 未覆盖 | `tests/e2e/**`（Playwright）与 `tests/gitlab_e2e/**` 仅看改动清单；未改动的历史 spec 未审；未启动 Docker/Harness CLI 的真实行为 |

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 1 |
| FIX_IF_CHEAP | 6 |
| DEFER | 4 |
| ACCEPT/CLOSE | 7 |

测试改动以「补真测试」为主，质量明显高于 V1：适配器测试驱动真实 shell/Go 子进程，命令平面与迁移测试跑真实 Postgres 并断言 CAS/唯一约束/幂等，前端 log stream 覆盖重连/去重/游标回退；核查未见「删了未补偿」的保护丢失。本轮 **FIX_NOW 1 项**：TST-01（mock 集成 compose 注入 `dual_canary`，唯一的端到端 HTTP 验收层整层失效）。18 项按「3 人内网 beta、无 CI」画像处置：6 项 FIX_IF_CHEAP 属补一行或删一例量级，4 项 DEFER、7 项 ACCEPT/CLOSE 书面关闭（多为覆盖纯度或 Linux/root 环境假设）。

## 2. 问题清单

### TST-01 mock 集成栈的启动模式非法，整层测试无法运行

- **判定**：FIX_NOW —— 已核仅该 compose 两行设置，`scripts/run-mock-stack.sh` 不覆盖
- **状态**：已修复（`7794eb92`，与 OPS-03 同一行配置）
- **位置**：`backend/tests/mock_integration/docker-compose.mock-test.yml:69`（与 `:113`）
- **证据**：compose 给 `backend`/`scheduler` 注入 `HARNESS_EXECUTION_MODE: dual_canary`；`backend/app/config.py:220-227` 的字段校验器只接受 `v2_only`（`raise ValueError("harness_execution_mode must be v2_only")`），`backend/app/core/harness_execution_policy.py:15` `HARNESS_EXECUTION_MODES = frozenset({"v2_only"})`，`backend/app/main.py:58` 与 `backend/app/scheduler_service.py:34` 启动时再次 `require_explicit_harness_execution_mode`。`Makefile:249-253` 仅使用该 compose 文件、`scripts/run-mock-stack.sh` 不覆盖该变量；对照 `deploy/docker-compose.yml:41,95`、`deploy/docker-compose.e2e.yml:47`、`deploy/.env.test:37` 全为 `v2_only`。实跑证明：`HARNESS_EXECUTION_MODE=dual_canary .venv/bin/python -c "from app.config import Settings; Settings()"` → `ValidationError: Value error, harness_execution_mode must be v2_only`。
- **影响**：`make test-mock-integration` / `test-mock-integration-parallel` 的 backend 容器在加载配置时即退出、healthcheck 永不通过，`make test-all:508`（含 mock 集成）不可用；这是本次 V2 唯一的端到端 HTTP 验收层（`deploy/entrypoint.worker.sh` + 真 Worker 容器，约 246 个用例）被整体关掉。
- **最小动作**：删掉两处 `HARNESS_EXECUTION_MODE: dual_canary`（默认即 `v2_only`，无需显式配置）
- **验证**：已实跑 settings 校验（命令与输出见上）；未启动 docker 栈验证容器退出码。

### TST-04 `protocol_error` 的"缺 init"（缺 `run.started`）分支无测试

- **判定**：FIX_IF_CHEAP —— 修法只是既有负例表加一行
- **位置**：`backend/app/core/harness_protocol.py:485-486`（纯 replay 校验）与 `backend/app/core/harness_attempts.py:199-217`（DB 增量摄入）
- **证据**：`grep -rn "missing_init\|missing run.started" backend/tests` → 0 命中。本报告的实测脚本证明该分支可达：`CanonicalEventReplay().ingest(seq=1, type=tool.started)` → `HarnessProtocolError code=missing_init`（同一脚本中 `seq=2` 触发的是 `sequence_gap`，即"缺 init"必须由首事件类型触发，不能被"缺口"测试覆盖）。`test_harness_event_fixtures.py:322-331` 的负例表只覆盖 missing task terminal / sequence gap / finalization 顺序三类。
- **影响**：契约明确要求"缺 init/双 terminal/缺序 = protocol_error"。若首事件非 `run.started` 被接受，attempt 的 harness 身份冻结在错误起点，后续 control ACK 会投影到错误的 attempt，而全部现有事件测试仍绿。
- **最小动作**：`test_harness_protocol.py` 负例表加 `[_event(1,"tool.started")] → missing_init`，不做 DB 层 receipt 用例
- **验证**：实跑一次性 python 片段证明分支可达（非测试）；未新增用例。

### TST-06 execute / schedule / retry 三个入口的 V1 只读门禁无测试

- **判定**：FIX_IF_CHEAP —— 门禁在代码里已存在，只有直连 API 才碰得到，UI 已隐藏 legacy 写操作
- **位置**：`backend/app/api/task_action_routes.py:418`（execute）、`:484`（schedule）、`backend/app/api/task_creation_service.py:142`（retry）；对照已覆盖的 `:95`（cancel）与 `backend/app/api/task_update_service.py:94`（update）
- **证据**：`grep -rn legacy_contract_not_executable backend/tests` 仅 3 处——`test_tasks_api.py:2375`（cancel 409）、`test_task_override_status.py:265`（override）、`test_tasks_api.py:659`（序列化只读标记）；AST 映射显示 26 处 `harness_execution_mode="v2_only"` 补丁全部落在 create/update/reschedule/analytics/slot 路径，没有一处围绕 execute/schedule/retry 路由；`ExecutionPolicyError` 在测试中只出现在 `test_harness_execution_policy.py`（策略函数本身）与 `test_scheduler_coverage.py`（claim/resume 恢复）。前端 `TaskView.spec.ts:1431-1528` 只验证 UI 隐藏写操作。
- **影响**：任一入口漏掉 `require_task_execution_writer`，v2_only 下会重新调度/重跑 legacy V1 任务，且无测试失败。
- **最小动作**：`test_tasks_api.py:2375` 同款参数化一条，覆盖 execute/schedule/retry 三路由
- **验证**：静态；未运行。补充：resume 侧由 `test_scheduler_coverage.py:1522-1535,1757-1774` 间接覆盖（注入 `ExecutionPolicyError` 而非驱动 legacy 任务）。

### TST-07 前端 steer 发送路径零覆盖

- **判定**：FIX_IF_CHEAP —— 两个 vitest 用例复用现有 mock，无新基建
- **位置**：`frontend/src/components/TaskSteeringPanel.spec.ts:13-16`（`sendHarnessCommand: vi.fn()`）对照 `frontend/src/components/TaskSteeringPanel.vue:201-235`（`send()`）
- **证据**：该 spec 共 12 个用例（vitest 实跑 12 passed）全部是渲染/门禁/历史展示断言，且 `n-button` 被 stub；`grep -c "sendHarnessCommand(" TaskSteeringPanel.spec.ts` = 0（`sendHarnessCommand` 声明后从未被调用）。`send()` 中的三种状态 toast、HTTP 失败 detail 解析与 `message.error`、`refreshHistory()`、`sending` 去重保护均无断言。
- **影响**：live steering 的真实提交路径（本专题里唯一的"写"交互）可以在前端坏掉而不被任何测试发现；`tasks.contract.spec.ts:159-169` 只验证 URL/UUID 生成。
- **最小动作**：补 2 例：resolve→清空输入+刷新历史；reject→`message.error`+`sending` 复位
- **验证**：已实跑该 spec（12 passed、1.87s）确认无发送用例。

### TST-09 名不符实的空断言：`projector` 不写命令状态

- **判定**：FIX_IF_CHEAP —— 真不变量已由 pump 文件覆盖
- **位置**：`backend/tests/unit/test_harness_events_v2.py:96-105`
- **证据**：函数体只对 fixture 做 `assert "command_id" in event["payload"] or event["type"] == "control.queue.updated"`，与"projector 不回写 command 状态"无关；docstring 自认 "the no-write guarantee is structural ... and covered by integration"。该不变量真正的验证在 `test_worker_command_pump.py`（`test_projector_does_not_guess_when_the_digest_mismatches` 断言 `status == "queued"`、`test_projector_scopes_command_lookup_to_the_event_attempt`）。
- **影响**：按名字检索"projector 不回写"的读者会误以为已有覆盖；将来真去删掉 pump 里的断言时，这个空壳仍在且绿。
- **最小动作**：删掉该用例（净减代码）
- **验证**：读代码 + 读 pump 同名断言；未运行。

### TST-10 四个 Kit 安装器 fail-closed 用例在非 root 下静默跳过

- **判定**：FIX_IF_CHEAP —— Kit 安装 fail-closed 在离线部署主路径上，3 条安全断言在开发者机器上永远 skip
- **位置**：`backend/tests/unit/test_offline_bundle_export.py:29-31`（`if os.geteuid() != 0: pytest.skip("Worker Kit installation requires root")`），调用点 `:930`、`:1002`、`:1076`
- **证据**：这三个用例分别覆盖"安装器校验并拒绝版本覆盖"、"目标在原子发布前出现时拒绝"、"绝不执行 kit 自带 content verifier"——均为 Kit fail-closed 的安全相关断言。仓库无 CI，`make test-unit` 以普通用户运行时它们全部 skip。
- **影响**：Kit 安装边界（invariant「present CLI bytes/SHA 不符时整 Kit fail closed」的落地环节）在开发者机器上永远不验证。
- **最小动作**：改 `_secure_install_root`：monkeypatch `os.geteuid`→0 + 安装根换 tmpdir
- **验证**：静态；未在 root 下运行。

### TST-13 075/077/078/079 迁移测试只断言 mock 的 SQL 文本

- **判定**：FIX_IF_CHEAP —— 078 的 DELETE 会让历史任务从统计里静默消失，正踩硬要求
- **位置**：`backend/tests/unit/test_079_migration.py:21-72`、`test_077_migration.py:27-47`、`test_078_migration.py:19-36`、`test_075_migration.py:11-18`
- **证据**：这些用例用 `mock.patch("alembic.op.add_column"/"create_check_constraint"/"get_bind")` 加载迁移模块并直接调用 `upgrade()`，然后断言 `add_column.call_args`、生成 SQL 的字符串形式（`assert any("INSERT INTO system_config" in sql ...)`）与 `side_effect` 预设的执行次序；不落任何真实库。对照同类 `test_074_migration.py`（真 PG，断言唯一约束抛错、回填数据）保护明显更弱：`conn.execute.side_effect` 的固定顺序让用例对实现调用次序敏感（改序即假失败），同时又无法发现"约束语句写了但未生效/回填值类型错误"这类只在真库里暴露的问题。
- **影响**：079 的 `execution_timeout_seconds` CHECK 约束与 077 的 kit identity 列只被文本/调用断言保护，迁移在真实 Postgres 上失败或约束未生效不会被这些用例发现。
- **最小动作**：切库前在正式数据副本上跑两条 SELECT/COUNT：078 受影响任务数、079 越界值；不新增真库测试。建议过重：把 079 纳入 `test_074_migration.py` 真库 fixture
- **验证**：读代码；未运行（PG 侧只实跑了 TST-02 记录的两个文件）。

### TST-02 命令平面核心断言只在"可达内网 Postgres"时执行，且无 CI 门禁

- **判定**：DEFER —— 本机内网 PG 可达、50 条断言在跑（实跑 18+32 passed），换机器即全跳
- **位置**：`backend/tests/unit/test_task_harness_commands.py:49-52`（`ADMIN_URL` 默认 `postgresql+asyncpg://codify:codify_password@192.168.50.129:5432/codify_test`）与 `:97` `pytest.skip(f"command-plane DB unreachable: {exc!r}")`；`backend/tests/unit/test_worker_command_pump.py:36-38,83`
- **证据**：承担断言包括同一 `command_id` 幂等/冲突 409（`test_task_harness_commands.py:326`、`:346`）、严格序列分配（`:309`）、CAS 与终态不可变（`:503/:538/:568`）、gate accepting/closing/closed（`:462`、`test_worker_command_pump.py:546,560`）。`Makefile:151-156`（`test-unit`）与 `:233-235`（`test-backend`）都不注入 `CODIFY_TEST_DATABASE_URL`；`git ls-files` 显示仓库无任何 CI 定义（无 `.github/workflows`）；`docs/TESTING.md:67` 明确写"数据库不可达时相关模块自动跳过"。`grep -rl "DB unreachable\|PostgreSQL verification test DB unreachable" tests/unit` 共 12 个文件、93 个用例在库不可达时整体跳过。
- **影响**：在无法访问该内网库的机器（新同事、任何自动化环境）上 `make test-unit` 全绿，而命令平面的 50 个核心断言全部跳过；命令幂等/序列/门禁回归会静默通过（本次本机可达，故未暴露）。
- **最小动作**：无需动作；换机器时 `export CODIFY_TEST_DATABASE_URL`。建议过重：`CODIFY_ALLOW_DB_SKIP=1` 新开关是为单机场景造机制
- **验证**：本机可连通该库，已实跑 `pytest tests/unit/test_task_harness_commands.py -q` → 18 passed (16.99s)、`pytest tests/unit/test_worker_command_pump.py -q` → 32 passed (54.04s)；无库环境的 skip 行为未实跑（静态证据充分）。

### TST-INFO-01 真实子进程 + 1s 边界等待的潜在 flake

- **判定**：DEFER
- **位置**：`backend/tests/unit/test_pi_owner.py:373-375`（`await asyncio.wait_for(owner.settled.wait(), timeout=1)` 紧跟 `owner.process.wait(), timeout=1`），同文件 `:312/:319/:421/:429/:479-506` 为 2-3s 边界
- **证据**：这些用例启动真实 `sys.executable -c` 子进程并 Unix socket，`make test-backend` 以 `-n auto --dist=loadgroup` 并行运行；1s 内需完成子进程启动+首次 settled 输出，负载高时可能超时。
- **影响**：未观测到失败（本次未运行该文件），仅记录为潜在 flake 点。
- **最小动作**：真 flake 时把 1s 边界放宽到 5s（1 行）
- **验证**：静态；未运行 `test_pi_owner.py`。

### TST-INFO-02 mock_e2e 的 schema 来自 ORM 而非迁移

- **判定**：DEFER —— ORM 建表是 V1 遗留取舍，硬要求由切库真迁移保证
- **位置**：`backend/tests/mock_e2e/conftest.py:41-50`（`Base.metadata.create_all`，session 级共享 in-memory SQLite）
- **证据**：新 conftest 把各文件自带的 `create_all` 收敛为一份；`[V1 遗留]` 模式本身未变。因此迁移里引入的唯一索引/CHECK（如 `(attempt_id, sequence_no)` 唯一）不会在 mock_e2e 层被校验，约束只由 PG 迁移测试覆盖（见 TST-02）。
- **影响**：`create_all` 与 Alembic 迁移漂移时 mock_e2e 仍绿。
- **最小动作**：不动；在 TESTING.md 注明"迁移约束只由 PG 套件保证"（可选 1 行）
- **验证**：读 conftest 与基线文件对比；未运行。

### TST-INFO-03 命令测试依赖"module 级共享 DB + 随机 owner"的隐式约定

- **判定**：DEFER —— 隐式约定当前自洽
- **位置**：`backend/tests/unit/test_worker_command_pump.py:355-358`（`_owner()` 注释）、`test_task_harness_commands.py:92-99`（module scope fixture `commands_db`）
- **证据**：DB 为 module 级复用、用例间不清理行，靠"每用例新 owner/新 attempt"避免互相干扰；`_claim_next_attempt` 按 `attempt_id` 排序取第一个可领取 attempt。
- **影响**：若有人把 owner 改成固定值或引入串行依赖，用例会互相污染；这正是 TST-03（租约分支无人走）的成因之一。
- **最小动作**：不动；下次改该文件时在文件头加一行注释
- **验证**：读代码 + 实跑（32 passed 说明当前约定自洽）。

### TST-03 attempt 租约过期与属主互斥分支无任何测试

- **判定**：ACCEPT/CLOSE —— 单 scheduler + 允许重启的画像下属过度防御
- **位置**：`backend/app/core/worker_command_pump.py:220-223`（`expires_at.is_(None) | expires_at < now | owner == owner`）、`:259-262`（`_promote_starting_attempt` 同条件）、`:517-530`（`_drop_lease` 仅属主可清）
- **证据**：`grep -rn "command_dispatch_expires_at|command_dispatch_owner|lease_ttl|DEFAULT_LEASE_TTL_SECONDS" backend/tests` 仅命中 `test_074_migration.py:281-291`（断言迁移后两列为 NULL）与 `test_worker_command_pump.py:406` 注释。`test_worker_command_pump.py:357` 的注释"Unique dispatcher identity per test so a test only claims its own fresh attempt"说明测试用随机 owner 刻意绕开租约分支。
- **影响**：若删掉"租约过期可被接管"这一支（只保留未过期不可抢），崩溃 dispatcher 会永久占住 attempt、该 Task 的后续命令永久 `queued`；`lease_ttl` 写错同样不报警。现有 32 个 pump 用例全绿。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态 grep 反证 + 读实现；未新增/运行用例。

### TST-05 命令 API 没有"路由 → 服务 → DB"的集成覆盖

- **判定**：ACCEPT/CLOSE —— 路由层与服务层两侧已覆盖，要求全链集成属覆盖纯度
- **位置**：`backend/tests/unit/test_task_command_routes.py:1-6`（文件自述"mocked DB session and patched service functions"）；服务层 `backend/tests/unit/test_task_harness_commands.py`（真 PG，见 TST-02 可跳过）
- **证据**：`grep -rn "commands\|catalog\|log-stream" backend/tests/mock_e2e/*.py` 只命中间接文案，V2 命令/目录/日志流路由零命中；mock_e2e 的所有改动都是 fixture 收敛（如 `test_tasks_e2e.py` 删除自带 `_test_engine`/`session_factory` 改用新 conftest）。即 `PUT /api/tasks/{id}/commands` 的 HTTP 层断言的是被 patch 的 `create_command`，而真实服务调用只由可跳过的 PG 测试覆盖，两者之间（路由参数、`command_id` 规范化、gate 前置顺序）没有一层会发现接线漂移。同类情况也存在于 harness catalog / results v2 / log stream 的 HTTP 面。
- **影响**：路由与服务之间传错参数（如 attempt_id、task_id 或丢失 preflight 顺序）时，两层测试都绿。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态（grep + 读文件 + 读 fixture）；未运行。

### TST-08 非 Linux 上进程回收断言静默失效

- **判定**：ACCEPT/CLOSE —— 生产是 Linux，非 Linux 断言失效属覆盖纯度
- **位置**：`backend/tests/unit/test_opencode_harness_adapter.py:3230-3233`（`_proc_start_time` 读 `/proc/{pid}/stat`）、`:3255-3257`（`_assert_process_gone`）、用例 `:3337/:3349/:3357/:3367`
- **证据**：`_assert_process_gone` 写成 `current = _proc_start_time(pid)` 后 `if current is not None: assert current != start_time`；macOS 无 `/proc` → `current` 恒为 None → 断言不执行。四个用例都依赖它（`for pid, start in zip(pids, starts): _assert_process_gone(pid, start)`），且用例注释写明 "to keep the regression portable on macOS CI hosts"。
- **影响**：在 macOS（本仓工作站即 darwin）上，`reaps_ignoring_child_after_cancel` / `timeout_signal_reaps_ignoring_child` / `default_cleanup_fits_cancel_budget` 这三条回归只剩"退出码正确"，孤儿 server 进程泄漏（正是它们要防的）不会被发现。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态（代码路径 + 本机 darwin，无 `/proc`）；未在 Linux/macOS 分别运行。

### TST-11 Dockerfile / verifier 源码子串测试

- **判定**：ACCEPT/CLOSE —— 真行为已由 `:464-535` 锁定，改成真实 docker build 验证属过重
- **位置**：`backend/tests/unit/test_worker_kit.py:858-866`、`:869-906`
- **证据**：`test_worker_kit_release_records_all_four_harness_entries_and_selfchecks` 对 `Dockerfile.worker-kit` / `Dockerfile.worker-java21-maven` / `verify-runtime.sh` 做约 30 条 `assert "<子串>" in <文件文本>`（含 `assert "advisory" in verifier`、`assert "KIT_CLI_SELECTION" in kit_dockerfile`）；`test_launcher_keeps_the_v1_install_verify_boundary...` 对 Go 源码做 3 条子串断言。同文件里真正的行为测试（`:464-535` 跑 `verify-runtime.sh` + fake docker 篡改字节）才是有效保护。
- **影响**：构建脚本被改坏（例如 selfcheck 顺序、`--verify` 分支语义）但字符串仍在时测试通过，属"看起来覆盖构建、实际只锚文本"。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：读代码；未运行 docker 构建（受任务约束禁止）。

### TST-12 新增 PG 测试沿用硬编码内网库与明文口令

- **判定**：ACCEPT/CLOSE —— 硬编码实为 25 处/18 文件（`[V1 遗留]`，被 V2 放大），统一改造过重
- **位置**：`backend/tests/unit/test_task_harness_commands.py:51-52`、`test_worker_command_pump.py:37-38`、`test_074_migration.py:36-37`、`test_worker_profile_verification_pg.py:22-23`
- **证据**：四处默认值均为 `postgresql+asyncpg://codify:codify_password@192.168.50.129:5432/codify_test`；该模式在基线提交已存在于 `test_072_migration.py:41-43` 等 V1 文件（`git show 8081c946^:...` 可证），V2 新增 4 个文件继续沿用。未发现真实生产凭据/私钥，口令是本地测试库口令。
- **影响**：新测试把"能否执行核心不变量"绑定到某个开发者内网主机，配合 TST-02 的 skip 形成门禁空洞；也让环境相关失败难以区分。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态（`git grep` 基线对比）；未运行。

### TST-INFO-04 Kit fixture 用被测模块函数生成期望值（部分自证）

- **判定**：ACCEPT/CLOSE
- **位置**：`backend/tests/unit/test_worker_kit.py:51-60`（`_recompute_bundle_digest` 调用被测的 `bundle_manifest_digest_from_files`），被 `:270`、`:523` 使用
- **证据**：fixture 的 `bundle_digest` 由生产函数算出，再交给独立的 `verify-runtime.sh` 校验；若该函数与 verifier 同时错（例如都忽略嵌套文件）则不会被发现——但 `test_worker_runtime_bundle_v2.py:270-281`（digest 递归）与 `:464-535`（verifier 篡改字节必须失败）从两侧独立锁定，风险已被抵消。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：读代码与相关用例；未运行。

### TST-INFO-05 删除/弱化核查结论：未见保护丢失

- **判定**：ACCEPT/CLOSE
- **位置**：`backend/tests/unit/test_worker_repository_bootstrap.py`（`+5/-111`）、`backend/tests/mock_e2e/*.py`（最大 `-86`）
- **证据**：该文件删除的 3 个用例（`test_clean_reused_workspace_pushes_a_preserved_local_commit`、`test_push_nonzero_is_recovered_when_remote_matches_local_commit`、`test_retry_finalizes_a_previously_uncertain_push_when_remote_already_matches`）语义已由 `test_worker_git_delivery.py:798-849`（push 非零但远端已含 head → `already_present`）、`:554`（hard cut 后忽略未确认标记）、`:1628-1634`（旧 git config marker 不再被读取）更强地覆盖。mock_e2e 的 `-111/-86/-74/-62/-54` 删除全部是各文件自带 engine/fixture 搬进新 conftest（`git diff` 中无 `def test_` 删除）。全 diff 未见 `xfail`、注释掉的用例或被放宽的既有断言。
- **影响**：无。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：逐文件 `git diff` 对比 + `grep '^-.*def test_'`。

## 3. 逐项核查记录

### 3.1 覆盖缺口矩阵（不变量 → 是否有测试 → 依据 → 合理 bug 下是否会失败）

| # | 不变量 | 结论 | 测试文件:行号 | 合理 bug 下会失败 |
|---|---|---|---|---|
| 1 | `command_id` 幂等（同 ID 同 payload）与同 ID 异 payload 409 | 强（真 PG + HTTP 双层） | `test_task_harness_commands.py:326,346`；`test_task_command_routes.py:112,172` | 是（DB 可达时） |
| 2 | `sequence_no` 行锁内严格分配、唯一 | 强 | `test_task_harness_commands.py:309`；`test_074_migration.py:320-330` | 是 |
| 3 | 单 dispatcher 租约与过期回收 | **无** | 实现 `worker_command_pump.py:220-223,259-262,517-530`；测试仅 `test_074_migration.py:281-291` | **否** → TST-03 |
| 4 | 状态机 CAS 与终态不可变 | 强 | `test_task_harness_commands.py:503,538,568` | 是 |
| 5 | gate `accepting/starting/closing/closed` 分支 | 强 | `test_worker_command_pump.py:546,560,627,1180`；`test_task_harness_commands.py:462` | 是 |
| 6 | settled → closing → 排空 → 收敛唯一 harness terminal | 中 | `test_worker_command_pump.py`（`closing_queue_drains_then_owner_ack_closes_gate`、`pre_drained_closing_attempt_is_claimed_and_closed`）；`test_harness_protocol.py:165` | 是 |
| 7 | `protocol_error`：缺 init | **无** | 实现 `harness_protocol.py:485-486`、`harness_attempts.py:199-217`；`grep missing_init tests` = 0 | **否** → TST-04 |
| 8 | `protocol_error`：缺口 / 双 terminal / terminal 非末条 | 强 | `test_harness_protocol.py:179,203,209,236` | 是 |
| 9 | 事件幂等（同 `event_id` 重放） | 强 | `test_harness_protocol.py:171`；`test_harness_attempts.py:101,136` | 是 |
| 10 | 乱序/跨 attempt 漂移/身份不可变 | 强 | `test_harness_attempts.py:163,198`；`test_harness_events_v2.py:107`；`test_harness_protocol.py:218,227` | 是 |
| 11 | `harness.*`/`delivery.*` 不是 task terminal | 强 | `test_harness_protocol.py:187,209`；`test_harness_event_fixtures.py:325` | 是 |
| 12 | `worker.finalization` 后唯一 `run.completed/failed` | 强 | `test_harness_protocol.py:195`；`test_harness_attempts.py:173`；`test_worker_results_v2.py:709-721` | 是 |
| 13 | V1 只读门禁（execute/schedule/retry/resume 全入口） | **弱** | 门禁 `task_action_routes.py:418,484`、`task_creation_service.py:142`；测试仅 cancel/update | **否** → TST-06 |
| 14 | Kit inventory present bytes/SHA 不符 → 整 Kit fail closed | 强（真 verifier 子进程） | `test_worker_kit_inventory.py:222-290`；`test_worker_kit.py:471-481`；`test_scheduler_harness_gate.py:120` | 是 |
| 15 | version/SHA-only 差异仅 advisory（不 gate） | 中 | `test_worker_kit.py:516-535`（真 verifier，placeholder 必须 returncode 0 + 输出 advisory） | 是 |
| 16 | Runtime Bundle digest 递归 manifest 文件列表 | 强 | `test_worker_runtime_bundle_v2.py:245,260,270` | 是 |
| 17 | `harness_options` deep merge + `task_override` 白名单 | 强 | `test_harness_options.py:87-178` | 是 |
| 18 | `model_protocol` → env 变量映射与凭据隔离 | 强 | `test_worker_runtime_model_protocol_env.py:59-70,118-130,179-215` | 是（`openai_chat_completions` 未单独参数化，走与 `openai_responses` 相同分支） |
| 19 | 迁移回填与约束（074/075/077/078/079） | 强弱混合 | 074 真 PG：`test_074_migration.py:281-359`；075/077/078/079 只 mock `alembic.op` 断言 SQL 文本：`test_079_migration.py:21-72` | 074 是；075/077/078/079 否 → TST-13 |
| 20 | 交付幂等与 push 失败分类 | 强 | `test_worker_git_delivery.py:798,977,1030,1593`；`test_worker_results_v2.py:328-750` | 是 |
| 21 | 取消/超时竞态 | 中 | `test_task_timeout.py:29-65`（仅时间窗计算）；`test_issue_execution_lock_concurrency.py:343-349` | 部分（超时并发下的收敛未直接覆盖） |
| 22 | 容器清理不误杀（非 worker 容器/服务容器） | 强 | `test_scheduler_coverage.py:611-680` | 是 |
| 23 | 命令 API 路由 → 服务 → DB 集成 | **无** | 见 TST-05 | **否** → TST-05 |
| 24 | 前端 steer 发送（乐观/失败/toast/去重） | **无** | 见 TST-07 | **否** → TST-07 |

### 3.2 已确认无问题的关键点

| # | 项 | 结论 | 依据 |
|---|---|---|---|
| 1 | 测试驱动真实实现而非 mock 回声 | 通过 | 三个最大适配器文件 `grep assert_called/call_count` = 0；`test_claude_harness_adapter.py:1324-1343`、`test_pi_owner.py` 起真实 bash/python 子进程；`test_worker_kit.py:464-535` 起真 `verify-runtime.sh` + fake docker |
| 2 | 适配器/runner 覆盖为 V2 大幅补齐 | 通过 | `test_opencode_harness_adapter.py` +3373、`test_pi_harness_adapter.py` +1752、`test_claude_harness_adapter.py` +779、`test_codex_harness_adapter.py` +406 行，含 thinking/partial lifecycle、cancel/timeout 回收、v2 envelope |
| 3 | 前端 log stream 难点有覆盖 | 通过 | `useTaskLogStreams.spec.ts`（409 行）：陈旧 source 回调丢弃、`mergeTaskLogState` 去重/就地升级/不倒退、`computeStructuredStreamSinceId` 回退游标、多 pending 场景 |
| 4 | 稳定性 | 基本通过 | 前端用 `vi.useFakeTimers`+`advanceTimersByTimeAsync`；后端并发用例用事件 + `wait_for` 而非盲等；`grep sleep(` 命中均为"模拟慢传输/超时"的刻意构造；固定 `/tmp` socket 名使用刻意冲突概率极低的大 task_id（`test_pi_owner.py:205-206,435-436`） |
| 5 | 卫生 | 通过（除 TST-12） | `grep` 未发现真实生产密钥/私钥；`print(` 命中均为 fake CLI 子进程的协议输出，不是调试残留；未发现残留调试用例文件（`__pycache__` 未入库） |
| 6 | 删除/弱化 | 通过 | 见 TST-INFO-05 |
| 7 | 新增用例分布 | 通过 | 新增用例集中在适配器/命令平面/交付/迁移等难点，而非只堆 UI 快照：前端无 `toMatchSnapshot`（0 命中），新增 4 个 spec 中 409 行的 log-stream 覆盖并发流处理；唯一的"好写"倾向是 `TaskSteeringPanel.spec.ts` 只做渲染（见 TST-07） |

## 4. 局限与未验证项

- 本次实跑（均为窄范围，未触发全量套件/构建）：
  - `backend && .venv/bin/python -m pytest tests/unit/test_task_harness_commands.py -q` → **18 passed**（16.99s，真 Postgres）
  - `backend && .venv/bin/python -m pytest tests/unit/test_worker_command_pump.py -q` → **32 passed**（54.04s，真 Postgres）
  - `frontend && npx vitest run src/components/TaskSteeringPanel.spec.ts` → **12 passed**（1.87s）
  - 一次性脚本（非测试）：证明 `Settings(harness_execution_mode="dual_canary")` 抛 `ValidationError`；证明首事件非 `run.started` 时 `CanonicalEventReplay` 抛 `code=missing_init`。
- 未运行：`make test-unit` / `test-backend` 全量、`npm run build`、mock 集成 docker 栈、Playwright 与 GitLab E2E（受审查纪律约束）；因此 TST-01 的"容器退出"结论来自配置校验实跑 + 静态启动路径，未经 docker 验证。
- 未验证：无库环境下 DB 用例的 skip 行为（本机可连通 `192.168.50.129`，12 个 PG 文件的 skip 分支未实跑）；TST-08 的 macOS 失效行为来自代码路径推断（未在两类平台对跑）；TST-10 的 root skip 未在非 root 下实跑。
- 未逐行通读全部 134 个后端测试文件（重点为新增文件、大改动文件与不变量相关文件）；`tests/e2e/tests/test_config_tabs.py`（+1 行）等轻改动仅看 diff。
- 未评估前端未改动历史 spec 的质量问题（不在"V2 引入"范围内）。
