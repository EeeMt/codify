# Open-Harness V2 思考详情回归修正证据

**日期：** 2026-09-08  
**Host：** `192.168.50.129`（开发环境，Docker context `remote`）  
**源码：** `b7cacd47`  
**范围：** 思考占位优化后的正文预览/“完整内容”入口，以及 Codex explicit reasoning summary 边界

## 结论

思考占位现在只负责显示生命周期状态和耗时。只要 Canonical 事件已有 `payload_id`、内联正文或已加载正文，
`TaskProcessTextRow` 保留预览和“完整内容”按钮；真正没有正文的空占位不显示全文入口。

Codex 只投影 Provider 明确提供的可读 `summary_text`（完成项 `summary` 或流式
`item/reasoning/summaryTextDelta`）。原始 reasoning `content`/`textDelta` 仍不作为页面正文，避免把隐藏内容
误当成用户可见的思考摘要。

## 源码与测试

提交 `b7cacd47` 包含：

- 前端正文入口按“是否有显式内容”决定，不再按生命周期状态隐藏已有正文；
- Codex App Server summary 完成项与 summary delta 的安全投影；
- 前端回归测试和 Codex adapter fixture，验证正文可展开且原始隐藏内容不进入 Canonical payload；
- 思考占位方案文档同步更新。

通过的验证：

- `backend/.venv/bin/python -m pytest backend/tests/unit/test_codex_harness_adapter.py`：37 passed；
- `cd frontend && npx vitest run src/components/task-process/TaskProcessTextRow.spec.ts`：11 passed；
- `cd frontend && npm run build`：通过（`vue-tsc` + Vite，3499 modules）；
- `git diff --check`：通过。

## 开发 Host 安装身份

- Profile 4：`v2-canary-0.6.11-four-harness`，generation `98`，Verify `ready`；
- Kit：`0.6.16-linux-amd64-4866812149bd`；
- Kit path：`/home/codify/worker-kits/0.6.16-linux-amd64-4866812149bd`；
- manifest SHA-256：`4866812149bd240af4802ab1aa11b8364cc49b400a8d4a71d2721b8ac9ef5f9c`；
- archive SHA-256：`ba03a4ff3273e6e5af456044c57193ab576cf5e92c5e0bc25da1689dce29f7c0`；
- Kit inventory：Pi `0.84.2`、OpenCode `1.18.19`、Claude `2.1.153`、Codex `0.146.0`，四项均 `present`；
- nginx image：`sha256:aa09c11639f0f5838c085006c0690344f32536c1dcbd91dda37681cd6e253f2`，`linux/amd64`；
- `http://192.168.50.129:8880/`：HTTP 200。

远端 Kit 构建期间根盘空间不足，Kit 改在本机支持 `linux/amd64` 的 Docker Builder 完成后传输，
再安装到远端独立 `/home` 分区；只清理了明确的失败 Builder 缓存和临时 Kit 归档，没有删除已有 Profile
使用中的 `/opt/codify/worker-kits`、volume 或运行中服务。

## 真实任务边界

### Task #526：已有正文可以展开

Task #526 是已有 Pi 长思考任务，数据库中有 3 条 thinking log，均带 `payload_id`；最大正文
`char_count=33447`。在部署 `b7cacd47` 的页面
`http://192.168.50.129:8880/tasks/526` 中，3 条“思考完成”事件均显示“完整内容”；点击第一条后，
正文在页面内正常展开。该浏览器证据确认占位优化没有隐藏已经投影的思考正文。

### Task #533：Codex Provider 没有提供可读正文

为验证新 Kit 创建了 Issue #137 的只读 Codex `plan` Task #533：

- Provider 4：`opencode-luna / gpt-5.6-luna`，协议 `openai_responses`；
- Harness：Codex `0.146.0`，CLI digest
  `2e863156ed35ecc5253b1e2f907a9143077b9f7cb51942070c61996471ff6e04`；
- Worker Kit：`0.6.16-linux-amd64-4866812149bd`；
- Runtime Bundle：215，digest
  `0a8281eccbaeec443bfc65bb02180d9e989692d881bfb79cf4f811efb29bde94`；
- 任务结果：`completed`，`+0/-0`，没有提交或工作区变更。

Task #533 的 archive `harness-events/codex.jsonl` 中每个 reasoning item 都是空的
`summary`/`content`，没有 `item/reasoning/summaryTextDelta`。因此 TaskLog 的 thinking 记录为
`payload_id=null`、`preview=""` 是 Provider 没有发送可读 summary 的真实结果，不是前端按钮被隐藏。
该任务同时证明新 Kit、真实 Provider 和 Codex App Server transport 可以正常完成。

### Task #539：当前 OpenCode Go/Codex 页面与无变更提交边界

当前 Bundle 216 的 Task #539 在浏览器中显示 11 条 `思考完成 · 耗时 5–6s`；由于同样没有可读
`summary`/payload，页面只保留状态和耗时，不伪造“完整内容”入口。该任务的结果页没有“提交记录”卡或
commit SHA，和 `+0/-0`、`commit_sha=null` 的 API/TaskLog 结果一致。它不再要求单段 30 秒思考，稳定的
5–6 秒 reasoning 生命周期即为本轮验收口径。

## 边界与后续

本证据关闭“已有正文因占位优化而不可展开”的 UI 回归；不把 Codex Provider 当前没有发送 summary
误报为“Codex 正文已展示”。当前 Task #539 进一步确认了无正文时的状态-only 与无变更提交展示边界。
若要让该 Provider 出现可展开 Codex 摘要，必须先观察到上游提供
`summary_text` 或 `summaryTextDelta`，再用同一 immutable identity 补真实页面证据。
