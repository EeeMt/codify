# Open-Harness V2 当前状态与硬切计划

**复核日期：** 2026-09-09

> 本文件只维护当前结论、证据边界、唯一下一工作包、退出条件和停止规则。
> Task/Issue 明细、逐次 Host 快照、digest、generation 和测试日志只保留在独立 evidence、
> runtime archive、数据库与 Git history 中。

## 1. 背景与执行决策

Codify 线上仍是少量用户使用的内测环境，可以停机发版和硬切；开发环境允许直接升级。因此本轮不再设计
长期 `dual_canary` 观察期、历史 Task 迁移、撤销列表、额外兼容 schema 或复杂回滚状态。

当前决策分两层：

- **允许进入：** 冻结干净 release candidate，并在开发环境停机切换到 `v2_only`；
- **暂不允许：** 直接把当前工作区或当前开发镜像用于线上硬切。必须先完成开发环境的 exact identity、
  migration 和四 Harness release smoke，再以同一套制品切线上。

V2 已不再处于主要功能开发阶段。后续推进指标只有三个：形成可追溯 RC、开发环境完成硬切、线上环境完成
硬切。不得用新增普通 smoke、generation、Bundle 编号或文档提交数代替这三个结果。

## 2. 当前完成度

| 工作包 | 状态 | 当前结论 |
| --- | --- | --- |
| R1：Internal Preview candidate | **完成** | 四 Harness 的 Image、Kit、Profile、Bundle 与真实 Host 已有历史证据 |
| R2：四 Harness hard-cut conformance | **完成，当前公共路径需最小重验** | Harness×protocol、lifecycle、command、cancel、recovery 和 delivery 基线已闭合；后续公共事件投影与 live-steering 去重修复必须绑定新 RC 做 release smoke |
| R3：正式 benchmark | **完成** | Pi/OpenCode formal benchmark 已完成；本轮不升级 CLI 或协议，不重跑 benchmark |
| R4.1：可信 Kit 启动边界 | **完成** | content-addressed Kit、完整 Verify、Task 热路径校验与 warm-start 已有证据 |
| R4.2：冻结 exact candidate | **开放** | 旧 candidate 已被后续源码和开发镜像替代；当前镜像没有 Git revision identity |
| R4.3/R4.4：交互与真实 Task | **历史证据完成，当前 RC 待四 Harness smoke** | 旧证据继续证明行为边界，但不能代替新 RC 的真实运行 |
| R4.5：发布确认 | **开放，按内测范围简化** | 改为单一 release owner 的备份、凭据、identity、窗口和 roll-forward 确认 |
| R4.6：开发 hard-cut go/no-go | **可进入准备，尚未执行** | 干净 RC、备份和切换前检查通过后执行开发硬切 |
| R5：线上 `v2_only` hard cut | **未执行** | 开发环境通过后，以同一套制品停机切线上 |

主要功能已经完成，包括：四 Harness Adapter/Bridge、Canonical Event、思考占位与正文边界、live steering、
取消与续跑、Task Snapshot、Runtime Bundle、Worker Kit、Git finalization/delivery、archive，以及覆盖
create/execute/schedule/retry/resume/Scheduler/Worker 启动路径的 `v2_only` 中央门禁。

## 3. 2026-09-09 当前事实

### 3.1 本地源码

- 当前 `dev` HEAD 已晚于旧 tracker 的 `079513e0` source anchor；之后包含公共事件生命周期显示和
  live-steering audit 去重修复，旧 candidate identity 已失效。
- `dev` 相对 `origin/dev` 为 ahead 60；是否 push 必须作为独立发布动作确认。
- 工作区还有 12 个未提交的 Provider/Analytics 相关文件。它们属于现有工作，不得被 V2 发布操作覆盖，
  也不得从 dirty worktree 构建 release。
- 本轮只读复核中，V2 相关 Backend focused tests 为 `156 passed`，Frontend focused tests 为
  `56 passed`，Frontend production build 通过。这是当前源码信号，不代替干净 RC 的完整测试。

### 3.2 开发环境

- Backend、Scheduler 和 NGINX 正常运行，但 Backend/Scheduler 仍为 `HARNESS_EXECUTION_MODE=dual_canary`；
- 长期服务均为 `AUTO_MIGRATE=false`，数据库 revision 仍为 `077_v2_worker_kit_identity`；
- Profile 4 启用 Pi、OpenCode、Claude、Codex，默认 Harness 为 Pi，Worker Kit 为 0.6.16，最近一次
  Verify generation 为 102；
- Backend/NGINX 于 2026-09-09 重新构建，但镜像没有 OCI source revision label，无法从当前镜像反推
  exact Git SHA；
- Task #543 处于 `pending`，计划于 2026-09-12 执行。硬切前必须记录参数并取消，切换后按新 RC 重建；
- 有一个 2026-09-01 遗留的 OpenCode 诊断容器。它不是硬切门禁；仅在确认无引用后于维护窗口精确删除，
  不执行广泛 Docker prune。

结论：开发环境健康只能证明现有 `dual_canary` 可运行，不能证明当前源码已经形成 release candidate。

## 4. 已有证据边界

以下证据继续有效，用于证明合同和历史行为；不要求重新跑完整矩阵：

- [R1 candidate evidence](../evidence/2026-08-31-open-harness-v2-r1-candidate.md)
- [R2 conformance evidence](../evidence/2026-09-01-open-harness-v2-r2-candidate.md)
- [R3 benchmark evidence](../evidence/2026-09-01-open-harness-v2-r3-benchmark.md)
- [R4.1 Kit boundary evidence](../evidence/2026-09-03-open-harness-v2-r4.1-kit-boundary.md)
- [R4.3/R4.4 live Host evidence](../evidence/2026-09-04-open-harness-v2-r4.3-r4.4-live-host.md)
- [four-Harness thinking probes](../evidence/2026-09-06-four-harness-thinking-probes.md)
- [R4-RC1 remote debug evidence](../evidence/2026-09-08-open-harness-v2-r4-rc1-remote-debug.md)
- [current Bundle real-task matrix](../evidence/2026-09-08-open-harness-v2-current-bundle-real-task-matrix.md)
- [R4.5 historical current-candidate audit](../evidence/2026-09-08-open-harness-v2-r4.5-current-candidate-audit.md)
- [dual-canary and production rollout Runbook](../../runbooks/multi-harness-rollout.md)

这些历史证据不能替代新 RC 的 Git SHA、image ID/digest、Kit、Bundle、Profile Snapshot 和真实 Task
identity。新 RC 只重验受后续公共路径变更影响的场景，不重跑完整协议矩阵或 20-task benchmark。

## 5. 唯一下一工作包：干净 RC + 开发环境硬切

### A. 冻结干净源码

1. 先完成、提交或隔离当前 12 个未提交文件；不得覆盖或夹带现有工作。
2. 选择一个明确 Git SHA 作为 RC source anchor，并记录与 `origin/dev` 的关系。
3. 在该提交上运行完整 Backend unit suite、Frontend unit suite、Frontend production build、Backend lint、
   shell syntax 和 `git diff --check`。
4. 任一 P0/P1 或测试失败都停止 RC；修复后更换 source anchor 并重新开始。

### B. 形成 exact composition

1. 从冻结 Git SHA 构建 Backend/NGINX，记录 `Git SHA → image ID/digest`；不再使用无法映射源码的
   `latest` 作为验收 identity。
2. 重新生成 Runtime Bundle 并比较 content digest：内容相同则复用既有不可变 identity，内容变化则生成
   新 Bundle；不得为了编号而重建。
3. Worker image 与 Kit 0.6.16 内容未变时直接复用，并记录 immutable digest/manifest；不升级 Harness CLI。
4. 将 Git SHA、Backend/NGINX、Worker image、Kit、Bundle、Profile 和四 Harness inventory 写入一份简短、
   脱敏的 RC evidence。
5. 只做一次管理员完整 Verify。结果必须为四 Harness `present`，readiness 为 `ready`，`ready_until=null`，
   image/Kit/Bundle 与 RC evidence 一致。

### C. 开发环境维护窗口

1. 确认 Docker context 为 `remote`，暂停新 Task 创建和 Scheduler promotion。
2. 排空 `running`/`queued`；记录并取消 Task #543，切换后重新创建。
3. 停止 NGINX、Scheduler 和 Backend，保留 PostgreSQL。
4. 执行一次 PostgreSQL 备份，并确认备份文件可读取。
5. 由唯一 migration owner 执行 reviewed target：

   ```bash
   MIGRATION_TARGET=078_remove_provider_driver \
     docker compose --env-file deploy/.env.test -f deploy/docker-compose.yml \
     --profile maintenance run --rm migrate
   ```

6. 将 `HARNESS_EXECUTION_MODE` 改为 `v2_only`；Backend/Scheduler 继续保持 `AUTO_MIGRATE=false`。
7. 启动 Backend、Scheduler、NGINX，运行 execution-mode preflight，确认两服务均报告 `v2_only`。
8. 确认默认路由使用四 Harness V2 Profile，默认 Harness 为 Pi；不修改已存在 Task Snapshot。

### D. 开发环境最小 release smoke

切换后每个 Harness 只创建一个真实 Task；四条任务合并覆盖公共路径和关键交付边界：

| Harness | 场景 | 必须检查 |
| --- | --- | --- |
| Pi | reasoning + live steering + Git delivery | native ACK、无重复 delivered audit、remote SHA、MR/结果卡一致 |
| OpenCode | reasoning + 活动取消 + 刷新/重连 | 同一 reasoning 行 interrupted、session/terminal/archive/cleanup 正确 |
| Claude | reasoning + 正常 Git delivery | receipt 连续、finalization、remote SHA、MR Ready 状态一致 |
| Codex | reasoning + 零变化成功 | started 早于 completed、空正文不伪造详情、不生成空提交或虚假 SHA |

同时验证：

- legacy V1 的 create/execute/schedule/retry/resume 均被拒绝；
- legacy 历史详情仍可读，不允许写操作；
- readiness 不再因旧 TTL 到期自动失效；显式 Verify 和真实启动错误仍可更新状态；
- 四条 Task 的 Snapshot、Bundle、Kit、image 与 RC evidence 完全一致；
- 无残留 Worker、Issue mutex、workspace lock 或未收尾 archive。

### E. 开发环境退出条件

满足以下条件即记录 R4.6 `GO`，停止新增验证 Task：

- exact composition 无漂移，数据库 revision 为 078，运行模式为 `v2_only`；
- 四 Harness release smoke 全部达到预期；
- V1 写路径全部 fail-closed，历史读取正常；
- 无凭据泄漏、错误成功判定、虚假 remote SHA、远端覆盖、重复 terminal/receipt 或无法取消；
- Task #543 已按新 RC 重建，或 release owner 明确决定不再执行；
- 形成一份脱敏的 hard-cut evidence。

## 6. Migration 078 决策

`078_remove_provider_driver` 会：

1. 删除 `provider_kind='openai_compatible'` 且 `model_protocol='anthropic_messages'` 的 Provider；
2. 删除未使用的 `provider_driver` 列；
3. 拒绝 downgrade，只允许从备份恢复或 roll forward。

开发库当前仅 Provider 11 命中删除条件；它有 23 条历史 Task 引用、没有 Issue 默认引用。Provider 删除后，
这些历史 Task 的 `provider_id` 会按外键变为 `NULL`。本轮接受这一内测数据变化：备份后直接执行 migration，
不增加兼容迁移、历史数据搬运或过渡 schema。

## 7. 简化后的发布确认

R4.5 不再要求五类独立 owner、签名发布包、长期 retention 日期或完整回滚演练。开发和线上各由一个明确的
release owner 确认以下五项：

- 数据库备份存在且可读取；
- Provider、GitLab、OAuth 凭据当前有效，权限范围可接受，证据不包含原始 secret；
- Git SHA 与 Backend/NGINX、Worker image、Kit、Bundle、Profile identity 已绑定；
- 维护窗口、执行人和恢复服务的决定明确；
- 失败时保持维护状态并 roll forward；只有 migration/data corruption 才从完整备份恢复。

安全、凭据和备份检查不能省略；不再为内测环境增加 release-signing 基础设施或复杂 rollback state。

## 8. 线上内测环境硬切

开发环境达到退出条件后，线上环境使用完全相同的 Git SHA、Backend/NGINX image、Worker image、Kit 和
Runtime Bundle，不重新构建：

1. 公告停机窗口，暂停创建/调度并排空任务；
2. 备份数据库，执行 migration 078；
3. 切换 `v2_only` 并启动服务；
4. 执行与开发环境相同的四 Harness release smoke；
5. 验证 V1 写拒绝、历史只读和服务健康后开放访问。

线上开放后观察每个 Harness 至少一个真实任务，并累计 5–10 个日常任务。无阻断即关闭 R5；不保留额外
数周 `dual_canary` 观察期。

## 9. 证据失效与停止规则

| 变化 | 处理 |
| --- | --- |
| 仅文档变化 | 不重开技术 evidence |
| 仅前端交互变化 | 重跑受影响前端测试和对应浏览器场景 |
| Runtime Bundle/finalization/delivery/terminal/archive 变化 | 更换 RC identity，补跑受影响 Harness release smoke |
| Adapter、Canonical Event、reasoning 或 command 投影变化 | 更换 RC identity，重验受影响 Harness；不自动重跑 benchmark |
| Harness CLI、Provider protocol/model 或 execution options 变化 | 更换 Kit/Bundle identity，重做受影响协议与真实 Host evidence |
| readiness/Scheduler gate 变化 | 重验 Verify、ready 持续性、unknown/unavailable 和真实启动错误 |

出现以下任一情况立即停止切换并保持维护状态：identity 漂移、mutable artifact、隐式 CLI 回退、跨 Task
session/config 串线、command/terminal/receipt 不变量破坏、凭据泄漏、错误成功判定、远端覆盖、无法取消
或未接受的 P0/P1。失败后修复并生成新 RC，不能用后续成功 Task 稀释失败证据。

## 10. 不进入本轮

- 不新增撤销、denylist、Task 迁移、紧急回退状态或过渡 schema；
- 不升级 Harness CLI，不修改协议适用矩阵，不重跑完整 benchmark；
- 不为 readiness 或 Kit 校验增加数据库字段、周期扫描或双模式；
- 不做移动设备专项验收；
- 不执行广泛 Docker prune，不清理 volume、active/unknown Worker 或不确定归属的 image/archive；
- 不从 dirty worktree 构建或部署，不在开发验证前直接切线上。
