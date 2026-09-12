# 17 横切补充与范围外核查 —— Code Review

> 审查日期：2026-09-12 · 审查目标：`dev @ cbad9e56`
> 本专题覆盖其它 16 个专题未明确归属的改动：进程入口（`main.py`）、全局配置（`config.py`）、
> 探针/回归脚本（`scripts/**`）、仓库卫生、文档与代码漂移，以及 Main 在汇总阶段的独立复核结论。

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56` |
| 文件 | `backend/app/main.py`（+165/-1）、`backend/app/config.py`（+46/-7）、`scripts/dev-regression.sh`（+3/-3）、`scripts/harness-probes/run-probe.sh`、`scripts/harness-probes/sanitize_fixture.py`、`scripts/harness-probes/v2/*`（13 文件 +648）、`output/playwright/*.png`、`.vite/vitest/results.json`、`CLAUDE.md`（+? 单行更新） |
| 审查方法 | 静态阅读 HEAD 完整文件 + 迁移/调用方交叉核对 + 实际 grep/脚本运行 |
| 未覆盖 | `deploy/**`（专题 15）、`backend/alembic/**`（专题 14）、`frontend/**`（专题 12）、探针脚本中 `summarize-run.py`/`provider-matrix.py` 的逐行逻辑（仅抽读） |

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 0 |
| FIX_IF_CHEAP | 4 |
| DEFER | 0 |
| ACCEPT/CLOSE | 3 |

入口与配置层的 V2 改动方向正确且防呆：显式 `HARNESS_EXECUTION_MODE` 启动门禁、命令入口 32 KiB 预检、未知持久化配置键安全忽略，核查未见密钥泄露或静默降级。本轮 **FIX_NOW 为 0**，4 项 **FIX_IF_CHEAP**（XC-01~XC-04）均为「顺手能修就修」量级，无 DEFER。7 项按「无 CI、3 人内网 beta、无可用性要求」画像处置：3 项 ACCEPT/CLOSE 书面关闭（探针/秘密扫描无自动入口、入口依赖 Starlette 私有属性与 API 模型）。

## 2. 问题清单

### XC-01 旧 `task_timeout` 迁移后可能超出新字段边界，导致 `get_effective_settings()` 抛错
- **判定**：FIX_IF_CHEAP —— 触发需绕过 API 的直改库历史行，未证实存在
- **位置**：`backend/alembic/versions/079_task_execution_timeout.py:30-52`、`backend/app/config.py:275-277`、`backend/app/config.py:401-406`
- **证据**：迁移把 `system_config.task_timeout` 的 `value` 原样复制到 `task_timeout_peak_seconds` /
  `task_timeout_off_peak_seconds`，不做范围校验或钳制：
  ```python
  for key in ("task_timeout_peak_seconds", "task_timeout_off_peak_seconds"):
      ...
      "INSERT INTO system_config (key, value, value_type, updated_at) VALUES (...)", {..., "value": legacy["value"], ...}
  ```
  而 V2 新增字段带边界：`task_timeout_peak_seconds: int = Field(default=1800, ge=60, le=28800)`；
  运行时合并是**无保护**的 pydantic 构造：
  ```python
  def get_effective_settings() -> Settings:
      settings = get_settings()
      settings_data = settings.model_dump()
      settings_data.update(_runtime_config)
      return Settings(**settings_data)   # 越界 override -> pydantic ValidationError
  ```
  触发面已被 V1 写入侧校验限制：`8081c946^:backend/app/api/config_runtime.py:243-248` 要求
  `60 <= task_timeout <= 7200`，落在 V2 新边界内。因此只有在该校验引入之前写入的历史行（无法在仓库内确认
  是否存在）才可能越界；T14 在真实 PostgreSQL 上验证了正常值的搬运链路（单头 079，非空 `system_config` 按预期搬运）。
- **影响**：若存在越界历史行，执行 079 后所有走 `get_effective_settings()` 的 API 请求会因 `ValidationError`
  返回 500，且启动不报错、首次请求才暴露。
- **最小动作**：079 里钳制一行：`value = max(60, min(int(legacy["value"]), 28800))`。建议过重：让 `get_effective_settings()` 吞掉非法 override（静默降级）——源头钳制即可
- **验证**：静态核查 + T14 的真实 PG 迁移验证（正常值路径）；未构造越界历史行的迁移复现。

### XC-02 V1→V2 回放脚本固化的 Codex control transport 与已发布 manifest 不一致
- **判定**：FIX_IF_CHEAP —— 只 codex transport 是真漂移，claude 那半是 README:69 历史捕获
- **位置**：`scripts/harness-probes/v2/replay_v2.py:44-49` 对比 `deploy/worker-entrypoint/harness/manifest.json`
- **证据**：`CONTROL_TRANSPORT["codex"] = {"kind": "cli_jsonl", "protocol": "codex-jsonl"}`，而 manifest 与架构文档
  §3 均为 `{"kind": "rpc_stdio", "protocol": "codex-app-server-v2"}`。同一文件 `CLI_VERSION["claude"] = "2.1.152"`，
  manifest 为 `artifact_version: "2.1.153"`（`docs/harness-probes/v2/README.md` 亦写 `2.1.153`）。
- **影响**：`docs/harness-probes/v2/codex/success.v2.jsonl` 等回放 fixture 携带过期的 transport/版本字段，
  被归档为「V2 证据」时会误导后续读者把已废弃的 `cli_jsonl` 路径当成现网路径。
- **最小动作**：改 2 个字符串常量。建议过重：`replay_v2.py` 直接读 manifest.json（为探针脚本引入新解析耦合）
- **验证**：已比对两处文件内容（本次静态核查）。

### XC-03 构建/验收产物进入版本库且未被忽略
- **判定**：FIX_IF_CHEAP —— `.vite/vitest/results.json` 记的还是 failed 的陈旧结果
- **位置**：`output/playwright/task-451..459-*.png`（8 个二进制，本次新增）、`.vite/vitest/results.json`
- **证据**：`git check-ignore -v` 对二者均返回未忽略（exit 1）；`.gitignore:51` 只忽略 `.playwright-cli/`。
- **影响**：截图与 vitest 结果属于本地验收产物，入库后每次刷新都产生二进制 diff，长期膨胀仓库；
  `results.json` 还会在多机/多分支间产生无意义冲突。
- **最小动作**：`.gitignore` 加 `output/`、`.vite/` + `git rm --cached` 这 9 个文件
- **验证**：`git check-ignore` 与 `git diff --numstat` 实测。

### XC-04 `CLAUDE.md` 与代码漂移（容器命名、迁移归属）
- **判定**：FIX_IF_CHEAP —— 同一错名也在 `.github/copilot-instructions.md`
- **位置**：`CLAUDE.md:22`（容器命名 `codify-{task_id}-p{project_id}-i{issue_iid}`、`AUTO_MIGRATE` 说明）
  对比 `backend/app/core/worker_runtime.py:821`、`backend/app/core/task_helpers.py:75`、
  `backend/app/api/task_action_routes.py:154`、`backend/app/scheduler.py:2664`、`backend/app/config.py`
- **证据**：代码统一生成 `{worker_container_prefix}-{task_id}-issue{issue_id}`
  （`f"{prefix}-{task.id}-issue{task.issue_id}"`），不存在 `-p{project_id}-i{issue_iid}` 形态；
  `config.py` 中 `auto_migrate: bool = Field(default=False)`，而 `CLAUDE.md` 仍描述
  `AUTO_MIGRATE=false/true` 作为服务默认值（现为「必须显式配置」语义，且 `main.py` 增加了
  `require_explicit_harness_execution_mode` 启动门禁）。
- **影响**：按 `CLAUDE.md` 排查问题（例如按旧容器名 `docker ps`/正则找容器、判断迁移归属）会得到错误结论。
- **最小动作**：改 CLAUDE.md 两处 + copilot-instructions.md 同名处（共 ~4 行）
- **验证**：全仓 grep `issue{` 得到 5 处一致的代码实现，无旧命名残留。

### XC-05 探针与秘密扫描脚本没有任何自动化入口
- **判定**：ACCEPT/CLOSE —— 全仓无 CI，启发式扫描器没有自动入口不构成风险。
- **位置**：`scripts/harness-probes/v2/secret-scan.py`、`replay_v2.py`、`benchmark.sh`、`full-chain-driver.sh`、`scripts/dev-regression.sh`
- **证据**：`grep -rn "secret-scan|replay_v2|full-chain-driver|benchmark.sh" Makefile .github/workflows/*.yml scripts/dev-regression.sh docs/TESTING.md`
  无任何命中；脚本仅在 `docs/harness-probes/v2/README.md` 以手工命令形式记录。
- **影响**：秘密扫描与 V2 协议回放完全依赖人工记得执行；`secret-scan.py` 的规则本身也只是启发式
  （`sk-`/`glpat-`/`authorization`/`credential-assignment` 四类），未覆盖 OpenCode/Pi/Codex 形态的 token，
  却已被 evidence 文档引用为「passed, findings=0」的放行依据（`docs/superpowers/evidence/2026-09-04-open-harness-v2-r4.5-security-release-audit.md:45`）。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：grep 实测无引用；脚本规则逐条阅读。

### XC-INFO-01 命令入口预检改写 `request.scope["path"]` 与 `request._body`（私有属性）
- **判定**：ACCEPT/CLOSE —— 依赖私有属性但当前可用，beta 每次发命令都在跑这条中间件。
- **位置**：`backend/app/main.py:236-247`、`backend/app/main.py:150-170`
- **证据**：预检中间件在鉴权前完成 32 KiB 读体、JSON 解码与 `CreateCommandRequest` 校验，然后把
  `request._body = body`（Starlette 私有重放缓存）并重写 `scope["path"]` 为规范化后的命令路径。
- **影响**：设计意图清晰（在配置同步/鉴权前给出冻结的 422 契约），但依赖 Starlette 私有属性与
  `scope["path"]` 改写，升级 Starlette 时需回归；`raw_path` 与 `path` 不一致也可能影响审计日志/中间件的路径判断。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：静态阅读 `main.py:210-268`。

### XC-INFO-02 入口层反向依赖 API 层模型
- **判定**：ACCEPT/CLOSE —— 见证据
- **位置**：`backend/app/main.py:13`（`from app.api.task_command_routes import CreateCommandRequest`）
- **证据**：应用入口为中间件导入 API 路由模块内的请求模型，形成 `main -> api` 的模块级依赖。
- **影响**：目前无循环导入问题；但请求模型放在路由模块内被入口复用，后续重构路由结构时容易漏改。
- **动作**：不改代码（本阶段书面接受并关闭）

## 3. 逐项核查记录（已确认无问题）

| # | 核查项 | 结论 | 依据 |
|---|---|---|---|
| 1 | `.env.example` 是否含真实凭据 | 通过（仅占位符） | `deploy/.env.example:9,16` 分别为 20 个重复字符与 5 种字符的占位串；形状检查非真实 token |
| 2 | 日志/正文渲染 XSS | 通过 | `frontend/src/components/task-process/taskProcessUtils.ts:44-55` `new MarkdownIt({ html: false })`；`TaskView.vue:673` `new AnsiToHtml({ escapeXML: true })` |
| 3 | 凭据清洗覆盖 | 通过（模式较广） | `backend/app/core/worker.py:110-145`：glpat/sk-ant/sk-proj/sk-or/AIza/ghp_/hf_/xox/Bearer/`api_key=` 等 |
| 4 | 未知/被移除的持久化配置键 | 通过 | `backend/app/runtime_config.py:91-98` 对不在 `PERSISTED_CONFIG_TYPES` 的行记 warning 后忽略 |
| 5 | 旧 `task_timeout` 是否有迁移转换 | 通过（存在转换，但见 XC-01 边界问题） | `alembic/versions/079_task_execution_timeout.py:30-52` 复制到 peak/off-peak 并删除旧键 |
| 6 | 执行模式是否可被静默降级 | 通过 | `backend/app/core/harness_execution_policy.py:45-57` 校验 `model_fields_set`，未显式配置即拒绝启动 |
| 7 | 容器命名是否与实现一致 | 通过（文档不一致见 XC-04） | `worker_runtime.py:821`、`task_helpers.py:75`、`task_action_routes.py:154`、`scheduler.py:2664` 一致 |
| 8 | 探针脚本是否泄露原始模型输出/凭据 | 通过 | `full-chain-driver.sh` 丢弃 stdout 且注释声明不读凭据文件；`pi-rpc-sequence.sh` 只输出事件计数 |

## 4. 局限与未验证项

- 未在真实 PostgreSQL 上执行 079 迁移，XC-01 为静态推导，触发条件依赖历史配置值。
- 未运行任何探针脚本（需要真实 Pi/OpenCode/Claude/Codex CLI 与凭据）。
- `scripts/harness-probes/v2/summarize-run.py`、`provider-matrix.py` 仅抽读，未逐行审查。
- 前端是否仍有 Mermaid `securityLevel` 相关风险由专题 12 负责，本专题只确认 markdown/ANSI 两条主路径安全。
