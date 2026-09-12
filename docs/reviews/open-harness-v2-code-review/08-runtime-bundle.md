# 08 Runtime Bundle / Harness Registry / harness_options / Readiness / Kit Inventory —— Code Review

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56`（`7b253fbf..cbad9e56`，结论基于 `dev @ cbad9e56` 当前完整代码） |
| 文件（+/-） | `backend/app/core/worker_runtime_bundle.py`（+836/-117）、`core/worker_runtime_bundle_export.py`（+222）、`core/harness_registry.py`（+259/-30）、`core/harness_options.py`（+262）、`core/worker_runtime_readiness.py`（+646/-65）、`core/worker_runtime.py`（+295/-23）、`core/worker_kit.py`（+44/-1）、`core/worker_kit_inventory.py`（+490）、`core/worker_environment_variables.py`（+47/-1）、`api/harness_catalog.py`（+430）、`api/worker_profiles.py`（+573/-94）、`api/worker_shared_configuration.py`（+20/-5）、`core/worker_profiles.py`（+294/-4） |
| 审查方法 | 静态阅读完整文件（含调用方、被调用方与测试）+ 契约/文档对照（`docs/architecture/open-harness-v2.md` §7/§9.2/§11.2/§12、实现计划 §4.4/§4.5/§5.4/§8.6）+ 跨模块调用方 grep + 基线（`8081c946^`）对照 + 窄范围单测 + 无副作用内联复现 |
| 实际运行的验证 | ① `cd backend && .venv/bin/python -m pytest tests/unit/test_harness_options.py -q` → `16 passed`；② `... tests/unit/test_worker_runtime_bundle_v2.py -q` → `12 passed`；③ 内联 `python -c` 复现 readiness 作用域判别（见 RTB-01 验证栏）。其余结论为静态推理 |
| 未覆盖 | 真实 Docker daemon / 真实 Worker Kit / 真实 Harness CLI（无环境，readiness 探针未实跑）；四 Harness shell adapter、bridge、runner 的逐行审查（T03/T04/T06/T07/T09）；前端对 catalog/options 的消费（T12）；alembic 迁移语义（T14）；制品导出 CLI 的运维流程（T15） |

## 1. 结论摘要

| 等级 | 数量 |
|---|---|
| P0 | 0 |
| P1 | 1 |
| P2 | 1 |
| P3 | 2 |
| INFO | 3 |

Runtime Bundle 主体质量良好：digest 确实递归自 manifest 文件清单（绑定期用受控源码字节替换模板 `files`，非写死数组）、per-adapter digest 覆盖共享库变更、冻结后不再回读 checkout、Evidence 与冻结的 Adapter/镜像/Kit identity 互相绑定、V2 载荷在读写两侧都做完整校验、Kit `present` 条目字节不符即整 Kit fail closed、`harness_options` 三个已知命名空间 `extra="forbid"` 且 Task override 有白名单、执行期身份只来自 Snapshot。主要缺陷集中在 **readiness 作用域判别**：V2 校验只写「完整内容清单作用域」，而任务创建/F6 切换/CI 自修复/公开 catalog 走按 `harness_runtimes[*].contract_version` 判别的另一条作用域，在仓库默认（`harness_runtimes = {}`，API 与前端都不下发该字段）下这些门禁与展示永远读到 `unknown`，使 §16.3 创建期 409 门禁失效、catalog 恒报 `runtime_not_verified`。

## 2. 问题清单

### RTB-01 readiness 作用域判别与 V2 校验写入不一致，创建/切换/CI 门禁失效
- **等级**：P1
- **位置**：`backend/app/core/worker_runtime_readiness.py:229`（提交 `cbad9e56`）
- **证据**：
  - 校验侧写入「完整内容清单」作用域：`api/worker_profiles.py:845-846`（`v2_harness_keys = eligible_v2_harness_keys(profile)`；`requires_v2_identity = bool(v2_harness_keys)`）+ `:885`（`run_deterministic_kit_probe(..., require_content_inventory=requires_v2_identity)`）；而 `core/worker_profiles.py:205-208` 的 `eligible_v2_harness_keys` 返回**全部 enabled harness**（`enabled_harnesses` 为空时回落 `["claude"]`），即任何 Profile 都为 True。
  - 读取侧按 `harness_runtimes` 判别：`worker_runtime_readiness.py:229-237` 的 `profile_requires_content_inventory()` 仅在 `harness_runtimes[selected_key]["contract_version"] == codify.worker.harness/v2` 时返回 True；`readiness_for_profile()`（`:416`，实际读取在 `:469`）用它决定 `require_content_inventory`，而 `runtime_readiness_fingerprint()`（`:204-226`）对 False 返回裸 locator fingerprint（作用域 A）、对 True 返回 `READINESS_SCOPE_SCHEMA` 哈希（作用域 B）——**两个不同的行主键**。
  - 该字段在真实部署中恒为空：迁移默认 `'{}'`（`backend/alembic/versions/064_multi_harness_runtime.py:64-70`）、创建接口原样落库 `harness_runtimes=request.harness_runtimes or {}`（`api/worker_profiles.py:1317`）、前端从不下发该字段（`frontend/src` 中 `harness_runtimes` 零命中，只下发 `harness_constraints`）。且 `validate_harness_runtimes`（`core/harness_registry.py:177-232`）只接受 `contract_version == codify.worker.harness/v2`，不存在「声明 v1」的可用 Profile，故按 `harness_runtimes` 判别只会得到 False。
  - 因此这些入口读到的行从未被写入：`api/task_creation_service.py:533-541`（创建）、`api/task_update_service.py:227`（F6 切换 Profile）、`core/ci_failure_collector.py:681`（CI 自修复跳过）、`api/harness_catalog.py:337`（公开 catalog 的 per-harness readiness）。同族读取方却统一按「快照 V2 契约」判别并读作用域 B：`api/task_creation_service.py:188-195`（retry）、`api/tasks.py:826`、`core/issue_task_order.py:364`、`scheduler.py:1637`、`api/harness_catalog.py:352`，admin 摘要亦用 `bool(eligible_v2_harness_keys(profile))`（`api/worker_profiles.py:582`）。症状：同一 Profile 的 admin 面板显示 `ready`，而任务表单 catalog 里四个 Harness 全是 `availability=unknown / reason=runtime_not_verified`。
  - 现有测试全部 mock 掉该函数，未覆盖作用域选择：`tests/unit/test_task_worker_profile_selection.py:348-357`（patch `readiness_for_profile`）、`tests/unit/test_harness_catalog_api.py:326-345`（patch 同族函数）、`tests/unit/test_worker_profile_admin_contract_api.py:289-337`（直接以 `require_content_inventory=True` 造行），因此分歧不会被测试发现。
- **影响**：某个已校验 Profile 的 Kit 随后消失/被篡改（作用域 B 行已写 `unavailable`）或 Kit inventory 把所选 Harness 标为 `absent` 时，§16.3/§11.3 契约要求的创建期 `409 worker_runtime_unavailable` / `harness_cli_unavailable` 不会触发——任务以 201 创建，之后由 Scheduler 门禁（读作用域 B）park 或失败，用户看到「已创建但等待/失败」而非前置拒绝；CI 自修复也不会按设计 skip 而是走到后续阶段失败。同时公开 catalog 在成功校验后仍对所有 Harness 报 `unknown`，前端无法据目录区分 present/absent，只能放行。
- **建议**：让读取侧与写入侧使用同一权威，取「统一到严格作用域」的方向（否则 Scheduler/retry/catalog 所读的作用域 B 将无人写入）：最小改动是把 `readiness_for_profile()` 的作用域判定改为 `require_content_inventory=bool(eligible_v2_harness_keys(profile))`（与 `api/worker_profiles.py:582` 一致）；若确认 `v2_only` 下不再需要 V1 作用域，可直接删除 `runtime_readiness_fingerprint()` 的双作用域分支与 `profile_requires_content_inventory()`，保留单一严格作用域，避免今后再次分叉。
- **验证**：已运行无副作用内联复现（`cd backend && .venv/bin/python -c "..."`），输出：`eligible_v2 (verify gate): ('claude',)`、`profile_requires_content_inventory: False`、`scope A (legacy): loc`、`scope B (strict): d6e5b1284fec08d5...`。修复后建议补一条不打桩的门禁测试：向作用域 B 写入 `unavailable` 后 `create_task` 必须返回 409。本次**未运行**需要 DB/Docker 的端到端验证。

### RTB-02 `pi/v1` options 被校验并冻结，但 worker 侧无任何消费者
- **等级**：P2
- **位置**：`backend/app/core/harness_options.py:39`（提交 `cbad9e56`）
- **证据**：`harness_options.py:39-43` 把 `thinking_level`/`steering_mode`/`follow_up_mode` 列为 `pi/v1` 的 Task override 白名单，`:72-95` 用 Pydantic 校验并给默认值；`core/worker_profiles.py:796-810`（`_freeze_harness_options`）与 `:959-960` 把结果冻结进 `harness_config_snapshot["options"]`，`core/worker_task_lifecycle.py:668-676` 按所选 Harness 写入 `CODIFY_HARNESS_OPTIONS_JSON`。但 worker 侧消费者只有两个：`deploy/worker-entrypoint/harness/adapters/codex.sh:123-145`（`reasoning_effort`）、`opencode.sh:143-172`（`agent`/`command`/`model_variant`）；全仓库 `CODIFY_HARNESS_OPTIONS_JSON` 命中仅这两处，`pi.sh`、`pi_bridge.py`、`pi_owner.py`、`harness/runners/pi-run.sh` 均不读取该变量，`pi.sh:184-200` 写出的 `models.json` 只有 provider/model/apiKey，无 thinking 字段。catalog 仍对外声明 `pi/v1` 与 steering/follow_up 能力（`core/harness_registry.py:463-490`、`deploy/worker-entrypoint/harness/manifest.json:97`）。
- **影响**：`POST /api/tasks` 携带 `harness_options: {"pi": {"thinking_level": "high"}}`（或 Profile 默认值同理）会被接受、写入冻结快照并计入 `effective_configuration_digest`，但 Pi 仍按 CLI/模型默认思考级别执行：调用方看到的冻结执行契约与实际执行不一致，且没有任何日志/告警提示该选项未生效。与 `tasks/unit/test_harness_options.py` 的 16 条通过测试无关——那些测试只覆盖校验与合并，不覆盖消费。
- **建议**：二选一——在 Pi 适配器/runner 中按冻结 options 显式设置思考级别（Pi CLI 已提供 thinking level 能力，见 `deploy/worker-cli/pi/CHANGELOG.md` 的 `get_available_thinking_levels`），或在接线落地前把 `pi/v1` 从 `TASK_OVERRIDE_KEYS`/`OPTION_VALIDATORS` 移除并在 catalog 标注未接线，避免对外接受一个无效契约。
- **验证**：静态证据（消费点 grep + 适配器源码 + 冻结写入路径）。未运行 Pi 真实任务，未验证 Pi 是否可通过配置文件等价设置思考级别。

### RTB-03 §13.4 容器错误重探被移除后遗留不可达代码与失效文档
- **等级**：P3
- **位置**：`backend/app/core/worker_task_lifecycle.py:756`（提交 `cbad9e56`）
- **证据**：基线 `8081c946^:backend/app/core/worker_task_lifecycle.py:487-503` 在 `create_execute_container` 的 `except Exception` 中调用 `is_kit_mount_error()` + `recheck_runtime_on_container_error()`；本次改动删除了该 import 与该分支（`git diff 8081c946^..HEAD -- backend/app/core/worker_task_lifecycle.py` 显示删除 `is_kit_mount_error`/`recheck_runtime_on_container_error` 导入与「§13.4: a Kit mount/entrypoint error must trigger the same strict probe」整段），现为裸 `except Exception: raise`（当前 `:756-757`）。结果：`worker_runtime_readiness.py:1452`（`is_kit_mount_error`）与 `:1470`（`recheck_runtime_on_container_error`）在 `backend/app` 与 `backend/tests` 内**已无调用者**；`WorkerRuntimeUnavailableError`（`:1395`）在生产代码中无处抛出，而 `core/worker_task_outcomes.py:110-120` 专为它准备的 `worker_runtime_unavailable` 结构化失败分支因此不可达；`:1395-1405` 的 docstring 仍写着「Raised in the container error path (§13.4)」。行为变更本身是刻意的——测试已改写为断言新语义（`tests/unit/test_worker_profile_runtime.py:738-770`「A Kit create error remains a Docker/runtime error without re-probing」）。
- **影响**：功能上有 Scheduler 门禁与容器内 launcher 校验兜底，不产生错误交付；但残留 3 个不可达符号 + 1 个不可达错误渲染分支 + 与实现矛盾的 docstring，会让后续维护者误以为「Kit 在创建/启动期消失」会被自动重探并标记 `unavailable`（实际只有显式 `verify-runtime` 会刷新 readiness，Kit 消失后每个新任务都会以泛化 Docker 错误失败，operator 需自行识别 `bind source path does not exist`）。
- **建议**：要么恢复容器错误路径的重探调用（与 §13.4 文档一致），要么删除 `is_kit_mount_error`、`recheck_runtime_on_container_error`、`WorkerRuntimeUnavailableError` 及 `fail_execute_task` 中对应分支并更新 §13.4 相关注释，避免两套语义长期并存。
- **验证**：基线/当前调用点对照 + 全仓库无调用者（grep）+ 测试语义已改写。静态推理，未运行。

### RTB-04 共享配置失效只递增 image generation 且不清空 `worker_kit_identity`
- **等级**：P3
- **位置**：`backend/app/api/worker_shared_configuration.py:378`（提交 `cbad9e56`）
- **证据**：共享配置 PATCH 的失效语句只处理镜像族字段——`api/worker_shared_configuration.py:378-393` 置空 `image_digest`/`verified_at`/`verified_runtime_configuration_digest`/`v2_worker_image_identity`/`v2_harness_verification_evidence` 并 `v2_worker_image_identity_generation + 1`，**不**清空也不递增 `worker_kit_identity` / `worker_kit_identity_generation`；对照 Profile PATCH（`api/worker_profiles.py:1601-1631`，两者同时清空并递增）、`verify`（`:854-871`、`:1155-1180`）与 `_clear_profile_verification`（`:637-656`，同时递增）。共享配置恰是 `worker_kit_source=system` 时 Kit 坐标的来源（`core/worker_shared_configuration.py:88-118`、`:236`）。
- **影响**：当前不可利用——`worker_kit_identity_generation` 全仓库只写不读（无任何判定引用；判定统一使用 `v2_worker_image_identity_generation`，如 `api/worker_profiles.py:858`、`:644`），且共享 PATCH 已清空 verification evidence，使旧 Kit identity 无法通过 `validate_v2_harness_evidence`（`core/worker_profiles.py:211-247`）进入新 Snapshot。风险是语义重叠：两条 generation 计数只有一条生效，共享 Kit 变更后 Profile payload 的 `worker_kit_identity` 仍显示旧 Kit 摘要；后续若以 kit generation 做 CAS/失效判断极易误用。
- **建议**：在共享失效语句中一并 `worker_kit_identity=None` 且 `worker_kit_identity_generation = ... + 1`（与 Profile PATCH 对齐），或直接删除未被判定的 `worker_kit_identity_generation` 列，保持单一 identity generation。
- **验证**：静态证据（三处失效语句 + 该列全部读写点：`models.py:1067`、`api/worker_profiles.py:655/867/1181/1194/1629` 等）。未运行验证。

### RTB-05（INFO）未注册命名空间与非选中 Harness 的 options 被静默接受
- **等级**：INFO
- **位置**：`backend/app/core/harness_options.py:166`
- **证据**：`validate_namespaced_options()` 对 `NS_TO_OPTIONS_SCHEMA` 未登记的命名空间原样透传（`harness_options.py:166-170`），`validate_task_overrides()` 对未登记命名空间直接 `continue` 丢弃（`:201-203`）。而冻结 manifest 为 claude 声明了 `options_schema: "claude/v1"`（`deploy/worker-entrypoint/harness/manifest.json:36`），公开 catalog 会原样返回该 schema 名（`core/harness_registry.py:463-490`）。因此 Profile 可保存 `harness_options: {"claude": {...任意 JSON...}}`（甚至 `{"foo": ...}`）进入快照与 `effective_configuration_digest`；Task 侧为未选 Harness 提交的 override（例如 claude 任务提交 `{"pi": {...}}`）也会被冻结却永不生效（执行时只读 `frozen_options.get(attempt.harness_key)`，`core/worker_task_lifecycle.py:668-676`）。
- **影响**：无运行时漏洞（claude.sh 不读 `CODIFY_HARNESS_OPTIONS_JSON`；pi/opencode/codex 适配器各自做二次白名单校验，`opencode.sh:150-160`、`codex.sh:124-134`），但冻结快照/digest 会携带无效数据，调用方无法从响应区分「已生效 / 被忽略」，catalog 声明的 `claude/v1` 也没有任何校验器对应。
- **建议**：对未登记命名空间显式报错或显式回显「已忽略」；Task override 增加与 `harness_key` 的交叉校验（不匹配即拒绝）。
- **验证**：静态证据 + `tests/unit/test_harness_options.py`（16 passed，仅覆盖已知命名空间）。

### RTB-06（INFO）capability 上界校验只拒绝布尔 `True`，非布尔真值绕过且消费方判定不一致
- **等级**：INFO
- **位置**：`backend/app/core/harness_registry.py:436`
- **证据**：`validate_v2_manifest_adapter_capabilities()` 仅在 `value is True and upper.get(name) is False` 时报错（`harness_registry.py:436-460`），`core/harness_protocol.py:756-808` 的 `validate_manifest` 只校验 capability 名属于 `HARNESS_CAPABILITY_KEYS`（`:836-843`），不校验类型。消费方判定不一致：`core/task_harness_commands.py:118` 用 `... is True`（严格），`core/worker_task_lifecycle.py:496-499` 用 `bool(...)`（真值）。因此 manifest 写成 `"steering": "false"` 这类非布尔值时，后端上界校验放行、attempt 会以 `control_supported=True` / `control_state="starting"` 打开命令门（`:500-510`），而命令 API 仍会以确定性 rejection 拒绝 steer/follow_up。
- **影响**：后端「manifest 只能收紧、不能扩大」的关闸可被非布尔真值绕过；端到端需要仓库内 manifest 写错类型才会触发，且预启动校验容器内的 `deploy/worker-kit/validate-runtime-manifest.py:234-243` 有 `isinstance(value, bool)` 检查可拦住已校验 Profile 的候选 manifest，故实际风险有限，但两处判定不一致会长期误导。
- **建议**：在 `validate_v2_manifest_adapter_capabilities`/`validate_adapter_capabilities` 中要求 `isinstance(value, bool)`，并把 `worker_task_lifecycle` 的真值判定改为 `is True`，与命令 API 保持一致。
- **验证**：静态证据（校验函数 + 两个消费点）。未构造畸形 manifest 实跑。

### RTB-07（INFO）`[V1 遗留, V2 依赖]` host_mount runtime 写入期不校验 version/binary_digest
- **等级**：INFO
- **位置**：`backend/app/core/harness_registry.py:220`（提交 `cbad9e56`）
- **证据**：`validate_harness_runtimes()` 的 host_mount 分支只要求 `executable_path` 为绝对路径（`:208-225`），`version`/`binary_digest` 可缺省或非 64 位十六进制；直到 `verify-runtime` 阶段 `_verification_cli_identity()`（`api/worker_profiles.py:691-760`）经 `validate_v2_cli_identity()`（`core/worker_profiles.py:142-179`）才抛 422 `harness_cli_unavailable`。基线 `8081c946^:core/harness_registry.py:121-130` 同样未校验这两项，故缺口本身是 V1 遗留；V2 让它变「更晚才致命」——host_mount 的 version/digest 现在是 per-Harness verification evidence 的必需字段（`api/worker_profiles.py:691-760`、`core/worker_profiles.py:211-247`）。
- **影响**：管理端可保存一个永远无法通过校验的 Profile，错误延后到 verify 才暴露；不产生错误执行（无 evidence 即无 Snapshot、无任务）。
- **建议**：对 host_mount 的 `version`/`binary_digest` 在写入期做与 `validate_v2_cli_identity` 同构的校验，或明确文档化「host_mount 身份在 verify 期声明」。
- **验证**：静态证据（两处校验函数对照 + 基线对照）。未运行验证。

## 3. 逐项核查记录

| # | 不变量/契约 | 结论 | 依据 |
|---|---|---|---|
| 1 | 编译期 allowlist 只有 `pi/opencode/claude/codex`，OMP 不可选 | 通过 | `core/harness_registry.py:24` `HARNESS_KEYS`；`core/harness_protocol.py:631` `APPROVED_MANIFEST_ADAPTER_KEYS`；`:791-795` manifest 出现未批准 adapter 直接 fail closed；`validate_harness_key` 被 `validate_enabled_harnesses`（`:161`）、`capability_policy`、`validate_protocol_compatibility`、`validate_harness_runtimes`（`:177`）共用 |
| 2 | 系统 capability upper bound 在后端，manifest 只能收紧 | 通过（布尔类型缺口见 RTB-06） | `harness_registry.py:61-81` `V2_SYSTEM_CAPABILITY_UPPER_BOUND` + `:436-460` 逐 adapter 校验；在构建期（`worker_runtime_bundle.py:300`）与目录投影期（`harness_registry.py:463-490`）都会执行 |
| 3 | Runtime Bundle digest 递归自 manifest 文件清单（非写死数组） | 通过 | `worker_runtime_bundle.py:116-138` `bundle_manifest_digest_from_files`（canonical `{path,size,sha256}`、按 path 排序）；绑定期用 `_controlled_source_files`（`:365-380` + `:428-478`）真实字节替换 `manifest["files"]`（`:472-478`）；V1 构建/持久化入口已改为抛错（`:412-426`）；装载期按冻结清单重算并比对 DB 绑定（`:958-1025`） |
| 4 | 每个 Adapter 独立 digest；共享库变更影响所有 Adapter | 通过 | `worker_runtime_bundle.py:166-215` `adapter_digest_from_manifest_files`（`own ∪ shared`）；`:278-292` 计算私有前缀作用域（`:100-110` 代码固定前缀 `worker-entrypoint/harness/adapters/<key>`），`shared = files − ∪private`；单测 `tests/unit/test_worker_runtime_bundle_v2.py::test_shared_file_change_alters_every_adapter_digest`、`::test_adapter_digests_are_independent_for_own_files`（本专题实跑该文件 12 passed） |
| 5 | digest 计算稳定（排序/路径规范化/归档元数据） | 通过 | 受控文件按 `relative.as_posix()` 排序（`:365-380`）；JSON 统一 `sort_keys=True, separators=(",",":")`（`:132-137`、`:210-214`、`:553-580`）；归档固定 `mtime=0/uid=0/gid=0/uname=""`（`:400-410`）与固定写入顺序（`:621-655`）；归档路径统一经 `_archive_name` + `RUNTIME_ARCHIVE_ROOT` 归一（`:390-397`）；符号链接按目标字节读取，不写链接元数据 |
| 6 | 缺失文件 fail closed | 通过（后端 + 校验容器双层） | 后端：`_controlled_paths` 对 `deploy/entrypoint.worker.sh` 与 `deploy/worker-entrypoint/` 缺失即 `RuntimeError`（`:365-380`）；按 Adapter 的缺失由校验容器兜底：`deploy/worker-entrypoint/verification.sh:12-55` 要求被选 Adapter 的 `.sh` 必须出现在 `files` 且字节匹配，否则候选 manifest 校验失败 → 无 verification evidence → 无法创建任务（故「Adapter 私有作用域为空」在实践中不可达，不单列问题） |
| 7 | Kit inventory `present` 条目字节/SHA/size/可执行位不符 → 整 Kit fail closed | 通过 | `worker_runtime_readiness.py:1048-1085`：逐 present 条目流式哈希比对，缺失/不可执行/尺寸或 SHA 不符一律 `READINESS_UNAVAILABLE + worker_kit_invalid`；另有完整内容清单逐条严格比对（`:1024-1046`，`content_inventory` 与挂载字节必须完全相等，含硬链接归一）；离线同构校验 `deploy/worker-kit/verify-kit-content.py:56-105,166-330`、`deploy/worker-kit/install.sh:159-190` |
| 8 | adapter baseline 差异只产生 advisory warning，不是硬门禁 | 通过 | 后端从不以 `source.artifact_version/artifact_sha256` 作门禁（仅 `worker_runtime_bundle.py:526-531` 注释提及）；advisory 在 shell 侧：`deploy/worker-kit/verify-runtime.sh:247-268`、`adapters/pi.sh:63-71`、`opencode.sh:62-70`、`claude.sh:97-103`、`codex.sh:84-90`。注：manifest 的 `artifact_sha256` 当前是占位符 `"<computed at freeze>"`（`manifest.json:15,44,73,105`），使 SHA 维度 advisory 恒告警（噪音，非门禁） |
| 9 | `absent` 条目处理（不接受路径/版本，且被判不可用） | 通过 | `worker_kit_inventory.py:160-237`：四 key 必须齐全，absent 只允许 `not_selected|missing_payload` 且禁止携带 payload 字段；`readiness.py:1343-1362` `is_harness_available` 仅显式 `present` 为 True；`:1364-1390` 结构化拒绝细节（含 reason_code/kit_version）；`missing_payload` 转脱敏 warning（`worker_kit_inventory.py:263-289`）；执行期拒绝路径 `core/worker_profiles.py:142-179` + `worker_task_lifecycle.py:513-551`（`HarnessCliUnavailableError`） |
| 10 | harness_options：类型校验 fail closed、task_override 白名单、deep merge 确定性、未知命名空间 | 通过（附 RTB-05） | `harness_options.py:56/72/106` 三处 `extra="forbid"`；枚举与正则校验 `:58-112`；override 白名单 `:39-43` + 执行 `:207-214`；`deep_merge_options` 按 namespace 排序、override 覆盖、显式 null 可清除、输出 `dict(sorted(...))`（`:229-262`）；`validate_task_overrides` 用 `exclude_unset=True` 保留偏量语义（`:220-227`） |
| 11 | Snapshot 冻结：options/identity 进入 fingerprint，运行时不读 Profile | 通过 | `core/worker_profiles.py:842-981` 冻结 image/kit identity、per-harness evidence、capabilities、options；digest 覆盖 `harness.key/config`（`worker_shared_configuration.py:322-410`、`:451-482`）；执行期四项身份交叉校验只读快照（`worker_task_lifecycle.py:407-460`）；容器输入只用快照（`core/worker_profiles.py:1118-1160`、`worker_runtime.py:75-101`）；绑定后不回读 checkout（`worker_runtime_bundle.py:582-619` 显式 `del source_dir`，`tests/unit/test_worker_runtime_bundle.py:225-237` 覆盖） |
| 12 | 环境变量由 `model_protocol` 决定；无冲突注入；密钥不入日志 | 通过 | `worker_runtime.py:392-472`：protocol 不在 allowlist 即 `RuntimeError`（`:413-419`），`anthropic_messages` 只注入 `ANTHROPIC_*`/`CLAUDE_*` 系列（`:461-472`），其余只注入 `OPENAI_*`，两条互斥；自定义环境在写入与装配两侧都过 `validate_worker_environment_variable_key`（`worker_environment_variables.py:105-112`、`worker_runtime.py:404-405`），保留键集合与冻结前缀（`ANTHROPIC_/CLAUDE_/CODEX_/CODIFY_/OPENAI_/OPENCODE_/PI_`，`:16-101`）禁止覆盖 provider/CLI/attempt 变量；`capture_provider_runtime_snapshot` 只记录 `api_key_configured: bool`（`worker_runtime.py:326-345`）；verify 响应只回显 secret 变量**名**（`api/worker_profiles.py:1200-1212`） |
| 13 | hard cut：execute/schedule/retry/resume/continue 覆盖；V1 不能作 continue 来源 | 通过 | 中央策略 `core/harness_execution_policy.py:75-230`（非 V2 bundle/attempt → `legacy_contract_not_executable`）；API 写入点 `api/task_action_routes.py:418`(execute)/`:484`(schedule)/`:370`(override-status)/`:95`(cancel PENDING|QUEUED)、`api/task_update_service.py:94`(update)、`api/task_creation_service.py:142`(retry)；创建期 `require_creatable_bundle_v2`（`:675`）+ `require_task_executable_contract`（`:728`）；Scheduler `scheduler.py:353,1502,3117`；Worker 启动 `worker_task_lifecycle.py:516,1029`；retry 复用 V1 bundle 在绑定层被拒（`worker_runtime_bundle.py:700-722`）；continue/resume 要求完整 projected lineage（`worker_task_lifecycle.py:597-604`、`issue_task_lineage.py:69-83`），V1 任务这些列为 NULL → 直接拒绝；resume 只认精确 `(harness, namespace, generation)` 行（`issue_task_lineage.py:86-160`） |
| 14 | Catalog API 只返回可展示 schema；不暴露启动命令/宿主路径；鉴权 | 通过（附注） | 投影白名单 `core/harness_registry.py:463-490`（key/display_name/support_tier/control_transport/model_protocols/capabilities/options_schema，不含 `source.repository`/路径）；host_mount 只返回状态与 `host_mount` 原因码，不返回 `executable_path`（`api/harness_catalog.py:69-79`）；路由级鉴权 `main.py:402-407`（`require_authenticated_user`），任务级目录另需项目访问权（`api/harness_catalog.py:400-413`）。附注：`control_transport` 整块直传，`validate_manifest` 只比对 `(kind, protocol)` 两项（`harness_protocol.py:811-824`），多写的键会进入响应——但 manifest 来自仓库、非用户输入 |
| 15 | readiness：TTL 移除后判定正确、并发 CAS、失败不污染缓存 | 通过 | `read_runtime_readiness`（`:379-408`）忽略历史 `ready_until`，`serialize_runtime_readiness` 恒回填 `None`（`:162-183`）；`begin_runtime_check` 行锁 + generation 自增（`:490-545`）；`finish_runtime_check` 把 generation 写进 `UPDATE ... WHERE` 并以 `rowcount` 为唯一成功依据（`:547-600`）；瞬时失败不留结论并清理无结论行（`:1223-1301`、`:1303-1340`）；verify 侧再以 `(profile_id, generation)` 条件 + `rowcount` 收敛（`api/worker_profiles.py:854-871`、`:1132`、`:1155-1180`）。语义：ready/unavailable 一直有效到下一次显式 re-check（无自动过期），与 §11.3「显式 re-verify」一致 |
| 16 | worker_profiles API：enabled/default 校验、force-disable、错误信息不泄露 | 通过 | `enabled_harnesses`/`default_harness_key` 在请求校验与读改写路径上都校验且 default 必须在 enabled 内（`api/worker_profiles.py:169-178`、`:1427-1446`、`core/harness_registry.py:161-175`）；disable 拒绝 default 与仍有活跃 issue 的 Profile（`core/worker_profiles.py:1258-1263`、`api/worker_profiles.py:1672-1685`）；force-disable 先关闭关联 issue 再禁用（`:1699-1725`）；错误细节不含 TLS 路径/凭据（`api/worker_profiles.py:620-632`、`readiness.py:476-492`、`:1364-1390`） |
| 17 | 新建 Profile 默认 harness 仍为 `claude` | 与计划差异（不记缺陷） | `api/worker_profiles.py:1317-1326`、前端 `WorkerSettingsPanel.vue:1391,1909` 均为 `["claude"]`/`claude`，`alembic/versions/` 内无「新行默认改为 pi」的迁移。计划 §8.6/Phase 5 把该默认值迁移绑定在**线上**正式硬切（阶段总结标注 R5「未执行」），因此当前状态可解释；若线上硬切已完成则属遗漏交付项 |

## 4. 局限与未验证项

- 无真实 Docker daemon / Worker Kit / 四 Harness CLI：所有 readiness 探针行为（Mount 元数据校验、archive API 流式哈希、完整内容清单比对）为静态推理；只有纯函数层判别（RTB-01）与两个纯逻辑测试文件被实跑。
- Kit 侧两条路径分处后端（Python）与 Kit 构建/安装脚本（shell/Python），本次只做源码与调用点对照，未在真实 Kit 上双向复现。两侧内容清单算法（`readiness.py:731-...` vs `deploy/worker-kit/verify-kit-content.py:251-330`）在「硬链接指向符号链接」这一形态上实现不同（后端 `resolve_hardlink` 不做符号链接链解析，离线校验器会解析），真实 Nix 闭包是否出现该形态未验证——INFO 级疑点，证据不足，未记为 finding。
- 未运行 Pi/OpenCode/Codex/Claude 真实任务，故 RTB-02 只证明「后端冻结的 options 无 worker 侧消费者」，未验证 Pi 是否可在容器内通过配置文件等价设置思考级别。
- manifest 的 `artifact_sha256` 占位符使 `verify-runtime.sh:247-268` 的 SHA advisory 恒告警；仓库内未找到打包期替换点，是否由离线发布脚本替换未确认（发布流程归 T15）。
- 前端是否按 catalog/availability 正确禁用不可用 Harness（RTB-01 的用户可见后果）归 T12；本专题只核查后端投影内容。
- 与 T01/T02/T07/T09/T11 共享的边界（command capability 读取、attempt/事件状态、runner/manifest 校验、Kit 构建与安装、交付与清理）只做消费点核查，未重复其深入结论。
- `[V1 遗留]` 观察（未达 finding 门槛）：自定义环境变量只按「保留键 + 冻结前缀」过滤，未封禁 `PATH`/`HOME`/`LD_PRELOAD` 等通用加载器变量；该能力为 admin-only 且 V1 已存在，V2 未放大，故仅记录。
