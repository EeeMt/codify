# 12 前端任务执行/交付/交互 UI（除 Provider 面板）—— Code Review

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56`（基线 `7b253fbf`，2026-08-20；当前 `dev @ cbad9e56`） |
| 主要文件 | `components/TaskSteeringPanel.vue`(+413 新增)、`components/task-process/TaskProcessControlEventRow.vue`(+140 新增)、`TaskProcessTextRow.vue`(+131/-6)、`TaskProcessToolRow.vue`(+43/-13)、`taskProcessUtils.ts`(+93/-4)、`components/TaskProcessPanel.vue`(+48/-3)、`components/TaskResultPanel.vue`(+533/-12)、`components/TaskFormDrawer.vue`(+303/-14)、`components/config/WorkerSettingsPanel.vue`(+148/-14)、`features/tasks/useTaskLogStreams.ts`(+85/-18)、`composables/usePolling.ts`(+20/-2)、`api/tasks.ts`(+147/-2)、`api/index.ts`(+61/-7)、`views/TaskView.vue`(+138/-16)、`views/config/RuntimeSettingsPanel.vue`(+88/-10)、`views/config/useConfigForm.ts`(+20/-5)、`views/CreateIssue.vue`(+80/-22)、`i18n/messages/en.ts`(+114/-4)、`i18n/messages/zh-CN.ts`(+114/-3)、`utils/slotError.ts`(+12 新增)，以及 `views/{Dashboard,IssueList,IssueView,ScheduleOverview,UsageManagement,Analytics,Config}.vue`、`App.vue`、`components/filter/*` 的增量改动 |
| 一起读的依赖上下文 | 后端契约：`api/task_command_routes.py`、`core/task_harness_commands.py`、`core/task_command_gate.py`、`core/harness_protocol.py`、`core/harness_options.py`、`api/harness_catalog.py`、`api/task_log_stream.py`、`api/containers.py`、`api/task_responses.py`、`core/worker_git_delivery.py`、`core/worker_event_projector.py`；worker 侧 `deploy/worker-entrypoint/harness/manifest.json` |
| 审查方法 | 静态阅读**当前完整文件**（含调用方与 spec）+ 前后端逐字段契约对照 + `git diff` 定位改动后回读完整文件 + `grep` 全量扫描 `v-html/innerHTML` + 窄范围单测 + node/esbuild 提取 i18n key 集合求差 |
| 未覆盖 | `components/config/AIProvidersPanel.*`（T10）；四个 adapter 的翻译语义（T04/T05/T06）；后端 gate/pump 状态机本身（T01）；迁移（T14）；E2E/Playwright 未执行；无真实浏览器与后端联调 |

本次实际执行的验证：

| 命令/操作 | 结果 |
|---|---|
| `cd frontend && npx vitest run src/components/config/WorkerSettingsPanel.spec.ts` | 37 passed（用于确认该 spec 的 i18n 断言方式：测试环境无 i18n 插件时 `t(key)` 原样返回 key，因此断言 `toContain('config....')` 无法发现缺 key） |
| node + esbuild 提取 `en.ts` / `zh-CN.ts` 叶子 key 求差集（脚本写在 `/tmp`，未落库） | en 2234 / zh 2235；唯一差异 `config.runtimeFailureDetailsUnavailable` 仅存在于 zh（FE-01） |
| `grep -rn "v-html\|innerHTML\|DOMPurify\|sanitize" frontend/src` | 9 处 `v-html` + 3 处 `innerHTML`，逐个回溯来源，结论见 §3 #9 |
| 未运行 | 全量 `vitest`、`npm run build` / `vue-tsc`、任何需要后端/DB/Docker/浏览器的场景 |

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 0 |
| FIX_IF_CHEAP | 3 |
| DEFER | 7 |
| ACCEPT/CLOSE | 0 |

本模块整体质量较高：事件原地更新与回绕游标、流身份守卫、原始日志有界窗口、请求代际守卫均实现完整并有新增 spec 逐条覆盖，渲染安全未发现 V2 新引入的 XSS。无 FIX_NOW；3 条 FIX_IF_CHEAP 都是错误路径与文案上的真缺陷，修复各约 5 行。其余 7 条按 3 人内测、无 SLA、避免过度防御的画像列 DEFER，本阶段书面接受 0 条。

## 2. 问题清单

### FE-01 英文语言包缺失 `config.runtimeFailureDetailsUnavailable`，EN 界面显示原始 key
- **判定**：FIX_IF_CHEAP —— 一行 key 即可修好
- **位置**：`frontend/src/i18n/messages/en.ts:1831`（提交 `6ffc86a3`）
- **证据**：该 key 只在中文包里定义，英文包里在 `runtimeLastChecked` 与 `harnessAvailable` 之间被漏掉：

```
      runtimeLastChecked: 'Last checked {time}',      // en.ts:1831
      harnessAvailable: 'available',                  // en.ts:1832
      runtimeFailureDetailsUnavailable: '运行时不可用。重新检查后可获取最新诊断详情。',   // zh-CN.ts:1807，en 无对应行
```

  使用点唯一且无回退：`components/config/WorkerSettingsPanel.vue:577` → `{{ workerFormValue.runtime_readiness.failure_message || t('config.runtimeFailureDetailsUnavailable') }}`。
  `i18n/index.ts:48` 只配置 `fallbackLocale: FALLBACK_LOCALE`（`'en'`），当 `locale === 'en'` 时缺 key 无任何回退目标，vue-i18n 返回 key 路径本身。
  用 esbuild 提取两侧叶子 key 求差集（en 2234 / zh 2235）后，这是**唯一**的不对称 key。
  `components/config/WorkerSettingsPanel.spec.ts:699` 断言 `toContain('config.runtimeFailureDetailsUnavailable')`，但该 spec 未安装 i18n 插件，`t()` 原样返回 key，因此该断言对“生产是否缺 key”零覆盖（已实跑确认 37 passed）。
- **影响**：Worker Profile 运行时状态为 `unavailable` 且后端未返回 `failure_message` 时，`en` 用户在配置页看到字面量 `config.runtimeFailureDetailsUnavailable`；zh 用户正常。属于默认语言下的可见缺陷。
- **最小动作**：`en.ts` 在 `runtimeLastChecked` 后补 `runtimeFailureDetailsUnavailable`
- **验证**：已用 key 差集脚本确认；修复后复用同一脚本（差值应为空），或给该 spec 装上真实 i18n 插件再断言文案。本次未运行 frontend build。

### FE-02 Steering 命令被拒（409/422/403）时丢弃后端 `detail` 对象，拒绝原因不可见
- **判定**：FIX_IF_CHEAP —— 纯 UX，不改任何服务端状态
- **位置**：`frontend/src/components/TaskSteeringPanel.vue:224-234`（提交 `ef098442`）
- **证据**：前端只识别字符串 / 数组形态的 `detail`：

```ts
  } catch (err) {
    const detail =
      (err as { response?: { data?: { detail?: string | { msg?: string }[] } } })
        ?.response?.data?.detail
    const msg =
      typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map(d => d.msg ?? '').join('; ') : ''
    message.error(`${t('taskView.steeringFailedToast')}${msg ? `: ${msg}` : ''}`)
```

  而后端所有拒绝路径的 `detail` 都是**对象** `{code, message, command_id}`：`backend/app/api/task_command_routes.py:120-146`（`task_not_running`/`attempt_mismatch`/`unsupported_harness`/`control_gate_closed` → 409，`payload_too_large`/`invalid_*` → 422，`not_authorized` → 403）、`:220-229`（同 ID 不同 payload → 409）。这些拒绝**不会**产生命令行（`backend/app/core/task_harness_commands.py:240-271` 在校验后直接 `return`，未 `db.add`），也不会写 `control_event`，因此 `GET /tasks/{id}/commands` 里查不到该命令。
- **影响**：面板的 `control_state` 来自 TaskView 的 5 秒轮询（`views/TaskView.vue:1303-1320` → `fetchTask` → `control_state`），存在最长 5 秒的陈旧窗口。用户在任务刚结束（`task_not_running`）或 gate 已 `closing`（`control_gate_closed`，例如收到 `agent_settled` 开始 draining）时点击发送，界面只弹出“命令发送失败”，历史里也查不到该命令 —— 运维无法区分“被拒绝（gate 已关）”与“网络/服务故障”，会去排查不存在的传输问题。
- **最小动作**：`TaskSteeringPanel.vue:224-234` 的 catch 按 `detail.message ?? detail.code` 展示（~5 行）
- **验证**：静态核对了后端 5 条拒绝分支的 `detail` 形态与前端解析；未运行真实后端。可用单文件单测注入 `{ response: { data: { detail: { code: 'control_gate_closed', message: 'The control gate is closed.' } } } }` 断言提示包含该 message。

### FE-03 每次发送都重新生成 `command_id`，传输失败后的重试会重复投递同一条指令
- **判定**：FIX_IF_CHEAP
- **位置**：`frontend/src/api/tasks.ts:750-760`（提交 `ef098442`）
- **证据**：幂等键在 `sendHarnessCommand` 内部生成，调用方拿不到、也无法重放：

```ts
export async function sendHarnessCommand(
  taskId: number,
  request: { type: 'steer' | 'follow_up', text: string }
): Promise<{ command: HarnessCommand, created: boolean }> {
  const commandId = generateCommandId()
  const response = await api.put(`/tasks/${taskId}/commands/${commandId}`, request)
```

  契约把 `command_id` 定义为**客户端生成**的幂等键（`backend/app/api/task_command_routes.py:3-10`；`backend/app/core/task_harness_commands.py:196-207` 的 `existing_same` 分支只在 ID 相同时去重），而 `TaskSteeringPanel.vue:203-245` 的 `catch` 只弹提示、不保留 ID。重复点击本身已被 `sending` 门闩与 `:disabled` 挡住（`TaskSteeringPanel.vue:44-48`），缺口只在“请求已到服务端但客户端没收到响应”这一层。
- **影响**：浏览器断网/被节流，或命中 `api/client.ts` 的 30s axios 超时（`frontend/src/api/client.ts:18`）时，PUT 可能已在服务端落库；用户重试 → 新 UUID → 第二条 `queued` 命令 → 运行中的 harness 收到两次同义指令（重复编辑/重复提交）。触发窗口小，但后果是控制面重复投递，而这正是幂等键存在的理由。
- **最小动作**：`sendHarnessCommand(taskId, request, commandId = generateCommandId())`，面板在文本未变的重试中复用同一 ID（~5 行）
- **验证**：未运行验证（需构造“服务端已提交/客户端失败”的传输场景）。可加单测：mock `api.put` 第一次 reject、第二次 resolve，断言两次请求 URL 中的 `command_id` 相同。

### FE-04 思考耗时 tooltip 硬编码英文，未走 i18n
- **判定**：DEFER
- **位置**：`frontend/src/components/task-process/TaskProcessTextRow.vue:13-17`（提交 `76d588da`）
- **证据**：新增的耗时徽标把英文写进模板，同文件其余文案都走 `t()`（如 `nameLabel`、`taskView.fullText`）：

```
      <span
        v-if="completedDuration !== null"
        class="event-duration"
        :title="`Thinking duration: ${completedDuration}`"
      >{{ completedDuration }}</span>
```

  同型问题 `TaskProcessToolRow.vue:17` 的 `` `Tool duration: ...` `` 在基线已存在（本次只把它的时长格式化函数换成 `formatEventDuration`），属 V1 遗留，不计入本条。
- **影响**：zh-CN 界面悬停出现英文 tooltip；无功能影响。
- **最小动作**：新增 `taskView.thinkingDurationHint` 两语言 key + 模板 1 行
- **验证**：静态核对（i18n key 差集脚本确认两侧都没有该 key）；无需行为验证。

### FE-05 OpenCode `model_variant` 输入缺少与后端一致的客户端校验，422 原因被丢弃
- **判定**：DEFER —— FE-02 透出 detail 后大半自愈，补正则属额外代码
- **位置**：`frontend/src/components/TaskFormDrawer.vue:636-645`（提交 `ab869c67`）
- **证据**：新输入框只有 `maxlength="64"` 与 `clearable`，无格式校验：

```
                          <n-input
                            :value="opencodeModelVariant ?? ''"
                            maxlength="64"
                            clearable
```

  而后端 `backend/app/core/harness_options.py:48` 要求 `^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$`（`:97-135` 的 `OpenCodeV1Options`），非法值经 `validate_task_overrides` 抛 `HarnessOptionsError` → 请求失败；edit 路径的 `catch` 只认字符串 detail（`features/tasks/useTaskFormSubmission.ts:197-206`），create 路径的 `extractSlotErrorMessage` 对数组 detail 也落到通用文案（`utils/slotError.ts:58-68`）。
- **影响**：输入含空格/中文（如 `my variant`）时保存只提示“任务更新失败”，用户无法定位到该字段。字段白名单本身正确：前端只发 `agent/command/model_variant`（`components/TaskFormDrawer.vue:1239-1248`），与 `harness_options.py:39-44` 的 `TASK_OVERRIDE_KEYS['opencode/v1']` 完全一致。
- **最小动作**：先吃 FE-02 的 detail 透出；字段级正则按需再补
- **验证**：静态对照前后端校验规则；未运行。可在 `TaskFormDrawer.spec.ts` 断言非法输入时提交被拦截/出现提示。

### FE-06 每秒把 `nowMs` 下发给每一行思考/回复行，长日志下形成 1Hz 全列表重渲染
- **判定**：DEFER —— 无实测卡顿，不阻塞任何工作
- **位置**：`frontend/src/components/TaskProcessPanel.vue:314-320`（提交 `03a7ae2c`）
- **证据**：面板持有共享时钟并每秒写一次，同时把该 prop 传给了 `v-for` 中的**每一行**文本行（列表无虚拟滚动，`TaskProcessPanel.vue:51`）：

```
    elapsedTimer = setInterval(() => {
      nowMs.value = Date.now()
      updateElapsed()
    }, 1000)
```

```
                    :now-ms="nowMs"
                    :task-active="props.isActive"
```

  行内 `elapsedText` 依赖 `props.nowMs`（`TaskProcessTextRow.vue:109-116`），因此每次 tick 都会推动每个文本行组件重新渲染（markdown 结果本身有缓存，`renderedHtml` 只在文本变化时重算）。
- **影响**：长任务（大量 thinking/assistant 事件）停留在“事件流”页签时，每秒 O(行数) 的重渲染，滚动与交互可能卡顿；改动前该定时器只更新表头的 `elapsedMs`（`TaskProcessPanel.vue:227`）。
- **最小动作**：只给 `in_progress` 行传 `nowMs`，其余传 null
- **验证**：未运行（缺长日志真机基线）；结论基于 prop → 子组件更新链的静态推导，建议在长日志任务上实测帧率后再定级。

### FE-INFO-01 `control_state='disabled'` 时 gate 徽标渲染为空
- **判定**：DEFER
- **位置**：`frontend/src/components/TaskSteeringPanel.vue:115-128`
- **证据**：`gateLabel` 的 `switch` 覆盖 `starting/accepting/closing/closed`，`disabled` 落到 `default: return ''`，但模板仍渲染 `<span class="steering-panel__gate steering-panel__gate--disabled">`（空文本）。可达性：面板可见要求 `capabilities.steering || follow_up`（`:99-105`），而后端 `control_supported` 只看 `capabilities.steering`（`backend/app/core/worker_task_lifecycle.py:496-500`）；现网 manifest 中唯一 `steering: true` 的适配器同时声明 `follow_up: true`（`deploy/worker-entrypoint/harness/manifest.json:94-95`），故当前不可达。
- **影响**：仅当 capability 与 `control_supported` 判定不一致时出现空徽标，无功能影响。
- **最小动作**：`disabled` 态加文案或该态不渲染徽标
- **验证**：静态核对 manifest 与两侧判定条件；未运行。

### FE-INFO-02 未知 `push.status` 被渲染为“推送失败”
- **判定**：DEFER
- **位置**：`frontend/src/components/TaskResultPanel.vue:657-668`
- **证据**：`return labels[status] ?? t('taskView.gitDeliveryFailed')` —— 任何未识别状态（未来新增枚举）都会显示为“失败”，而非“未知”。
- **影响**：仅在后端新增 `push.status` 且前端未同步时误报失败；当前后端枚举冻结为 5 值（`backend/app/core/worker_git_delivery.py:23`），不可达。
- **最小动作**：兜底改中性文案（「状态未知」）
- **验证**：静态核对后端枚举集合；未运行。

### FE-INFO-03 `showCommitRecord` 在“有 push 结论但无提交列表”时隐藏整张提交记录卡
- **判定**：DEFER —— 该组合是否可达未验证
- **位置**：`frontend/src/components/TaskResultPanel.vue:597-601`
- **证据**：`if (gitDelivery.value) return gitDeliveryHasContent.value || gitDeliveryPushFailed.value`，即 `commits`/`recovered_commits` 均为空且 `push.status !== 'failed'` 时整卡不渲染（模板 `:167`）；而后端 `normalize_git_delivery` 只约束“有内容 ⇒ 必须是确认态”（`backend/app/core/worker_git_delivery.py:239-256`），允许 `push.status='pushed'` 且 `commits=null`。该组合是否会被 worker 产出未经验证。
- **影响**：若该组合真实存在，`head_sha`/`branch` 等交付事实在 UI 上完全不可见。
- **最小动作**：展示条件加入确认态 + `head_sha`/`branch`
- **验证**：静态核对归一化约束；未运行（需真实交付产物）。

### FE-INFO-04 `command-delivered` 事件无消费方
- **判定**：DEFER
- **位置**：`frontend/src/components/TaskSteeringPanel.vue:88,215`、`frontend/src/views/TaskView.vue:432-439`
- **证据**：面板声明 `defineEmits<{ (e: 'command-delivered'): void }>()`，并在 `delivered` 分支 emit，但 TaskView 挂载处只传 props 与 `data-testid`，无监听者；面板自身已 `await refreshHistory()`，父组件没有必须刷新的状态。
- **影响**：无功能影响，属未接线的接口。
- **最小动作**：删除 `command-delivered` emit（1 行）
- **验证**：静态核对两处代码；未运行。

## 3. 逐项核查记录

| # | 不变量/契约 | 结论 | 依据 |
|---|---|---|---|
| 1 | 结构化日志 SSE：`since_id` 回绕后不丢事件、不重复追加、旧连接回调不污染新状态 | 通过 | `useTaskLogStreams.ts:43-58`（`computeStructuredStreamSinceId` 取最早 `in_progress` 行 -1，与后端 `id > cursor` 语义一致，`api/task_log_stream.py:40-43`）；`:167-230` 用 `structuredLogSource !== source` 丢弃旧 source 的 batch/update/done/error；`:154-160` `closeStructuredLogStream` 清空待 flush 队列并复位标志 |
| 2 | thinking 行原地更新且状态不回退（`in_progress` 不覆盖 `completed`） | 通过 | `useTaskLogStreams.ts:54-58,66-85` 状态秩比较（`completed 2 > interrupted 1 > in_progress 0 > 无状态 -1`）；后端只在状态变化/终态时发 `update`（`api/task_log_stream.py:96-125`，以 `status` 而非 payload_id 判定结束）；`useTaskLogStreams.spec.ts:169-203,309-360` 覆盖 |
| 3 | tool_call 完成态用“键是否存在”判定，而不是 null | 通过 | `TaskProcessToolRow.vue:136-141` 用 `!== undefined`；后端 start 事件不写 `output`、仅完成时写 `output_payload_id`（`core/worker_event_projector.py:263-296,326-360`），与 SSE 只在 `output_payload_id` 出现后发 `update` 一致 |
| 4 | 原始日志窗口有界、截断有标记、游标单调 | 通过 | `useTaskLogStreams.ts:99-127`（500k 字符窗口 + `truncated`）、`:233-257`（`chunk.sequence_no <= rawLogSequenceNo` 跳过重复）；渲染前再截一次尾部（`views/TaskView.vue:803-810`）；后端快照 `last_sequence_no` 取最新分片（`api/containers.py:150-183`），`done` 仅在 task 终态且 `raw_logs_finalized_at` 非空时发出（`:559-565`） |
| 5 | 定时器/事件监听在卸载时清理；切换 task 清空派生状态 | 通过 | `usePolling.ts:30-50,67-70`（`start` 先 `stop`；`onUnmounted` 移除 visibilitychange + `stop()`）；`TaskView.vue:1347-1360`（close 两条流 + clearInterval）、`:1280-1295`（`resetLogsState`）、`:1322-1345`（路由切换清空 task/controlState/capabilities/history 并重新加载）；`IssueView.vue:706-712,898-910`、`Dashboard.vue:429-455`、`ScheduleOverview.vue:622-676` 均成对增删 |
| 6 | 陈旧响应不得覆盖新状态（请求代际守卫） | 通过 | `TaskView.vue:1076-1092`（`taskRequestGeneration` + `requestedTaskId` 双检）、`:1237-1246`（`logRequestGeneration`）、`useTaskLogStreams.ts:275-310`（`rawLogSnapshotRequest` + taskId 比对）、`TaskSteeringPanel.vue:164-176`（`historyRequestGeneration`，spec `:193-216` 覆盖跨任务历史串台） |
| 7 | 仅 `control_state=accepting` 且 task running 时可新建命令；capability 未知时 fail-closed | 通过 | `TaskSteeringPanel.vue:99-114`（`visible` 需 catalog capability；`inputEnabled` 需 running + accepting）；`views/TaskView.vue:1153-1170`（catalog 拉取失败 → `capabilities=null` → 面板隐藏）；后端二次判定 `core/task_harness_commands.py:264-271` |
| 8 | 命令文本上限前后端一致（4000 UTF-16） | 通过 | 前端 `TaskSteeringPanel.vue:35` `maxlength="4000"` + `show-count`；后端 `core/harness_protocol.py:657` `MAX_COMMAND_TEXT_UTF16_CODE_UNITS = 4_000` |
| 9 | 渲染安全：日志/thinking/tool/summary 不得把不可信文本直出为 HTML | 通过（无 V2 新引入的 XSS） | 全量 `grep v-html` 命中 9 处：`TaskProcessRawPane.vue:6`（`terminalHtml` ← `views/TaskView.vue:673` `new AnsiToHtml({ escapeXML: true })`，ansi-to-html 0.7.2 经 `entities.encodeXML` 转义 `<>&"'`）、`TaskProcessTextRow.vue:45`（`renderedHtml` ← `taskProcessUtils.ts:44-62` `markdown-it({ html: false })`；highlight 分支的 `lang` 必须先命中 `hljs.getLanguage(lang)` 才会拼入 class，无法注入引号）、`TaskResultPanel.vue:128,334,401`（markdown 同上 + mermaid `securityLevel: 'strict'`，`features/tasks/useSummaryRenderer.ts:40-48`；`summaryMermaid.ts:26-46,120-140` 对 source/message 做 `escapeSummaryHtml`）、`IssueView.vue:186,353`、`views/TaskView.vue:377`（均 `renderMarkdown`）、`App.vue:91`（服务端公告文本，基线既有，见 §4）；`innerHTML` 3 处：`useSummaryRenderer.ts:67,89,149`（mermaid 输出，strict 已消毒）、`VariableEditor.vue:202`（本区间仅新增 CSS，未触及该行） |
| 10 | 401 重定向不产生循环；401 之外的鉴权失败有提示 | 部分通过 | `api/client.ts:26-38`（未改动）仅在非 `/login` 且 401 时跳转，`/login` 自身不会再跳；403 无专门处理，落入 FE-02（steering）与各页通用错误提示 |
| 11 | 终态渲染：completed/failed 渲染结果卡与交付记录 | 通过 | `TaskView.vue:287-290`（`:820-822` 的 `isTerminal`，基线值，不含 cancelled）+ `TaskResultPanel.vue:167-171`（`showCommitRecord` 分支渲染 `git_delivery`：提交/恢复列表、push 结论、diff 统计），`pushStatusLabel` 覆盖 5 个冻结状态 |
| 12 | 未知状态/未知字段降级而非崩溃 | 通过 | `statusColors`/`t(\`status.${status}\`)`（模板 `:12`）/`t(\`taskView.executionState.${status}Title\`)`（`:853`）对未知值只显示原始 key；`isActiveTaskStatus` 未知返回 false（`useTaskLogStreams.ts:12-14`）；`parseLogMetadata`/`parseTextEntry`/`parseToolCall` 对垃圾 metadata 全部回退（`taskProcessUtils.ts:396-460`） |
| 13 | 命令/事件的未知枚举不得渲染成缺失 i18n key | 通过 | `TaskSteeringPanel.vue:137-150` 未知 command status 走 `'Unknown'`（spec `:186-200` 断言不含 `taskView.`）；`taskProcessUtils.ts:135-138` 未知 control event 类型退化为原始类型名 |
| 14 | control event 消费端不静默丢弃应展示的事件 | 通过 | `taskProcessUtils.ts:463-486` 只过滤 `control.queue.updated`（attempt 级审计）与不带 `control.` 前缀的 `agent_settled`（`core/worker_event_projector.py:731-737` 写入的 `metadata.type` 为 `agent_settled`，自然不通过 `startsWith('control.')`），`control.command.{delivered,rejected,outcome_unknown}` 均进入 `TaskProcessControlEventRow` |
| 15 | `harness_options` 前端载荷与后端白名单/形状一致 | 通过 | `taskFormModel.ts:87-88,147-148` 仅在 `harnessKey==='opencode'` 时带 `harness_options`；`TaskFormDrawer.vue:1239-1248` 只发 `agent/command/model_variant`，与 `core/harness_options.py:44-49` 的 `TASK_OVERRIDE_KEYS['opencode/v1']` 完全一致；快照读取兼容 flat/namespaced（`TaskFormDrawer.vue:1256-1272`），与 `api/task_responses.py:41-47` 的 flat 投影一致 |
| 16 | harness catalog 的可用性/原因码在 UI 有对应分支 | 通过 | `TaskFormDrawer.vue:1383-1407` 覆盖后端 `api/harness_catalog.py:60-66` 的 7 个常量 + `not_selected`/`missing_payload`；`:1408-1428` 区分 `enabled===false` 与 `availability!=='present'`；create 提交在 catalog 非 ready 时禁用（`:1300-1307`）并与 `useTaskFormSubmission.ts:74-77,152-155` 双重拦截 |
| 17 | V1 只读任务（hard cut）不得出现可写交互 | 通过 | `TaskView.vue:914`（`execution_contract.read_only`）门控 execute/cancel/retry/编辑/reschedule/override 按钮（模板 `:47,77,91,119,133,160,173`）与追加任务 `:946-952`；legacy catalog 返回空 catalog（`api/harness_catalog.py:259-268`）→ capability 为 null → steering 面板隐藏 |
| 18 | 运行时长趋势改用总量后标签同步 | 通过 | `views/Analytics.vue:918-919` 改读 `total_execution_seconds`，与后端 `api/analytics_queries.py:310` 一致；`i18n/messages/en.ts:1535`、`zh-CN.ts:1513` 已改为“总运行时长”语义 |
| 19 | 运行时超时配置字段前后端一致（peak/off-peak 硬切） | 通过 | `views/config/useConfigForm.ts:33-36,79-82,148-151,284-287,338-341` 与 `views/config/RuntimeSettingsPanel.vue:41-124,371-424` 全部改用 `task_timeout_{peak,off_peak}_seconds` + `task_timeout_peak_{start,end}`，与 `backend/app/config.py:35-38,275-278` 一致；全仓已无 `task_timeout` 残留（grep 仅命中新字段） |
| 20 | 列表/卡片动画在大数据量下不退化 | 通过 | `views/UsageManagement.vue:287,366` 新增 `USER_CARD_ANIMATION_LIMIT = 20`，超过即 `animation: none` 并去掉逐卡 `animationDelay`；`views/IssueList.vue:251,656-660` 新增的 worker_profile 筛选项来自后端 filter-options（`backend/app/api/issues.py:757-760` 的 `value` 为字符串，前端转 number），无本地全量重算 |
| 21 | 与后端分类一致：`failure_kind` 标签映射 | 有缺口但非本次引入 | `TaskResultPanel.vue:432-441` 的映射表与基线逐字相同（`git show 8081c946^:frontend/src/components/TaskResultPanel.vue`），而 worker 自基线起就会产出 `authentication_error`/`rate_limited`/`crash`/`sandbox_error`（`git grep 8081c946^ -- deploy/worker-entrypoint/harness/adapters`），未命中时显示原始枚举串；属 V1 遗留，未计入问题清单 |

## 4. 局限与未验证项

- 未执行任何浏览器/E2E 验证（无 Playwright 运行、无真实后端），交互结论均为静态推导 + 现有 spec 对照。
- 未运行 `npm run build` / `vue-tsc`，因此无法排除类型层隐患（如 `api/tasks.ts:309-312` 把 `ToolCall.output` 由 `string|null` 放宽为可选后，其他消费点是否仍按非可选使用 —— 本次只抽查了 `TaskProcessToolRow` 与 `taskProcessUtils`）。
- FE-06 的重渲染开销、FE-INFO-03 的“推送确认但无提交列表”组合，均缺少真实数据/度量支撑，仅给出机制级判断。
- 未覆盖 `AIProvidersPanel.*`（T10）与测试质量本身（T16）；`WorkerSettingsPanel.spec.ts` 仅用于判定 i18n 断言方式，未评估其测试质量。
- 「V1 遗留」观察（不计入问题清单，供后续参考）：
  1. `views/TaskView.vue:1299-1320` 的 `pollTimer` 在 `await loadTaskView()` **之后**创建；若组件在首次请求期间被卸载，`onBeforeUnmount`（`:1347`）清不到该定时器，5 秒轮询会持续请求；V2 让该轮询体额外调用 `connectStructuredLogStream/reconnectLogStream`，会保留一条 SSE 连接。轮询体与基线逐字相同（`git show 8081c946^:frontend/src/views/TaskView.vue:1225-1244`）。
  2. `isTerminal`（`TaskView.vue:820-822`）不含 `cancelled`，因此 `TaskResultPanel` 的失败卡（`TaskResultPanel.vue:13,429-431` 已把 `cancelled` 计入 `hasFailure`）对取消任务永不渲染，取消原因只在执行概览卡里；`hasFailure` 与 `isTerminal` 两处基线即如此。
  3. `failure_kind` 标签映射与 worker 实际产出的枚举值不一致（§3 #21）。
  4. `App.vue:91` 用 `v-html` 渲染服务端公告文本，基线既有，建议由安全专题（T13）确认公告写入侧的转义。
