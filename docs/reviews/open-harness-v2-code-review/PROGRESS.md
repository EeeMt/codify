# Open-Harness V2 Code Review —— 进度跟踪

> 更新规则：每个专题审查结束后更新本表（状态、问题计数、一句话结论）。
> 状态取值：`待开始` / `进行中` / `已完成` / `已复核` / `受阻`

## 1. 总进度

| 指标 | 值 |
|---|---|
| 审查基线 | `8081c946^` = `7b253fbf`（2026-08-20） |
| 审查目标 | `dev @ cbad9e56`（2026-09-12） |
| 提交数 / 文件数 / 变更行 | 477 / 437 / +74,905 −3,855 |
| 专题总数 | 17（16 个分派专题 + 1 个 Main 横切专题） |
| 已完成专题 | 17 |
| 原始问题计数 | 170（P0 0 / P1 12 / P2 41 / P3 48 / INFO 69） |
| 归并去重后 | 165（P0 0 / P1 10 / P2 38 / P3 48 / INFO 69） |
| 汇总文档 | [SUMMARY.md](SUMMARY.md) |

## 2. 专题状态

| # | 专题 | 文档 | 负责人 | 状态 | P0 | P1 | P2 | P3 | INFO | 结论 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---|
| 01 | 命令平面与并发门禁 | [01-command-plane.md](01-command-plane.md) | T01 | 已完成 | 0 | 0 | 4 | 3 | 6 | 命令状态机/门禁/幂等实现完整，但 CAS 实际依赖 CHECK 约束兜底、租约 TTL(120s)≪transport(1890s)、retry 无上限 |
| 02 | 事件契约与投影 | [02-event-contract.md](02-event-contract.md) | T02 | 已完成 | 0 | 1 | 4 | 1 | 4 | V1/V2 分发、seq 连续、唯一终态等不变量成立；但 projector 违反单写者契约，且单条非法审计记录可永久卡死 ingest |
| 03 | Pi Bridge 与事件 | [03-pi-bridge.md](03-pi-bridge.md) | T03 | 已完成 | 0 | 3 | 1 | 4 | 7 | Pi 交互能力覆盖完整；3 个 P1 集中在原生拒绝路径未收敛与冻结 options/skills 未接线 |
| 04 | OpenCode Bridge 生命周期 | [04-opencode-bridge.md](04-opencode-bridge.md) | T04 | 已完成 | 0 | 1 | 1 | 1 | 3 | Server 生命周期/收敛/超时层级完整；P1 为状态兜底查询用了制品中不存在的路由 |
| 05 | OpenCode 事件映射 | [05-opencode-events.md](05-opencode-events.md) | T05 | 已完成 | 0 | 1 | 4 | 1 | 4 | SSE 映射与 settled 判定实现细致；P1 为 abort/error 形状被按成功收敛 |
| 06 | Claude/Codex V2 迁移 | [06-claude-codex.md](06-claude-codex.md) | T06 | 已完成 | 0 | 0 | 1 | 2 | 3 | V1→V2 移植忠实（冻结 fixture 等价性用例通过）；P2 为 Claude 每个 text delta 派生事件进程的开销 |
| 07 | 公共 Runner/Bridge 基础设施 | [07-runner-infra.md](07-runner-infra.md) | T07 | 已完成 | 0 | 2 | 0 | 2 | 5 | 唯一终态与控制通道纪律经实测严格（8 条拒绝路径生效）；P1 为 manifest capability 词表收窄与 argv 负载上限 |
| 08 | Runtime Bundle/Registry/Options/Readiness | [08-runtime-bundle.md](08-runtime-bundle.md) | T08 | 已完成 | 0 | 1 | 1 | 2 | 3 | bundle digest/allowlist/硬切门禁正确；P1 为 readiness 作用域写入与读取判定不一致导致门禁不生效 |
| 09 | Worker Kit 制品与校验 | [09-worker-kit.md](09-worker-kit.md) | T09 | 已完成 | 0 | 0 | 2 | 6 | 6 | Kit 校验链结构完整（归档绑定摘要、双次清单校验、无路径逃逸）；P2 为 bridge 自检被吞与两个安装器漂移 |
| 10 | Model Endpoint/Provider/请求选项代理 | [10-model-endpoints.md](10-model-endpoints.md) | T10 | 已完成 | 0 | 0 | 2 | 2 | 2 | 重命名无残留、出口代理不变量（头部/流式/取消/监听）逐项通过；P2 为归一化不一致与创建期保留字段校验缺失 |
| 11 | Git 交付与任务生命周期/Scheduler | [11-delivery-lifecycle.md](11-delivery-lifecycle.md) | T11 | 已完成 | 0 | 0 | 1 | 4 | 2 | 交付/生命周期/Scheduler 核心不变量成立，无 P0/P1；P2 为终态失败原因被归档 provider 错误覆盖 |
| 12 | 前端任务执行与交付 UI | [12-frontend.md](12-frontend.md) | T12 | 已完成 | 0 | 0 | 3 | 3 | 4 | 前端质量高、无 P0/P1、无 V2 新引入 XSS；P2 为 i18n 缺键、拒绝原因丢失、命令幂等键每次重生成 |
| 13 | 安全与凭据（横切） | [13-security.md](13-security.md) | T13 | 已完成 | 0 | 0 | 2 | 4 | 3 | 未见越权或凭据转发；P2 为清洗规则覆盖缺口（自定义 key 形态、JSON apiKey）与历史凭据未吊销 |
| 14 | 迁移与数据模型 | [14-migrations-models.md](14-migrations-models.md) | T14 | 已完成 | 0 | 0 | 0 | 2 | 4 | 迁移单头线性、真实 PG 上全链通过且重复执行幂等、约束索引均生效；仅 2 项 server_default 漂移 P3 |
| 15 | 部署与离线包 | [15-deploy-ops.md](15-deploy-ops.md) | T15 | 已完成 | 0 | 2 | 8 | 1 | 6 | 编排/离线包核心正确（单一迁移 owner、V1 只读、preflight fail-closed）；2 个 P1 为文档化主入口不可用与历史凭据 |
| 16 | 测试质量与覆盖 | [16-tests.md](16-tests.md) | T16 | 已完成 | 0 | 1 | 7 | 5 | 5 | 测试以真实脚本/真实 PG/真实子进程为主，未发现删除后未补偿；P1 为 mock 栈配置非法，另有 7 处覆盖假象 |
| 17 | 横切补充（入口/配置/脚本/卫生） | [17-cross-cutting.md](17-cross-cutting.md) | Main | 已完成 | 0 | 0 | 0 | 5 | 2 | 入口与配置层防呆到位（显式执行模式、命令入口 32KiB 预检）；1 个降级 P3 与 4 处一致性/卫生问题 |

## 3. 时间线

| 时间 | 事件 |
|---|---|
| 2026-09-12 | 确定审查范围（`8081c946^..cbad9e56`），建立索引/分级标准/进度跟踪，分派 16 个专题 |
| 2026-09-12 | 16 个专题全部完成；Main 完成横切补充（17）与 15 项独立复核 |
| 2026-09-12 | 归并跨专题重复、汇总分级问题表、输出 `SUMMARY.md` 与修复批次建议 |

## 4. 遗留事项

- [x] 各专题 P0/P1 交叉复核（15 项，见 `SUMMARY.md §9`）；其中 2 条按复核结论调整等级
- [x] 汇总 `SUMMARY.md`（全量问题表 + 分级统计 + 修复优先级建议）
- [ ] 修复批次 A（发布前收口）—— 由研发按 `SUMMARY.md §8` 执行
