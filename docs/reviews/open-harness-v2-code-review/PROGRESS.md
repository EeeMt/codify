# Open-Harness V2 Code Review —— 进度跟踪

> 更新规则：每个专题审查结束后更新本表（状态、判定计数、一句话结论）。
> 状态取值：`待开始` / `进行中` / `已完成` / `已复核` / `受阻`
> 判定取值与依据见 [README.md](README.md) §1.1（部署画像）与 §3（判定标准）。

## 1. 总进度

| 指标 | 值 |
|---|---|
| 审查基线 | `8081c946^` = `7b253fbf`（2026-08-20） |
| 审查目标 | `dev @ cbad9e56`（2026-09-12） |
| 提交数 / 文件数 / 变更行 | 477 / 437 / +74,905 −3,855 |
| 专题总数 | 17（16 个分派专题 + 1 个 Main 横切专题） |
| 已完成专题 | 17 |
| 原始问题计数 | 170（FIX_NOW 15 / FIX_IF_CHEAP 50 / DEFER 56 / ACCEPT/CLOSE 49） |
| 归并去重后 | 165（FIX_NOW 13 / FIX_IF_CHEAP 48 / DEFER 55 / ACCEPT/CLOSE 49） |
| 汇总文档 | [SUMMARY.md](SUMMARY.md) |

按 §1.1 画像（上线默认 `v2_only`、无 canary、上线后默认 harness 为 Pi），165 条里 **13 条属于「现在就修」**
（其中 10 条在主路径上），**49 条判定为本画像下的过度防御**（书面接受并关闭）。修复顺序见 SUMMARY §7。

## 2. 专题状态

| # | 专题 | 文档 | 负责人 | 状态 | FIX_NOW | FIX_IF_CHEAP | DEFER | ACCEPT/CLOSE | 结论 |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 1 | 01 命令平面与并发门禁 | [01-command-plane.md](01-command-plane.md) | T01 | 已完成 | 1 | 3 | 3 | 6 | 幂等/顺序/唯一终态完整；单 scheduler 画像下租约与跨会话 CAS 属过度防御（6 条接受），仅 CMD-04 列宽会导致 500 须修 |
| 2 | 02 事件契约与投影 | [02-event-contract.md](02-event-contract.md) | T02 | 已完成 | 1 | 3 | 3 | 3 | 投影契约成立；EVT-02（Pi 拒绝事件永久卡流、丢统计投影）必修，单写者属契约文字问题（改文档） |
| 3 | 03 Pi RPC Bridge 与原生事件 | [03-pi-bridge.md](03-pi-bridge.md) | T03 | 已完成 | 3 | 1 | 6 | 5 | 上线后 Pi 为默认 harness ⇒ Pi 通道即主路径：PI-01/PI-02/PI-04 必修（卡流丢统计、配置错误挂超时、skills 静默失效），PI-03 顺手摘掉未接线选项 |
| 4 | 04 OpenCode Task-scoped Server / Bridge 生命周期 | [04-opencode-bridge.md](04-opencode-bridge.md) | T04 | 已完成 | 0 | 2 | 2 | 2 | Server 生命周期/超时层级完整；OCB-01 恢复路由不存在（4~5 行）顺手修 |
| 5 | 05 OpenCode 事件/SSE 映射与 settled 判定 | [05-opencode-events.md](05-opencode-events.md) | T05 | 已完成 | 0 | 4 | 5 | 1 | SSE 映射与 settled 判定细致；4 条错误路径顺手修，其余延后/接受 |
| 6 | 06 Claude / Codex V2 迁移与无回归 | [06-claude-codex.md](06-claude-codex.md) | T06 | 已完成 | 0 | 1 | 5 | 0 | V1→V2 移植忠实（冻结 fixture 等价）；仅 CX-03 顺手修，其余延后（claude 不再是默认 harness） |
| 7 | 07 公共 Runner / Bridge 基础设施与 harness manifest | [07-runner-infra.md](07-runner-infra.md) | T07 | 已完成 | 2 | 0 | 4 | 3 | 终态纪律严格；RUN-01（默认 harness 静默功能回归，claude 与 pi 同样受影响）与 RUN-02（大 payload 丢交付）必修 |
| 8 | 08 Runtime Bundle / Harness Registry / harness_options / Readiness / Kit Inventory | [08-runtime-bundle.md](08-runtime-bundle.md) | T08 | 已完成 | 0 | 2 | 3 | 2 | bundle 冻结/门禁正确；RTB-01 一行修好 catalog 误报，RTB-02 与 PI-03 同根因顺手摘白名单 |
| 9 | 09 Worker Kit 制品、安装与校验 | [09-worker-kit.md](09-worker-kit.md) | T09 | 已完成 | 0 | 5 | 4 | 5 | Kit 校验链结构完整；5 条一行级顺手修，5 条（可复现/供应链）画像接受 |
| 10 | 10 Model Endpoint 重命名、Provider 配置、请求选项出口代理 | [10-model-endpoints.md](10-model-endpoints.md) | T10 | 已完成 | 0 | 2 | 2 | 2 | 重命名与出口代理不变量成立；MEP-01（带空格配置误报篡改）两行修 |
| 11 | 11 Git/MR 交付、Task 生命周期与终态、Scheduler | [11-delivery-lifecycle.md](11-delivery-lifecycle.md) | T11 | 已完成 | 1 | 1 | 5 | 0 | 交付/生命周期核心不变量成立；DEL-01（真实失败原因被覆盖）必修，其余延后 |
| 12 | 12 前端任务执行/交付/交互 UI（除 Provider 面板）—— Code Review | [12-frontend.md](12-frontend.md) | T12 | 已完成 | 0 | 3 | 7 | 0 | 无阻断项；3 条顺手（i18n 缺键 / 拒绝原因丢失 / 命令幂等键），其余延后 |
| 13 | 13 横切安全与凭据 | [13-security.md](13-security.md) | T13 | 已完成 | 1 | 4 | 0 | 4 | 无越权/凭据转发；SEC-02（吊销历史凭据，0 代码）须做，4 条内网画像下接受 |
| 14 | 14 Alembic 迁移与数据模型 | [14-migrations-models.md](14-migrations-models.md) | T14 | 已完成 | 0 | 1 | 2 | 3 | 迁移单头线性、真实 PG 验证过；切库前做 078/079 两条 SQL 核实，「指定 revision 门禁」随 canary 一并接受关闭 |
| 15 | 15 部署编排与离线包 | [15-deploy-ops.md](15-deploy-ops.md) | T15 | 已完成 | 5 | 8 | 1 | 3 | 5 条必修：离线包插值即失败（正解是让 v2_only 成为默认）、mock 栈 dual_canary、e2e 迁移落后、Makefile、文档 canary 叙述；OPS-09 双轨回滚 runbook 接受关闭 |
| 16 | 16 测试质量与覆盖 | [16-tests.md](16-tests.md) | T16 | 已完成 | 1 | 6 | 4 | 7 | 测试以真实脚本/真实 PG 为主；TST-01 必修（mock 栈全崩），7 条覆盖纯度接受 |
| 17 | 17 横切补充与范围外核查 | [17-cross-cutting.md](17-cross-cutting.md) | T17 | 已完成 | 0 | 4 | 0 | 3 | 入口与配置层防呆到位（默认收敛 v2_only）；4 条一行级顺手修，3 条接受 |

## 3. 时间线

| 时间 | 事件 |
|---|---|
| 2026-09-12 | 确定审查范围（`8081c946^..cbad9e56`），建立索引/判定标准/进度跟踪，分派 16 个专题 |
| 2026-09-12 | 16 个专题全部完成；Main 完成横切补充（17）与 15 项独立复核 |
| 2026-09-12 | 归并跨专题重复、汇总问题表、输出修复顺序与接受清单 |
| 2026-09-12 | 明确部署画像并按画像**原地重判**全部 170 条：判定取代严重度分级，多数契约/高可用类要求按过度防御接受 |
| 2026-09-12 | 画像补充：上线默认 `v2_only`（不需显式配置、不做 canary）、上线后默认 harness 为 Pi ⇒ 复检受影响条目（OPS-01/03/07/08 改写动作，OPS-09 与 MIG-INFO-03 改判接受，PI-02/PI-04 升为 FIX_NOW） |
| 2026-09-12 | 全库去重精简：§1 结语压到 ≤3 句/≤450 字，判定理由 ≤50 字，删除泛化「不做」与重复「何时再管」 |

## 4. 遗留事项

- [x] 各专题交叉复核（15 项，见 `SUMMARY.md` §9）
- [x] 汇总 `SUMMARY.md`（全量问题表 + 判定统计 + 修复顺序 + 接受清单）
- [ ] 执行 Tier-1 修复（`SUMMARY.md` §7）：10 条主路径项，一次小 PR
- [ ] 切库前核实 078/079 对历史统计的影响（`SUMMARY.md` §8）
- [ ] 其余条目按 §4~§6 的判定执行或书面关闭
