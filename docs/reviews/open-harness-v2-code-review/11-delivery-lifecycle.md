# 11 Git/MR 交付、Task 生命周期与终态、Scheduler —— Code Review

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56`（`dev`，477 commits / 437 files / +74,905 / -3,855） |
| 审查方法 | 静态阅读 `dev @ cbad9e56` 当前完整文件（非 diff 片段）+ 设计文档契约对照（git-delivery reconciliation 设计 §4–§9、peak/off-peak 超时设计 §6/§13）+ 与 V1 基线 `8081c946^` 逐点对比以区分「遗留 / 新引入」+ 窄范围单测运行 |
| 已运行的窄范围验证 | `cd backend && .venv/bin/python -m pytest tests/unit/test_task_timeout.py tests/unit/test_worker_git_delivery.py tests/unit/test_worker_task_artifacts.py -q` → 56 passed；`... test_worker_task_lifecycle.py test_worker_freeform_delivery.py test_worker_gitlab_delivery_text.py -q` → 23 passed；`... test_scheduler.py test_scheduler_core.py test_scheduler_harness_gate.py -q` → 70 passed；`... test_worker_results_v2.py test_containers_api.py test_task_failure_details.py -q` → 79 passed；`ast.parse`（本次改动的后端文件）全部通过；`import app.scheduler / app.core.worker_task_lifecycle / app.core.worker_git_delivery / app.core.task_timeout / app.api.task_action_routes` 通过 |
| 未覆盖 | 前端结果卡与 MR 展示实现（T12）、canonical 事件校验 / projector 细节（T02）、命令平面与 control gate（T01）、四个 adapter 内部（T03/T04/T05/T06/T07）、Kit / Runtime Bundle 制品与 registry（T08/T09）、安全横切深度（T13）、迁移与数据模型（T14）、部署编排与 preflight（T15） |

### 实际审查文件

| 文件 | +/- |
|---|---|
| `backend/app/api/containers.py` | +47 / -0 |
| `backend/app/api/issues.py` | +46 / -2 |
| `backend/app/api/task_action_routes.py` | +30 / -7 |
| `backend/app/api/task_operations.py` | +41 / -5 |
| `backend/app/api/task_responses.py` | +32 / -1 |
| `backend/app/api/task_runtime_summary_routes.py` | +48 / -0 |
| `backend/app/api/tasks.py` | +80 / -1 |
| `backend/app/core/ci_failure_collector.py` | +43 / -20 |
| `backend/app/core/task_timeout.py` | +120 / -0 |
| `backend/app/core/worker_git_delivery.py` | +325 / -0 |
| `backend/app/core/worker_gitlab.py` | +159 / -13 |
| `backend/app/core/worker_task_artifacts.py` | +71 / -2 |
| `backend/app/core/worker_task_lifecycle.py` | +488 / -43 |
| `backend/app/core/worker_task_outcomes.py` | +15 / -1 |
| `backend/app/core/worker_task_runner.py` | +45 / -7 |
| `backend/app/scheduler.py` | +595 / -99 |
| `backend/app/scheduler_service.py` | +38 / -0 |
| `deploy/worker-entrypoint/git-delivery.py` | +725 / -0 |
| `deploy/worker-entrypoint/git-delivery.sh` | +429 / -0 |
| `deploy/worker-entrypoint/repository-helpers.sh` | +218 / -85 |
| `deploy/worker-entrypoint/main.sh` | +156 / -178 |
| `deploy/worker-entrypoint/verification.sh` | +150 / -34 |
| `deploy/worker-entrypoint/bootstrap.sh` | +72 / -12 |
| `deploy/worker-entrypoint/delivery.sh` | +71 / -22 |
| `deploy/worker-entrypoint/artifacts.py` | +1 / -0 |

关联阅读（非本专题主责，仅用于交叉验证）：`backend/app/core/worker_results.py`、`backend/app/core/harness_attempts.py`、`backend/app/core/worker_event_projector.py`、`backend/app/core/worker_runtime.py`、`deploy/worker-entrypoint/harness/common.sh`、`deploy/entrypoint.worker.sh`。

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 1 |
| FIX_IF_CHEAP | 1 |
| DEFER | 5 |
| ACCEPT/CLOSE | 0 |

本专题核心不变量在 V2 改动中基本成立：Scheduler 的原子认领与超时档位冻结在同一事务内完成、容器按不可变 `container_id` 与 daemon key 校验归属、`codify.git-delivery.v1` 三层一致且矛盾即 fail closed、`worker.finalization` 与唯一终态的时序两侧都有强制校验。FIX_NOW 只有 DEL-01：终态失败原因被 provider 重试错误覆盖，属「对交付结果说谎」，不修则终态语义不可信。其余 6 条（1 FIX_IF_CHEAP + 5 DEFER）按 3 人内测、无 SLA、避免过度防御的画像记录在案，本阶段书面接受 0 条。

## 2. 问题清单

### DEL-01 终态失败原因被归档的 provider 错误覆盖
- **判定**：FIX_NOW —— 触犯本档「对交付结果说谎」的定义
- **位置**：`backend/app/api/tasks.py:657-668`（另见 `:709-718`）（提交 `ab869c67`）；更深一处在 `backend/app/core/worker_results.py:591-595`（提交 `9c4a094b`，属失败分类专题，建议与 T02 协同）
- **证据**：`get_task` 对终态任务取归档 detail 后无条件覆盖 `error_message`，失败摘要同样被覆盖（仅排除 `failure_kind == "protocol_error"`）：

  ```python
  if task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
      archived_failure_detail = await asyncio.to_thread(
          read_archived_harness_failure_detail, task.id, sanitize_sensitive_data,
      )
      if archived_failure_detail:
          result_data["error_message"] = archived_failure_detail
  ```

  同一替换也发生在 canonical 终态写入路径：

  ```python
          archived_failure_detail = read_archived_harness_failure_detail(
              task.id,
              sanitize_sensitive_data,
          )
          if archived_failure_detail and failure_kind != "protocol_error" and terminal_status != "protocol_error":
              failure_message = archived_failure_detail
  ```

  `read_archived_harness_failure_detail`（`backend/app/core/task_failure_details.py:221-231`）返回的是归档**原始 harness 事件流**中最后一条 provider 侧错误（Pi `session.error` / legacy `errorMessage`、`auto_retry_start`），与 canonical 终态无关；`_legacy_pi_error_values`（`task_failure_details.py:88-110`）的注释本身说明这些记录出现在**可恢复的重试**流里。`failure_kind == "cancelled"`、交付失败的 `engine_error`、timeout 之外的一切失败都会落入替换条件。
- **影响**：两类终态的失败原因与事实不符：(a) 取消的任务 —— canonical/生命周期写入的是 `"Cancelled by user"`（`worker_task_lifecycle.py:1301-1309`），持久化与接口却显示 provider 错误（如 "Pi provider returned HTTP 429 …"）；(b) 交付失败任务 —— `git_delivery.push.error.message`（交付设计 §7 要求投影到 `Task.error_message`，实现见 `deploy/worker-entrypoint/harness/common.sh:338-349`）会被 provider 错误盖住，同时 `send_failure_alert` 会把该错误原文发到告警 webhook（`core/worker_task_outcomes.py:241-275`）。触发前提：该 Task 归档原始流中存在 provider 错误记录（Pi / OpenCode 重试流中常见）。
- **最小动作**：仅当 canonical 失败原因为空（legacy Pi 记录才是 raw payload）时才用归档 detail 兜底，且排除 cancelled / timeout / 交付失败；归档 detail 另存字段。改 2 处条件：`api/tasks.py:657-668`（读，含 `:709-718` 的 failure_summary）、`core/worker_results.py:589-595`（写）
- **验证**：现有测试只覆盖 reader（`backend/tests/unit/test_task_failure_details.py`），未覆盖替换语义。应补一例：归档含 `session.error`，任务因取消或交付失败而终态，断言 `error_message` 仍为 canonical 原因。本次**未运行验证**（需真实 archive 与 Pi 原始流，见 §4）。

### DEL-INFO-02 `[V1 遗留]` 无变更失败在 `error_message` 上只留 `engine_error`
- **判定**：FIX_IF_CHEAP —— 默认 `require_changes=true` 下「无变更」常见，~3 行可修
- **位置**：`deploy/worker-entrypoint/main.sh:331-340`、`deploy/worker-entrypoint/harness/common.sh:371-405`、`backend/app/core/worker_results.py:574-600`
- **证据**：`require_changes=true` 且无交付内容时 main.sh 以 exit 1 结束，此时既无 `harness.failed` 事件、`push.error` 也为 null；`common.sh` 由 `codify_harness_last_failure_message` 取到空串后回落到 `failure_kind=engine_error`，Backend 在 `failure.message` 缺失时以 `kind` 兜底（`"engine_error"`）。
- **影响**：用户看到 `error_message = "engine_error"`，无法得知真实原因是「本次没有产生任何变更」。V1 的 `main.sh` 无内容分支与 finalizer 同结构（基线 `harness/common.sh:150-161`、`main.sh` 末尾 else 分支），故按遗留记录；V2 已通过 `push.status=not_needed` 与 MR 展示部分改善可观测性。
- **最小动作**：无内容分支补发 `harness.failed{kind:engine_error,message:"No changes were delivered and require_changes is enabled"}`（~3 行；finalizer `common.sh:319-413` 已能读 harness.failed 的 kind/message）
- **验证**：对照基线 `git show 8081c946^:deploy/worker-entrypoint/harness/common.sh`、`.../main.sh`（本次已执行）；未在容器内复现。

### DEL-02 交付采集的软失败原因不会进入任何事件或 Task 字段
- **判定**：DEFER —— 默认部署不可达
- **位置**：`deploy/worker-entrypoint/git-delivery.py:397-405`（软错误）、`:536-540`（写入快照）、`deploy/worker-entrypoint/main.sh:302-311`、`deploy/worker-entrypoint/harness/common.sh:325-328,355-358`（提交 `48b94dc2`）
- **证据**：继承范围无法证明时 worker 记录软错误但仍保留已采集的 commits：

  ```python
      if not collected:
          delivery["recovered_commits"] = None
          error = {
              "code": "history_unverifiable",
              "message": (
                  "Inherited pending commits cannot be proven within the "
  ```

  该 `error` 只写进容器内快照（`git-delivery.py:536-540`）。main.sh 仅在 `commits == null` 时当硬失败（`main.sh:302-310`）；`delivery.*` 与 `worker.finalization` 事件只投影 `{exit_code,commit_sha,commit_message,diff,git_delivery}`（`common.sh:325-328`、`355-358`），快照顶层 `error` 永远到不了 Backend。
- **影响**：当本次无提交且继承范围不可证明（`_recovered_range_base` 返回 `collected=False`，`git-delivery.py:168-185`；浅克隆 / `--filter` partial clone 下 `merge-base --is-ancestor` 不可判定时成立）时，快照为 `commits=[]`、`recovered_commits=null`、`push=not_needed`，main.sh 走「无内容」分支（`main.sh:331-340`），任务以「No changes were delivered and require_changes is enabled」失败。真正的失败原因（继承提交无法归属）只存在于容器内快照文件，`Task.error_message`、`worker_metadata`、canonical 事件都没有记录，运维无法区分「确实没有变更」与「有继承变更但无法证明」。
- **最小动作**：无内容分支（`main.sh:331-340`）在快照 `.error.code` 非空时以该原因退出（~4 行 shell），或投影 `git_delivery.collect_error`
- **验证**：`deploy/worker-entrypoint/git-delivery.py` 有真实本地 git 单测（`backend/tests/unit/test_worker_git_delivery.py`，本次通过），但未覆盖「浅历史 + 无本次提交 + 软失败投影」；需新增一例断言快照 `error` 出现在终态可见字段。本次**未运行验证**。

### DEL-03 `task_timeout` 共享 helper 未被生产代码使用，派生值在 API 内各写一遍
- **判定**：DEFER —— 本阶段不值得单独一轮改动
- **位置**：`backend/app/core/task_timeout.py:90-92`、`backend/app/core/task_timeout.py:108-110`；重复实现于 `backend/app/core/task_helpers.py:38-41`、`backend/app/api/issues.py:319-322`（提交 `7e0c59a6`）
- **证据**：全仓库（排除 `.git` / `__pycache__` / `node_modules`）检索：`resolve_task_timeout_seconds` 只出现在定义处与设计文档（`docs/superpowers/specs/2026-09-09-peak-off-peak-task-timeout-design.md:185`）；`execution_deadline_at` 只被 `backend/tests/unit/test_task_timeout.py:9,69,73` 使用。两处 API 各自内联同一公式：

  ```python
              "execution_deadline_at": (
                  (t.started_at + timedelta(seconds=t.execution_timeout_seconds)).isoformat()
  ```
- **影响**：无功能缺陷；但契约「deadline = `started_at` + `execution_timeout_seconds`」被复制到 3 处（含测试），将来改变 deadline 语义需同步修改两处 API 与测试；`resolve_task_timeout_seconds` 已成死代码，与设计 §11「直接执行入口复用同一解析函数」的意图脱节（实际调用点是 `scheduler.py:1569` 的 `select_task_timeout`）。
- **最小动作**：两处 API 改调 `execution_deadline_at`；删 `resolve_task_timeout_seconds`（下次触及这两个文件时顺手）
- **验证**：全仓库检索（本次已执行，结果如上）。改动为纯接线，现有单测可覆盖。

### DEL-04 冻结 harness options 的序列化 helper 被复制成两份
- **判定**：DEFER
- **位置**：`backend/app/api/task_responses.py:41-47`、`backend/app/api/task_runtime_summary_routes.py:170-176`（提交 `ab869c67`）
- **证据**：两个函数逐行相同（`config.get("options")` → 用 `snapshot.harness_key` 取选中项 → `dict(selected) if isinstance(selected, dict) else {}`），分别服务 Task 详情与 runtime-summary。
- **影响**：可维护性风险；当前两处输出一致（选项 schema 无凭据字段，见 `backend/app/core/harness_options.py:53-140`），但若将来需要过滤 / 裁剪选项视图，容易只改一处导致详情页与 runtime-summary 口径漂移。
- **最小动作**：保留 `task_responses._snapshot_harness_options` 一份，另一处 import
- **验证**：逐行比对两段源码（本次已执行）。

### DEL-05 `ci_failure_collector` 调用参数意外去缩进
- **判定**：DEFER
- **位置**：`backend/app/core/ci_failure_collector.py:803`（提交 `cda8e6ee`）
- **证据**：

  ```python
              endpoint=endpoint,
          shared_configuration=shared,
          )
  ```
- **影响**：无功能影响（位于调用括号内续行，`ast.parse` 通过，`tests/unit/test_ci_failure_collector.py` 通过），但属误编辑残留，会干扰后续 diff 阅读与自动格式化。
- **最小动作**：顺手改回 12 空格缩进
- **验证**：`python3 -c "import ast; ast.parse(open('app/core/ci_failure_collector.py').read())"` 通过（本次已执行）。

### DEL-INFO-01 `[V1 遗留]` 取消意图会把「已失败的终态」改写成 CANCELLED 并覆盖原因
- **判定**：DEFER —— V1 遗留；收紧条件有把「用户取消」误判为 FAILED 的风险
- **位置**：`backend/app/core/worker_task_lifecycle.py:1301-1309`（基线 `8081c946^` 同结构）
- **证据**：取消分支只保护 COMPLETED 与 timeout：

  ```python
  if (
      task.status == TaskStatus.CANCELLED or cancellation_requested
  ) and task.status != TaskStatus.COMPLETED and not timed_out:
      if task.status != TaskStatus.CANCELLED:
          task.status = TaskStatus.CANCELLED
          task.error_message = "Cancelled by user"
  ```

  触发窗口真实存在：cancel 路由 Phase A 在 RUNNING 时只写 `cancel_requested_at`（`backend/app/api/task_action_routes.py:141-146`），而 worker 的终态要到 `monitor_container_run` 末尾才 commit（`worker_task_lifecycle.py:1525` 起的同一收尾段）。
- **影响**：用户点击取消时若该次运行其实已以失败终态结束（交付失败 / engine_error / protocol_error），任务展示为 CANCELLED 且原因被替换，V2 新增的结构化交付失败原因不再出现在 `error_message`（仍保留在 `worker_metadata.git_delivery` 与结果卡）。V1 同结构即存在，V2 只是让被覆盖的信息更具体，故按遗留记录、未计入问题清单。
- **最小动作**：加 `and task.status != TaskStatus.FAILED`，但先验证取消导致的非零退出不会被判失败，再改
- **验证**：静态对照基线 `git show 8081c946^:backend/app/core/worker_task_lifecycle.py`（本次已执行）；并发场景未运行验证。

## 3. 逐项核查记录（关键不变量/契约 → 结论 → 依据）

| # | 不变量/契约 | 结论 | 依据（`dev @ cbad9e56`） |
|---|---|---|---|
| 1 | attempt 内终态唯一：`worker.finalization` 之后有且仅有一个 `run.completed`/`run.failed` | 通过 | `deploy/worker-entrypoint/harness/common.sh:355-405`（单一 if/else 只发一个 terminal）；`common.sh:289-306`（缺 harness terminal 时只补发一次）；`backend/app/core/harness_attempts.py:241-262`、`backend/app/core/harness_protocol.py:493-503`（重复 finalization / 顺序错误即 `HarnessProtocolError`） |
| 2 | 终态写入幂等；缺 init / 双 terminal / 未知 terminal = protocol_error | 通过 | `backend/app/core/worker_results.py:526-572`（无 terminal / run.completed 与退出码·信封·git_delivery 冲突 → `protocol_error` + FAILED）；`:306-320`（归档 V2 信封二次校验）；`:574-600`（run.failed 分类） |
| 3 | 生命周期迁移点合法（PENDING→QUEUED→RUNNING→终态）与取消竞争 | 通过 | `backend/app/scheduler.py:1229-1267`（非法 QUEUED 归一化回 PENDING）、`:1442-1462`（重读 `FOR UPDATE` + `populate_existing`）、`:1464-1488`（非 QUEUED 即放弃）、`:1548-1589`（CAS 同事务写 `started_at` + `execution_timeout_seconds`）；cancel Phase A/B 与 claim 共用 Issue 行锁顺序（`api/task_action_routes.py:100-131`、`scheduler.py:1442-1444」） |
| 4 | issue mutex：键、释放、无泄漏 | 通过（键已演进） | 键为 `issues.id`（唯一，语义等价 `project_id:issue_iid`）而非字符串键：`scheduler.py:262-263`、`:1271`、`:1395-1398`、`:548-550`、`:1597-1598`；DB 侧同键 `IssueExecutionLock(issue_id)`；释放点 `:2074-2078`、`:2143`、`:2649-2660`、`:2844-2845`、`:2950-2954`；漂移纠正 `:562-633` |
| 5 | 并发调度下不重复投递 | 通过 | `scheduler.py:1442-1462`（Issue 行锁先于 Task 行锁，顺序固定）、`:1490-1500`（sequence / schedule / predecessor 复核）、`:1548-1575`（`acquire_issue_execution_lock` 失败即放弃，CAS 提交后才启动 worker 线程） |
| 6 | 崩溃恢复：死容器 vs 活跃容器、不误杀其他 Task 容器 | 通过（含 1 处不可达分支） | 正则 `^<prefix>-(\d+)-issue(\d+)$`（`scheduler.py:155-158`，与 `core/worker_runtime.py:818-821` 一致）；按名字枚举 `:2316-2372`、按不可变 `container_id` 恢复 `:2460-2555`；归属校验 `core/worker_task_lifecycle.py:1080-1130`（daemon key + image id + `codify.task_id` + `runtime_bundle_digest`）；`:2330` 的 `task_id is None` 分支不可达（与 `_extract_task_id` 同正则，死代码） |
| 7 | 容器 kill 后后端状态收敛（取消） | 通过 | 两阶段取消路由 `api/task_action_routes.py:100-345`；worker 侧 `core/worker_task_lifecycle.py:1301-1334`（终态 + 容器处置 + 取消通知）、`:862-903`（`stop_container_for_persisted_cancellation`）；容器缺失/不可达时由 deferred recovery 与崩溃恢复收敛（`scheduler.py:2649-2740`） |
| 8 | 超时档位冻结、恢复只用剩余时间 | 通过 | 认领时同事务冻结 `scheduler.py:1567-1576`；直接执行入口复用同一函数 `core/worker_task_lifecycle.py:188-205`；容器 env 用冻结值 `core/worker_runtime.py:434-435`；日志流用剩余值 `core/worker_task_lifecycle.py:1141-1147`、`core/task_timeout.py:113-120`；窗口 `[start,end)` 与跨午夜 `task_timeout.py:60-87`；配置校验 `config.py:242-268` |
| 9 | RUNNING 缺冻结超时 / `started_at` 时 fail closed | 通过 | `core/worker_task_lifecycle.py:189-192`（RUNNING 且无冻结值 → `TaskTimeoutError`）、`:322-338`（终态 + 关闸）、`:1001-1019`（resume 同样拒绝） |
| 10 | 外层 timeout 与用户取消可区分 | 通过 | 后端先写 marker 再停容器（`core/worker_task_lifecycle.py:1189-1213`，`put_archive` 写 `/tmp/codify-runtime/.codify-timeout`）；容器侧 `bootstrap.sh:258-279`（marker → `CODIFY_CANCELLED=0`，否则 =1）；finalizer `harness/common.sh:386-405`；worker 最终判定 `worker_task_lifecycle.py:1470-1490`（timeout → FAILED，不降级为 CANCELLED） |
| 11 | 交付合同校验与 SHA 投影：仅确认远端含完整范围才投影 | 通过 | `core/worker_git_delivery.py:106-271`（schema、attempt 归属、全 40-hex、diff 自洽、`pushed` 要求 `remote_sha == head_sha`、确认状态必须有内容）、`:273-293`（`project_delivery_commit_sha`）、`:295-320`（`completed_delivery_error`）；Backend 三处一致性校验 `core/worker_results.py:404-460`，冲突 → FAILED + `protocol_error`（`:542-546`） |
| 12 | 交付幂等：不重复建 MR、不重复推送 | 通过 | MR 复用 `core/worker_gitlab.py:83-100`（已有 IID）、`:102-122`（按 `source_branch` 查 opened MR）；freeform 后置 MR 走同一路径 `core/worker_task_lifecycle.py:1394-1415`；推送用祖先校验 + `--force-with-lease`（`git-delivery.sh:155-177`、`:300-312`），远端已含 H 即 `already_present`（`git-delivery.py:550-630`） |
| 13 | 远端分叉 / 不可确认不误报成功 | 通过 | `git-delivery.sh:197-345`（`remote_deleted` / `remote_rewound` / `remote_diverged` / `remote_changed` / `remote_unconfirmed`）、`:313-345`（失败后一次有界复查）、`harness/common.sh:338-349`（`delivery.failed` 携带 `push.error`）→ `worker_results.py:591-595`（进入 `run.failed.failure.message`，见 DEL-01 的副作用） |
| 14 | 空变更 / 无改动的成功表达 | 通过 | `main.sh:302-340`：硬归属失败 exit 1；有内容但未确认 exit 1（元数据仍写入）；无内容 → `record not_needed`，`REQUIRE_CHANGES=false` 时 exit 0；`require_changes` 由 Backend 注入（`core/worker_runtime.py:514`） |
| 15 | git 凭据不进 remote URL / argv / 日志 | 通过 | `bootstrap.sh:429-444`（URL 只含 host，凭据写 `/root/.git-credentials`、600 权限）；网络 Git 用隔离环境 `repository-helpers.sh:108-142`（`env -i` + `GIT_CONFIG_GLOBAL=/dev/null` + 显式 credential store + `protocol.ext.allow=never`） |
| 16 | harness 事件在 finalization 前排空、丢失可回填 | 通过（有界，见 §4） | `bootstrap.sh:281-323`（先 `codify_drain_console_tee` 再 finalize，最后打 archive）、`core/worker_task_artifacts.py:309-346`（tail → archive → console/event 回填）、`core/worker_event_projector.py:791-818` + `core/worker_results.py:127-148`（archive 单次尝试，缺失仅告警） |
| 17 | Artifacts 采集边界（大小 / 数量 / 路径） | 通过 | `deploy/worker-entrypoint/artifacts.py:23-53`（固定 runtime 目录 + 体积 / 条目 / 深度上限 + `BASE_ARCHIVE_FILES` 白名单）、`core/worker_task_artifacts.py:17-20`（读取路径为常量，无外部输入拼接） |
| 18 | 新 API 端点的鉴权与信息面 | 通过 | `api/containers.py:603-608`（`get_task_with_access_check`）、`api/task_runtime_summary_routes.py:42-63`（`require_project_access`）；新增 `harness_options` 仅暴露冻结的非密选项（`task_runtime_summary_routes.py:170-176`）；`api/tasks.py:620-656`（`git_delivery.commit_url` 仅在确认态生成） |
| 19 | V1 任务只读（execute / schedule / retry / update / override 全禁） | 通过 | 统一守卫 `api/task_operations.py:93-108`；调用点 `api/task_action_routes.py:95,370,418,484`、`api/task_creation_service.py:142`（retry）、`api/task_update_service.py:94`（update）；cancel 仅对 PENDING/QUEUED 加门禁（RUNNING 允许记录意图，`task_action_routes.py:88-96`）；恢复侧 `scheduler.py:3117`、`core/worker_task_runner.py:112-142` |
| 20 | Scheduler 健康端点暴露执行模式且不阻塞主循环 | 通过 | `scheduler_service.py:43-63`（独立 uvicorn，`ws="none"`，`install_signal_handlers` 置空）、`:88-105`（`should_exit` 后 await） |

## 4. 局限与未验证项

- **无真实运行环境**：本次没有任何真实 Docker / Scheduler / Worker 容器运行，所有取消、超时、崩溃恢复、推送冲突的并发场景均为静态推理（已在问题清单中标注「未运行验证」）。未运行全量测试套件；仅运行了 §0 列出的 5 组窄范围单测（均通过）。
- **DEL-01 的前提未实测**：未在真实 Pi / OpenCode 运行上确认「归档原始事件流中存在 provider 错误记录」这一前提；该前提由 `backend/app/core/task_failure_details.py:88-110` 的既有注释与 `tests/unit/test_task_failure_details.py` 的夹具间接支持。
- **DEL-02 的触发条件未实测**：未用浅克隆 / partial clone 的真实交付数据复现 `merge-base --is-ancestor` 返回「不可判定」的场景。
- **worker shell 负向路径**：`deploy/worker-entrypoint/git-delivery.sh`、`repository-helpers.sh` 的行为由仓库内真实本地 git 测试（`backend/tests/unit/test_worker_git_delivery.py`）覆盖并通过，但「push 被服务端拒绝 / 网络中断 / 并发创建分支」等路径未在容器内复现，仅做静态链路核对。
- **事件 archive 丢失的下界（T02 范围）**：`flush_task_artifacts` 先 tail 再回填 archive（`core/worker_task_artifacts.py:309-346`），而 archive 由容器 EXIT trap 在 finalization 之后生成（`bootstrap.sh:313-323`）。若 archive 因体积超限被省略（`artifacts.py:28` 的 640 MiB 上限、`bootstrap.sh:243-252`），容器退出前最后约一个轮询周期（2s，`core/worker_task_artifacts.py:267`）内的事件将失去第二来源。本专题仅记录，未计入问题清单。
- **已隔离但未记为缺陷的观察**：`scheduler.py:2330` 的不可达分支；`_harness_availability_gate`（`:1735-1788`）与 `_fail_task_for_execution_identity`（`:1921-1932`）对 QUEUED 任务未做状态 CAS 即 commit 终态（与 V1 `_fail_task_for_runtime_check`（`:1886-1920`）同构，属既有模式）；`worker_task_lifecycle.py:1517-1545`（usage ledger、`_save_task_metadata_from_container`、`_update_mr_description_for_issue`）中的副作用均在自身 try/except 内，未发现「终态已被 commit 后再被 `fail_execute_task` 覆盖」的可达路径。
