# Open-Harness V2 Code Review —— 索引与审查契约

> 审查日期：2026-09-12
> 审查范围提交：`dev @ cbad9e56`（工作区状态与该提交一致，未提交改动不参与本次审查）
> 基线提交（不含 v2 工作）：`8081c946^` = `7b253fbf`（2026-08-20）
> 审查 diff 规模：477 个提交，437 个文件，`+74,905 / -3,855`
> 审查方式：按模块/专题切分（17 个专题），逐专题静态审查 + 契约对照 + 窄范围实测，只读不改代码
>
> **结果：165 条唯一问题（P0 0 / P1 10 / P2 38 / P3 48 / INFO 69）。**
> 汇总、分级总表与修复批次建议见 [SUMMARY.md](SUMMARY.md)；进度与各专题计数见 [PROGRESS.md](PROGRESS.md)。

## 1. 范围定义

“从 open harness v2 开始”在本仓库中对应 `8081c946 docs(harness): define open-harness v2 rollout`
（2026-08-21，首个 V2 架构方案提交）。因此本次审查覆盖：

```bash
git diff 8081c946^..HEAD            # 全部 v2 相关工作
```

即 2026-08-21 之后落在 `dev` 上的全部 V2 架构、实现、迁移、前端、部署与文档改动。基线之前
已存在的历史代码不在审查范围，除非它是 V2 改动的直接上下文（例如被 V2 改写的旧模块）。

`output/playwright/*.png`、`.vite/vitest/results.json` 等构建/验收产物属于噪声，只做“是否应入库”
的合规性判断，不做内容审查。

## 2. 目录结构

| 文档 | 专题 | 主要负责人 |
|---|---|---|
| [README.md](README.md) | 索引、范围、分级标准、审查契约 | 汇总 |
| [PROGRESS.md](PROGRESS.md) | 进度跟踪（每个专题的状态/结论/问题计数） | 汇总 |
| [SUMMARY.md](SUMMARY.md) | 全量问题汇总表 + 分级统计 + 优先级建议 | 汇总 |
| [01-command-plane.md](01-command-plane.md) | 命令平面：持久化命令队列、投递泵、并发门禁、Command API、Scheduler 集成 | T01 |
| [02-event-contract.md](02-event-contract.md) | 事件契约与投影：`harness_protocol`、projector、result v2、failure 分类、日志流 | T02 |
| [03-pi-bridge.md](03-pi-bridge.md) | Pi RPC Bridge、owner 进程管理、原生事件映射 | T03 |
| [04-opencode-bridge.md](04-opencode-bridge.md) | OpenCode Task-scoped Server 生命周期、Bridge、Runner | T04 |
| [05-opencode-events.md](05-opencode-events.md) | OpenCode 事件/SSE 映射与 settled 判定 | T05 |
| [06-claude-codex.md](06-claude-codex.md) | Claude/Codex V2 迁移（adapter + events + runner） | T06 |
| [07-runner-infra.md](07-runner-infra.md) | 公共 Runner/Bridge 基础设施：runner.sh、common.sh、bridge.py、control_client、manifest | T07 |
| [08-runtime-bundle.md](08-runtime-bundle.md) | Runtime Bundle、Harness Registry、harness_options、readiness、kit inventory | T08 |
| [09-worker-kit.md](09-worker-kit.md) | Worker Kit 制品、manifest 校验、安装/导出、CLI 摘要验证 | T09 |
| [10-model-endpoints.md](10-model-endpoints.md) | Model Endpoint 重命名、Provider 配置、请求选项出口代理（含 Go proxy、前端 Provider 面板） | T10 |
| [11-delivery-lifecycle.md](11-delivery-lifecycle.md) | Git/MR 交付、Task 生命周期与终态、Scheduler、timeout、容器清理 | T11 |
| [12-frontend.md](12-frontend.md) | 前端任务执行/交付/交互 UI（除 Provider 面板） | T12 |
| [13-security.md](13-security.md) | 横切安全：凭据、日志清洗、秘密轮换、鉴权、制品完整性 | T13 |
| [14-migrations-models.md](14-migrations-models.md) | Alembic 迁移与数据模型变更 | T14 |
| [15-deploy-ops.md](15-deploy-ops.md) | 部署编排、离线包、preflight、环境变量契约 | T15 |
| [16-tests.md](16-tests.md) | 测试质量与覆盖（后端单测/mock 集成 + 前端 spec） | T16 |
| [17-cross-cutting.md](17-cross-cutting.md) | 横切补充：进程入口、全局配置、探针脚本、仓库卫生、文档漂移 | Main |

## 3. 分级标准（所有文档必须使用）

| 等级 | 定义 | 处理要求 |
|---|---|---|
| **P0 阻断** | 数据丢失/损坏；安全漏洞或越权；凭据泄露；破坏性迁移不可恢复；唯一终态/幂等等核心不变量被破坏导致错误交付；hard cut 门禁失效 | 必须修复后才可发布 |
| **P1 高** | 主路径功能缺陷；契约/不变量违反（幂等、唯一终态、顺序、CAS、gate 状态机）；并发竞态导致错误终态或永久挂起；资源/进程/连接泄漏；交付结果与事实不符；错误分类错误导致错误重试 | 发布前必须处理或给出明确接受理由 |
| **P2 中** | 错误路径不健壮；边界/超时/取消处理不完整；可观测性缺失；性能退化；重复实现或隐式耦合带来的可维护性风险；测试与实现脱节 | 排期修复 |
| **P3 低** | 命名/风格/注释/文档不一致；死代码；轻微 UX；日志措辞 | 顺手修 |
| **INFO** | 观察、建议、需要人工确认的疑点（未验证到缺陷） | 仅记录 |

判定必须给出**证据**：`文件:行号`（必要时加提交 hash）。无法给出证据的怀疑一律记为 INFO，不得记为 P1/P2。

## 4. 每个专题文档的固定结构

```markdown
# <编号> <专题名> —— Code Review

## 0. 范围
| 项 | 值 |
| 提交区间 | 8081c946^..cbad9e56 |
| 文件 | <列表，含 +/- 行数> |
| 审查方法 | 静态阅读 + 契约对照 + <其他> |
| 未覆盖 | <明确写出没看的部分> |

## 1. 结论摘要
| 等级 | 数量 |
|---|---|
| P0 | n |
| P1 | n |
| P2 | n |
| P3 | n |
| INFO | n |

一段话总结本模块质量结论。

## 2. 问题清单
### CMD-01 <一句话标题>
- **等级**：P1
- **位置**：`backend/app/core/xxx.py:123`（提交 `abcdef1`）
- **证据**：<代码/契约/测试原文，或可复现步骤>
- **影响**：<具体后果，谁在什么条件下受影响>
- **建议**：<最小可行修复方向>
- **验证**：<如何验证修复；本次是否实际验证>

（按 P0 → INFO 排序）

## 3. 逐项核查记录（已确认无问题的关键不变量）
| # | 不变量/契约 | 结论 | 依据 |
|---|---|---|---|
| 1 | 同一 command_id 重投不产生两条用户消息 | 通过 | `xxx.py:88-140` CAS ... |

## 4. 局限与未验证项
- <没有真实环境/没有运行测试/没有上游 CLI 可复现 等>
```

## 5. 审查纪律

1. **只读**：不得修改任何源码、测试、迁移、文档（除自己负责的那一个专题文档）。
2. **不得运行全量测试套件**；可运行窄范围、无外部依赖的单测来支撑结论，并注明命令与结果。
   需要 DB/网络/Docker/真实 CLI 的场景，用静态推理并标注为“未运行验证”。
3. **必须看当前代码而非只看 diff**：`git diff` 用来定位改动，结论必须基于 `dev @ cbad9e56` 的完整文件
   （含调用方），避免把已修复问题当成现存问题。
4. **必须做跨模块调用方核查**：被改动函数的其他调用点（`grep`/LSP）要确认是否同步更新。
5. **区分“V1 遗留”和“V2 引入”**：V2 改动导致的问题正常报告；V1 既有问题只有在 V2 放大/依赖它时
   才报告，并标注 `[V1 遗留]`。
6. 报告要可执行：明确最小修复方向，不要只写“建议优化”。
