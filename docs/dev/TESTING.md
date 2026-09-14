# 测试指南

本文档介绍项目中所有类型测试的运行方法。

## 快速开始

所有测试命令统一通过 `make` 运行：

```bash
# 查看所有可用测试命令
make help

# 单元测试（后端 + 前端 + mock E2E）
make test-unit

# 全部测试（单元 + mock 集成 + Playwright E2E + GitLab E2E）
make test-all

# mock 集成改回单栈串行
make test-all MOCK_INT_MODE=serial
```

`make test-unit`、`make test-all` 会依赖 `backend/.venv` 与 `frontend/node_modules` 两个安装哨兵文件，首次运行会先装依赖。

> 直接执行 `cd backend && python -m pytest` 只收集三个套件：`tests/unit`、`tests/mock_integration`、`tests/mock_e2e`（见 `backend/pyproject.toml` 的 `testpaths`）。Playwright E2E 与 GitLab E2E 被 `norecursedirs` 和 `addopts` 排除，它们各自需要 `backend/tests/e2e/pytest.ini`、`backend/tests/e2e/requirements-e2e.txt` 和 Docker 环境。

## 测试类型概览

| 类型 | 命令 | 依赖 |
|------|------|------|
| 后端单元测试 | `make test-backend` | Python |
| 前端单元测试 | `make test-frontend` | Node.js |
| Mock E2E | `make test-mock-e2e` | Python |
| Mock 集成测试 | `make test-mock-integration` | Docker |
| Playwright E2E | `make test-e2e-ui` | Docker |
| GitLab E2E | `make test-e2e-gitlab` | Docker + 真实 GitLab |
| 全部 E2E | `make test-e2e` | Docker（含 GitLab） |

---

## 1. 后端单元测试

### 运行命令

```bash
make test-backend
```

或直接使用 pytest：

```bash
cd backend
source .venv/bin/activate  # Linux/Mac
python -m pytest tests/unit/ -v

# 运行特定测试文件
python -m pytest tests/unit/test_auth_session.py -v

# 运行特定测试类
python -m pytest tests/unit/test_auth_session.py::AuthSessionTests -v

# 运行特定测试方法
python -m pytest tests/unit/test_auth_session.py::AuthSessionTests::test_hash_session_token_is_deterministic -v
```

### 特点
- 使用 `pytest` + `asyncio_mode = "auto"`（`backend/pyproject.toml`），依赖在 `backend/requirements-test.txt`
- `tests/unit` 当前收集 3578 个测试，可用 `cd backend && .venv/bin/python -m pytest tests/unit/ --collect-only -q | tail -1` 复核
- `make test-backend` 用 `-n auto --dist=loadgroup` 并行；`tests/unit/conftest.py` 把两个共用 `codify_test` 库的文件（`test_issue_execution_lock_concurrency`、`test_system_lifecycle_statistics_pg`）归到同一个 xdist group，其余按文件分组
- 需要真实 PostgreSQL 的用例（`test_0XX_migration.py`、`test_task_harness_commands.py` 等）默认连
  `postgresql+asyncpg://codify:codify_password@192.168.50.129:5432/codify_test`，可用 `CODIFY_TEST_DATABASE_URL` 覆盖；
  数据库不可达时这些用例 `pytest.skip`，不会让整轮变红
- 迁移脚本本身的往返验证（`upgrade head` → `downgrade 062_task_skills` → `upgrade head`）由
  `scripts/test-harness-migration.sh` 完成，它要求 `CODIFY_MIGRATION_TEST_DATABASE_URL` 指向本机 testing 库：

  ```bash
  CODIFY_MIGRATION_TEST_DATABASE_URL=postgresql+asyncpg://codify:codify_password@localhost:5432/codify_test \
    ./scripts/test-harness-migration.sh
  ```

---

## 2. 前端单元测试

### 运行命令

```bash
make test-frontend
```

或直接使用 vitest：

```bash
cd frontend
npx vitest run
npx vitest run --coverage

# 跑单个文件
npx vitest run src/guide/guideContent.spec.ts

# watch 模式
npx vitest
```

### 特点
- 使用 Vitest + Vue Test Utils，环境为 jsdom（`frontend/vitest.config.ts`）
- 用例范围是 `src/**/*.{test,spec}.{js,ts}`，与组件同目录
- `frontend/src/test/setup.ts` 提供 localStorage、`matchMedia`、`ResizeObserver`、`getBoundingClientRect`、`scrollIntoView` 的打桩，jsdom 没有布局能力
- `--coverage` 用 v8 provider，产物在 `frontend/coverage/`

---

## 3. Mock E2E 测试

### 运行命令

```bash
make test-mock-e2e

# 串行调试单个文件
cd backend && python -m pytest tests/mock_e2e/test_tasks_e2e.py -v
```

### 特点
- 不需要 Docker 或外部服务，GitLab API 用 mock 模拟
- 8 个文件、380 个用例，覆盖任务、配置、统计、认证、Prompt 模板、slot capacity、Mattermost 通知
- 全部文件共用内存 SQLite：schema 每个 worker 会话创建一次，每个用例结束后清空数据，fixture 定义在 `tests/mock_e2e/conftest.py`
- `make test-mock-e2e` 用 `-n auto --dist=loadfile` 按文件并行

---

## 4. Mock 集成测试

Mock 集成测试用 Mock 服务替代外部依赖（GitLab API、Claude CLI），但保留真实 Docker 容器、真实 worker entrypoint（`deploy/entrypoint.worker.sh` 与 `deploy/worker-entrypoint/`）和真实业务逻辑。

### 架构

```
pytest (本机) → HTTP → codify-backend (Docker)
                      → codify-scheduler (Docker)
                      → mock-services (Docker): Mock GitLab API + Git HTTP + Anthropic API
                      → codify-worker-test (Docker): 真实 entrypoint + fake claude-run.sh
                      → postgres (Docker)
```

### 运行命令

```bash
make test-mock-integration                 # 单栈串行：构建镜像 + 启动 + 跑完 + 拆栈
make test-mock-integration-parallel        # 三栈并行（Makefile 注释标注约 8 分钟）
make test-mock-integration-up              # 只构建并启动
make test-mock-integration-logs            # 跟随环境日志
make test-mock-integration-down            # 停止环境并删除卷

# 环境已启动时手动跑
cd backend && pytest tests/mock_integration/ -v
cd backend && pytest tests/mock_integration/test_happy_path.py -v
```

`make` 目标通过 `scripts/run-mock-stack.sh` 启动单栈：脚本会 build/up `postgres mock-services backend scheduler`，把宿主机的 `backend/tests` 拷进容器，然后用容器内的 pytest 跑用例（`-k "not TestCrashRecovery"`）。`TestCrashRecovery` 的两个用例默认不跑，需要时手工在容器里执行 `docker exec <project>-backend-1 python -m pytest tests/mock_integration/test_advanced.py::TestCrashRecovery -v`。

`test-mock-integration-parallel` 把用例拆成三组（`MOCK_GROUP_A/B/C`，79/80/89 个），各自跑一个栈：

| 栈 | compose project | 网络 | worker 前缀 | mock 端口 | backend 端口 |
|----|-----------------|------|-------------|-----------|--------------|
| A | `mock_a` | `codify-mock-test-a` | `mocka` | 19000 | 18000 |
| B | `mock_b` | `codify-mock-test-b` | `mockb` | 19001 | 18001 |
| C | `mock_c` | `codify-mock-test-c` | `mockc` | 19002 | 18002 |

单栈脚本的工作目录默认放在 `/tmp/<project>-workspaces-$$`，退出时清理；需要保留时设 `MOCK_WORKSPACE_HOST_PATH`。

### 测试文件概览（23 文件，248 个测试）

| 文件 | 测试数 | 覆盖范围 |
|------|--------|----------|
| test_remaining_endpoints.py | 25 | stats、config reset、缓存失效、容器日志轮询等剩余端点 |
| test_health_access_sse.py | 25 | 健康检查、鉴权拦截、SSE 日志流 |
| test_notifications_and_operations.py | 17 | 通知配置 CRUD、slot capacity、reschedule 与 execute-now |
| test_mutex_and_scheduling.py | 15 | issue 互斥、调度、分支校验、任务优先级 |
| test_system_apis.py | 14 | 统计、分析、配置、认证、项目列表 |
| test_failure_injection.py | 13 | 故障注入：项目 404、git clone 失败、退出码、组合故障 |
| test_admin_and_templates.py | 13 | Prompt 模板 CRUD、用户与角色管理、会话 |
| test_validation_and_dedup.py | 12 | 任务生命周期校验、列表排序、创建边界 |
| test_security_and_resilience.py | 12 | 日志脱敏、互斥强约束、状态机、压力场景 |
| test_entrypoint_paths.py | 12 | MR 描述更新、复用已有 MR、事件投影、日志脱敏 |
| test_entrypoint.py | 12 | MR 描述、CODIFY markers、Claude 输出归一化、no-MR 模式 |
| test_edge_cases_advanced.py | 12 | 容器超时、用量统计、重试、自定义文件改动 |
| test_api_endpoints.py | 12 | 任务分页、scheduled、slot-capacity、日志流端点 |
| test_mr_followup_and_env.py | 11 | 同 issue 的 MR follow-up、容器环境变量、并发重试 |
| test_webhook_and_lifecycle.py | 7 | runtime config、任务状态迁移、登出 |
| test_gap_analysis.py | 7 | 无改动时的 MR/no-MR 行为、MR 创建失败、正向并发 |
| test_edge_cases.py | 6 | git push 失败、MR 更新失败、评论失败、token 用量 |
| test_advanced.py | 6 | base branch、调度延迟、issue 互斥、崩溃恢复 |
| test_happy_path.py | 4 | issue → task → scheduler → worker → completed 主流程 |
| test_coverage_gaps.py | 4 | 状态过滤、特殊字符 prompt、任务指标、损坏 marker |
| test_additional.py | 4 | 容器超时、execute-now、项目查找失败、reschedule |
| test_failure_paths.py | 3 | 容器失败、取消、重试 |
| test_scheduling.py | 2 | 优先级顺序、MAX_CONCURRENCY 限制 |

### 关键配置

`backend/tests/mock_integration/docker-compose.mock-test.yml` 给 backend 与 scheduler 注入：

| 配置项 | 值 |
|--------|-----|
| WORKER_NETWORK | codify-mock-test |
| MAX_CONCURRENCY | 5 |
| SCHEDULER_INTERVAL | 1 |
| WORKER_SKIP_IMAGE_PULL | true |
| TASK_TIMEOUT_PEAK_SECONDS | 120 |
| TASK_TIMEOUT_OFF_PEAK_SECONDS | 120 |
| TASK_TIMEOUT_PEAK_START | 09:00 |
| TASK_TIMEOUT_PEAK_END | 18:00 |
| Backend 端口 | 18000 |
| Mock 服务端口 | 19000 |

### 测试进程读取的环境变量

`tests/mock_integration/conftest.py`：

| 变量 | 作用 |
|------|------|
| `MOCK_TEST_BACKEND_URL` | pytest 访问的 backend 地址（默认 `http://<docker host>:18000`） |
| `MOCK_TEST_MOCK_URL` | pytest 访问的 mock 服务地址（默认 `http://<docker host>:19000`） |
| `DOCKER_HOST_IP` | 覆盖 docker host 探测结果，远程 Docker context 下需要 |
| `WORKER_IMAGE` | 断言 worker 容器使用的镜像 |

`scripts/run-mock-stack.sh` 额外接受 `MOCK_WORKSPACE_HOST_PATH`、`MOCK_BACKEND_TEST_IMAGE`、`MOCK_SERVICES_IMAGE`、`MOCK_WORKER_TEST_IMAGE`。

---

## 5. Playwright E2E 测试

Playwright E2E 测试需要完整的 Docker 环境，套件用 pytest-xdist 并行执行（`backend/tests/e2e/pytest.ini` 默认 `-n auto --dist=loadfile`），状态无关的用例并行跑，状态相关的用例串行跑。

### 运行命令

```bash
# 完整流程（启动环境 → 并行 + 串行 → 关闭环境）
make test-e2e

# 仅并行组（292 个）
make test-e2e-parallel

# 仅串行组（29 个）
make test-e2e-serial

# 运行特定文件 / 类 / 方法（TEST_FILE 相对 tests/e2e/tests/）
make test-e2e-specific TEST_FILE=test_dashboard.py
make test-e2e-specific TEST_FILE=test_dashboard.py::TestDashboardPage
make test-e2e-specific TEST_FILE=test_dashboard.py::TestDashboardPage::test_dashboard_page_loads

# 分步控制
make test-e2e-up      # 启动测试环境（--build --wait）
make test-e2e-down    # 关闭测试环境
make test-e2e-logs    # 查看测试环境日志

# 带视频录制，视频写到 deploy/e2e-videos/（已在 .gitignore）
make test-e2e RECORD_VIDEO=1
```

### 测试分组

| 分组 | 文件 | 测试数 |
|------|------|--------|
| 并行（无状态） | test_config_tabs, test_task_view, test_issue_view, test_monitor, test_navigation, test_task_queue, test_dashboard, test_issue_list, test_task_details, test_schedule_overview, test_create_issue, test_analytics, test_sessions, test_login, test_shell, test_oidc_diagnostics | 292 |
| 串行（有状态） | test_bootstrap, test_prompt_template, test_access_management, test_slot_capacity | 29 |

串行组的判定依据是 `pytest.mark.serial`。`make test-e2e-parallel` 用 `-m "not serial"` 把串行用例排除在并行轮之外，`make test-e2e-serial` 用 `-m serial` 单独跑；`test_bootstrap.py` 另外在模块导入时检测到 `PYTEST_XDIST_WORKER` 就整模块 `pytest.skip`。`test_access_management.py` 与 `test_slot_capacity.py` 只有标记了 `serial` 的类（分别 2 个和 9 个用例）属于串行组，同文件其余用例照常在并行组里跑。分组规则与 fixtures 见 [E2E_TESTS.md](./E2E_TESTS.md)。

### 环境说明

- E2E 前端走 `18980` 端口，避免与开发环境 `8880` 冲突
- 独立的 PostgreSQL（tmpfs，无持久化），容器名 `codify-e2e-postgres`
- 测试容器读取的环境变量：`E2E_BASE_URL`、`E2E_BACKEND_URL`、`E2E_GITLAB_URL`、`E2E_POSTGRES_URL`、`E2E_RECORD_VIDEO`，另外 pytest-xdist 会设置 `PYTEST_XDIST_WORKER`
- `RECORD_VIDEO=1` 时 Makefile 把 `E2E_RECORD_VIDEO=1` 传给容器，并用固定容器名 `codify-e2e-recorder` 把 `/videos/` 拷回宿主机

---

## 6. GitLab E2E 测试

### 运行命令

```bash
make test-e2e-gitlab
```

目标内部是 `docker-compose -f docker-compose.e2e.yml run --rm e2e pytest tests/gitlab_e2e/ -v`，compose 会按 `depends_on` 自行拉起并等待 postgres、backend、nginx，因此不强制先跑 `make test-e2e-up`。

### 测试文件

| 文件 | 说明 | 依赖 |
|------|------|------|
| `test_manual_task.py` | 手动任务创建（GitLab API 直连 + backend API） | 真实 GitLab |
| `test_task_execution.py` | 任务创建 API + 完整 worker 执行 | 见下表 |

#### `test_task_execution.py` 各测试类依赖

| 测试类 | 说明 | 运行环境 |
|--------|------|----------|
| `TestTaskAPIIntegrity` | 快速 API 完整性检查（6 个） | E2E 环境 |
| `TestManualTaskExecution` | 完整 worker 执行（需真实 Harness CLI） | 真实部署 |
| `TestScheduledTaskExecution` | 调度行为验证（需真实 Harness CLI） | 真实部署 |

#### 只跑 API 完整性检查

`TEST_FILE` 只能拼在 `tests/e2e/tests/` 之下，跑 GitLab 套件里的单个类要用原生的 compose 命令：

```bash
cd deploy && docker-compose -f docker-compose.e2e.yml run --rm e2e \
  pytest tests/gitlab_e2e/test_task_execution.py::TestTaskAPIIntegrity -v
```

#### 认证说明

`test_task_execution.py` 自己处理登录：

- 系统未初始化（E2E 全新环境）：自动注册 `test_admin_gitlab_e2e`（密码 `SecurePass123!`）
- 系统已初始化：直接登录，登录失败时 skip

`test_manual_task.py` 用的账号是 `test_admin_manual_e2e`，两个账号都由 `tests/gitlab_e2e/conftest.py` 在会话开始时直插数据库。

#### 读取的环境变量

| 变量 | 作用 |
|------|------|
| `GITLAB_URL` | GitLab 地址，默认 `http://192.168.50.129:8080` |
| `GITLAB_BOT_TOKEN` | 缺失时 `test_manual_task.py` 全部 skip |
| `E2E_BACKEND_URL` / `BACKEND_URL` | Codify 后端地址 |
| `TEST_PROJECT_ID` | 用例使用的 GitLab 项目，默认 `1` |
| `TASK_EXECUTION_TIMEOUT` | 等待任务终态的秒数，默认 `360` |
| `E2E_POSTGRES_URL` / `DATABASE_URL` | conftest 直插测试用户用 |

### 环境要求
- 可访问的 GitLab 实例（`TestTaskAPIIntegrity` 不需要 GitLab，只需要 backend）
- 有效的 `GITLAB_BOT_TOKEN`
- 测试项目和配置（测试代码按 `backend/tests/gitlab_e2e/.env`、`deploy/.env.test` 的顺序查找，文件可以不存在）
- 完整执行测试还需要真实 Harness CLI 可用的部署

### 安全注意事项

> **警告**：真实 GitLab E2E 测试只应该跑在隔离测试环境。

- 测试可能创建任务、分支、MR、Issue 评论
- 不要对着正式环境运行

---

## 重建镜像

E2E 环境的镜像由 compose 构建：

```bash
make test-e2e-up        # 带 --build，代码改动后重新构建
make up                 # 开发环境同样带 --build
```

只重建 E2E 测试容器本身：

```bash
docker build --no-cache -f deploy/Dockerfile.e2e -t codify-e2e:latest .
```

worker 镜像（任务真正执行的运行时镜像）用：

```bash
make worker-runtime-image-build
```

---

## 相关文档

- [E2E_TESTS.md](./E2E_TESTS.md) - Playwright E2E 测试详细指南（含集成调试与 GitLab 验证）
- [dev-env-core-regression.md](./dev-env-core-regression.md) - 开发环境核心回归流程与 `scripts/dev-regression.sh` 的用法
