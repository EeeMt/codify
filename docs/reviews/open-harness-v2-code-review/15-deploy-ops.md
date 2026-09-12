# 15 部署编排与离线包 —— Code Review

> 审查日期：2026-09-12 · 审查目标：`dev @ cbad9e56`
> 本专题覆盖 `deploy/**` 的编排文件与脚本、离线包、preflight、环境变量契约，以及 `Makefile`、
> `.gitignore`、`.dockerignore` 中的部署相关部分。未执行任何镜像构建或容器启动。

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56` |
| 文件 | `deploy/docker-compose.yml`(+41/-1)、`deploy/docker-compose.e2e.yml`(+29/-1)、`deploy/.env.example`(+4/-1)、`deploy/.env.test`(+21/-18)、`deploy/Dockerfile.backend`(+4/-3)、`deploy/Dockerfile.worker-kit`(+108/-12)、`deploy/Dockerfile.worker-java21-maven`(+15/-6)、`deploy/entrypoint.worker.sh`(+17/-12)、`deploy/scripts/preflight-v2-release.sh`(+157 新增)、`deploy/scripts/preflight-execution-mode.sh`(+60 新增)、`deploy/scripts/run-migration-owner.sh`(+83 新增)、`deploy/offline-bundle/**`(README +37/-11、docker-compose +32/-1、config/.env.offline.example +4/-1、docs/CONFIGURATION.md +4/-1、scripts/package-bundle.sh +91/-2、scripts/install-worker-kit.sh +152/-9、scripts/verify-worker-runtime.sh +27/-89、scripts/validate-kit-archive.py 新增 +131)、`Makefile`(+34/-12)、`.gitignore`(+3)、`.dockerignore`(+7)、`scripts/dev-regression.sh`(+3/-3) |
| 审查方法 | 静态阅读 HEAD 完整文件 + 调用方/契约对照 + `docker compose config` 插值复现（只读）+ 窄范围 Python/alembic 事实校验；未构建镜像、未启动容器 |
| 未覆盖 | worker 内 harness 执行细节（专题 07/08/09）、命令平面（01）、事件契约（02）、前端（12）、Alembic 迁移体（14）、Kit CLI 字节一致性（09）、凭据清洗（13）。未在真实 Docker Host 上演练任何流程 |

### 本次实际执行的验证命令（均为只读/无副作用）

| 命令 | 结果 |
|---|---|
| `cd deploy && env -u HARNESS_EXECUTION_MODE docker compose -f docker-compose.yml config` | rc=15，`required variable HARNESS_EXECUTION_MODE is missing a value` |
| `cd deploy && docker compose --env-file .env.test -f docker-compose.yml config` | rc=0（开发路径满足必填变量） |
| `cd deploy/offline-bundle && docker compose --env-file config/.env.offline.example -f docker-compose.yml config` | rc=15，缺 `HARNESS_EXECUTION_MODE` |
| 上条加 `HARNESS_EXECUTION_MODE=v2_only` 后重跑 | rc=15，缺 `MIGRATION_TARGET`（`services.migrate.command`） |
| `cd deploy && SCHEDULER_HEALTH_PORT=9100 docker compose --env-file .env.test -f docker-compose.yml config` | 渲染为 `env=9100` / `target 8001` / `published 9100`（容器端口与发布端口不一致） |
| `cd deploy && SCHEDULER_HEALTH_PORT=0 docker compose ... config` | 渲染为 `published "0"`（随机宿主端口），healthcheck 仍打 8001 |
| `backend/.venv/bin/python -c "from app.config import Settings; Settings(harness_execution_mode='dual_canary')"` | `ValidationError`（拒绝 `dual_canary`） |
| `backend/.venv/bin/python -c "...ScriptDirectory.from_config(...).get_current_head()"` | `alembic head = 079_task_execution_timeout` |

## 1. 结论摘要

| 等级 | 数量 |
|---|---|
| P0 | 0 |
| P1 | 2 |
| P2 | 8 |
| P3 | 1 |
| INFO | 6 |

编排层的主要方向是对的：`AUTO_MIGRATE` 已收敛为「Scheduler 单一 migration owner」（backend 固定 false），
`HARNESS_EXECUTION_MODE` 改为必填且只接受 `v2_only`（默认值不再放行），Kit/镜像 preflight 与离线包
校验链（sidecar → 路径 → manifest SHA 前缀 → 内容库存 → root 所有权）都做得比 V1 更严。但**两个独立
的命令行入口没有跟上这条硬约束**：离线包 `start.sh` 与 `make worker-runtime-bundle-export` 都会因为
新加的 `${VAR:?}` 必填插值直接失败；同时被测/被运维的两套栈（mock 集成 compose、E2E compose）分别留下
了 `dual_canary` 与落后 4 个版本的 migration 目标，形成「文档/模板说能用、实际跑不起来」的漂移。此外
`deploy/.env.test` 中真实密钥虽已被本次改动替换为占位值，但密钥仍在 git 历史中，必须按凭据事件处理。

## 2. 问题清单

### OPS-01 离线包 `start.sh` 因两个必填插值变量缺失无法启动
- **等级**：P1
- **位置**：`deploy/offline-bundle/docker-compose.yml:30`（另见 `:79`、`:128`）
- **证据**：
  - 本次改动新增 `- HARNESS_EXECUTION_MODE=${HARNESS_EXECUTION_MODE:?set HARNESS_EXECUTION_MODE to v2_only}`（backend `:30`、scheduler `:79`），`migrate` 服务新增 `command: [... alembic upgrade ${MIGRATION_TARGET:?set MIGRATION_TARGET to the reviewed Alembic revision}]`（`:123-128`）。
  - 实测：`cd deploy/offline-bundle && docker compose --env-file config/.env.offline.example -f docker-compose.yml config` → rc=15 `required variable HARNESS_EXECUTION_MODE is missing a value`；补上该变量后 → rc=15 `required variable MIGRATION_TARGET is missing a value`。
  - `config/.env.offline.example` 与 `docs/CONFIGURATION.md` 全文均无这两个键（grep 0 命中）；而 `deploy/offline-bundle/README.md:110` 指示「Run `./scripts/start.sh`」，`scripts/start.sh:22` 正是 `--env-file config/.env.offline -f docker-compose.yml up -d`。
  - 对照：`deploy/docker-compose.yml:153` 对同一变量使用 `${MIGRATION_TARGET:-}` 并注释「Blank is harmless during ordinary `docker compose config`」——即作者知道 `:?` 会破坏普通 compose 调用。
- **影响**：按 README/CONFIGURATION 的离线部署步骤在目标主机执行 `./scripts/start.sh`，会在插值阶段直接失败，整栈（含不启用 `maintenance` profile 的默认路径）都起不来；这是离线交付的主路径。
- **建议**：`config/.env.offline.example` 增加 `HARNESS_EXECUTION_MODE=v2_only`（并在 CONFIGURATION.md §3 列为必填），同时把 `migrate` 的 `MIGRATION_TARGET` 改为空默认（`${MIGRATION_TARGET:-}`）并交由运行期守卫脚本校验（见 OPS-07）。
- **验证**：已用 `docker compose config` 复现两次 rc=15；修复后同一命令应 rc=0。

### OPS-02 真实密钥曾被提交入库，替换占位符后仍留在 git 历史中（未轮换）
- **等级**：P1
- **位置**：`deploy/.env.test:6`（同文件 `:11` 为 Provider key；提交 `9cf05ff9` 于本次区间内替换为占位符）
- **证据**：`git show 8081c946^:deploy/.env.test` 中仍可读出两条真实凭据（GitLab bot token `glpat-*` 与
  Anthropic/GLM API key，明文不在此复述）；`git log -S` 显示 GitLab token 由基线前提交 `6cbd8dcc` 引入、
  由本次区间提交 `9cf05ff9` 移除；API key 同样由基线提交引入、区间内提交移除。本次改动只把它们改成
  `replace-via-secret-store`，仓库内没有任何轮换记录或吊销证据（HEAD 提交信息提到「rotate unreadable
  webhook secrets」，但 `deploy/.env.test` 无法证明该 token/key 已在 GitLab/Provider 侧吊销）。
- **影响**：任何能读取仓库历史（含 `origin/dev`、`origin/codify/issue-42`）的人都能取得这两个仍然有效的
  凭据，可直接以 bot 身份访问/修改 GitLab 与消耗模型额度。属于需要人工轮换的凭据事件，代码修改无法弥补。
- **建议**：立即在 GitLab 侧吊销该 bot token 并重置该 Provider key；在发布说明中记录轮换时间与责任人，
  并明确「仓库历史中的旧值作废」。后续用 secret-scan（另见横切 XC-05）覆盖历史扫描。
- **验证**：`git show <base>:deploy/.env.test` 已确认历史中存在；本次未接触任何线上服务，未验证轮换状态。

### OPS-03 mock 集成 compose 仍写 `dual_canary`，backend/scheduler 启动即崩
- **等级**：P2
- **位置**：`backend/tests/mock_integration/docker-compose.mock-test.yml:69`（另见 `:113`）
- **证据**：本次改动在该文件两处**新增** `HARNESS_EXECUTION_MODE: dual_canary`（`git diff` 显示为 `+` 行）；
  而 HEAD 代码只接受 `v2_only`：`backend/app/core/harness_execution_policy.py:15`
  （`HARNESS_EXECUTION_MODES = frozenset({"v2_only"})`）、`backend/app/config.py:220-227`（字段校验器拒绝
  其它值）。实测 `Settings(harness_execution_mode='dual_canary')` → `ValidationError`；
  `validate_harness_execution_mode('dual_canary')` → `invalid_harness_execution_mode`。
  `backend/app/main.py:58` 与 `backend/app/scheduler_service.py:34` 在启动时再次校验。
- **影响**：`make test-mock-integration`、`make test-mock-integration-parallel`（`Makefile:276/:304`）以及
  默认走 parallel 的 `make test-all`（`Makefile:497-508`）中，backend 与 scheduler 容器在加载 Settings 时
  就退出，healthcheck 永不通过，`up -d --wait` 超时，mock 集成套件整体不可运行。
- **建议**：两处改为 `HARNESS_EXECUTION_MODE: v2_only`。
- **验证**：已用 venv 实测 Settings 拒绝 `dual_canary`；未构建/启动容器（禁止构建）。

### OPS-04 E2E compose 的 migration 目标落后 4 个 revision，E2E 数据库 schema 与代码不符
- **等级**：P2
- **位置**：`deploy/docker-compose.e2e.yml:41`
- **证据**：新增的 `migrate` 服务命令为 `alembic upgrade ${MIGRATION_TARGET:-075_pi_command_dispatch_journal}`；
  实测 `ScriptDirectory.from_config(Config('alembic.ini')).get_current_head()` = `079_task_execution_timeout`
  （仓库存在 `076_v2_worker_image_identity`、`077_v2_worker_kit_identity`、`078_remove_provider_driver`、
  `079_task_execution_timeout`）。同一文件把 backend（`:46`）与 scheduler（`:131`）的 `AUTO_MIGRATE` 都设为
  `false`，全仓 grep 也不存在其它 alembic 调用，因此栈内没有任何组件会把 schema 推到 head。
  而 `backend/app/models.py:475` 已映射 `tasks.execution_timeout_seconds`（079 新增列）。
- **影响**：`docker-compose -f docker-compose.e2e.yml up` 后数据库停在 075，backend 一旦读写 tasks
  表就会因缺列报错（`UndefinedColumn: execution_timeout_seconds`），`make test-e2e` / `test-e2e-ui` /
  `test-e2e-gitlab` 全链路失败。
- **建议**：默认值改为 `${MIGRATION_TARGET:-head}`（e2e 场景无「已评审 revision」约束，head 即镜像内迁移）。
- **验证**：静态对照 + alembic head 实测；未运行 E2E（需 Docker，禁止构建）。

### OPS-05 `make worker-runtime-bundle-export` 未传 `--env-file`，文档化的 L3 导出命令直接失败
- **等级**：P2
- **位置**：`Makefile:54`
- **证据**：该目标（本区间新增）执行
  `docker-compose -f $(PROJECT_ROOT)/deploy/docker-compose.yml exec -T backend python -m app.scripts.export_runtime_bundle ...`，
  同文件其它所有 deploy 目标都带 `--env-file .env.test`（`:23`、`:58`、`:62`、`:66`、`:70`、`:74`、`:86`、
  `:91`、`:96`），本目标缺失。实测从仓库根执行 `docker compose -f deploy/docker-compose.yml config`
  → rc=15 `required variable HARNESS_EXECUTION_MODE is missing a value`（仓库不存在 `deploy/.env`，已确认）。
  compose 在 `exec` 之前必须先完成配置装载与插值，故该目标同样在插值阶段失败。
- **影响**：`docs/DEPLOYMENT.md` §10.1 与 `docs/runbooks/multi-harness-rollout.md` §5.1 记载的
  `make worker-runtime-bundle-export TASK_ID=... BUNDLE_EXPORT_DIR=...`（L3 证据导出）在干净 checkout /
  仅部署 `.env.production` 的环境下无法执行。
- **建议**：加 `--env-file .env.test`（与兄弟目标一致），或在该目标显式 `-e HARNESS_EXECUTION_MODE=v2_only`。
- **验证**：已复现插值错误（`config` 子命令）；`exec` 因需运行中容器未实测。

### OPS-06 `SCHEDULER_HEALTH_PORT` 端口契约不自洽：非默认值会让 Scheduler 永久 unhealthy
- **等级**：P2
- **位置**：`deploy/docker-compose.yml:105-107`
- **证据**：同一变量同时用于三处且只有一处跟随取值：
  - 容器环境 `SCHEDULER_HEALTH_PORT=${SCHEDULER_HEALTH_PORT:-8001}`（`:105`），应用按该值监听
    （`backend/app/scheduler_service.py:60`，无「0 = 不监听」分支）；
  - 发布映射 `"${SCHEDULER_HEALTH_PORT:-8001}:8001"`（`:107`）——容器端口硬编码 8001；
  - healthcheck `curl -f http://localhost:8001/health`（`:134`）——同样硬编码。
  实测 `SCHEDULER_HEALTH_PORT=9100 docker compose config` 渲染为 `SCHEDULER_HEALTH_PORT: "9100"`、
  `target: 8001`、`published: "9100"`；`SCHEDULER_HEALTH_PORT=0` 渲染为 `published: "0"`。
  另外 `backend/app/config.py:216-218` 注释写「Set 0 to disable the listener」，但 `scheduler_service.py`
  始终 `uvicorn.Config(port=settings.scheduler_health_port)`，0 只会绑定随机端口而非禁用。
- **影响**：运维一旦按注释覆盖该变量（含「设 0 关闭监听」），容器内实际监听端口与 healthcheck 目标不一致，
  Scheduler 永久 `unhealthy`；而 `nginx` 依赖 `scheduler: condition: service_healthy`（`:12-16`），入口
  永不开放——表现为「整个栈卡在启动中」。默认值 8001 下行为正常，故非 P1。
- **建议**：让发布映射与 healthcheck 引用同一变量（例如 `"${SCHEDULER_HEALTH_PORT}:${SCHEDULER_HEALTH_PORT}"`
  与 `curl -f http://localhost:${SCHEDULER_HEALTH_PORT}/health`），或把该变量限定为宿主端口、容器端口固定
  8001；若确实要支持 0=禁用，需在 `scheduler_service.py` 实现跳过监听并同步 healthcheck。
- **验证**：已用 `docker compose config` 复现渲染结果；未启动容器验证 unhealthy 表现。

### OPS-07 离线包 maintenance `migrate` 绕过 `run-migration-owner` 的 fail-closed 守卫
- **等级**：P2
- **位置**：`deploy/offline-bundle/docker-compose.yml:128`
- **证据**：离线包新增的 `migrate` 服务直接执行 `python3 -m alembic upgrade ${MIGRATION_TARGET:?...}`
  （`:123-128`），只校验「非空」；而开发 compose 走守卫脚本
  `deploy/docker-compose.yml:154` `command: ["/usr/local/bin/run-migration-owner"]`，该脚本
  （`deploy/scripts/run-migration-owner.sh:8-12`、`:23-45`、`:56-62`）拒绝空白/`head`/非法字符/未随镜像发布的
  revision/当前 revision 的祖先（禁止 downgrade）。镜像内已包含该脚本（`deploy/Dockerfile.backend:70-72`）。
- **影响**：离线环境按 compose 执行维护迁移时，`MIGRATION_TARGET=base` 会触发破坏性 downgrade，
  `MIGRATION_TARGET=head` 会让维护动作依赖未评审镜像内容，与 V2「已评审 revision + roll-forward-only」
  的硬切约束冲突；两套 compose 的维护语义不一致，运维易按在线经验误操作。
- **建议**：改为 `command: ["/usr/local/bin/run-migration-owner"]`，并把 `MIGRATION_TARGET` 改为空默认
  （`${MIGRATION_TARGET:-}`），由脚本自身做 fail-closed 校验（与 `deploy/docker-compose.yml:140-154` 对齐）。
- **验证**：静态对照两侧 compose 与脚本；未在离线环境执行 maintenance 流程。

### OPS-08 部署文档仍把 `dual_canary` 写成合法值，按文档执行会启动失败
- **等级**：P2
- **位置**：`docs/DEPLOYMENT.md:134`（另见 `:20`、`:64`）
- **证据**：这三行都是本次改动**新增/改写**的内容：
  - `docs/DEPLOYMENT.md:20`「`HARNESS_EXECUTION_MODE` 必须显式设置为 `dual_canary` 或 `v2_only`」；
  - `docs/DEPLOYMENT.md:64`「验证阶段使用 `dual_canary`；硬切验收通过后才使用 `v2_only`」；
  - `docs/DEPLOYMENT.md:134` `HARNESS_EXECUTION_MODE=dual_canary docker compose up -d --build backend scheduler nginx`；
  - 同类：`docs/README.zh-CN.md:373`（默认值 `dual_canary`）、`:421`（`dual_canary|v2_only`）、
    `docs/DEVELOPMENT.md:132`（`HARNESS_EXECUTION_MODE=dual_canary uvicorn app.main:app`）。
  而 HEAD 只接受 `v2_only`：`backend/app/core/harness_execution_policy.py:15`、`backend/app/config.py:220-227`
  （实测 `Settings(...)` 与 `validate_harness_execution_mode(...)` 均拒绝 `dual_canary`）。
- **影响**：运维照 DEPLOYMENT.md §4.3 / DEVELOPMENT.md 执行，Backend 与 Scheduler 会在启动校验处
  fail-closed 退出（错误信息为 `HARNESS_EXECUTION_MODE must be one of ['v2_only']`），被误判为发布故障；
  `docker compose up` 之后的 health 门禁与 NGINX 也不会开放。
- **建议**：三处文档统一改为 `v2_only`，并注明 `dual_canary` 已随 hard cut 删除（保留一句历史说明）。
- **验证**：文档按行号核对 + 代码侧已实测拒绝；未实际部署。

### OPS-09 多 Harness 上线 runbook 仍以 dual-canary/legacy V1 overlay 为前提，回滚步骤不可执行
- **等级**：P2
- **位置**：`docs/runbooks/multi-harness-rollout.md:34`（另见 `:11`、`:132`、`:211`、`:280`、`:286`、§8 `:259-268`）
- **证据**：
  - `:11` / `:286`（本次改动新增句）「基础 Compose 保留 legacy V1 execution path；只有显式 V2 release overlay …」；
  - `:34` 冻结清单要求 `HARNESS_EXECUTION_MODE=dual_canary`；
  - `:132` 同时承认「`docker-compose.v2-release.yml` 已随旧链删除」，即该 overlay 已不存在；
  - §8 回滚（`:259-268`）第 7 步要求「创建 legacy V1 smoke Task，验证 Issue 分配与完整执行路径恢复」，
    但 hard cut 后 V1 创建/执行已被拒：`docs/superpowers/evidence/2026-09-09-open-harness-v2-r4.6-dev-hard-cut.md`
    §4 记录 V1 create → HTTP 422 `legacy_contract_not_executable`，代码侧见
    `backend/app/core/harness_execution_policy.py:217-225` 与 `backend/app/api/task_action_routes.py:91-94`。
- **影响**：运维按此 runbook 推进或回滚会指向不存在的路径（无 overlay、无 `dual_canary`、V1 smoke 无法创建），
  §8/§9 要求的「回滚演练」在实现上不可能完成；与 hard cut 事实上的 roll-forward-only 声明矛盾。
- **建议**：把 §1/§2/§6/§8/§9.1 改写为 `v2_only` + roll-forward-only：回滚定义收敛为「回到同一 V2 形态的
  上一个 release（backend/nginx 镜像、Kit、Runtime Bundle、Profile snapshot）」，并删除 legacy V1 smoke 步骤。
- **验证**：文档行号 + 代码/证据文档对照；未在任何环境演练回滚。

### OPS-10 生产密钥仍被引导写入仓库内被追踪的 `deploy/.env.test`（本次仅加了「不要写」的注释）
- **等级**：P2
- **位置**：`deploy/docker-compose.yml:29-30`（`env_file: .env.test`）
- **证据**：`deploy/.env.test` 是 git 已追踪文件（`git diff` 中显示为 `M`），同时 `.gitignore:47` 又把它列为
  忽略项（对已追踪文件无效）；本次改动给该文件新增头部注释「never write them into this tracked file」，
  但同一改动的 `docs/DEPLOYMENT.md` §4.1 仍指示「`cp .env.test .env.production`」并「或者直接维护现有文件名」，
  且 `deploy/docker-compose.yml`（backend `:29-30`、scheduler `:82-83`、migrate `:146-147`）继续把
  `.env.test` 作为运行时 env_file。这正是 OPS-02 中两条真实凭据进入历史的通道。
- **影响**：运维按文档把 `SECRET_KEY`/`GITLAB_BOT_TOKEN` 等真实值写入 `deploy/.env.test` 后，该文件处于版本
  控制下，任何一次误提交都会再次把生产密钥写进历史；注释与实际操作路径自相矛盾。
- **建议**：`git rm --cached deploy/.env.test`（保留 `deploy/.env.example` 作为模板）并把 compose 的
  `env_file` 指向未追踪文件（如 `deploy/.env.production`，或使用 `${ENV_FILE:-.env.test}`），同步修正
  DEPLOYMENT.md §4.1 的命令。
- **验证**：`git ls-files deploy/.env.test` 确认追踪状态；`.gitignore:47` 与 compose `env_file` 行号已核对。

### OPS-11 `.dockerignore` 未排除 `.env.*`，部署密钥文件进入构建上下文
- **等级**：P3
- **位置**：`.dockerignore:20`
- **证据**：排除项只有 `.env`（`:20`）、`.env.local`（`:66`）、`.env.*.local`（`:67`），没有 `.env.production`
  / `.env.test`；而 `!deploy/`（`:44`）把整个 `deploy/` 重新纳入构建上下文。`docs/DEPLOYMENT.md` §4.1 引导在
  `deploy/` 下就地生成含真实 `SECRET_KEY` 的 `.env.production`，构建上下文会把该文件整体发送给 Docker
  daemon / 远程 builder。
- **影响**：当前 Dockerfile 未 `COPY` 这些文件，故尚未泄露进镜像层；但每次 `docker compose build` 都会把
  生产密钥文件传输到 builder（含远程 daemon 场景），一旦后续新增 `COPY .` 或 `COPY deploy/` 即直接入镜像层。
  当前 `.env.test` 已是占位值，影响有限，故 P3。
- **建议**：`.dockerignore` 增加 `.env.*`（如需保留模板再 `!.env.example`）。
- **验证**：静态核对 `.dockerignore` 全文与构建上下文来源路径；未实际构建验证。

### INFO-01 `preflight-v2-release.sh` 覆盖面具限于 Kit + Worker 镜像身份
- **等级**：INFO
- **位置**：`deploy/scripts/preflight-v2-release.sh:31-160`
- **证据**：脚本校验顺序为 归档 `.sha256` sidecar（`:41-47`）→ 归档名 content-addressed 正则（`:49-54`）→
  成员/可执行位（`:63-102`）→ manifest SHA 与归档名前缀一致（`:104-110`）→ manifest 形状与四 key
  inventory（`:112-131`）→ 目标 daemon 上镜像存在、image ID、平台一致（`:149-160`）；失败统一 `exit 2`
  （`fail()` `:26-29`），阻断行为正确。但**不校验**：待部署的 backend/nginx 镜像身份、数据库 revision、
  离线包内制品、以及 `V2_RELEASE_WORKER_IMAGE` 是否 digest 固定（`docs/DEPLOYMENT.md:271` 示例即为可变 tag）。
  执行模式一致性由另一个脚本覆盖（`deploy/scripts/preflight-execution-mode.sh:31-51`，不一致时 exit 1）。
- **影响**：发布前置门禁的真实覆盖面小于「硬切前置条件」清单，DB revision/后端镜像需依赖 runbook 的人工步骤。
- **建议**：在文档中显式列出 preflight 覆盖矩阵（已覆盖/未覆盖），或在同脚本追加 `alembic heads` 与
  backend 镜像 ID 记录。
- **验证**：逐行阅读脚本；未在真实 daemon 上运行。

### INFO-02 离线包用可变 tag 加载镜像，且没有校验 `images/SHA256SUMS`
- **等级**：INFO
- **位置**：`deploy/offline-bundle/README.md:28-29`（要求按 repo digest 校验）；实现侧 `deploy/offline-bundle/scripts/load-images.sh:13` 未变
- **证据**：`load-images.sh` 直接 `gunzip -c ... | docker load`，从不读取 `export-images.sh:20-24` 生成的
  `images/SHA256SUMS`；离线 compose 与开发 compose 均引用 `codify-backend:latest` / `codify-nginx:latest`。
  而 `deploy/offline-bundle/README.md`（本次新增段落）要求「verified by repo digest after loading, not by
  mutable tag」，工具链没有任何实现。
- **影响**：若运维漏执行或部分执行 `load-images.sh`，栈会静默使用宿主上同 tag 的旧镜像，无任何提示或阻断。
- **建议**：`load-images.sh` 增加 `sha256sum -c images/SHA256SUMS` 校验，并在 `export-images.sh` 额外记录
  每个镜像的 repo digest 供 `start.sh` 比对。
- **验证**：静态阅读两个脚本；未执行加载。

### INFO-03 版本坐标漂移（worker 镜像 tag / Kit 默认版本）
- **等级**：INFO
- **位置**：`deploy/.env.test:27`
- **证据**：`deploy/.env.test:27` `WORKER_IMAGE=codify-worker/java21-maven:2026.08`，而 `Makefile:17`
  `RUNTIME_IMAGE ?= codify-worker/java21-maven:2026.07`、`deploy/.env.example:45` 与
  `deploy/offline-bundle/config/.env.offline.example:38` 均为 `2026.07`。Kit 版本同样三处不一：
  `deploy/worker-kit/export.sh:5` 默认 `0.4.0`、`deploy/Dockerfile.worker-kit:4` 默认 `0.6.17`、
  `Makefile:12` 为 `0.6.17`。
- **影响**：`make worker-kit-verify`（`Makefile:16-17`）默认校验 `2026.07` 镜像，而 compose 部署的是
  `2026.08`；直接调用 `deploy/worker-kit/export.sh`（不经 Makefile 传 `WORKER_KIT_VERSION`）会产出 0.4.0
  命名的 Kit，与冻结清单不一致。
- **建议**：让 `.env.test`、Makefile 默认值与 `.env.example` 使用同一 release 坐标，或把 `RUNTIME_IMAGE`
  默认值改为从 `.env.test` 读取。
- **验证**：逐文件比对版本字符串；未构建任何镜像确认 tag 是否存在。

### INFO-04 maintenance `migrate` 无并发互斥，也无维护窗口前置检查
- **等级**：INFO
- **位置**：`deploy/scripts/run-migration-owner.sh:1-14`
- **证据**：脚本只校验目标 revision 合法性（`:8-12`、`:23-45`、`:56-62`），不提锁、不检查是否存在
  `PENDING/QUEUED/RUNNING` 任务；`deploy/docker-compose.yml:140-154` 的 `migrate` 服务与在跑的
  Scheduler 之间没有任何互斥，而 Scheduler 在 `AUTO_MIGRATE=true` 时会于启动阶段执行迁移
  （`deploy/entrypoint.backend.sh:39-40`、`backend/app/migrations.py:23-45`），两者可并发。
- **影响**：并发场景下通常表现为其中一方报「已存在/重复列」而失败退出（Postgres DDL 在事务内），
  而非静默损坏；但「迁移期间无任务在跑」目前完全依赖 runbook 的人工步骤，没有强制门禁。
- **建议**：在守卫脚本中增加「无活跃任务」前置查询（或使用 PG advisory lock），并在文档中把该检查写成
  脚本行为而非人工约定。
- **验证**：静态阅读；未构造并发迁移场景。

### INFO-05 离线包没有 execution-mode preflight 等价物，且前置依赖未列 `python3`
- **等级**：INFO
- **位置**：`deploy/offline-bundle/docker-compose.yml:109-110`（新增的 Scheduler healthcheck）；实现侧 `deploy/offline-bundle/scripts/health-check.sh:20-21` 未变
- **证据**：离线 `health-check.sh` 只打印 backend/frontend 的 HTTP 状态码，不检查
  `harness_execution_mode`；`deploy/scripts/preflight-execution-mode.sh` 不随离线包分发（bundle 脚本清单见
  README `:5-19`）。同时 `deploy/offline-bundle/docs/CONFIGURATION.md` §1 的 Host 前置条件未列 `python3`，
  但 `install-worker-kit.sh`、`verify-worker-runtime.sh`、`validate-kit-archive.py` 与 `verify-kit-content.py`
  都强制要求 `python3`。
- **影响**：离线部署无法自证执行模式一致（只能事后手工 curl）；无 `python3` 的主机会在安装 Kit 阶段才失败。
- **建议**：把 execution-mode 校验并入 `health-check.sh`（解析 `/health` 的 JSON 字段），并在 CONFIGURATION.md
  前置条件中补 `python3`。
- **验证**：静态阅读三个脚本与离线包文件清单；未执行离线安装。

### INFO-06 运行时暴露面小结（含 V1 遗留项）
- **等级**：INFO
- **位置**：`deploy/docker-compose.yml:172`
- **证据**：`[V1 遗留]` postgres 以 `"5432:5432"` 发布到宿主所有接口，密码 `codify_password` 硬编码在同一文件
  （密码 `:166`、端口 `:172`，基线中已存在）；全文件无 `logging` 限额、无内存/CPU 限制、
  无 `privileged`/`cap_add`；新增的 Scheduler `/health` 监听 `0.0.0.0:8001`（`backend/app/scheduler_service.py:59-60`）
  并发布到宿主（`deploy/docker-compose.yml:107`），无鉴权，但仅暴露 `status` 与 `harness_execution_mode`。
  `docker.sock` 挂载（`:59`、`:122`）是动态创建 Worker 容器的功能必需项，未发现可去耦的替代路径。
- **影响**：暴露面与 V1 相比基本不变（新增一个信息量极小的健康端点）；无日志轮转意味着长期运行会无界增长
  json-file 日志，属既有运维债务。
- **建议**：为 backend/scheduler 增加 `logging.options.max-size/max-file`；如无外部采集需求，把 8001 与 5432
  改为 `127.0.0.1:` 绑定。
- **验证**：逐行阅读 compose 全文 + scheduler_service 监听配置；未做端口扫描。

## 3. 逐项核查记录（关键契约 → 结论 → 依据）

| # | 不变量/契约 | 结论 | 依据 |
|---|---|---|---|
| 1 | `AUTO_MIGRATE` 只有 Scheduler 为 true | 通过 | `deploy/docker-compose.yml:38`(backend false)/`:93`(scheduler true)；`deploy/offline-bundle/docker-compose.yml:29`/`:78`；`deploy/docker-compose.e2e.yml:46`/`:131` 双 false + 专用 `migrate` 服务（`:35-52`）；`deploy/entrypoint.backend.sh:39-40` 与 `backend/app/migrations.py:23-25` 都按该开关判定 |
| 2 | `run-migration-owner` 幂等 + fail closed + 有维护窗口前置检查 | 部分通过：幂等与 fail-closed 通过；维护窗口/并发无强制门禁 | `deploy/scripts/run-migration-owner.sh:8-12` 拒绝空/`head`/非法字符；`:23-45` 拒绝未随镜像发布的 revision；`:56-62` 拒绝当前 revision 的祖先（防 downgrade）；`:63` 仍走 `alembic upgrade`（对已应用目标为 no-op）。无锁、无活跃任务检查 → INFO-04 |
| 3 | hard cut 后 V1 执行被真正禁用（服务端强制，不靠环境变量/前端） | 通过 | `backend/app/core/harness_execution_policy.py:15` 仅 `v2_only`；`:217-225` 拒绝非 V2 bundle（`legacy_contract_not_executable`）；`backend/app/scheduler.py:511`、`:1304`、`:1386` 按 `v2_only` 过滤可执行队列，`:2216` 启动收敛遗留契约；`backend/app/api/task_action_routes.py:91-94` 拒绝 legacy 任务的启动类操作。实测 `Settings`/`validate_harness_execution_mode` 拒绝 `dual_canary` |
| 4 | 执行模式开关默认值安全（缺省不放行 V1） | 通过 | compose 强制必填：`deploy/docker-compose.yml:41/:95`、`deploy/offline-bundle/docker-compose.yml:30/:79`、`deploy/docker-compose.e2e.yml:47/:72/:132` 显式 `v2_only`；`backend/app/config.py:215` 默认 `v2_only`，且 `harness_execution_policy.py:45-57` 以 `model_fields_set` 要求显式配置，纯默认值不放行 |
| 5 | 回滚声明与实现一致（roll-forward-only） | 不一致（文档侧） | OPS-09：`docs/runbooks/multi-harness-rollout.md:11/:34/:132/:259-268/:286` 仍描述 legacy V1 路径与 overlay；实现侧 V1 create/execute 已拒（`harness_execution_policy.py:217-225`，证据文档 §4）。`docs/DEPLOYMENT.md:125-128` 的 roll-forward-only 表述与实现一致 |
| 6 | preflight 覆盖硬切前置条件且失败阻断 | 部分通过 | 覆盖：Kit 归档 sidecar/成员/manifest 形状/内容库存/归档名（`preflight-v2-release.sh:41-131`）、镜像存在与平台（`:149-160`）；执行模式一致性（`preflight-execution-mode.sh:31-51`，不一致或不可达 exit 1）。未覆盖：DB revision、backend/nginx 镜像、离线制品、digest 固定（INFO-01）。失败阻断：`set -euo pipefail` + `fail(){exit 2;}`（`:26-29`） |
| 7 | compose/env 变量与 `backend/app/config.py` 一致、缺省不导致静默降级 | 部分通过 | 新增 `TASK_TIMEOUT_PEAK_*`/`TASK_TIMEOUT_OFF_PEAK_*` 与 `config.py:275-278` 一致（`.env.example:66-69`、`.env.test:31-34`、offline example:46-49）；`HARNESS_EXECUTION_MODE` 仅 `.env.test:37` 提供，`.env.example` 与离线模板缺失 → OPS-01/OPS-08；`SCHEDULER_HEALTH_PORT` 未出现在任何 env 模板（compose 默认 8001，`config.py:218`），覆盖即 OPS-06；旧 `TASK_TIMEOUT` 因 `config.py:106 extra="ignore"` 被静默忽略，spec 明确要求人工替换（`docs/superpowers/specs/2026-09-09-peak-off-peak-task-timeout-design.md:345-349`），属已声明的破坏性变更，记为 INFO |
| 8 | 部署侧 `get_settings()` vs `get_effective_settings()` 使用面 | 通过 | `/health` 用 `get_settings()`（`backend/app/main.py:322`、`backend/app/scheduler_service.py:54`），与启动门禁同源；任务创建/执行用 `get_effective_settings()`（`backend/app/api/task_creation_service.py:677/:731`、`backend/app/api/task_operations.py:99`）。`harness_execution_mode` 不在 DB 覆盖键集合内（`backend/app/config.py:35-100` 的类型表未含它），两者对 mode 等价 |
| 9 | 镜像与制品固定性/可复现 | 部分通过（记为 INFO） | 基础镜像按 tag 固定（`deploy/Dockerfile.worker-kit:3` `nixos/nix:2.24.11`、`alpine:3.21`、`golang:1.24-alpine`）；应用镜像用本地 `:latest` + `build`（`deploy/docker-compose.yml:3-4`、`:22-23`）；`docker build` 未带 `--pull`（`deploy/worker-kit/export.sh:174-180`、`Makefile:48`）；preflight 接受可变 tag（INFO-01/INFO-02）；Kit 归档字节不可复现见专题 09 KIT-07（不重复记账） |
| 10 | 运行时安全（socket/特权/端口/健康检查/重启/日志/资源） | 部分通过 | docker.sock 挂载（`deploy/docker-compose.yml:59`/`:122`）为功能必需；无 privileged/cap_add；`restart: unless-stopped`（`:17`、`:68`、`:130`、`:170`）；Scheduler 新增 healthcheck（`:133-138`），nginx 依赖其 healthy（`:12-16`）；缺日志限额/资源限制、postgres 暴露见 INFO-06 |
| 11 | 幂等与清理（重复 up、容器名、残留） | 通过（设计如此） | 除 one-shot `migrate` 外所有服务固定 `container_name`（`:9`、`:26`、`:80`、`:163`），重复 `up -d` 复用/重建而不产生副本；`migrate` 走幂等守卫脚本（`:154`）；Kit 安装拒绝覆盖既有身份目录（`deploy/offline-bundle/scripts/install-worker-kit.sh:66-69`） |
| 12 | `.gitignore`/`.dockerignore` 覆盖产物与敏感文件 | 部分通过 | `.gitignore` 有 `node_modules/`、`deploy/worker-cli/`（`:30`、`:76`）；构建产物入库问题由横切 XC-03 记录（不重复）；`.dockerignore` 排除 `deploy/worker-cli/**`、`deploy/offline-bundle/`、`**/node_modules`，缺 `.env.*` → OPS-11 |
| 13 | 离线包校验和、内容完整性、无网络依赖 | 通过（打包/安装侧） | 打包：`package-bundle.sh:22-24` 缺 verifier 即拒；`:50` sidecar 校验；`:56` 路径校验；`:75-86` 归档与解包内容库存必须一致；`:113-115` 生成 bundle SHA-256 sidecar。安装：`install-worker-kit.sh:36-43` 校验 sidecar、`:45-57` 要求 root 且安装根 root 所有/不可写、`:89`/`:105` 归档与落盘内容库存、`:113-117` manifest SHA 前缀、`:120-135` 平台一致、`:66-69` 拒绝覆盖。网络依赖与可变 tag 见 INFO-02 |
| 14 | 密钥不入库 | 失败 | OPS-02（历史密钥仍有效）、OPS-10（追踪的 `.env.test` 仍是运行时 env_file）；本次改动已把工作区明文替换为占位符（`deploy/.env.test:6`/`:11` 等） |

## 4. 局限与未验证项

- **未构建、未启动任何容器**：所有编排结论来自静态阅读 + `docker compose config`（只读插值）+ 窄范围
  Python/alembic 事实校验。因此 OPS-03/OPS-04 的运行时表现为静态推理（Settings 拒绝已实测，容器退出未实测）。
- **未在真实 Docker Host 执行**：`preflight-v2-release.sh`、`install-worker-kit.sh`、`package-bundle.sh`、
  离线 `start.sh` 全流程均未运行；远程 daemon 场景（路径可见性、digest 校验）未验证。
- OPS-05 仅以 `config` 子命令复现插值错误，`exec` 子命令未实测（需运行中容器）。
- OPS-02 无法确认 GitLab/Provider 侧凭据是否已轮换或吊销（本次未接触线上系统）。
- OPS-04 未运行 E2E（禁止构建）；`UndefinedColumn` 结论由「migrate 目标 075 + 模型已含 079 列」推出。
- 本专题不覆盖：worker-entrypoint/Kit 内部行为（07/08/09）、命令平面与事件契约（01/02）、Alembic 迁移体
  正确性（14）、前端（12）、凭据清洗与鉴权实现（13）。
