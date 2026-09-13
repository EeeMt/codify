# 配置参考

部署期环境变量、运行期覆盖方式与常用运维命令。产品使用说明见应用内「指南」页（源文件 `frontend/src/guide/`），部署流程见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 部署期环境变量

在 `deploy/.env` 或 Docker Compose 环境变量中配置：

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `GITLAB_URL` | GitLab 实例地址 | `https://gitlab.example.com` |
| `GITLAB_BOT_TOKEN` | Bot 账号 PAT（`api` 权限） | `glpat-xxxx` |
| `ANTHROPIC_BASE_URL` | 默认 AI Provider（Claude）端点 | `https://api.anthropic.com` |
| `ANTHROPIC_API_KEY` | 默认 AI Provider（Claude）密钥 | `sk-ant-xxxx` |
| `ANTHROPIC_MODEL` | 默认模型（多 Provider 场景以 Dashboard 配置为准） | `claude-sonnet-4-20250514` |
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://...` |
| `DOCKER_HOST` | Docker 引擎地址 | `tcp://localhost:2376` |
| `WORKER_IMAGE` | Worker 容器镜像 | `codify-worker/java21-maven:2026.07` |
| `MAX_CONCURRENCY` | 最大并发 Worker 数 | `3` |
| `TASK_TIMEOUT_PEAK_SECONDS` | 高峰任务超时秒数 | `1800` |
| `TASK_TIMEOUT_OFF_PEAK_SECONDS` | 低峰任务超时秒数 | `3600` |
| `TASK_TIMEOUT_PEAK_START` | 高峰开始时间（Asia/Shanghai） | `09:00` |
| `TASK_TIMEOUT_PEAK_END` | 高峰结束时间（Asia/Shanghai） | `18:00` |
| `DEFAULT_TARGET_BRANCH` | 默认 MR 目标分支 | `main` |
| `CONFIG_ENCRYPTION_KEY` | 配置加密密钥（32 字节 base64） | — |
| `AUTO_MIGRATE` | 仅一次性 migration owner 可设为 `true`；长驻服务必须关闭 | `false` |
| `HARNESS_EXECUTION_MODE` | Harness 执行策略，当前只接受 `v2_only`，通常无需设置 | `v2_only` |

> 运行时配置（并发数、超时、Max Turns、AI Provider 等）也可以通过 Dashboard 配置页面动态修改，无需重启服务。两层设置的关系见 `backend/app/config.py` 的 `get_settings()` 与 `get_effective_settings()`：后者在环境变量之上叠加 `system_config` 表中持久化的覆盖值。

密钥类配置（`gitlab_bot_token`、`anthropic_api_key` 等）在写入 `system_config` 前加密存储。

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

## 运维备忘

- `deploy/docker-compose.yml` 中，`backend` 和 `scheduler` 共用同一个 backend 镜像
- 默认 Compose 中，Backend 使用 `AUTO_MIGRATE=false`，Scheduler 使用 `AUTO_MIGRATE=true` 作为唯一启动阶段 migration owner；NGINX 等待 Scheduler healthy 后开放入口
- Backend/Scheduler 的执行策略默认 `v2_only`（`dual_canary` 已随硬切删除），无需显式设置
- 配置页面路由为 `/configuration`
- 认证用户能看到的项目和任务会按 GitLab 权限过滤

## 相关文档

- [部署指南](DEPLOYMENT.md)
- [GitLab OIDC 登录配置](GITLAB_OIDC_SETUP.md)
- [日志追踪方案](LOGGING.md)
- [内网离线迁移实施方案](OFFLINE-DEV.md)
