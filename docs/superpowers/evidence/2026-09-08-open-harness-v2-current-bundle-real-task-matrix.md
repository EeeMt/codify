# Open-Harness V2 当前 Bundle 真实 Task 矩阵证据

**复核日期：** 2026-09-08
**Host：** `192.168.50.129`（开发环境，Docker context `remote`）
**结论：** Codex 真实模型响应/reasoning/正常 Git delivery、零变化 delivery、取消/刷新终态、OpenCode 活动 reasoning canonical interrupted，以及当前 Bundle 的 OpenCode `openai_responses` durable lifecycle 已验证；Worker 仓库前置失败的 canonical terminal 也已补齐。Pi `openai_responses` 在同一 Provider 上仍以真实 401/活动 tool fail-closed 边界失败，不能计入成功行。R4.3/R4.4 仍未签署，整体保持 `NO-GO`

本记录补充 [Codex App Server bridge evidence](2026-09-08-open-harness-v2-codex-app-server-bridge.md)，
记录历史 source/Kit composition 下的 Pi、OpenCode、Claude 真实任务，以及 Pi OpenAI endpoint
与 Worker finalization、OpenCode native abort drain 修复后新 Bundle 的真实回归。事件来自远端
`task_harness_event_receipts`，raw/archive 只记录元数据，不复制原始内容。历史 Bundle 保持不可变，
修复后的 Task 使用独立 Bundle 201/202/203/204/205/206/207/208/209/210；#482/#483/#484 又在当前 Bundle 上复核了
`openai_responses` 的真实 Provider 失败边界，#485–#488 补齐了 Claude 的正常交付与受控远端
分叉保护，#490–#498 复核了 OpenCode finalization、native abort、archive 和 cancelled terminal
收敛边界，#499–#503 在新 Bundle 上完成正常完成、工具阶段取消和活动 reasoning canonical
interrupted 回归；#504–#505 在 Bundle 206 上补充了受控远端分叉前置失败和 Claude 长运行探针。
#508 在 Bundle 207 上补齐了 Codex App Server 的真实成功响应、两段 reasoning 与 Git delivery；
#510 在新的 Bundle 208 上验证了仓库准备早于 Harness 失败时仍能生成完整 V2 canonical terminal；
#511 在同一 Bundle 208 上补齐了 Codex 零变化成功、无空提交与无远端虚假 SHA 的真实边界；
#512 作为同一 Provider 的长运行取消探针，证明总运行时间不能替代长 reasoning 或活动取消证据；#513 在 Bundle 209
验证了 OpenCode `openai_responses` 的真实成功生命周期；#514 在 Bundle 210 复核 Pi `openai_responses`，
保留了上游 401 与活动 tool 的 fail-closed 终态，未伪造成功；#515 在 Bundle 208 上补齐 Codex
运行中取消、页面刷新后的 `已取消` 终态、canonical failure/finalization/archive 和容器清理。

## 1. Exact composition

| 项 | 当前值 |
| --- | --- |
| Source anchor（当前未推送本地候选） | `6835e43ce855564f5c825c91c58ff2ee718637c9` |
| Profile | `4 / v2-canary-0.6.11-four-harness` |
| Worker Kit | `0.6.15 / 506dbc2c61fbc03144c45fdffcd9a0e264781fe4038ad0ed13b38112580b831b` |
| Backend image（pre-Harness finalizer 修复后） | `sha256:9c24e529fcd2238d57be93a359ab79a5f4868ed4143f09852c88c92406bba510` |
| NGINX image | `sha256:ba50f6296e92e426dd445740d7214c6c54aaddd2a79d58d1513a4741379c6e43` |
| Worker image | `127.0.0.1:5000/codify-worker/java21-maven@sha256:234582c692d1ebb00ba8e882160618c2258463149d968009ac81c545e63a538b` |
| Profile 4 Verify | generation `95`，四 Harness evidence keys 均存在，状态“已就绪” |

任务创建时产生的 Bundle 是不可变、任务快照绑定的同组成实例；本轮使用的 Bundle 及 digest 为：

| Bundle | Harness | Runtime Bundle digest |
| ---: | --- | --- |
| 198 | Pi（修复前历史） | `a0b036a1f698c3f3ad41cc3fdfd0b467eb0da2a6138754cb2df74d2045c33ec0` |
| 199 | OpenCode | `ac62176c7d341ab59f97a68cf58f49883e8ae29b91866d7e729c88fda1a03ea6` |
| 200 | Claude | `e77660b1253779c3e5402b6140a4d54822cb96118cfe870887742fe3030c06ea` |
| 201 | Pi（`ae223cb1` 修复后） | `d2e9acdddcb3470e39d3c65eb45176462022154584ab54eef701311e4b173dfa` |
| 202 | OpenCode（同一 Kit/Backend composition） | `415d0ba667afb4e6b81a7e9ab919e2a25104da5d7115df38ea8bdfaf4f230226` |
| 203 | Claude（同一 Kit/Backend composition） | `4f22bb5db5e00fdbab820c4d1a5ada8da212555049b7a26c27730d88430a167e` |
| 204 | OpenCode（finalization drain 修复后） | `10cfd1acfb5674f14fdc0586a3b84da0be99f6dc28b75fea51e2f8d531260f3b` |
| 205 | OpenCode（native abort drain 修复后） | `a9992043629103ef544de7250d1817e14cfd5f61653f17a4feab57176c38a2c9` |
| 206 | Claude（#504/#505；同一当前 composition） | `921d7b53676eb61f4b8c1301802392e8791fe1d912cfddecd1381caddd28dffc` |
| 207 | Codex（#508；Profile 4 generation 94） | `6dca863dcb69e26bd6ce9db082e7fd5d1827fdfa6b46027322cb8524fd2bda35` |
| 208 | Codex（#510/#511/#512/#515；pre-Harness finalizer 修复后） | `96341e488faa37bd081169a3c69a91504fbbaa2efa89f0ce890eb2e55114adc7` |
| 209 | OpenCode（#513；当前 Profile 4 generation 95） | `1788f343846af0ea05de39a45276640e49d92f62a990fdd30b2c571416f6a91c` |
| 210 | Pi（#514；当前 Profile 4 generation 95） | `9d206d5c90fb8ddbdb850f92e19976b46e749fb0ab736ccb1ccf23ed71806030` |

上述 manifest 均保留四 Harness；实际 Task snapshot 分别绑定对应 Harness 的 adapter/CLI：
Pi `2.1.1/0.84.2`、OpenCode `2.1.0/1.18.19`、Claude `1.1.0/2.1.153`、Codex `1.2.0/0.146.0`。Bundle 201 的 Pi
adapter digest 为 `d326e5c4f0bc2eedcbc4d835ef17c804d1b07b959be5a6af9384309d50249c3d`；修复前
Bundle 198 为 `e619b8464d7b1c6fee08661eb1e2dd3a87da58065f10dc9166d749403a836356`。
Backend 仅重建/重启 Backend 与 Scheduler；NGINX 保持原 immutable image。部署修复后重新 Verify
Profile 4 生成 generation `95`，以刷新与新 Runtime source 一致的四 Harness evidence；历史
Bundle 207 及更早 Bundle 保持不可变。

Bundle 206 的 `size_bytes=655360`；数据库中的四 Harness manifest 与 Bundle 205 完全一致，
因此把 206 记录为 #504/#505 的当前任务快照 identity，不把它误计为新的 Adapter source 修复。

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
| #484 | OpenCode / 4 / `gpt-5.6-luna` | 202 | failed；0 reasoning，`run.failed` | `openai_responses` 返回 403：地区不支持；attempt 正常关闭，0 changes |
| #485 | Claude / 3 / `minimax-m2.7` | 203 | completed；5/5 reasoning，`run.completed` | +12/-0；Worker `pushed`，remote SHA `160bcf4c3f72dbc65470c6169d1edb4e64b83724`，MR !102 |
| #486 | Claude / 3 / `minimax-m2.7` | 203 | completed；6/6 reasoning，`run.completed` | +1/-0；Worker `pushed`，remote SHA `c50547ffed83619b8e0dc6ac99b5d642da7081c2` |
| #487 | Claude / 3 / `minimax-m2.7` | 203 | completed；7/7 reasoning，`run.completed` | +1/-0；Worker `pushed`，remote SHA `cb8a20a09a562283f2f97ded57e9e97ae9ccbf2a` |
| #488 | Claude / 3 / `minimax-m2.7` | 203 | failed；6/6 reasoning，`run.failed` | 并发空提交推进远端后，delivery 以 `remote_diverged` fail-closed；0 changes、无 remote-confirmed Worker SHA |
| #498 | OpenCode / 3 / `minimax-m2.7` | 204 | cancelled；1/1 reasoning，`run.failed` | 页面捕获活动“正在思考”；取消请求早于 canonical completed 183ms，但最终为 completed、无 interrupted；native abort HTTP 200，0 changes |
| #499 | OpenCode / 3 / `minimax-m2.7` | 205 | completed；1/1 reasoning，`run.completed` | 继续会话正常完成；0 changes，archive 正常封存 |
| #500 | OpenCode / 3 / `minimax-m2.7` | 205 | cancelled；1/1 reasoning，`run.failed` | reasoning 完成后的 Bash `sleep 180` 取消；native abort HTTP 200，0 changes |
| #501 | OpenCode / 3 / `minimax-m2.7` | 205 | completed；1/1 reasoning，`run.completed` | 全新会话正常完成；0 changes，archive 正常封存 |
| #502 | OpenCode / 3 / `minimax-m2.7` | 205 | cancelled；1/1 reasoning，`run.failed` | 页面显示思考中，但 canonical reasoning 已在取消前自然完成；0 changes |
| #503 | OpenCode / 3 / `minimax-m2.7` | 205 | cancelled；1/0/1 reasoning，`run.failed` | 页面 `正在思考 · 2s` 时取消；canonical `reasoning_summary.interrupted(reason=aborted)`，刷新后终态稳定；0 changes |
| #504 | Claude / 3 / `minimax-m2.7` | 206 | failed；0 reasoning，无 canonical receipt | 受控 Issue #131 远端分叉在进入 Harness 前被拒绝；Worker 未覆盖远端，不能计入 Provider/reasoning 验收 |
| #505 | Claude / 3 / `minimax-m2.7` | 206 | completed；1/1 reasoning，约 2.0s，`run.completed` | 长运行探针总时长约 2m32s、381 条 `message.delta`；freeform、0 changes、delivery `not_needed`，不能计入长思考 |
| #508 | Codex / 4 / `gpt-5.6-luna` | 207 | completed；2/2 reasoning，`run.completed` | App Server V2 真实响应；`delivery.completed`/`worker.finalization` confirmed `remote_sha=cc97997fd0e5813398b4c60da0a09003496645cc`，+1/-0 |
| #510 | Codex / 4 / `gpt-5.6-luna` | 208 | failed；0 reasoning；`run.failed` | checkout/fetch 阶段早于 Harness 失败；canonical `run.started → harness.failed(engine_error) → worker.finalization → run.failed`，无 delivery、0 changes |
| #511 | Codex / 4 / `gpt-5.6-luna` | 208 | completed；6/6 reasoning，`run.completed` | 分析模式真实 `openai_responses` 成功；`+0/-0`，`delivery.completed.commit_sha=null`，`worker.finalization` 为零 diff；GitLab `codify/issue-133` 分支返回 Not Found，无空提交或远端虚假 SHA |
| #512 | Codex / 4 / `gpt-5.6-luna` | 208 | completed；8/8 reasoning，`run.completed` | 只读长运行探针总时长 1m9s；8 个 reasoning block 为 0.011–2.252s，未捕获活动 reasoning 取消；`+0/-0` |
| #513 | OpenCode / 4 / `gpt-5.6-luna` | 209 | completed；5/5 reasoning，`run.completed` | 当前 Provider 4 `openai_responses` 真实成功；5 个 reasoning block（2.177/7.769/0.017/7.872/2.219s），`+0/-0`，delivery/finalization 无提交 |
| #514 | Pi / 4 / `gpt-5.6-luna` | 210 | failed；6/6 reasoning，`run.failed` | Pi 归档正文报告上游 401 `invalid_api_key`；canonical seq 279 以活动 tool fail-closed 为 `protocol_error`，11 started/10 completed，0 changes；不计入 Pi Responses 成功 |
| #515 | Codex / 4 / `gpt-5.6-luna` | 208 | cancelled；6/6 reasoning，5/5 tool，`run.failed` | 页面运行中取消后刷新仍为 `已取消`；canonical seq 31/32/33 为 `harness.failed(cancelled)` → `worker.finalization(exit_code=143, diff=0)` → `run.failed(status=cancelled)`，0 changes、无远端写入 |

除 #504（旧 Bundle、进入 Harness 前失败且没有 canonical receipt）外，上述 Task 的 attempt 均为
`codify.worker.event/v2`，transport 与 adapter identity 来自真实 `run.started` receipt，而非
手工 fixture。#468/#469/#471 的 `worker.finalization` 均报告
`push.status=pushed`、精确 `remote_sha` 和 branch，故这些 delivery 不是 artifact metadata 或
平铺 SHA 推断；#510 另外证明了没有 Harness 终端时不会再错误地缺少 Task terminal。

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
| #484 | 4 / 2,618 | 4,564 bytes | `run.failed` |
| #485 | 12 / 17,655 | 17,581 bytes | `run.completed` |
| #486 | 11 / 20,117 | 17,927 bytes | `run.completed` |
| #487 | 15 / 26,887 | 24,180 bytes | `run.completed` |
| #488 | 13 / 23,197 | 22,299 bytes | `run.failed` |
| #498 | 5 / 3,291 | 7,032 bytes | `run.failed` / cancelled |
| #499 | 5 / 3,248 | 36,683 bytes | `run.completed` |
| #500 | 6 / 2,519 | 5,695 bytes | `run.failed` / cancelled |
| #501 | 5 / 3,182 | 67,604 bytes | `run.completed` |
| #502 | 4 / 2,797 | 8,636 bytes | `run.failed` / cancelled |
| #503 | 4 / 2,581 | 5,829 bytes | `run.failed` / cancelled |
| #504 | 3 / 1,517 | 1,384 bytes | 无 canonical terminal；Task `failed` |
| #505 | 66 / 101,140 | 173,301 bytes | `run.completed` |
| #508 | 6 / 4,476 | 7,407 bytes | `run.completed` |
| #510 | 2 / 1,518 | 2,103 bytes | `run.failed` / `engine_error` |
| #511 | 6 / 3,087 | 26,236 bytes | `run.completed` |
| #512 | 6 / 3,881 | 46,212 bytes | `run.completed` |
| #513 | 5 / 2,540 | 117,940 bytes | `run.completed` |
| #514 | 3 / 2,215 | 135,463 bytes | `run.failed` / `protocol_error` |
| #515 | 5 / 2,534 | 22,868 bytes | `run.failed` / cancelled |

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

Task #484 的 attempt 为 `task-484-attempt-1-ecc5c0374656`，OpenCode adapter `2.1.0`、CLI
`1.18.19`，`last_seq=8`，终态为 `run.failed`、control `closed`。任务使用当前 Bundle 202 和
Provider 4 `opencode-luna`（`gpt-5.6-luna`）；真实页面显示执行中后失败，远端错误来自
`https://opencode.ai/zen/go/v1/responses`，为 `unsupported_country_region_territory` 403，
没有 reasoning receipt。Canonical 仅有 `diagnostic` 3、`run.started`、`harness.failed`、
`run.failed`、`usage.final` 和 `worker.finalization`，raw 为 4 chunks / 2,618 bytes，archive
为 4,564 bytes，0 changes。该任务确认 Provider 4 的 Responses 请求路径可被当前 OpenCode
Bundle 调用，但上游地域策略在模型响应前拒绝；它不能计入 OpenCode Responses 验收，也不能通过
替换 Provider 配置绕过既有边界。

Task #485 的 attempt 为 `task-485-attempt-1-c3f518566122`，Claude adapter `1.1.0`、CLI
`2.1.153`，`last_seq=36`，终态为 `run.completed`、control `closed`，包含 5 个 reasoning
start/end 与 4 对工具事件。任务使用 Bundle 203（digest
`4f22bb5db5e00fdbab820c4d1a5ada8da212555049b7a26c27730d88430a167e`）和 Provider 3
`opencode-minimax`（`minimax-m2.7`），产生 +12/-0；`worker.finalization` 的 delivery
报告 `push.status=pushed`、remote SHA `160bcf4c3f72dbc65470c6169d1edb4e64b83724`，真实页面
随后显示 MR !102。raw 为 12 chunks / 17,655 bytes，archive 为 17,581 bytes。

Task #486 的 attempt 为 `task-486-attempt-1-c1abbca70b20`，Claude adapter `1.1.0`、CLI
`2.1.153`，`last_seq=41`，终态为 `run.completed`、control `closed`，包含 6 个 reasoning
start/end 与 6 对工具事件。它使用同一 Bundle 203/Provider 3，产生 +1/-0；
`worker.finalization` 报告 `push.status=pushed`、remote SHA
`c50547ffed83619b8e0dc6ac99b5d642da7081c2`。raw 为 11 chunks / 20,117 bytes，archive 为
17,927 bytes；它是正常 Claude delivery 证据，不是远端分叉证据。

Task #487 的 attempt 为 `task-487-attempt-1-cc740d9a116c`，Claude adapter `1.1.0`、CLI
`2.1.153`，`last_seq=63`，终态为 `run.completed`、control `closed`，包含 7 个 reasoning
start/end 与 13 对工具事件。它使用同一 Bundle 203/Provider 3，产生 +1/-0；
`worker.finalization` 报告 `push.status=pushed`、remote SHA
`cb8a20a09a562283f2f97ded57e9e97ae9ccbf2a`。raw 为 15 chunks / 26,887 bytes，archive 为
24,180 bytes；延长提示词仍只作为正常完成与交付回归，不宣称 30 秒单一长思考。

Task #488 的 attempt 为 `task-488-attempt-1-027660f6d209`，Claude adapter `1.1.0`、CLI
`2.1.153`，`last_seq=58`，先收到 `harness.completed`，随后以 `delivery.failed`、
`run.failed` 终止，control `closed`；包含 6 个 reasoning start/end 与 11 对工具事件。
任务使用 Bundle 203/Provider 3。受控探针在 Worker 运行期间向 `codify/issue-131` 推送空提交，
把远端从任务开始的 `cb8a20a09a562283f2f97ded57e9e97ae9ccbf2a` 推进到
`c34f7ff5add4a188b1fb8ed020d8d10ae7b3a246`；Worker 本地 head 为
`726d21ae40f2a8e9c82955c57ed150fd9664ebb7`。Git delivery 的非敏感 metadata 记录
`push.status=failed`、`push.error.code=remote_diverged`，并返回“remote task branch and local
head have diverged; refusing to overwrite the remote branch”；Task 的 `commit_sha` 为空、
0 changes，未产生 Worker 的 remote-confirmed SHA 或 Ready 交付。raw 为 13 chunks / 23,197
bytes，archive 为 22,299 bytes。该真实 Host 任务关闭 Claude 受控远端 divergence 的
fail-closed 验收边界。

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
- Claude Task #485/#486/#487 补齐了当前 Bundle 203 的真实正常 reasoning 与 Git delivery，
  #488 又以并发远端分叉证明 delivery fail-closed，拒绝覆盖远端分支且不产生成功交付；
- OpenCode Task #475 与 Pi Task #477 分别在 Bundle 199/201 上关闭了 Chat 正常成功和运行中
  页面时序子项；Pi #476/#470 的 404 仍作为修复前失败边界保留，没有改 Provider 配置或伪造成功。
- OpenCode Task #503 在 Bundle 205 上补齐了活动 reasoning 取消：页面先显示“正在思考”，随后
  canonical `reasoning_summary.started → reasoning_summary.interrupted(reason=aborted) →
  harness.failed(cancelled) → worker.finalization → run.failed`，刷新后任务保持 `已取消`。
- Claude Task #505 在 Bundle 206 上补齐了正常长运行任务的 archive/finalization/terminal 收敛；
  其 reasoning block 约 2.0 秒，不能计入长思考。
- Codex Task #508 在 Bundle 207 上补齐了真实 `openai_responses` 成功路径：V2 App Server
  identity 为 adapter `1.2.0` / CLI `0.146.0`，canonical 有两段 reasoning start/end，随后
  `harness.completed → delivery.completed → worker.finalization → run.completed`；Worker
  推送了 `cc97997fd0e5813398b4c60da0a09003496645cc`。它证明 Provider 与 Codex transport
  可用，但本次产生了 `hello.py`，尚未关闭“成功且零代码变化”的精确验收行。
- Codex Task #510 在 Bundle 208 上使用同一 Provider/Profile 触发受控 Issue #131 远端分叉，
  在 Harness 启动前失败；新的 finalizer 从 Bundle manifest 补齐 V2 identity，生成
  `run.started → harness.failed(engine_error) → worker.finalization → run.failed`，页面显示
  `Worker repository preparation failed before Harness start (phase=checkout, action=fetch, exit_code=1)`，
  没有 delivery、commit 或远端覆盖。
- Codex Task #511 在 Bundle 208 上使用同一 Provider/Profile 完成严格只读的真实
  `openai_responses` 任务；6 对 canonical reasoning start/end 均保持 start 先于 end，最终
  `delivery.completed` 的 `commit_sha=null`，`worker.finalization` 为 `total=0/additions=0/deletions=0`，
  Task/UI 均为 `+0/-0`。GitLab 工作分支 `codify/issue-133` 返回 Not Found，证明没有空提交或
  虚假远端 SHA；该任务关闭了 Codex 精确零变化验收行。

仍未关闭：

- Codex 的真实成功响应与 reasoning 已由 #508 证明，精确零代码变化、无空提交和无虚假远端 SHA
  已由 #511 关闭；#512 的长运行探针没有形成长 reasoning 或活动取消窗口，仍缺 Codex 取消/刷新
  和长思考回归，不修改 Provider slug。
- Pi/OpenCode 的 `openai_responses` 仍未完成：#482/#483 在当前 Bundle 202/201 上均由真实
  OpenRouter 免费模型 404 阻断，#484 在 Bundle 202 上由 Provider 4 地区 403 阻断；不能改用
  付费 slug 或绕过上游地区策略伪造能力；当前仍缺 Pi/OpenCode 可用 Responses、四 Harness
  长思考和 Codex 取消验收。#488 已关闭 Claude 受控远端 divergence 的
  fail-closed 边界。#478 的 Pi 取消已覆盖终态
  兜底，但没有 canonical interrupted receipt；#475/#477/#479/#480 是正常完成，#481 是思考完成
  后的取消，#498/#502 是 native reasoning 收尾竞态，#503 已补齐 OpenCode 的 canonical
  interrupted，但单个思考块耗时也很短；#505 的 Claude 长运行探针同样只有约 2.0 秒思考，不能替代第 8 节长思考要求；
- R4.5 owner closure、R4.6 独立 GO/NO-GO 和 R5/L6 仍未执行。

因此本记录是当前 exact composition 的真实推进证据，不是四 Harness 8 行全部通过或 release
candidate 签署。

## 5. 2026-09-08 finalization 与 native abort drain 修复后的历史续测

本节记录 Bundle 204–206 的历史 exact composition；当前 pre-Harness finalizer 修复后的
generation 95、Bundle 207/208 和 Task #508/#510/#511 见第 6 节。

为验证 Worker finalization 与原生 OpenCode abort 的竞态，本地提交
`4f42b9d7cbca3b575913745e225c24ff0cc52c8d` 将 `codify_finalize_on_exit` 调整为：先解除
console FIFO 继承并 drain tee，再执行 canonical attempt finalization 和 archive sealing；随后
`90dfe874d155df38909c5d273cf2729b121dded5` 在 native abort 后给 OpenCode Bridge 一个有界
drain grace，再进入原有硬终止路径。相关 OpenCode adapter/Worker coverage 共 `231 passed`，
`bash -n deploy/worker-entrypoint/harness/adapters/opencode.sh deploy/worker-entrypoint/bootstrap.sh`
与 `git diff --check` 通过。

远端开发 Host 重新构建 Backend/Scheduler 后，Profile 4 重新 Verify 为 generation `94`
（`2026-09-07T23:15:45.467794Z`），四 Harness evidence 均 ready。新生成的 Bundle 205
digest 为 `a9992043629103ef544de7250d1817e14cfd5f61653f17a4feab57176c38a2c9`；其
`worker-entrypoint/bootstrap.sh` SHA-256 为
`f7d0bbfcdae1fb336584a88cb468c421d4c7979496ca3b007e1e79236c2662cf`，OpenCode adapter
文件 SHA-256 为 `093005ffe94815daf84381d9bfbaa77a012ac5963699906e3415613de772c29b`，manifest
adapter digest 为 `969cd7d9a560c489df42b58e316fc30df16f1826efe5e6109eb089455bdba7ad`。旧 Bundle
保持不可变；Backend image 为 `sha256:459ce6cb448c83c278e440d8ae0a993144037f227363736d03045c5934783210`。
随后 #504/#505 绑定的 Bundle 206 digest 为
`921d7b53676eb61f4b8c1301802392e8791fe1d912cfddecd1381caddd28dffc`，大小为 655,360 bytes；
其四 Harness manifest 与 Bundle 205 相同。

| Task | Provider / Bundle | 终态与 reasoning | 取消边界 | raw / archive |
| ---: | --- | --- | --- | ---: |
| #490 | Provider 5 `opencode-mimo` / 202 | completed；2/2/0，`run.completed` | 正常完成 | 5 / 12,424 B |
| #491 | Provider 5 `opencode-mimo` / 202 | cancelled；7/6/0，`run.failed` | 取消时未形成 canonical interrupted | 4 / 30,417 B |
| #493 | Provider 5 `opencode-mimo` / 204 | failed；5/5/0，`run.failed` | `permission.asked` 需要交互响应，控制面按边界失败 | 4 / 29,738 B |
| #494 | Provider 5 `opencode-mimo` / 204 | cancelled；8/8/0，`run.failed` | 取消请求晚于最后 reasoning completed | 4 / 35,703 B |
| #495 | Provider 5 `opencode-mimo` / 204 | cancelled；14/14/0，`run.failed` | 取消落在 reasoning 完成后的阶段 | 4 / 69,628 B |
| #496 | Provider 5 `opencode-mimo` / 204 | cancelled；2/2/0，`run.failed` | 取消竞态中新 reasoning 在请求后开始，但未产生 interrupted | 4 / 17,869 B |
| #497 | Provider 3 `opencode-minimax` / 204 | cancelled；1/1/0，`run.failed` | 页面捕获“正在思考”，但 canonical completed 为 `22:43:35.390724Z`，取消请求为 `22:43:36.069676Z`；仍未发生活动 reasoning 中断 | 4 / 7,908 B |
| #498 | Provider 3 `opencode-minimax` / 204 | cancelled；1/1/0，`run.failed` | `model_variant=high`；取消请求为 `23:01:53.007558Z`，reasoning completed 为 `23:01:53.190446Z`，native abort 已获 HTTP 200，但未产生 interrupted | 5 / 3,291 B |
| #499 | Provider 3 `opencode-minimax` / 205 | completed；1/1/0，`run.completed` | 继续会话正常完成；0 changes | 5 / 3,248 B |
| #500 | Provider 3 `opencode-minimax` / 205 | cancelled；1/1/0，`run.failed` | reasoning 完成后的 Bash `sleep 180` 取消；native abort HTTP 200 | 6 / 2,519 B |
| #501 | Provider 3 `opencode-minimax` / 205 | completed；1/1/0，`run.completed` | 全新会话正常完成；0 changes | 5 / 3,182 B |
| #502 | Provider 3 `opencode-minimax` / 205 | cancelled；1/1/0，`run.failed` | 页面显示思考中，但 canonical reasoning 已在取消前自然完成；0 changes | 4 / 2,797 B |
| #503 | Provider 3 `opencode-minimax` / 205 | cancelled；1/0/1，`run.failed` | 页面 `正在思考 · 2s` 时取消；canonical interrupted；刷新后 `已取消` | 4 / 2,581 B |
| #504 | Provider 3 `opencode-minimax` / 206 | failed；0/0/0，无 canonical receipt | Issue #131 分叉在 Harness 前拒绝；Worker 未覆盖远端 | 3 / 1,517 B |
| #505 | Provider 3 `opencode-minimax` / 206 | completed；1/1/0，`run.completed` | 总时长约 2m32s，但 reasoning 约 2.0s；freeform、0 changes | 66 / 101,140 B |

#497 的 attempt 为 `task-497-attempt-1-62f6fa10ec1d`，OpenCode adapter `2.1.0`、CLI
`1.18.19`，`last_seq=26`、control `closed`。Canonical reasoning ID
`opencode-reason-part-ses_f81f5958fffefr6ZZIAgr2XPs9-msg_07e0a6fe3001nII73RZuiXosf2-prt_07e0a7c39001PUWHcNu8OoAg4G`
在 seq 5 started、seq 13 completed；随后 seq 24 为 `harness.failed`/`cancelled`，seq 25
为 `worker.finalization`（exit 143），seq 26 为 `run.failed`。原始 console 记录了
`OpenCode native abort acknowledged: HTTP 200`，说明 native abort 已被接受；本次没有
`reasoning_summary.interrupted`，不能把页面短暂显示的“正在思考”提升为活动 reasoning
中断证据。

#498 的 attempt 为 `task-498-attempt-1-1891d4c37a6e`，OpenCode adapter `2.1.0`、CLI
`1.18.19`，`last_seq=23`、control `closed`。任务使用 Bundle 204、Provider 3
`opencode-minimax`，并以已有 Provider 任务级 `model_variant=high` 作为延长 reasoning 探针。
页面在取消前显示 `正在思考 · 4s`，任务的 `cancel_requested_at` 为
`2026-09-07 23:01:53.007558Z`；canonical seq 5 的 reasoning started 为
`23:01:48.675687Z`，seq 17 的同一 reasoning completed 为 `23:01:53.190446Z`，随后 seq 21/22/23
依次为 `harness.failed(cancelled)`、`worker.finalization` 和 `run.failed(cancelled)`。原始
console 记录 `OpenCode native abort acknowledged: HTTP 200`，raw 为 5 chunks / 3,291 bytes、
archive 为 7,032 bytes；但没有 `reasoning_summary.interrupted`。这证明取消请求、native abort
和 finalization/archive 能收敛，却仍不是活动 reasoning 的 canonical interrupted 证据。

#503 的 attempt 为 `task-503-attempt-1-17527a229b82`，OpenCode adapter `2.1.0`、CLI
`1.18.19`，`last_seq=18`、control `closed`。任务绑定 Bundle 205、Provider 3
`opencode-minimax`，`session_mode=fresh`；`cancel_requested_at=2026-09-07 23:37:58.281812`
（UTC）。Canonical seq 5 在 `23:37:55.833694Z` 开始 reasoning，seq 14 在
`23:37:58.732995Z` 产生同一 reasoning ID 的 `reasoning_summary.interrupted`，payload
`reason=aborted`；随后 seq 16/17/18 依次为 `harness.failed(cancelled)`、
`worker.finalization(exit_code=143)`、`run.failed(cancelled)`。raw 为 4 chunks / 2,581 bytes，
archive 为 5,829 bytes；console 记录 `OpenCode native abort acknowledged: HTTP 200`。真实页面
在取消前显示 `正在思考 · 2s`，取消收束页显示 `思考记录已中断`；随后刷新验证终态仍为
`已取消`。

这组续测确认了 finalization 顺序修复已进入实际 Bundle，且正常完成、native abort、archive
和 cancelled terminal 均能收敛。#503 进一步证明 native abort drain 能在活动 reasoning
期间保留 canonical `reasoning_summary.interrupted`，并按 `harness.failed → worker.finalization
→ run.failed` 收尾；#498/#502 仍保留浏览器页面滞后于 canonical part 生命周期的真实边界。

#504 的 attempt 为 `task-504-attempt-1-db3e087851d7`，绑定 Bundle 206、Provider 3
`opencode-minimax`、Claude `1.1.0/2.1.153`，但 `last_seq=0`，没有 canonical receipt。受控
Issue #131 探针在进入 Harness 前发现本地 head `726d21ae40f2a8e9c82955c57ed150fd9664ebb7`
与远端 `c34f7ff5add4a188b1fb8ed020d8d10ae7b3a246` 分叉，bootstrap 拒绝 merge/overwrite；Task
记录为 `protocol_error: canonical attempt is missing a Task terminal`。这是受控远端分叉的
前置失败边界，不是 Provider 或 reasoning 结果；Worker 没有覆盖远端分支。raw 为 3 chunks /
1,517 bytes，archive 为 1,384 bytes。

#505 的 attempt 为 `task-505-attempt-1-2ef68217d604`，绑定 Bundle 206、Provider 3
`opencode-minimax`，`session_mode=fresh`，`last_seq=393`、control `closed`。真实页面显示
`思考完成 · 耗时 2s`，随后任务在约 2m32s 后正常完成；canonical seq 4/5 在
`2026-09-07T23:59:08.166676Z` / `23:59:10.201940Z` 对同一 reasoning ID 完成 start/end，
相隔约 2.0s，seq 391/392/393 依次为 `delivery.completed`、`worker.finalization`、
`run.completed`。任务共有 381 个 `message.delta`，但为 `freeform`、`require_changes=false`，
branch `codify/issue-115` 保持原 head，Git delivery 为 `not_needed`，0 changes；raw 为
66 chunks / 101,140 bytes，archive 为 173,301 bytes。它证明长运行任务的页面、archive 和正常
terminal 能收敛，但没有形成长 reasoning block，不能关闭四 Harness 长思考条件。

当前 OpenCode Chat 的活动思考取消/刷新终态子项已在 Bundle 205 关闭；Bundle 206 的 #505
补充了 Claude 正常长运行边界；#508/#510/#511 的 Codex 证据与 pre-Harness finalizer 修复见第 6 节。
当前仍保持 `NO-GO`，不追加无目的 smoke，不执行 migration 078、`v2_only` 或 R5。

## 6. 2026-09-08 pre-Harness finalizer 修复与 Codex 真实回归

本地提交 `6835e43ce855564f5c825c91c58ff2ee718637c9` 将已有
`harness/common.sh` 提前加载到 repository preparation 之前；当仓库 checkout/fetch 在
Harness 初始化前失败时，finalizer 从不可变 Runtime Bundle manifest 读取精确的 V2
Harness/Adapter/CLI/transport/model-protocol identity，再生成完整 canonical terminal。失败
信息保留 repository preparation artifact 的 phase/action/exit_code，不合成 Harness 成功或
delivery。

本地验证：

- `backend/.venv/bin/python -m pytest backend/tests/unit/test_opencode_harness_adapter.py backend/tests/unit/test_claude_harness_adapter.py backend/tests/unit/test_codex_harness_adapter.py backend/tests/unit/test_pi_harness_adapter.py backend/tests/unit/test_worker_coverage.py backend/tests/unit/test_worker_git_delivery.py -q`：`417 passed`；
- `backend/.venv/bin/ruff check backend/tests/unit/test_worker_coverage.py backend/tests/unit/test_worker_git_delivery.py`：通过；
- `bash -n deploy/entrypoint.worker.sh deploy/worker-entrypoint/bootstrap.sh deploy/worker-entrypoint/harness/common.sh deploy/worker-entrypoint/harness/adapters/opencode.sh` 与 `git diff --check`：通过。

远端 Backend image 为 `sha256:9c24e529fcd2238d57be93a359ab79a5f4868ed4143f09852c88c92406bba510`，
本地与 Backend `/opt/codify/runtime-source` 的 entrypoint/common SHA 完全一致。Profile 4
重新 Verify 为 generation `95`，Kit 仍为 `0.6.15`、manifest SHA
`506dbc2c61fbc03144c45fdffcd9a0e264781fe4038ad0ed13b38112580b831b`，四 Harness evidence
均 ready。

Task #508 的 attempt 为 `task-508-attempt-1-f2fffc8c1ab3`，绑定 Bundle 207、Profile 4、
Provider 4 `opencode-luna / gpt-5.6-luna`，`codify.worker.event/v2`，Codex adapter `1.2.0`、
CLI `0.146.0`，transport `rpc_stdio/codex-app-server-v2`、model protocol
`openai_responses`。`last_seq=21`；seq 6/7 与 11/12 为两段 reasoning start/end，seq 17 为
`harness.completed`，seq 19/20/21 为 `delivery.completed`、`worker.finalization`、
`run.completed`。真实页面 [Task #508](http://192.168.50.129:8880/tasks/508) 显示 Codex、
`gpt-5.6-luna`、思考完成、+1/-0 和已推送 commit；raw 为 6 chunks / 4,476 bytes，archive
为 7,407 bytes。

Task #510 的 attempt 为 `task-510-attempt-1-7ceae3061ae8`，绑定 Bundle 208、digest
`96341e488faa37bd081169a3c69a91504fbbaa2efa89f0ce890eb2e55114adc7`，同一 Provider/Profile，
Codex identity 完整写入四个 canonical receipt。seq 1/2/3/4 依次为
`run.started(startup_phase=repository_preparation)`、`harness.failed(engine_error)`、
`worker.finalization(exit_code=1)`、`run.failed(engine_error)`；Task error 为
`Worker repository preparation failed before Harness start (phase=checkout, action=fetch, exit_code=1)`。
无 `delivery.*`、commit SHA 或远端写入，raw 为 2 chunks / 1,518 bytes，archive 为 2,103 bytes；
真实页面 [Task #510](http://192.168.50.129:8880/tasks/510) 显示同一失败原因，证明旧 #504 的
`canonical attempt is missing a Task terminal` 生命周期缺口已修复。

Task #511 的 attempt 为 `task-511-attempt-1-19618031c8ac`，绑定同一 Bundle 208、Provider 4
`opencode-luna / gpt-5.6-luna`、Codex adapter `1.2.0`、CLI `0.146.0`，`last_seq=35`、
`control=closed`。它以全新会话、分析模式执行严格只读提示词；canonical seq 6/7、9/10、14/15、
18/19、22/23、27/28 分别为 6 对 reasoning start/end，全部 `started_before_completed=true`。
末尾 seq 32/33/34/35 依次为 `delivery.started`、`delivery.completed(exit_code=0, commit_sha=null)`、
`worker.finalization(diff total=0, additions=0, deletions=0, commit_sha=null)`、`run.completed`。
Task 记录 `completed`、`commit_sha=null`、`additions=0`、`deletions=0`、`total_changes=0`；真实页面
[Task #511](http://192.168.50.129:8880/tasks/511) 显示 `+0/-0` 和 6 条完成的 reasoning。
GitLab 分支页面 [codify/issue-133](http://192.168.50.129:8080/xiquan/121/-/tree/codify%2Fissue-133)
返回 Not Found，未产生远端分支提交。raw 为 6 chunks / 3,087 bytes，archive 为 26,236 bytes；
该任务关闭了计划中的 Codex 零变化行，但不关闭取消、刷新/重连或长思考条件。

Task #512 的 attempt 为 `task-512-attempt-1-e4f933f8320d`，同样绑定 Bundle 208、Provider 4、
Codex adapter `1.2.0`、CLI `0.146.0`，`last_seq=43`、`control=closed`。这是一个全新会话的
严格只读长运行探针；总运行时间约 1m9s、`+0/-0`，canonical 有 8 对 reasoning start/end，
没有 `reasoning_summary.interrupted`。按 receipt 时间计算 8 个 block 分别为
`2.252s/0.014s/0.015s/0.015s/2.179s/2.191s/0.011s/2.179s`；seq 40/41/42/43 依次为
`delivery.started`、`delivery.completed`、`worker.finalization`、`run.completed`，无取消终态。
raw 为 6 chunks / 3,881 bytes，archive 为 46,212 bytes。它是有界负证据：总任务耗时和较多
只读工具调用没有产生长 reasoning，也没有提供活动 reasoning 取消窗口；不关闭 Codex 长思考或
取消验收，也不授权增加等待卡或静态伪造。

## 7. Current Bundle Responses recheck: #513/#514

Task #513 的 attempt 为 `task-513-attempt-1-b97b9dc7fbf2`，绑定 Bundle 209、Profile 4、Provider 4
`opencode-luna / gpt-5.6-luna`，`codify.worker.event/v2`，OpenCode adapter `2.1.0`、CLI
`1.18.19`，`last_seq=1214`、`control=closed`。它以全新会话、分析模式执行严格只读
`openai_responses` probe；canonical 有 5 对 reasoning start/end，receipt 间隔分别为
`2.177s/7.769s/0.017s/7.872s/2.219s`，均为同一 reasoning ID 且 start 早于 end。seq 1210/1211/1212/1213/1214
依次为 `harness.completed`、`delivery.started`、`delivery.completed(exit_code=0, commit_sha=null)`、
`worker.finalization(diff total=0, additions=0, deletions=0, commit_sha=null)`、`run.completed`。
真实页面 [Task #513](http://192.168.50.129:8880/tasks/513) 显示 OpenCode、`+0/-0` 和完成状态；
raw 为 5 chunks / 2,540 bytes，archive 为 117,940 bytes。GitLab 对其 `codify/issue-134` 分支
返回 Not Found，未产生远端提交。该任务关闭了当前 exact composition 的 OpenCode Responses
“可用 Provider + durable terminal”子项，但不关闭页面长思考、取消/刷新或四 Harness 全覆盖。

Task #514 的 attempt 为 `task-514-attempt-1-5d6b64feed50`，绑定 Bundle 210、Profile 4、Provider 4
`opencode-luna / gpt-5.6-luna`，`codify.worker.event/v2`，Pi adapter `2.1.1`、CLI `0.84.2`，
`last_seq=281`、`control=closed`。它同样是全新会话、分析模式的严格只读 `openai_responses` probe；
canonical 有 6 对 reasoning start/end，receipt 间隔为
`2.177s/2.213s/2.187s/0.014s/2.185s/0.014s`。真实归档中的脱敏 Pi 输出报告了上游
`401 invalid_api_key`，但至少一个 tool execution 只有 `tool.started` 而没有对应结束记录；因此
seq 279/280/281 依次为 `harness.failed(protocol_error)`、`worker.finalization(exit_code=1, diff=0)`、
`run.failed(protocol_error)`，canonical failure 保留了活动 tool ID，未把它升级成 Provider 成功或
自动闭合为成功。raw 为 3 chunks / 2,215 bytes，archive 为 135,463 bytes，未产生提交或远端写入。
该结果是 Pi 当前 Provider/流终态的真实失败边界，不计入 Pi Responses 成功，也不授权修改 Provider
凭据、模型 slug 或绕过上游认证策略；应在后续有明确修复方案时重新生成新 Bundle，而不是覆盖 Bundle 210。

Task #515 的 attempt 为 `task-515-attempt-1-03caff857bce`，绑定 Bundle 208、Profile 4、Provider 4
`opencode-luna / gpt-5.6-luna`，`codify.worker.event/v2`，Codex adapter `1.2.0`、CLI `0.146.0`，
`last_seq=33`、`control=closed`。它是分析模式的真实只读任务；页面先显示运行中的 6 个 reasoning block
和 5 对 shell/tool 事件，随后在仍有事件流时点击取消。页面立即进入 `已取消`，刷新后仍保留该终态、
reasoning、tool 事件和原始日志。canonical seq 31/32/33 分别为
`harness.failed(payload.failure.kind=cancelled)`、`worker.finalization(exit_code=143, diff=0)`、
`run.failed(status=cancelled, failure.kind=cancelled)`；Task DB 的 `error_message` 为
`Cancelled by user`，`container_id` 为空，raw 为 5 chunks / 2,534 bytes，archive 为 22,868 bytes。
该 Task 证明当前 Codex cancellation/refresh/finalization/archive/cleanup 子项已闭合，但没有产生
`reasoning_summary.interrupted`，因此不关闭 Codex 长思考验收，也不改变四 Harness 全覆盖和 R4.3/R4.4
签署结论。
