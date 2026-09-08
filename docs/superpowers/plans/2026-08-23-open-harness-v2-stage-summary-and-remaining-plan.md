# Open-Harness V2 当前状态与剩余验收计划

**复核日期：** 2026-09-08

> 本文件只维护当前结论、证据边界、唯一下一工作包、退出条件和停止规则。
> Task/Issue 编号、逐次 Host 快照、digest、generation 和测试明细只保留在独立 evidence、
> runtime archive、数据库与 Git history 中，不再向本文件追加 `continuation` 流水帐。

**2026-09-08 思考详情回归修正：** 思考占位只补充生命周期和耗时反馈，不再按
`in_progress`/`completed` 状态隐藏已有正文。只要 Canonical 事件已有 `payload_id`、内联正文或已加载正文，
前端继续显示预览和“完整内容”入口；真正空的占位才只显示状态。提交 `b7cacd47` 已补齐这一 UI 回归，
并让 Codex 仅投影 Provider 明确提供的可读 `summary_text`/`summaryTextDelta`，不把原始隐藏
`content`/`textDelta` 当作页面正文。真实 Task #526 页面已展开 Pi 思考正文；新 Codex Task #533 的
App Server 原始 reasoning `summary`/`content` 均为空且没有 `summaryTextDelta`，因此它的空详情是 Provider
没有提供可读摘要，不是页面隐藏。

**2026-09-08 Codex Go Provider 长思考探针：** 按用户指定使用 Provider 4
`opencode-luna / gpt-5.6-luna`（`https://opencode.ai/zen/go/v1`）在同一 Profile 4 generation 98、Kit 0.6.16、
Bundle 215 上完成真实 Codex Task #536/#537；两次页面运行中均出现 `正在思考 · 8s`，但单一 reasoning block
最大仅 `8.377s`/`8.160s`，任务总时长 `51s`/`92s` 不计入长思考门槛。两次均 `+0/-0`、无提交、Canonical
receipt 连续，归档仍无可读 summary/payload；#534/#535 的免费 OpenRouter provider 则在 reasoning 前被上游
404 拒绝。详细边界见 [Codex Go Provider long-thinking probes](../evidence/2026-09-08-open-harness-v2-codex-long-thinking-probes.md)。

**2026-09-08 reasoning 验收口径更新：** 用户确认本轮不需要 30 秒长思考，稳定的约 5–6 秒真实 reasoning
block 即可。随后在 source `4249fcc4` 上完成 Task #539：Provider 4、Profile 4 generation 99、Kit 0.6.16、
Bundle 216，显式快照 `{"codex":{"reasoning_effort":"high"}}`；11 个 reasoning block 均正常
`started → completed`，耗时 `5.204–6.349s`，页面先显示 `正在思考`，无代码变化、提交或远端写入。该任务关闭
“Codex 必须达到 30s”这一旧技术缺口。结合不可变历史 Task #468/#469/#488/#513/#517/#521/#523，固定 8 行
技术 evidence 已形成预期结果；R4.3/R4.4 剩余为正式 identity/验收签署，R4.5 仍等待 owner closure。详见同一
[Codex Go Provider reasoning probe evidence](../evidence/2026-09-08-open-harness-v2-codex-long-thinking-probes.md)。

**2026-09-08 readiness TTL 复核：** 在继续推进 release gate 前，对同一开发 Host 的 Profile 4 做了显式管理员
Verify。四个 Harness 均通过，Profile generation 更新为 `100`，readiness 有效至 `2026-09-08 09:07:59 UTC`；
Worker image、Kit `0.6.16`、manifest SHA 和 Harness inventory 均未变化，验证容器已清理，未产生新的 Bundle。
Task #539 / Bundle 216 保留为 generation `99` 下的不可变真实 Task 证据；由于没有实际 runtime artifact 漂移，
不追加重复 smoke，当前 release identity 以 generation `100` 为准。

## 1. 当前结论

**当前执行门禁：`NO-GO`（尚未形成 R4.6 正式签署）。** 系统继续保持 `dual_canary`；不得执行 migration 078、
切换 `v2_only` 或进入 R5。暂停重复只读 smoke，先冻结与当前源码一致的新 release candidate。

| 工作包 | 状态 | 当前结论 |
| --- | --- | --- |
| R1：Internal Preview candidate | **完成** | 四 Harness 的 `linux/amd64` Image、Kit、Profile、Bundle 与真实 Host identity 已有可追溯历史证据 |
| R2：四 Harness hard-cut conformance | **完成，受影响场景重开** | 历史 8 个适用 Harness×protocol 行及 lifecycle/command/recovery 已闭合；`c089b67a`、`7fd0939c` 及 `5d2fad8e` 修改 reasoning lifecycle、共享 delivery 隔离边界和 Codex App Server transport，仍须在同一 candidate 上重验受影响组合 |
| R3：正式 20-scenario benchmark | **完成** | Pi/OpenCode 20/20 formal pair 与 Pi 非劣性门槛已通过；当前变化未升级 CLI 或修改 model endpoint protocol，但切换了 Codex control transport，故不整体重跑 benchmark、改由 R2/R4 重验 Codex；真实验收若发现 terminal、质量或性能回归再按影响重开 |
| R4.1：可信 Kit 启动边界 | **完成** | content-addressed 安装、管理员完整 Verify、Task 热路径轻量校验与 warm-start 已有 L2–L4 证据 |
| R4.2：冻结 exact candidate | **已形成，未签署** | 当前调试 overlay 已推进到 source `4249fcc4`、Profile 4 generation `100`、Worker Kit 0.6.16、Backend image `sha256:029384d710497c768bd6ca23ef6fa62fcd4751670d03d7aa0c35d990e91ed81e`、NGINX image `sha256:aa09c11639f0f5838c085006c0690344f32536c1dcbd91dda37681cd6e253f2`；Task #539 的 Bundle 216 是 generation `99` 下的不可变真实 Task 证据，历史 Bundle 198–215 保持不可变；镜像没有 OCI source revision label，且尚未推送，故仍不是已签署 candidate |
| R4.3：正式交互验收 | **技术 evidence 已闭合，未签署** | 固定 8 行由 #468/#469/#488/#513/#517/#521/#523 与 generation `99` 快照下的 #539 组成，覆盖四 Harness 的真实占位、完成/中断、刷新/重连、正文边界和受控 fail-closed；Task #539 在 Bundle 216 上补齐 Provider 4 + Codex 的 `reasoning_effort=high`、11 个 `started → completed` 生命周期和 `5.204–6.349s` 页面/TaskLog 时序。reasoning 空 summary 仍保持状态-only，不伪造正文；5–6 秒已是当前口径。剩余是固定 8 行整体 identity 与正式签署，移动设备验收不作为本轮技术执行项 |
| R4.4：运维与真实 Task 验收 | **技术 evidence 已闭合，未签署** | #468/#469/#488/#513/#517/#521/#523 与 generation `99` 快照下的 #539 已覆盖 delivery、finalization、archive、取消、零变化、Codex reasoning 和受控远端 divergence；#488 的失败是预期 fail-closed。Task #539 的 canonical receipt `1..34` 连续、`+0/-0`、`commit_sha=null`，无远端写入。当前不再以 30s 单段 reasoning 作为技术门槛；generation `100` Verify 未改变这些 runtime artifact。剩余是 exact identity/owner 签署，而不是追加普通 smoke |
| R4.5：安全与发布审计 | **技术审计已收敛，阻塞于 owner 输入** | 当前 candidate 的 identity、测试、Provider credential-ref 边界、Docker/Kit 状态和未执行项已记录在 [R4.5 current-candidate audit](../evidence/2026-09-08-open-harness-v2-r4.5-current-candidate-audit.md)；最小权限/轮换、migration 078 决定、签名发布包、retention、维护窗口与独立 P0/P1 审阅仍未签署 |
| R4.6：hard-cut go/no-go | **未执行** | R4.2–R4.5 全部闭合后才能形成独立 `GO` 或 `NO-GO` |
| R5：L6 `v2_only` hard cut | **未执行** | 仅在 R4.6 `GO` 且获得单独执行批准后进入维护窗口 |

完成 R1–R3 证明 V2 的合同、四 Harness 适用矩阵和 formal benchmark 已成立；它们不能替代
当前源码的 release candidate、owner 签署或 hard cut。generation 数量、重复 Task 数量和文档提交数
都不是推进指标；只有上表状态变化才算推进。

## 2. 当前源码与部署边界

### 2.1 当前源码

| 项 | 当前值 |
| --- | --- |
| Git revision | `4249fcc4` (`feat(codex): forward configured reasoning effort`)；保留 `b7cacd47` 的思考正文入口修复 |
| 分支状态 | `dev` 的运行时 candidate 仍以 `4249fcc4` 为 source anchor；本轮另补齐严格 `git_delivery` contract 的旧测试夹具与当前 evidence，候选及关联文档仍未推送；既有 security audit 仍按独立路径处理 |
| 影响面 | 思考占位/预览/完整内容入口、Codex App Server explicit `summary_text`/`summaryTextDelta` 投影、`turn/start.effort` options、Adapter/manifest/runtime digest 与既有 Canonical reasoning 投影；不读取 Codex 原始隐藏 `content`/`textDelta` |
| 设计基线 | [Task Git delivery reconciliation design](../specs/2026-09-04-task-git-delivery-reconciliation-design.md)；[four-Harness thinking lifecycle plan](2026-09-04-thinking-event-placeholder-plan.md) |
| 当前聚焦 L2 | 当前 Backend unit suite `3419 passed, 4 skipped, 99 subtests`；Frontend unit suite `1748 passed`（80 files），`npm run build`、Backend lint、受影响 106 tests、shell/diff check 均通过；生产部署仍保持既有 Runtime identity |

本轮提交不升级 Harness CLI、不修改 Provider 协议、Scheduler 排队规则或既有 Task Snapshot schema；
除既有 Codex App Server Bridge/Pi endpoint 变更外，`4f42b9d7` 调整 Worker finalization 的
console FIFO drain 与 canonical finalization 顺序，`90dfe874` 增加 native OpenCode abort 后
Bridge 有界 drain 与回归测试，`6835e43c` 修复仓库准备早于 Harness 失败时的 canonical
terminal 缺口；未升级 Harness CLI、未修改 Provider 协议或 Task Snapshot schema。
`dcd0b7b5` 在外部取消/超时先于 Adapter 原生结束事件到达时，为仍开放的 reasoning block 写出
`reasoning_summary.interrupted`，保持已关闭 block 不变；未升级 Harness CLI、未修改 Provider 协议或 Task Snapshot schema。
因此必须在同一 exact composition 上重验受影响的 OpenCode terminal/archive，以及 Codex reasoning、
session、usage、最终结果和共享 Git delivery；局部测试和直接 Adapter fixture 不等于 L3/L4/L5
evidence。

### 2.2 远端开发 candidate

> 本节早期 Bundle/Kit 段落保留历史 identity；当前开发 composition 以本节末尾的
> “当前 reasoning effort overlay”和 R4.2 表为准。

本轮在开发 Host 形成了包含 Pi endpoint、Worker finalization、OpenCode native abort drain 与
pre-Harness finalizer 与外部取消 reasoning 收尾修复的新调试 composition：Profile 4 为
`v2-canary-0.6.11-four-harness`，Backend image 为
`sha256:7e1878d5107dcc0e4871ef269bf1ddea16fbf03046301bb291a56dae31dc62cf`，NGINX image 为
`sha256:ba50f6296e92e426dd445740d7214c6c54aaddd2a79d58d1513a4741379c6e43`，Runtime Bundle 为
`201/202/203/204/205/206/207/208/209/210/211/212/213/214`（Bundle 205 为 native abort drain 修复后的历史任务快照，Bundle 206 为 #504/#505 的历史任务快照，Bundle 207 为 #508，Bundle 208 为 #510/#511/#512/#515/#518，Bundle 209 为 #513，Bundle 210 为 #514/#516/#517，Bundle 211 为 #521/#526，Bundle 212 为 #523/#527/#531，Bundle 213 为 #524/#525/#529/#532，Bundle 214 为 #528；历史 Bundle 仍保持不可变），Worker Kit 为 `0.6.15`、manifest SHA 为
`506dbc2c61fbc03144c45fdffcd9a0e264781fe4038ad0ed13b38112580b831b`；Profile Verify 和真实
Pi/OpenCode/Claude/Codex Task 结果详见 [Codex App Server bridge evidence](../evidence/2026-09-08-open-harness-v2-codex-app-server-bridge.md)
和 [Current Bundle real-task matrix](../evidence/2026-09-08-open-harness-v2-current-bundle-real-task-matrix.md)。

Profile 4 在创建 #499 前为 generation `94`；部署 pre-Harness 修复后重新 Verify 为 generation
`95`，部署外部取消 reasoning 收尾修复后再次 Verify 为 generation `96`，四 Harness 状态“已就绪”。Bundle 205
digest 为 `a9992043629103ef544de7250d1817e14cfd5f61653f17a4feab57176c38a2c9`，其中 OpenCode
manifest adapter digest 为 `969cd7d9a560c489df42b58e316fc30df16f1826efe5e6109eb089455bdba7ad`，
adapter 文件 SHA 为 `093005ffe94815daf84381d9bfbaa77a012ac5963699906e3415613de772c29b`，共享
`worker-entrypoint/bootstrap.sh` digest 为 `f7d0bbfcdae1fb336584a88cb468c421d4c7979496ca3b007e1e79236c2662cf`。#477 使用
Bundle 201（digest `d2e9acdddcb3470e39d3c65eb45176462022154584ab54eef701311e4b173dfa`），其 Pi
adapter digest 为 `d326e5c4f0bc2eedcbc4d835ef17c804d1b07b959be5a6af9384309d50249c3d`；旧 Bundle 198
的 Pi adapter digest 为 `e619b8464d7b1c6fee08661eb1e2dd3a87da58065f10dc9166d749403a836356`。
随后 OpenCode Task #479/#480 绑定同一 Kit/Backend composition 的 Bundle 202，digest 为
`415d0ba667afb4e6b81a7e9ab919e2a25104da5d7115df38ea8bdfaf4f230226`，OpenCode adapter digest
为 `ae70869632a2f0b54e550b9904055321d613dbe266bcd9f7f77b4f50b2227b5d`。#482 复用 Bundle 202，
#483 复用 Bundle 201；#485–#488 复用 Bundle 203（digest
`4f22bb5db5e00fdbab820c4d1a5ada8da212555049b7a26c27730d88430a167e`）。Responses 任务
均在 reasoning 前被现有 Provider 以 404/403 拒绝。
随后 #504/#505 绑定 Bundle 206（digest
`921d7b53676eb61f4b8c1301802392e8791fe1d912cfddecd1381caddd28dffc`）；其四 Harness manifest
与 Bundle 205 相同。#505 的 Claude reasoning 仅约 2.0 秒，虽整项任务运行约 2m32s 并正常
封存 archive/finalization，但不能计入长思考。#508 绑定 Bundle 207（digest
`6dca863dcb69e26bd6ce9db082e7fd5d1827fdfa6b46027322cb8524fd2bda35`）并完成 Codex 成功回归；
#510/#511 绑定 Bundle 208（digest
`96341e488faa37bd081169a3c69a91504fbbaa2efa89f0ce890eb2e55114adc7`）：#510 完成 pre-Harness
canonical failure 回归，#511 完成 Codex 零变化成功回归。
#512 在同一 Bundle 记录了长运行但短 reasoning、未捕获活动取消的负证据；#513 绑定 Bundle 209
完成当前 Provider 4 的 OpenCode Responses 成功回归；#514 绑定 Bundle 210 复核 Pi Responses，
以真实 401/活动 tool `protocol_error` 收敛，未改变 Provider 配置；#516/#517 继续复用 Bundle 210，
分别确认 Pi 无 reasoning 基础响应与正常 reasoning 成功 terminal；#518 复用 Bundle 208，记录
Codex 32s 只读探针的 4 个短 reasoning block（最大约 4.139s）和零变化 finalization；#521 绑定
Bundle 211，使用 Provider 5 `opencode-mimo / mimo-v2.5` 的 Pi Chat 取消探针，验证外部取消时
open reasoning 收尾为 canonical `reasoning_summary.interrupted(reason=worker_cancelled)`，并完成
刷新终态、archive 与容器清理。

远端 Backend、Scheduler、NGINX 健康，当前没有 `pending`、`queued` 或 `running` Task。Task #490–#539
已完成终态收尾。当前根盘约 91% 使用率、剩余约 6.0GB；本轮仅清理了明确的失败 Builder 缓存和临时 Kit 归档，未触碰活动容器、服务、
volume 或不确定归属的 image。远端 app image 没有 OCI
`org.opencontainers.image.revision` label，且 source commit 尚未推送，因此当前 composition
是可复核的开发调试 candidate，不是已签署 release candidate。

**2026-09-08 思考详情 overlay：** Worker Kit 0.6.16 安装在
`/home/codify/worker-kits/0.6.16-linux-amd64-4866812149bd`，manifest SHA-256 为
`4866812149bd240af4802ab1aa11b8364cc49b400a8d4a71d2721b8ac9ef5f9c`；Profile 4 generation 98
管理员 Verify 为 `ready`，四个 Harness inventory 均为 present（Pi 0.84.2、OpenCode 1.18.19、
Claude 2.1.153、Codex 0.146.0）。由于远端根盘曾在 Kit 构建时耗尽，Kit 在本机支持
`linux/amd64` 的 Builder 完成后传输并在远端 `/home` 分区安装；没有修改已有 `/opt` Kit、volume
或运行中服务。当前 NGINX image 为 AMD64
`sha256:aa09c11639f0f5838c085006c0690344f32536c1dcbd91dda37681cd6e253f2`，浏览器/HTTP 访问已验证。
Task #533（Issue #137，Provider 4 `opencode-luna / gpt-5.6-luna`，Codex）绑定 Bundle 215，
digest 为 `0a8281eccbaeec443bfc65bb02180d9e989692d881bfb79cf4f811efb29bde94`，快照使用上述 Kit、
CLI digest 为 `2e863156ed35ecc5253b1e2f907a9143077b9f7cb51942070c61996471ff6e04`；任务成功完成、
无代码变化，但归档里的 reasoning item 都是 `summary:[]/content:[]`，没有
`item/reasoning/summaryTextDelta`，所以没有可展示正文。Task #526 的已有 Pi 正文则在
`http://192.168.50.129:8880/tasks/526` 通过“完整内容”按钮实际展开，证明 UI 没有隐藏已投影正文。
详细 archive、原始 App Server 行和测试结果见 [thinking detail regression evidence](../evidence/2026-09-08-open-harness-v2-thinking-detail-regression.md)。

随后 Task #536/#537 在同一 Bundle、Profile 和 Provider 4 上完成两次真实 Codex Go Provider 长思考探针；
页面运行中的 `正在思考 · 8s` 占位先于完成，Canonical receipt 连续且均 `+0/-0`，但单段 reasoning 最大仅
`8.377s`/`8.160s`，归档仍没有可读 summary/payload。#534/#535 的免费 OpenRouter 组合在 reasoning 前被
上游 404 拒绝，未改变 Provider 配置。详细探针数据见 [Codex Go Provider long-thinking probes](../evidence/2026-09-08-open-harness-v2-codex-long-thinking-probes.md)。

**2026-09-08 当前 reasoning effort overlay：** 为支持真实 OpenCode Go 验证，Backend/Scheduler 已部署
source `4249fcc4`（Backend image `sha256:029384d710497c768bd6ca23ef6fa62fcd4751670d03d7aa0c35d990e91ed81e`），
Task #539 创建时 Profile 4 的 Verify generation 为 `99`，Worker Kit 仍为 0.6.16；代码更新后的 Codex adapter digest
为 `9cc9dfe316cbba7f93ae1aad751f95f729e67706de365206671d6e485ae247b0`。Task #539 绑定新 Bundle 216
（digest `c374ef5a009c53d2fc469a262e5cabcb23efff97f9d6176655992198bba946a7`），快照明确包含
`{"codex":{"reasoning_effort":"high"}}`，Provider 4 为 `openai_responses` / OpenCode Go；11 个真实
reasoning block 均正常完成，耗时 `5.204–6.349s`，Canonical receipt `1..34` 连续，任务 `+0/-0`、无提交。
本轮不再要求 30s 单段长思考；历史 #536/#537 的长思考负证据仍保留为历史对照。详见 [Codex Go Provider reasoning
probe evidence](../evidence/2026-09-08-open-harness-v2-codex-long-thinking-probes.md)。

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
- [R4.5 current-candidate audit](../evidence/2026-09-08-open-harness-v2-r4.5-current-candidate-audit.md)
- [generation 78 four-Harness smoke evidence](../evidence/2026-09-05-open-harness-v2-generation-78-four-harness-smoke.md)
- [generation 81 delivery-summary regression evidence](../evidence/2026-09-05-open-harness-v2-delivery-summary-regression.md)
- [four-Harness thinking native probes](../evidence/2026-09-06-four-harness-thinking-probes.md)
- [R4-RC1 remote debug evidence](../evidence/2026-09-08-open-harness-v2-r4-rc1-remote-debug.md)
- [Codex App Server bridge evidence](../evidence/2026-09-08-open-harness-v2-codex-app-server-bridge.md)
- [Thinking detail regression evidence](../evidence/2026-09-08-open-harness-v2-thinking-detail-regression.md)
- [Codex Go Provider reasoning probes](../evidence/2026-09-08-open-harness-v2-codex-long-thinking-probes.md)
- [Current Bundle real-task matrix](../evidence/2026-09-08-open-harness-v2-current-bundle-real-task-matrix.md)
- [Worker Kit validation boundary](../specs/2026-09-03-worker-kit-validation-boundary-design.md)
- [V2 schema and benchmark contract](../../architecture/open-harness-v2-schemas.md)
- [dual-canary and production rollout Runbook](../../runbooks/multi-harness-rollout.md)

以上 evidence 的原始 Task、digest 和 Host 快照只在各自文档维护；本 tracker 不再复制。

## 4. 唯一下一工作包：R4-RC1

R4-RC1 已在开发 Host 形成当前 source/Kit composition，并完成固定 8 行的真实 Provider evidence；
其中 #468/#469/#488/#513/#517/#521/#523 使用不可变历史 Bundle，Codex 行由 generation `99` 快照下的 #539
在 Bundle 216 上重验；当前 generation `100` 仅重新确认了相同 image/Kit/runtime readiness。技术退出条件已形成预期结果，尚未完成的是 R4.2–R4.4 的正式 identity/验收签署
和 R4.5 owner closure。停止追加无关 smoke，不刷新历史 benchmark，不进入 owner 签署前的 hard cut。

### A. 冻结源码与变更范围

1. 以 `4249fcc4` 为本轮 source anchor；该提交在既有 Codex App Server/Worker delivery、外部取消 reasoning 收尾和思考正文入口修复之上，补齐 Codex `reasoning_effort` 的 Profile options、Worker adapter 校验/导出和 App Server `turn/start.effort`；尚未推送，故候选未签署。
2. 审阅 Git delivery 与 thinking lifecycle 两份设计的完成条件；关闭当前 L2 P0/P1，执行受影响的 backend/frontend 测试和 production build，并在真实 Codex Provider 可响应后补回归。当前 finalization/native abort/pre-Harness/外部取消续测见 [Current Bundle real-task matrix](../evidence/2026-09-08-open-harness-v2-current-bundle-real-task-matrix.md) 的第 5–7 节。
3. 冻结前若再修改 Worker finalization、delivery、Codex transport、Backend projection 或结果 UI，更新候选 SHA 并从本步骤重新开始。
4. 不因本工作包升级 Harness CLI、修改 Provider 协议、增加 schema 或扩展产品范围。

### B. 形成一次 exact composition

1. 从冻结提交构建 Backend/Frontend，并记录可回溯的 revision/image identity。
2. 生成包含当前 `worker-entrypoint` 的新 Runtime Bundle；不得原地修改历史 Bundle。
3. 当前 Worker image 与 Kit 0.6.16 已通过 Verify；内容未变时继续使用 immutable identity，不为 generation 数字重建 Kit。
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

固定 8 行的技术结果已由不可变历史 Task 与当前受影响 Codex Task 组成：Pi `anthropic_messages` #468、Pi
`openai_responses` #517、Pi Chat 取消 #521、OpenCode `anthropic_messages` #469、OpenCode
`openai_responses` #513、OpenCode Chat 取消 #523、Claude 受控 divergence #488（预期 fail-closed），以及
当前 source `4249fcc4` 上的 Codex `openai_responses` #539。#511 保留为上一候选的 Codex 零变化基线；本轮只改变
Codex options/adapter，因此没有重复创建不受影响 Harness 的 Task。每一行均以真实 receipt、TaskLog、最终化、
archive 和 delivery 结果核对；“全部通过”包含 #488 按预期拒绝远端覆盖。技术项闭合不等于 R4.2–R4.5 签署。

验收前先用带接收时间的原生/可控探针确认开始信号可实时到达。若 Codex `exec --json` 只有完成信号，
按 thinking plan 的既定出口停止该 candidate 并实现 App Server stdio Bridge；不得用更多 Provider 重试、
通用等待卡或完成后静态内容冒充提前占位。8 条均使用受控测试仓库和合法 Provider；任一 P0/P1
立即停止整个 candidate，完成最小修复后生成新 candidate，不用后续成功 Task 稀释失败证据。

本轮已执行的 Task 映射、archive 序号、reasoning 计数、远端 refs 和浏览器页面见独立 evidence。
#461/#462/#463 使用新 Codex App Server transport，但均因 Provider 上游模型不可用或地区限制
在 reasoning 之前失败；它们只能证明真实 transport/失败边界，不能计入 Codex 行的成功验收。
#464–#488 的 Bundle 矩阵补充了 Pi/OpenCode/Claude 的真实 reasoning、delivery、Provider
边界；#468/#469/#471/#485/#486/#487 的 `worker.finalization` 均报告精确 remote SHA。#482/#483/#484 在当前
Bundle 202/201/202 上分别用 OpenCode/Provider 9、Pi/Provider 12 和 OpenCode/Provider 4 复核
`openai_responses`；前两者在 reasoning 之前收到 OpenRouter 免费模型 404，#484 收到上游地区
403，attempt、raw/archive 和 control close 正常，不能计入 Responses 行，也不授权修改现有
Provider 到付费 slug 或绕过地区策略。#485–#487 在 Bundle 203 上完成 Claude reasoning 与
正常 delivery；#488 在同一 Bundle 上以并发远端空提交触发 `remote_diverged`，delivery 拒绝
覆盖远端分支且没有 remote-confirmed Worker SHA，关闭 Claude 受控 divergence 的 fail-closed
边界。
#472 另外在真实 Codify 页面中捕获了运行中 `正在思考 · 1s`、同一行完成、工具事件继续增长，
随后取消并刷新为稳定终态；它没有发生在活动 reasoning block 内，因此不能计入 interrupted
thinking 或长思考验收。#478 在 Bundle 201/Pi Chat 上捕获了活动 `正在思考 · 2s` 后取消，
刷新/重连稳定显示 `已取消`；该次没有 canonical `reasoning_summary.interrupted`，由 TaskLog
终态兜底保留一条 `interrupted`，因此只关闭允许的用户态终态兜底，不伪称 canonical interrupted
receipt。#473/#479/#480 的 OpenCode 页面观察分别落在终态或自然完成，#480 未发生取消；#481
在第二段 reasoning 已完成约 7.3 秒后才取消，实际位于工具/诊断阶段，不能关闭 OpenCode Chat
活动思考取消/刷新项；Bundle 205 的 #503 已补齐 OpenCode 活动 reasoning 的 canonical
`interrupted` 与刷新后 `已取消`。#474 补齐了 Claude 运行中占位与同一行完成的页面时序。
#450/#452/#453/#457 提供了部分成功交付/生命周期 evidence；#451、#456、#458、#454、#459 和
#449 分别暴露了 zero-change 无 reasoning、无 reasoning 的取消、Claude normalization failure 及
复杂 reconciliation timeout 边界。#455 的 Provider 404 不计入验收。
#504 在受控 Issue #131 远端分叉下于进入 Harness 前拒绝 merge/overwrite，没有 canonical receipt，
不计入 Provider/reasoning 行；#505 在 Bundle 206 上完成 Claude 长运行 probe，但 reasoning
start/end 仅约 2.0 秒，属于正常 terminal/archive evidence，不关闭长思考条件；#508 在 Bundle 207
完成 Codex App Server 真实 reasoning 与 delivery；#510 在 Bundle 208 验证新的 pre-Harness
canonical failure finalization；#511 在同一 Bundle 208 验证 Codex 零变化成功不会生成空提交或
虚假远端 SHA；#513 在 Bundle 209 证明 OpenCode `openai_responses` 当前真实 Provider 可成功完成
durable lifecycle，`+0/-0` 且无提交；#514 在 Bundle 210 复核 Pi `openai_responses`，Pi 归档中出现
脱敏上游 401，但 canonical 终态因活动 tool 以 `protocol_error` fail-closed，11 个 tool start
中只有 10 个 completion，不能把该多轮工具链失败误计入成功；#515 复用 Bundle 208 完成 Codex 运行中
取消、页面刷新终态与 canonical finalization/archive/cleanup 验证；#516/#517 复用 Bundle 210，分别
确认 Pi 基础 Responses 可用和正常 reasoning start/end、零变化 finalization；#518 复用 Bundle 208
保留 Codex 总运行时间与单段 reasoning 时长的历史区分；本轮已取消 30s 长 reasoning 门槛；#521 在 Bundle 211 使用 Pi Chat 真实取消探针，补齐
外部取消 finalizer 产生的 canonical `reasoning_summary.interrupted`、刷新后 `已取消`、archive 与容器清理。
#523 在 Bundle 212 补齐 OpenCode Chat 的同一闭环，#524 在 Bundle 213 补齐 Codex 活动 reasoning
取消/刷新闭环；#525/#526/#527/#528/#529/#531/#532 又在同一 exact composition 上形成 Codex、Pi、OpenCode、Claude 的
长思考正负证据：Pi #526 的 block 为 63.864s、Claude #528 的两个 block 为 469.513s/213.294s，OpenCode #531
的 block 为 1,040.182s，而 Codex #525/#529/#532 最大仅 7.635s/7.116s/6.938s；所有有效任务均正常收敛且未产生代码变化或远端写入。
该失败边界不授权修改
Provider 凭据、模型 slug 或绕过上游认证；若后续要修复多轮工具链，必须生成新 Bundle 并重新执行受影响行。

### D. R4-RC1 退出条件

- 当前 committed source 的受影响测试、frontend build、shell syntax 和 diff check 全部通过；
- 新 Backend/Frontend/Runtime Bundle 与 Task Snapshot identity 一致，无 deployment drift；
- 固定 8 行技术 evidence 的原生接收时间、reasoning ID、canonical seq、TaskLog、SSE/页面状态、remote refs、
  提交图、`worker_metadata.git_delivery`、Task 结果卡、MR、archive、notification、container/lock cleanup 全部核对；
- 四 Harness 均至少一条真实 reasoning 页面证据；当前 Pi #526、Claude #528、OpenCode #531 与 Codex #539
  均已出现开始先于结束的页面/Canonical lifecycle，约 5–6 秒即可作为本轮可用性证据；取消/异常只中断对应块；
- push 失败不会产生成功 Task、虚假 remote-confirmed SHA 或错误 Ready MR；
- 无未接受的 P0/P1；形成一份独立、脱敏的 R4-RC1 evidence；
- 完成后停止技术执行，转入 R4.5 owner closure，不再追加普通 smoke。

当前技术执行不再因 30 秒单段 reasoning 开放：generation `99` 快照下的 Task #539 已在新 Bundle 216 上关闭 Codex 的真实
Provider/adapter/占位/Canonical/TaskLog/finalization 子项，固定 8 行技术 evidence 也已形成预期结果。
R4-RC1 仍保持开放，仅因为 R4.2 candidate identity、R4.3/R4.4 正式签署和 R4.5 owner closure 尚未完成；
后续不追加普通长思考 smoke。

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
