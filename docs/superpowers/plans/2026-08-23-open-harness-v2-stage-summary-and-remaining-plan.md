# Open-Harness V2 当前状态与剩余验收计划

**复核日期：** 2026-09-08

> 本文件只维护当前结论、证据边界、唯一下一工作包、退出条件和停止规则。
> Task/Issue 编号、逐次 Host 快照、digest、generation 和测试明细只保留在独立 evidence、
> runtime archive、数据库与 Git history 中，不再向本文件追加 `continuation` 流水帐。

## 1. 当前结论

**当前执行门禁：`NO-GO`（尚未形成 R4.6 正式签署）。** 系统继续保持 `dual_canary`；不得执行 migration 078、
切换 `v2_only` 或进入 R5。暂停重复只读 smoke，先冻结与当前源码一致的新 release candidate。

| 工作包 | 状态 | 当前结论 |
| --- | --- | --- |
| R1：Internal Preview candidate | **完成** | 四 Harness 的 `linux/amd64` Image、Kit、Profile、Bundle 与真实 Host identity 已有可追溯历史证据 |
| R2：四 Harness hard-cut conformance | **完成，受影响场景重开** | 历史 8 个适用 Harness×protocol 行及 lifecycle/command/recovery 已闭合；`c089b67a`、`7fd0939c` 及 `5d2fad8e` 修改 reasoning lifecycle、共享 delivery 隔离边界和 Codex App Server transport，仍须在同一 candidate 上重验受影响组合 |
| R3：正式 20-scenario benchmark | **完成** | Pi/OpenCode 20/20 formal pair 与 Pi 非劣性门槛已通过；当前变化未升级 CLI 或修改 model endpoint protocol，但切换了 Codex control transport，故不整体重跑 benchmark、改由 R2/R4 重验 Codex；真实验收若发现 terminal、质量或性能回归再按影响重开 |
| R4.1：可信 Kit 启动边界 | **完成** | content-addressed 安装、管理员完整 Verify、Task 热路径轻量校验与 warm-start 已有 L2–L4 证据 |
| R4.2：冻结 exact candidate | **已形成，未签署** | 当前调试 composition 为 source `5d2fad8e`、Profile 4、Backend/Scheduler/NGINX、任务绑定 Bundle 198–200 与 Worker Kit 0.6.15；已完成管理员 Verify 和多条真实 Task，但镜像没有 OCI source revision label，且尚未推送，故仍不是已签署 candidate |
| R4.3：正式交互验收 | **部分 evidence，未签署** | #464–#474 已有当前 Bundle 的真实 Task/Canonical 证据，其中 Pi/OpenCode/Claude 有 reasoning start/end；#472/#474 已补齐 Pi/Claude 运行中页面“正在思考”先于同一行完成的时序，#473 仅补充 OpenCode 终态页面；仍缺 Codex 成功行、可用 Chat/Responses 行、OpenCode 的运行中页面和四 Harness 全覆盖；用户暂缓的真实移动设备验收不作为本轮技术执行项 |
| R4.4：运维与真实 Task 验收 | **部分 evidence，未签署** | #468/#469/#471 已完成 Pi/OpenCode/Claude delivery 并有 canonical remote SHA；Codex #461–#463 仍在 Provider 响应前失败，Pi Chat #470 为真实 404，Claude 受控远端 divergence 和其他协议行仍未闭合 |
| R4.5：安全与发布审计 | **阻塞于 owner 输入** | 最小权限、轮换、migration 078、签名发布包、retention、维护窗口与独立 P0/P1 审阅尚未签署 |
| R4.6：hard-cut go/no-go | **未执行** | R4.2–R4.5 全部闭合后才能形成独立 `GO` 或 `NO-GO` |
| R5：L6 `v2_only` hard cut | **未执行** | 仅在 R4.6 `GO` 且获得单独执行批准后进入维护窗口 |

完成 R1–R3 证明 V2 的合同、四 Harness 适用矩阵和 formal benchmark 已成立；它们不能替代
当前源码的 release candidate、owner 签署或 hard cut。generation 数量、重复 Task 数量和文档提交数
都不是推进指标；只有上表状态变化才算推进。

## 2. 当前源码与部署边界

### 2.1 当前源码

| 项 | 当前值 |
| --- | --- |
| Git revision | `5d2fad8e7f81e947097d092e1b502f2eae31607c` |
| 分支状态 | `dev` 已提交 Codex App Server Bridge，尚未推送；关联文档、证据和既有 security audit 仍按独立路径处理 |
| 影响面 | Worker Git finalization credential isolation、Codex App Server stdio Bridge、Codex Adapter/manifest/runtime digest、Backend protocol matrix 与既有 Canonical reasoning 投影 |
| 设计基线 | [Task Git delivery reconciliation design](../specs/2026-09-04-task-git-delivery-reconciliation-design.md)；[four-Harness thinking lifecycle plan](2026-09-04-thinking-event-placeholder-plan.md) |
| 当前聚焦 L2 | 本轮 `test_worker_git_delivery.py` 为 36 passed，相关 shell `bash -n` 与 `git diff --check` 通过；既有 frontend production build 已通过 |

本次提交不升级 Harness CLI、不修改 Provider 协议、Scheduler 排队规则或既有 Task Snapshot schema；
但它把 Codex 主任务路径从 `cli_jsonl/codex-jsonl` 切换为单一 `rpc_stdio/codex-app-server-v2`
Bridge，并更新 Adapter、manifest、Bundle digest、协议矩阵和测试。因此必须在同一 exact
composition 上重验 Codex reasoning、session、usage、最终结果和共享 Git delivery；局部测试和
直接 Adapter fixture 不等于 L3/L4/L5 evidence。

### 2.2 远端开发 candidate

本轮在开发 Host 形成了新的 Codex 调试 composition：Profile 4 为
`v2-canary-0.6.11-four-harness`，Backend image 为
`sha256:7673b0b07afcaeb4f7c250bd531f23da825a765d43706c41007069b1931d875a`，NGINX image 为
`sha256:ba50f6296e92e426dd445740d7214c6c54aaddd2a79d58d1513a4741379c6e43`，Runtime Bundle 为
`198–200`（Codex 失败探针使用 `197`），Worker Kit 为 `0.6.15`、manifest SHA 为
`506dbc2c61fbc03144c45fdffcd9a0e264781fe4038ad0ed13b38112580b831b`；Profile Verify 和真实
Codex Task 结果详见 [Codex App Server bridge evidence](../evidence/2026-09-08-open-harness-v2-codex-app-server-bridge.md)。

远端 Backend、Scheduler、NGINX 健康，当前没有 `pending`、`queued` 或 `running` Task。Task #472
已完成取消收尾。根盘曾达 99% 使用率、剩余约 793MB；确认归属后仅清理超过一小时的 Codify
BuildKit 调试缓存 1.78GB，未触碰 `quirky_allen` 等活动容器、服务或 volume，清理后约 93%、
剩余 4.6GB。远端 app image 没有 OCI
`org.opencontainers.image.revision` label，且 source commit 尚未推送，因此当前 composition
是可复核的开发调试 candidate，不是已签署 release candidate。

此前 generation 84/Kit 0.6.14、generation 81 与 Task 439 继续保留为历史 evidence，不再代表当前
开发 Host。

## 3. 已完成证据索引

- [R1 candidate evidence](../evidence/2026-08-31-open-harness-v2-r1-candidate.md)
- [R2 conformance evidence](../evidence/2026-09-01-open-harness-v2-r2-candidate.md)
- [R3 benchmark evidence](../evidence/2026-09-01-open-harness-v2-r3-benchmark.md)
- [Task #348 启动延迟 evidence](../evidence/2026-09-02-task-348-startup-delay.md)
- [R4.1 Kit boundary evidence](../evidence/2026-09-03-open-harness-v2-r4.1-kit-boundary.md)
- [R4.3/R4.4 live Host evidence](../evidence/2026-09-04-open-harness-v2-r4.3-r4.4-live-host.md)
- [R4.5 security/release audit](../evidence/2026-09-04-open-harness-v2-r4.5-security-release-audit.md)
- [generation 78 four-Harness smoke evidence](../evidence/2026-09-05-open-harness-v2-generation-78-four-harness-smoke.md)
- [generation 81 delivery-summary regression evidence](../evidence/2026-09-05-open-harness-v2-delivery-summary-regression.md)
- [four-Harness thinking native probes](../evidence/2026-09-06-four-harness-thinking-probes.md)
- [R4-RC1 remote debug evidence](../evidence/2026-09-08-open-harness-v2-r4-rc1-remote-debug.md)
- [Codex App Server bridge evidence](../evidence/2026-09-08-open-harness-v2-codex-app-server-bridge.md)
- [Current Bundle real-task matrix](../evidence/2026-09-08-open-harness-v2-current-bundle-real-task-matrix.md)
- [Worker Kit validation boundary](../specs/2026-09-03-worker-kit-validation-boundary-design.md)
- [V2 schema and benchmark contract](../../architecture/open-harness-v2-schemas.md)
- [dual-canary and production rollout Runbook](../../runbooks/multi-harness-rollout.md)

以上 evidence 的原始 Task、digest 和 Host 快照只在各自文档维护；本 tracker 不再复制。

## 4. 唯一下一工作包：R4-RC1

R4-RC1 已在开发 Host 形成当前 source/Kit composition，并执行 #461–#474 真实 Provider Task；
其中三 Harness reasoning 与三条 Git delivery 已闭合部分证据，但固定的 8 个合法 Harness×protocol
退出条件尚未满足。完成前不追加无关 smoke，不刷新历史 benchmark，不进入 owner 签署。

### A. 冻结源码与变更范围

1. 以 `5d2fad8e7f81e947097d092e1b502f2eae31607c` 为本轮 source anchor；该提交已固定 Codex App Server Bridge 和 Worker delivery 修复，但尚未推送，故候选未签署。
2. 审阅 Git delivery 与 thinking lifecycle 两份设计的完成条件；关闭当前 L2 P0/P1，执行受影响的 backend/frontend 测试和 production build，并在真实 Codex Provider 可响应后补回归。
3. 冻结前若再修改 Worker finalization、delivery、Codex transport、Backend projection 或结果 UI，更新候选 SHA 并从本步骤重新开始。
4. 不因本工作包升级 Harness CLI、修改 Provider 协议、增加 schema 或扩展产品范围。

### B. 形成一次 exact composition

1. 从冻结提交构建 Backend/Frontend，并记录可回溯的 revision/image identity。
2. 生成包含当前 `worker-entrypoint` 的新 Runtime Bundle；不得原地修改历史 Bundle。
3. 当前 Worker image 与 Kit 0.6.15 已通过 Verify；内容未变时继续使用 immutable identity，不为 generation 数字重建 Kit。
4. 在真实 Task 前只做一次管理员 Verify，记录有效 TTL、Profile、Kit、Worker image 和各 Harness Bundle identity。

### C. 固定 8 条合并验收

以下每个合法 Harness×protocol 组合只创建一个真实 Task。每条都验证真实 Provider 的 reasoning
开始早于结束、约 5 秒内出现占位、同一行完成或中断、刷新/重连不重复；四个标注的行同时承担
Git delivery 验收，不再另开第二轮 Task。

| Harness | 模型协议 | 同一 Task 附加场景 |
| --- | --- | --- |
| Pi | `anthropic_messages` | 自主生成两个未推送提交；Worker 补推并完整展示 |
| Pi | `openai_responses` | 正常或空正文 reasoning 完成 |
| Pi | `openai_chat_completions` | 思考期间取消并刷新/重连；同一记录变为 `interrupted` |
| OpenCode | `anthropic_messages` | 推送 A、再提交 B 并留下少量未提交改动；Worker 安全补交 |
| OpenCode | `openai_responses` | durable lifecycle 与 part snapshot 不重复 |
| OpenCode | `openai_chat_completions` | 思考期间取消并刷新/重连；session 终态正确 |
| Claude | `anthropic_messages` | 完成真实 thinking 后制造受控远端拒绝/并发分叉；远端受保护且 MR 不误标 Ready |
| Codex | `openai_responses` | 成功但零代码变化；必须实证 `item.started` 早于 `item.completed`，不生成空提交或虚假 SHA |

验收前先用带接收时间的原生/可控探针确认开始信号可实时到达。若 Codex `exec --json` 只有完成信号，
按 thinking plan 的既定出口停止该 candidate 并实现 App Server stdio Bridge；不得用更多 Provider 重试、
通用等待卡或完成后静态内容冒充提前占位。8 条均使用受控测试仓库和合法 Provider；任一 P0/P1
立即停止整个 candidate，完成最小修复后生成新 candidate，不用后续成功 Task 稀释失败证据。

本轮已执行的 Task 映射、archive 序号、reasoning 计数、远端 refs 和浏览器页面见独立 evidence。
#461/#462/#463 使用新 Codex App Server transport，但均因 Provider 上游模型不可用或地区限制
在 reasoning 之前失败；它们只能证明真实 transport/失败边界，不能计入 Codex 行的成功验收。
#464–#474 的当前 Bundle 矩阵补充了 Pi/OpenCode/Claude 的真实 reasoning、delivery、Provider
边界；#468/#469/#471 的 `worker.finalization` 均报告精确 remote SHA。
#472 另外在真实 Codify 页面中捕获了运行中 `正在思考 · 1s`、同一行完成、工具事件继续增长，
随后取消并刷新为稳定终态；它没有发生在活动 reasoning block 内，因此不能计入 interrupted
thinking 或长思考验收。#473 的 OpenCode 页面观察落在完成后，只能证明终态投影，不能证明
运行中占位先于完成。#474 补齐了 Claude 运行中占位与同一行完成的页面时序。
#450/#452/#453/#457 提供了部分成功交付/生命周期 evidence；#451、#456、#458、#454、#459 和
#449 分别暴露了 zero-change 无 reasoning、无 reasoning 的取消、Claude normalization failure 及
复杂 reconciliation timeout 边界。#455 的 Provider 404 不计入验收。

### D. R4-RC1 退出条件

- 当前 committed source 的受影响测试、frontend build、shell syntax 和 diff check 全部通过；
- 新 Backend/Frontend/Runtime Bundle 与 Task Snapshot identity 一致，无 deployment drift；
- 8 条真实 Task 的原生接收时间、reasoning ID、canonical seq、TaskLog、SSE/页面状态、remote refs、
  提交图、`worker_metadata.git_delivery`、Task 结果卡、MR、archive、notification、container/lock cleanup 全部核对；
- 四 Harness 均至少一条真实长思考页面证据；开始信号先于完成，取消/异常只中断对应块；
- push 失败不会产生成功 Task、虚假 remote-confirmed SHA 或错误 Ready MR；
- 无未接受的 P0/P1；形成一份独立、脱敏的 R4-RC1 evidence；
- 完成后停止技术执行，转入 R4.5 owner closure，不再追加普通 smoke。

本轮退出条件仍未满足：Codex App Server 已部署但没有 canonical reasoning start/end，#461–#463
均未获得模型响应；Pi Chat #470 在 Provider 404 前失败，Pi #464/#472 的取消均发生在活动
tool/诊断而非 reasoning block；Claude 的受控远端 divergence、可用 Responses/Chat 协议行、
以及 OpenCode 成功 Task 的实时浏览器时序仍未证明。#472/#474 关闭了 Pi/Claude 的页面时序子项，
不改变四 Harness 长思考和 8 行矩阵的未完成状态。因此 R4-RC1 保持开放，R4.3/R4.4 不签署。

## 5. R4.5 owner closure

技术 candidate 不能代替以下 owner 输入。所有项必须绑定 R4-RC1 的 exact identity：

| Owner | 必须提供的结果 |
| --- | --- |
| Provider/GitLab/OAuth credential owner | 最小权限 scope、有效凭据来源、最近轮换时间、撤销/恢复流程和账户控制确认 |
| Migration owner | 数据库备份/恢复点、migration 078 执行决定，以及 Provider 11 与受影响历史引用的处理和复验计划 |
| Release owner | 精确 release notes、签名 package/manifest、签名 identity |
| Operations owner | Kit/image retention 与退役日期、维护窗口、rollback owner、观察窗口 |
| Independent reviewer | R4.3–R4.5 当前 P0/P1、已接受例外和明确 R4.6 `GO`/`NO-GO` |

当前审计已发现权限与治理项尚未闭合；重复 Task、短期 readiness 或开发 Host 健康不能替代 owner 签署。
任一输入缺失时，R4.5 保持 **未签署**，R4.6 记录 `NO-GO`，系统保持 `dual_canary`。

## 6. R4.6 与 R5

R4.6 只接受两种结论：

- `GO`：R4-RC1 identity 未漂移，R4.3–R4.5 无阻断并全部签署，且明确目标 Host、R5 窗口和 owner；
- `NO-GO`：列出具体阻断、责任人和重新评审条件，停止新增 smoke。

只有 `GO` 且获得单独执行批准后，才按 Runbook 在维护窗口执行 R5：暂停创建/调度、排空任务、
备份、由唯一 owner 执行已评审 migration、切换 Pi 默认与 `v2_only`、执行最小四 Harness release smoke、
确认 V1 execute/retry/schedule/resume 被拒绝而历史详情保持只读。失败时保持维护状态并 roll forward。

## 7. 证据失效与停止规则

| 变化 | 处理 |
| --- | --- |
| 仅文档变化 | 不重开技术 evidence |
| 仅前端交互变化 | 重跑受影响前端测试与 R4.3，不重跑协议矩阵或 benchmark |
| Runtime Bundle/finalization/delivery/terminal/archive 变化 | 生成新 Bundle，更新 L2/L3，补跑受影响 R2/R4.4 场景 |
| Adapter、Canonical Event 或 reasoning 投影变化 | 生成新 Bundle，重验受影响 Harness×protocol 行和 R4.3 页面时序；不自动重跑无关 benchmark |
| Harness CLI、Provider protocol/model 或 execution options 变化 | 生成新 immutable identity，重做受影响 L3/L4/R2/R3 evidence |
| readiness TTL 过期 | 状态派生为 `unknown`；发布前重新 Verify，不重跑历史里程碑 |

出现以下任一情况立即停止当前 candidate：identity 漂移、mutable artifact、隐式 CLI 回退、
跨 Task session/config 串线、command/terminal/receipt 不变量破坏、凭据泄漏、错误成功判定、远端覆盖、
无法取消、P0/P1 或未接受的发布例外。不得用后续成功 Task 覆盖或稀释已有失败。

## 8. 不进入本轮

- 不增加撤销、denylist、任务迁移、紧急回退状态或新的过渡 schema；
- 不升级 Harness CLI，不修改协议适用矩阵，不重新跑完整 R3 benchmark；
- 不为 readiness 或 Kit 校验增加数据库字段、双模式或后台周期性扫描；
- 不执行用户已暂缓的真实移动设备键盘/IME/刘海/手势区验收；
- 不清理 shared Host 的服务、volume、active/unknown Worker 或未确认归属的 image/archive；
- 不执行 migration 078、`v2_only` 或 R5，除非获得对应 owner 签署和单独批准。
