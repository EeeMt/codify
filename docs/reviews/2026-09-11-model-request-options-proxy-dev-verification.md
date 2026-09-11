# Model Request Options 与 Task-local Egress Proxy —— 开发环境验收记录

> 日期：2026-09-11
>
> 分支/HEAD：`dev @ e2972e40`（验收改动未提交，位于工作区）
>
> 目标 Host：`192.168.50.129`（docker context `remote`）
>
> 触发改动：`docs/architecture/model-request-options-egress-proxy.md` 实现（Backend 校验/合并、Worker Kit 代理二进制、common runner 生命周期、Provider UI）
>
> Tier：Tier 2 子集（Provider/Task/Harness 链路 L4）+ Harness × Model Protocol 合同矩阵
>
> 结果：**通过**（§11.2 Harness × Protocol 矩阵与 §11.3 真实 vLLM 用例均为真机证据，见第 3、6 节）

## 1. 交付物与制品

| 项 | 值 |
|---|---|
| Worker Kit | `0.6.17`，manifest sha256 `606c7e83560f1c9974acca7ed7da4d3f54d38ad29ad0ef57e38e7d153ea534cd` |
| Kit 安装路径 | `/home/codify/worker-kits/0.6.17-linux-amd64-606c7e83560f` |
| Kit 代理 | `bin/codify-model-proxy` sha256 `e352c32c5a1787ee916faf4c2dc0ebd8795cd6ebd670d73e5fadb89dbc9f4269`（version 0.1.0） |
| Worker Profile | `id=4 v2-canary-four-harness`（`mounted_kit`，四个 Harness 全启用），`POST /api/worker-profiles/4/verify-runtime` 通过 |
| Worker 镜像 | `127.0.0.1:5000/codify-worker/java21-maven@sha256:234582c692d1ebb00ba8e882160618c2258463149d968009ac81c545e63a538b` |
| Runtime Bundle 来源 | backend 镜像重建（`make rebuild-backend` + `docker-compose up -d scheduler`），实测镜像内 `/opt/codify/runtime-source/deploy/worker-entrypoint/**` 含新逻辑 |

Kit 0.6.17 在**本机** builder 上导出（`make worker-kit-export WORKER_KIT_VERSION=0.6.17 WORKER_KIT_PLATFORM=linux/amd64 WORKER_KIT_CLI_SELECTION=pi,opencode,claude,codex`）：目标机 `/` 仅剩 1–4 GB，Nix closure 构建报 `No space left on device`。归档经 `scp` 上传后由 `deploy/worker-kit/install.sh` 安装（content-addressed，receipt 校验通过）。

## 2. 实现要点

- **Backend**：`backend/app/core/provider_request_options.py` 定义唯一合同（保留字段集合、校验、递归合并）；`providers.py` 在创建/更新（422）与连接测试中使用同一合同与同一合并实现；`worker_runtime.py` 仅当冻结 Snapshot 的 `provider_options` 非空时注入 `CODIFY_MODEL_PROVIDER_OPTIONS_JSON`；该键加入 Worker reserved namespace。
- **Proxy**：`deploy/worker-kit/model-proxy/main.go`（Go stdlib `net/http/httputil.ReverseProxy`）实现 §7 合同：`127.0.0.1:0` bind、原子 readiness JSON、路径保真、目标请求 JSON object 递归合并（保留字段永不合并）、非目标请求与响应/SSE/取消/状态码原样透传、压缩或非 JSON 目标请求 fail closed、日志不含 body/query/凭据。
- **Kit**：Dockerfile 构建并在构建期 `go vet`/`go test`；manifest 记录 `model_proxy{version,path,sha256}`；`install.sh` 与 `verify-runtime.sh` 校验存在性与 digest 一致性（`content_inventory` 双保险）。
- **Worker common runner**：`codify_model_proxy_start/stop`（`harness/runner.sh`，即 common runner 本体），在 `adapter_prepare_config` 前启动并把当前协议 Base URL 镜像到 loopback；Harness 结束、initializer 失败、TERM/INT、EXIT finalizer 四条路径都停止代理；四个 Adapter 无任何参数逻辑。
- **Frontend**：Provider 新建/编辑弹窗新增默认折叠的「高级请求参数」JSON 编辑区（空值等价 `{}`、编辑时格式化、保留字段给出字段名错误、中英文提示参数进入非敏感 Snapshot 且不得填写密钥），payload 使用 `provider_options`。
- **共享 golden vectors**：`deploy/worker-kit/model-proxy/testdata/golden_vectors.json` 同时驱动 Go 与 Python 测试（递归 object、array 替换、`null`、保留字段、非 ASCII、大整数精度）。

## 3. Harness × Protocol 真机矩阵（§11.2）

测试服务为 dev 主机上的**记录型转发代理**（throwaway，转发到真实 Provider 并记录原始请求 body；测试后已移除）。每个组合均为**真实 Worker 容器 + 真实 Harness CLI + 真实模型回合**，Task 均为 `task_mode=execute / session_mode=fresh / require_changes=true`，Kit 0.6.17。

| Harness | Protocol | Task | 结果 | Commit | 目标 path（合并） | provider_options（upstream 实测） | reasoning 事件 | terminal |
|---|---|---|---:|---|---|---|---:|---|
| Claude | `anthropic_messages` | 591 | completed | `1d3ebfc9` | `/zen-go/v1/messages` ×4 | `{"temperature":0.6,"top_p":0.95}` | 8 | `run.completed` |
| Codex | `openai_responses` | 590 | completed | `cf4eadcb` | `/deepseek/v1/responses` ×5 | `{"chat_template_kwargs":{"thinking":true,"reasoning_effort":"high"}}` | 6 | `run.completed` |
| Pi | `anthropic_messages` | 583 | completed | `50e7dc64` | `/deepseek-anthropic/v1/messages` ×5 | `{"temperature":0.6}` | 10 | `run.completed` |
| Pi | `openai_responses` | 588 | completed | `28ba5c8e` | `/deepseek/v1/responses` ×9 | `chat_template_kwargs{...}` | 4 | `run.completed` |
| Pi | `openai_chat_completions` | 585 | completed | `554e3d95` | `/deepseek/v1/chat/completions` ×4 | `{"temperature":0.6}` | 6 | `run.completed` |
| OpenCode | `anthropic_messages` | 579 | completed | `5d45db4e` | `/zen-go/v1/messages` ×6 | `{"temperature":0.6,"top_p":0.95}` | 10 | `run.completed` |
| OpenCode | `openai_responses` | 589 | completed | `ea3307cf` | `/deepseek/v1/responses` ×5 | `chat_template_kwargs{...}` | 4 | `run.completed` |
| OpenCode | `openai_chat_completions` | 581 | completed | `86bb905f` | `/zen-go/v1/chat/completions` ×6 | `{"temperature":0.6,"top_p":0.95}` | 10 | `run.completed` |

每个组合同时确认：

1. **合并生效**：该 Task 的**每一次**目标推理请求 body 都带有冻结的 `provider_options`（记录型上游实测，不是单元测试推断）。
2. **Harness 骨架未被替换**：目标请求中 `model` 等于 Provider 模型、`stream=true`、`tools`（3–10 个）、`messages`/`input`、`instructions`、`stream_options` 保持 Harness 原值。
3. **代理只在非空选项时启动**：archive `console.log` 含 `Model request options proxy active for protocol ...`。
4. **canonical 协议未退化**：`event.jsonl` seq 连续、唯一 terminal 且位于末尾、含 `worker.finalization`；`harness-result.json` 与 DB 状态一致，任务产出 commit。
5. **非目标请求原样转发**：Task 572 中 Claude CLI 的 `HEAD /deepseek-anthropic` 经代理转发（proxy 日志 `status=501`，上游原样状态），未被合并逻辑改写。

### 3.1 空选项直连对照（§3 目标 6）

Provider `provider_options={}` → 新建 Task 592（Claude/`anthropic_messages`）completed：archive `console.log` **不含** proxy 启动行，upstream 收到的是 Harness 原始 body（无 `temperature`/`top_p`），直连路径未改变。

### 3.2 收口后最终布局冒烟

矩阵在 `harness/common.sh` 版本上执行（代理生命周期块初始放在该模块）。收口时该块移入 common runner 本体 `harness/runner.sh`（`worker-entrypoint` 模块有 450 行预算，`common.sh` 因此回到 420 行），Backend 镜像重建、Profile `verify-runtime` 重跑后对最终布局重跑冒烟：

- Task 594（Claude/`anthropic_messages`，Provider 3）completed，commit `e322797c`，4 次目标请求全部带 `{"temperature":0.6,"top_p":0.95}`，`model=minimax-m2.7` 保持，`console.log` 含代理启动行，canonical terminal `run.completed`。
- 操作要点：改动 `deploy/worker-entrypoint/**` 后除重建 Backend 镜像外，**必须重跑 `POST /api/worker-profiles/{id}/verify-runtime`**；否则 Task 创建会以 `V2 Runtime Bundle evidence Adapter digest does not match frozen Adapter` 失败（fail closed，符合预期）。

### 3.3 环境相关失败（非本改动引入）

矩阵首轮的部分失败均定位为 dev Provider/模型环境问题，改用可用 Provider 后全部通过，且失败形态在**直连对照**下同样复现：

- `claude` CLI + `deepseek-anthropic`：4 次上游 200、工具调用与文件写入均成功，但收尾报 `Harness result normalization failed`（开启与关闭代理完全一致 → 与本改动无关）。
- OpenRouter `z-ai/glm-5.2:free` 已下架（上游 404 "This model is unavailable for free"）；opencode zen `gpt-5.6-luna` 不接受 `temperature`。
- 一次 `codex` Task 在创建阶段返回 `missing_execution_attempt`（无执行 attempt），重跑即 completed；与代理无关。

## 4. 单元与合同测试

| 层 | 命令 | 结果 |
|---|---|---|
| Backend | `pytest tests/unit` | 通过（含新增 `test_provider_request_options.py`、Provider 422/合并、连接测试合并、Worker 环境仅从冻结 Snapshot 注入） |
| Proxy | `go vet ./... && go test ./...`（Kit 构建阶段执行） | 通过（golden vectors、SSE 首字节、取消传播、fail closed、readiness 原子性） |
| Frontend | `npx vitest run`、`npx vue-tsc --noEmit`、`npm run build` | 通过（新增高级参数解析/保留字段/清空/编辑格式化用例） |

## 5. 回滚与清理

- Provider 3/4/5/6/7/9/14/15/16 已恢复验收前的 `base_url` / `model` / `provider_options={}`（验收期间仅临时指向记录型上游或 vLLM）。
- 记录型上游容器已移除；上传的 Kit 归档与安装脚本已从目标机删除。
- Worker Profile 4 保持在 Kit `0.6.17`（`verify-runtime` 已通过）；Kit `0.6.16` 目录保留为回滚坐标。
- vLLM 服务已停止（验收后释放约 5 GB 内存）；`/home/vllm` 安装保留，启动命令见 §6。

## 6. §11.3 真实 vLLM 验收（通过）

### 6.1 服务器

dev 目标机无 GPU（`docker run --gpus all` → `could not select device driver "" with capabilities: [[gpu]]`），因此使用 vLLM 的 CPU 构建：

| 项 | 值 |
|---|---|
| 运行时 | `/home/vllm/venv`（独立 CPython 3.12 + `vllm-cpu==0.29.0`，upstream vLLM 源码的社区 CPU 打包，PyPI `vllm-cpu`，GPU 主机不使用） |
| 模型 | `Qwen/Qwen3-0.6B`（bfloat16） |
| 端点 | `http://192.168.50.129:18001/v1`（OpenAI Chat Completions） |
| 资源约束 | systemd 单元 `vllm-cpu`，`MemoryMax=7G`（避免影响目标机其它服务） |

启动命令（验收后已停止；`vllm` CLI 在该 CPU 打包下会因发行名不同报 `No package metadata was found for vllm`，故使用模块入口）：

```bash
systemd-run --unit=vllm-cpu --collect -p MemoryMax=7G -p MemorySwapMax=0 \
  -E HF_HOME=/home/vllm/hf -E VLLM_CPU_KVCACHE_SPACE=2 \
  /home/vllm/venv/bin/python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-0.6B --host 0.0.0.0 --port 18001 --served-model-name qwen3-0.6b \
  --max-model-len 12288 --dtype bfloat16 --max-num-seqs 1 --enforce-eager \
  --enable-auto-tool-choice --tool-call-parser hermes [--reasoning-parser qwen3]
```

### 6.2 证据

| 验收要求 | 证据 |
|---|---|
| Provider 保存后 API 返回配置 | `PATCH /api/providers/16` → `base_url=http://192.168.50.129:18080/vllm/v1`, `model=qwen3-0.6b`, `provider_options={"chat_template_kwargs":{"thinking":true,"reasoning_effort":"high"}}` |
| Task 冻结 Snapshot / fingerprint | Task 601/603/604/605：`task_worker_profile_snapshots.model_endpoint_snapshot` 的 `provider_options` 即为该对象，fingerprint `v2:abac0d57d91c046f3188cfcc1e93b7e6`；清空后 Task 602 的 fingerprint 变为 `v2:6e059949ddd5ace6a8feef62a475ff32`（选项参与指纹） |
| upstream 捕获 / vLLM 可观测 | 记录型上游（vLLM 前置）：Task 601/603 的**每一次**目标请求 body 均含该对象；`console.log` 有 `codify-model-proxy: started ... upstream_path=/vllm/v1` + `Model request options proxy active`。另有 vLLM 请求级消费证明：`chat_template_kwargs={"enable_thinking":false}` → 回复 `Hi!`，不带该参数 → 回复 `<think>...`（同一 prompt/温度，`v2.9.0` 模板确实按请求参数渲染） |
| Task 实际 reasoning 与 terminal 事件 | Task 601：`run.completed`（commit `29aa4a9f`）；Task 603/604/605：**4 个 reasoning 事件** + `run.failed` terminal（`Pi protocol ended without complete terminal lifecycle: final_assistant_text`） |
| 清空后恢复直连 | Task 602：completed（commit `6137657e`），`console.log` 无代理启动行，上游 body 不含该对象 |

**已知限制（模型能力，非本改动）**：`Qwen3-0.6B` 在 CPU 上开启 reasoning parser 时只产出 thinking，Pi 要求回合以 final assistant text 收尾，因此带 reasoning 的三个 Task 终态为 `run.failed`；关闭 reasoning parser 时 Task 601 可 completed 但不产生 reasoning 事件。要同一 Task 同时满足"completed + reasoning 事件"，需换用更大的模型（如 Qwen3-4B/1.7B）或 GPU 主机。此外 OpenCode 固定发送 `max_tokens=32000`，本 CPU 服务器 `max-model-len` 受内存限制为 12288，故 §11.3 用例选用 Pi；`Codex`/`Pi` 的 `max_completion_tokens=8192` 在 12288 上下文内可正常服务。
