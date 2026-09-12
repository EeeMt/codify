# 01 命令平面与并发门禁 —— Code Review

> 审查对象：`dev @ cbad9e56`（未提交改动不参与审查） · finding 前缀 `CMD-` · 2026-09-12

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `git diff 8081c946^..cbad9e56`（477 commits / 437 files / +74,905 / -3,855） |
| 主文件（V2 新增，逐行通读 HEAD 全文） | `backend/app/core/task_harness_commands.py`（+508）、`backend/app/core/worker_command_pump.py`（+909）、`backend/app/core/task_command_gate.py`（+245）、`backend/app/api/task_command_routes.py`（+306）、`backend/app/core/harness_execution_policy.py`（+246） |
| 改动文件 | `backend/app/core/harness_attempts.py`（+201/-5，本专题只看 attempt 身份/复用与 attempt 行锁部分，事件 ingest 主体归 02） |
| 模型/迁移 | `backend/app/models.py`（`TaskHarnessAttempt`/`TaskHarnessCommand`，+178/-13）、`backend/alembic/versions/074_open_harness_v2.py`（表+索引+CHECK）、`075_pi_command_dispatch_journal.py`（列+状态枚举+一致性 CHECK） |
| 调用方（跨模块核查） | `backend/app/core/worker_event_projector.py`（gate 迁移 459-466、`_command_display_fields`、742-748）、`backend/app/scheduler.py`（pump 启动 3016-3032 / 3154-3158；`close_task_control_gates` 2144/2582/2700/2833）、`backend/app/core/worker_task_lifecycle.py`（attempt 创建 496-511；close 332/1010/1284）、`worker_task_runner.py:138`、`backend/app/api/task_operations.py`（access check）、`backend/app/dependencies/project_access.py` |
| 容器侧契约实现（只读交叉核对） | `deploy/worker-entrypoint/harness/control_client.py`（+130）、`adapters/pi_owner.py`（+519，仅 `_dispatch_locked`/native id/reopen 语义）、`adapters/pi_bridge.py:146-205`、`adapters/pi_events.py:580-615` |
| 契约依据 | `docs/architecture/open-harness-v2-schemas.md` §4/§4.1/§4.2/§4.3/§8、`docs/architecture/open-harness-v2.md` §6.3/§9.3、`docs/architecture/open-harness-v2-phase1-design.md` §2.2、`docs/superpowers/plans/2026-08-21-open-harness-v2-implementation-plan.md` |
| 审查方法 | 静态通读 + 冻结契约逐条对照 + 跨模块调用方/消费者追踪（含 pi_owner↔pump 的 `native_request_id`/状态码跨边界核对）+ 仓库外 `/tmp` 最小复现（用仓库真实 ORM 模型与 helper，未改仓库任何文件）+ 窄范围单测 |
| 已运行验证 | `cd backend && .venv/bin/python -m pytest tests/unit/test_task_harness_commands.py -q` → **18 passed, 17.71s**；`tests/unit/test_worker_command_pump.py -q` → **32 passed, 54.33s**；`/tmp/saprobe/{probe.py,race2.py}`（SQLAlchemy 2.0.50 identity-map 与 CHECK 约束语义复现，见 CMD-01） |
| 未覆盖 | 真实 Docker 容器 / Pi CLI / 真实 Pi turn-boundary ACK（无法实测 1800s 级等待与租约过期抢占）；PG 实例上的并发与锁行为（只用静态推理 + SQLite 复现 ORM 语义）；多 scheduler 进程部署形态；前端命令面板的 UX/状态映射（归 12）；模型 provider 与 Kit 制品（归 08/09/10） |

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 1 |
| FIX_IF_CHEAP | 3 |
| DEFER | 3 |
| ACCEPT/CLOSE | 6 |

命令平面主干契约实现质量高：幂等查重严格优先于资格检查、`sequence_no` 在 Task→attempt 行锁内分配、先持久化 `dispatching` 再 native send 的 crash boundary，以及 PUT 与 `accepting→closing` 的线性化，均在单测与推演中固定，未发现“closing 后永远 queued”窗口。**FIX_NOW 只有 CMD-04**（长用户名下每次 PUT 直接 500，一条迁移可修），其余为 3 条 FIX_IF_CHEAP、3 条 DEFER。6 条 ACCEPT/CLOSE（CMD-02/07、CMD-INFO-01/02/03/05）本阶段书面接受并关闭：本系统是单 `codify-scheduler`、无可用性要求、允许停机与硬切的内网 beta，且 command 行不入统计，为其补防护属过度防御。

## 2. 问题清单

### CMD-04 `created_by` 列宽 64 < `username` 上限 255，长用户名使 PUT 直接 500

- **判定**：FIX_NOW —— 主干路径可用性故障，非边缘情形
- **状态**：已修复（`7794eb92`）：列宽 64 → 255 + 迁移 `080_task_command_created_by`
- **位置**：`backend/app/models.py:737`（对照 `:1480`）、`backend/alembic/versions/074_open_harness_v2.py:103`、`backend/app/api/task_command_routes.py:69-72`（提交 `cbad9e56`）
- **证据**：`TaskHarnessCommand.created_by = String(64)`；`User.username = String(255)`（`models.py:1480`，仓库其它 username 列一律 255：`models.py:125/369/1435/1537`）；`_created_by()` 直接把 `current_user.username` 作为 `created_by` 写库（`task_command_routes.py:69-72` → `:218` → `task_harness_commands.py:286`）。PostgreSQL 对 `varchar(64)` 溢出抛 `StringDataRightTruncation`（SQLAlchemy `DataError`，属 `DBAPIError` 但非 `IntegrityError`），`put_command` 的 `except DBAPIError` 只在 SQLSTATE `40P01` 时重试、否则 re-raise（`:234-242`）→ 500。
- **影响**：GitLab/OIDC 用户名长度 > 64 的用户（自建 GitLab 允许至 255）**完全无法发送命令**，每次 PUT 500；SQLite 不校验长度，故单测不会暴露该问题。
- **最小动作**：`created_by` 放宽到 `String(255)` + 一条迁移（与仓库其它 username 列一致）
- **验证**：静态（列宽/异常类型对照）；未在 PostgreSQL 上用 65 字符用户名实测。

### CMD-01 command 状态 helper 的 “CAS” 判定读本会话缓存行，跨会话终态只能靠 CHECK 约束挡下

- **判定**：FIX_IF_CHEAP —— 后果限于审计层，command 行不入统计
- **位置**：`backend/app/core/task_harness_commands.py:324-346`（另 `:348-378`、`:380-407`、`:409-427`、`:429-441`、`:443-467`）、`backend/app/database.py:29-35`（提交 `cbad9e56`）
- **证据**：
  - 六个 helper 的写法都是“`select(...).with_for_update()` / `db.get(..., with_for_update=True)` 取出 ORM 行 → 判 `command.status` → 直接改属性 → `flush()`”。`with_for_update` 只加 DB 行锁，**不会刷新 identity map 中已加载对象的位置**；仓库 session 全部 `expire_on_commit=False`（`database.py:32`，`scheduler.py:3019/3085`），因此同一 session 内已加载过的行会一直读旧值，而 flush 产出的是 `UPDATE ... WHERE command_id = ?`（无状态守卫）。
  - 仓库外复现（`/tmp/saprobe/race2.py`，用仓库真实模型与真实 helper，仅 sqlite 内存/文件库）：
    - `A 会话` 读出 `dispatching` 行并 `commit()`（pump 在 native send 前的边界）→ `B 会话` 用 `write_command_outcome_unknown()` 把它终态化为 `outcome_unknown` 并 commit → `A` 再调 `write_command_delivery()`：**返回值仍走“判定通过”分支**，flush 抛 `IntegrityError: CHECK constraint failed: ck_task_harness_command_unknown_consistency`，行状态保持 `outcome_unknown`。
    - 反向（`requeue_pre_send_failure` 把已被 gate 终态化的行改回 `queued`）同样被 `ck_task_harness_command_queued_consistency` / `ck_..._unknown_consistency` 挡下。即：**终态没被写坏，但那是因为 074/075 的 CHECK 约束，而不是因为代码里的 CAS 判定**。
  - 触发路径（可达，非理论）：pump 在 `transport()` 内最长等待 `CONTROL_TRANSPORT_TIMEOUT_SECONDS=1890s`（`worker_command_pump.py:63`，注释明确说明 steer/follow_up 只在 Pi 下一个 turn boundary 才 ACK）；此窗口内 cancel / timeout / 容器退出会走 `close_task_control_gates` → `close_control_gate`（`task_command_gate.py:98-166`，调用点 `scheduler.py:2144/2582/2700/2833`、`worker_task_lifecycle.py:332/1010/1284`、`worker_task_runner.py:138`），把在途 `dispatching` 行写成 `outcome_unknown`。
  - 异常落点：写入抛出的 `IntegrityError` 不在 `dispatch_one_command` 的 `try` 内，会冒泡到 `run_pump_until_task_ends` 的 `except Exception`（`worker_command_pump.py:144-152`）→ 整轮 `rollback()` + `logger.exception("Command pump cycle failed ...")`。
- **影响**：竞态发生时，该轮已完成但未提交的写入（`native_sent_at` / `native_request_id` / `native_ack_at`、`_clear_pending_follow_up`、pump 侧控制事件）全部回滚丢失；scheduler 日志出现 ERROR 级堆栈（每命中一次一条）；命令行最终仍为 gate 写的终态，即“Pi 实际已 ACK 的命令”在审计上被记为 `outcome_unknown`。此外 helper docstring/契约 §4.1 宣称的“CAS / 终态不可变”与实现不符，一旦将来放宽任一 CHECK 约束，同类竞态立即变成**静默覆写终态**（`delivered_at` 与 `outcome_unknown_at` 并存等非法组合也会立刻可见）。
- **最小动作**：只给会与 gate 竞争的 3 处终态写 + `requeue_pre_send_failure` 加 `WHERE status = :expected` 守卫（照抄 `task_command_gate.py:33-59` 既有写法）；不必重写全部 6 个 helper，也不必上 `populate_existing`
- **验证**：已复现（仓库外，真实 model+helper，SQLite）；未在 PostgreSQL 实例上执行——PG 对 CHECK 违规同样抛 IntegrityError，故结论一致但属推断。现有单测只覆盖单会话 transition（`test_task_harness_commands.py:503-540`、`test_worker_command_pump.py:1168-1200` 用同一 session 完成 claim 与 delivery），无跨会话终态竞态用例。

### CMD-03 `retry` 结果无上限、无退避、无审计，队首可被无限重试并阻塞整条队列

- **判定**：FIX_IF_CHEAP —— owner 不可达期间本就投不出去，非正确性缺陷
- **位置**：`backend/app/core/worker_command_pump.py:773-777`（另 `:94-99`、`task_harness_commands.py:429-441`）（提交 `cbad9e56`）
- **证据**：
  - 容器侧 `control_client._forward_to_bridge` 在 Unix socket 连接失败时返回 `{"status": "retry", "rejection_code": "control_owner_unreachable"}`（`control_client.py:104-113`）。
  - pump 的处理是 `await requeue_pre_send_failure(...)` → `return "queued"`，`run_pump_cycle` 随即 `break`（注释“Pre-send retry keeps this exact head in place; do not spin it”，`:885-887`），下一轮（`interval_seconds=2.0`，`:99`，scheduler 未传覆盖值）再次投递同一条。
  - `delivery_attempts` 只在 `begin_command_dispatch` 自增（`task_harness_commands.py:404`），**全仓库无任何读取或上限判断**（`grep delivery_attempts`：仅模型默认值、迁移、单测与文档）；retry 分支也不写任何 `TaskLog`（对比同函数其他终态分支都会 `_record_*`）。
  - 契约侧无冲突：§4.1 允许“proven pre-send failure → queued”，但未规定次数。
- **影响**：Pi owner 崩溃/尚未就绪而 Worker 容器仍存活期间，pump 每 ~2s 对 Docker API 做一次完整控制往返（`put_archive` + `exec_create` + detached `exec_start` + `get_archive` 轮询，`:390-470`），持续到容器退出或任务超时；同时因严格顺序（§4.3），卡住的队首会一直挡住后续命令（含 follow_up）；用户侧只看到该命令停在 `queued`（公开投影无重试次数/原因），没有任何诊断事件，属“静默不收敛”。
- **最小动作**：retry 分支加 1 行 `logger.warning`（含 `delivery_attempts`）；不加退避/上限
- **验证**：静态推理 + `delivery_attempts` 只写不读的全局 grep；未用真实容器复现（需 owner 不可达且容器存活）。

### CMD-06 pump 持久化 `native_rejected`（非冻结枚举），同一拒绝在 API 与事件流显示不一致

- **判定**：FIX_IF_CHEAP —— 不改 bridge 协议，只补公开文案
- **位置**：`backend/app/core/worker_command_pump.py:752-762`、`backend/app/core/task_harness_commands.py:42-59`、`backend/app/core/harness_protocol.py:43-54`（提交 `cbad9e56`）；跨界对照 `deploy/worker-entrypoint/harness/adapters/pi_owner.py:379-386`、`pi_events.py:603-613`、`pi_bridge.py:146-155`
- **证据**：pi_owner 对原生失败返回 `rejection_code="native_rejected"`；pump 取 `outcome.get("rejection_code") or "delivery_outcome_unknown"` 原样落库（列 `String(64)` 无枚举校验），但 `REJECTION_CODES`（§4.2 冻结枚举，`harness_protocol.py:43-54`）与 `PUBLIC_REJECTION_MESSAGES` 都没有该值 → API 投影退化为 `command_rejected` / “The command was rejected.”。同时 `pi_bridge._attach_ack` 不携带 `rejection_code`，translator 于是用默认值 `delivery_outcome_unknown` 发出 `control.command.rejected` 事件（`pi_events.py:603-613`）→ 同一拒绝在事件流显示为“delivery outcome unknown”，与命令行 `rejected` 自相矛盾。
- **影响**：审计/排障时同一命令在事件流与命令行给出不同结论；`native_rejected` 落在冻结枚举之外，后续按 `REJECTION_CODES` 做统计/映射的消费者会漏掉它（当前靠 fallback 兜底，无泄漏风险）。
- **最小动作**：`PUBLIC_REJECTION_MESSAGES`（±`REJECTION_CODES`）加 `native_rejected`，2 行
- **验证**：静态跨模块追踪（pi_owner → control_client → pump → API/事件投影）；未运行容器。

### CMD-05 空文本命令被 API 接受、被容器内 client 拒绝，且公开消息套用错误的 code 文案

- **判定**：DEFER —— 前端已拦截（`TaskSteeringPanel.vue:48,204`），仅手搓 API 可触发
- **位置**：`backend/app/core/harness_protocol.py:682-690`、`deploy/worker-entrypoint/harness/control_client.py:66-71`、`backend/app/core/task_harness_commands.py:52`（提交 `cbad9e56`）
- **证据**：`is_valid_command_text("")` 只为长度（≤4000 UTF-16 units）与 surrogate 检查，空串/纯空白返回 True → PUT 返回 201 且落库 `queued`（占用一个 `sequence_no`）；容器内 client 对 `not text.strip()` 返回 `{"status":"reject","rejection_code":"invalid_command_type"}`；`PUBLIC_REJECTION_MESSAGES["invalid_command_type"] = "The command type is invalid."`（`task_harness_commands.py:52`）。
- **影响**：用户发送空文本时先得到成功 201，随后命令变为 `rejected`，公开原因显示“命令类型无效”（类型其实是合法的），结论与事实不符；REST 契约 §4.3 只冻结了上限，未声明空文本合法。
- **最小动作**：不做；若顺手，1 行把空文本并入既有 422（文案偏差可接受）
- **验证**：静态（两侧校验对照）；未运行容器。

### CMD-INFO-04 `create_task_attempt` 复用已有 attempt 时忽略传入的 `control_state="starting"`

- **判定**：DEFER
- **位置**：`backend/app/core/harness_attempts.py:57-73`、`backend/app/core/worker_task_lifecycle.py:496-511`（提交 `cbad9e56`）
- **证据**：`create_task_attempt` 命中已存在 attempt 时直接 `return existing`（`:57-62`），不重置 `control_state`；调用方只在**新建**时传 `control_state="starting"`。pump 侧只认 `starting→accepting`（`worker_command_pump.py:238-290`）与 `accepting/closing`（`:200-211`）。
- **影响**：若存在“容器仍存活但 gate 已被 `close_task_control_gates` 置为 `closed`”的恢复/复用路径，复用后的 attempt 将永远无法被 pump claim，也不会有 `accepting`：所有 PUT 恒 409、命令永不投递。我未找到该路径（retry 走 `task_creation_service.retry_task_record` 新建 task → 新 attempt；resume 只针对存活容器且此时 gate 仍为 `accepting`），故记为待确认疑点。
- **最小动作**：无；真出现再加一行断言
- **验证**：静态 + 调用点 grep（`create_task_attempt` 全仓库仅一处调用）；未构造运行时用例。

### CMD-INFO-06 长会话下的 identity map 陈旧同样作用于 projector 的 gate 判定（CMD-01 同一根因）

- **判定**：DEFER
- **位置**：`backend/app/core/worker_event_projector.py:459-466`、`backend/app/core/task_command_gate.py:20-26`（提交 `cbad9e56`）
- **证据**：projector 的 ingest 会话是 per-task 长会话（`tail_event_jsonl` 每 chunk `commit()`，`expire_on_commit=False`）；`ingest_canonical_event` 用 `select(...).with_for_update()` 取 attempt，但按 CMD-01 证明的语义，**已加载对象不会被刷新**，`begin_control_drain` 依据的 `attempt.control_state` 可能是旧值。我逐一推演了各方向（'starting' 覆盖 'accepting' 写成 'closing'、'closed'/'closing' 抑制 drain）均得到与新鲜值相同或更安全的行为，未构造出有害交错。
- **影响**：当前无可证后果；但与 CMD-01 同源，若将来 `begin_control_drain`/`close_control_gate` 增加基于状态的分支（例如区分 `starting` 与 `accepting`），会立刻变成真实缺陷。
- **最小动作**：随 CMD-01 一起把 gate 写入改守卫式，不单独修
- **验证**：静态 + `/tmp/saprobe/probe.py` 的 ORM 语义复现；未运行并发用例。

### CMD-02 单 dispatcher 租约 TTL(120s) 远短于 transport/ACK 上限(1890s) 且从不续租

- **判定**：ACCEPT/CLOSE —— 单容器部署下 TTL 只是崩溃回收层
- **位置**：`backend/app/core/worker_command_pump.py:53`、`:57-71`、`:183-236`（提交 `cbad9e56`）；对照 `deploy/worker-entrypoint/harness/control_client.py:27`
- **证据**：
  - `DEFAULT_LEASE_TTL_SECONDS = 120`（`:53`）写入 `command_dispatch_expires_at`（`:220-232`）；而 `CONTROL_TRANSPORT_TIMEOUT_SECONDS = 1890`、`CONTROL_RESULT_TIMEOUT_SECONDS = 1860`（`:63/69`），容器内 `control_client.SOCKET_TIMEOUT_SECONDS = 1830`（`control_client.py:27`），Pi owner 侧 `NATIVE_COMMAND_ACK_TIMEOUT_SECONDS = 1800`。代码注释本身写明“a ``steer``/``follow_up`` is only ACKed at Pi's next turn boundary ... can be many minutes”（`:61-63`）。
  - `_claim_next_attempt` 的 where 允许 `command_dispatch_expires_at < now` 时**任何** owner 抢占（`:200-211`），docstring 把该情形定义为 “crash recovery”；全仓库除 claim 写入外没有任何续租调用（`grep command_dispatch_expires_at` 仅 `:183-236`、`:517-527`）。
  - 单进程内同一 task 只有一个 pump（`scheduler.py:3026-3032` owner=`scheduler-thread-{id}`、`3154-3158` owner=`scheduler-resume-{id}`；`_crash_recovery` 只在启动跑一次且用 `_running_tasks` 去重，`scheduler.py:459`）。
- **影响**：当同一 attempt 存在两个存活 dispatcher（第二个 scheduler 进程 / 残留进程——系统对此无防护，而租约机制本身就是为了在多 dispatcher 下保证单一 owner）时，第二个 owner 会在第一条命令仍处于 native-send 等待期（可达 30 分钟）时抢到 attempt，把队首 `dispatching` 判为 crash recovery → `outcome_unknown`（`:559-570`），随后**下一轮直接投递后一条命令**：同一 attempt 同时有两帧 native 在途、可能乱序到达 Pi，违反 §4.3 冻结的“前一条未进入终态不得领取后一条 / 同一 attempt 任一时刻只有一个 dispatcher 处理队首”。第一条命令的真实 ACK 又会因 CMD-01 被 CHECK 约束挡下而丢失。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态推理 + 常量对照；未运行（需两个存活 dispatcher + 真实容器/长 ACK）。

### CMD-07 `_drop_lease` 是死代码，租约从不显式释放

- **判定**：ACCEPT/CLOSE —— 无释放需求，死代码无行为危害
- **位置**：`backend/app/core/worker_command_pump.py:517-527`（提交 `cbad9e56`）
- **证据**：全仓库 `grep -rn "_drop_lease" backend/` 只有定义处，无调用；租约仅在 `_claim_next_attempt`/`_promote_starting_attempt` 写入，attempt 收敛 `closed`（`:639-641`、`task_command_gate.py:98-166`）或 pump 退出路径都不清理 `command_dispatch_owner/expires_at`。
- **影响**：阅读租约语义时会被误导（看起来有释放路径）；owner 消失后残留租约只能等 TTL 过期才能被其它 owner 接管，间接放大 CMD-02 的抢占判定。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：grep（只读）。

### CMD-INFO-01 projector 路径会写 command 行状态，与 §4.1/§8 冻结文字冲突（有明确意图）

- **判定**：ACCEPT/CLOSE —— 与 EVT-01 同一处代码，有意设计
- **位置**：`backend/app/core/worker_event_projector.py:459-466`、`backend/app/core/task_command_gate.py:98-166`（提交 `cbad9e56`）
- **证据**：`schemas §4.1` 冻结“Canonical control event、projector、SSE 日志不参与 command 行状态写入”，§8 亦写“project 不使用 projector 参与这些状态迁移；gate 迁移由 Worker/pump 在 attempt 行锁内进行”；实现中 projector 在 `run.completed`/`run.failed` 时调用 `close_control_gate`，后者把 queued 行写成 `rejected`、`dispatching` 行写成 `outcome_unknown`（`:118-166`）。模块 docstring 写明这是 “shared by projector and lifecycle paths” 的**有意设计**。
- **影响**：无数据损坏；若不这样做，harness 终止时未发送的命令会永久停在 `queued`（正是 §8 禁止的）。但契约文档与实现不一致，`harness_attempts` 的“唯一 writer”表述会被误读。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态阅读 + 调用点 grep。

### CMD-INFO-02 closing 收敛（drain 判定 + close IPC）未持有 attempt 行锁

- **判定**：ACCEPT/CLOSE
- **位置**：`backend/app/core/worker_command_pump.py:885-900`（提交 `cbad9e56`）
- **证据**：`_claim_next_attempt` 在 cycle 开始持 attempt 行锁（`:229-236`），但 `dispatch_one_command` 在 native send 前 `await db.commit()`（`:695`）会释放该锁；cycle 尾部的“是否还有队首 → `_close_drained_attempt`（写 `control_state='closed'`，`:639-641`）”因此不在行锁内，与 §8 的“gate 迁移在 attempt 行锁内进行”不符。
- **影响**：我尝试构造有害交错未成功——该分支只在 `control_state == "closing"` 时进入，而 `create_command` 要求 `accepting`（`task_harness_commands.py:264`），所以排空判定后不可能插入新命令；唯一竞争者是 `reopen_control_after_native_turn_start`（`closing→accepting`），它要求 `awaiting_follow_up_turn=True` 且 pending id 匹配，而该 flag 为真时 pump 不会进入 close 分支（`:888`）。故记录为“需人工确认”的疑点，不作为缺陷。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态交错推演；未运行并发用例。

### CMD-INFO-03 pump 任务取消不会中断已启动的 `docker exec` 线程

- **判定**：ACCEPT/CLOSE —— 线程有界，不阻塞重启/停机
- **位置**：`backend/app/core/worker_command_pump.py:472-497`、`backend/app/scheduler.py:3033-3041`（提交 `cbad9e56`）
- **证据**：transport 通过 `asyncio.wait_for(asyncio.to_thread(_exec), timeout=1890)` 执行阻塞 Docker SDK 调用；scheduler 在 `finally` 里 `pump_task.cancel()` 后仅 `await pump_task`，不 join 线程。取消时 `_exec` 可能仍在对 Docker API 轮询（最长 ~31 分钟）后才结束。
- **影响**：每次取消留下一个后台线程（有界：每 task 一个）继续做完当前控制往返；此期间已 detached 的 exec 仍可能把帧写进容器，但其命令行状态已由 gate 收敛为 `outcome_unknown`（fail-closed），不会重复注入。属资源/退出卫生问题。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态阅读（asyncio 取消语义）；未在真实 Docker 上验证线程存活时长。

### CMD-INFO-05 transport 作用域不符时把“可证明未发送”的帧记为 `outcome_unknown`

- **判定**：ACCEPT/CLOSE —— 语义洁癖，非实际缺陷
- **位置**：`backend/app/core/worker_command_pump.py:118-130`（提交 `cbad9e56`）
- **证据**：`_task_scoped_transport` 在 `frame["task_id"] != task_id` 或 attempt 不属于本 task 时返回 `{"status": "unknown", "rejection_code": "wrong_attempt"}`；`dispatch_one_command` 对 `unknown` 一律走 `write_command_outcome_unknown`（`:781-789`），且固定使用 code `delivery_outcome_unknown`。
- **影响**：这是**发送前**就能证明的失败，却被记为“跨 native-send 边界结果不可证”（§4.1 对 `outcome_unknown` 的定义），语义上更接近 `wrong_attempt` 的确定性拒绝。该分支在当前调用链中不可达（frame 的 task_id/attempt 由本函数构造），无实际后果。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态阅读 + 调用链核对。

## 3. 逐项核查记录（已确认的关键不变量）

| # | 不变量/契约 | 结论 | 依据 |
|---|---|---|---|
| 1 | 幂等查重优先于新建资格检查（ID 已存在即使 task 已 closing/terminal 仍返回原状态） | 通过 | `task_harness_commands.py:190-207` 在 Task/attempt/capability/gate 全部检查之前；`:193-199` 返回 `existing_same` + 原 `sequence_no` |
| 2 | 同 ID 不同 payload → 409；同 ID 同 payload → 200 | 通过 | `:192-207`（digest 含 `task_id/attempt_id/type/payload`）→ `task_command_routes.py:220-229` 409 / `:253` 200 vs 201 |
| 3 | 唯一键并发竞争后回读再判，不 500 | 通过 | `:292-315` 捕获 `IntegrityError` → `rollback()` → `db.get()` 重读 → 同 digest 返回 `existing_same`，否则 `existing_conflict`。`db.rollback()` 会连带回滚 `next_command_sequence` 自增，故失败方不占号 |
| 4 | payload_digest 覆盖全部影响语义的字段 | 通过 | `harness_protocol.py:693-703`：`canonical_json_bytes`（sort_keys + 紧凑分隔符 + `ensure_ascii=False`）+ `{task_id, attempt_id, type, payload}`；首版 payload 仅 `{"text": str}`，无浮点；UTF-16 units 上限与 surrogate 拒绝在 `:682-690`。同一 `command_id` 跨 task 复用因 digest 含 `task_id` 必落 409，不泄露他人命令内容 |
| 5 | 文本超长（>4000 UTF-16 units）确定性拒绝 | 通过 | `harness_protocol.py:682-690`（API 侧，422 `payload_too_large`）；容器侧 `control_client.py:72-74` 用 Python 码点计数，因 UTF-16 units ≥ 码点，不会出现“API 放行/容器拒绝”的长度不一致 |
| 6 | `sequence_no` 在 attempt 行锁内单调分配、从 1 起、无跳号/复用 | 通过 | Task 行锁 `:209-220` → attempt 行锁 `harness_attempts.py` 式 `_load_current_attempt(for_update=True)`（`task_harness_commands.py:233`）→ 分配 `:274-291`；唯一键 `uq_task_harness_command_attempt_seq`（`models.py:782-784`，迁移 `074:135-137`）；所有拒绝路径都在分配前返回，失败分支回滚自增 |
| 7 | 单 dispatcher：同一 attempt 任一时刻只有一个 owner（正常单进程部署下） | 通过 | `_claim_next_attempt` 用 `with_for_update(skip_locked=True)` + lease（`:183-236`），单 task 单 pump（`scheduler.py:3026-3032/3154-3158`）。**跨进程/长 ACK 场景见 CMD-02** |
| 8 | 先持久化 `dispatching` 再 native send（commit-before-send） | 通过 | `begin_command_dispatch`（`:380-407`）→ `dispatch_one_command` 内 `await db.commit()`（`:690-695`）在 `transport()` 之前，注释与单测 `test_pump_recovers_dispatching_as_outcome_unknown` 固定该边界 |
| 9 | 只有能证明尚未 native send 的失败才可回到 `queued` | 通过 | `requeue_pre_send_failure:429-441` 要求 `status=="dispatching"` 且 `native_sent_at is None`；transport 异常（无法证明未发送）走 `:714-719` → `outcome_unknown`，不 requeue |
| 10 | `outcome_unknown` 只用于跨 native-send 边界且不可证的场景 | 基本通过（1 处不可达例外） | 正常路径：`:714-719`（异常）、`:781-789`（未识别 outcome）、`:559-570`（dispatcher recovery）、`task_command_gate.py:140-166`（gate closed 时在途）；例外见 CMD-INFO-05 |
| 11 | 终态不可变（delivered/rejected/outcome_unknown 不可重开） | 通过（但保障来自 DB 约束，非代码 CAS） | helper 的守卫判定不可靠（CMD-01）；实际由 `ck_task_harness_command_delivered/rejected/unknown/queued_consistency` 拦截（`models.py:767-781`，迁移 `074:107-131` + `075:44-67`） |
| 12 | `delivery_attempts` 上限/退避 | 未实现 | 只写不读（`task_harness_commands.py:404`），见 CMD-03 |
| 13 | gate 拒绝路径齐全：`starting/closing/closed/disabled` 均拒绝新命令 | 通过 | `task_harness_commands.py:264-272` 仅 `accepting` 放行，返回 409 `control_gate_closed`；`disabled`（无 capability 的 harness）在此之前已被 `bundle_supports_command` 以 `unsupported_harness` 拒绝（`:252-263`，能力读自冻结 manifest：`:100-120`） |
| 14 | `closing` 排空后才收敛：先排空 queued/dispatching，再发唯一 close IPC，ACK 后才 `closed` | 通过 | `run_pump_cycle:885-900` → `_load_head_command` 无队首且未等 follow-up turn → `_close_drained_attempt:616-643`（IPC 非 ack 则保持 `closing` 供下轮重试） |
| 15 | settled 触发 `accepting→closing`；已 ACK 的 follow-up 使 gate 重开 `accepting` | 通过 | `worker_event_projector.py:459-460`（agent_settled → `begin_control_drain`）、`:742-748`（`pi_follow_up_turn_started` → `reopen_control_after_native_turn_start`）；跨边界值一致：pump 写入 `pending_follow_up_native_id = str(1_000_000+seq)`（`worker_command_pump.py:672-689`）＝ pi_owner 回显的 `native_request_id`（`pi_owner.py:347-353/386`）＝ 诊断事件 `native_id`（`pi_events.py:1054`） |
| 16 | cancel/timeout/容器退出：拒绝剩余 queued、在途 `dispatching` 收敛为终态 | 通过 | `close_control_gate`（`task_command_gate.py:98-166`）与 `request_force_close_after_unknown_follow_up`（`:169-227`）都拒绝 queued + 终态化 dispatching，并写 `control.command.rejected/outcome_unknown` 审计事件；调用点见 §0 |
| 17 | PUT 与 `accepting→closing` 竞争的线性化不会留下“永久 queued” | 通过 | PUT 先锁 Task 行再锁 attempt 行（`task_harness_commands.py:209-220/233`），gate 迁移方持 attempt 行锁（pump claim 或 `close_control_gate` 的 `with_for_update`）→ 二者串行：要么 PUT 先提交、随后被 drain 或确定性拒绝，要么 PUT 读到非 `accepting` 得 409 |
| 18 | 容器恢复后未确认命令继续投递；已 `dispatching` 的不得重放 | 通过 | resume 时 pump 以新 owner 等租约过期后接管（`:200-211`）；队首 `dispatching` → `_recover_dispatching_head:559-570` → 终态 `outcome_unknown`（不重投），并有单测覆盖（`test_worker_command_pump.py:1168+`，已运行通过） |
| 19 | 崩溃在 `dispatching` 状态不会永久卡住（有 lease 过期回收） | 通过 | lease 过期即可被接管（`:200-211`）→ 判为 recovery 并终态化，随后继续后续队首；Task 184 样本（`docs/superpowers/evidence/2026-09-01-open-harness-v2-r2-candidate.md:71`）记录该链路已实测 |
| 20 | attempt 切换后旧 command 不得投给新 attempt | 通过（且当前不存在 attempt 切换） | `_load_head_command:532-556` 同时约束 `attempt_id` 与 `task_id`（并 join attempt 校验 task 归属）；`create_task_attempt` 只复用 attempt 且 `attempt_no` 恒为 1（`harness_attempts.py:64-73`），retry 走新建 Task（`task_creation_service.py:352-372`：`retry_source_task_id=original_task.id`，`:359`） |
| 21 | API 鉴权：谁能对哪个 task 发命令 | 通过 | `require_project_access_scope`（依赖 `require_authenticated_context`）+ `get_task_with_access_check`（默认 `require_operator=True` → project access + task initiator/platform admin，`task_operations.py:35-79`、`task_helpers.py:162-216`），与 cancel/execute/schedule 同级；匿名访问在 OIDC 启用时被拒 |
| 22 | 错误码与契约一致（409/404/403/422）且不泄露内部诊断 | 通过 | 映射表 `task_command_routes.py:139-158`：`task_not_running/attempt_mismatch/unsupported_harness/control_gate_closed`→409、`payload_too_large/invalid_command_id/invalid_command_type`→422、`not_authorized`→403；跨 task 的 command_id 404（`:295-301`）；内部 `rejection_message`（如冻结 Bundle 文案）经 `public_rejection` 投影（`task_harness_commands.py:42-84`），`ProjectionError` 统一 500 `command_projection_unavailable`（`:161-169`） |
| 23 | 公开投影字段与 §4.2 冻结清单一致 | 通过 | `task_command_routes.py:97-122`：`command_id/sequence_no/type/status/text/created_at/dispatch_started_at/native_ack_at/outcome_unknown_at/delivered_at/rejected_at/rejection_code/rejection_message`；不暴露 `native_request_id/native_sent_at/payload_digest/rejection_message(原始)`；`outcome_unknown` 强制公开 code `delivery_outcome_unknown`（`:103-107`） |
| 24 | 文本经凭据清洗后才投影 | 通过 | `_command_payload_text:80-94` 与 `task_harness_commands.sanitized_command_text:470-480` 都过 `sanitize_sensitive_data`，三个投影点（API、pump 控制事件、projector `_command_display_fields`）共用 |
| 25 | 性能：pump 查询走索引、无全表扫描/N+1 | 通过 | `ix_task_harness_commands_attempt_status (attempt_id,status)`、`ix_task_harness_commands_task_id`、`ix_task_harness_commands_attempt_id`、`uq_task_harness_command_attempt_seq`（`models.py:782-790`，迁移 `074:139-155`）；claim/队首/列表查询全部带 `task_id`+`attempt_id` 谓词（`:183-236`、`:532-556`、`task_harness_commands.py:498-508`）。`list_commands` 不分页，超长任务会返回全部历史，本阶段可接受、无需动作 |
| 26 | 同一 `command_id` 重投不产生两条用户消息 | 通过 | 单主键 `command_id`（`models.py:720`）+ 幂等分支（#1/#3）；pump 侧 `mark_command_native_sent`/`write_command_delivery` 均要求 `dispatching`（`:409-427/324-346`） |
| 27 | 控制事件审计不重复 | 通过 | pump 只在“无 native ACK 事件”的本地拒绝场景投影 `control.command.rejected`（`worker_command_pump.py:752-771`，用 `native_sent_at is None` 判定），delivered 交给 harness 事件（pi_events 的 `control.command.delivered`）；`dispatch_one_command:749-751` 注释明确不重复写日志 |
| 28 | 不可变 harness identity / V2-only 执行门禁（与本专题交叉部分） | 通过 | `harness_execution_policy.py:96-190`：Bundle/snapshot digest、harness_key ∈ Bundle adapters、model_protocol 由 Bundle 声明、attempt harness_key 一致；`create_task_attempt` 拒绝 recovery 改 harness（`harness_attempts.py:57-62`） |

## 4. 局限与未验证项

- **无真实运行环境**：本专题全部结论基于静态阅读 + 契约对照 + 仓库外最小复现。未启动 Docker 容器、未跑真实 Pi CLI，因此 **1800s 级 native ACK 等待、租约过期抢占、pump 取消时 `to_thread` 线程存活时长** 均未实测（CMD-02/CMD-INFO-03）。
- **PostgreSQL 未实测**：CMD-01 的 ORM 语义用 SQLite 复现（`/tmp/saprobe/race2.py`，真实模型 + 真实 helper）；PG 侧的锁等待（`FOR UPDATE` + READ COMMITTED 重判）与 CHECK 违规抛错为静态推断。CMD-04 的 `varchar(64)` 溢出属 PG 行为，SQLite 不校验故单测无法覆盖。
- **多 dispatcher 形态未验证**：CMD-02 的具体危害需要“同一 attempt 存在两个存活 dispatcher”，我只证明单进程单 pump（`scheduler.py:459` 的 recovery 仅启动一次且有 `_running_tasks` 去重），未验证双 scheduler 进程部署是否被部署层禁止（归 15）。
- **未覆盖模块**：事件 ingest/投影正确性（`harness_attempts.py` 的 seq/event_id/terminal 校验、projector 的 control 事件投影）归 02；pi owner/bridge 内部实现归 03；OpenCode/Claude/Codex 的 control 能力与 `disabled` 语义归 04/05/06；门禁/套件制品（bash/runtime_bin 解析、`KIT_MANIFEST_PATH`）归 07/09；任务终态与 timeout 收敛归 11；`task_command_routes.py` 的前端行为归 12；`created_by` 列宽同时属 14（迁移/模型一致性），本文件只从“命令平面可用性”角度记录。
- **未运行的验证**：真实容器内 `control_client.py` 行为、`pi_owner` 的 journal/replay 去重、两个并发 PUT 在 PG 上的唯一键竞争（靠代码路径与单测 `test_task_command_routes.py` 的 deadlock/竞态用例推断）、`docker exec` detach 语义。
