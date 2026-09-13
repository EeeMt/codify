# Open-Harness V2 四 Harness Subagent 适配方案

> 状态：Implemented（Backend、Worker Kit 与 Task Process 分组展示已落地；真实 dev Host 已验收）
>
> 日期：2026-09-12
>
> 范围：Claude、Codex、OpenCode、Pi 的 subagent 执行、Canonical Event 归属、Task 事件流展示与运行验收

## 1. 结论

四个 Harness 不应共用一套新的 subagent 调度器。Codify 只统一产品合同和可观测语义：

1. Claude、Codex、OpenCode 继续使用各自原生 subagent。
2. Pi Core 不内置 subagent；Worker Kit 固化经过审计的成熟上游 `pi-subagents`，Codify 只维护最薄的策略配置和事件适配。
3. Delegation 统一投影为现有 `tool.started` / `tool.completed`，不新增
   `subagent.started` / `subagent.completed` Event type。
4. 子代理产生的 message、reasoning 和 tool 事件增加可选 `payload.agent` 归属。
5. 只有 root Harness 可以结束 Task；子代理 idle、失败或取消都不能直接产生 Harness/Task terminal。
6. 继续复用 `TaskLog.log_metadata` 和现有 Task 事件流，不新增数据库表、迁移或独立 agent 工作台。

统一的是事件语义、归属、脱敏、终态和验收，不是四家内部 agent 类型、调度方式或原生协议。

## 2. 当前基线

Runtime Bundle 当前冻结版本为 Claude `2.1.153`、Codex `0.146.0`、Pi `0.84.2`、OpenCode
`1.18.19`，但 manifest 尚未声明 subagent capability：

- [`manifest.json`](../../deploy/worker-entrypoint/harness/manifest.json)
- [`harness_protocol.py`](../../backend/app/core/harness_protocol.py) 的
  `HARNESS_CAPABILITY_KEYS` 目前只有 `resume`、`task_skills`、`usage_tokens`、`steering`、
  `follow_up`。

| Harness | 原生能力 | Codify 当前适配 | 缺口 |
|---|---|---|---|
| Claude | 支持内置和自定义 subagent | 已用 `CLAUDE_CODE_SUBAGENT_MODEL` 冻结子代理模型 | Translator 未保留 `parent_tool_use_id`；并发消息和 thinking 没有按 agent 分桶 |
| Codex | 冻结二进制包含 multi-agent / `collab_tool_call` 能力 | App Server Bridge 正常工作 | `codex_events.py` 未映射 collaboration item；任务配置未显式冻结启用方式 |
| OpenCode | 原生 agent 使用 child session | Bridge 只允许 root session，避免 child idle 结束父任务 | child session 的消息、工具和 usage 在进入 raw/canonical 前被过滤 |
| Pi | Core 明确不内置 subagent，生态 Extension 已成熟 | 当前未加载 subagent Extension | 需要 Kit 固化上游 Extension、收窄能力并补事件归属 |

Pi 生态已有可直接采用的成熟 Extension：

- [`pi-subagents`](https://pi.dev/packages/pi-subagents?name=pi-subagents) 当前版本为 `0.67.0`，MIT，
  提供前台/后台 delegation、并发、流式进度、取消、可观测产物和 capability ceiling；项目已有大量实际使用与持续维护。
- [`@mjakl/pi-subagent`](https://pi.dev/packages/@mjakl/pi-subagent) 当前版本为 `3.0.1`，MIT，明确要求
  Pi `>=0.80.5`，零运行时依赖，具备独立子进程、RPC 流、并发、进程组终止和递归保护。

本方案选择 `pi-subagents` 作为生产上游，因为其维护度、可观测能力和事件接口更完整；
`@mjakl/pi-subagent` 只保留为兼容失败时的轻量备选，不同时集成两套插件。

现有 Pi `0.84.2` 源码快照也包含官方 subagent 示例：

- [`README.md`](../../deploy/worker-cli/pi/README.md) 明确说明 Core 不内置 subagent；
- [`examples/extensions/subagent/index.ts`](../../deploy/worker-cli/pi/examples/extensions/subagent/index.ts)
  使用独立 Pi 进程、JSON 模式、并行调度和 usage 汇总。

该示例只用于理解 Pi Extension 和事件机制，不再作为 Codify 自行实现 subagent 的起点。

版本边界需要真实 probe：`pi-subagents 0.67.0` 的当前包包含 `@earendil-works/pi-server 0.85.0`，
上游对 standalone 后台执行的说明以 Pi `0.85.1` 为基线，而 Codify 当前冻结 Pi 为 `0.84.2`。
Phase 0 先验证 `0.84.2 + 0.67.0` 的前台 delegation；若不兼容，升级冻结 Pi 到上游验证版本，
不通过 fork 插件或重写官方示例维持旧版本。

## 3. 目标

- 四个 Harness 都能实际调用 subagent，并返回结果给 root agent。
- Task 事件流能区分 root 和 child 的 message、reasoning、tool 与 delegation 状态。
- 多个并发 child 的事件不会互相拼接、覆盖或错误配对。
- 子代理失败只结束对应 delegation；是否继续或结束 Task 由 root Harness 决定。
- Task 取消、超时或容器收尾时，所有 child session/process 都能收敛。
- Attempt 级 usage 不漏算、不重复计算。
- 子代理原生记录经过现有脱敏边界后进入 runtime archive，并能用 `raw_ref` 定位。
- capability 只在对应冻结版本通过真实 Runtime Bundle 验收后声明为 `true`。

## 4. 非目标

- 不实现 Codify 自有多代理调度器、任务队列或跨容器 agent service。
- 不从 Pi 官方示例复制并长期维护 Codify 自有 subagent Extension。
- 不统一四家的原生 agent 定义、昵称、提示词或调度算法。
- 不新增子代理管理页、树形工作台、人工中断单个 child 的 API。
- 不允许用户在 Task 中覆盖 child model、provider、cwd 或进程并发上限。
- 不支持跨 Task、跨容器或长期持久化的 child session。
- 首版只支持 root 的直接子代理；不支持 nested subagent。
- 不用 prompt 文本猜测父子关系，也不扫描 Harness 的内部 session 文件作为旁路事件源。
- 不在运行时下载或安装第三方 Pi package。

## 5. 公共产品合同

### 5.1 Capability

V2 Runtime Manifest 新增布尔 capability：

```json
{
  "capabilities": {
    "subagents": true
  }
}
```

同时把 `subagents` 加入后端 `HARNESS_CAPABILITY_KEYS` 和四个 Harness 的 system upper bound。

- `true` 表示当前冻结 Runtime Bundle 已通过 §10 的真实验收。
- `false` 或缺失表示不得把该 Harness 描述为 subagent-compatible。
- 首版不增加 profile 开关、并发字段或 UI 配置项；Harness 使用冻结实现中的固定限制。

这属于对已冻结 V2 capability vocabulary 的显式增量；实施时必须同步更新
[`open-harness-v2-schemas.md`](./open-harness-v2-schemas.md)、manifest、校验器和四 Harness fixtures。

### 5.2 不新增 Event type

四个 Harness 的 delegation 都能对应到一个原生工具或 collaboration item：

| Harness | 原生 delegation |
|---|---|
| Claude | `Agent` tool use/result |
| Codex | collaboration / agent tool item |
| OpenCode | `Task`/subagent tool + child session |
| Pi | Kit 内置 `pi-subagents` 的 `subagent` tool |

因此继续使用已有 tool 生命周期。开始事件的目标形态：

```json
{
  "type": "tool.started",
  "payload": {
    "tool_id": "native-delegation-call-id",
    "name": "Subagent",
    "input": {
      "role": "explore",
      "task": "定位认证入口"
    },
    "subagent": {
      "id": "attempt-scoped-agent-id",
      "parent_id": "root",
      "role": "explore"
    }
  }
}
```

结束事件继续使用 `tool.completed`：

```json
{
  "type": "tool.completed",
  "payload": {
    "tool_id": "native-delegation-call-id",
    "name": "Subagent",
    "output": "子代理最终摘要",
    "error": false,
    "subagent": {
      "id": "attempt-scoped-agent-id",
      "parent_id": "root",
      "role": "explore",
      "status": "completed",
      "usage": {
        "input_tokens": 1200,
        "output_tokens": 300
      }
    }
  }
}
```

`status` 只允许 `completed`、`failed`、`cancelled`。`error=true` 表示本次 delegation 失败，
不是 Task terminal。

### 5.3 Child event 归属

Child 产生的现有 Canonical Event 在 `payload` 中附加：

```json
{
  "agent": {
    "id": "attempt-scoped-agent-id",
    "parent_id": "root",
    "role": "explore"
  }
}
```

适用类型：

- `message.delta` / `message.completed`
- `reasoning_summary.started` / `delta` / `completed` / `interrupted`
- `tool.started` / `tool.completed`
- `context.compacted`
- `diagnostic`

Root event 省略 `payload.agent`。`agent.id` 只要求在一个 attempt 内稳定且唯一；优先使用原生 child
session/thread/agent ID，没有稳定原生 ID 时使用 delegation tool ID 派生。归档中的 ID继续经过现有稳定脱敏。

实施时对 `payload.agent` / `payload.subagent` 做公共结构校验，禁止各 Adapter 私自定义不同字段。

### 5.4 配对与并发

现有 Projector 的消息缓冲和 pending tool 映射是 attempt 级全局状态。支持 subagent 后，以下状态必须按
agent 分桶：

```text
(agent_id | "root", native_message_id)
(agent_id | "root", reasoning_id)
(agent_id | "root", tool_id)
```

Adapter 生成的 `reasoning_id` 必须包含 agent 身份，避免不同 child 复用原生 message/item ID 时冲突。

首版不要求 UI 实时显示每个 token delta；如果冻结 Harness 只可靠提供 completed message，可以只发
`message.completed`，但不能把 child 最终内容伪装成 root 输出。

### 5.5 唯一终态

终态规则保持不变：

- `harness.completed` / `harness.failed` 只代表 root Harness settled。
- `run.completed` / `run.failed` 仍由公共 Runner 在 finalization 后唯一产生。
- child idle、child session error 和 `tool.completed.error=true` 不得直接改变 Task 状态。
- root 可以根据 child 失败自行决定重试、继续或最终失败；Adapter 不替 root 做业务判断。
- 观察到 nested child 时保留脱敏 raw evidence，投影 `diagnostic(code=subagent_depth_unsupported)`，
  不把它提升为第二层产品事件。

### 5.6 Usage

现有 attempt 级 `usage.final` 继续作为 Task 统计和计费的唯一权威总量。

- `payload.subagent.usage` 是展示/排障明细，不参与后端二次累加。
- 每个 Adapter 必须通过冻结版本 probe 确认 root terminal usage 是否已经包含 child。
- 已包含：直接使用原生 attempt total。
- 未包含：Adapter 汇总 root 与 child 的 leaf request usage，最终只发一个 `usage.final`。
- 不能确认时 capability 不得置为 `true`，不得以“可能少算”完成验收。

### 5.7 Raw archive 与脱敏

- Child 原生事件必须先经过现有 Harness sanitizer，再进入 `harness-events/<harness>.jsonl`。
- Canonical Event 的 `raw_ref` 指向产生它的脱敏 raw 行。
- OpenCode 的 descendant session 必须先通过当前 Task 的 parent chain 白名单，不能放行同 Server 中的任意 session。
- Pi child 的 JSON 事件通过 Extension `onUpdate.details` 回到父 Pi RPC 流，由 root-owned Bridge 归档；
  不创建由 `codify` 用户直接写入的“审计”sidecar。
- hidden reasoning、凭据、Provider key 和未脱敏 command 继续禁止进入 Canonical Event、TaskLog 和 archive。

## 6. Harness 映射

### 6.1 Claude

保留现有 CLI `stream-json` Runner，不改写为 Agent SDK：

1. 用 `Agent` tool ID 表示 delegation invocation。
2. 保留完整 assistant/user record 的 `parent_tool_use_id`。
3. `parent_tool_use_id != null` 时，将记录归属到对应 child agent。
4. 从 `Agent` tool input 的 `subagent_type`/agent type 缓存 display role。
5. message、thinking、tool 状态按 agent ID 分桶；不能在新消息开始时中断其他 agent 的 thinking。
6. 继续使用 [`worker_runtime.py`](../../backend/app/core/worker_runtime.py) 已注入的
   `CLAUDE_CODE_SUBAGENT_MODEL`，禁止 child 选择公共默认模型。

Phase 0 必须用冻结的 `2.1.153` 证明：

- 完整 child message 是否默认出现在 `stream-json`；
- partial message 是否只属于 root；
- 是否需要版本支持的显式 child-text forwarding 参数；
- tool result、child usage 与 `parent_tool_use_id` 的实际时序。

若 CLI 输出已足够，不增加 hook；只有缺失稳定 start/stop/identity 时，才考虑受控的
`SubagentStart` / `SubagentStop` hook side channel。

### 6.2 Codex

继续使用当前 App Server Bridge：

1. 在任务私有 `CODEX_HOME/config.toml` 中冻结 `0.146.0` 实际支持的 multi-agent 开关和限制。
2. 将 collaboration item 归一化为 `tool.started` / `tool.completed`，display name 为 `Subagent`。
3. 使用原生 child thread/agent ID 填充 `payload.agent`。
4. 如果 root subscription 能收到 child item，直接映射；否则使用 App Server 的公开 thread/event 接口订阅。
5. 禁止 tail Codex rollout/session 内部文件作为旁路实现。
6. Child 默认继承当前 Snapshot model/provider；不提供每次 delegation 的模型覆盖。

当前本地 vendored `codex` 是 Linux x86-64 ELF，不能用 macOS Host 直接验证。因此 feature 名称、App Server
item shape、child subscription 和 cancel 传播必须在目标 Worker 镜像中 probe，不能仅根据当前官方 API 文档猜测。

### 6.3 OpenCode

保留全局 `/event` SSE，但把 admission 与 terminal decision 分开：

1. 初始化 `allowed_sessions = {root_session_id}`。
2. 收到 `session.created/updated`，只有其 `parentID` 已在白名单中才登记为 descendant。
3. 只把 root 和 descendant 事件写入 raw/translator；其他有 session 的事件继续丢弃。
4. Translator 按 session ID 保存 message、reasoning、tool 和 usage 状态。
5. Child session ID 作为 `agent.id`，`parentID` 映射为 `parent_id`。
6. 只有 root `session.idle/error/status` 驱动 Harness settled；child idle 仅结束对应 delegation。
7. Cancel 时显式 abort 所有已知 descendant，再收敛 root；实际 cascade 行为由 probe 决定是否可省略调用。

当前需要替换的是 [`opencode_bridge.py`](../../deploy/worker-entrypoint/harness/adapters/opencode_bridge.py)
“只允许精确 root session”的过滤，而不是删除 session 隔离。

### 6.4 Pi

Pi 使用随 Worker Kit 固定版本和 digest 的 `pi-subagents`，不要求 Host 安装插件，也不在 Task 启动时访问网络。
Runtime Bundle 同时保存上游源码、lockfile、MIT license、审计记录和必要的最小 vendor patch；禁止浮动版本。

首版只启用插件的前台 delegation 路径，并设置 Codify capability ceiling：

- 只开放 root 到直接 child，累计最多 4 个 child；禁止 nested delegation。
- 只开放 Bundle 内的 `scout`、`worker`、`reviewer` 和 `delegate`；不发现用户或项目 agent。
- Child 继承 Snapshot provider/model 和 `/workspace`；禁止 tool call 覆盖 model、cwd、provider。
- 禁用后台任务、持久 session、mission/schedule、chain/council、steering、intercom 和外部 runner。
- 不向 child 注入额外 Extension、Skill 或 Prompt；只继承当前 Task 已核准的工具边界。
- 插件原生 child/run identity 映射为稳定 `agent.id`；不存在稳定 ID 时才用
  `delegation_tool_id:index` 派生。
- 插件的前台 lifecycle、message、tool、usage 和最终摘要经父 Pi RPC 流进入 `pi_events.py`，
  不扫描插件工作目录补事件；结果压缩保留有界的 child `toolCalls[]`（原生 tool id/name、
  output、error 和可选开始/结束时间），未匹配到原生 `toolResult` 时不伪造 output。
- Task cancel 必须调用插件公开取消路径并等待 child 收敛；若上游前台路径不能证明进程树收敛，
  只补一个局部 vendor patch，不复制其调度器。

Codify 的适配层只负责加载固定插件、注入上述 ceiling、验证调用参数和翻译事件。若上游公开配置无法
表达某项限制，允许维护小型、可审计的 vendor patch；不重新实现 delegation、并发或 child lifecycle。

Parent Pi 仍由现有 `pi_owner.py` 独占 stdin/stdout；Extension 不直接写 canonical `event.jsonl`。

## 7. Backend 与 UI 投影

### 7.1 Backend

复用现有表：

- `TaskHarnessEventReceipt` 继续负责 Canonical Event 幂等和顺序。
- `TaskPayload` 继续保存完整 message/tool 文本。
- `TaskLog.log_metadata` 保存 `agent` / `subagent`，不新增列。

`WorkerEventProjector` 需要：

1. 将 message/reasoning/tool 的 `payload.agent` 复制到 `TaskLog.log_metadata`。
2. 按 agent identity 隔离 message delta、reasoning 和 tool 配对状态。
3. Delegation tool row 保留 `payload.subagent` 的 role/status/usage。
4. 回放、重连和重复 event 仍保持幂等。
5. Adapter 只有在原生流提供可信时间时才携带 `payload.started_at` / `payload.ended_at`；
   Projector 校验 RFC3339 后用其计算 tool duration，否则回退到 Canonical Event 的接收时间。
   `TaskLog.id` 仍是唯一稳定到达顺序，不按时间戳重排并发 child。

### 7.2 Frontend

首版不新增页面或第二套事件状态，只增强现有 `TaskProcessPanel` 单一事件流的展示投影：
直接子代理按 `agent.id` 形成连续分组；root 事件仍留在同一条时间线，组内事件继续按
`TaskLog.id` 展示顺序排列。

```text
Root event before delegation                                      10:12:00
┌─ Subagent · reviewer #1       已完成 · 5.0s · 1.5k tokens      10:12:01
│  ├─ Thinking                    1.2s                         10:12:02
│  ├─ Read backend/app/auth.py                                  10:12:03
│  └─ Assistant 认证入口位于……                                 10:12:05
└─
┌─ Subagent · reviewer #2       已完成 · 4.1s · 1.4k tokens      10:12:01
│  ├─ Thinking                    0.9s                         10:12:02
│  └─ Assistant 另一处入口位于……                               10:12:05
└─
Root continuation                                               10:12:06
```

#### 7.2.1 前端归一化模型

`taskProcessUtils.ts` 从 `TaskLog.metadata.agent` / `subagent` 解析公共字段，不从 tool name、文本或
Harness 特有 metadata 猜测：

```ts
interface ProcessAgentRef {
  id: string
  parentId: string
  role: string
  ordinal: number | null
}

interface ProcessSubagentState extends ProcessAgentRef {
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  inputTokens?: number
  outputTokens?: number
}
```

- `NormalizedTextEventRow`、`NormalizedToolEventRow` 和 `NormalizedCompactRow` 增加
  `agent: ProcessAgentRef | null`；`null` 表示 root，渲染完全保持现状。
- Delegation 仍是 `NormalizedToolEventRow`，仅增加 `subagent: ProcessSubagentState | null`，
  不新增第五种 row kind。
- 同一 attempt 中只有一个相同 role 时显示 `Subagent · reviewer`；出现多个相同 role 时，按该
  agent/subagent ID 首次出现的 `TaskLog.id` 稳定编号为 `reviewer #1`、`reviewer #2`。默认页不暴露原生长 ID。
- 归一化输入以 `TaskLog.id` 为稳定顺序；`created_at` 只用于显示时间。并发 child 在同一时间戳下
  不能重排。
- 展示层把同一直接 child 的 delegation、message、reasoning 和 tool 行放入一个连续块；块按其中
  事件首次出现的位置插入 root 时间线，组内仍按 `TaskLog.id` 排列。该操作不改写 TaskLog、
  Canonical Event 或 Raw archive 的到达顺序。

#### 7.2.2 行为与状态

| Canonical Event | 事件页表现 |
|---|---|
| root `tool.started` + `subagent` | 对应 child 分组的 header；显示角色、任务摘要、spinner 和“运行中” |
| child reasoning | 一级缩进的 Thinking row；保留现有进行中、完成、耗时行为 |
| child tool | 一级缩进的 Tool row；保留现有输入/输出按需展开 |
| child message | 一级缩进的 Assistant row；保留现有 preview 和全文展开 |
| root `tool.completed` + `subagent` | 原地结束 delegation row；显示已完成/失败/已取消、耗时和可选 token 明细 |
| root message/tool | 保持当前样式和行为 |

- Delegation row 复用 `TaskProcessToolRow`：`Subagent` 使用现有 icon 集中的 branch/people 图标，
  输入摘要显示委派任务，完整输入和最终摘要继续使用现有展开区域。
- Child row 在对应分组内增加一条轻量引导线并缩进一级，delegation header 使用统一的
  `Subagent · <display role>` 标识；不为不同 child 生成颜色，身份始终靠文字区分。
- Child 最终 Assistant row 正常展示；delegation output 默认折叠，避免同一摘要在页面上展开显示两次。
- `failed` 使用现有 error tag；`cancelled` 使用中性 tag；`completed` 不增加高饱和绿色块。
  状态必须有文字，不能只靠颜色或图标。
- `subagent.usage` 存在时只在 delegation row 显示紧凑 token 明细，不参与事件数或总量计算；
  缺失时不显示占位符。
- Child diagnostic 不单独增加新 row；可行动失败汇总到 delegation row，完整信息留在 Raw 页。

#### 7.2.3 组件落点

- `taskProcessUtils.ts`：解析 agent/subagent、生成同 role 稳定编号、按 `TaskLog.id` 排序。
- `TaskProcessPanel.vue`：继续负责单一事件流、payload expansion、自动滚动和事件计数；调用
  `groupTaskProcessRows` 生成只读展示分组，不建立 agent store。
- `TaskProcessTextRow.vue` / `TaskProcessToolRow.vue`：消费归一化后的 badge、缩进和 delegation 状态。
- 新增一个无状态的 `TaskProcessAgentBadge.vue`，复用两种 row 的 badge 与无障碍标签；不承担数据归并。
- `TaskLog` API shape 和 SSE endpoint 不变；`metadata` 中已有的 `agent` / `subagent` 是唯一新增输入。

现有实时行为保持不变：新 child row 到达时沿用当前自动滚动；用户已向上滚动时不抢焦点，继续通过
“最新”按钮返回底部；delegation 完成只更新原 row，不增加 event count。Raw 页继续展示合并后的原生脱敏流。

桌面和移动端使用同一 DOM。桌面缩进 `20px`，窄屏可降到 `12px`；role 和 preview 可省略号截断，
状态、时间和展开按钮不可被挤出容器。`390px` 和 `1512px` 下都必须满足页面级
`scrollWidth == clientWidth`。

不增加整棵 child 折叠、树形导航、agent tabs、拓扑图、agent 过滤器或独立统计面板；分组只解决同一
直接 child 的可读性，不引入第二套事件模型或持久化排序。

## 8. 取消、超时与失败

| 场景 | 必须行为 |
|---|---|
| child 正常完成 | 更新对应 delegation tool row；root 继续 |
| child 失败 | `tool.completed.error=true`；root 决定是否继续 |
| child 被 root 取消 | 对应 delegation 为 `cancelled`；Task 不自动失败 |
| Task 用户取消 | 停止 root 和全部 child；最终唯一 `run.failed(status=cancelled)` |
| Task 超时 | 停止 root 和全部 child；最终 failure.kind 为 `timeout` |
| Bridge/Adapter crash | 公共 Runner 按现有规则产生唯一 Harness/Task failure |

所有 Harness 都必须验证“取消后不再产生 Provider 请求”。仅依赖容器最终销毁不是 Adapter 正常取消的验收证据。

## 9. 实施阶段

### Phase 0：冻结二进制 probe

在目标 Worker 镜像中分别捕获一个 root + 两个 child 的完整原生流：

| Harness | 必须确认 |
|---|---|
| Claude | `parent_tool_use_id`、child text、thinking/tool 时序、terminal usage |
| Codex | feature/config 名称、collaboration item shape、child thread event、cancel |
| OpenCode | `parentID`、child session lifecycle、usage、abort cascade |
| Pi | `0.84.2 + pi-subagents 0.67.0` 前台 event shape、usage、并发、取消和 capability ceiling；失败时验证 Pi `0.85.1` |

Probe 产物脱敏后进入 `docs/harness-probes/v2/subagents/<harness>/`。没有 probe 证据的字段不进入冻结合同。

### Phase 1：公共合同与投影

- 增加 `subagents` capability vocabulary 和 manifest upper bound。
- 校验 `payload.agent` / `payload.subagent`。
- Projector 按 agent 分桶并保留 metadata。
- 前端按 `TaskLog.id` 稳定排序，增加 agent badge、同 role 编号、一级缩进和 delegation 状态。
- 公共 protocol/projector/frontend fixtures。

### Phase 2：原生 Adapter

建议按风险从低到高实施：

1. OpenCode descendant whitelist；
2. Claude `parent_tool_use_id`；
3. Codex collaboration item/App Server child thread。

每个 Harness 完成 Adapter fixture 后，manifest 仍保持 `subagents=false`，直到 Phase 4 真机通过。

### Phase 3：Pi 上游插件集成

- 把审计后的 `pi-subagents` 精确版本、依赖、license 和 digest 固化进 Runtime Bundle。
- 通过 capability ceiling 或最小 vendor patch 固定 agent、Provider/model/cwd、前台模式和并发。
- 衔接 Pi RPC raw、Canonical Event、usage 与取消收敛。
- 不引入 npm/git runtime install，不复制官方示例另造 Extension。

### Phase 4：Runtime Bundle 与真实 Task 验收

- 构建不可变 Worker Kit，核对 digest 和 manifest composition。
- 在开发 Host 用真实 Provider、真实 Task 跑 §10 矩阵。
- 浏览器核对事件流、raw archive 和 Task terminal。
- 单个 Harness 全部通过后才把对应 `subagents` capability 置为 `true`。

## 10. 验收矩阵

完整验收覆盖 8 个合法 Harness/Model Protocol 组合：

| Harness | Model Protocol |
|---|---|
| Claude | `anthropic_messages` |
| Codex | `openai_responses` |
| Pi | `anthropic_messages`、`openai_responses`、`openai_chat_completions` |
| OpenCode | `anthropic_messages`、`openai_responses`、`openai_chat_completions` |

每个组合必须完成：

1. Root 明确启动两个 child；两个 child 分别执行一个工具并返回不同 marker。
2. Canonical Event 中两个 child 的 `agent.id`、role、message、tool start/end 不串线。
3. 默认事件流可看到 delegation 状态、child badge、child 最终消息和工具。
4. Child idle/失败先发生时，root 仍能继续并最终产生唯一 terminal。
5. `usage.final` 与 Harness/Provider 原生总量一致；child 明细之和不会被后端再次累加。
6. Task 取消后，child session/process 已终止且不再产生 Provider 请求。
7. Runtime archive 包含对应脱敏 raw 行；Canonical `raw_ref` 可解析。
8. Archive、TaskLog、API 和浏览器页面不泄漏凭据或 hidden reasoning。
9. 两个同 role child 在事件页显示稳定 `#1/#2`，root/child 事件按 `TaskLog.id` 交错且刷新后不重排。
10. Delegation 从运行中原地变为 completed/failed/cancelled，不新增重复 row，失败不伪装为 Task terminal。
11. 在 `390px` 与 `1512px` 浏览器 viewport 下 badge、状态、时间和展开操作可用，页面无水平溢出。

证据分层记录，不能互相替代：

```text
source + unit fixtures
        ↓
immutable Runtime Bundle composition
        ↓
development Host process/session evidence
        ↓
real Task canonical/raw/usage evidence
        ↓
served browser event-stream evidence
```

## 11. 预计改动面

公共合同与投影：

- `backend/app/core/harness_protocol.py`
- `backend/app/core/harness_registry.py`
- `backend/app/core/worker_event_projector.py`
- `deploy/worker-entrypoint/harness/manifest.json`
- `frontend/src/components/TaskProcessPanel.vue`
- `frontend/src/components/task-process/taskProcessUtils.ts`
- `frontend/src/components/task-process/TaskProcessTextRow.vue`
- `frontend/src/components/task-process/TaskProcessToolRow.vue`
- 新增 `frontend/src/components/task-process/TaskProcessAgentBadge.vue`
- 中英文 i18n 与对应测试

Harness 适配：

- `deploy/worker-entrypoint/harness/adapters/claude_events.py`
- `deploy/worker-entrypoint/harness/adapters/codex.sh`
- `deploy/worker-entrypoint/harness/adapters/codex_events.py`
- `deploy/worker-entrypoint/harness/adapters/opencode_bridge.py`
- `deploy/worker-entrypoint/harness/adapters/opencode_events.py`
- `deploy/worker-entrypoint/harness/runners/pi-run.sh`
- Runtime Bundle 内新增固定版本的 `pi-subagents`、Codify policy 配置及必要的最小 vendor patch

Schema、fixtures、Runtime Bundle build inventory 和验收文档随对应阶段同步更新。该清单是评审边界，
不是要求一次提交修改全部文件；实施应按 Phase 拆成可独立验证的窄提交。

## 12. 上游依据

- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
- [OpenCode agents](https://opencode.ai/v2/docs/agents)
- [OpenCode SDK event subscription](https://opencode.ai/v2/docs/build/sdk)
- [OpenAI Agent session subagent identity](https://developers.openai.com/api/reference/typescript/resources/beta/subresources/agents/subresources/sessions/subresources/subagents/methods/list)
- [`pi-subagents` package](https://pi.dev/packages/pi-subagents?name=pi-subagents) 与
  [`pi-subagents` source](https://github.com/nicobailon/pi-subagents)
- [`@mjakl/pi-subagent` package](https://pi.dev/packages/@mjakl/pi-subagent)（轻量备选）
- Pi `0.84.2` 的本地冻结 README 与官方 subagent Extension 示例，见 §2。

OpenAI Agents API 的身份字段只用于公共命名参考，不代表 Codex App Server `0.146.0` 的 wire contract；
Codex 的最终映射必须以 Phase 0 目标镜像 probe 为准。
