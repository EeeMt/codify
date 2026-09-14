# 文档索引

文档按受众分四层。新增文档必须落在其中一层，不要平铺在 `docs/` 根目录。

| 层 | 受众 | 位置 |
|----|------|------|
| 指南 | 使用 Codify 的人（含管理员） | 应用内 `/guide` 页，源文件 [`../frontend/src/guide/`](../frontend/src/guide/) |
| 运维 | 部署与维护 Codify 的人 | [`ops/`](ops/) |
| 开发 | 参与开发与测试的人 | [`dev/`](dev/) |
| 设计档案 | 需要追溯决策过程的人 | [`design/`](design/) |

英文索引见 [README.md](README.md)。

## 指南

产品使用说明是应用内页面，不在本目录：

- 中文源文件：[`frontend/src/guide/zh-CN/`](../frontend/src/guide/zh-CN/)
- 英文源文件：[`frontend/src/guide/en/`](../frontend/src/guide/en/)
- 阅读入口：应用内 `/guide`

这些 markdown 由前端构建内联进 SPA，改内容只改那些文件。不要在本目录再维护一份用户指南副本——两处内容必然漂移。

覆盖范围：快速开始、创建需求、核心概念、创建任务、运行与引导、交付、调度、Harness 支持、可观测性、交付内部、使用技巧、系统配置、治理与运维、故障排查、Worker 运行时。

## 运维

- [配置参考](ops/CONFIGURATION.md) — 部署期环境变量、运行时覆盖、常用命令、运维备忘
- [生产部署指南](ops/DEPLOYMENT.md) — 部署目标、更新、备份、排障、升级回滚
- [GitLab OIDC 登录配置](ops/GITLAB_OIDC_SETUP.md)
- [内网离线迁移实施方案](ops/OFFLINE-DEV.md) — 无公网环境的开发/构建/测试/部署
- [日志追踪方案](ops/LOGGING.md) — 前后端 Trace ID 全链路日志定位
- Runbook：[Multi-Harness 切换与生产验收](ops/runbooks/multi-harness-rollout.md)
- [Multi-Harness 验收证据模板](ops/runbooks/multi-harness-rollout-evidence.md)
- [Worker CLI 制品清单](ops/runbooks/worker-cli-artifact-candidate-2026-08-23.md)（已退役：镜像自带 CLI 时代的只读盘点，保留作审计参考）

## 开发

- [开发环境搭建指南](dev/DEVELOPMENT.md)
- [测试指南](dev/TESTING.md) — 所有测试类型的运行总览
- [E2E 测试指南](dev/E2E_TESTS.md) — Playwright 编写/运行/调试 + GitLab 集成验证
- [开发环境核心功能回归计划](dev/dev-env-core-regression.md)
- [开发环境 API 回归验证手册](dev/dev-env-api-regression.md)
- [Multi-Harness 接入调试与通用经验](dev/multi-harness-debugging.md)
- [Mounted Worker Kits](dev/worker-kits.md) · [Worker Volume Mounts](dev/worker-volume-mounts.md)
- [Harness 探针证据](dev/harness-probes/v2/README.md)：分册 [Pi](dev/harness-probes/v2/pi/README.md)、[OpenCode](dev/harness-probes/v2/opencode/README.md)、[Claude/Codex 回放](dev/harness-probes/v2/claude/README.md)、[Subagent](dev/harness-probes/v2/subagents/README.md)

## 设计档案

历史决策档案。这里的文档记录"当时为什么这么做"，不代表当前实现，改动实现时不要同步修改它们。

### 架构与合同

- [Worker Harness Adapter 契约 v1](design/architecture/worker-harness-contract-v1.md)
- [Worker Canonical Event v1](design/architecture/worker-canonical-event-v1.md)
- [Open-Harness V2 冻结 Schema 与合同](design/architecture/open-harness-v2-schemas.md)
- [Open-Harness V2 Phase 1 接口骨架](design/architecture/open-harness-v2-phase1-design.md)
- [Open-Harness V2 Phase 3 OpenCode 一级 Harness](design/architecture/open-harness-v2-phase3-opencode-design.md)
- [Live Steering 事件流投影](design/architecture/live-steering-event-stream-projection.md)
- [模型请求选项出口代理](design/architecture/model-request-options-egress-proxy.md)
- [Open-Harness V2 架构方案](design/architecture/open-harness-v2.md)
- [Open-Harness V2 四 Harness Subagent 适配方案](design/architecture/open-harness-v2-subagent-adaptation.md)

### 实施计划与设计文档

- [plans/](design/plans/)，带日期的实施计划
- [specs/](design/specs/)，设计文档，例如 [Issue Task 有序回合](design/specs/2026-08-08-issue-task-ordered-turns-design.md)、[Task Freeform 模式](design/specs/2026-08-14-task-freeform-mode-design.md)、[Worker Profile 共享配置](design/specs/2026-08-14-worker-profile-shared-configuration-design.md)
- [evidence/](design/evidence/)，发布候选与验收证据

### 评审与安全

- [评审档案](design/reviews/)，含 [Open-Harness V2 代码评审](design/reviews/open-harness-v2-code-review/README.md) 与 [Multi-Harness 架构评审纪要](design/reviews/multi-harness-architecture.md)
- [模型凭据交付方式：受限 legacy 风险接受](design/security/credential-delivery-risk-acceptance.md)
