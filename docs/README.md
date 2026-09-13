# Documentation Index

文档按受众分四层。新增文档必须落在其中一层，不要平铺在 `docs/` 根目录。

| 层 | 受众 | 位置 |
|----|------|------|
| 指南 | 使用 Codify 的人（含管理员） | 应用内 `/guide` 页，源文件 `frontend/src/guide/` |
| 运维 | 部署与维护 Codify 的人 | [`ops/`](ops/) |
| 开发 | 参与开发与测试的人 | [`dev/`](dev/) |
| 设计档案 | 需要追溯决策过程的人 | [`design/`](design/) |

## 指南

产品指南是应用内页面，不在本目录：章节 markdown 位于 `frontend/src/guide/{zh-CN,en}/`，由前端构建内联进 SPA，访问 `/guide` 查看。改内容只改那些 markdown 文件。

不要在本目录再维护一份用户指南副本——两处内容必然漂移。

Covers: quick start, creating an issue, core concepts, creating tasks, running and steering, delivery, scheduling and capacity, observability, admin configuration, access and usage governance, troubleshooting.

## 运维

- [配置参考](ops/CONFIGURATION.md) — 部署期环境变量、运行时覆盖、常用命令、运维备忘
- [生产部署指南](ops/DEPLOYMENT.md) — 部署目标、更新、备份、排障、升级回滚
- [GitLab OIDC 登录配置](ops/GITLAB_OIDC_SETUP.md)
- [内网离线迁移实施方案](ops/OFFLINE-DEV.md) — 无公网环境的开发/构建/测试/部署
- [日志追踪方案](ops/LOGGING.md) — 前后端 Trace ID 全链路日志定位

### Runbooks

- [Multi-Harness 切换与生产验收 Runbook](ops/runbooks/multi-harness-rollout.md)
- [Multi-Harness 验收证据模板](ops/runbooks/multi-harness-rollout-evidence.md)

## 开发

- [开发环境搭建指南](dev/DEVELOPMENT.md)
- [测试指南](dev/TESTING.md) — 所有测试类型的运行总览
- [E2E 测试指南](dev/E2E_TESTS.md) — Playwright 编写/运行/调试 + GitLab 集成验证
- [开发环境核心功能回归计划](dev/dev-env-core-regression.md) — 分层（冒烟/完整/发版演练）核心链路回归
- [开发环境 API 回归验证手册](dev/dev-env-api-regression.md) — Phase 1 L4 API 级验证步骤与已知问题
- [Multi-Harness 接入调试与通用经验](dev/multi-harness-debugging.md) — 通用接入断层清单（含 codex 专项）与验证命令
- [Mounted Worker Kits](dev/worker-kits.md) — worker 交付模式（Kit 挂载 vs 烘焙镜像）
- [Worker Volume Mounts](dev/worker-volume-mounts.md) — 独立运行时镜像的卷挂载梳理
- [Harness 探针证据](dev/harness-probes/v2/README.md) — 固定版本协议探针与 canonical 事件样本

## 设计档案

历史决策档案。这里的文档记录"当时为什么这么做"，不代表当前实现，改动实现时不要同步修改它们。

### 架构与合同

- [Worker Harness Adapter 契约 v1](design/architecture/worker-harness-contract-v1.md)
- [Worker Canonical Event v1](design/architecture/worker-canonical-event-v1.md)
- [Open-Harness V2 — 冻结 Schema 与合同](design/architecture/open-harness-v2-schemas.md)
- [Open-Harness V2 — Phase 1 接口骨架](design/architecture/open-harness-v2-phase1-design.md)
- [Open-Harness V2 — Phase 3 OpenCode 一级 Harness](design/architecture/open-harness-v2-phase3-opencode-design.md)
- [Live Steering 事件流投影](design/architecture/live-steering-event-stream-projection.md)
- [模型请求选项出口代理](design/architecture/model-request-options-egress-proxy.md)

### 实施计划与设计文档

- [plans/](design/plans/) — 带日期的实施计划
- [specs/](design/specs/) — 设计文档，例如 [Issue Task 有序回合](design/specs/2026-08-08-issue-task-ordered-turns-design.md)、[Task Freeform 模式](design/specs/2026-08-14-task-freeform-mode-design.md)、[Worker Profile 共享配置](design/specs/2026-08-14-worker-profile-shared-configuration-design.md)
- [evidence/](design/evidence/) — 发布候选与验收证据

### 评审与安全

- [评审档案](design/reviews/) — 含 [Open-Harness V2 代码评审](design/reviews/open-harness-v2-code-review/README.md) 与 [Multi-Harness 架构评审纪要](design/reviews/multi-harness-architecture.md)
- [模型凭据交付方式：受限 legacy 风险接受](design/security/credential-delivery-risk-acceptance.md)
