# 高峰/低峰任务超时设计

**Date:** 2026-09-09

**Status:** Draft

**Scope:** 将平台级单一任务超时升级为每日高峰、低峰两档超时，并保证每次 Task 执行使用可追溯、可恢复的冻结值

## 1. 结论

第一版采用一个每日高峰窗口，高峰窗口之外全部视为低峰：

```text
任务进入 RUNNING
        │
        ├── 当前时间位于高峰窗口 ──> 高峰超时
        │
        └── 当前时间位于窗口之外 ──> 低峰超时
                                      │
                                      └── 冻结到本次 Task 执行
```

配置只包含两个超时值和高峰开始、结束时间，不增加启用开关、工作日规则、多时间段、项目级覆盖或
Harness 级覆盖。

每个 Task 在实际进入 `RUNNING` 时选择一次超时档位，并将最终秒数持久化到 Task。运行中跨越时段
边界、管理员修改配置或 Scheduler 恢复任务，都不能改变该 Task 已选择的超时值。

第一版使用固定业务时区 `Asia/Shanghai`，配置页明确展示该时区，不读取浏览器或 Docker Host 的
本地时区。

## 2. 当前实现

当前超时是平台级运行时配置 `task_timeout`：

- `backend/app/config.py` 定义默认值 `1800` 秒；
- `backend/app/api/config_runtime.py` 通过 Runtime Config API 读写和校验，允许 `60–28800` 秒；
- `frontend/src/views/config/RuntimeSettingsPanel.vue` 提供单个“任务超时”输入框；
- `backend/app/core/worker_runtime.py` 将该值注入 Worker 容器的 `TASK_TIMEOUT`；
- `backend/app/core/worker_task_lifecycle.py` 使用该值限制日志流等待、生成超时日志并写入失败信息；
- Claude、Codex、Pi、OpenCode Adapter 继续消费同一个容器环境变量 `TASK_TIMEOUT`。

当前配置对象在一次 Worker 调用期间基本稳定，但 Task 本身没有记录本次执行实际使用的超时值。
因此不能仅在 Worker 启动或恢复时重新读取“当前档位”，否则跨时段恢复和运行中配置更新可能改变同一
Task 的执行契约。

## 3. 目标与非目标

### 3.1 目标

1. 平台管理员可以分别配置高峰和低峰任务超时。
2. 平台管理员可以配置一个每日高峰开始、结束时间。
3. 普通窗口和跨午夜窗口都具有明确、可测试的边界语义。
4. Task 按实际进入 `RUNNING` 的时间选择档位，而不是创建时间或 `scheduled_at`。
5. 同一 Task 的超时值在执行期间保持不变，并可在 Scheduler/Backend 恢复后继续使用。
6. Backend 强制超时、Worker 环境、错误消息和任务详情展示使用同一个冻结值。
7. 保持现有超时失败分类、容器优雅停止和四 Harness 行为不变。

### 3.2 非目标

第一版不包括：

- 多个高峰窗口；
- 工作日、周末或节假日规则；
- 可配置时区；
- 按 Project、Priority、Provider、Worker Profile 或 Harness 覆盖；
- 动态负载、并发数或 Provider 限流驱动的超时；
- 运行中 Task 随时段变化动态延长或缩短；
- 通用排班规则引擎；
- 修改现有超时失败 taxonomy、canonical 事件结构或容器停止流程。

如果两个超时配置相同，系统自然退化为全天单一超时，因此不需要单独的功能开关。

## 4. 配置契约

### 4.1 配置项

用以下四个 Runtime Config 键替换现有 `task_timeout`：

| 配置键 | 类型 | 新安装默认值 | 约束 | 说明 |
|---|---:|---:|---|---|
| `task_timeout_peak_seconds` | integer | `1800` | `60–28800` | 高峰时段 Task 的最大执行秒数 |
| `task_timeout_off_peak_seconds` | integer | `3600` | `60–28800` | 低峰时段 Task 的最大执行秒数 |
| `task_timeout_peak_start` | string | `09:00` | 严格 `HH:mm` | 每日高峰开始时间，包含该时刻 |
| `task_timeout_peak_end` | string | `18:00` | 严格 `HH:mm` | 每日高峰结束时间，不包含该时刻 |

对应部署环境变量为：

```text
TASK_TIMEOUT_PEAK_SECONDS
TASK_TIMEOUT_OFF_PEAK_SECONDS
TASK_TIMEOUT_PEAK_START
TASK_TIMEOUT_PEAK_END
```

Worker 容器内部的 `TASK_TIMEOUT` 保留，但它不再表示平台原始配置，而表示该 Task 已冻结的最终秒数。

### 4.2 校验

- 两个秒数字段必须是整数，布尔值不作为整数接受；
- 两个秒数字段继续沿用当前 `60–28800` 范围；
- 时间只接受零填充的 24 小时制 `HH:mm`，例如 `09:00`、`23:30`；
- `24:00`、带秒、带时区、非零填充格式均不接受；
- `task_timeout_peak_start == task_timeout_peak_end` 时拒绝整次配置更新；
- 不强制高峰超时小于低峰超时，避免把命名约定变成不必要的系统限制；UI 提示推荐高峰不大于低峰；
- Runtime Config 的部分更新必须先与当前有效配置合并并完成整体校验，再写入数据库，不能产生半套策略。

## 5. 时段判定

### 5.1 时间基准

数据库时间继续使用仓库现有的 naive UTC 约定。判定时：

1. 取得本次认领将写入的 `started_at`；
2. 将该 UTC 时间附加 UTC 时区信息；
3. 使用 Python 标准库 `zoneinfo.ZoneInfo("Asia/Shanghai")` 转换为业务本地时间；
4. 只取本地时分参与窗口判断。

不能使用：

- Backend/Scheduler 进程本地时区；
- Docker Host 本地时区；
- 浏览器时区；
- Task 创建者所在时区。

### 5.2 边界规则

高峰窗口统一采用半开区间 `[start, end)`。

普通窗口，`start < end`：

```text
peak = start <= local_time < end
```

跨午夜窗口，`start > end`：

```text
peak = local_time >= start or local_time < end
```

示例：

| 高峰窗口 | 当前时间 | 档位 |
|---|---|---|
| `09:00–18:00` | `08:59` | 低峰 |
| `09:00–18:00` | `09:00` | 高峰 |
| `09:00–18:00` | `17:59` | 高峰 |
| `09:00–18:00` | `18:00` | 低峰 |
| `22:00–06:00` | `23:00` | 高峰 |
| `22:00–06:00` | `05:59` | 高峰 |
| `22:00–06:00` | `06:00` | 低峰 |

## 6. Task 执行快照

### 6.1 数据模型

在 `tasks` 增加：

```text
execution_timeout_seconds INTEGER NULL
```

约束：

```text
execution_timeout_seconds IS NULL
OR execution_timeout_seconds BETWEEN 60 AND 28800
```

字段允许 NULL 是为了如实表示升级前的历史 Task 没有持久化该事实。升级后的 Task 一旦进入
`RUNNING`，该字段必须非空；Worker 遇到新的 RUNNING Task 缺少该值时应失败关闭，而不是静默读取
当前配置。

不额外保存 `peak/off_peak` 枚举。运行时真正需要恢复和执行的是最终秒数，档位名称只写结构化日志；
增加第二个持久化字段不会提高执行正确性。

### 6.2 原子认领

Scheduler 当前在同一个事务中执行 Issue 锁、`QUEUED → RUNNING` CAS 和 `started_at` 写入。超时选择
应加入同一事务：

```text
claim_time = utcnow()
timeout_seconds = resolve_task_timeout_seconds(effective_settings, claim_time)

task.status = RUNNING
task.started_at = claim_time
task.execution_timeout_seconds = timeout_seconds
COMMIT
```

这样不会出现 Task 已经可执行但未记录超时值的中间已提交状态。

直接执行入口也必须复用同一个解析函数。当前 Worker 准备阶段会再次写 `started_at`；实现时改为仅当
`started_at` 为空时写入，不能覆盖 Scheduler 原子认领时已经确定的时间锚点和档位。

### 6.3 执行期间

Worker 后续所有超时用途只读取 `task.execution_timeout_seconds`：

1. 构建容器环境 `TASK_TIMEOUT`；
2. Backend 日志流等待；
3. 超时 marker 和容器停止路径；
4. `Task timed out after Ns` 错误消息；
5. TaskLog 超时消息；
6. Task API 展示。

不得在这些路径再次调用时段解析函数，也不得重新读取两个平台超时配置。

### 6.4 截止时间与恢复

本次执行的权威截止时间为：

```text
execution_deadline_at = started_at + execution_timeout_seconds
```

`execution_deadline_at` 不单独持久化，避免保存可推导的重复状态。Task API 可以按上式返回派生值。

正常执行和恢复执行传给 Backend 日志监控的值都是剩余秒数：

```text
remaining_seconds = ceil(execution_deadline_at - utcnow())
```

如果剩余时间小于等于零，Backend 立即进入现有超时 marker、优雅停止和失败收敛流程。Scheduler 或
Backend 重启不能给 Task 重新增加一整段超时时间。

容器内 Harness 收到的是本次完整 `execution_timeout_seconds`。恢复时不会重建容器，因此容器环境仍是
原值；Backend 的剩余时间是恢复场景下更严格的最终裁决边界。

本设计沿用当前 Backend 在容器日志监控阶段实施外层超时的边界，不新增包围全部 GitLab/Docker 前置
操作的全局取消器。如果某个前置调用自身永久阻塞，Task 截止时间只能在该调用返回后被检查；这属于
独立的调用超时治理问题，不能把本次时段拆分描述成已经解决了所有前置 IO 挂死。

## 7. 配置更新语义

配置更新只影响尚未进入 `RUNNING` 的 Task：

| Task 状态 | 配置更新后的行为 |
|---|---|
| `PENDING` | 实际认领时使用新配置 |
| `QUEUED` | 实际认领时使用新配置 |
| `RUNNING` | 继续使用已冻结的 `execution_timeout_seconds` |
| 终态 | 不受影响 |

Scheduled Task 按实际认领时刻判断，不按 `scheduled_at` 判断。Retry 会创建新的 Task，因此按 Retry Task
实际认领时刻重新选择档位。

配置保存后不需要扫描或更新 Task，也不需要新增定时任务。

## 8. API 与前端

### 8.1 Runtime Config API

现有 Runtime Config response/update model 删除 `task_timeout`，加入四个新字段。继续复用：

- `GET /api/config`；
- `PATCH /api/config`；
- `GET /api/config/runtime`；
- `PATCH /api/config/runtime`；
- 现有单键重置和全量重置能力。

不新增专用时段 API 或数据库表。

### 8.2 Task API

Task 列表和详情增加：

```json
{
  "execution_timeout_seconds": 1800,
  "execution_deadline_at": "2026-09-09T10:30:00"
}
```

规则：

- 历史 Task 或尚未运行的 Task 返回 `null`；
- `execution_deadline_at` 只在 `started_at` 和 `execution_timeout_seconds` 都存在时返回；
- API 时间格式继续沿用现有 naive UTC 序列化约定；
- 不把当前平台配置冒充为 Pending Task 已选择的超时值。

### 8.3 Runtime Settings 页面

将当前单个“任务超时”输入改为“任务超时策略”区域：

```text
任务超时策略                         时区：Asia/Shanghai

高峰开始时间  [09:00]    高峰结束时间  [18:00]
高峰超时（秒）[1800 ]    低峰超时（秒）[3600 ]

任务在实际开始执行时选择一次超时限制，运行中不会切换。
```

使用项目现有 Naive UI 控件，不增加前端依赖。中英文 i18n 必须同步更新。Config 页面顶部摘要由单个
`task_timeout` 改为例如“高峰 1800s / 低峰 3600s”。

Task 详情在已有运行元数据区域展示：

- 本次超时上限；
- 截止时间；
- 尚未运行时显示“开始执行时确定”。

## 9. 日志与可观测性

Task 被认领时写一条结构化、无敏感信息的日志：

```text
[Task 123] Selected peak timeout: 1800s (window=09:00-18:00, timezone=Asia/Shanghai)
```

低峰对应 `Selected off-peak timeout`。恢复日志应包含冻结值和剩余值：

```text
[Task 123] Resuming with frozen timeout=1800s, remaining=742s
```

现有 canonical timeout 事件和 `failure_kind=timeout` 保持不变。本功能不为时段选择新增 canonical
事件类型；Task 字段、Backend 日志和现有最终事件已经足够定位问题。

## 10. 迁移与发布

新增 Alembic migration：

```text
079_task_execution_timeout.py
```

迁移内容：

1. 增加可空 `tasks.execution_timeout_seconds`；
2. 增加允许 NULL、非 NULL 时范围为 `60–28800` 的 CHECK；
3. 如果 `system_config.task_timeout` 存在，将其值分别复制为
   `task_timeout_peak_seconds` 和 `task_timeout_off_peak_seconds`；
4. 删除旧的 `system_config.task_timeout`；
5. 不为历史 Task 猜测执行快照。

发布采用项目当前允许停机升级的方式。迁移前必须确认没有 RUNNING Task；不为跨版本运行中 Task 增加
双读或兼容恢复路径。

存在数据库 `task_timeout` override 时，迁移后的两个档位初始相同，因此该环境不会因为升级立即改变
执行时长。只通过部署环境变量配置旧 `TASK_TIMEOUT` 的环境，发布前必须显式将原值同时写入两个新
超时变量；管理员随后再保存新的低峰值和窗口。新安装环境使用第 4.1 节默认值。

部署配置中的旧 `TASK_TIMEOUT` 必须同步替换成四个新环境变量。Worker 容器内部仍继续使用
`TASK_TIMEOUT`，两者属于不同配置层，不应删除 Adapter 对该变量的消费。

Downgrade 不尝试重建已经丢失的逐 Task 选择语义，保持仓库现有 roll-forward-only 迁移策略。

## 11. 实现边界

建议新增一个小型纯函数模块：

```text
backend/app/core/task_timeout.py
```

只负责：

- 解析严格 `HH:mm`；
- 判断普通/跨午夜窗口；
- 根据 UTC 时刻返回最终超时秒数；
- 计算 Task 剩余时间。

其余修改保持在现有所有者中：

| 范围 | 主要文件 |
|---|---|
| Settings 和持久化键 | `backend/app/config.py` |
| Config API 与校验 | `backend/app/api/config_runtime.py`、`backend/app/api/_validators.py` |
| Task 字段 | `backend/app/models.py`、`backend/alembic/versions/079_*.py` |
| Scheduler 原子认领 | `backend/app/scheduler.py` |
| 直接执行与恢复 | `backend/app/core/worker_task_lifecycle.py`、`worker_task_runner.py` |
| Worker 环境 | `backend/app/core/worker_runtime.py` |
| Task API | `backend/app/core/task_helpers.py`、`backend/app/api/task_responses.py` |
| Runtime Settings | `frontend/src/views/config/RuntimeSettingsPanel.vue`、`useConfigForm.ts` |
| 前端类型和文案 | `frontend/src/api/index.ts`、`frontend/src/api/tasks.ts`、两份 i18n 文件 |

不修改 Worker Profile Snapshot、Provider Snapshot、Runtime Bundle manifest 或 Harness Adapter 协议。

## 12. 测试与验收

### 12.1 Backend 单元测试

时段解析和选择：

- 普通窗口开始前、开始点、结束前、结束点；
- 跨午夜窗口的晚间、凌晨和结束点；
- UTC 到 `Asia/Shanghai` 转换；
- 非法格式、`24:00`、开始等于结束；
- 两个超时值相同；
- 秒数上下界和布尔值拒绝。

执行生命周期：

- Scheduler 在 RUNNING 认领事务中同时写 `started_at` 和 `execution_timeout_seconds`；
- Worker 不覆盖已经存在的 `started_at` 或冻结超时；
- 容器环境 `TASK_TIMEOUT` 使用 Task 冻结值；
- Backend 日志流、错误消息和 TaskLog 使用同一个值；
- 运行中更新配置不改变已有 Task；
- 恢复使用剩余时间而不是完整超时；
- 截止时间已过时立即进入 timeout，而不是重新运行一个完整周期；
- 新 RUNNING Task 缺失冻结值时失败关闭。

API：

- Config GET/PATCH/Reset 完整往返四个字段；
- 部分更新先整体校验再落库；
- Task Pending/历史态返回空执行超时；
- Running/终态返回冻结秒数和派生截止时间。

### 12.2 Frontend 测试

- Runtime Settings 正确加载、修改、保存和重置四个字段；
- 时间和秒数错误能阻止保存；
- dirty-state 包含四个新字段，不再包含旧 `task_timeout`；
- Config 摘要展示两个档位；
- Task 详情展示本次冻结上限和截止时间；
- 中英文文案和前端类型同步。

### 12.3 实际验收

在开发环境使用短超时完成两次真实 Task 验证：

1. 调整高峰窗口使当前时刻落在高峰，设置高峰 `60s`、低峰 `120s`，确认 Task 冻结为 `60s` 并以
   `timeout` 失败；
2. 调整窗口使当前时刻落在低峰，确认新 Task 冻结为 `120s`；
3. 第二个 Task 运行中修改配置，确认该 Task 仍保持 `120s`；
4. 至少覆盖 Claude、Codex、Pi、OpenCode 的自动化环境注入和生命周期测试；真实 Host 验收可任选一个
   当前已验证可用的 Harness，但不能用单个 Adapter 测试替代四 Harness 的自动化覆盖；
5. 验收结束后恢复正式配置，并确认数据库 Runtime Config 与页面显示一致。

## 13. 核心不变量

1. 一个升级后的 RUNNING Task 必须只有一个持久化的 `execution_timeout_seconds`。
2. 超时档位只在第一次进入 RUNNING 时选择一次。
3. Backend、Worker 环境、错误消息和 API 展示必须来自同一 Task 冻结值。
4. 高峰窗口开始包含、结束不包含，并支持跨午夜。
5. Scheduled Task 按实际执行时刻而不是预约时刻选档。
6. 配置更新不修改已经 RUNNING 或终态的 Task。
7. 恢复不能重新选档，也不能重新获得完整超时时间。
8. 新执行缺失冻结值时失败关闭；历史 Task 的 NULL 保持 Unknown。
9. 第一版只有一个每日窗口和固定 `Asia/Shanghai` 时区。
10. 四个 Harness 继续使用统一的 Task 级 `TASK_TIMEOUT`，不形成各自独立语义。
