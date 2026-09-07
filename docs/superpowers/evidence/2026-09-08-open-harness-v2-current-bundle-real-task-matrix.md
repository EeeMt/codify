# Open-Harness V2 当前 Bundle 真实 Task 矩阵证据

**复核日期：** 2026-09-08
**Host：** `192.168.50.129`（开发环境，Docker context `remote`）
**结论：** 真实 reasoning 与部分 Git delivery 已验证；R4.3/R4.4 仍未签署，整体保持 `NO-GO`

本记录补充 [Codex App Server bridge evidence](2026-09-08-open-harness-v2-codex-app-server-bridge.md)，
记录历史 source/Kit composition 下的 Pi、OpenCode、Claude 真实任务，以及 Pi OpenAI endpoint
修复后新 Bundle 的真实回归。事件来自远端 `task_harness_event_receipts`，raw/archive 只记录元数据，
不复制原始内容。历史 Bundle 保持不可变，修复后的 Task 使用独立 Bundle 201/202；#482/#483
又在这两个当前 Bundle 上复核了 `openai_responses` 的真实 Provider 失败边界。

## 1. Exact composition

| 项 | 当前值 |
| --- | --- |
| Source anchor（当前未推送本地候选） | `ae223cb18c67e1189cbba909892e585cbbd1fcac` |
| Profile | `4 / v2-canary-0.6.11-four-harness` |
| Worker Kit | `0.6.15 / 506dbc2c61fbc03144c45fdffcd9a0e264781fe4038ad0ed13b38112580b831b` |
| Backend image（Pi endpoint 修复后） | `sha256:87cc35d940d97ef2c82ef9f6f00d2f8cc7feddb01e7d8c74ee6aac37326a10d1` |
| NGINX image | `sha256:ba50f6296e92e426dd445740d7214c6c54aaddd2a79d58d1513a4741379c6e43` |
| Worker image | `127.0.0.1:5000/codify-worker/java21-maven@sha256:234582c692d1ebb00ba8e882160618c2258463149d968009ac81c545e63a538b` |
| Profile 4 Verify | generation `92`，四 Harness evidence keys 均存在，状态“已就绪” |

任务创建时产生的 Bundle 是不可变、任务快照绑定的同组成实例；本轮使用的 Bundle 及 digest 为：

| Bundle | Harness | Runtime Bundle digest |
| ---: | --- | --- |
| 198 | Pi（修复前历史） | `a0b036a1f698c3f3ad41cc3fdfd0b467eb0da2a6138754cb2df74d2045c33ec0` |
| 199 | OpenCode | `ac62176c7d341ab59f97a68cf58f49883e8ae29b91866d7e729c88fda1a03ea6` |
| 200 | Claude | `e77660b1253779c3e5402b6140a4d54822cb96118cfe870887742fe3030c06ea` |
| 201 | Pi（`ae223cb1` 修复后） | `d2e9acdddcb3470e39d3c65eb45176462022154584ab54eef701311e4b173dfa` |
| 202 | OpenCode（同一 Kit/Backend composition） | `415d0ba667afb4e6b81a7e9ab919e2a25104da5d7115df38ea8bdfaf4f230226` |

上述 manifest 均保留四 Harness；实际 Task snapshot 分别绑定对应 Harness 的 adapter/CLI：
Pi `2.1.1/0.84.2`、OpenCode `2.1.0/1.18.19`、Claude `1.1.0/2.1.153`。Bundle 201 的 Pi
adapter digest 为 `d326e5c4f0bc2eedcbc4d835ef17c804d1b07b959be5a6af9384309d50249c3d`；修复前
Bundle 198 为 `e619b8464d7b1c6fee08661eb1e2dd3a87da58065f10dc9166d749403a836356`。
Backend 仅重建/重启 Backend 与 Scheduler；NGINX 保持原 immutable image。

## 2. Real Task matrix

| Task | Harness / Provider / model | Bundle | 终态与 reasoning | Delivery / 结论 |
| ---: | --- | ---: | --- | --- |
| #464 | Pi / 6 / `deepseek-v4-flash` | 198 | cancelled；27/27 reasoning，取消时无活动 reasoning block | 工具诊断持续增长后安全取消；0 changes，不能计入 interrupted thinking |
| #465 | OpenCode / 6 / `deepseek-v4-flash` | 199 | completed；1/1 reasoning，`run.completed` | 0 changes；正常完成 |
| #466 | Claude / 3 / `minimax-m2.7` | 200 | completed；1/1 reasoning，`run.completed` | 0 changes；正常完成 |
| #467 | Pi / 3 / `minimax-m2.7` | 198 | completed；1/1 reasoning，`run.completed` | 0 changes；正常完成 |
| #468 | Pi / 3 / `minimax-m2.7` | 198 | completed；6/6 reasoning，`run.completed` | 两次未推送提交由 Worker 推送；`remote_sha=3e6f910f19de1f24c31134219f433019b8ac7f88`，MR !99 |
| #469 | OpenCode / 3 / `minimax-m2.7` | 199 | completed；9/9 reasoning，`run.completed` | 两次 harness commit + dirty file 被 Worker 合并交付；`remote_sha=49c80a78fec43bba1fd9d8627b6d4427784b7a83`，MR !100 |
| #470 | Pi / 5 / `mimo-v2.5` | 198 | failed；Provider HTTP 404 HTML，0 reasoning | `openai_chat_completions` 真实 Provider 边界；未改配置、0 changes |
| #471 | Claude / 3 / `minimax-m2.7` | 200 | completed；7/7 reasoning，`run.completed` | Worker 推送一条提交；`remote_sha=305bf29f8221cd4b689f7a43a02077f85a80d310`，MR !101 |
| #472 | Pi / 6 / `deepseek-v4-flash` | 198 | cancelled；7/7 reasoning，取消发生在后续工具/诊断期间 | 页面运行中捕获“正在思考 · 1s”后同一行完成；随后有界取消；0 changes |
| #473 | OpenCode / 3 / `minimax-m2.7` | 199 | completed；2/2 reasoning，`run.completed` | 0 changes；真实响应与终态正常，但页面采集落在完成后，不能计入运行中时序 |
| #474 | Claude / 3 / `minimax-m2.7` | 200 | completed；4/4 reasoning，`run.completed` | 页面运行中捕获“正在思考 · 3s”后同一行完成；0 changes |
| #475 | OpenCode / 5 / `mimo-v2.5` | 199 | completed；3/3 reasoning，`run.completed` | 页面运行中捕获思考占位后同一行完成；0 changes；Chat 正常成功路径 |
| #476 | Pi / 5 / `mimo-v2.5` | 198 | failed；Provider HTTP 404 HTML，0 reasoning | 修复前 Bundle 的真实失败边界；`openai_chat_completions`，0 changes |
| #477 | Pi / 5 / `mimo-v2.5` | 201 | completed；24/24 reasoning，`run.completed` | 修复后 Chat 正常成功；页面捕获“正在思考”及同一行完成；0 changes |
| #478 | Pi / 5 / `mimo-v2.5` | 201 | cancelled；6 started / 5 canonical completed，`run.failed` | 页面在活动思考时取消并刷新；TaskLog 终态兜底为 5 completed + 1 interrupted，但无 canonical `reasoning_summary.interrupted`；0 changes |
| #479 | OpenCode / 5 / `mimo-v2.5` | 202 | completed；4/4 reasoning，`run.completed` | 当前 Bundle 正常 Chat 回归；页面观察未抓到活动思考或取消；0 changes |
| #480 | OpenCode / 5 / `mimo-v2.5` | 202 | completed；2/2 reasoning，`run.completed` | 第二次取消探针自然完成；未发生取消，不能计入 OpenCode Chat 取消/刷新验收；0 changes |
| #481 | OpenCode / 5 / `mimo-v2.5` | 202 | cancelled；2/2 reasoning，`run.failed` | 取消请求晚于第二段 reasoning 完成约 7.3s，实际发生在工具/诊断阶段；刷新终态稳定，不能计入活动思考取消；0 changes |
| #482 | OpenCode / 9 / `z-ai/glm-5.2:free` | 202 | failed；0 reasoning，`run.failed` | `openai_responses` 返回 404：免费模型需使用付费 slug；attempt 正常关闭，0 changes |
| #483 | Pi / 12 / `minimax/minimax-m3:free` | 201 | failed；0 reasoning，`run.failed` | `openai_responses` 返回 404：免费模型需使用付费 slug；attempt 正常关闭，0 changes |

上述 Task 的 attempt 均为 `codify.worker.event/v2`，transport 与 adapter identity 来自真实
`run.started` receipt，而非手工 fixture。#468/#469/#471 的 `worker.finalization` 均报告
`push.status=pushed`、精确 `remote_sha` 和 branch，故这些 delivery 不是 artifact metadata 或
平铺 SHA 推断。

## 3. Raw/archive 结构摘要

| Task | raw chunks / bytes | archive | terminal |
| ---: | ---: | ---: | --- |
| #464 | 3 / 5,700 | 342,878 bytes | `run.failed` / cancelled |
| #465 | 5 / 2,490 | 74,864 bytes | `run.completed` |
| #466 | 8 / 8,694 | 6,514 bytes | `run.completed` |
| #467 | 4 / 2,489 | 6,566 bytes | `run.completed` |
| #468 | 6 / 3,640 | 14,111 bytes | `run.completed` |
| #469 | 6 / 4,725 | 23,701 bytes | `run.completed` |
| #470 | 3 / 2,204 | 5,460 bytes | `run.failed` |
| #471 | 13 / 16,732 | 13,020 bytes | `run.completed` |
| #472 | 4 / 5,844 | 79,564 bytes | `run.failed` / cancelled |
| #473 | 5 / 2,882 | 9,647 bytes | `run.completed` |
| #474 | 10 / 13,959 | 16,191 bytes | `run.completed` |
| #475 | 5 / 2,849 | 19,579 bytes | `run.completed` |
| #476 | 3 / 2,553 | 5,649 bytes | `run.failed` |
| #477 | 4 / 2,837 | 140,940 bytes | `run.completed` |
| #478 | 3 / 5,767 | 29,548 bytes | `run.failed` / cancelled |
| #479 | 6 / 2,878 | 21,045 bytes | `run.completed` |
| #480 | 5 / 2,878 | 20,339 bytes | `run.completed` |
| #481 | 4 / 2,627 | 16,830 bytes | `run.failed` / cancelled |
| #482 | 5 / 2,612 | 5,003 bytes | `run.failed` |
| #483 | 3 / 2,616 | 3,752 bytes | `run.failed` |

所有任务结束后，相关 Worker 容器均已清理；Backend/Scheduler 保持健康。#472 的 attempt 为
`task-472-attempt-1-9ef92102943b`，`codify.worker.event/v2`、Pi adapter `2.1.1`、CLI
`0.84.2`，共 7 个 `reasoning_summary.started` 与 7 个 `reasoning_summary.completed`，
另有 13 个 tool start、12 个 tool completion；取消终态为 `run.failed`，没有
`reasoning_summary.interrupted`。任务绑定 Bundle 198（digest `a0b036a1f698c3f3ad41cc3fdfd0b467eb0da2a6138754cb2df74d2045c33ec0`）。

#473 的 attempt 为 `task-473-attempt-1-98753286cb17`，`codify.worker.event/v2`、OpenCode
adapter `2.1.0`、CLI `1.18.19`，2 个 reasoning start/end、1 个工具调用，终态为
`run.completed`；任务绑定 Bundle 199（digest `ac62176c7d341ab59f97a68cf58f49883e8ae29b91866d7e729c88fda1a03ea6`）。

#474 的 attempt 为 `task-474-attempt-1-bf4d82ed037d`，`codify.worker.event/v2`、Claude
adapter `1.1.0`、CLI `2.1.153`，4 个 reasoning start/end、5 个工具调用，终态为
`run.completed`；任务绑定 Bundle 200（digest `e77660b1253779c3e5402b6140a4d54822cb96118cfe870887742fe3030c06ea`）。

本轮远端根盘曾达 99%（约 793 MB 可用）；确认活动容器、服务镜像和 volume 后，仅回收超过
1 小时的 Codify BuildKit 调试缓存 1.78 GB，未删除 active/unknown image、服务或 volume。
清理后根盘约 93%（4.6 GB 可用），Backend/Scheduler/NGINX 及 `quirky_allen` 保持运行。

已通过真实 Codify 页面检查 Task #471：
`http://192.168.50.129:8880/tasks/471` 显示 Completed、Claude、MR !101、远端提交短 SHA
`305bf29f`、`+1/-0` 和 7 条已完成思考行。该页面是终态页面，证明 UI 能投影当前 canonical
结果，但不单独证明任务运行中占位先于完成；实时页面时序仍保持未验收。

另在真实运行中检查 Task #472：
`http://192.168.50.129:8880/tasks/472` 在开始后约 7 秒显示 `执行中`、`事件流 0 1 0`、
`deepseek-v4-flash` 容器以及 `正在思考 · 1s`；随后同一页面在仍为 `执行中` 时显示同一思考行
`思考完成 · 耗时 1s`，并继续显示工具输入/输出和增长中的事件流。取消并刷新后页面显示
`已取消`、完成时间 `2026/09/08 03:46:50`，7 条思考行均保持完成。该证据关闭了 Pi 的
“运行中开始占位先于完成”页面子项，但不是四 Harness 全覆盖，也不是思考期间取消/中断证据。

Task #473 的真实页面最终显示 `已完成`、OpenCode、2 条已完成思考行和 `+0/-0`；本次首次完整
页面观察已在 `run.completed` 之后，因此只作为 OpenCode 的终态 UI 投影证据，不关闭运行中
占位时序子项。

Task #474 的真实页面在仍为 `执行中` 时显示 `事件流 1 3 1`、Claude 容器和
`正在思考 · 3s`；下一次页面更新显示同一行 `思考完成 · 耗时 1s`，随后终态为 `已完成`、
`+0/-0`。该证据关闭了 Claude 的运行中页面时序子项，但不构成 30 秒长思考或思考期间取消证据。

Task #475 的 attempt 为 `task-475-attempt-1-310cd0abd24b`，OpenCode adapter `2.1.0`、CLI
`1.18.19`，`last_seq=119`，3 个 reasoning start/end、2 个工具调用，终态为 `run.completed`；
运行中页面先显示思考占位，随后显示完成行。任务绑定 Bundle 199，raw 为 5 chunks / 2,849
bytes，archive 为 19,579 bytes。该任务关闭 OpenCode Chat 的正常成功与页面时序子项，但不是
思考期间取消证据。

Task #476 的 attempt 为 `task-476-attempt-1-32b375ff0209`，Pi adapter `2.1.1`、CLI `0.84.2`，
`last_seq=8`，终态为 `run.failed`；Provider 5 返回 404 HTML，未产生 reasoning。它绑定修复前
Bundle 198，raw 为 3 chunks / 2,553 bytes，archive 为 5,649 bytes。该失败证据保留为修复前
边界，不能与 Task #477 合并解释。

Task #477 的 attempt 为 `task-477-attempt-1-4d685b28d8e5`，`codify.worker.event/v2`、Pi
adapter `2.1.1`、CLI `0.84.2`，`last_seq=1579`，终态 `run.completed`、control `closed`。
Canonical Event 包含 24 个 `reasoning_summary.started`、24 个 `reasoning_summary.completed`、
70 对 tool start/completed、1 个 `worker.finalization`；TaskLog 同样记录 24 条 thinking 与
70 条 tool_call。任务绑定新 Bundle 201，raw 为 4 chunks / 2,837 bytes，archive 为 140,940
bytes，页面运行中先显示 `正在思考 · 4s`，随后持续出现完成行和工具事件，最终 `已完成`、
`+0/-0`。这证明 `ae223cb1` 的 Pi OpenAI endpoint root normalization 已在新 Bundle 上越过
原先的 HTTP 404 边界，但只覆盖正常成功路径。

Task #478 的 attempt 为 `task-478-attempt-1-785527b5c108`，`codify.worker.event/v2`、Pi
adapter `2.1.1`、CLI `0.84.2`，`last_seq=292`，终态 `run.failed`、control `closed`。真实页面
在任务仍为 `执行中` 时显示活动 `正在思考 · 2s`，随后点击取消；取消后刷新/重连页面稳定显示
`已取消`，没有悬挂计时。Canonical Event 有 6 个 `reasoning_summary.started`、5 个
`reasoning_summary.completed`，没有 `reasoning_summary.interrupted`；TaskLog 终态兜底保留
5 条 `completed` 和 1 条 `interrupted` thinking 记录。它证明了允许的进程终止/终态兜底路径和
用户态刷新恢复，但不伪称为 canonical interrupted receipt，也不满足 30 秒长思考。
任务绑定 Bundle 201，raw 为 3 chunks / 5,767 bytes，archive 为 29,548 bytes，0 changes。

Task #479 的 attempt 为 `task-479-attempt-1-a838dce068a6`，OpenCode adapter `2.1.0`、CLI
`1.18.19`，`last_seq=124`，4 个 reasoning start/end、4 个工具调用，终态为 `run.completed`；
任务绑定 Bundle 202（digest `415d0ba667afb4e6b81a7e9ab919e2a25104da5d7115df38ea8bdfaf4f230226`），
raw 为 6 chunks / 2,878 bytes，archive 为 21,045 bytes。它是当前 Bundle 的 OpenCode Chat
正常回归，但页面观察没有捕获活动思考行，不能计入取消或运行中时序。

Task #480 的 attempt 为 `task-480-attempt-1-a4a5824ee217`，OpenCode adapter `2.1.0`、CLI
`1.18.19`，`last_seq=107`，2 个 reasoning start/end、2 个工具调用，终态为 `run.completed`；
raw 为 5 chunks / 2,878 bytes，archive 为 20,339 bytes，0 changes。该任务用于再次寻找
OpenCode 活动思考取消窗口，但自然完成，未执行取消，因此不能关闭 OpenCode Chat 的取消/刷新
验收项。

Task #481 的 attempt 为 `task-481-attempt-1-6cef0bbbeab9`，OpenCode adapter `2.1.0`、CLI
`1.18.19`，`last_seq=54`，2 个 reasoning start/end，终态为 `run.failed`、control `closed`。
`cancel_requested_at=2026-09-07 21:01:42.955391`，而第二个 `reasoning_summary.completed` 为
`2026-09-07 21:01:35.615688`；取消实际落在后续 tool/diagnostic 阶段。页面随后刷新为稳定的
`已取消`，没有悬挂记录，但没有 `reasoning_summary.interrupted`，因此仍不能关闭 OpenCode
Chat 的活动思考取消/刷新验收项。任务绑定 Bundle 202，raw 为 4 chunks / 2,627 bytes，
archive 为 16,830 bytes，0 changes。

Task #482 的 attempt 为 `task-482-attempt-1-0ffce61f4284`，OpenCode adapter `2.1.0`、CLI
`1.18.19`，`last_seq=8`，终态为 `run.failed`、control `closed`。任务使用当前 Bundle 202
和 Provider 9 `openrouter-glm52-responses`；真实页面显示失败，远端错误为 OpenRouter 404，
明确提示 `z-ai/glm-5.2:free` 不可用且付费版本为 `z-ai/glm-5.2`，没有 reasoning receipt。
Canonical 仅有 `diagnostic` 3、`run.started`、`harness.failed`、`run.failed`、`usage.final` 和
`worker.finalization`，raw 为 5 chunks / 2,612 bytes，archive 为 5,003 bytes，0 changes。
不得在未获授权时把 Provider slug 改为付费版本；该任务证明当前 OpenCode Responses Provider
边界，而不是 OpenCode Adapter 生命周期完成。

Task #483 的 attempt 为 `task-483-attempt-1-372a15140d61`，Pi adapter `2.1.1`、CLI `0.84.2`，
`last_seq=9`，终态为 `run.failed`、control `closed`。任务使用当前修复后的 Bundle 201 和
Provider 12 `openrouter-minimax-responses`；真实页面显示失败，远端错误为 OpenRouter 404，
明确提示 `minimax/minimax-m3:free` 不可用且付费版本为 `minimax/minimax-m3`，没有 reasoning
receipt。Canonical 仅有 `agent_settled`、`diagnostic`、`harness.failed`、`model.resolved`、
`run.failed`、`run.started`、`usage.final`、`usage.updated` 和 `worker.finalization`，raw 为
3 chunks / 2,616 bytes，archive 为 3,752 bytes，0 changes。该任务确认 Pi 当前 Bundle 的
Responses 请求已越过 Worker 启动阶段，但被真实 Provider 在模型响应前拒绝；不能计入 Pi
Responses 的 reasoning 验收，也不能把付费 slug 当作现有 Provider 能力。

## 4. 验收边界

本轮关闭了以下当前 composition 的 L4 子项：

- Pi、OpenCode、Claude 均有真实 Provider 的 canonical reasoning start/end，且成功 Task 的
  start 发生在对应 completed 之前；
- Pi、OpenCode、Claude 各有真实 Worker Git delivery，且有 canonical `worker.finalization`
  的远端确认 SHA；OpenCode 的 dirty file 被纳入最终交付；
- Pi Task #472 有真实运行中页面时序：开始占位先于同一行完成，刷新后的取消终态不悬挂；
- Pi Task #478 补齐了活动思考期间取消与刷新/重连的用户态终态；该次使用了 TaskLog 终态兜底，
  没有 canonical `reasoning_summary.interrupted` receipt；
- Claude Task #474 有真实运行中页面时序：开始占位先于同一行完成，终态无代码变更；
- OpenCode Task #475 与 Pi Task #477 分别在 Bundle 199/201 上关闭了 Chat 正常成功和运行中
  页面时序子项；Pi #476/#470 的 404 仍作为修复前失败边界保留，没有改 Provider 配置或伪造成功。

仍未关闭：

- Codex 尚无真实模型响应，因此没有 App Server reasoning/空完成/取消/最终结果回归；付费
  slug 仍需明确授权；
- Pi/OpenCode 的 `openai_responses` 仍未完成：#482/#483 在当前 Bundle 202/201 上均由真实
  OpenRouter 免费模型 404 阻断，不能改用付费 slug 伪造能力；OpenCode Chat 的思考期间取消/
  刷新重连、Claude 受控远端 divergence、Codex 成功响应仍未完成。#478 的 Pi 取消已覆盖终态
  兜底，但没有 canonical interrupted receipt；#475/#477/#479/#480 是正常完成，#481 是思考完成
  后的取消，单个思考块耗时也很短，不能替代第 8 节长思考要求；
- R4.5 owner closure、R4.6 独立 GO/NO-GO 和 R5/L6 仍未执行。

因此本记录是当前 exact composition 的真实推进证据，不是四 Harness 8 行全部通过或 release
candidate 签署。
