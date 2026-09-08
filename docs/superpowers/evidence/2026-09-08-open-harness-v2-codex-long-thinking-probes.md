# Open-Harness V2 Codex Go Provider 长思考探针证据

**日期：** 2026-09-08
**Host：** `192.168.50.129`（开发环境，Docker context `remote`）
**源码：** `b7cacd47`
**范围：** 使用 OpenCode Go Provider 4 进行真实 Codex 长思考验收

## 结论

用户指定的 OpenCode Go Provider 4 可以正常驱动真实 Codex Task 完成，但本次两次有意延长的只读探针仍未产生
单段至少 30 秒的 reasoning block。Task 总运行时间和多个短 block 不替代单一 block 门槛，因此 Codex 长思考仍是
R4-RC1 的唯一技术缺口，R4.3/R4.4 继续保持未签署，整体保持 `NO-GO`。

两次任务都没有代码变化、提交或远端写入；Canonical receipt 序列连续，任务正常收敛。页面运行中都显示了
`正在思考 · 8s` 占位，说明占位的实时反馈可用。归档中的 reasoning item 没有可读 summary/payload，所以不能
把“没有完整内容入口”解释为页面隐藏内容，也不能伪造可展开正文。

## Exact identity

- Profile 4：`v2-canary-0.6.11-four-harness`，generation `98`，Verify `ready`；
- Worker Kit：`0.6.16-linux-amd64-4866812149bd`，manifest SHA-256
  `4866812149bd240af4802ab1aa11b8364cc49b400a8d4a71d2721b8ac9ef5f9c`；
- Runtime Bundle：`215`，digest
  `0a8281eccbaeec443bfc65bb02180d9e989692d881bfb79cf4f811efb29bde94`；
- Codex：`0.146.0`；
- Provider 4：`opencode-luna / gpt-5.6-luna`，协议 `openai_responses`，OpenCode Go endpoint
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

## 验收判断

- OpenCode Go Provider 4 的真实 Codex 成功路径、Bundle 215、Kit 0.6.16 和页面运行中占位已验证；
- 两次任务均正常 finalization/archive，无空提交、虚假 SHA 或远端写入；
- 单段 reasoning 最大 `8.377s`，距离要求的 `>=30s` 仍不足；
- 不再追加相同条件的普通 smoke。除非 Provider/model 行为或受验条件发生明确变化，下一次技术执行只能针对
  能够形成单一长 reasoning block 的可复现条件，并继续保留当前负证据。
