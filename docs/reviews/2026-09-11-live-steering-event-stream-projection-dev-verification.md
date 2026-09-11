# 实时引导事件流产品投影 —— 开发环境验收记录

> 日期：2026-09-11
>
> 分支/HEAD：`dev @ ace95c18`（验收改动未提交，位于工作区）
>
> 目标 Host：`192.168.50.129`（docker context `remote`）
>
> 触发改动：`docs/architecture/live-steering-event-stream-projection.md` 实现（Backend 产品投影、Command Pump/Gate 公共展示字段、前端控制事件行与 i18n）
>
> 结果：**通过**（§10.1 后端回归、§10.2 前端回归、§10.3 真实 Task 验收均为真机证据）

## 1. 交付物与制品

| 项 | 值 |
|---|---|
| Backend 镜像 | `codify-backend:latest` sha256 `269553a88b0c603cfbf2344107bf8525060026d94ef62adab194480e88005490`（含 `native_sent_at` 守卫的最终构建；Task 614 在该构建上重跑拒绝场景） |
| Nginx 镜像（含前端构建） | `codify-nginx:latest` sha256 `808cb12a6226992e82aca8b1a898d2c6e202b7188bc0b796fe7cc68ab79465ce` |
| Worker Kit | `0.6.17`（**未改动**；§9.3 明确不改 Harness Adapter / Worker Kit event schema，因此无需重跑 `verify-runtime`） |
| Worker Profile | `id=4 v2-canary-four-harness`（Pi 启用） |
| Provider | `id=14 ds_offical_anthropic`（`deepseek-flash`，`anthropic_messages`） |
| 验收 Issue | `#182` `steering-projection-acceptance-1789135229`（project 16） |

**同一不可变 composition**：Task `608–614` 的冻结快照完全一致 ——
`runtime_bundle_digest=9a75bd2131c8fc5484293a46e8aa4ce5c506428d47b70abcf9445d57fe4ec524`、
`image_digest=127.0.0.1:5000/codify-worker/java21-maven@sha256:234582c692d1ebb00ba8e882160618c2258463149d968009ac81c545e63a538b`、
`runtime_locator_fingerprint=040a37a475205db17e56fcebd5a68e3a3ab240cfbbf0425efdf4e68905eaf0f1`。

部署方式：`make rebuild-backend` + `docker-compose --env-file .env.test up -d backend scheduler` + `make rebuild-nginx`（产物由目标机构建；后端产品投影与 Command Pump 都在 scheduler 进程，两个容器都用新镜像重建）。

## 2. 实现要点

- **Projector（`worker_event_projector.py`）**：`control.command.delivered/rejected` 落 `TaskLog` 时，按
  `task_id + ingest.attempt.attempt_id + sequence_no` 查 `TaskHarnessCommand`，并校验 `payload_digest`
  全等；命中才复制 `command_type` 与经 `sanitize_sensitive_data()` 的 `payload.text`。不使用
  `command_id` 关联（归档把它稳定脱敏为 `<UUID:...>`）。未命中只记录服务端 warning，identity/status
  事件照常落库，Task 生命周期不受影响。
- **公共展示字段**：`task_harness_commands.command_projection_fields()` 统一产出
  `command_id/payload_digest/sequence_no/command_type/text`，Pump 的 `outcome_unknown` 与 Gate 的
  `outcome_unknown` 全部改用它（前端只需读顶层字段）。
- **本地拒绝投影（§9.4 落地补充）**：`close_control_gate` /
  `request_force_close_after_unknown_follow_up` 的 `queued → rejected`，以及 Command Pump 的
  `DISPATCH_REJECT`，都会写入一条 `control.command.rejected` 事件流记录，原因来自公共映射
  （`PUBLIC_REJECTION_MESSAGES`，由 `app/api/task_command_routes.py` 移入
  `app/core/task_harness_commands.py`，HTTP 与事件流共用一份），bridge/transport 诊断文本不外泄。
  Pump 只在 `native_sent_at` 为空（原生请求确实没发出）时投影；已发送后的拒绝仍由 Harness ACK 独占，
  不会产生第二条记录。
- **前端**：`normalizeTaskProcessRows()` 过滤 `control.queue.updated`；`TaskProcessControlEventRow.vue`
  把类型提升为主标签、正文独立成块、序号单独一行、隐藏 command ID；i18n 中文
  `steer → 转向`、`follow_up → 续接指令`、`delivered → Harness 已接收`，英文 `Delivered → Harness accepted`，
  新增 `steeringRejectionReason`（`原因：{message}` / `Reason: {message}`）。

## 3. 真实 Task 验收（§10.3）

| 场景 | Task | 必须看到 | 实测（`task_logs.log_metadata` / 页面） |
|---|---|---|---|
| Pi 运行中发送 steer | 608 | 一条「转向 · Harness 已接收」，正文与命令历史一致 | `sequence_no=1 command_type=steer text=完成后简要总结即可`，命令行 `delivered`（`14:00:56.818`），commit `f684da13`，任务 completed |
| 当前轮结束前发送 follow_up | 608 | 一条「续接指令 · Harness 已接收」，下一轮按原生语义开始 | `sequence_no=2 command_type=follow_up text=完成当前步骤后继续检查测试`，命令行 `delivered`（`14:00:57.204`）；`delivered` 时间戳晚于原生发送，Pi 在 turn 边界 ACK |
| closing 后拒绝 | 611 | 一条「已拒绝」，类型、正文和公共原因正确 | `control.command.rejected sequence_no=1 command_type=follow_up text=续接指令：检查测试 [GITLAB_TOKEN] rejection_code=control_gate_closed rejection_message=The command channel is not accepting commands.`；命令行 `rejected`，`dispatch_started_at` 已置、`native_sent_at` 为空（owner/bridge 在原生请求前拒绝） |
| closing 后拒绝（最终构建重跑） | 614 | 同上 | 同一 recipe 在含 `native_sent_at` 守卫的最终镜像上复现：命令行 `rejected`、`native_sent_at` 为空，且只有 1 条 `control.command.rejected` 记录（`command_type=steer`、`text=任务正在收尾时的转向命令 [GITLAB_TOKEN]`、公共原因同上） |
| 显式 outcome_unknown | 610 | 类型 + 脱敏正文的「结果未知」 | `control.command.outcome_unknown sequence_no=1 command_type=steer text=任务收尾时的转向命令 [GITLAB_TOKEN] code=delivery_outcome_unknown`（取消竞态；无原生 ACK，由后端路径产生） |
| 页面刷新 | 608 | 展示保持一致，不依赖发送页内存 | 页面 `location.reload()` 后两行内容逐字不变（见 §4） |
| 查看运行归档 | 608 | queue update 和 ACK 原始审计仍存在 | 归档 `event.jsonl` 保留 4 条 `control.queue.updated` 与 2 条 `control.command.delivered`（含真实 `<UUID:...>` 与 `payload_digest`），`task_logs` 同样保留 |

**每条命令只有一条可见结果事件**：Task 608 两条命令共 2 条 `control.command.delivered` 记录；Task 611/614 各只有
1 条 `control.command.rejected` 记录；Task 610/612/613 各只有 1 条 `control.command.outcome_unknown` 记录，均无重复。

## 4. UI 证据（真实页面，中文 locale）

Task 608（delivered，`http://192.168.50.129:8880/tasks/608`）：

```text
[转向] | Harness 已接收 | 22:01:12 | 完成后简要总结即可 | #1
[续接指令] | Harness 已接收 | 22:01:13 | 完成当前步骤后继续检查测试 | #2
```

Task 611（rejected）：

```text
[续接指令] | 已拒绝 | 22:19:47 | 续接指令：检查测试 [GITLAB_TOKEN] | 原因：The command channel is not accepting commands. | #1
```

同时确认：

- 页面文本中**不存在**「控制队列已更新」；
- 页面文本中**不存在** `cmd <UUID:...>`（默认视图只保留 `#sequence_no`）；
- 凭据 `glpat-*` 在事件流中显示为 `[GITLAB_TOKEN]`；
- 页面刷新后（`location.reload()`）两行逐字不变，与发送该命令的浏览器会话无关。

## 5. 单元与合同测试

| 层 | 命令 | 结果 |
|---|---|---|
| Backend | `pytest tests/unit` | 通过（3484 passed, 4 skipped, 99 subtests）；`test_worker_command_pump.py` 新增/扩展 7 个投影用例：精确关联 delivered/rejected、digest 不匹配不补正文、attempt 作用域不串命令、gate 关闭拒绝投影、pump DISPATCH_REJECT 投影、gate outcome_unknown 展示字段、原生已发送拒绝不重复投影（该文件 32 passed） |
| Backend lint | `ruff check app/core app/api tests/unit/test_worker_command_pump.py` | 通过（`app/core/worker_profiles.py` 的既有告警与本改动无关，改动前即存在） |
| Frontend | `npx vitest run`、`npx vue-tsc --noEmit`、`npm run build` | 通过（82 files / 1770 tests；新增 `TaskProcessControlEventRow.spec.ts` 4 例与 `taskProcessUtils.spec.ts` 2 例） |

## 6. 已知边界与注入说明

- **Pi 不会原生拒绝命令**：截至验收，开发库从未产生过 `control.command.rejected` 收据；Task 609 在
  attempt 已 `closing`、Pi 已 `agent_settled` 之后投递的 steer 仍返回 `success:true` 并 `delivered`。
  这正是 §9.4 需要补齐本地拒绝投影的原因。
- 复现确定性：Task 609/610/611/612/613/614 使用了 dev-only 手段制造窗口（`docker pause codify-scheduler`、
  终止容器内 Pi 进程）以稳定复现「closing / 进程已退出」竞态；这些是验收注入，不是产品行为。同一 recipe
  会随调度时序落到 `rejected`（611/614）或 `outcome_unknown`（610/612/613）——后者是 owner 已整体退出、
  传输无法判定时既有的 fail-closed 语义，同样带有类型与脱敏正文。多次执行是为证明最终镜像上的
  `rejected` 可复现，不是替换既定语义。
- §4 非目标遵守：未新增数据库字段/迁移/配置开关；未改 Canonical Event 合同；未回填历史 `TaskLog`
  （历史行仍缺 `command_type`/`text`，实时引导历史面板继续用 commands API 展示正确类型/正文/终态）。
- 验收期间创建的 Issue 182 与 Task 608-614 保留为证据；未改动 Provider/Profile 配置。

## 7. 回滚与清理

- 无 Kit/镜像回滚需求：Worker Kit 与 Worker Image 未改动，回滚只涉及 backend/nginx 镜像。
- 未删除容器（均已自然结束）、归档或 DB 记录。/tmp 下的 cookie 与归档临时文件已删除。
