# Worker Profile / Worker Kit 宽松运行时失败策略改造方案

日期：2026-09-24
状态：Implemented（2026-09-26）
范围：Worker Profile、系统 Worker Kit 继承、运行时 Verify、任务创建、Scheduler、Worker Kit launcher

相关文档：

- [Worker Kit 可信安装与 Task 启动校验边界设计](../specs/2026-09-03-worker-kit-validation-boundary-design.md)
- [Worker Profiles Design](../specs/2026-06-24-worker-profiles-design.md)
- [Worker Kits](../../dev/worker-kits.md)

本方案调整了旧版 Kit 校验边界设计中的 **Task 启动时 manifest SHA-256 必须等于快照值** 规则：快照值保留为验证时基线，启动时差异改为告警。管理员 Verify 的完整 Kit 内容校验，以及 Task 的所选 CLI 和 Runtime Bundle 文件校验仍为硬门禁。

## 1. 结论

Codify 是内部系统，不需要把所有“尚未证明一定可运行”的情况都转换成硬失败。

本方案将运行时检查分成三类：

1. **硬失败**：安全、数据完整性或执行身份不明确，继续阻断；
2. **等待恢复**：已冻结完整执行身份的任务遇到暂时不可用的运行环境，使用现有 `PENDING` 语义等待；
3. **告警继续**：Kit manifest 漂移、Adapter 漂移、未选中能力缺失等兼容性问题，在当前任务所需文件仍通过校验时不阻止运行。

不新增历史版本、回滚、撤销或新的任务状态，优先复用现有 Profile 验证、runtime readiness、`PENDING` 和结构化事件。

## 2. 当前问题

当前链路存在几处过度保守的前置门禁：

| 控制点 | 当前行为 | 目标行为 |
| --- | --- | --- |
| 创建任务时已验证的运行时暂不可用 | API 直接返回 `409` | 冻结完整身份并创建 `PENDING` 任务；按故障类型等待恢复 |
| 重试时已验证的运行时暂不可用 | API 直接拒绝重试 | 复用完整原快照，创建等待中的重试任务 |
| 快照没有已观测 Kit 版本 | 生成快照和启动容器失败 | V2 mounted Kit 仍拒绝创建；版本只能来自有效验证证据 |
| Kit 版本或 manifest 变化 | Scheduler 已告警，但 launcher 仍退出 | 保留快照基线，记录实际版本和 manifest SHA-256；当前任务所需校验通过则告警继续 |
| 非选中 Harness 或可选工具缺失 | 全量 Kit/Profile 验证失败 | 保留其他已验证 Harness 的证据；可选能力产生告警 |
| Profile smoke 或辅助检查失败 | 清除验证状态并阻断使用 | 失败的 Harness 不产生执行证据；非关键辅助检查只告警 |
| V2 执行身份不完整 | 任务失败 | V2 契约本身仍然硬失败 |

主要代码位置：

- 任务创建 readiness 门禁：[task_creation_service.py](../../../backend/app/api/task_creation_service.py)
- 任务快照和容器配置：[worker_profiles.py](../../../backend/app/core/worker_profiles.py)
- 运行时 readiness：[worker_runtime_readiness.py](../../../backend/app/core/worker_runtime_readiness.py)
- Scheduler 领取前检查：[scheduler.py](../../../backend/app/scheduler.py)
- Kit launcher：[main.go](../../../deploy/worker-kit/launcher/main.go)
- Worker Kit 全量验证：[verification.sh](../../../deploy/worker-entrypoint/verification.sh)

## 3. 失败分级

### 3.1 必须硬失败

以下情况意味着系统无法安全或明确地启动任务：

- Worker Kit 路径非法、路径穿越或挂载冲突；
- `manifest.json` 缺失、损坏、无法解析或缺少合法身份信息；
- 平台或架构不匹配；
- launcher、entrypoint 或当前任务选中的 Harness 不存在；
- Runtime Bundle、选中 CLI 或归档文件缺失、被篡改或 digest 不匹配；
- V2 任务缺少冻结的 image、Kit 验证基线、Harness 或 Bundle 身份；
- 权限、任务归属、数据库一致性和任务生命周期约束错误；
- 任务已经实际启动后，Harness 进程返回非零退出码。

这些检查保护安全边界和当前任务实际使用的文件完整性。Kit manifest 的验证时 SHA-256 仍写入 Snapshot/Bundle 供诊断，但不再保证整个 Kit 的字节与创建 Task 时完全相同。

### 3.2 等待恢复

仅当 Profile 已经验证过、当前选中 Harness 的 V2 证据仍有效，且 Task 能冻结完整的 image、Kit 验证基线、CLI 和 Bundle 身份时，以下情况才不阻止创建或重试：

- Docker Host 暂时不可连接；
- 已验证的 Worker Kit 挂载目录暂时不存在（`worker_kit_not_found`）；
- 已验证的 Worker image 暂时不能在目标 Host 使用。

`worker_kit_not_found` 只指整个挂载目录暂时不存在；目录存在但 `manifest.json` 缺失属于 Kit 损坏。未验证 Profile、选中 Harness 缺少 CLI 证据、Kit manifest 无效或文件完整性失败不属于等待。`readiness=unknown` 且冻结身份完整时，也不需要等待，沿用现有 V2 启动校验。

处理方式：

1. 创建或重试接口冻结完整身份和 Kit 验证基线，任务使用现有 `PENDING` 状态；
2. Docker / image 的瞬时故障沿用 Scheduler 的 transient 重试，不写入持久的 Kit `unavailable` 结论；
3. 已确认 `worker_kit_not_found` 时，Scheduler 不反复把任务从 `PENDING` 提升到 `QUEUED`；管理员恢复同一 Kit 后显式 Verify，将 readiness 更新为 `ready`，任务再继续；
4. 等待原因通过现有任务队列上下文和 readiness 投影展示，用户仍可取消。

不新增 `WAITING_FOR_RUNTIME` 等状态。

### 3.3 告警并继续

以下情况不应被视为当前任务不可执行：

- Adapter 版本或 digest 漂移，但文件仍可执行；
- Kit manifest 的实际 SHA-256 或版本与 Task 验证时基线不同，但格式、平台、必需路径和所选 CLI 校验通过；
- 未选中的 Harness 在 manifest 中声明为不可用，或其 Profile smoke 失败；
- 当前任务不依赖的 CodeGraph、Mermaid、SSH 等可选工具缺失；
- 非关键 smoke 检查失败；
- 与当前任务无关、且 manifest 明确声明为不可用的 Kit 条目。

管理员 Verify 发现 manifest 声明文件存在但实际缺失、content inventory 或 digest 不匹配，仍判定 Kit 无效；普通 Task 启动不重新扫描完整 Kit，只校验当前任务实际依赖的路径、所选 CLI 和 Runtime Bundle。告警应进入验证结果；与某个 Task 有关的告警还须进入该 Task 的持久日志，不能只写 Scheduler 服务日志。

## 4. Worker Profile 语义

### 4.1 Kit 路径与版本分离

- `worker_kit_path` 是运行时定位信息；
- `worker_kit_version` 只能由实际读取的 `manifest.json` 产生；
- 不从路径名称、目录名称或管理员输入推断版本；
- 前端不提供可编辑的 Worker Kit 版本输入框；
- 验证区域只读展示当前实际观测到的版本。

### 4.2 系统继承型 Profile

系统继承型 Profile 只继承系统 Worker Kit 路径和相关运行模式：

- 不继承系统 Profile 的版本；
- 不复制其他 Profile 的版本或验证结果；
- 每个 Profile 按实际运行目标重新读取 manifest；
- 同一路径在不同主机或架构上的版本可以不同；
- Kit readiness 按实际运行目标和路径隔离；Profile 的 Harness 验证证据按 Profile 隔离。

### 4.3 哪些修改需要重新验证

以下修改会清除当前 Profile 的运行时观测和验证证据：

- 有效 Worker Kit 路径变化；
- 运行模式变化；
- 实际运行目标或平台变化；
- Worker image、挂载、传入 Verify 容器的环境变量或 Harness/CLI 运行配置变化；
- 系统 Worker Kit 路径变化，并且 Profile 继承该路径。

以下修改不需要重新验证：

- Profile 名称、描述；
- Provider、模型等不参与运行时 Verify 的选择；
- 不传入 Verify 容器的前后置脚本和运行指令模板。

无关字段保存时必须保留已有的 manifest 观测结果，避免完整表单提交造成无意义的验证失效。

## 5. 目标执行链路

### 5.1 保存和验证

Profile 保存不以运行时 Verify 成功为前提。保存只校验配置结构、路径格式、挂载冲突和保留字段。

Verify 分为三层：

1. **核心 Kit 能力**：manifest、完整 content inventory、launcher、entrypoint、平台、挂载和基本运行路径；
2. **每个已启用 Harness 的执行证据**：分别确认 CLI 身份和必要 Adapter，并记录各自的 smoke 结果；
3. **可选能力**：辅助工具和非关键 smoke。

第一层失败使 Kit 不可用；第二层仅决定对应 Harness 能否用于新的 V2 Task，其他 Harness 的成功证据不因某个 Harness 失败而丢失；第三层只产生告警。选中 Harness 缺少有效证据时，创建阶段拒绝 Task，不能以等待代替冻结身份。

核心 Kit 探测成功后，单独记录 manifest 版本和 Kit identity。后续 Harness 或可选 smoke 失败不能抹掉这条观测，但版本观测本身不等于 Profile 对所有 Harness 均可执行。对同一份未变更配置重新 Verify 时，Docker 瞬时故障或 `worker_kit_not_found` 只更新 readiness，不能先清空此前有效的 Profile 身份证据；确定的 Kit 完整性失败则使证据失效。验证写回仍需使用 generation/CAS，避免迟到结果覆盖新配置。

### 5.2 任务创建和重试

任务创建服务调整为：

- 先检查 Profile、选中 Harness 的验证证据及 Bundle，冻结 image、CLI、Bundle 身份，以及验证时的 Kit manifest SHA-256 和版本基线；任何必需证据缺失时仍拒绝创建；
- 身份完整但 readiness 为 `worker_kit_not_found`，或 Docker / image 遇到瞬时故障时，允许创建或重试等待中的 Task；
- readiness 报告 `worker_kit_invalid`、平台不匹配或已知完整性错误时仍拒绝创建；
- `readiness=unknown` 且身份完整时允许创建，真实启动仍须校验冻结身份；
- 重试复用原 Task 的不可变 Snapshot，不从当前 Profile 补填缺失身份。

### 5.3 Scheduler

Scheduler 调整为：

- `worker_kit_not_found`：保持或退回 `PENDING`，在 readiness 更新前跳过再次提升，避免每轮 `PENDING → QUEUED → PENDING` 和重复事件；恢复同一 Kit 后由管理员显式 Verify；
- Docker / image 瞬时故障：沿用 transient 重试，不把它们记成确定性的 Kit 损坏；
- `worker_kit_invalid`、V2 身份缺失或 Bundle 合同不匹配：当前 Task 硬失败；
- 有效 readiness 的 Kit manifest SHA-256 或版本与 Task 基线不同：发出告警，继续领取；真实容器仍校验所选 CLI 和 Bundle；
- 未选中 Harness 的可用性不参与当前 Task 的领取判断。

不做静默 Harness 替换。用户选中的 Harness 必须仍然是实际运行目标。

### 5.4 Launcher

launcher 的 Kit 处理改为：

1. 读取当前 Kit 的 manifest；
2. 计算实际 manifest SHA-256；与 Task 基线 SHA-256 或版本不同时输出结构化 warning，记录基线值和实际值；
3. 以当前 manifest 的版本作为实际运行版本；manifest 解析、schema、平台和必需路径校验失败仍退出；
4. 对 V2 Task 始终校验冻结的所选 CLI 路径、来源和文件 digest，以及 Runtime Bundle manifest、文件与 digest；任一失败仍退出。

这允许管理员在同一 Kit 路径更新兼容的内容；Task 的 Kit SHA-256 只表示创建时验证基线。实际版本和 manifest SHA-256 必须随 Task 告警持久记录，以便事后确认执行时使用的 Kit。未通过当前任务所需校验的更新仍会使 Task 失败。

## 6. 前端和可观测性

验证区域只读展示：

- 当前实际读取的 Worker Kit 版本；
- 实际运行平台；
- 最近验证时间；
- 各已启用 Harness 的验证结果；Kit inventory 中明确缺失的可选能力由 readiness 派生，非关键 smoke 警告在本次 Verify 结果中展示。

任务页面区分以下信息：

- `可执行`：冻结身份完整，且没有已知的运行时阻断；
- `等待运行时`：任务因暂时缺失的 Kit 或目标环境故障等待；
- `存在兼容性警告`：当前 Task 可继续，但 Adapter 或非关键能力存在差异。

等待原因使用现有 Task API 的 `waiting_reason` / runtime readiness 投影。Scheduler 的结构化日志仅供运维诊断；与具体 Task 相关的兼容性告警写入现有 `TaskLog`（`log_level=WARNING`，`log_type=runtime_warning`，`log_metadata` 含稳定原因码），任务页从现有日志接口和流读取。不新增数据库状态。至少保留以下原因码：

- `worker_kit_version_drift_warning`：Kit 版本与验证时基线不同；
- `worker_kit_manifest_drift_warning`：manifest SHA-256 与验证时基线不同；
- `worker_runtime_unavailable`：仅用于可等待的暂时故障；
- `optional_harness_unavailable`；
- `optional_runtime_tool_missing`。

两种 Kit 漂移告警都包含基线与实际的版本和 manifest SHA-256；同一次启动可合并写入一条 Task 日志。告警本身不代替 launcher 对所选 CLI 和 Runtime Bundle 的硬校验。

## 7. 实施顺序

### Phase 1：统一运行时语义

- 调整任务创建和重试的 readiness 门禁；
- 保留 V2 快照必须记录验证时的 Kit 版本与 manifest SHA-256 基线，以及冻结的所选 CLI 证据；
- 同配置的 Verify 遇到瞬时故障或 `worker_kit_not_found` 时保留此前有效证据，确定的完整性失败则使证据失效；
- 保证 Profile 无关字段保存不清除版本观测；
- 保证系统继承 Profile 只继承路径；传入 Verify 容器的环境变量等输入变化仍使执行证据失效。

### Phase 2：统一 Scheduler 和 launcher

- Scheduler 按 `worker_kit_not_found`、瞬时故障和 `worker_kit_invalid` 分流，已知等待任务在显式 Verify 前不反复入队；
- Scheduler 对 Kit 基线差异告警继续；launcher 记录实际 manifest SHA-256 和版本，并始终校验所选 CLI 与 Runtime Bundle；
- 保留平台、路径、Bundle、CLI 和 V2 身份硬校验。

### Phase 3：收窄全量验证

- Kit content inventory 继续完整校验；每个已启用 Harness 分别产生可用于创建 Task 的成功证据；
- 某个 Harness 验证失败不清除其他已成功 Harness 的证据，但该 Harness 不能被新 Task 选中；
- 非关键 smoke 失败不再清除核心 manifest 观测；
- Verify 结果明确区分 Kit 失败、各 Harness 失败和可选能力告警。

### Phase 4：前端和回归验证

- 删除所有可编辑的 Worker Kit 版本输入；
- 在验证区域展示 manifest 版本、各 Harness 结果和本次 Verify 告警；
- 通过现有任务队列上下文展示等待原因，通过 `TaskLog` 展示 Task 兼容性告警；
- 补齐后端、launcher、前端和真实任务回归。

## 8. 验收标准

### Profile 和继承

1. 修改名称、模型、Provider 或模板，不要求重新验证；修改传入 Verify 容器的环境变量或挂载仍要求重新验证；
2. 修改有效 Kit 路径或运行模式，需要重新验证；
3. 系统路径变化会使继承型 Profile 的旧证据失效；
4. 不同主机或架构可以在同一路径上观测到不同 Kit 版本；
5. 版本只能来自 manifest，不能来自路径或手工输入；
6. 保存继承系统 Kit 的 Profile 不再被后端拒绝；
7. 一个 Harness 的 smoke 失败不抹掉成功 Harness 的证据，也不允许缺少证据的 Harness 创建 V2 Task；
8. 同配置重新 Verify 遇到瞬时故障或 Kit 目录暂缺时，之前有效的执行证据仍可用于创建等待任务；manifest 损坏时不可继续用于新 Task。

### 任务和执行

1. 已验证 Profile 的完整 V2 身份可在 Docker / image 瞬时故障或 `worker_kit_not_found` 时创建等待任务；未验证 Profile 仍拒绝创建；
2. 重试复用完整原快照，已知暂时故障不会直接返回 `409`；
3. 已知 Kit 缺失的任务保持 `PENDING`，管理员恢复并 Verify 后自动入队，等待期间不重复提升/退回；
4. manifest SHA-256 或版本与快照基线不同，只产生包含实际值的 Task 告警；所选 CLI 与 Runtime Bundle 校验通过时仍可执行；
5. 未选中 Harness 声明不可用或非关键工具缺失不影响当前任务；管理员 Verify 发现 content inventory 损坏仍失败；
6. manifest 损坏、挂载冲突、平台不匹配仍然失败；
7. Runtime Bundle、所选 CLI 或归档文件 digest 不匹配仍然失败；Kit manifest 无法解析或与平台不兼容仍然失败；
8. 当前选中的 Harness 实际启动失败时，当前任务仍然正确失败；
9. V2 执行身份不完整时，任务仍然硬失败；
10. Task 兼容性告警在任务日志接口中可读，并能在任务页展示。

## 9. 非目标

- 不增加 Profile 历史版本系统；
- 不增加新的任务状态；
- 不引入自动 Harness fallback；
- 不取消路径、挂载、manifest 结构与平台、Bundle、所选 CLI 和 V2 必需身份校验；管理员 Verify 仍完整校验 Kit 内容；
- 不把实际进程失败改成成功；
- 不为内部系统引入独立的 strict/relaxed 配置开关；
- 不修改已完成任务的不可变 Snapshot。

## 10. 实施验证

- 后端相关单测：401 passed；恢复格式后的事件投影和 Worker 覆盖测试：145 passed。
- 前端 `WorkerSettingsPanel` 单测：40 passed；`npm run build` 通过。
- Worker Kit launcher 在 Linux/amd64 构建通过，model-proxy 的 `go vet` 和 Go 测试通过。
- 开发环境 backend、scheduler、nginx 已重建并健康；管理员 Verify Runtime 返回 HTTP 200，Kit `0.6.22` 的 Pi 与 OpenCode 分别验证通过。
