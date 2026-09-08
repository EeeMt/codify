# Open-Harness V2 R4-RC1 远端真实任务调试证据

**复核日期：** 2026-09-08
**Host：** `192.168.50.129`（开发环境，Docker context `remote`）
**结论：** `NO-GO`，继续保持 `HARNESS_EXECUTION_MODE=dual_canary`

本记录只收敛本轮真实 Provider、Runtime identity、Task archive 结构摘要和浏览器页面证据。
它不把一次成功 Task 推广为四 Harness 完成，也不替代 R4.5 owner 签署或 R4.6 决策。

> 第 1–5 节保留 generation 84 的早期远端调试快照；当前开发 candidate 以本节 overlay 和方案文档
> R4.2 表为准。旧快照不因新部署改写，旧失败边界也继续保留为历史 evidence。

## 0. Current candidate overlay

| 项 | 当前值 |
| --- | --- |
| Source anchor | `4249fcc4` (`feat(codex): forward configured reasoning effort`) |
| Profile / Verify | Profile 4 `v2-canary-0.6.11-four-harness`，generation `99`，`2026-09-08 07:52:51.33487` |
| Worker Kit | `0.6.16-linux-amd64-4866812149bd`，manifest SHA `4866812149bd240af4802ab1aa11b8364cc49b400a8d4a71d2721b8ac9ef5f9c` |
| Backend / Scheduler | `sha256:029384d710497c768bd6ca23ef6fa62fcd4751670d03d7aa0c35d990e91ed81e`，远端运行 35 分钟且 Backend healthy |
| NGINX | `sha256:aa09c11639f0f5838c085006c0690344f32536c1dcbd91dda37681cd6e253f2`，远端运行 2 小时 |
| Worker image | `127.0.0.1:5000/codify-worker/java21-maven@sha256:234582c692d1ebb00ba8e882160618c2258463149d968009ac81c545e63a538b` |
| Runtime Bundle | `216` / `c374ef5a009c53d2fc469a262e5cabcb23efff97f9d6176655992198bba946a7` |
| Provider / Task | Provider 4 `opencode-luna / gpt-5.6-luna`，`openai_responses`；Task #539 `completed` |
| Task snapshot | `worker_profile_id=4`、`runtime_bundle_id=216`、`projected_harness_key=codex`、`reasoning_effort=high` |

远端 Docker 只读复核得到 11 个容器全部运行（Backend/Scheduler/NGINX/Postgres 健康），没有
`pending`、`queued` 或 `running` Task；`docker system df` 为 Images `20/9`、`7.991GB`、可回收
`961.5MB`，Build cache 可回收 `380MB`。未触及服务、volume、active/unknown Worker 或不确定归属的
image/archive，也没有执行清理。

Task #539 在当前 Bundle 上有 34 条连续 Canonical receipt，11/11 reasoning `started → completed`，
单段 `5.204–6.349s`，最终 `+0/-0`、`commit_sha=null`，无远端写入。该任务和固定 8 行中的
不可变历史 Task #468/#469/#488/#513/#517/#521/#523 一起构成当前技术 evidence；5–6 秒是当前 reasoning
可用性口径，历史段落中的 30s 仅作旧负探针记录。R4.3/R4.4 技术 evidence 已闭合但尚未正式签署，
R4.5 owner closure 未完成，故 R4.6 仍为 `NO-GO`。

## 1. Historical source 与部署组成（generation 84）

| 项 | 本轮值 |
| --- | --- |
| 本地 source anchor | `7fd0939c78d4b4f5388dff43dc71e2f2587e2497` |
| source 变更 | Worker delivery 在隔离 Git 配置下显式使用 `/root/.git-credentials`；相关单测 36 passed |
| Profile | id `4`，`v2-canary-0.6.11-four-harness` |
| Verify generation | `84` |
| Verify time | `2026-09-07 16:35:14.943911 UTC` |
| Backend/Scheduler image | `sha256:5f1373d01da7de58c92382264284ee47dbab233e9eb424a9afd1a69a18c4e0d1` |
| NGINX image | `sha256:7df17a98f90e32e60d5648c73862c1819c06659404f5f74cd665d3f70cf00265` |
| Worker image | `127.0.0.1:5000/codify-worker/java21-maven@sha256:234582c692d1ebb00ba8e882160618c2258463149d968009ac81c545e63a538b` |
| Worker image id | `sha256:b07ac48b129c35876c044079f8e9cd7aa7558dbb0ade2e50e856d4ab980f5e71` (`linux/amd64`) |
| Worker Kit | `0.6.14`，manifest `d461d040694b20b88944a88de47b5ad78188f91d74d528421cdef44b68274035` |
| Runtime configuration digest | `0096dc7e06c4f8c8211f2170b33dfd76adf89c0033f6fd1453aa6c58943171c4` |

Backend、Scheduler 和 NGINX 在远端正常运行，数据库没有残留 `pending`、`queued` 或 `running`
Task。容器没有 OCI `org.opencontainers.image.revision` label，因此上表记录的是实际 image/profile/kit
identity；它不是已签名的 source-to-image provenance。分支当前与 `origin/dev` 非线性分叉，故本记录
仍不能作为 release candidate 签署。

远端 `docker system df`：Images `27/9`、`7.799GB`，可回收 `1.105GB`；Build cache 可回收
`2.176GB`；根盘约 41% 使用率。本轮未达到磁盘满条件，未清理任何 Codify 镜像、volume、cache
或不确定归属的活动容器。

## 2. Historical 真实 Task 结构摘要

完整 raw archive 仍保留在远端；下表只记录脱敏后的事件类型/序号、终态和交付摘要。`reasoning`
列依次为 `started/completed/interrupted`，不是把 archive 内容复制到本地。

| Task | Harness / protocol | Provider | 终态 | Archive | Reasoning | Delivery / 边界 |
| --- | --- | --- | --- | ---: | ---: | --- |
| #450 | Pi / `openai_responses` | 12 | completed | 223 | 0/0/0 | `1b1c59be...`，push confirmed；无 canonical reasoning |
| #451 | Codex / `openai_responses` | 12 | completed | 18 | 0/0/0 | zero-change，`push=not_needed`；raw execution item 不能证明 reasoning start |
| #452 | Pi / `anthropic_messages` | 6 | completed | 791 | 4/4/0 | recovered 两个 commit，`cc071acc...` push confirmed；页面显示完成 thinking |
| #453 | OpenCode / `openai_responses` | 12 | completed | 123 | 0/0/0 | `2424ca3a...` push confirmed；无 canonical reasoning |
| #454 | Claude / `anthropic_messages` | 6 | failed `protocol_error` | 314 | 23/22/1 | 远端 `codify/issue-116=4e76d94f...` 未被覆盖；push not attempted；失败发生在 Harness normalization 前，未形成完整 reconciliation |
| #456 | Pi / `openai_chat_completions` | 7 | cancelled | 20 | 0/0/0 | cancel HTTP 200，终态为 cancelled；无 reasoning，因此不是 interrupted thinking 证明 |
| #457 | OpenCode / `anthropic_messages` | 6 | completed | 189 | 6/6/0 | `782f0750...` push confirmed；页面显示 6 条 completed thinking |
| #458 | OpenCode / `openai_chat_completions` | 7 | cancelled | 16 | 0/0/0 | cancel HTTP 200，`MessageAbortedError`；无 reasoning start/interrupted |
| #459 | Claude / `anthropic_messages` | 6 | failed `protocol_error` | 219 | 5/5/0 | `Harness result normalization failed`；`4dd0851f...` 未 push，故不是成功交付 |
| #449 | OpenCode / `anthropic_messages` | 6 | timeout | 11,365 | 7/6/— | 复杂 delivery/reconciliation 场景在 1800 秒边界超时，push not attempted |

此外，#455 的 Provider 返回模型不可用的 404；它不是取消、thinking 或 delivery 证据，故不计入矩阵。

## 3. Historical 浏览器页面证据

以下截图来自开发 Host 的真实 Task detail 页面；它们证明页面终态、Provider/Harness、delivery 摘要和
可见 thinking 行，但截图是在任务完成/取消/失败后取得，不能单独证明“开始占位早于完成”或 5 秒内出现。

- [#451 Codex zero-change](../../../output/playwright/task-451-codex-zero-change.png)
- [#452 Pi Anthropic delivery](../../../output/playwright/task-452-pi-anthropic-delivery.png)
- [#453 OpenCode Responses delivery](../../../output/playwright/task-453-opencode-responses-delivery.png)
- [#454 Claude controlled divergence](../../../output/playwright/task-454-claude-divergence-failed.png)
- [#456 Pi Chat cancelled](../../../output/playwright/task-456-pi-chat-cancelled.png)
- [#457 OpenCode Anthropic delivery](../../../output/playwright/task-457-opencode-anthropic.png)
- [#458 OpenCode Chat cancelled](../../../output/playwright/task-458-opencode-chat-cancelled.png)
- [#459 Claude normalization failure](../../../output/playwright/task-459-claude-normalization-failed.png)

## 4. Historical 验收边界与停止条件

本轮确认了 Pi/OpenCode 的部分真实成功交付、受控远端分叉保护、两个 Chat 取消终态和 Claude 的
两类失败边界；没有满足完整 R4-RC1 退出条件：

- Codex #451 没有 canonical reasoning start/end；不能用 raw `item.started/completed` execution item 替代。
- Pi/OpenCode Chat 的 #456/#458 是无 reasoning 的取消，不能证明 thinking interrupted placeholder。
- Claude #454/#459 分别落在截断 thinking stream 与 result normalization failure；没有成功闭合路径。
- OpenCode #449 的复杂 delivery 场景超时；不能把部分提交或失败前日志当成成功 reconciliation。
- #452、#457 的 reasoning start/end 与完成页面已留证，但本轮没有在任务运行中截取“占位先于完成”的实时页面时序。

因此 generation 84 快照本身不能作为当前 R4.3/R4.4 的完整 evidence；它的失败边界继续有效，不能被后续成功
Task 稀释。当前 R4.3/R4.4 的技术结论和 #539 见第 0 节；正式签署仍等待 R4.2 identity、R4.3/R4.4
验收签字与 R4.5 owner closure。不得执行 migration 078、`v2_only` 或 R5，也不追加普通 smoke 来稀释历史失败边界。

## 5. Historical 本地验证

- `backend/.venv/bin/python -m pytest backend/tests/unit/test_worker_git_delivery.py -q`：`36 passed`
- `bash -n deploy/worker-entrypoint/repository-helpers.sh`：passed
- `git diff --check`：passed
- `npm run build`：本轮代码变更前已通过；本轮未修改 frontend source
