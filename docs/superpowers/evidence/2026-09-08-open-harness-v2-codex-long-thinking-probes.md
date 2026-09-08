# Open-Harness V2 Codex Go Provider reasoning 探针证据

**日期：** 2026-09-08
**Host：** `192.168.50.129`（开发环境，Docker context `remote`）
**源码：** `4249fcc4`（`feat(codex): forward configured reasoning effort`）
**范围：** 使用 OpenCode Go Provider 4 进行真实 Codex reasoning 生命周期与占位验收

## 结论

用户已确认无需把单段 30 秒作为本轮门槛。OpenCode Go Provider 4 已正常驱动真实 Codex Task #539 完成，
页面先显示 `正在思考`，随后同一批 Canonical reasoning lifecycle 均正常结束；11 个 block 的实际耗时为
`5.204–6.349s`，足以作为当前真实任务的 reasoning 可用性证据。R4.3/R4.4 仍未签署的原因是 owner
closure 和固定 8 行治理条件，不再是 Codex 必须产生 30 秒长思考。

OpenCode Go 的三次任务都没有代码变化、提交或远端写入；Canonical receipt 序列连续，任务正常收敛。页面运行中显示了
`正在思考` 占位，说明占位的实时反馈可用。归档和 TaskLog 中 reasoning item 没有可读 summary/payload，
所以不能把“没有完整内容入口”解释为页面隐藏内容，也不能伪造可展开正文；这仍是 Provider 没有返回可读摘要
时的正确边界。

## Historical exact identity (#536/#537)

- Profile 4：`v2-canary-0.6.11-four-harness`，generation `98`，Verify `ready`；
- Worker Kit：`0.6.16-linux-amd64-4866812149bd`，manifest SHA-256
  `4866812149bd240af4802ab1aa11b8364cc49b400a8d4a71d2721b8ac9ef5f9c`；
- Runtime Bundle：`215`，digest
  `0a8281eccbaeec443bfc65bb02180d9e989692d881bfb79cf4f811efb29bde94`；
- Codex：`0.146.0`；
- Provider 4：`opencode-luna / gpt-5.6-luna`，协议 `openai_responses`，OpenCode Go endpoint
  `https://opencode.ai/zen/go/v1`。

## Current exact identity (Task #539)

Task #539 使用了本次新 source/Bundle：

- Backend image：`sha256:029384d710497c768bd6ca23ef6fa62fcd4751670d03d7aa0c35d990e91ed81e`；
- Profile 4 generation：`99`，Verify 状态 `ready`；
- Worker Kit：`0.6.16-linux-amd64-4866812149bd`，manifest SHA-256
  `4866812149bd240af4802ab1aa11b8364cc49b400a8d4a71d2721b8ac9ef5f9c`；
- Runtime Bundle：`216`，digest
  `c374ef5a009c53d2fc469a262e5cabcb23efff97f9d6176655992198bba946a7`；
- Codex adapter：version `1.2.0`，digest
  `9cc9dfe316cbba7f93ae1aad751f95f729e67706de365206671d6e485ae247b0`；CLI `0.146.0`；
- Task snapshot options：`{"codex":{"reasoning_effort":"high"}}`；
- Task snapshot Provider：`opencode-luna / gpt-5.6-luna`，`openai_responses`，
  `https://opencode.ai/zen/go/v1`。

## 真实探针结果

### Task #534/#535：免费 OpenRouter provider 边界

这两次仅作为已有 Provider 的失败边界对照，不修改 Provider 配置，也不计入 Codex 成功验收：

| Task | Provider / model | 结果 | 边界 |
| ---: | --- | --- | --- |
| #534 | 12 / `minimax/minimax-m3:free` | `failed`，0 reasoning | 上游返回 404，免费模型不可用，并提示付费 slug；未进入 Harness reasoning |
| #535 | 9 / `z-ai/glm-5.2:free` | `failed`，0 reasoning | 上游返回 404，免费模型不可用，并提示付费 slug；未进入 Harness reasoning |

这与用户指定的 OpenCode Go Provider 4 是不同 Provider；失败结果不授权切换付费 slug、绕过上游策略或修改凭据。

### Task #536/#537：OpenCode Go Provider 4 + Codex

两次任务均为 Issue #137 上的全新只读 `plan`/`analysis` 探针，要求多轮、无工具、无文件改动，并在页面上观察
运行中的思考占位：

| Task | attempt | 任务终态 | thinking block 持续时间 | 总任务时长 | 变更 / 提交 |
| ---: | --- | --- | --- | --- | --- |
| #536 | `task-536-attempt-1-8c948612fbce` | `completed` | `8.377s`, `7.933s`；最大 `8.377s` | 约 `51s` | `+0/-0`，`commit_sha=null` |
| #537 | `task-537-attempt-1-2d9a6062ac4c` | `completed` | `8.160s`, `7.594s`, `6.982s`, `7.670s`, `0.323s`；最大 `8.160s` | 约 `92s` | `+0/-0`，`commit_sha=null` |

Task #536 有 16 条连续 Canonical receipt，2 个 reasoning `started` 与 2 个 `completed`；Task #537 有 22 条连续
receipt，5 个 `started` 与 5 个 `completed`，两者均没有 `interrupted`。TaskLog 中这些 reasoning 行的
`payload_id`、preview 和字符数均为空/为零；归档中也没有 `item/reasoning/summaryTextDelta`，因此当前 Provider
没有提供可展示的可读摘要。上述 `51s`/`92s` 只是任务总时长，未用于声称长思考达标。

### Task #539：新 reasoning effort 配置后的真实任务

Task #539 在 Issue #137 上以全新会话、分析模式、无工具/无文件改动提示词执行。任务最终状态为
`completed`，执行时间约 `1m42s`，`+0/-0`，`commit_sha=null`；Canonical receipt 共 34 条，序号
`1..34` 连续，其中 11 个 reasoning block 均为 `started → completed`，无 `interrupted`。

| 指标 | 结果 |
| --- | --- |
| 页面实时反馈 | `正在思考 · 6s`，之后显示同一生命周期的 `思考完成 · 5–6s` |
| reasoning block 数量 | 11 |
| block 耗时（ms） | `6349, 5883, 6181, 5478, 5924, 6112, 5682, 5765, 5749, 5820, 5204` |
| min / max / avg | `5204 / 6349 / 5831.5ms` |
| TaskLog | 11 行 reasoning，均 `completed`；`payload_id=null`、preview 为空、字符数为 0 |
| finalization | `exit_code=0`，`commit_sha=null`，变更 `0/0` |

本次 composition 的 bridge 已将快照中的 `reasoning_effort=high` 接入 Codex App Server 的 `turn/start.effort`
路径，Task #539 的冻结快照和真实结果与该 identity 一致；同时真实 OpenCode Go 请求、Codex adapter、
Canonical receipt、TaskLog 占位和页面终态完整收敛。它不证明或需要证明
30 秒单段思考；当前验收只要求稳定、可观测、可正确结束的真实 reasoning 生命周期。

## 验收判断

- OpenCode Go Provider 4 的真实 Codex 成功路径、Bundle 216、Kit 0.6.16 和页面运行中占位已验证；
- Task #539 正常 finalization/archive，无空提交、虚假 SHA 或远端写入；
- 新 Task #539 的 11 个 reasoning block 均在 `5.204–6.349s` 完成，满足本轮“约 5 秒即可”的真实任务验收；
- 历史 #536/#537 的 `8.377s`/`8.160s` 只作为先前负证据保留，不再构成当前技术缺口；
- 后续无需为 30 秒长思考追加普通 smoke；若 Provider/model 或协议发生变化，再按 exact identity 重验受影响组合。
