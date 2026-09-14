# 生产环境部署指南

本文档面向运维和部署人员，说明如何在长期运行的环境中部署 Codify（Codify），以及如何安全地更新、备份和排障。

## 1. 部署目标与架构

默认部署方式基于 `deploy/docker-compose.yml`，会启动 4 个常驻服务：

- `postgres`：持久化任务、配置、用户、会话和审计数据，镜像 `postgres:16-alpine`，端口 `5432:5432`
- `backend`：HTTP API 与 Dashboard 后端，镜像 `codify-backend:latest`，端口 `8000:8000`
- `scheduler`：任务调度与崩溃恢复，复用 backend 镜像，端口 `${SCHEDULER_HEALTH_PORT:-8001}:8001`
- `nginx`：前端静态资源与反向代理入口，镜像 `codify-nginx:latest`，端口 `8880:80`

compose 里还定义了第五个服务 `migrate`，它挂在 `maintenance` profile 下，正常上线不会启动。

当前 compose 约定：

- `backend` 与 `scheduler` 共用 `codify-backend:latest`
- `backend` 固定 `AUTO_MIGRATE=false`；`scheduler` 是唯一的启动阶段 migration owner，使用
  `AUTO_MIGRATE=true`
- `nginx` 等待 Backend 与 Scheduler health 后才开放入口；正常上线不单独运行 `migrate` profile
- `HARNESS_EXECUTION_MODE` 默认 `v2_only`，无需显式设置；`dual_canary` 已随硬切删除
- PostgreSQL 数据挂载在 Docker volume `postgres_data`
- `backend` 与 `scheduler` 都挂载宿主机的 `/var/run/docker.sock`，因为 Worker 容器由它们通过 Docker API 动态创建

## 2. 部署前准备

### 2.1 基础依赖

请确认目标主机满足以下条件：

- 已安装 Docker 和 Docker Compose
- 可访问目标 GitLab 实例
- 可访问四个 Harness 的兼容模型服务（Pi/OpenCode/Claude/Codex）
- Docker Engine 允许当前部署方式所需的 Worker 容器启动能力
- 宿主机路径已就绪。Compose 把这几条 bind 挂进 backend 与 scheduler：
  - `/opt/ca.crt` 必须作为文件存在。这条 bind 设了 `create_host_path: false`，文件缺失时 `docker compose up` 直接报错。没有自签 CA 时改 `deploy/docker-compose.yml` 里的 source，或先放一个占位证书
  - `/opt/codify-workspaces`，Worker 工作区根目录，路径要与 Worker 容器内看到的完全一致
  - `/opt/codify-archives`，V2 Runtime Bundle 导出目录
  - `/opt/codify-ci-failures` 与 `/opt/codify-docker-certs`，可用 `CI_FAILURE_BUNDLE_HOST_PATH`、`DOCKER_CERTS_HOST_PATH` 改路径
- 调度器会在同一个 Docker Host 上创建 Worker 容器，因此 `WORKER_WORKSPACE_HOST_PATH` 在控制面容器和 Worker 容器里必须是同一个绝对路径

### 2.2 关键配置项

`deploy/docker-compose.yml` 当前通过 `deploy/.env.test` 为 `backend` 和 `scheduler` 注入环境变量。生产环境至少需要准备以下配置：

#### GitLab

- `GITLAB_URL`
- `GITLAB_BOT_TOKEN`

#### 模型服务

- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`

#### 应用安全

- `SESSION_SECRET`：会话令牌签名密钥。`deploy/.env.example` 与 `deploy/offline-bundle/config/.env.offline.example` 都已带这一项；`deploy/.env.test` 仍然只有 `SECRET_KEY`，而 `SECRET_KEY` 在代码里只有一个默认值、没有任何读取点，所以以 `.env.test` 为底复制正式环境文件时，要把它换成 `SESSION_SECRET`
- `CONFIG_ENCRYPTION_KEY`：加密写入 `system_config` 的敏感值。留空时回退到 `SESSION_SECRET`，两者都停留在默认值时保存密钥类配置会失败

#### 调度与 Worker

- `WORKER_IMAGE`
- `WORKER_WORKSPACE_HOST_PATH`
- `MAX_CONCURRENCY`
- `TASK_TIMEOUT_PEAK_SECONDS`
- `TASK_TIMEOUT_OFF_PEAK_SECONDS`
- `TASK_TIMEOUT_PEAK_START`
- `TASK_TIMEOUT_PEAK_END`
- `SCHEDULER_INTERVAL`
- `SCHEDULER_HEALTH_PORT`（默认 `8001`，preflight 脚本按这个端口取 Scheduler 健康信息）
- `DEFAULT_TARGET_BRANCH`
- `HARNESS_EXECUTION_MODE`（默认 `v2_only`，无需显式设置；`dual_canary` 已删除）

#### 入口与代理

- `BACKEND_URL`、`FRONTEND_URL`：任务链接与 webhook 回写使用的外部地址
- `COOKIE_SECURE`：走 HTTP 入口时保持 Compose 里的 `false`，前置 HTTPS 后设为 `true`
- `CUSTOM_CA_BUNDLE`（容器内路径）与 `WORKER_CA_CERT_HOST_PATH`（宿主机路径）：自签 CA 场景使用

#### 可选认证配置

- OIDC 相关环境项只提供默认值，实际参数在 `/configuration` 页面配置；可持久化的键包括 `oidc_enabled`、`oidc_issuer_url`、`oidc_client_id`、`oidc_client_secret`、`oidc_redirect_uri`
- Break-glass 走环境变量，且不在 `/configuration` 页面里：`AUTH_BREAK_GLASS_ENABLED`、`AUTH_BREAK_GLASS_USERNAME`、`AUTH_BREAK_GLASS_PASSWORD_HASH`

环境变量与 Dashboard 的两层关系：`get_effective_settings()` 先读环境变量，再用 `system_config` 表中的覆盖值顶掉同名字段，所以同一个键在页面里改过之后，改 `.env` 不会立刻生效。`--env-file` 参数只影响 compose 文件里的 `${...}` 插值，容器内的环境变量仍然来自 `env_file: .env.test` 指向的那个文件。

## 3. 持久化与数据安全

这是生产部署里最重要的一条：

- 运行时配置、OIDC 配置、用户、会话、审计日志都保存在 PostgreSQL 中
- Dashboard 中通过 `/configuration` 页面录入的敏感配置会加密后落到数据库
- 如果 PostgreSQL volume 被删除，以上数据会一并丢失

因此请避免在生产环境执行以下操作：

```bash
docker-compose down -v
```

这个命令会删除 volume，等价于重置数据库。

建议至少建立以下备份策略：

- 定期导出 PostgreSQL 数据库
- 定期备份 Docker volume 或底层磁盘快照
- 对 `deploy/.env.test` 或对应的正式环境变量来源做安全备份
- 单独保留 OIDC Client Secret、Break-glass 配置等恢复材料

逻辑备份用容器自带的 `pg_dump`，先停掉写入方再导出：

```bash
cd deploy
docker compose stop backend scheduler
docker exec codify-postgres pg_dump -U codify -d codify -F c -f /tmp/codify-backup.dump
docker cp codify-postgres:/tmp/codify-backup.dump ./codify-$(date +%F).dump
docker exec codify-postgres rm -f /tmp/codify-backup.dump
docker compose start backend scheduler
```

恢复时把 dump 拷回容器，用 `pg_restore` 覆盖现有 schema 与数据。这一步会先删表，只在确认要回到备份点时执行：

```bash
docker cp ./codify-<date>.dump codify-postgres:/tmp/restore.dump
docker exec codify-postgres pg_restore -U codify -d codify --clean --if-exists /tmp/restore.dump
```

volume 级备份对应 `<compose 项目名>_postgres_data`（默认项目名取自 `deploy` 目录，即 `deploy_postgres_data`），可以在停机后对底层磁盘做快照，或用一次性容器打包该 volume。恢复完成的库必须与迁移历史对齐，回滚 schema 用修订版本做不到，只能从备份恢复。

## 4. 首次部署流程

### 4.1 准备配置文件

在 `deploy/` 目录准备环境变量文件，例如：

```bash
cd deploy
cp .env.test .env.production
```

然后将 `docker-compose.yml` 中 `env_file` 指向你的正式配置文件，或者直接维护现有文件名。`docker compose --env-file` 只替换 compose 里的 `${...}` 变量，容器环境仍然读 `env_file` 指的那个文件。

至少确认以下两类密钥已替换为正式值：

- `SESSION_SECRET`
- `CONFIG_ENCRYPTION_KEY`

如果这两个值不稳定或被重置，会影响会话和已落库配置的解密。Compose 里 `backend` 硬编码了 `COOKIE_SECURE=false`，正式启用 HTTPS 后要改成 `true`。

### 4.2 停机、备份与启动阶段自动迁移

上线时先停止 Codify 入口和调度，等待部署编排确认没有 `RUNNING/QUEUED` 任务，再备份 PostgreSQL。
随后直接启动新版 Codify：Scheduler 的 entrypoint 在启动阶段执行 `alembic upgrade head`，迁移成功后才报告 healthy，
NGINX 再依赖 Backend 与 Scheduler health 开放入口。正常上线不再单独运行 `migrate` 服务。

```bash
cd deploy
HARNESS_EXECUTION_MODE=v2_only docker compose --env-file .env.production up -d backend scheduler nginx
```

物理 schema 变更仍是 roll-forward-only；如果 Scheduler migration 失败，health 不会通过，NGINX 不会开放，
应保持维护状态并部署已评审的向前修复 revision。`migrate` 服务挂在 `maintenance` profile 下，仅保留给恢复/测试等明确场景，
调用时必须给出已评审的非 `head` revision：

```bash
cd deploy
MIGRATION_TARGET=<revision> docker compose --profile maintenance run --rm migrate
```

这个命令拒绝 `head`，也拒绝把数据库降级到当前 revision 之前。

### 4.3 构建并启动服务

在仓库根目录执行：

```bash
cd deploy
docker compose up -d --build backend scheduler nginx
```

启动后建议检查：

```bash
docker compose ps
docker compose logs --tail 100 backend
docker compose logs --tail 100 scheduler
docker compose logs --tail 100 nginx
```

### 4.4 健康检查

默认端口：

- 前端：`http://<host>:8880`
- 后端：`http://<host>:8000`
- Scheduler 健康接口：`http://<host>:8001`（由 `SCHEDULER_HEALTH_PORT` 决定）
- PostgreSQL：宿主机 `5432`

Backend 的 `/health` 会检查数据库和 Docker 连接，两项都通过才返回 200，任一项失败返回 503 并把失败项写进 `checks`；Compose 的 healthcheck 用 `curl -f`，所以 Docker socket 没挂好时 backend 会一直不健康，nginx 也就不会开放入口。Scheduler 的 `/health` 只回 `status` 和 `harness_execution_mode`。检查顺序如下：

```bash
curl -f http://<host>:8000/health
curl -f http://<host>:8001/health
deploy/scripts/preflight-execution-mode.sh http://<host>:8000/health http://<host>:8001/health
```

preflight 脚本比对两个进程上报的 `HARNESS_EXECUTION_MODE`，不一致或取不到值就以退出码 1 结束。全部通过后访问前端首页确认 Dashboard 可打开。

## 5. 上线后的初始化配置

### 5.1 OIDC 登录

建议在服务基础可用后，再通过 Dashboard 配置 OIDC：

1. 初次部署先保持 OIDC 关闭
2. 登录 Dashboard（如果已有入口）
3. 打开 `/configuration`
4. 填写 OIDC 参数
5. 使用内置测试与诊断页面验证
6. 验证通过后再启用 OIDC

详细步骤见 [GITLAB_OIDC_SETUP.md](GITLAB_OIDC_SETUP.md)。

### 5.2 Break-glass 紧急入口

如果生产环境启用了 break-glass：

- 三个环境变量一起配齐才生效：`AUTH_BREAK_GLASS_ENABLED=true`、`AUTH_BREAK_GLASS_USERNAME`、`AUTH_BREAK_GLASS_PASSWORD_HASH`，任一为空时 `break_glass_enabled` 判定为关闭
- `AUTH_BREAK_GLASS_PASSWORD_HASH` 支持 `sha256$<hex>` 与 `pbkdf2_sha256$<iterations>$<salt_hex>$<digest_hex>` 两种格式
- 仅在紧急恢复时开启，使用后尽快关闭
- 定期验证审计日志是否记录正常

这些值只从环境变量读取，不会写进 `system_config`，也不要提交到仓库。

## 6. 日常发布与重建

### 6.1 后端 / 调度器代码更新

当 `backend/`、调度逻辑或 API 变更时：

```bash
docker build -f deploy/Dockerfile.backend -t codify-backend:latest .
cd deploy && docker-compose up -d backend scheduler
```

说明：

- `backend` 与 `scheduler` 共用同一个镜像
- 如果只重启其中一个，容易出现代码版本不一致
- 仓库根目录的 `make rebuild-backend` 与 `make rebuild-scheduler` 做同样的事，并统一带上 `--env-file .env.test`

### 6.2 前端代码更新

当 `frontend/` 变更时：

```bash
cd frontend && npm run build
cd ../deploy && docker-compose build nginx && docker-compose up -d nginx
```

`make rebuild-nginx` 是同一动作的 Makefile 版本。nginx 容器里只有构建产物和 `deploy/nginx/default.conf`，改动代理规则同样要走这条重建路径。

### 6.3 Worker 镜像与 Worker Kit 更新

当 Worker 执行环境变更时，例如：

- `deploy/Dockerfile.worker-java21-maven`（Project Runtime Image 工具链）
- Worker 内依赖工具
- Harness CLI 版本或选择集（Worker Kit）

**Kit-owned 模型**：Project Runtime Image 只提供 Java 21 / Maven / Git 等项目工具链，不再携带或锁定任何 Harness CLI。
四个 Harness CLI（pi/opencode/claude/codex）由 **Worker Kit** 提供：Kit 是 content-addressed 归档，其身份是
归档内 `manifest.json` 字节的 SHA-256，归档名嵌入该前缀（前 12 位）。
Kit manifest 的 `harness_inventory` 记录四个 key（`pi/opencode/claude/codex`）的 `availability=present|absent`；
absent 时带 `reason_code`（`not_selected` 或 `missing_payload`）。

#### 构建 Project Runtime Image（仅工具链）

```bash
make worker-runtime-image-build \
  WORKER_KIT_PLATFORM=linux/amd64 \
  RUNTIME_IMAGE=codify-worker/java21-maven:<release>
```

#### 导出 Worker Kit（含 CLI 选择集）

Kit 构建入口是 `deploy/worker-kit/export.sh`（`make worker-kit-export`），通过环境变量指定选择集与版本：

```bash
make worker-kit-export \
  WORKER_KIT_VERSION=<kit-version> \
  WORKER_KIT_PLATFORM=linux/amd64 \
  WORKER_KIT_CLI_SELECTION=pi,opencode \
  WORKER_KIT_PI_CLI_VERSION=0.84.2 \
  WORKER_KIT_OPENCODE_CLI_VERSION=1.18.19
```

- `WORKER_KIT_CLI_SELECTION`：逗号/加号分隔的 `pi,opencode,claude,codex` 子集，默认 `pi,opencode`；
  未选中的 key 在 manifest 中记录为 `availability=absent, reason_code=not_selected`。
- `WORKER_KIT_<KEY>_CLI_VERSION`（可选）：每个 Harness 的精确版本构建参数（`<KEY>` 为 `PI/OPENCODE/CLAUDE/CODEX`）。
- 产物为 content-addressed 归档 `codify-worker-kit-<version>-linux-<arch>-<12位manifest sha256前缀>.tar.gz`
  及其 `.sha256` sidecar，写入 `WORKER_KIT_OUTPUT_DIR`（默认 `deploy/offline-bundle/kits/`）。

#### 安装 Worker Kit

在目标 Docker Host 上安装（`deploy/offline-bundle/scripts/install-worker-kit.sh`），安装到 `/opt/codify/worker-kits/`：

```bash
sudo ./scripts/install-worker-kit.sh kits/codify-worker-kit-<version>-linux-<arch>-<manifest-prefix>.tar.gz
```

安装先校验归档 `.sha256`、归档内路径、manifest SHA 与 canonical full-content inventory，再放置 Kit，
并拒绝覆盖已存在的 content-addressed 身份目录。安装器要求 root，并拒绝不具备 root 所有权
或对 group/others 可写的安装路径；落盘后的 Kit 与 receipt 均由 root 持有且不可被其他用户写入。

#### V2 release 预检

`deploy/scripts/preflight-v2-release.sh` 校验 Kit 归档与 Worker image 身份（不读取任何镜像内 CLI lock）：

```bash
export WORKER_KIT_ARCHIVE=/srv/codify/releases/<release>/codify-worker-kit-<version>-linux-<arch>-<manifest-prefix>.tar.gz
export V2_RELEASE_WORKER_IMAGE=codify-worker/java21-maven:<release>
deploy/scripts/preflight-v2-release.sh
```

预检验证：归档与其 `.sha256` 校验通过；`manifest.json` 的 `manifest_kind`（`codify.worker.kit-manifest/v1`）、
`kit_version`、`platform`（`linux/<arch>`）、`harness_inventory`（恰好四个 key；present 含以 `/opt/codify-kit/`
开头的 `path`/`version`/`sha256`/`size`，absent 含 `not_selected|missing_payload`）；归档名与 manifest SHA-256
前缀一致；`V2_RELEASE_WORKER_IMAGE` 在所选 Docker daemon 上存在，且其 image ID/Os/Architecture 与 manifest
platform 一致。通过时输出一行 `V2 release preflight OK: <kit version> <platform> <manifest sha256> content=<inventory sha256>`，失败退出码 2
并说明原因。`WORKER_KIT_ARCHIVE` 由本脚本在控制机读取；`V2_RELEASE_WORKER_IMAGE` 必须在所选 Docker daemon
上。远程 Docker 时，归档及其 sidecar 也必须存在于 daemon Host，供安装脚本使用。

完成 Kit 安装后，使用显式 Runtime manifest 验证四个 Harness：

```bash
make worker-kit-verify \
  KIT_PATH=/opt/codify/worker-kits/<version>-linux-<arch>-<manifest-prefix> \
  RUNTIME_IMAGE=codify-worker/java21-maven:<release> \
  RUNTIME_MANIFEST=/srv/codify/releases/<release>/frozen-runtime-manifest.v2.json \
  VERIFY_ALL_HARNESSES=1 \
  SMOKE='java -version && mvn -version'
```

`RUNTIME_MANIFEST` 必须是已写入 Adapter artifact SHA 的冻结
`codify.worker.runtime-manifest/v2` 文档，或数据库持久化且保留嵌套 Adapter identity 的
`codify.worker.runtime-bundle/v2` 文档；不能传入 Kit manifest、placeholder source template 或容器 Launcher 的
flat projection。此命令只是 L1/L2 source/image/Kit verification；随后仍需按 Profile 调用 API verify-runtime，并在真实
Docker Host 上完成最小 Task/MR smoke 后才有 L3/L4 证据。若 `WORKER_IMAGE` 使用其他 tag/digest，
必须同步更新 Profile 并重新验证。

## 7. 常见运维检查

### 7.1 查看服务日志

```bash
cd deploy
docker-compose logs -f backend
docker-compose logs -f scheduler
docker-compose logs -f nginx
docker-compose logs -f postgres
```

backend 与 scheduler 除了把日志写到 stderr，还会在容器内 `/app/logs/app_<date>.log` 留一份 JSON 行文件，保留 7 天，按天轮转。要单独看某个 Worker 的日志，用宿主机的 `docker logs codify-<task_id>-issue<issue_id>`，容器名里的前缀来自 `WORKER_CONTAINER_PREFIX`（默认 `codify`）。

### 7.2 查看数据库中的任务状态

```bash
docker exec codify-postgres psql -U codify -d codify -c \
  "SELECT id, status, error_message FROM tasks ORDER BY id DESC LIMIT 10;"
```

### 7.3 查看最近任务日志

```bash
docker exec codify-postgres psql -U codify -d codify -c \
  "SELECT task_id, log_level, message, created_at FROM task_logs ORDER BY id DESC LIMIT 20;"
```

### 7.4 检查 GitLab 回写结果

可以使用 GitLab API 查看 issue note / MR 内容是否已被正常更新。

## 8. 故障排查建议

### 8.1 Dashboard 打不开

优先检查：

- `nginx` 是否启动
- `backend` 是否健康，`curl -f http://localhost:8000/health` 的 `checks` 里 `database` 或 `docker` 是否报错
- `/var/run/docker.sock` 是否正确挂进 backend 容器
- 浏览器访问的 URL 是否指向前端端口 `8880`

### 8.2 任务创建成功但不执行

优先检查：

- `scheduler` 是否运行
- `MAX_CONCURRENCY` 是否被设得太低
- 数据库中任务是否停留在 `PENDING` / `QUEUED`
- 是否存在同一 Issue 的互斥任务
- 是否配置了 `scheduled_at`

### 8.3 OIDC 配置突然失效

优先检查：

- `system_config` 是否仍有数据
- PostgreSQL volume 是否被重建
- `CONFIG_ENCRYPTION_KEY` 是否变化
- OIDC Client Secret 是否仍可正确解密

### 8.4 任务执行失败但前端日志不完整

优先检查：

- Task detail 页面是否拿到了实时日志
- `backend` / `scheduler` 日志里是否有异常
- Worker 容器是否被提前退出

如果是 E2E 或真实 GitLab 集成问题，参见 [E2E_TESTS.md](../dev/E2E_TESTS.md)。

## 9. 升级与回滚建议

升级前先确认三件事：

- 数据库里没有旧的 `worker_workspace_host_path` 覆盖值。启动时会拿它和 `WORKER_WORKSPACE_HOST_PATH` 比对，两者不一致就直接抛错退出，此时先把环境变量改成库里的值，或在升级前删掉那条 `system_config` 记录
- 没有 `RUNNING`/`QUEUED` 任务，按第 3 节的命令导出过数据库
- 上一版的 `codify-backend:latest` 和 Worker 镜像标签还在本地

升级后优先验证：

- Backend 与 Scheduler 的 `/health`，以及 `deploy/scripts/preflight-execution-mode.sh`
- Dashboard 可访问
- 手动创建任务
- 一条真实或测试任务可执行

如果需要回滚：

1. 重新给旧镜像打上 `codify-backend:latest` 并重建 `backend`、`scheduler`，必要时重建 `nginx`
2. 回到旧的 `WORKER_IMAGE` 标签，Profile 里的 runtime image 也要同步改回
3. 迁移只向前走。已经跑过的新 revision 不会因为换回旧镜像而回退，schema 与旧代码之间的兼容性要在升级前确认；真要回到旧 schema，只能用备份恢复

## 10. 生产环境操作红线

请避免以下高风险操作：

- 在生产环境跑带破坏性清理的 E2E 脚本
- 执行 `docker-compose down -v`
- 未备份就重置 PostgreSQL volume
- 未记录密钥就轮换 `SESSION_SECRET` / `CONFIG_ENCRYPTION_KEY`（轮换 `SESSION_SECRET` 会让现存会话失效，轮换 `CONFIG_ENCRYPTION_KEY` 会让已落库的密钥类配置无法解密）
- 在未验证 Worker 镜像的情况下直接替换正式环境

### 10.1 导出 DB 绑定的 V2 Runtime Bundle（L3 证据）

只可从一个已验证的 V2 Task 或一个已知 bundle digest 导出；命令不读取当前 checkout、不会重新构建
Bundle，也不会通过 HTTP 获取内容。基础 Compose 将宿主机 `/opt/codify-archives` bind 到 backend
容器的同一路径，因此 `BUNDLE_EXPORT_DIR` 必须使用容器内的持久目录
`/opt/codify-archives/runtime-bundles`，不能写入容器层或使用控制机路径：

```bash
make worker-runtime-bundle-export TASK_ID=123 BUNDLE_EXPORT_DIR=/opt/codify-archives/runtime-bundles
```

导出结果固定为 `/opt/codify-archives/runtime-bundles/runtime-bundle-v2-<bundle-digest>/`，包含数据库中原始 tar 字节、规范化的
数据库 manifest 和各自 SHA-256 sidecar。目标已经存在、manifest/归档出现 secret 形态、或 Bundle 与
冻结的 V2 identity/evidence/platform 不一致时都会拒绝，不能覆盖或“清洗后继续”。一个 Bundle 仅证明
该 Task 选中的 Harness；四个 Harness 的 L3 证据必须来自四个分别验证通过的 Task。L3 是制品/绑定证据，
不是 Host 上的完整执行与 MR 验收（L4）。

## 11. 相关文档

- [文档索引](../README.md)
- [项目总览 README](../../README.md)
- [中文文档索引](../README.zh-CN.md)
- [配置参考](CONFIGURATION.md)
- [GITLAB_OIDC_SETUP.md](GITLAB_OIDC_SETUP.md)
- [日志追踪方案](LOGGING.md)
- [内网离线迁移实施方案](OFFLINE-DEV.md)
- [Multi-Harness 切换与生产验收 Runbook](runbooks/multi-harness-rollout.md)
- [E2E_TESTS.md](../dev/E2E_TESTS.md)
