# 开发环境搭建指南

本文档面向本地开发者，介绍如何搭建 Codify 的后端、前端和测试环境，并说明推荐的开发流程。

## 1. 你会开发到哪些部分

当前仓库主要由三部分组成：

- `backend/`：FastAPI + SQLAlchemy + 调度与任务执行逻辑
- `frontend/`：Vue 3 + Vite + Naive UI 的管理后台
- `deploy/`：Docker Compose 与生产/集成部署相关文件

日常开发通常分两类：

- 本地开发后端 / 前端，快速迭代
- 通过 Docker 或远程 Docker 环境验证完整链路

## 2. 前置条件

建议本地具备以下工具：

- Python 3.11 或兼容版本
- Node.js 18+ 与 npm
- Docker 与 Docker Compose
- PostgreSQL（本地安装，或通过 Docker 提供）
- 可访问的 GitLab 测试环境
- 可访问的 Harness 兼容模型服务（Claude/Codex）

如果你要跑真实 GitLab E2E，还需要：

- 独立测试项目
- 独立测试 Token
- 不会影响正式环境的数据隔离

## 3. 获取代码

```bash
git clone <your-repo-url>
cd codify
```

## 4. 后端开发环境

### 4.1 安装 Python 依赖

```bash
cd backend
pip install -r requirements.txt
```

如果你使用虚拟环境，建议先创建并激活虚拟环境再安装。

### 4.2 准备环境变量

从模板复制：

```bash
cp .env.example .env
```

然后按本地环境修改关键项：

#### GitLab

- `GITLAB_URL`
- `GITLAB_BOT_TOKEN`

#### 模型服务

- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`

#### 数据库

- `DATABASE_URL`

注意：

- `.env.example` 中的数据库地址默认面向 Docker 网络里的 `postgres`
- 如果你是在宿主机直接运行后端，需要把 `DATABASE_URL` 改成你本机可访问的 PostgreSQL 地址

#### 应用配置

- `SESSION_SECRET`
- `CONFIG_ENCRYPTION_KEY`
- `WORKER_IMAGE`
- `MAX_CONCURRENCY`
- `TASK_TIMEOUT_PEAK_SECONDS`
- `TASK_TIMEOUT_OFF_PEAK_SECONDS`
- `TASK_TIMEOUT_PEAK_START`
- `TASK_TIMEOUT_PEAK_END`
- `DEFAULT_TARGET_BRANCH`

`backend/.env.example` 已带上述键与示例值，默认值和取值范围见 `backend/app/config.py`；高峰窗口按 `Asia/Shanghai` 判定。

### 4.3 准备 PostgreSQL

你可以任选一种方式：

#### 方式 A：本机已有 PostgreSQL

手动创建数据库并把 `DATABASE_URL` 指向本机数据库。

#### 方式 B：用 Docker 起一个 PostgreSQL

最简单的方式是用项目里的 compose 起 `postgres` 服务（容器名 `codify-postgres`）：

```bash
cd ../deploy
docker-compose --env-file .env.test up -d postgres   # 只起数据库
docker-compose --env-file .env.test up -d            # 起整套
```

compose 把数据库端口映射到宿主机 `5432`，所以在这种方式下 `DATABASE_URL` 用 `localhost` 或 `127.0.0.1` 都能连上。

然后在 `backend/.env` 中把 `DATABASE_URL` 指向与当前运行方式匹配的地址。

如果后端也跑在宿主机上，通常不能直接使用 `postgres:5432` 这个容器内主机名，需改成宿主机可访问地址。

### 4.4 执行数据库迁移

Backend 固定不自动迁移（`AUTO_MIGRATE=false`），Scheduler 是启动阶段唯一的 migration owner
（`AUTO_MIGRATE=true`）。启动新版服务时由 Scheduler 自动执行 Alembic，NGINX 等待 Scheduler
healthy 后再开放入口，不需要先手工运行 migration。

只有恢复/测试等明确场景才使用 maintenance profile 里的 `migrate` 服务，它跑完即退出：

```bash
cd deploy
MIGRATION_TARGET=<revision> docker compose --profile maintenance run --rm migrate
```

> 项目使用 Alembic 进行数据库迁移，迁移脚本位于 `backend/alembic/versions/`。

### 4.5 本地启动后端

```bash
uvicorn app.main:app --reload   # HARNESS_EXECUTION_MODE 默认 v2_only，无需设置
```

默认后端地址通常是：

- `http://localhost:8000`

## 5. 前端开发环境

### 5.1 安装依赖

```bash
cd frontend
npm install
```

### 5.2 启动开发服务器

```bash
npm run dev
```

开发服务器监听 `http://localhost:5173`，`server.port` 定义在 `frontend/vite.config.ts`。

同一个文件把 `/api` 代理到 `http://192.168.50.129:8000`。后端跑在本机时，把 `server.proxy` 里 `/api` 的 `target` 改成 `http://localhost:8000`，否则页面里的接口请求会发到那台远端机器。

### 5.3 前端构建校验

前端改动完成后，推荐执行：

```bash
npm run build
```

这也是当前仓库里最直接的前端类型/构建校验方式。

## 6. 推荐本地开发组合

### 方案 A：前后端都本地运行

适合前端页面与后端 API 联调。

推荐组合：

- PostgreSQL：本地或 Docker
- backend：宿主机 `uvicorn --reload`
- frontend：宿主机 `npm run dev`

优点：

- 改动反馈最快
- 日志查看最直接
- 调试工具最方便

### 方案 B：前端本地，后端使用远端或 Docker 环境

适合你只改前端、希望直接对接现有测试后端。

注意确认前端 API 指向和跨域设置是否匹配当前环境。

### 方案 C：用 compose 验证接近生产的运行方式

适合验证部署问题、容器行为和调度问题：

```bash
make up     # 等价于 cd deploy && docker-compose --env-file .env.test up -d --build
make logs
```

这个方案更接近生产，但迭代速度比本地直接跑慢。

## 7. 常用开发命令

### 7.1 Makefile 一键命令

仓库根目录的 `Makefile` 把常用动作包成了目标，`make help` 会列出全部：

```bash
make setup        # 安装后端 venv 与前端 npm 依赖
make up           # 起开发环境（docker-compose --env-file .env.test up -d --build）
make logs         # 跟随开发环境日志
make down         # 停开发环境
make ps           # 查看容器状态
make test-unit    # 后端 + 前端 + mock E2E 单元测试
make lint         # Ruff 检查
```

`make test-backend` 这类目标直接调 `backend/.venv/bin/python`，不需要先激活虚拟环境。

### 7.2 后端

```bash
# 安装依赖
cd backend && pip install -r requirements.txt

# 本地运行
cd backend && uvicorn app.main:app --reload

# 手动迁移
cd backend && alembic upgrade head
```

### 7.3 前端

```bash
cd frontend && npm install
cd frontend && npm run dev
cd frontend && npm run build
```

### 7.4 Docker / 部署验证

```bash
make up                  # 起开发环境
make logs                # 跟随日志
make rebuild-backend     # 只重建并重启 backend
make rebuild-scheduler   # 只重建并重启 scheduler
```

## 8. 测试

详细测试指南请参阅：[TESTING.md](TESTING.md)

### 快速参考

| 测试类型 | 命令 |
|---------|------|
| 后端单元测试 | `make test-backend` 或 `cd backend && python -m pytest tests/unit/ -v` |
| 前端单元测试 | `make test-frontend` 或 `cd frontend && npx vitest run` |
| Mock E2E | `make test-mock-e2e` 或 `cd backend && python -m pytest tests/mock_e2e/ -v` |
| Mock 集成测试（Docker） | `make test-mock-integration` |
| Playwright E2E（Docker） | `make test-e2e-ui` |
| GitLab E2E（Docker） | `make test-e2e-gitlab` |
| 全部测试 | `make test-all` |

### 前端验证

```bash
cd frontend && npm run build
```

### 安全注意事项

> **警告**：真实 GitLab E2E 测试只应该跑在隔离测试环境。

- 测试可能创建任务、分支、MR、Issue 评论
- 不要对着正式环境运行
- 确保测试环境有适当的清理机制

## 9. 本地开发常见问题

### 9.1 后端启动时报数据库连接失败

先确认：

- PostgreSQL 是否真的已启动
- `DATABASE_URL` 是否指向当前运行方式下可访问的地址
- 你是否误用了 Docker 内部主机名 `postgres`

### 9.2 前端页面打开了，但接口全 401 或无数据

先确认：

- 当前环境是否启用了 OIDC
- 你是否已经登录
- 后端 `/api/auth/me` 返回的 `oidc_enabled` 和 `authenticated` 是否符合预期

### 9.3 任务能创建，但 Worker 起不来

先确认：

- `DOCKER_HOST` 是否可用
- `WORKER_IMAGE` 是否存在
- 当前运行方式能否访问 Docker Engine

### 9.4 OIDC UI 元素突然消失

先确认：

- 数据库里的 `system_config` 是否还在
- OIDC 配置是否因数据库重置而丢失
- `/api/config` 与 `/api/auth/me` 返回值是否正常

## 10. 推荐开发流程

比较稳妥的日常流程如下：

1. 拉取最新代码
2. 本地修改后端或前端
3. 先跑与你改动最相关的测试
4. 前端改动至少执行一次 `cd frontend && npm run build`
5. 后端行为改动至少跑对应单元测试 / E2E
6. 需要接近生产验证时，再用 compose 或远程 Docker 环境复测

## 11. 相关文档

- [文档索引](../README.md)
- [项目总览 README](../../README.md)
- [中文文档索引](../README.zh-CN.md)
- [DEPLOYMENT.md](../ops/DEPLOYMENT.md)
- [GITLAB_OIDC_SETUP.md](../ops/GITLAB_OIDC_SETUP.md)
- [TESTING.md](TESTING.md)
- [E2E_TESTS.md](E2E_TESTS.md)
