# Model Request Options 与 Task-local Egress Proxy 方案

> 状态：Proposed
>
> 日期：2026-09-10
>
> 范围：Codify Open-Harness V2、AI Provider、Worker Runtime Bundle / Worker Kit

## 1. 结论

Codify 使用一个 **Task-local、协议不转换的薄 HTTP 代理**，把 AI Provider 的
`provider_options` 合并进 Harness 发出的模型请求 JSON。

这不是四个 Harness 各自实现参数适配，也不是把三个 Model Protocol 转成统一协议：

- Claude、Codex、Pi、OpenCode 仍使用各自原生 CLI / SDK；
- `anthropic_messages`、`openai_responses`、`openai_chat_completions` 仍保持原始 wire semantics；
- 一个通用代理只在模型请求发出前修改 JSON body，响应、SSE、错误和取消语义保持原样；
- `chat_template_kwargs` 只是任意请求参数的一个例子，不建立专用字段或专用逻辑。

实现使用 Go 标准库 [`net/http/httputil.ReverseProxy`](https://pkg.go.dev/net/http/httputil)，
不在 Worker 中引入 LiteLLM、Envoy 或 mitmproxy。

## 2. 背景与现状

AI Provider 已有 `provider_options: JSON`：

- Provider API 可以保存和返回它；
- Model Endpoint Snapshot 会冻结它；
- Endpoint fingerprint 已包含它；
- Worker 能从冻结 Snapshot 恢复它；
- 当前 Provider 配置 UI 尚未提供编辑入口；
- 当前 Worker 只把 Base URL、API Key 和 Model 注入 Harness，`provider_options` 没有进入实际模型请求。

四个 Harness 与三个 Model Protocol 的现有兼容关系保持不变：

| Harness | Anthropic Messages | OpenAI Responses | OpenAI Chat Completions |
|---|---:|---:|---:|
| Claude | 是 | 否 | 否 |
| Codex | 否 | 是 | 否 |
| Pi | 是 | 是 | 是 |
| OpenCode | 是 | 是 | 是 |

如果逐 Harness 注入参数，必须分别追随四个 CLI / SDK 的配置能力和升级变化，而且某些 Harness
没有任意 request body 扩展点。统一出口代理可以在实际 HTTP 边界完成一次合并。

## 3. 目标

1. Provider 管理员可以配置任意、非敏感的模型请求参数。
2. 同一份配置对所有兼容 Harness 生效。
3. 参数随 Model Endpoint Snapshot 冻结，Task 重试继续使用原值。
4. 不改变 Model Protocol，不隐藏不兼容的 Harness / Protocol 组合。
5. 不缓冲模型响应，保留 SSE 首字节、增量事件、错误状态和取消传播。
6. `provider_options = {}` 时继续走现有直连路径。

## 4. 非目标

- 不做 Anthropic Messages、OpenAI Responses、Chat Completions 之间的协议转换。
- 不做模型路由、负载均衡、重试、限流、计费或缓存。
- 不做统一 Provider catalog 或模型能力推断。
- 不替代现有 Model Credential 生命周期，也不在本期建设 credential broker。
- 不允许 Provider 参数替换对话、工具或流式传输等 Harness 执行骨架。
- 不把 LiteLLM 等完整网关打包进每个 Worker。

需要集中路由、预算、审计或多租户鉴权时，可以独立部署
[LiteLLM Proxy](https://docs.litellm.ai/) 等上游网关，再把 Codify Provider 的 Base URL 指向它；
这与本方案不冲突。

## 5. 总体架构

```text
Model Endpoint Snapshot
  ├─ model_protocol
  ├─ base_url
  ├─ model
  ├─ credential_ref
  └─ provider_options
              │
              ▼
        Worker common runner
              │
      provider_options 非空？
         ├─ 否：保持现有直连
         └─ 是：启动 loopback proxy
                    │
Claude / Codex / Pi / OpenCode
                    │ HTTP JSON request
                    ▼
        127.0.0.1:<dynamic-port>
          校验目标请求与 JSON
          合并 provider_options
          保留原始 path / headers
                    │
                    ▼
          Snapshot upstream Base URL
```

代理是每个 Task 容器内的进程，只监听 `127.0.0.1`。它不作为 Backend 或 Host 上的共享服务，
避免不同 Task 的 Endpoint、凭据和冻结参数互相影响。

## 6. Provider 合同

### 6.1 API 与存储

复用现有字段：

```json
{
  "provider_options": {
    "chat_template_kwargs": {
      "thinking": true,
      "reasoning_effort": "high"
    },
    "temperature": 0.6
  }
}
```

不新增 `chat_template_kwargs`、`reasoning_effort` 或其他 Provider 专用数据库列，也不需要数据库迁移。

`provider_options` 的合同定义为：

- 必须是 JSON object；
- key 不做模型参数 allowlist，未知参数原样保留；
- value 支持 JSON object、array、string、number、boolean 和 `null`；
- 不允许保存 API Key、Token 或其他秘密；该字段属于非敏感 Snapshot 和 fingerprint；
- Provider 创建、更新和连接测试使用相同的校验规则。

### 6.2 保留字段

“任意参数”指不维护模型参数白名单，不代表可以破坏 Harness 请求结构。以下顶层字段由 Harness
和 Model Endpoint 合同所有，`provider_options` 出现这些 key 时 API 直接返回 `422`：

```text
model
messages
input
instructions
tools
tool_choice
stream
stream_options
```

`system_prompt` 继续使用现有 Provider 字段，不通过 `messages` 或 `instructions` 旁路注入。

首版只保护上述已知结构字段；不增加 Provider-specific denylist、参数类型目录或模型能力数据库。

### 6.3 合并规则

代理只对所选 `model_protocol` 的主推理请求执行合并：

| `model_protocol` | 目标 path suffix |
|---|---|
| `anthropic_messages` | `/v1/messages` |
| `openai_responses` | `/v1/responses` |
| `openai_chat_completions` | `/v1/chat/completions` |

其他请求原样转发，避免影响 Harness 可能发出的模型发现、token 统计或健康检查请求。

合并采用递归 JSON object merge：

1. Harness body 是基础对象；
2. `provider_options` 覆盖同名的非保留字段；
3. 两边同名且都是 object 时递归合并；
4. array、scalar 和 `null` 作为整体值覆盖，不做数组拼接；
5. 合并后重新计算 `Content-Length`；
6. 不修改 URL query、认证 header 或其他 header。

示例：

Harness body：

```json
{
  "model": "qwen3",
  "stream": true,
  "messages": [{"role": "user", "content": "hello"}],
  "chat_template_kwargs": {
    "reasoning_effort": "medium"
  }
}
```

`provider_options`：

```json
{
  "temperature": 0.6,
  "chat_template_kwargs": {
    "thinking": true,
    "reasoning_effort": "high"
  }
}
```

upstream 实际收到：

```json
{
  "model": "qwen3",
  "stream": true,
  "messages": [{"role": "user", "content": "hello"}],
  "temperature": 0.6,
  "chat_template_kwargs": {
    "thinking": true,
    "reasoning_effort": "high"
  }
}
```

因此，对支持 request-level `chat_template_kwargs` 的 vLLM 服务，请求值可以覆盖服务启动时的
`--default-chat-template-kwargs`，而 Codify 不需要理解其中的具体 key。

## 7. Proxy 合同

### 7.1 进程与网络

- 二进制：`/opt/codify-kit/bin/codify-model-proxy`；
- 监听：由进程直接 bind `127.0.0.1:0`，使用内核分配端口；
- readiness：bind 成功后原子写入 Task runtime 目录下的 readiness JSON；
- 上游：只允许启动参数指定的冻结 Base URL；
- 生命周期：common runner 启动、监控并在 Harness 结束或 Worker 收到终止信号时停止；
- 代理异常退出视为 `configuration_error`，不得静默回退到直连。

不采用“先探测空闲端口、释放、再启动”的流程，避免端口竞争窗口。

### 7.2 Base URL 保真

Harness 看到的代理 Base URL 必须保留上游 Base URL 的 path，只替换 scheme 和 authority。

```text
upstream: https://provider.example/api/v1
local:    http://127.0.0.1:43127/api/v1
```

这样现有 Adapter 对 `/v1` 的规范化仍产生与直连路径相同的最终 request path。代理转发时再把本地
scheme / authority 换回冻结上游，保留 path 和 query，不在代理内复制四个 Adapter 的 URL 规则。

### 7.3 请求与响应

仅当请求同时满足以下条件时修改 body：

- method 是 `POST`；
- path suffix 与冻结 `model_protocol` 对应；
- body 是 JSON object；
- Content-Encoding 为空。

目标推理请求不满足条件时 fail closed，返回稳定、无敏感信息的代理错误；非目标请求原样转发。

响应路径不做业务处理：

- 不读取或重写响应 body；
- 不聚合 SSE；
- 原样保留上游状态码和可转发 headers；
- 客户端断开时通过 request context 取消上游请求；
- 不增加代理级重试。

### 7.4 日志与敏感信息

代理不得记录：

- request / response body；
- Authorization、`x-api-key` 或 Cookie；
- 完整 URL query；
- `provider_options` 原文。

只允许记录启动、停止、协议、脱敏 path、状态码、耗时和稳定错误码。所有错误文本继续经过 Worker
现有敏感信息清洗后再进入 TaskLog / raw archive。

## 8. Worker 集成

### 8.1 Backend 环境注入

Backend 从冻结 Model Endpoint Snapshot 序列化以下运行时输入：

```text
CODIFY_MODEL_PROTOCOL
CODIFY_MODEL_ENDPOINT_FINGERPRINT
CODIFY_MODEL_PROVIDER_OPTIONS_JSON
```

Base URL、Model 和 Credential 继续使用现有协议环境变量。`provider_options = {}` 时不设置代理相关
运行时输入或由 Runner 直接判空，现有行为不变。

新变量加入 Worker reserved environment namespace，Shared / Profile 自定义环境变量不能覆盖。

### 8.2 Common runner

在 `adapter_prepare_config` 前增加公共步骤：

1. 校验冻结 `provider_options`；
2. 非空时启动代理并等待 readiness；
3. 把当前协议对应的 `ANTHROPIC_BASE_URL` 或 `OPENAI_BASE_URL` 切换到代理镜像 Base URL；
4. 调用现有 Adapter prepare；
5. Harness 结束时停止代理。

四个 Adapter 不解析、不筛选、不合并 `provider_options`。它们只继续消费公共环境中已经切换的
Base URL，因此没有四份参数逻辑。

### 8.3 Worker Kit 与 Runtime Bundle

Worker Kit 已有 Go build stage，新增第三个静态二进制即可，不增加 Worker 运行时依赖：

```text
deploy/worker-kit/model-proxy/main.go
    -> /worker-kit/bin/codify-model-proxy
```

Worker Kit manifest 记录代理版本、路径和 SHA-256；安装和 Runtime Verify 检查它存在且 digest 匹配。
Runtime Bundle 冻结调用代理的 common runner 和合并合同版本。Task 已冻结的 Worker Kit / Runtime
Bundle 身份继续是重试与恢复的执行事实。

## 9. Provider UI

在 AI Provider 新建 / 编辑弹窗增加一个默认折叠的“高级请求参数”区域：

- 多行 JSON 编辑框；
- 空值等价于 `{}`；
- 新建默认 `{}`；
- 编辑时格式化展示现有 `provider_options`；
- 保存前解析 JSON，并要求顶层为 object；
- 保留字段给出明确的字段名错误；
- 中英文说明明确“参数进入非敏感 Task Snapshot，请勿填写密钥”；
- 示例只展示 `chat_template_kwargs`，但标签和 API 不绑定 vLLM。

UI 不为 temperature、reasoning、thinking 等参数建立独立控件或参数目录。

## 10. Provider 连接测试

连接测试继续由 Backend 直接请求 Provider，但发送前使用与代理相同的合并合同：

- 先构造当前协议的最小测试 body；
- 再合并 `provider_options`；
- 同样拒绝保留字段；
- 保持现有无上游 body、无秘密的测试结果响应。

Python 与 Go 的实现共享一组 JSON golden vectors，至少覆盖递归 object、array 替换、`null`、保留字段
和非 ASCII 数据，防止 Backend 测试行为与 Worker 实际行为漂移。

## 11. 验证与验收

### 11.1 单元与合同测试

Backend：

- Provider 创建 / 更新接受任意 JSON 参数；
- 非 object 和保留字段返回 `422`；
- Snapshot、fingerprint 和 retry 保留原始 `provider_options`；
- 连接测试发送合并后的 body；
- Worker 环境只从冻结 Snapshot 注入选项。

Proxy：

- 三个目标 path 的递归合并；
- 非目标 path 原样转发；
- 上游 path 前缀保持；
- Authorization 等 headers 保持且不记录；
- 上游 4xx / 5xx body 和 status 保持；
- SSE 首字节不等待完整响应；
- 客户端取消会取消上游 request；
- 非 JSON、压缩请求、代理启动失败均 fail closed。

Frontend：

- JSON parse、object 校验和保留字段错误；
- 新建、编辑、清空和重新打开保持值；
- API payload 使用 `provider_options`，不创建专用字段。

### 11.2 Harness × Protocol 矩阵

使用可记录原始 upstream request 的测试服务验证：

| Harness | 必测协议 |
|---|---|
| Claude | `anthropic_messages` |
| Codex | `openai_responses` |
| Pi | 三个协议 |
| OpenCode | 三个协议 |

每个组合至少确认：

1. Harness 能完成真实模型回合；
2. upstream 实际收到 `provider_options`；
3. `model`、对话内容、tools 和 `stream` 未被改变；
4. canonical reasoning / message / usage / terminal 事件仍完整；
5. 上游错误和 Task 取消语义未退化。

### 11.3 vLLM 验收

开发环境增加一个真实 vLLM 用例：

```json
{
  "chat_template_kwargs": {
    "thinking": true,
    "reasoning_effort": "high"
  }
}
```

验收证据必须包含：

- Provider 保存后 API 返回的配置；
- Task 的冻结 Endpoint fingerprint / Snapshot 证据；
- upstream 捕获或 vLLM 可观测证据，证明 request body 包含该对象；
- Task 实际 reasoning 与 terminal 事件；
- 清空 `provider_options` 后新 Task 恢复直连路径。

源码和单元测试不能替代真实 Worker Host / Task 证据。

## 12. 上线顺序

1. 冻结 Backend 校验、合并规则和 golden vectors。
2. 增加 Provider UI JSON 编辑入口。
3. 构建 Proxy binary，接入 Worker Kit manifest / install / verify。
4. 在 common runner 接入非空选项的代理生命周期。
5. 完成 mock upstream 的 Harness × Protocol 合同矩阵。
6. 部署开发 Worker Kit / Runtime Bundle，完成真实 vLLM Task 验收。
7. 通过后随正常停机发布进入目标环境。

不增加长期 feature flag。若需要停止新流量使用代理，清空 Provider 的 `provider_options`；已冻结参数的
旧 Task / retry 继续使用其冻结 Worker Kit 和 Runtime Bundle，不改写历史 Snapshot。

## 13. 方案取舍

| 方案 | 结论 | 原因 |
|---|---|---|
| 四个 Harness 分别注入 | 不采用 | 能力不一致，跟随四个 CLI / SDK 演进 |
| 三个协议转换 Adapter | 不采用 | 本需求不需要协议转换，增加语义和流式风险 |
| 每个 Worker 内置 LiteLLM | 不采用 | 路由、鉴权、费用等能力超出需求，且仍需定制 body merge |
| mitmproxy | 不采用 | 偏调试拦截，运行时和证书能力过重 |
| Envoy + Lua | 不采用 | 对 Task 容器体积和配置复杂度过高 |
| Go stdlib Task-local proxy | 采用 | 使用成熟 HTTP transport，只维护很小的 JSON 合并边界 |

最终边界是：**一个代理、一个合并合同、三个目标协议路径、四个原生 Harness 零参数适配逻辑。**
