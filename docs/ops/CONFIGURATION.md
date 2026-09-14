# 配置参考

部署期环境变量、运行期覆盖方式与常用运维命令。产品使用说明见应用内「指南」页（源文件 `frontend/src/guide/`），部署流程见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 部署期环境变量

`deploy/docker-compose.yml` 通过 `env_file: .env.test` 注入这些变量。模板见 `deploy/.env.example`，正式环境按它生成自己的文件后把 `env_file` 指过去，也可以直接写进 Compose 的 `environment` 段：

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `GITLAB_URL` | GitLab 实例地址 | `https://gitlab.example.com` |
| `GITLAB_BOT_TOKEN` | Bot 账号 PAT（`api` 权限） | `glpat-xxxx` |
| `ANTHROPIC_BASE_URL` | 默认 AI Provider（Claude）端点 | 代码默认 `http://localhost:11434/v1`；`deploy/.env.example` 用 `https://api.anthropic.com` |
| `ANTHROPIC_API_KEY` | 默认 AI Provider（Claude）密钥 | `sk-ant-xxxx` |
| `ANTHROPIC_MODEL` | 默认模型（多 Provider 场景以 Dashboard 配置为准） | `claude-sonnet-4-20250514` |
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://...` |
| `DOCKER_HOST` | Docker 引擎地址；Compose 内为 `unix:///var/run/docker.sock` | `tcp://localhost:2376` |
| `WORKER_IMAGE` | Worker 容器镜像 | `codify-worker/java21-maven:2026.07` |
| `WORKER_WORKSPACE_HOST_PATH` | 宿主机上的 Issue 工作区根目录，backend、scheduler 与派生的 Worker 容器共用同一路径 | `/opt/codify-workspaces` |
| `MAX_CONCURRENCY` | 最大并发 Worker 数 | `3` |
| `SCHEDULER_INTERVAL` | 调度轮询间隔（秒） | `5` |
| `SCHEDULER_HEALTH_PORT` | Scheduler `/health` 监听的端口，同时也是 Compose 映射到宿主机的端口；进程始终监听，设 `0` 只会让 uvicorn 绑定一个临时端口 | `8001` |
| `TASK_TIMEOUT_PEAK_SECONDS` | 高峰任务超时秒数 | `1800` |
| `TASK_TIMEOUT_OFF_PEAK_SECONDS` | 低峰任务超时秒数 | `3600` |
| `TASK_TIMEOUT_PEAK_START` | 高峰开始时间（Asia/Shanghai） | `09:00` |
| `TASK_TIMEOUT_PEAK_END` | 高峰结束时间（Asia/Shanghai） | `18:00` |
| `DEFAULT_TARGET_BRANCH` | 默认 MR 目标分支 | `main` |
| `SESSION_SECRET` | 会话令牌签名密钥，与 `CONFIG_ENCRYPTION_KEY` 互相独立 | 随机字符串 |
| `CONFIG_ENCRYPTION_KEY` | 敏感配置加密密钥。留空时回退到 `SESSION_SECRET`，两者都停留在默认值时读写加密配置会报错 | 随机字符串 |
| `COOKIE_SECURE` | 会话 Cookie 是否只在 HTTPS 下发送；走 8880 的 HTTP 入口时需设为 `false` | `true` |
| `FRONTEND_URL` | Dashboard 外链地址，任务链接使用它；留空回退到 `BACKEND_URL` | `http://<host>:8880` |
| `BACKEND_URL` | Webhook 回调与默认外链地址 | `http://<host>:8000` |
| `LOG_LEVEL` | 日志级别，控制台与文件输出共用 | `INFO` |
| `CUSTOM_CA_BUNDLE` | 容器内自定义 CA 证书路径；Compose 把宿主机 `/opt/ca.crt` 挂到这里 | `/etc/ssl/certs/custom-ca.crt` |
| `WORKER_CA_CERT_HOST_PATH` | 宿主机 CA 证书绝对路径，Scheduler 会把它挂进每个 Worker 容器 | `/opt/ca.crt` |
| `AUTO_MIGRATE` | 启动期迁移开关，默认 `false`。默认 Compose 里只有 `scheduler` 设为 `true`，`backend` 保持关闭；同一时刻只应有一个进程打开 | `false` |
| `HARNESS_EXECUTION_MODE` | Harness 执行策略，当前只接受 `v2_only`，通常无需设置 | `v2_only` |

> 运行时配置（并发数、超时、Max Turns、AI Provider 等）也可以通过 Dashboard 配置页面动态修改，无需重启服务。两层设置的关系见 `backend/app/config.py` 的 `get_settings()` 与 `get_effective_settings()`：后者在环境变量之上叠加 `system_config` 表中持久化的覆盖值，同一个键两边都有值时以数据库为准；数据库没有覆盖的键才使用环境变量或代码默认值。`system_config` 里的键名是设置字段名的小写下划线形式，例如 `max_concurrency`、`anthropic_model`。

加密存储只作用于 `system_config` 的这几类值：`gitlab_bot_token`、`gitlab_admin_token`、`anthropic_api_key`、`oidc_client_secret`、`mattermost_bot_token`、`alert_webhook_url`。它们以 Fernet 密文落库，密钥来自 `CONFIG_ENCRYPTION_KEY`，未配置时回退到 `SESSION_SECRET`。

## 常用命令

运行 `make help` 查看所有可用命令。

### 后端

```bash
cd backend && pip install -r requirements.txt
cd backend && uvicorn app.main:app --reload
cd backend && alembic upgrade head
cd backend && pytest
```

### 前端

```bash
cd frontend && npm install
cd frontend && npm run dev
cd frontend && npm run build
```

### 重建部署镜像

```bash
# backend / scheduler
docker build -f deploy/Dockerfile.backend -t codify-backend:latest .
cd deploy && docker-compose up -d backend scheduler

# frontend / nginx
docker build -f deploy/Dockerfile.frontend -t codify-nginx:latest .
cd deploy && docker-compose up -d --build nginx

# worker
docker build -f deploy/Dockerfile.worker-java21-maven -t codify-worker/java21-maven:2026.07 .
```

同样的动作在仓库根目录有对应的 Makefile 目标，它们统一带上 `--env-file .env.test`：

```bash
make rebuild-backend      # 重建 backend 镜像并重启 backend 容器
make rebuild-scheduler    # 重建 scheduler 镜像并重启 scheduler 容器
make rebuild-nginx        # 重建 nginx 镜像并重启 nginx 容器
make up                   # 启动整套 Compose
make down                 # 停止整套 Compose
make logs                 # 跟随日志
make ps                   # 查看容器状态
make worker-runtime-image-build RUNTIME_IMAGE=codify-worker/java21-maven:<release>
```

## 运维备忘

- `deploy/docker-compose.yml` 中，`backend` 和 `scheduler` 共用 `codify-backend:latest` 镜像；只重启其中一个会让两者跑在不同代码版本上，应一起重建
- 默认 Compose 中 Backend 使用 `AUTO_MIGRATE=false`，Scheduler 使用 `AUTO_MIGRATE=true` 作为唯一启动阶段 migration owner；Scheduler 的 entrypoint 先执行 `alembic upgrade head`，迁移失败时容器不会就绪，NGINX 依赖 Backend 与 Scheduler 的 healthy 状态才开放入口
- 需要单独迁移时用 `maintenance` profile 的一次性 `migrate` 服务，且必须给出已评审的非 `head` revision：
  `cd deploy && MIGRATION_TARGET=<revision> docker compose --profile maintenance run --rm migrate`。该命令拒绝 `head`，也拒绝回退到数据库当前 revision 之前
- 宿主机上 `/opt/ca.crt` 必须作为文件存在，Compose 里这条 bind 设了 `create_host_path: false`，缺失时 `docker compose up` 直接失败；`/opt/codify-archives`、`/opt/codify-ci-failures`、`/opt/codify-docker-certs`、`/opt/codify-workspaces` 不存在时 Docker 会创建空目录，可用 `CI_FAILURE_BUNDLE_HOST_PATH`、`DOCKER_CERTS_HOST_PATH`、`WORKER_WORKSPACE_HOST_PATH` 改路径
- 默认 Compose 把 `COOKIE_SECURE` 设为 `false`，因为入口是 8880 上的 HTTP；前置 HTTPS 之后应设回 `true`
- Backend/Scheduler 的执行策略默认 `v2_only`（`dual_canary` 已随硬切删除），无需显式设置
- 配置页面路由为 `/configuration`
- 认证用户能看到的项目和任务会按 GitLab 权限过滤

## 相关文档

- [部署指南](DEPLOYMENT.md)
- [GitLab OIDC 登录配置](GITLAB_OIDC_SETUP.md)
- [日志追踪方案](LOGGING.md)
- [内网离线迁移实施方案](OFFLINE-DEV.md)
