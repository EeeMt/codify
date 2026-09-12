# 04 OpenCode Task-scoped Server / Bridge 生命周期 —— Code Review

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56`（审查修订：`dev @ cbad9e56`） |
| 文件 | `deploy/worker-entrypoint/harness/adapters/opencode.sh`（+452，新增于 `333dbc90`）；`deploy/worker-entrypoint/harness/adapters/opencode_bridge.py`（+1293，新增于 `333dbc90`）；`deploy/worker-entrypoint/harness/runners/opencode-run.sh`（+240，新增于 `2c3b95c7`）。三者均为 V2 全新文件，无删除行。 |
| 审查方法 | 对 `cbad9e56` 当前完整文件逐函数静态阅读（非只看 diff）+ 契约对照；跨模块核查调用方（`harness/runner.sh`、`harness/common.sh`、`worker-entrypoint/bootstrap.sh`、`main.sh`、`delivery.sh`、`backend/app/core/harness_options.py`、`worker_runtime.py`）；把冻结制品 `deploy/worker-cli/opencode/opencode`（1.18.19 Bun 单文件二进制，内含 JS 源码/路由表）当作上游事实源逐条核对 HTTP 路由、CLI 旗标、env 名与心跳周期；对照 `docs/harness-probes/v2/opencode/`、`docs/architecture/open-harness-v2-phase3-opencode-design.md`；跑窄范围单测。 |
| 未覆盖 | `opencode_events.py` 的 SSE 映射与 settled 判定（T05 专题，仅核对桥接↔translator 的接口边界）；`materialize_skills` 的 skills 内容语义（T08/T09）；真实 OpenCode Server / Docker 容器内的实际信号路径（本机不可运行，见 §4）。 |
| 已执行的验证 | `cd backend && .venv/bin/python -m pytest tests/unit/test_opencode_harness_adapter.py -q -k "status or legacy_runner"` → `10 passed, 86 deselected in 16.24s`；桥接客户端路由复现脚本（见 OCB-01「验证」）；本机 bash 子进程/信号实验（见 OCB-03「验证」）。 |

## 1. 结论摘要

| 等级 | 数量 |
|---|---|
| P0 | 0 |
| P1 | 1 |
| P2 | 1 |
| P3 | 1 |
| INFO | 3 |

整体质量结论：OpenCode 适配器的骨架与设计/探针证据一致——Task-scoped `opencode serve`（loopback 显式 `--port`、Task 私有 Basic 口令、`--pure`、XDG/HOME 全量隔离）、先订阅 `/event` 再 prompt、Server 独立进程组 + TERM→KILL 收敛、凭据只经 env 注入、HTTP 审计脱敏、快照强制覆盖 provider/model、命令面确定性 reject（与 Pi 同一 reject 词表）等关键点在 §3 逐条核查通过。主要缺陷是桥接的「SSE 断开后恢复会话终态」兜底查询打在了 1.18.19 **不存在的路由**（`GET /session/{id}/status`）上（OCB-01），使该设计路径完全失效，并把「连接断了但 Server 仍活着」的场景一律误判为 `session_missing`；其次是快照凭据缺失时 `prepare_config` 静默跳过整份 `opencode.json` 物化却返回成功（OCB-02）。其余为需要实机确认的环境/隔离假设（OCB-03/04/05/06）。

## 2. 问题清单

### OCB-01 Session 状态兜底查询使用了 1.18.19 不存在的路由
- **等级**：P1
- **位置**：`deploy/worker-entrypoint/harness/adapters/opencode_bridge.py:584-586`（消费点 `:806-880`、审计模板 `:84-99`/`:104-112`）（提交 `333dbc90`）
- **证据**：
  - 实现：`def status(self, session_id): return self._request("GET", f"/session/{quote(session_id)}/status")`，`_recover_status()` 用它判定「断线后会话是否已 idle」，其 docstring 同样写 `poll GET /session/status`。
  - 冻结制品 `deploy/worker-cli/opencode/opencode`（1.18.19）中 `/session/{id}/...` 的**全部**子路由为：`abort / children / command / diff / fork / init / message / prompt_async / revert / share / shell / summarize / todo / unrevert`——**没有 `status`**；状态路由只有集合级 `GET /session/status`（`status(w,O){...url:"/session/status"}`，`C.get("status",Dn.status,...)`，注释为 "current status of **all** sessions"），且官方前端读取方式就是 `data.session_status?.[sessionID]`。
  - probe 证据与设计同口径：`docs/harness-probes/v2/opencode/README.md`（"也见 `GET /session/status` 轮询 `{type:busy}` → `{}`"）、设计 §3.1（"`GET /session/status` 作为恢复/兜底"）。
  - 复现（本机执行，无需真实 Server）：给 `OpenCodeServerClient._request` 打桩后调用 `status('ses_abc')` → 实际发出 `('GET', '/session/ses_abc/status')`；同时 `_http_path_template('/session/status')` 返回 `/session/{session_id}`、`_http_operation` 返回 `session.get`（即修好 URL 后审计标签也要一起改，否则把集合路由记成单会话 GET）。
  - 现有单测（`test_opencode_run_attempt_status_fallback_after_disconnect` 等）全部 stub 掉客户端，故本缺陷不被覆盖（`-k "status or legacy_runner"` 10 passed）。
- **影响**：`_recover_status()` 在两条路径被调用（`:1248-1251`：SSE 传输断开、或流正常结束但未见到终态信号）。此时 Server 若仍存活（典型：SSE 被中途切断/IncompleteRead/读超时，而进程未死），请求落到不存在的路由 → 404 → 走 `status_code == 404` 分支，向 translator 投递 `session_missing: OpenCode session status returned 404`（T05 分类为 `engine_error`）。后果有二：(1) 设计承诺的"断线后恢复真实状态（含最终 assistant 文本）、必要时收敛为成功"永久不可达；(2) 一个实际已 idle/已完成的回合会被交付为 `session_missing` 引擎错误，交付结论与事实不符，且会误导运维定位（Server 明明活着却报 session 不存在）。注意 Server 进程真死时走的是连接异常分支（报 `OpenCodeServerCrash`），不受本缺陷影响。
- **建议**：改用集合路由并按 sessionID 取值，同时补齐审计模板：

```
    def status(self, session_id: str) -> tuple[int, dict]:
        return self._request("GET", "/session/status")
```

```
    if route == "/session/status":
        return "/session/status"
```

```
        ("GET", "/session/status"): "session.status",
```
  并把 `_recover_status()` 的解析从 `body.get("info")` 改为按 sessionID 索引（`body.get(session_id)`，兼容 `{sessionID: {type: "idle"|...}}` 形状）。
- **验证**：修复后可用单测断言 `OpenCodeServerClient.status()` 发出的路径为 `/session/status`、且 `_recover_status` 能从 `{"<sid>": {"type": "idle"}}` 恢复出 `session.idle`；实机验证需真实 Server（未运行）。

### OCB-02 快照凭据缺失时静默跳过 provider 配置物化
- **等级**：P2
- **位置**：`deploy/worker-entrypoint/harness/adapters/opencode.sh:240-270`（提交 `333dbc90`）
- **证据**：`if [ -n "${model}" ] && [ -n "${base_url}" ] && [ -n "${api_key}" ]; then ... 写 opencode.json ... fi` 之后直接 `export OPENCODE_MODEL="${model}"` 并 `return 0`。三者只要有一个为空，`opencode.json` 完全不落盘，但 `prepare_config` 仍成功返回（`codify_harness_initialize` 认为配置就绪，runner 正常启动 Server、readiness 通过）。后端 `AIProvider.api_key` 允许为空（`backend/app/models.py:259`，`api_key: str | None`），创建/更新接口亦然（`backend/app/api/providers.py:108,176`），连接测试在无 key 时只是省掉鉴权头（`api_key:` 条件分支），即「无凭据 Endpoint」是后端允许的合法配置。
- **影响**：对无凭据（或 base_url 为空）的 Endpoint，OpenCode Task 会在 Server 侧以 "provider/model 未配置" 类错误失败，最终被归类为协议/引擎错误且错误信息与真实原因（快照未物化 provider）无关；同时 HTTP 审计里 `config_sha256` 恒为 null，缺一条可诊断线索。属于错误路径不健壮，不会造成错误交付（fail-closed 发生在更晚的模型调用阶段）。
- **建议**：在 protocol 分支后显式 fail-closed：`model` 为空 → 直接报错返回 1；`base_url`/`api_key` 为空时也返回 1 并在 stderr 指明"快照端点/凭据缺失"，而不是静默跳过（若产品上确需支持无凭据端点，则应写出不带 `apiKey` 的 provider 配置并在文档中明确）。
- **验证**：以 `ANTHROPIC_MODEL` 有值、`ANTHROPIC_API_KEY` 为空的 env 调 `opencode_adapter_prepare_config`，断言返回非 0 且 stderr 有明确原因；本次仅静态推理，未运行该场景。

### OCB-03 取消/超时路径的硬停 TERM 到不了 Harness（公共 Runner 机制）
- **等级**：P3
- **位置**：`deploy/worker-entrypoint/harness/runner.sh:134-136`（`adapter_run ... &` / `CODIFY_HARNESS_ADAPTER_PID=$!`）与消费点 `deploy/worker-entrypoint/harness/adapters/opencode.sh:407-445`、`deploy/worker-entrypoint/bootstrap.sh:269-277`（提交 `333dbc90` / `2c3b95c7`；机制属公共 Runner，T07 亦有覆盖）
- **证据**：`adapter_run` 是 shell 函数，`&` 产生的是**子 shell 进程**，`$!` 即该子 shell 而非其内部的 `timeout … runner.sh`。本机实验（bash 3.2.57，脚本形状与 `opencode_adapter_run` 一致：函数内多条语句 + 末条 `timeout … > file`）：`subshell pid=72203`，其子进程为 `timeout`(72205)→`sleep`；`kill -TERM $!` 后子 shell 立即消失，`timeout`/`sleep` 被 reparent 到 PID 1 继续存活。即 `adapter_terminate` 的"grace 之后 `kill -TERM "${pid}"`"打不到 runner，runner 的 `trap 'exit 143' TERM`+`stop_server`（进程组 TERM→5s→KILL 收敛）不会执行；实际停止依赖 bootstrap `exit 143` 后容器被 Docker 回收。README 中该路径声称的"hard-stop path"因此并不成立（原生 abort 才是唯一真实生效的机制）。
- **影响**：取消/超时且原生 abort 未在 2s grace 内收敛时，Server/Bridge/runner 会在容器被销毁前继续运行（继续消耗模型额度、可能继续改工作区）；本容器内不会遗留 daemon（PID 1 退出即被运行时清理），故非资源泄漏级问题。注意仓库单测 `test_opencode_legacy_runner_*` 是**直接把 TERM 发给 runner**（`process.send_signal`），与生产拓扑不同，因此覆盖不到该差异。
- **建议**：在 `codify_harness_run` 里把子 shell 收成可 exec 的形状（例如 `adapter_run ... &` 改为 `exec` 化的单命令启动，或用 `setsid`/进程组地址化并让 `adapter_terminate` 对整组发 TERM），或让 `adapter_terminate` 收到 pid 后对 `-pid`/子进程树收敛。
- **验证**：需在容器内 bash 5.x 上复跑同一实验（`ps -o pid,pgid,command` 确认 `$!` 是否为 `timeout`），并补一条以生产拓扑（TERM→子 shell pid）驱动的 runner 测试；本次仅在本机 bash 3.2 验证，未在目标镜像验证。

### OCB-04 `ps -o pgid=` / `setsid` 依赖镜像 PATH，且测试用替身掩盖
- **等级**：INFO
- **位置**：`deploy/worker-entrypoint/harness/runners/opencode-run.sh:85`、`:125-133`、`:170`（提交 `2c3b95c7`）
- **证据**：Kit 运行时闭包（`deploy/worker-kit/default.nix`）包含 coreutils/curl/jq/python3 等，但**不含 util-linux（setsid）与 procps（ps）**；`CODIFY_RUNTIME_PATH` 默认回落到镜像 PATH（`deploy/entrypoint.worker.sh:77`），因此这两个二进制必须由项目运行时镜像提供。`setsid` 缺失时 runner 明确 fail-closed（`:125-128`）；但 `ps` 缺失或不支持 `-o pgid=` 时，`pgid` 取空 → `start_server` 判定"未成为进程组 leader" → 每次启动都失败，且报错信息会指向进程组而非缺工具。`backend/tests/unit/test_opencode_harness_adapter.py:3168-3227` 用替身 `setsid`/`ps`/`curl` 注入 PATH，故该依赖在单测中不可见。
- **影响**：镜像选择（slim/busybox）差异可能让 OpenCode Task 100% 无法启动，且错误信息误导。属需要实机确认的疑点，非已证缺陷（Debian/Ubuntu 系镜像自带 procps/util-linux，风险低）。
- **建议**：把 `setsid`/`ps` 一并纳入 Kit 闭包（或在 runner 里对 `ps` 缺失给出显式错误信息），并在 verify-runtime 阶段做一次 `ps -o pgid= -p $$` 探测。
- **验证**：在真实 worker 镜像内执行 `command -v setsid ps && ps -o pgid= -p $$`；本次未运行。

### OCB-05 XDG_DATA_HOME 落在 issue-shared 卷，同时承载 auth.json 与 Server 日志
- **等级**：INFO
- **位置**：`deploy/worker-entrypoint/harness/adapters/opencode.sh:99-122`（提交 `333dbc90`）
- **证据**：`xdg_data_home` 被改成 `/opt/codify-issue-shared/opencode-data`（为跨 Task 恢复会话，注释已说明），而 1.18.19 的凭据存储与日志都在 data 根下：制品内 `o5()/X7()` 计算 `$XDG_DATA_HOME/opencode/auth.json`、日志写入 `Path.log`（`$XDG_DATA_HOME/opencode/log/opencode.log`）。同文件注释声称 "config/cache/state remain ephemeral so provider credentials and user settings never cross task boundaries"——该保证对 data 目录并不成立（凭据文件与日志随 issue 卷跨 Task 留存）。当前 codify 路径用 `{env:OPENCODE_SNAPSHOT_KEY}` 插值、不触发 auth 登录写盘，因此未观察到实际凭据落盘；日志是否会写入端点/请求细节未验证。
- **影响**：潜在跨 Task 的凭据/诊断信息残留（同一 issue 内的后续 Task 与宿主卷可读）；今天没有可证实的泄漏路径，故记 INFO，凭据与日志卫生以 T13 结论为准。
- **建议**：把 `auth.json` 与 `log/` 显式指向 Task 目录（例如设 `HOME` 同卷的临时目录 + 打开时校验 `auth.json` 不存在/清空），或在文档中收敛注释措辞为"仅会话 DB 跨 Task 持久"。
- **验证**：真实 Task 内 `ls -l /opt/codify-issue-shared/opencode-data/opencode/` 确认是否生成 `auth.json`/`log/`；本次未运行。

### OCB-06 子代理（child session）事件被会话过滤丢弃，用量/诊断不完整
- **等级**：INFO
- **位置**：`deploy/worker-entrypoint/harness/adapters/opencode_bridge.py:205-216`、`:1182-1188`（提交 `333dbc90`）
- **证据**：`_belongs_to_task_session()` 只放行本 Task session 与 `server.connected`/`server.heartbeat`，其余（含子会话）一律 drop；注释明确这是有意为之（避免子会话影响 active-tool 跟踪与终态恢复）。1.18.19 的 `task` 工具确实在**子会话**中运行（制品内 `session create {parentID}` 与前端 "Go to first child session" 证实 session 有 `parentID`）。
- **影响**：使用子代理的 Task，子会话的 `message.part.*`/usage 事件不会进入 canonical 流，`usage_tokens`/`usage_cost` 与工具时间线会少算子代理部分（终态判定仍以父会话 `session.idle` 为准，正确）。这是刻意取舍，故只作观察记录；若产品要求用量准确，需要在桥接层按 parent/child 关系白名单放行（同时保留只以父会话判定终态）。
- **建议**：如确认用量必须完整，改为"父会话 + 其 child session 集合"过滤；否则在能力说明中标注子代理用量不计。
- **验证**：实机上跑一个使用 `task` 工具的 Task，比对 result 的 usage 与服务端消息用量；本次未运行。

## 3. 逐项核查记录（已确认无问题的关键不变量）

| # | 不变量 / 契约 | 结论 | 依据 |
|---|---|---|---|
| 1 | Server 启动参数与设计一致（显式 loopback 端口、`--hostname 127.0.0.1`、`--pure`） | 通过 | `opencode-run.sh:130-133`；制品内确认 `--pure` 为全局旗标（`.option("pure",{describe:"run without external plugins"})`，置 `OPENCODE_PURE=1`，`serve`/`debug skill` 均可用） |
| 2 | 端口交接无发现通道、无端口冲突兜底 | 通过（设计已接受探测窗口） | `opencode.sh:82-91`（bind 127.0.0.1:0 取端口后立即释放）、`:186`；设计 §1.1 明确接受探测↔绑定窗口，冲突由 readiness 超时收敛 |
| 3 | readiness 超时 30s 且不重试启动；401/200 都算就绪 | 通过 | `opencode-run.sh:198-217`（`OPENCODE_READINESS_TIMEOUT:-30`、接受 `200|401`、失败 `stop_server_force` + 打印 `server.log` + exit 1）；设计 §1.1 "readiness 失败不重试启动" |
| 4 | 鉴权：口令为 Task 私有随机值、仅经 env 传递、不进日志/raw archive | 通过 | `opencode.sh:191`（`secrets.token_urlsafe(32)`）、`:372-373`（只注入 runner 命令行环境）、`opencode_bridge.py:384-387`（Basic header 由 env 拼装）；审计记录不含认证头（`_write_http_audit` 字段白名单 `:410-450`） |
| 5 | 端口/口令不落盘、不写进 `opencode.json`（凭据用 `{env:…}` 引用） | 通过 | `opencode.sh:247-267`（`apiKey:"{env:OPENCODE_SNAPSHOT_KEY}"`）；probe 明确 `{env:VAR}` 才是正确插值语法 |
| 6 | 快照强制覆盖：项目/用户配置与外部 skills 全部隔离 | 通过 | `opencode.sh:119-136`（HOME/XDG_*/`OPENCODE_CONFIG_DIR` 全量隔离、`OPENCODE_DISABLE_PROJECT_CONFIG/MODELS_FETCH/EXTERNAL_SKILLS/CLAUDE_CODE_SKILLS`、`unset OPENCODE_CONFIG*`）；制品内确认这些 env 名真实存在，且 `DISABLE_PROJECT_CONFIG` 会跳过本地 config 与 AGENTS.md 的 globUp 发现 |
| 7 | 冻结 provider/model 写入 config；`models.<id>.provider` 为对象 | 通过 | `opencode.sh:256-266`；制品 `promptAsync`/`command` body 支持 `model/agent/variant`，与桥接 payload 一致（`opencode_bridge.py:540-580`） |
| 8 | Agent/Command/model variant 双层校验（fail-closed） | 通过 | worker 侧 `opencode.sh:138-172`（jq 白名单 + 正则）与桥接侧 `opencode_bridge.py:960-980` 完全镜像后端 `backend/app/core/harness_options.py:47-49,110-134`（同一 allowlist 与同一正则） |
| 9 | 先订阅 `/event` 再 prompt（防漏首事件） | 通过 | `opencode_bridge.py:1030-1052`（等 `server.connected` 才继续）、`:1150-1156` 之后才发 prompt；与设计 §3.1、probe wire（首帧即 `server.connected`）一致 |
| 10 | `session.idle`/`session.error` 作为终态信号；断流有兜底且不重复 prompt | 通过（兜底路由有缺陷，见 OCB-01） | `:1222`（`saw_terminal_signal`）、`:1248-1251`（两条恢复路径）；全程无重试/重发 prompt 代码路径，故不存在重试导致的重复 prompt |
| 11 | SSE 分帧：只对空行终止的完整事件放行，跨 chunk 切分不重复 | 通过 | `parse_sse` `:290-360` + `event_stream` `:609-700`（`read1(8192)` + `_sse_tail` 复用残余）；单测覆盖 `data:` 单行帧、`payload` 包装、durable `data`、CRLF、跨 chunk、真实 1.18.19 wire 抓包（`test_opencode_parse_sse_*`） |
| 12 | 读超时不会误杀长回合（心跳保活） | 通过 | 客户端默认 `timeout=30.0`（`:379`，SSE socket 读超时即 30s），而制品内全局 `/event` 每 10s 发 `server.heartbeat`、实验性订阅每 15s 发 `: heartbeat` 注释帧；10s 心跳足以在 30s 读超时前刷新（注释帧也不会被误解析为事件：`parse_sse` 对空 `event` 不 yield） |
| 13 | 传输异常分类：HTTPError→ConnectionError、IncompleteRead/URLError/Timeout→ConnectionError；无 Content-Type 时的降级 | 通过 | `event_stream` `:670-690`；200+非 SSE 响应体不产生任何记录 → `subscribed=False` → 显式失败（`:1058-1067`）；单测 `test_opencode_event_stream_classifies_incomplete_read_as_disconnect` |
| 14 | 原生 abort：`POST /session/{id}/abort`，200/202/204/404 均视为已收敛，重复 abort 安全 | 通过 | `_abort_session` `:705-735`（404 打印"session already closed"并返回 0）；适配器 terminate 先 abort 再 2s grace 轮询再 TERM（`opencode.sh:407-445`）；制品路由表含 `/session/{id}/abort`（返回 Boolean，probe 实测 200+true） |
| 15 | 进程组收敛：Server 独立 session/pgid，TERM 组→轮询→KILL，且绝不误伤 runner 自身进程组 | 通过 | `opencode-run.sh:120-178`（`setsid` + pgid==pid 校验后才发布 pid 文件）、`:78-105`（pgid≠pid 时拒绝组信号，仅 TERM leader）、注释已说明 5s grace 低于容器 10s 预算；单测 `test_opencode_legacy_runner_reaps_*`（含忽略 TERM 的子进程）通过 |
| 16 | Server 降权：Server（含其仓库工具）以 `codify` 运行，root 仍持有审计/事件写权限 | 通过 | `opencode-run.sh:137-146`（`codify-run-as -- setsid …`）；`opencode.sh:350-376`（raw/audit 文件 `chown 0:0` + 644）；单测 `test_opencode_legacy_runner_drops_server_to_worker_identity` |
| 17 | 会话恢复不新建会话、且校验返回 id 一致 | 通过 | `opencode_bridge.py:1000-1030`（`GET /session/{id}`，`status==200 && session_id==resume_session` 才继续）；v1 `GET /session/{id}` 返回裸 Info（含 `id`），解析兼容 `{info:{id}}`/`{id}`；单测 `test_opencode_run_attempt_resumes_existing_session_without_creating_one` 断言不调用 `create_session` |
| 18 | translator 子进程在所有退出路径被关闭并回收 | 通过 | setup 失败 `finally`（`:1032-1038`）+ 主流程 `finally`（`:1252-1253`）；`_close_translator` 容忍 BrokenPipe（`:737-750`） |
| 19 | 每 Task 一个 Server、Bridge 只连本 Task loopback | 通过 | `opencode_bridge.py:376-380`（host 硬编码 127.0.0.1，`base_url` 仅测试注入）、`:1000` 用 `OPENCODE_PORT`；`OPENCODE_*` 全部列入后端保留前缀，自定义环境无法注入（`backend/app/core/worker_environment_variables.py:92-104,109-113`） |
| 20 | command gate：确定性 reject，outcome 词表与 Pi 一致，不伪装 steering | 通过 | `opencode_bridge.py:279-288`（`negotiate_capabilities` 恒返回 steering/follow_up=false）、`:751-772`；reject code 词表与 `pi_bridge.py:157-174`、`control_client.py:49-82` 完全一致；设计 §5 冻结该行为 |
| 21 | HTTP 审计脱敏：无请求/响应正文、无 session id、无认证头，写入失败不影响控制结果 | 通过 | `:400-460`（route template、`config_sha256`、`flock`、异常吞掉）；单测 `test_opencode_client_audits_*` |
| 22 | HTTP 失败只投影有界 message + 数字 statusCode，不转发响应体 | 通过 | `_safe_http_failure_message`（`:218-235`，500 字符上限）、`_http_failure_record`（`:238-262`）；与 T05 的错误分类契约一致（`test_opencode_structured_session_error_uses_status_code_taxonomy`） |
| 23 | 与 probe 证据一致性（启动/鉴权/随机端口/异步 prompt/事件/abort） | 通过 | `docs/harness-probes/v2/opencode/README.md` 与 `events.wire.sse` 对照：`POST /session` 需 `model:{id,providerID}`（`:531-536` 一致）、`prompt_async` 返回 204 且被接受（`:1156-1162` 接受 200/202/204）、`session.idle` 为 settled 信号（`:1195`）、`abort` 200（`:705-735`）、`{env:VAR}` 插值（`:243-266`）；**唯一不一致项为 `GET /session/{id}/status`**（OCB-01） |

## 4. 局限与未验证项

- **无真实 OpenCode Server / 无 Docker**：所有涉及真实 HTTP、真实 `opencode serve` 进程、容器信号（`docker stop` → SIGTERM → PID 1 退出 → 运行时清理）的结论均为静态推理 + 冻结制品（`deploy/worker-cli/opencode/opencode`，1.18.19）内的路由表/旗标/env 名核对；未运行端到端。OCB-01 的路由事实来自该冻结制品，仍建议在 canary 上用真实 Server 复核一次 404 行为。
- **未在目标镜像验证 OCB-03**：本机只有 bash 3.2，实验确认了 `$!` 为子 shell 且 TERM 后 `timeout` 被孤儿化；容器内为 nixpkgs bash 5.x，行为需实机复跑（同一实验脚本即可）。
- **未运行验证的环境依赖**：`setsid`/`ps` 是否存在于项目运行时镜像（OCB-04）；`opencode debug skill --pure` 的 JSON 形状仅从制品确认为"含 `name`/`location`"（`materialize_skills` 的实际通过与否未验证）。
- **未覆盖的相邻专题**：`opencode_events.py` 的 settled/错误分类细节（T05）；manifest/registry/`model_protocols` 交集校验（T08）；Worker Kit 的 CLI 校验与 `--version` 口径（T09）；凭据与日志卫生（T13）；runner 公共信号的完整语义（T07）。
- **未验证的边界假设**：OpenCode 对"无凭据 Endpoint"的行为（OCB-02 的修复方向取决于此）；子代理场景下 usage 的完整口径（OCB-06）；`OPENCODE_READINESS_TIMEOUT`/`OPENCODE_SERVER_STOP_GRACE_SECONDS` 被传入非数字值时仅会 fail-closed（算术展开失败 → 未就绪/立即 KILL），由于这些 key 属保留前缀、自定义环境无法注入，未计入问题清单。
