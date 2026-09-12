# 13 横切安全与凭据 —— Code Review

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56`（`dev @ cbad9e56`，2026-09-12） |
| 主要文件（diff 行数） | `deploy/worker-entrypoint/harness/adapters/sanitize.py` (+19/-2)、`harness/adapters/{pi.sh:+306,opencode.sh:+452,pi_owner.py:+519,pi_bridge.py:+275,opencode_bridge.py:+1293}`、`harness/runners/{claude-run.sh:+896,opencode-run.sh:+240,pi-run.sh:+83,codex-run.sh:+82}`、`deploy/worker-entrypoint/{bootstrap.sh:+84,main.sh:+156/-178,repository-helpers.sh:+218/-85,verification.sh:+150/-34,artifacts.py:+1,entrypoint.worker.sh}`、`deploy/worker-kit/model-proxy/main.go` (+420 新增)、`deploy/worker-kit/{install.sh:+218/‑10,verify-cli-payloads.sh:+210,verify-kit-content.py}`、`deploy/offline-bundle/scripts/validate-kit-archive.py`、`deploy/docker-compose.yml` (+41/-1)、`deploy/.env.test` (+25/-19)、`deploy/.env.example` (+5/-1) |
| 交叉核查文件（后端信任边界） | `backend/app/api/{providers.py:+298,task_command_routes.py:+306,harness_catalog.py:+430 新增,containers.py:+47,task_runtime_summary_routes.py:+48,task_log_stream.py:+36,project_webhooks.py:+15}`、`backend/app/core/{worker.py:+14,worker_environment_variables.py:+48,worker_runtime.py:+318,worker_kit_inventory.py:+490,worker_profiles.py:+298,model_credentials.py,task_harness_commands.py:+508,worker_command_pump.py:+909,worker_event_projector.py:+452}`、`backend/app/dependencies/project_access.py`、`backend/app/scheduler_service.py`、`backend/app/main.py`（路由挂载） |
| 审查方法 | 静态阅读 HEAD 完整文件（非仅 diff）+ 只读 git 历史取证（`git show 8081c946^:<path>`）+ 调用方/消费者双向核对（API→依赖、容器脚本→后端解析、后端→容器 env）+ 1 组可执行正则对照实验（见下）+ 与 `docs/security/credential-delivery-risk-acceptance.md`、`docs/architecture/open-harness-v2.md` §3 威胁模型对照 |
| 实际运行的实验 | ① 用**真实** `deploy/worker-entrypoint/harness/adapters/sanitize.py`（`importlib` 直接加载）+ 逐条复刻的 `backend/app/core/worker.py:scrub_sensitive_data` 正则，对 11 组样本（含本项目历史上真实使用过的 Provider key 形态）比对清洗结果（`python3 -B`，未修改仓库）。② `git show 8081c946^:deploy/.env.test` 读取历史明文。**未运行**任何 pytest / docker / compose / 真实 CLI |
| 未覆盖 | OpenCode/Pi/Codex adapter 的功能性正确性（T03/T04/T05/T06）、命令平面与事件投影的不变量（T01/T02）、Runtime Bundle/readiness 功能审查（T08）、Kit 校验链细节（T09）、Model Endpoint/Go 代理功能（T10）、部署编排与 preflight（T15）、前端功能（T12）、迁移（T14）。本专题只回答“这些改动的安全影响” |

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 1 |
| FIX_IF_CHEAP | 4 |
| DEFER | 0 |
| ACCEPT/CLOSE | 4 |

V2 的信任边界整体收紧且可验证：凭据解析对 `revoked` 一律 fail-closed、provider 快照带 fingerprint 篡改检测、Runtime Bundle 与 Kit inventory 逐文件/逐字节复验不符即 fail closed、4 个新增 API 端点全部有鉴权，新增代码无 `eval`/`pickle`/`shell=True` 与路径穿越。唯一 FIX_NOW 是 SEC-02：真实凭据仍留在 git 历史且未吊销，轮换是纯运维、0 代码。另 4 条 FIX_IF_CHEAP 是错误路径或 1 行配置缺陷，4 条 ACCEPT/CLOSE 按离线内网、3 人内测、避免过度防御的画像书面接受。

**本专题触发条件**：
- 出现非管理员/外部用户、需要多团队隔离，或启用 OIDC、加入外部协作者 → 重开 SEC-04 / SEC-09。
- 同容器运行不可信代码或多租户共容器 → 重开 SEC-INFO-01。
- 接入 Broker/短期 token，或转向公网/外部仓库 Profile → 重开 SEC-INFO-02。

## 2. 问题清单

### SEC-02 git 历史仍含真实凭据（HEAD 已清理但未吊销，仍可完整检出）
- **判定**：FIX_NOW —— 本 patch 只清 HEAD，吊销是纯运维、0 代码
- **位置**：`deploy/.env.test:6-7`（提交 `cbad9e56`，本 patch 将真实值替换为 `replace-via-secret-store`）；原始明文见 `git show 8081c946^:deploy/.env.test:3,9,32`
- **证据**：
  ```
  8081c946^:deploy/.env.test
    GITLAB_BOT_TOKEN=glpat-<REDACTED，形态为 `glpat-` + 20 位 + `.01.` + 9 位>
    ANTHROPIC_API_KEY=<REDACTED，形态为 32 位 hex + "." + 16 位 base62>
    CONFIG_ENCRYPTION_KEY=dev-oidc-config-key
  ```
  这三行在 `git log -p -- deploy/.env.test` / `git show` 中永久可检索（本次以只读命令直接读出）。`deploy/docker-compose.yml` 以 `env_file: .env.test` 引用该文件（`:29-30` backend、`:82-83` scheduler、`:146-147` 第三个服务），说明它们曾是真实部署输入而非随机示例。
- **影响**：任何拥有仓库读权限（含 CI、镜像构建上下文、历史 clone）者可取得：① GitLab bot PAT（按 `docs/architecture/open-harness-v2.md` 的部署模型，该 token 对所有受管项目有写权限）；② 一个可用的模型 Provider key；③ 若 `dev-oidc-config-key` 曾是部署实际密钥，则可解密 `system_config`/`ai_providers`/`project_webhook_config`/`model_credentials` 中全部密文（连带泄露 webhook 密钥与其它 Provider key）。从 HEAD 删除**不等于**吊销。
- **最小动作**：吊销/轮换三类凭据；`CONFIG_ENCRYPTION_KEY` 换新后按需重新录入受影响密文（provider key / webhook secret）。建议过重：`git filter-repo` 清理历史 + 通知所有 clone/CI 重拉没必要（凭据死了即可）
- **验证**：不可在代码层验证；本次已用 `git show` 取证确认。吊销结果需在 GitLab 与部署侧人工确认。

### SEC-01 清洗模式覆盖不全：自定义 Provider 密钥形态与 JSON `apiKey` 字段不被脱敏
- **判定**：FIX_IF_CHEAP —— 补几条正则即修好，无新机制
- **位置**：`deploy/worker-entrypoint/harness/adapters/sanitize.py:92-108`（本 patch 新增的 `sanitize_json_value`；相关模式表 `:25-29`、`:36-38` 未被本 patch 修改）；对照 `backend/app/core/worker.py:118-122`（本 patch 新增 OpenRouter 形态）
- **证据**：以真实 `sanitize.py` + 复刻的 `scrub_sensitive_data` 正则实测（样本为**本项目历史上真实使用过**的 Provider key：`8081c946^:deploy/.env.test` 的 `ANTHROPIC_API_KEY=<REDACTED，形态为 32 位 hex + "." + 16 位 base62>`，智谱/OpenAI 兼容形态；`GITLAB_BOT_TOKEN=glpat-<REDACTED，形态为 `glpat-` + 20 位 + `.01.` + 9 位>`）：

  | 样本 | worker-side `sanitize` | backend `scrub_sensitive_data` |
  |---|---|---|
  | `{"provider":{"codify":{"options":{"apiKey":"<key>"}}}}` | 原样保留 | 原样保留 |
  | `{"api_key":"<key>"}` | 原样保留 | 原样保留 |
  | `apiKey: <key>` | 原样保留 | `apiKey: [REDACTED]` |
  | `export ANTHROPIC_API_KEY=<key>` | `<REDACTED>` | 原样保留 |
  | `<key>`（裸值/URL query） | 原样保留 | 原样保留 |
  | `ghp_…` / `AIza…` / `hf_…` / `xoxb-…` | 原样保留 | 全部脱敏 |
  | `glpat-…<REDACTED 尾部>` | `<GITLAB_TOKEN>.01.<9 位尾串>`（**尾部泄漏**） | 同左 |

  失败原因：`sanitize.py:36-38` 的赋值规则是大小写敏感且要求名字后直接跟 `[:=]`，因此 JSON 形态 `"apiKey": "…"` 不匹配；两种清洗器都只按**值前缀**识别（`sk-*`/`glpat-*`/`AIza`…），自定义形态密钥（本项目实际使用 `<32hex>.<16base62>`）完全不被覆盖；`glpat-*` 正则遇 `.` 即停，GitLab 新格式 PAT 的 `.01.xxxx` 后缀逃逸。V2 恰好在把这类形态推到前台：新增的 pi adapter 把**原始 key 明文**写进容器内配置文件（`pi.sh:191-195` 的 `apiKey:$api_key` → `~/.pi/agent/models.json`），opencode adapter 写 `opencode.json` 的 `apiKey`（`opencode.sh:246-250`），而该原始流经 `sanitize.py` 后原样落到 `harness-events/<key>.jsonl`（`claude_events.py:396`、`pi_events.py:1143`、`opencode_events.py:1689`）。
- **影响**：`harness-events/` 全量进入任务 Runtime Archive（`bootstrap.sh:207-220` 收集 `harness-events`，`artifacts.py:575-586`），该归档由 `/api/tasks/{task_id}/archive/download` 下发给**任何有该项目查看权**的用户（`tasks.py:987-1000`，`require_operator=False`）。触发条件：任何自定义形态（非 `sk-*`）的 Provider 凭据进入原始 CLI 流即可 —— 最常见路径是模型读取自身配置文件（如 `~/.pi/agent/models.json`、`~/.pi/agent/` 下的调试输出）或 CLI 打印配置/错误时带出 `"apiKey": "…"`。此时该凭据对项目成员可见，而 canonical 事件流与 UI（走 backend scrubber + `command_projection_fields`）在多数路径上仍是脱敏的，造成“日志里看不到、归档里能看到”的不对称。
- **最小动作**：补「名字型规则容忍 JSON 引号/空格」+ `glpat` 尾部 / `ghp_` / `AIza` / `hf_` / `xox[baprs]-`；不做「通用密钥识别」（做不到就直说）
- **验证**：本次已用真实模块实测（上表）。修复后应在 `backend/tests/unit/test_harness_events_v2.py` 的 sanitize 相关用例与 `backend/tests/unit/test_scrubbing.py` 旁补一组“JSON `apiKey` + 自定义形态值”的 fixture 做回归。**本次未运行 pytest**（不做全量；单文件回归留给修复方）。

### SEC-03 调度器 `/health` 端口默认发布到所有宿主接口
- **判定**：FIX_IF_CHEAP —— 1 行零成本；严格说属过度防御
- **位置**：`deploy/docker-compose.yml:106-107`（提交 `cbad9e56`），配合 `backend/app/scheduler_service.py:50-60`
- **证据**：本 patch 新增 `ports: - "${SCHEDULER_HEALTH_PORT:-8001}:8001"`，容器内 uvicorn 为 `host="0.0.0.0"`（`scheduler_service.py:59`）；`/health` 无任何鉴权，返回 `{"status":"running","harness_execution_mode":…}`（`scheduler_service.py:50-55`）。消费方 `deploy/scripts/preflight-execution-mode.sh:18` 默认只请求 `http://localhost:8001/health`，即该映射无需绑定到宿主全部网卡。
- **影响**：与宿主同网段的任意主机可探测调度器存活并读取 `harness_execution_mode`；不含凭据，属新增的低价值信息暴露面（同一 compose 中 backend 8000 亦为 0.0.0.0，故与既有约定一致，仅是新增端口）。
- **最小动作**：端口映射改成 `"127.0.0.1:${SCHEDULER_HEALTH_PORT:-8001}:8001"`（1 行）
- **验证**：未运行 `docker compose`（无 daemon）；静态确认端口映射与监听地址、以及 preflight 只访问 localhost。

### SEC-05 webhook 密钥轮换：DB 与 GitLab 可能永久漂移且无检测手段
- **判定**：FIX_IF_CHEAP —— ~5 行可修；加轮换状态字段属过度设计
- **位置**：`backend/app/api/project_webhooks.py:175-200`（本 patch 新增 `except ConfigEncryptionError` 分支）
- **证据**：新分支的调用顺序是**先**生成并写入 DB（`save_project_webhook_secret(db, project_id, managed_secret)`，`:188-189`），**后**调用 `ensure_project_webhook` 对 GitLab 侧执行 `PUT /projects/:id/hooks/:hook_id`（`gitlab_client.py:602-612`）。若该 PUT 因网络/权限失败（端点直接 400 返回，`:197-201`），DB 已是新 secret 而 GitLab 仍是旧 token；GitLab API 不回读 token，`GET /config/gitlab/projects/{id}/webhook` 只比对 hook URL 并报告 `managed_secret_configured=True`（`:239-258`、`project_webhook_config.py:19-21`），因此该漂移对 operator 不可见。
- **影响**：轮换后所有入站 webhook 因 token 不匹配返回 401（`webhook_handler.py:151-155`），CI 自动修复静默失效，而状态页显示“已配置”。**不是认证绕过**：接收侧对缺失/不匹配 secret 一律 401（fail closed），本次已静态确认 `get_project_webhook_secret` 抛 `ConfigEncryptionError` 时异常直接上抛为 500，也不会降级为“接受未签名请求”。
- **最小动作**：先 PUT 成功再落库（失败即回滚刚写的 secret 并返回明确错误），~5 行
- **验证**：需真实 GitLab 或 mock，本次未运行；漂移路径由上述调用顺序静态确认。

### SEC-INFO-03 默认数据库口令 + 5432 端口发布（`[V1 遗留]`）
- **判定**：FIX_IF_CHEAP —— `[V1 遗留]`，本 patch 未放大
- **位置**：`deploy/docker-compose.yml:165-172`；同值出现在 `deploy/.env.test:15`
- **证据**：`POSTGRES_PASSWORD: codify_password` 且 `ports: - "5432:5432"`；`8081c946^:deploy/docker-compose.yml:121-134` 与之逐行相同 → V1 遗留，本 patch 未改动、未放大（本 patch 只新增了 scheduler/migrate 相关段落）。
- **影响**：宿主可达 5432 的任意主机可用已知口令直连数据库，读取全部任务数据与密文；生产部署由 operator 覆盖 `POSTGRES_*` 时才无此问题。
- **最小动作**：`"127.0.0.1:5432:5432"`（1 行，保留宿主 psql）。改口令是可选运维：`ALTER USER` + 同步 3 处 `DATABASE_URL`；建议过重：`${POSTGRES_PASSWORD:?…}` 会让栈在未设变量时直接起不来，对 3 人内网不值
- **验证**：静态 diff 对照 base 提交确认。

### SEC-04 `GET /api/harness-catalog` 仅校验登录态，`worker_profile_id` 无范围约束
- **判定**：ACCEPT/CLOSE —— 无权限模型、信息零增量；改 `require_admin_user` 会打断建任务
- **何时再管**：出现非管理员/外部用户或需要多团队隔离
- **位置**：`backend/app/api/harness_catalog.py:369-395`（新增文件，提交 `cbad9e56`）
- **证据**：该路由只有 router 级依赖 `require_authenticated_user`（`main.py:402-407`），函数签名里没有 `access_scope`（对比同文件任务级端点 `:401-414` 使用 `get_task_with_access_check` + `require_project_access_scope`）；`_load_catalog_profile`（`:300-320`）对不存在的 `worker_profile_id` 抛 404，对存在的返回该 profile 的 `enabled_harnesses`/`enabled`/`availability`/`availability_reason`。项目内的 `GET /worker-profiles` 同样只需登录（`worker_profiles.py:367-371`），但 `/worker-profiles/admin` 才含 Docker 目标与路径等敏感字段（`:374-389`）。
- **影响**：任意已登录用户（即使不属于任何项目、无 admin 角色）可通过递增 id 枚举 worker profile 的存在性（200 vs 404）并读取每个 profile 的 Harness 启用状态与 Kit 可用性；`options_schema`/`control_transport` 等同为公开投影，未泄漏宿主路径或启动命令（`harness_registry.py:463-500` 的投影确实剔除了 `source.*` 与路径），因此危害仅限于配置面信息与 ID 枚举。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态审查；本次未运行 API（无 DB）。

### SEC-09 `OIDC_ENABLED=false`（默认）下所有已登录用户对所有项目不受限，V2 命令平面使其升级为写权限
- **判定**：ACCEPT/CLOSE —— 加显式开关 + 多用户拒绝写属新机制（`[V1 遗留，V2 放大]`）
- **何时再管**：用户跨团队、加入外部协作者、或启用 OIDC 时
- **位置**：`backend/app/dependencies/project_access.py:95-96`（未随本 patch 改动），被 V2 新端点复用：`backend/app/api/task_command_routes.py:230-250`
- **证据**：`require_project_access_scope` 在 `not settings.oidc_enabled`（默认值，`config.py:153`；本 patch 的 `deploy/.env.test`/`docker-compose.yml` 均未设置 OIDC 变量）时直接返回 `is_unrestricted=True`，`allows()` 对任意 `project_id` 恒真（`:62`）。V2 在此之上新增：`PUT /tasks/{task_id}/commands/{command_id}`（对**任意** RUNNING 任务注入 steer/follow_up，`task_command_routes.py:230-300`）、`/tasks/{id}/model-service-summary`、`/worker-runtime-summary`、`/tasks/{id}/archive/download`（原始 harness 流归档，`tasks.py:987-1000`）。
- **影响**：在使用本地认证（`/auth/local/register` 仅首启引导，`auth.py:355-370`；此后由管理员建本地用户）且未开启 OIDC 的多用户部署中，任一已登录用户可读取全部项目的任务、容器与原始日志、下载任意任务归档，并可向任意正在运行的任务注入指令（写操作）。这是 `project_access.py` 的既定设计（缺少 OIDC 项目来源时无法做项目级裁剪），本 patch 未改变它，但把“跨项目可读”放大为“跨项目可写”。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态确认分支与默认值；多用户本地认证部署未复现（无 DB）。

### SEC-INFO-01 OpenCode Server 口令出现在 curl argv（容器内可见）
- **判定**：ACCEPT/CLOSE
- **何时再管**：同容器运行不可信代码或多租户共容器
- **位置**：`deploy/worker-entrypoint/harness/runners/opencode-run.sh:201-203`（本 patch 新增）
- **证据**：就绪探测使用 `curl … -u "opencode:${OPENCODE_SERVER_PASSWORD}"`，口令在 argv 中；该口令是任务级随机值（`opencode.sh:189-192`），Server 只监听 `127.0.0.1`（`opencode-run.sh:131-133`），Server 的常规请求走 Basic 头（`opencode_bridge.py:384-387`）。
- **影响**：同一 PID 命名空间内的其它进程（含以同一 `codify` 身份运行的模型/CLI）可通过 `/proc/<pid>/cmdline` 读到该任务口令，从而控制本任务的 OpenCode Server。由于 Server 已在同一容器、同一身份下运行，且威胁模型已排除容器内恶意代码，实际提升有限；不影响其它任务或宿主。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态确认 argv 位置与监听地址；未在容器内实测 `ps`。

### SEC-INFO-02 以模型工作负载身份可见的长期 GitLab bot PAT（文档化的受限风险接受）
- **判定**：ACCEPT/CLOSE
- **何时再管**：接入 Broker/短期 token、公网或外部仓库 Profile
- **位置**：`backend/app/core/worker_runtime.py:424`（`"GITLAB_TOKEN": settings.gitlab_bot_token`）
- **证据**：该变量进入容器 env，而 harness 以 `CODIFY_RUN_UID`(默认 1000)/`codify` 身份运行（`entrypoint.worker.sh:87-108`）并继承容器环境，因此模型进程可读取该 PAT。容器内**实际消费者只有 root 侧的 bootstrap**（`bootstrap.sh:7,402,438`）与未被 V2 入口 source 的遗留 `gitlab.sh:17`；git 交付改用隔离的 `/root/.git-credentials`（`repository-helpers.sh:108-136`）。`docs/security/credential-delivery-risk-acceptance.md` §1/§3 明确接受“长期 key 以 env 进入 worker”这一 legacy 模式，并把“外部 GitLab/OAuth 最小权限、账户控制、轮换与撤销”列为尚未签署项。
- **影响**：模型进程持有可写全部受管项目的长期 PAT。属**已被文档声明接受**的既有边界（V1 行为，V2 未改变，也未放大），本次仅作为审计事实记录，不构成 V2 回归。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态确认注入位置与身份继承；未在运行容器内读取 env。

## 3. 逐项核查记录

### 3.1 仓库内密钥扫描结论

| 扫描对象 | 命令 | 结论 |
|---|---|---|
| 全工作区（HEAD） | `grep -rInE '(glpat-[A-Za-z0-9_-]{20,}\|sk-ant-…\|sk-proj-…\|sk-or-v1-…\|ghp_…\|hf_…\|xox[baprs]-…\|AIza…)' --exclude-dir={node_modules,.git,dist,.venv} .` | **未发现真实凭据**。命中仅 3 类：`deploy/.env.example` 的占位符（`glpat-xxxx`/`sk-ant-xxxx`/`change-me-*`）、`backend/tests/**` 的合成 token（`glpat-abcdefghij…`、`sk-or-v1-abcdef…`、`xoxb-test-token`）、测试断言文本 |
| `deploy/.env.test` | `cat deploy/.env.test` | 全部为 `replace-via-secret-store` / `codify_password` / 内网 IP `192.168.50.129`；已由本 patch 清理（原值的残留风险见 SEC-02） |
| `backend/tests/fixtures/harness_events*`、`docs/harness-probes/v2/*` | 同上 + 私有 URL/IP 扫描 `(https?://…\|x.x.x.x\|/Users/…\|/home/…)` | 干净：UUID/tool_id 已替换为稳定占位符（`<UUID:…>`/`<TOOL_ID:…>`、`<REDACTED_SIGNATURE>`），URL 仅为 `api.deepseek.com`、`github.com/*/releases`、`127.0.0.1:PORT` 之类公开/占位值；无内网地址、无宿主用户名 |
| `deploy/worker-cli/**`（本地 staging） | `git ls-files deploy/worker-cli \| wc -l` → 0 | **未入库**（gitignored），CLI 二进制不在仓库中 |
| `output/`、`.vite` 等产物 | `git ls-files` | 未入库；`output/playwright/*.png` 为验收产物，无凭据 |
| 构建产物 `.pyc` | `git ls-files \| grep -E '\.pyc$\|__pycache__'` → 空 | 未入库（工作区存在若干未跟踪 `__pycache__`，属本地/并行审阅运行残留） |

**git 历史（超出工作区扫描范围）**：`deploy/.env.test` 的历史版本含真实凭据 → 见 SEC-02。建议把历史扫描（`gitleaks`/`git filter-repo --analyze`）纳入 CI，并把 `scripts/harness-probes/v2/secret-scan.py` 的规则从 4 条扩到覆盖 GitLab 新格式 PAT 后缀、`CONFIG_ENCRYPTION_KEY` 与自定义 Provider key 形态（本次实测该脚本规则对上述三类均无命中）。

### 3.2 关键不变量/契约核查

| # | 不变量/契约 | 结论 | 依据 |
|---|---|---|---|
| 1 | 密钥不进 argv/进程列表/inspect | 基本通过 | 容器 env 注入（`worker_runtime.py:424,470-500`）是文档化通道；`docker inspect` 未对 API 暴露（`containers.py:394` 只取 `Created`）；唯一 argv 例外见 SEC-INFO-01；`pi.sh:191-195` 落盘 `models.json` 为 0600 且目录在容器内（非宿主挂载） |
| 2 | 新端点鉴权与项目隔离 | 通过（范围过宽见 SEC-04；OIDC 关闭时不受限见 SEC-09） | `main.py:383-407` 全部新增 router 挂 `require_authenticated_user`；`task_command_routes.py:230-300` 三个方法先 `get_task_with_access_check` 再操作；`task_runtime_summary_routes.py:56-70` 先 `require_project_access`；`containers.py:401-430,500-520` 逐项目过滤/校验；provider 写接口 `require_admin_user`（`providers.py:399-470,470-560`） |
| 3 | IDOR（直接用 task_id/attempt_id/command_id） | 通过 | 所有 command 查询都带 `task_id`（`task_harness_commands.py:498-508`、`_load_command` `task_command_routes.py:113-124`）；幂等 digest 含 `task_id`+`attempt_id`（`harness_protocol.py:693-703`），跨任务同 ID 只会得到 409 而不回显内容；日志/归档/payload 端点全部 `get_task_with_access_check`（`tasks.py:975-1022`） |
| 4 | SSRF（Provider 连接测试、出口代理） | 通过（受 admin 边界约束） | `providers.py:436-470` 需 admin，`follow_redirects=False`，错误信息经 `_provider_connection_error_detail` 重写；任务级代理只从冻结 base_url 出网（`runner.sh:258-320`）且仅 `--listen 127.0.0.1:0`；`provider_options` 只合并请求体且保留字段被白名单剔除（`provider_request_options.py:22-40`，Go 侧同表 `model-proxy/main.go:60-70`） |
| 5 | 命令注入/RCE（用户文本进 shell/git） | 通过 | 新增代码无 `eval`/`sh -c` 拼接用户文本；`codify_run_shell` 的插值点均取已校验值：分支名服务端生成 `codify/issue-{id}`（`issues.py:420`）、commit sha 先过 `^[0-9a-f]{40}$`（`repository-helpers.sh:96-100`）、helper 参数走数组+`python3 '…'`（`repository-helpers.sh:123-135`）；harness options 有 allowlist（`harness_options.py:83-140`，adapter 侧二次 jq 校验 `opencode.sh:158-168`、`codex.sh:124-137`）；控制帧经文件/stdin 传入而非 argv（`worker_command_pump.py:356-400`） |
| 6 | 任意文件读写 / 路径穿越 | 通过 | `artifacts.py:330-460` 用 `O_NOFOLLOW`+fd 相对操作+`..` 拒绝+跨挂载点拒绝；`kit_relative_path` 显式拒绝任一 `..` 分量（`worker_kit_inventory.py:255-285`）；`validate-kit-archive.py:21-120` 解析符号/硬链接链并拒绝逃逸；归档文件名由整型 `task_id` 生成（`task_event_archive.py:30-31`）；后端无 `extractall`（只 `extractfile` 单成员读取） |
| 7 | 反序列化/解析不安全用法 | 通过 | 新增 Python/Go 代码中无 `yaml.load`/`pickle`/`marshal`/`eval`/`exec`/`shell=True`；JSON 一律 `json.loads` 并做类型/范围校验（`worker_runtime.py:88-160`、`harness_catalog.py:262-292`），`_read_trusted_root_json` 额外校验属主/权限/size（`artifacts.py:130-150`） |
| 8 | 制品校验绕过（CLI 二进制完整性） | 通过 | 安装态 `content_inventory` 与挂载字节**逐条比对**（`worker_runtime_readiness.py:1024-1040`），present CLI 另做 mode/size/sha 复验且不符即 `READINESS_UNAVAILABLE`（`:1060-1085`）；安装器把 path 后缀/版本/平台/manifest+inventory 摘要绑到 receipt（`worker_kit_inventory.py:345-420`）；Runtime Bundle 在容器内按 manifest 逐文件复验 size/sha 且拒符号链接（`entrypoint.worker.sh:18-70`），未通过即拒绝启动（`entrypoint.worker.sh:73-80`） |
| 9 | 凭据解析 fail-closed（revoked/缺失） | 通过 | `model_credentials.py:106-125`：`revoked` 恒拒、`retired` 仅 `allow_retired=True`（仅重试路径）；`worker_runtime.py:311-325` 解析失败即 `RuntimeError` 阻断执行；`providers.py:479-486` 连接测试遇非 active 凭据直接 400 |
| 10 | Provider 快照/协议不可被后续编辑改变 | 通过 | 端点快照校验 fingerprint（`worker_runtime.py:140-160`）；执行前再做 snapshot/Bundle 版本+摘要+harness+协议一致性（`harness_execution_policy.py:120-200`）；`CODIFY_MODEL_PROTOCOL` 由冻结快照注入而非猜环境（`worker_runtime.py:404-412`） |
| 11 | 自定义 env 不能覆盖冻结运行时/凭据命名空间 | 通过 | `worker_environment_variables.py:20-84`：保留键集 + `_FROZEN_RUNTIME_ENVIRONMENT_PREFIXES` 命名空间级拒绝（`ANTHROPIC_/CLAUDE_/CODEX_/CODIFY_/OPENAI_/OPENCODE_/PI_`），写入路径 `replace_worker_environment_variables` 逐个校验；密钥值静态加密（`config_crypto`）且 API 不回传 secret 值（`serialize_worker_environment_variable_for_api`） |
| 12 | webhook 接收 fail-closed | 通过 | `webhook_handler.py:151-169`：无 secret 或不匹配一律 401 + 审计日志；不可解密时异常上抛 500（不降级接受）；漂移风险见 SEC-05 |
| 13 | 日志/事件清洗覆盖 | **部分不通过** | 产品可见文本经 `WorkerEventProjector` 统一走 `sanitize_sensitive_data`（`worker_event_projector.py:118,221,273,347,374,439,700-720`），命令文本经 `command_projection_fields`/`sanitized_command_text` 清洗；缺口见 SEC-01（原始归档通道）与 3.1（历史凭据） |
| 14 | 容器边界：挂载与监听地址 | 通过 | worker 容器仅挂载任务工作区/`.claude`/shared/meta（`worker_runtime.py:770-800`），**不含 docker.sock**（仅 backend/scheduler 挂，`docker-compose.yml:59,122`，属 V1 既有）；Pi 控制 socket `0600`（`pi_owner.py:414`）；OpenCode Server 与 model-proxy 均 loopback（`opencode-run.sh:131-133`、`runner.sh:280`） |
| 15 | 默认值不危险 | 基本通过（2 处例外 = SEC-03/SEC-INFO-03） | `harness_execution_mode` 只接受 `v2_only`（`config.py:215-222`）、`auto_migrate` 默认 false（`:150`）、未配置 OIDC 时无 session 即 401（`session.py:84-120`，无“关闭鉴权自动放行”分支）；`scheduler_health_port` 默认 8001 且 compose 发布到 0.0.0.0（SEC-03）；项目作用域在 OIDC 关闭时不受限（SEC-09） |
| 16 | 威胁模型外事项的归位 | 已归位 | 容器内模型可读自身 env/argv/凭据（SEC-INFO-01/SEC-INFO-02）、恶意仓库与恶意插件路径均属 `docs/architecture/open-harness-v2.md` §3 明确排除项，故未作为缺陷上报，而是按本画像书面接受（即 SEC-INFO-01/SEC-INFO-02 的 ACCEPT/CLOSE）；相关既有设计（长期 key 进容器 env、`/root/.git-credentials`）与 `docs/security/credential-delivery-risk-acceptance.md` §1/§3 一致 |

## 4. 局限与未验证项

- **无运行时验证**：本机无 Docker daemon / DB / 真实 GitLab 与 Provider，SEC-03/04/05/09 与 SEC-INFO-01/02/03 均为静态推理（SEC-01 有真实模块实验、SEC-02 有只读 git 取证，见 §3.1）；涉及端口发布、webhook 漂移、argv 可见性的结论未做端到端复现。
- **凭据是否仍有效未验证**：SEC-02 只能证明“历史中存在真实形态的凭据”，无法证明其当前是否仍被上游接受（不可、也不应对第三方发起探测）。
- **SEC-01 的触发依赖“凭据出现在原始 CLI 流”**：已给出代码级可行路径（`pi.sh:191-195` 明文落盘 + 模型读取自身配置）与实际正则对照证据，但未在真实 CLI 上复现“模型把 key 打印进原始流”的一刻；若评审方认为该前提过强，可将其移出 FIX_IF_CHEAP 改归 DEFER，脱敏缺口本身与修复方向不变。
- **清洗规则为“模式匹配”而非结构化**：自定义 Provider（V2 明确支持任意 `base_url`/key）在裸值与 JSON `apiKey` 形态下无法靠值前缀识别，本次只给出名字型规则的补强方向，未设计可覆盖任意密钥的通用方案（可能需在 adapter 侧对已知敏感字段名做结构化剔除）。
- **未审查**：其它专题的功能性结论（T01–T16）不重复；前端仅用 `git diff | grep` 检查了 `v-html`/`innerHTML`/`eval`/`new Function`（均无命中），未做完整 XSS/CSRF 审计；未评估 TLS/证书校验策略（`CUSTOM_CA_BUNDLE`、`http.sslVerify` 回退为 false 的既有行为）与 OIDC/会话实现（V1 范围）。
- **并行审阅影响**：工作区存在其它审阅者运行产生的未跟踪 `__pycache__` 与 `output/` 产物；本次实验以 `python3 -B` 运行以避免新增字节码，未删除他人文件。
