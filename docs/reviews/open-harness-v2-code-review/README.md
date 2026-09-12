# Open-Harness V2 Code Review —— 索引与审查契约

> 审查日期：2026-09-12
> 审查范围提交：`dev @ cbad9e56`（工作区状态与该提交一致，未提交改动不参与本次审查）
> 基线提交（不含 v2 工作）：`8081c946^` = `7b253fbf`（2026-08-20）
> 审查 diff 规模：477 个提交，437 个文件，`+74,905 / -3,855`
> 审查方式：按模块/专题切分（17 个专题），逐专题静态审查 + 契约对照 + 窄范围实测，只读不改代码
>
> **结果：165 条唯一问题（FIX_NOW 13 / FIX_IF_CHEAP 48 / DEFER 55 / ACCEPT/CLOSE 49）。**
> 判定标准与部署画像见 §1.1 与 §3；汇总、修复顺序与接受清单见 [SUMMARY.md](SUMMARY.md)，
> 进度与各专题计数见 [PROGRESS.md](PROGRESS.md)。

## 1. 范围定义

“从 open harness v2 开始”在本仓库中对应 `8081c946 docs(harness): define open-harness v2 rollout`
（2026-08-21，首个 V2 架构方案提交）。因此本次审查覆盖：

```bash
git diff 8081c946^..cbad9e56         # 全部 v2 相关工作
```

即 2026-08-21 之后落在 `dev` 上的全部 V2 架构、实现、迁移、前端、部署与文档改动。基线之前
已存在的历史代码不在审查范围，除非它是 V2 改动的直接上下文（例如被 V2 改写的旧模块）。
各专题证据里带 `..HEAD` 的 `git diff`/`git show` 命令，其 `HEAD` 均指 `cbad9e56`（该区间之后
只新增本目录文档，不影响任何被引用的源文件）。

`output/playwright/*.png`、`.vite/vitest/results.json` 等构建/验收产物属于噪声，只做“是否应入库”
的合规性判断，不做内容审查。

### 1.1 部署画像（判定前提）

所有判定都基于下面这个**唯一权威**的运行画像；画像变化时判定必须重做：

| 维度 | 现状 | 对判定的影响 |
|---|---|---|
| 使用范围 | 内部系统，生产在**离线内网**，无外部用户 | 无恶意租户模型；凭据泄露面 ≈ 已有仓库/网络权限的人 |
| 阶段 | 内测，约 **3 人**；目标是支撑**数十人** | 并发/多写者/大规模场景当前不可达 |
| 上线形态 | 执行模式**默认即 `v2_only`**：不需要显式配置该环境变量，**不做 canary**（canary 与 V1 双轨回滚属过度设计，回滚=重新部署上一版镜像/Kit） | 「hard cut 门禁/显式配置/canary/指定 revision 迁移」类要求不作缺陷 |
| 默认 harness | 上线后的默认 harness 是 **Pi**（claude/codex/opencode 仍可选但不是主路径） | Pi 通道的问题即主路径问题；claude 通道的等价问题按同一标准处理 |
| 可用性 | **无 SLA**：可停机、可硬切（`v2_only`）、可强制关闭 issue/task、可手工重跑迁移 | 「高可用不变量」（租约续期、在线迁移互斥、双轨回滚）不是缺陷 |
| 唯一硬约束 | **历史数据不丢**，主要指统计/分析页所依赖的数据 | 任何会丢统计口径、丢终态投影的问题优先修 |
| 工程取向 | 明确避免**过度设计与过度防御** | 契约纯度、字节级可复现、覆盖纯度的要求一律降级 |

关键推论：生产只有**一个** `codify-scheduler` 容器，执行模式默认 `v2_only` 且无 canary，上线后默认 harness 是
Pi——「多 dispatcher 竞争」「跨会话 CAS」「租约 TTL vs 在途窗口」「显式硬切门禁/双轨回滚」在本画像下不可达。

## 2. 目录结构

| 文档 | 专题 | 主要负责人 |
|---|---|---|
| [README.md](README.md) | 索引、范围、部署画像、判定标准、审查契约 | 汇总 |
| [PROGRESS.md](PROGRESS.md) | 进度跟踪（每个专题的状态/结论/判定计数） | 汇总 |
| [SUMMARY.md](SUMMARY.md) | 全量问题汇总表 + 判定统计 + 修复顺序 + 接受清单 | 汇总 |
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

## 3. 判定标准（所有文档必须使用）

每条问题只给一个**判定**，取值为下列四档之一。判定回答的是「按 §1.1 画像，这条现在做不做」，
而不是「它在抽象意义上多严重」。

| 判定 | 定义 | 处理要求 |
|---|---|---|
| **FIX_NOW** | 破坏主路径；静默丢交付或对交付结果说谎；任务永久卡死/挂到超时；文档化的部署主路径不可用 | 下次真实使用前必须修 |
| **FIX_IF_CHEAP** | 真实缺陷，但只在错误路径/边界上触发；修复 ≤ ~6 行且不引入新机制 | 顺手修；否则跟 FIX_NOW 一起排期 |
| **DEFER** | 真实但本画像可容忍（可停机、可重跑、可手工介入） | 记录在案，出现「何时再管」里的触发条件再修 |
| **ACCEPT/CLOSE** | **本画像下属于过度防御**：它要求的不变量（严格 CAS、租约续保、单写者、字节级可复现、全链覆盖、无 SLA 下的高可用机制）在此不需要 | 书面接受并关闭；在条目里写明触发条件，触发即重开 |

判定纪律：

1. **证据 + 最小动作**：位置给 `文件:行号`（必要时加提交 hash）；无法给出证据的怀疑只能记
   `ACCEPT/CLOSE` 或 `DEFER`。`- **最小动作**：` 只写最省力的可行改动，不得顺手加机制、开关、
   抽象层或测试矩阵；原建议确实有害时才写 `- **不做**：` 并说明害处。
2. **写作长度上限**：§1 结论摘要 ≤3 句 / ≤450 字；`- **判定**：` 的理由 ≤50 字，且不得复述
   同一条目的 `影响`/`证据`；`- **何时再管**：` 只写该条目独有的触发条件。
3. **判定可升可降**：任一条目都可从 DEFER 变 FIX_NOW（或反之），只要写明画像依据与触发条件。

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
| 判定 | 数量 |
|---|---|
| FIX_NOW | n |
| FIX_IF_CHEAP | n |
| DEFER | n |
| ACCEPT/CLOSE | n |

一段话总结本模块质量结论（按画像说明「现在修什么、接受什么」）。
**本专题触发条件**：<ACCEPT/DEFER 条目共同的「何时再管」（可选）>

## 2. 问题清单
### CMD-01 <一句话标题>
- **判定**：FIX_NOW / FIX_IF_CHEAP / DEFER / ACCEPT/CLOSE —— <一句话画像依据>
- **何时再管**：<仅 ACCEPT/CLOSE/DEFER 需要>
- **位置**：`backend/app/core/xxx.py:123`（提交 `abcdef1`）
- **证据**：<代码/契约/测试原文，或可复现步骤>
- **影响**：<具体后果，谁在什么条件下受影响>
- **最小动作**：<最省力的改动；不引入新机制>
- **不做**：<原建议中过重的部分（可选）>
- **验证**：<如何验证修复；本次是否实际验证>

（按 FIX_NOW → FIX_IF_CHEAP → DEFER → ACCEPT/CLOSE 排序；INFO 条目同样用 `### <前缀>-INFO-nn` 编号）

## 3. 逐项核查记录（已确认无问题的关键不变量）
| # | 不变量/契约 | 结论 | 依据 |
|---|---|---|---|
| 1 | 同一 command_id 重投不产生两条用户消息 | 通过 | `xxx.py:88-140` CAS ... |

## 4. 局限与未验证项
- <没有真实环境/没有运行测试/没有上游 CLI 可复现 等>
```

## 5. 审查纪律

1. **只读**：不得修改任何源码、测试、迁移、文档（除自己负责的那一个专题文档）。
2. **不得运行全量测试套件**；窄范围、无外部依赖的单测可运行并注明命令与结果。需要 DB/网络/Docker/
   真实 CLI 的场景用静态推理并标注「未运行验证」。
3. **看当前代码而非只看 diff**：结论基于 `dev @ cbad9e56` 的完整文件（含调用方），并核查被改动函数的
   其他调用点（`grep`/LSP），避免把已修复问题当成现存问题。
4. **区分「V1 遗留」与「V2 引入」**：V1 既有问题只有被 V2 放大或依赖时才报告，并标注 `[V1 遗留]`。
