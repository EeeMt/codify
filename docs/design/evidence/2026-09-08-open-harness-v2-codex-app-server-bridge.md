# Open-Harness V2 Codex App Server Bridge 与真实 Provider 边界证据

**复核日期：** 2026-09-08
**Host：** `192.168.50.129`（开发环境，Docker context `remote`）
**结论：** `NO-GO`，继续保持 `HARNESS_EXECUTION_MODE=dual_canary`

本记录补充 R4-RC1 的 Codex App Server 运行路径和真实 Provider 调试结果。它证明新
Runtime Bundle/Kit 已部署并能进入 Codex App Server 任务链路，但不把 Provider 在上游
拒绝前的启动事件当成 reasoning 生命周期验收，也不替代 R4.5 owner 签署或 R4.6 决策。

## 1. Source 与部署组成

| 项 | 本轮值 |
| --- | --- |
| Source anchor | `5d2fad8e7f81e947097d092e1b502f2eae31607c` |
| Source commit | `feat(worker): run Codex through App Server bridge` |
| Backend image | `sha256:7673b0b07afcaeb4f7c250bd531f23da825a765d43706c41007069b1931d875a` |
| NGINX image | `sha256:ba50f6296e92e426dd445740d7214c6c54aaddd2a79d58d1513a4741379c6e43` |
| Profile | id `4`，`v2-canary-0.6.11-four-harness` |
| Runtime mode | `mounted_kit` |
| Worker Kit | `0.6.15`，path `/opt/codify/worker-kits/0.6.15-linux-amd64-506dbc2c61fb` |
| Kit manifest SHA-256 | `506dbc2c61fbc03144c45fdffcd9a0e264781fe4038ad0ed13b38112580b831b` |
| Profile Verify | `2026-09-07 18:41:57.416347`，管理员 Verify HTTP 200 |
| Runtime Bundle | id `197` |
| Codex identity | adapter `1.2.0`，CLI `0.146.0` |
| Codex transport | `rpc_stdio` / `codex-app-server-v2` |
| Codex model protocol | `openai_responses` |
| Worker image | `127.0.0.1:5000/codify-worker/java21-maven@sha256:234582c692d1ebb00ba8e882160618c2258463149d968009ac81c545e63a538b` |

Kit 在本地 `linux/amd64` Docker builder 构建后导出并原子安装到远端，Kit smoke 覆盖
Claude `2.1.153`、Codex `0.146.0`、OpenCode `1.18.19` 和 Pi `0.84.2`。远端 Backend、
Scheduler、NGINX 当前正常，Scheduler 仍为 `dual_canary`；Profile 4 的 readiness 已显示
`ready`。

本轮远端构建曾因根盘空间不足失败。仅执行了有明确 Codify ownership 的窄范围处理：删除
8 个 dangling Codify compose image，并清理一小时以前的 BuildKit cache，回收约 1.96GB；
未触碰服务、volume、活动 Worker 或不确定归属的镜像。复核时根盘约 99% 使用、剩余约
841MB，因此不再进行大体积构建或宽泛 prune。

## 2. 真实 Codex Task 结果

三个 Task 都由同一 Profile、同一 Runtime Bundle 和同一 Codex App Server 路径执行。三者
均达到 `run.started`、`model.resolved`、Provider retry、`harness.failed`、
`worker.finalization` 和 `run.failed`，没有产生 reasoning 或代码变化。

| Task | Provider / model | 结果 | Attempt | 结构证据 |
| --- | --- | --- | --- | --- |
| #461 | 12 / `minimax/minimax-m3:free` | OpenRouter HTTP 404：free model unavailable，建议付费 slug | `task-461-attempt-1-c09c90848c09` | 5 raw chunks，2,243 bytes；archive 4,546 bytes |
| #462 | 4 / `gpt-5.6-luna` | OpenCode Zen HTTP 403：`unsupported_country_region_territory` | `task-462-attempt-1-db7be28ff3ad` | 5 raw chunks，2,595 bytes；archive 4,545 bytes |
| #463 | 9 / `z-ai/glm-5.2:free` | OpenRouter HTTP 404：free model unavailable，建议付费 slug | `task-463-attempt-1-3a73a2f124c7` | 4 raw chunks，2,599 bytes；archive 4,618 bytes |

三条 attempt 均为 `codify.worker.event/v2`、Harness `codex`、adapter `1.2.0`、CLI
`0.146.0`、transport `rpc_stdio/codex-app-server-v2`，终态 `run.failed` / `closed`。
每条 event 类型计数均为：`run.started=1`、`model.resolved=1`、`provider.retry=5`、
`diagnostic=4`、`harness.failed=1`、`run.failed=1`、`worker.finalization=1`；
`reasoning_summary.started/completed/interrupted` 均为 0。三个 Task 的 additions、deletions
和 total changes 均为 0。

开发 Host 的 Task #463 页面已通过真实服务页面检查：
`http://192.168.50.129:8880/tasks/463` 显示 Failed、Codex、Provider
`openrouter-glm52-responses`、模型 `z-ai/glm-5.2:free` 和上游 404 原因。页面是失败终态，
不能替代运行中“开始占位早于完成”的浏览器时序证据。Playwright 截图命令本轮因本地
npm registry DNS 不可用未生成新 PNG，不影响服务端/数据库证据结论。

## 3. 本轮实现与验证

- 新增单一 Codex App Server stdio Bridge：执行 `initialize`、`thread/start` 或
  `thread/resume`、`turn/start`，转发原生 JSONL；未授权的 server request fail closed；
  收到 TERM/INT 时发送 `turn/interrupt`，不自动回退到旧 transport。
- Codex Adapter 映射原生 `item/started` / `item/completed`、agent message delta、usage、
  turn terminal 和上下文压缩，并把 Bridge 纳入 Runtime Bundle digest。
- 更新 Codex manifest、Backend protocol matrix 和 Kit validator 为
  `rpc_stdio` / `codex-app-server-v2`；既有旧 Bundle 与历史 fixture 不被覆盖。
- 定向验证：`223 passed`；`make lint-backend`、shell syntax、Python compile 和
  `git diff --check` 全部通过。

## 4. 结论与下一出口

本轮已关闭“Codex 仍停留在 exec JSONL、没有 App Server 主路径”的实现缺口，并证明真实
任务使用了新 transport；但 Provider 在模型响应前失败，因此仍没有真实 reasoning start/end、
空内容完成、取消中断或共享 delivery 回归证据。不能将这三条失败 Task 计入第 8.2 节
Codex 行，也不能把 `model.resolved` 或 `turn.started` 当作思考开始。

Provider 12 和 9 的上游错误分别建议付费 model slug；使用 `minimax/minimax-m3` 或
`z-ai/glm-5.2` 会产生外部付费请求，当前未得到授权，未修改 Provider 配置。Provider 4
受地区限制；其他现有 Provider 的协议不是 Codex 当前声明的 `openai_responses`，不能作为
绕过合同的替代。下一次成功 Codex 真实 turn 需要用户明确授权付费 slug（或提供可用的
现有 `openai_responses` Provider），然后在同一 exact source/Kit/Bundle identity 下重做
Codex 行验收。

因此 R4.3/R4.4 仍为部分 evidence、未签署；R4.5 等待 owner 输入；R4.6 保持 `NO-GO`。
不得执行 migration 078、`v2_only` 或 R5。
