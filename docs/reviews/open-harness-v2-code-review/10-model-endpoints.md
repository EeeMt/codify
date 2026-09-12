# 10 Model Endpoint 重命名、Provider 配置、请求选项出口代理 —— Code Review

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56`（`dev @ cbad9e56`，2026-09-12） |
| 主要文件（diff 行数） | `backend/app/core/model_endpoints.py` (+102/-13)、`backend/app/core/provider_request_options.py` (+73 新增)、`backend/app/api/providers.py` (+268/-30)、`backend/app/api/config_runtime.py` (+59/-8)、`backend/app/api/project_webhooks.py` (+13/-2)、`backend/app/api/task_creation_service.py` (+146/-20)、`backend/app/api/task_update_service.py` (+62/-10)、`deploy/worker-kit/model-proxy/main.go` (+420 新增)、`main_test.go` (+481 新增)、`testdata/golden_vectors.json` (+162 新增)、`go.mod` (+3)、`deploy/worker-entrypoint/harness/runner.sh` (+169/-2)、`deploy/Dockerfile.worker-kit` (+108/-12)、`frontend/src/components/config/AIProvidersPanel.vue` (+535/-102)、`AIProvidersPanel.spec.ts` (+247/-23)、`frontend/src/api/index.ts` (+61/-7) |
| 交叉核查文件（只做契约一致性） | `backend/app/core/worker_runtime.py` (+295/-23)、`harness_registry.py` (+259/-30)、`harness_execution_policy.py` (+246 新增)、`worker_environment_variables.py` (+47/-1)、`model_credentials.py`、`config_crypto.py`、`backend/alembic/versions/074_open_harness_v2.py`、`078_remove_provider_driver.py`、`deploy/worker-kit/install.sh`、`verify-runtime.sh`、`frontend/src/i18n/messages/{en,zh-CN}.ts`、`docs/architecture/model-request-options-egress-proxy.md` |
| 审查方法 | 读 HEAD 完整文件与调用方（不止看 diff）+ 契约对照（egress-proxy 方案 §6–§9、2026-09-11 dev 验收记录）+ 全仓递归 grep 重命名残留（`wire_protocol`/`provider_driver`）+ 1 次指纹端到端复现（直接调用 `normalize_endpoint` → `_model_endpoint_from_snapshot`）+ 2 组窄范围单测 + 核对 Go 1.24 `net/http/httputil/reverseproxy.go` 上游行为（hop-by-hop 剥离 / flush / hijack） |
| 实际运行的验证 | ① `cd backend && .venv/bin/python -m pytest tests/unit/test_model_endpoints.py tests/unit/test_provider_request_options.py -q` → **32 passed**；② `cd backend && .venv/bin/python -m pytest tests/unit/test_providers_api.py tests/unit/test_project_webhooks_api.py -q` → **70 passed**；③ 指纹复现（见 MEP-01）→ 复现出 `RuntimeError: Task 42 has a tampered frozen model endpoint fingerprint` |
| 未覆盖 | Go 代理运行时行为（本机无 `go` 工具链，`go test ./...` 与 Dockerfile 内的 `go vet/go test` 均**未运行**）；真实上游 / Worker Host 端到端（引用既有 dev 验收记录，未复现）；前端渲染与视觉（未起 dev server）；V1 历史数据的真实分布；Worker Kit 归档/安装（T09）、Runtime Bundle/readiness（T08）、迁移（T14）、Go/前端测试质量（T16） |

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 0 |
| FIX_IF_CHEAP | 2 |
| DEFER | 2 |
| ACCEPT/CLOSE | 2 |

`wire_protocol` → `model_protocol` 重命名在生产代码里**干净**：RENAME COLUMN、`provider_driver` 列已删除、快照旧键只在 4 处 reader（`worker_runtime.py:119-121`、`harness_execution_policy.py:164-166`、`task_responses.py:168-170`、`task_runtime_summary_routes.py:43-44`）中回退，不存在写新值读旧值的静默失效；代理只替换 scheme/authority、path/query 保真，hop-by-hop 头在 `Rewrite` 前剥离，SSE 立即 flush、取消可传播、无代理级重试。无 FIX_NOW；需修 2 条 FIX_IF_CHEAP（MEP-01、MEP-03）；其余 4 条按内部离线、约 3 名用户的 beta 画像接受。

## 2. 问题清单

### MEP-01 Backend 与 Worker 对 endpoint 快照字段的归一化不一致，带首尾空格的 Provider 配置会导致任务执行期误报"指纹被篡改"
- **判定**：FIX_IF_CHEAP —— 仅存量脏配置可触发
- **位置**：`backend/app/core/model_endpoints.py:125-129`（提交 `90a2593d`；对端 `backend/app/core/worker_runtime.py:177-178`、`:187-191`）
- **证据**：Backend 冻结指纹时用的是**原样字符串**——`normalize_endpoint()` 通过 `_attr_str()`（`model_endpoints.py:74-76`）取值，不做任何 `strip`（`model_endpoints.py:104-105`），这些值直接进入 `endpoint_fingerprint()` 的 payload（`model_endpoints.py:127-128`）；而 Worker 侧重算指纹时先 `strip`——`_model_endpoint_from_snapshot()` 用 `required_string()`（`worker_runtime.py:124-127`）取 `base_url`/`model` 并 `return value.strip()`，随后用同一个 `endpoint.fingerprint` 与快照里冻结的值比对，不等就抛 `Task {id} has a tampered frozen model endpoint fingerprint`（`worker_runtime.py:187-191`）。API 侧 `base_url` 只校验前缀、不做归一化（`providers.py:145-149`）；API 层同样接受该值：实测 `UpdateProviderRequest(base_url='https://api.example.com/v1 ')` 与 `CreateProviderRequest(...)` 都原样保留尾随空格（`model` 侧 `validate_model` 会 `strip`，`base_url` 侧不会）；前端虽然 `trim()` 后再提交，`AIProvidersPanel.vue:753`，但 API/`PATCH` 接受 `"https://api.example.com/v1 "`）。实测复现（本机 venv，直接调用两侧函数，无 DB/网络）：
  ```
  base_url='https://api.example.com/v1 ' → stored fingerprint v2:830f0c3f8ab539a3437f4b4517ad37b4
                                          snapshot base_url 'https://api.example.com/v1 '
                                          → RuntimeError: Task 42 has a tampered frozen model endpoint fingerprint
  base_url='https://api.example.com/v1'  → 指纹一致，正常
  model=' m'                             → 同样触发上述 RuntimeError
  ```
- **影响**：只要 Provider 的 `base_url`（或 `model`，例如 V1 历史行）带有首尾空格，用该 Provider 新建的**每一个** Task 都能创建成功（`create_task_record` 不做 strip，快照与指纹都按原样写入），但在 Worker 启动解析快照时必然抛错，任务以"指纹被篡改"这种误导性理由失败，且重试永远失败。诊断成本高（错误指向数据被篡改，而不是配置含空白字符）。
- **最小动作**：`_attr_str` 返回 `value.strip()`（2 行）；先跑 `SELECT id,name FROM ai_providers WHERE base_url<>btrim(base_url) OR model<>btrim(model);` 判定脏行
- **验证**：已实际运行上表复现脚本（修复后同样脚本应输出"指纹一致"）；另需为 `normalize_endpoint`/`_model_endpoint_from_snapshot` 增加一条带空白的快照往返断言（现有测试只用干净值，`backend/tests/unit/test_model_endpoints.py`）。

### MEP-03 `endpoint_transport_fingerprint()` 是死代码，其 docstring 声称的"Provider 重绑定检测"没有任何调用方
- **判定**：FIX_IF_CHEAP
- **位置**：`backend/app/core/model_endpoints.py:148-169`（提交 `90a2593d`）
- **证据**：全仓（排除 node_modules/.git/coverage/.venv）grep `transport_fingerprint` 只有 3 处命中：定义本身、以及 `backend/tests/unit/test_model_endpoints.py:12,66-67` 的自测。没有任何生产调用点。其 docstring 却写着"this narrower value is used only when checking that the source Provider still points at the same endpoint"——该检查在实现中不存在；实际存在的只有 `worker_runtime.py:187-191` 用完整 `endpoint.fingerprint` 做的篡改校验（一旦 Provider 的 max_turns/system_prompt 被改动，快照与源 Provider 的指纹就会不同，但冻结语义正是"任务不受后续编辑影响"，所以并不需要该函数）。
- **影响**：无功能影响；但会误导后续维护者以为存在一条"transport rebind"检测路径（例如以为 Provider 改了 base_url 会阻断排队任务），且该函数与 `endpoint_fingerprint()` 是同一 payload 的两份复制，任何一侧改动（例如再加入一个字段）都会静默漂移。
- **最小动作**：删函数 + `test_model_endpoints.py` 2 条断言（净 -20 行）
- **验证**：静态 grep 已确认；删除后 `pytest tests/unit/test_model_endpoints.py` 应仅需删掉对应断言。本次已运行该文件（32 passed，含 2 条 `endpoint_transport_fingerprint` 断言）。

### MEP-02 `provider_options` 保留字段契约未覆盖 Task 创建路径：遗留行会让已冻结的保留参数被代理静默丢弃
- **判定**：DEFER
- **位置**：`backend/app/api/task_creation_service.py:518-527`（提交 `6a6e6f63`，契约来自 `6d8153f5`；对端 `deploy/worker-kit/model-proxy/main.go:344-352`）
- **证据**：同一份 `provider_options` 契约在代码里有三个强制点：Provider 写入 422（唯一实现 `providers.py:74`，由 `create`/`update` 的 model_validator 调用，`providers.py:118-125`、`providers.py:595-606`）、连接测试 422（`providers.py:357`）、以及 Worker 代理的**静默丢弃**（`main.go:349-352` `if reservedRequestFields[key] { continue }`，仅在启动日志里记一条 `provider_options_reserved_keys_ignored count=N`，`main.go:180-182`）。Task 创建路径只校验 `provider_kind`/`model_protocol`/`compat_profile`（`task_creation_service.py:518-527`），**不校验** `provider_options` 是否含保留字段；`normalize_endpoint()` 也不会拒绝（`model_endpoints.py:79-81` 只判断 `isinstance(dict)`）。V1 的写入校验只有 `if not isinstance(provider_options, dict)`（`8081c946^:backend/app/api/providers.py:58-59` 的 `_validate_kind_protocol` 只判断 `isinstance(provider_options, dict)`），因此"`provider_options = {"stream": false}`"这类遗留行是可达状态——作者自己在连接测试里就为它写了用例（`backend/tests/unit/test_providers_api.py:1047-1058`，期望 422）。
- **影响**：对该类遗留 Provider，(a) 连接测试返回 422（拒绝），(b) 却能成功创建新 Task，快照把 `stream: false` 一起冻结并注入 Worker 环境（`worker_runtime.py:452-459`），(c) 代理启动后把它悄悄丢掉（只有一条启动日志）。(b)+(c) 的组合让管理员看到"参数已保存、任务已创建"，但上游请求里该参数**从未生效**，与 §6.2"出现这些 key 时 API 直接返回 422"的契约不一致，且失败无可观测信号（既不在 TaskLog 的规范化错误里，也不使任务失败）。
- **最小动作**：先跑 `SELECT id,name FROM ai_providers WHERE provider_options ?| array['model','messages','input','instructions','tools','tool_choice','stream','stream_options'];`；>0 行才在 `normalize_endpoint` 滤除保留键（3 行），=0 行书面接受关闭
- **验证**：为"Provider 携带保留字段 → 创建 Task"补一条 API 用例断言 422；已确认现有 `test_connection_test_rejects_legacy_reserved_options` 覆盖连接测试一侧。本次未运行端到端 Task（需 DB/Worker）。

### MEP-04 重命名未覆盖用户可见术语：Provider 面板与 i18n 仍以 "Wire Protocol / Wire 协议" 展示 `model_protocol`
- **判定**：DEFER —— 仅 3 名可信同事可见
- **位置**：`frontend/src/components/config/AIProvidersPanel.vue:77,236`（提交 `cbad9e56`/`6a6e6f63`；文案 `frontend/src/i18n/messages/en.ts:2255-2259`、`zh-CN.ts:2226-2230`）
- **证据**：字段、API、DB 列、快照键、Go 代理参数均已改为 `model_protocol`，但表单标签仍取 `t('config.providers.wireProtocol')`（`AIProvidersPanel.vue:236`）、移动卡片同样（`:77`，`cbad9e56` 新增行），文案为 `wireProtocol: 'Wire Protocol'` / `'Wire 协议'`（`en.ts:2255`、`zh-CN.ts:2226`），协议下拉的 i18n key 也是 `wireProtocolAnthropicMessages` 等（`AIProvidersPanel.vue:423-432`）。
- **影响**：仅术语不一致（用户在 UI 上看到的仍是已被废弃的 "Wire Protocol" 概念，而 API 字段叫 `model_protocol`，harness 兼容性矩阵文档也用 Model Protocol）；不影响功能。
- **最小动作**：下次改面板时把 i18n key 机械改名（en/zh-CN + spec）
- **验证**：`grep -rn "wireProtocol" frontend/src` 应归零；本次未运行前端测试。

### MEP-INFO-01 `compat_profile` 目前是无消费者字段，且 CI auto-repair 创建路径不校验其 allowlist
- **判定**：ACCEPT/CLOSE
- **位置**：`backend/app/core/model_endpoints.py:29`、`backend/app/api/task_creation_service.py:523-524`、`backend/app/core/ci_failure_collector.py:716-722`
- **证据**：`compat_profile` 只出现在：Provider 写入校验（`providers.py:127-132,203-208`）、`normalize_endpoint`（`model_endpoints.py:85-87`）、快照/指纹（`model_endpoints.py:63,126`）、Worker 快照 reader（`worker_runtime.py:149-151,181`）、创建期 allowlist（`task_creation_service.py:523-524`）。没有任何**行为分支**读取它——既不影响协议选择、路径后缀（`main.go:51-55`）、也不影响 harness 兼容矩阵（`harness_registry.py:351-366` 只看 `model_protocol`）。同时 CI auto-repair 的创建路径只调用 `ensure_harness_protocol_compatibility(profile_default_key, endpoint)`（`ci_failure_collector.py:719`），没有 `COMPAT_PROFILES` 检查，也没有 `require_task_executable_contract`（后者在 Scheduler claim 才兜底，`worker_task_lifecycle.py:516`）。
- **影响**：当前无功能影响（该值只参与指纹与快照）。若将来把 compat_profile 接入执行分支，"仅 Provider 写入 + 交互式创建校验"的覆盖不足（CI 自动修复任务、或直接改库的值会绕过），建议届时把 allowlist 校验下沉到 `normalize_endpoint`/`ensure_harness_protocol_compatibility` 这类唯一入口。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：grep `compat_profile` 全仓消费者已确认；未构造 CI 修复场景运行。

### MEP-INFO-02 前端没有 `compat_profile` 入口，TS 类型缺 `clear_compat_profile`：API 设置的值在面板不可见、不可改
- **判定**：ACCEPT/CLOSE —— 字段无消费者前补 UI/清空入口是为未来需求写代码
- **位置**：`frontend/src/api/index.ts:234-239`、`frontend/src/components/config/AIProvidersPanel.vue:751-759`
- **证据**：后端 `UpdateProviderRequest` 支持 `compat_profile` 与 `clear_compat_profile`（`providers.py:184-185,643-646`），TS 侧 `UpdateProviderRequest` 只有 `compat_profile?: string | null`（`index.ts:238`）没有 `clear_compat_profile`；面板的编辑表单没有该字段（`resetForm()`/`openEdit()` 都不含 `compat_profile`，`AIProvidersPanel.vue:660-715`），保存时也不发送它（`AIProvidersPanel.vue:751-759`）。
- **影响**：通过 API 设置过 `compat_profile` 的 Provider，在面板里看不到该配置、也无法清除，只能靠 API；由于写入时未发送该字段，PATCH 不会误清空（当前行为无数据风险）。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态阅读 UI 与类型定义；未运行前端。

## 3. 逐项核查记录（关键不变量/契约 → 结论 → 依据）

| # | 不变量 / 契约 | 结论 | 依据 |
|---|---|---|---|
| 1 | `wire_protocol` 重命名完整性（生产代码无残留） | 通过 | 全仓 grep 仅命中：迁移 `074_open_harness_v2.py:36-46`/`064`（历史列定义）、`078`（删除 `provider_driver`）、4 处显式 V1 兼容 reader（`worker_runtime.py:119-121`、`harness_execution_policy.py:164-166`、`task_responses.py:168-172`、`task_runtime_summary_routes.py:41-44`）、V1 迁移测试（`test_074_migration.py`）与旧文档/`frontend/coverage/**`（构建产物）。`backend/app` 内无任何生产代码写 `wire_protocol` |
| 2 | 快照 JSON 旧键读取不会静默给错值 | 通过 | 三处 reader 都是 `model_protocol or wire_protocol` 顺序回退，且都归一化 `-`→`_`（`worker_runtime.py:121-125`、`harness_execution_policy.py:164-167`、`task_runtime_summary_routes.py:34-44`）；新写入端只有 `as_snapshot()`（`model_endpoints.py:56-70`）与 `capture_provider_runtime_snapshot`（`worker_runtime.py:332-340`） |
| 3 | 前后端 API 契约一致（protocol/provider_options） | 通过 | 后端序列化 `model_protocol`/`compat_profile`/`provider_options`（`providers.py:274-282`）与 `frontend/src/api/index.ts:188-239` 一致；保留字段清单三处一致：`provider_request_options.py:21-32`、`main.go:61-70`、`AIProvidersPanel.vue:369-378`（Go 侧另有 golden vector 断言 `main_test.go:95-108`） |
| 4 | `compat_profile` 未知值在 Task 创建时被拒绝 | 通过（但见 MEP-INFO-01） | `task_creation_service.py:523-524` 抛 `HarnessRegistryError` → 422；Provider 写入侧 `providers.py:127-132,203-208`；`normalize_endpoint` 把空串归一为 None（`model_endpoints.py:85-87`） |
| 5 | Endpoint 指纹纳入 `model_protocol`/`compat_profile`/`base_url`/`model`/`provider_options`/`max_turns`/`system_prompt` | 通过 | `model_endpoints.py:123-140`；`max_turns`/`system_prompt` 仅在 `max_turns is not None` 时纳入，正是为了兼容"执行控制加入契约前"的 v2 快照（`:131-140`）；指纹版本前缀 `v2`（`:24`）避免与 v1 混用 |
| 6 | 不同 Provider 不会共用同一指纹（缓存/去重语义） | 通过（除 MEP-01 的空白归一化差异） | 指纹 payload 含 base_url+model+protocol+kind+compat_profile+options（`model_endpoints.py:123-140`）；`credential_ref`/`name`/`id` 刻意不入指纹（secret-free），会话命名空间由 harness+指纹决定（`harness_sessions.py:24-40`） |
| 7 | 快照是 model/base_url/credential 的唯一事实源，Provider 后续编辑不改写排队任务 | 通过 | `resolve_provider` 优先走 `model_endpoint_snapshot`（`worker_runtime.py:75-92`），`_resolve_frozen_provider` 只用快照的 base_url/model/options + 独立解析 credential（`worker_runtime.py:218-320`）；`provider_runtime_snapshot` 仅叙事用途 |
| 8 | 仓库/Profile 自定义环境不能改写 model/base_url/credential | 通过 | `validate_worker_environment_variable_key` 拒绝 `ANTHROPIC_/OPENAI_/CODIFY_/CLAUDE_/CODEX_/OPENCODE_/PI_` 前缀与保留集（`worker_environment_variables.py:94-112`），且 `build_worker_environment` 在合并前逐键复验（`worker_runtime.py:404-406,519-520`） |
| 9 | 协议组合由冻结 Bundle 决定，不受"今天的矩阵"放宽 | 通过 | `runtime_bundle_model_protocols` 以 Bundle manifest 的 `adapters[key].model_protocols` 为准且拒绝未声明协议（`harness_registry.py:298-348`）；`ensure_harness_protocol_compatibility(..., runtime_bundle=…)` 在 provider 切换时传入（`task_update_service.py:151-158,255-265`，`runtime_bundle` 由 `get_task_with_access_check` eager load，`task_operations.py:62-70`）；创建后在绑定 Bundle 后再校验一次（`task_creation_service.py:728-732` → `harness_execution_policy.py:162-176`） |
| 10 | 代理不把 Provider 凭证转发给 harness | 通过 | 代理只把上游响应原样回传（无 `ModifyResponse`，`main.go:236-253`），请求方向转发的是 harness 自己带的认证头（`main_test.go:233-235` 断言 `Authorization` 原样透传）；worker 环境注入的是冻结凭证，代理从不注入/改写认证头（`main.go:239-248` 只改 scheme/host 并 `SetXForwarded`） |
| 11 | hop-by-hop 头处理 | 通过 | Go 1.24 标准库 `net/http/httputil/reverseproxy.go:399` 在调用 `Rewrite`（同文件 `:419`）**之前**执行 `removeHopByHopHeaders`；`Rewrite` 只设置 URL/Host 与 `X-Forwarded-*`，不会再引入 hop-by-hop 头（`main.go:240-248`）。`Transfer-Encoding`/`Content-Length` 在合并后被显式清理（`main.go:307-311`） |
| 12 | 合并优先级与语义（provider 默认覆盖 harness 骨架，但保留字段永不覆盖） | 通过（Python/Go 由同一 golden vectors 钉住） | Python `merge_provider_request_options`（`provider_request_options.py:58-73`）与 Go `mergeProviderOptions`（`main.go:344-361`）语义一致：object 递归、array/scalar/null 整体替换、保留字段 `continue`；共享向量含递归/数组替换/null/非 ASCII/大整数/保留字段（`golden_vectors.json`），两侧测试读取同一文件（`test_provider_request_options.py:29-45`、`main_test.go:79-92`）；本次运行的 Python 侧 32 passed |
| 13 | 代理只改目标推理请求；非目标请求/响应/状态码/SSE 原样透传 | 通过 | `isTargetRequest` = POST 且 path 以协议后缀结尾（`main.go:274-276`，三协议表 `:51-55`）；无 `ModifyResponse`；`FlushInterval: -1`（`main.go:239`，Go 1.24 `net/http/httputil/reverseproxy.go:619` 用 `http.NewResponseController(dst).Flush`，`statusRecorder` 同时实现 `Flush()` 与 `Unwrap()`，`main.go:412-420`，flush 能力不被包装破坏）；`http.NewResponseController(rw).Hijack()`（同文件 `:755-756`）同样经 `Unwrap` 可达底层 writer |
| 14 | 超时/重试不产生重复请求或重复计费 | 通过 | 代理无重试逻辑（`main.go` 无 retry/backoff）；`http.Transport` 对 POST 带 body 不重放（不可 replayable）；`ErrorHandler` 只回 502（`main.go:249-252`）；无 `http.Client` 级 timeout，长流式请求不会被代理截断 |
| 15 | 目标请求无法合并时 fail closed（不静默直连） | 通过 | `applyProviderOptions` 对压缩体、非 JSON、空体、超 64MiB、编码失败返回稳定错误码（`main.go:281-312`），`ServeHTTP` 直接回 502 且**不转发**（`main.go:260-267`）；`main_test.go:291-343` 断言上游从未被调用 |
| 16 | 代理监听与鉴权 | 通过（设计如此） | 默认 `--listen 127.0.0.1:0`（`main.go:86`），内核分配端口，无共享服务；Runner 也显式传 `127.0.0.1:0`（`runner.sh:288`）；因此无需鉴权，也不暴露给容器外 |
| 17 | Base URL 保真（只替换 scheme/authority） | 通过 | Runner 镜像函数保留上游 path、剥离 query（`runner.sh:223-234`）；Go 侧 `Rewrite` 只改 `Scheme`/`Host`/`Out.Host`（`main.go:240-248`），path/query 来自 harness 请求；dev 验收实测 path `/deepseek-anthropic/v1/messages` 等保真 |
| 18 | 代理生命周期覆盖 delivery 文本生成，不残留"指向死端口"的 Base URL | 通过 | 启动在 `codify_harness_initialize`（`runner.sh:55-58`，早于 `adapter_prepare_config`）；停止只在启动失败分支（`runner.sh:305`）与 EXIT finalizer（`bootstrap.sh:303`）中调用，任务收尾文本生成仍在代理存活期内（对应 2026-09-11 验收 §7 的修复 `fe733f05`） |
| 19 | 代理密钥/敏感信息不落日志 | 通过 | 只记录 path（`sanitizedPath`，剥 query，`main.go:364-370`）、协议、状态码、耗时与稳定错误码；`upstream_host`/`upstream_path` 不含 query/userinfo（`url.Parse` 的 `Path`）；`provider_options` 原文不记录（仅 count，`main.go:181`） |
| 20 | Provider CRUD 鉴权与越权 | 通过 | 路由级 `require_authenticated_user`（`main.py:487-491`），写操作额外 `require_admin_user`（`providers.py:444,500,571,701,772`）；读接口不返回密钥（`api_key_configured` 布尔，`providers.py:266-270`） |
| 21 | 连接测试不泄漏密钥、不跟随重定向 | 通过 | 错误详情仅回稳定文案（`providers.py:461-487`），日志详情对 url/api_key 做替换（`providers.py:374-380`）；`follow_redirects=False`（`providers.py:457`）；`_provider_connection_target` 去除 userinfo/query（`providers.py:364-372`） |
| 22 | 连接测试使用与代理相同的合并/保留字段契约 | 通过 | `_provider_connection_request` 复用 `validate_provider_request_options` + `merge_provider_request_options`（`providers.py:301-363`）；测试覆盖合并与遗留保留字段（`test_providers_api.py:1014-1058`），本次运行 70 passed |
| 23 | SSRF（用户可控 base_url 打内网/元数据） | 通过（设计权衡，非缺陷） | `base_url` 必须 `http(s)://` 前缀（`providers.py:145-149`），仅管理员可写；内网地址（`host.docker.internal:11434`）正是受支持的 Provider 形态（UI 默认占位即此，`AIProvidersPanel.vue:202-205`），因此不做网段封锁；连接测试无并发限流（前端单飞，`AIProvidersPanel.vue:831-840`），仅管理员可触发 |
| 24 | 密钥加密存储与轮换 | 通过 | `api_key` 与 `ModelCredential.secret_encrypted` 均经 `encrypt_config_secret`（`providers.py:522-535`、`providers.py:660-674`，`model_credentials.py:30-44`）；轮换时新建 credential 并 soft-retire 旧的（`providers.py:650-674`），删除 Provider 只 soft-retire（`providers.py:748-756`），已冻结任务仍能解析 retired 凭证（`model_credentials.py:79-101`） |
| 25 | webhook secret 不可读时的轮换 | 通过（本次修复有效） | `setup_gitlab_project_webhook` 捕获 `ConfigEncryptionError` 后签发新 secret 并让 `ensure_project_webhook` 轮换 GitLab 侧 token（`project_webhooks.py:176-189`）；GitLab 调用失败时 `get_db` 会回滚（`database.py:44-52`），不会留下"本地新 secret / GitLab 旧 token"的不一致；新增用例覆盖（`test_project_webhooks_api.py:352-380`，本次 70 passed 含该用例） |
| 26 | Kit 中代理二进制缺失/篡改时整 Kit fail closed | 通过 | 安装期校验 manifest path/sha 与文件摘要、内容清单（`install.sh:120-133`）；`verify-runtime.sh:84-102` 校验 `model_proxy` 字段、content_inventory 唯一命中且 sha 一致；构建期记录 version+sha（`Dockerfile.worker-kit:94-107`） |
| 27 | 代理启动失败不静默回退直连 | 通过 | Runner 在 readiness 缺失或进程提前退出时 `return 1`，使 harness 初始化失败（`runner.sh:294-321`），不存在"代理失败→直连"的分支 |
| 28 | 前端请求选项编辑的类型校验与提交契约 | 通过 | 空值等价 `{}`、非 object 报错、保留字段列出字段名（`AIProvidersPanel.vue:455-480`）；提交始终使用 `provider_options`（`:751-790`）；i18n 键中英文齐备（`en.ts:2262-2266`、`zh-CN.ts:2233-2237`）；spec 覆盖创建/编辑/清空/非法 JSON（`AIProvidersPanel.spec.ts:446-535`，未运行） |

## 4. 局限与未验证项

- **Go 代理未运行**：本机无 `go` 工具链（`go: command not found`），`cd deploy/worker-kit/model-proxy && go test ./...` 与 Dockerfile 构建期的 `go vet ./... && go test ./... -count=1`（`Dockerfile.worker-kit:19-21`）**均未执行**。Go 侧结论来自完整源码阅读 + 上游 `go1.24` `net/http/httputil/reverseproxy.go` 行为核对（`removeHopByHopHeaders` 在 `Rewrite` 之前、`NewResponseController` 的 flush/hijack 路径）+ `main_test.go` 的断言阅读，属静态推理。
- **端到端未复现**：真实 Provider / Worker Host / Harness CLI 的组合行为未复现，引用 `docs/reviews/2026-09-11-model-request-options-proxy-dev-verification.md`（Task 572–607 的 Harness × Protocol 矩阵与 vLLM 用例）。MEP-02 的影响链路（创建 Task → 代理丢弃保留键）未经真机验证。
- **V1 历史数据分布未知**：MEP-02 与 MEP-INFO-01 的触发前提是"存在 `provider_options` 含保留字段的 Provider 行"或"存在非 allowlist 的 compat_profile"。V1 校验只判断 dict（`8081c946^` 的 `providers.py`），代码上可达，但本机无生产库，未统计真实命中数。
- **前端未运行**：未执行 `vitest`/`vue-tsc`/dev server/MEP 中提到的 UI 行为（`AIProvidersPanel.spec.ts` 只做静态阅读）。已单独确认"移除 `:scroll-x` 后仍可横向滚动"不成立为缺陷（naive-ui auto layout 下 `xScrollable` 仍为真，`node_modules/naive-ui/es/data-table/src/use-scroll.mjs:14-21`；且 `81b25e6d` 已为卡片加 `min-width: 0`），故未列为问题。
- **config_runtime / 项目 webhook 的其它改动**（peak/off-peak 超时模型、`get_visible_projects`）只在"是否影响本专题契约"的范围内核查，细节归 T11/T15/T13 文档。
- **重命名残留的构建产物**：`frontend/coverage/**` 仍是旧字段（`wire_protocol`），按 README §1 作为产物入库合规性问题处理，未做内容审查。
