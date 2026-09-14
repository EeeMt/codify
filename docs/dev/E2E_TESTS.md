# E2E 测试指南

本文档介绍 Codify 项目的 Playwright E2E 浏览器测试的开发、运行、调试方法，以及真实 GitLab 集成测试的排查要点。

## 目录

- [快速开始](#快速开始)
- [环境配置](#环境配置)
- [运行测试](#运行测试)
- [并行 / 串行架构](#并行--串行架构)
- [测试结构](#测试结构)
- [编写测试](#编写测试)
- [Fixtures 详解](#fixtures-详解)
- [常见问题](#常见问题)
- [调试技巧](#调试技巧)
- [调试命令速查](#调试命令速查)
- [GitLab 集成验证](#gitlab-集成验证)

---

## 快速开始

```bash
# 1. 启动测试环境（构建镜像并等待 postgres / backend / nginx healthy）
make test-e2e-up

# 2. 跑 UI 套件：并行组 + 串行组
make test-e2e-ui

# 或者只跑其中一组
make test-e2e-parallel
make test-e2e-serial

# 3. 收工
make test-e2e-down
```

`make test-e2e` 把上面三步合成一次运行，并在最后追加 GitLab E2E 再关栈。

### 运行特定测试

```bash
# 单个文件、单个类、单个方法（TEST_FILE 相对 tests/e2e/tests/）
make test-e2e-specific TEST_FILE=test_dashboard.py
make test-e2e-specific TEST_FILE=test_dashboard.py::TestDashboardPage
make test-e2e-specific TEST_FILE=test_dashboard.py::TestDashboardPage::test_dashboard_page_loads

# 按标记运行
cd deploy && docker-compose -f docker-compose.e2e.yml run --rm e2e pytest tests/e2e/tests/ -m dashboard -v
```

> 分组规则、`class_page` 与 `logged_in_page` 的区别、确定性等待和 Naive UI 选择器见下文；跑法汇总见 [TESTING.md](TESTING.md) §5。

---

## 环境配置

### 文件结构

```
deploy/
├── docker-compose.e2e.yml      # E2E 测试环境
├── Dockerfile.e2e              # E2E 测试容器（pytest + Playwright + Chromium）
├── Dockerfile.backend          # Backend / Scheduler / migrate 镜像
└── Dockerfile.frontend         # nginx + 前端构建

backend/tests/e2e/
├── __init__.py
├── conftest.py                 # fixtures、DB 重置、xdist 适配
├── pytest.ini                  # E2E 专用 pytest 配置（markers / -n auto --dist=loadfile）
├── requirements-e2e.txt        # pytest-playwright / playwright / pytest-html / pytest-xdist
├── README.md
└── tests/
    ├── test_access_management.py   test_analytics.py        test_bootstrap.py
    ├── test_config_tabs.py         test_create_issue.py     test_dashboard.py
    ├── test_issue_list.py          test_issue_view.py       test_login.py
    ├── test_monitor.py             test_navigation.py       test_oidc_diagnostics.py
    ├── test_prompt_template.py     test_schedule_overview.py test_sessions.py
    ├── test_shell.py               test_slot_capacity.py    test_task_details.py
    ├── test_task_queue.py          test_task_view.py
```

### docker-compose.e2e.yml 配置（节选）

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: codify-e2e-postgres
    tmpfs:
      - /var/lib/postgresql/data        # 无持久卷，每次启动都是空库

  migrate:                              # 唯一的 migration owner，跑完即退出
    image: codify-backend:latest
    command:
      - python3
      - -m
      - alembic
      - upgrade
      - ${MIGRATION_TARGET:-head}
    environment:
      - DATABASE_URL=postgresql+asyncpg://codify:codify_password@postgres:5432/codify
      - AUTO_MIGRATE=false

  backend:
    image: codify-backend:latest
    container_name: codify-e2e-backend
    # 单 worker：配置 PATCH 与 webhook 必须落在同一进程
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
    environment:
      - AUTO_MIGRATE=false

  nginx:
    image: codify-nginx:latest
    container_name: codify-e2e-nginx
    ports:
      - "18980:80"

  scheduler:
    image: codify-backend:latest
    container_name: codify-e2e-scheduler
    command: ["python3", "-m", "app.scheduler_service"]
    environment:
      - AUTO_MIGRATE=false

  e2e:
    image: codify-e2e:latest
    container_name: codify-e2e-tester
    environment:
      - E2E_BASE_URL=http://nginx:80
      - E2E_BACKEND_URL=http://backend:8000
      - E2E_GITLAB_URL=http://gitlab:8080
      - E2E_POSTGRES_URL=postgresql://codify:codify_password@postgres:5432/codify
      - E2E_RECORD_VIDEO=${E2E_RECORD_VIDEO:-}
      - BACKEND_URL=http://backend:8000
    shm_size: '2gb'
```

E2E 栈里 backend 与 scheduler 都是 `AUTO_MIGRATE=false`，迁移由 `migrate` 服务在 backend 启动前完成。完整的镜像重建方式见 [TESTING.md](TESTING.md)。

### 环境变量说明

`tests/e2e/conftest.py` 读取以下变量，未设置时用括号里的默认值：

| 变量 | compose 注入值 | 说明 |
|------|----------------|------|
| `E2E_BASE_URL` | `http://nginx:80` | 前端入口，Playwright 的 `base_url`（无值时 `http://nginx`） |
| `E2E_BACKEND_URL` | `http://backend:8000` | 后端 API，`_api_login` 与 API 建数据用它 |
| `E2E_GITLAB_URL` | `http://gitlab:8080` | conftest 提供 `gitlab_url` fixture 并写进报告头，当前用例没有使用 |
| `E2E_POSTGRES_URL` | `postgresql://codify:codify_password@postgres:5432/codify` | 直连数据库做用户插入与重置 |
| `E2E_RECORD_VIDEO` | 由 `RECORD_VIDEO=1` 传入 | 非空即为每个用例录制视频 |
| `PYTEST_XDIST_WORKER` | pytest-xdist 设置 | `gw0`、`gw1`…；conftest 用它切换并行/串行实现 |

### 重新构建镜像

```bash
# 开发环境镜像（backend / nginx / scheduler）
make build-app-images

# E2E 测试容器本身
docker build -f deploy/Dockerfile.e2e -t codify-e2e:latest .

# worker 运行时镜像
make worker-runtime-image-build
```

> **注意**：worker 容器执行的 entrypoint 来自 Task Runtime Bundle（backend 在任务创建时从镜像内
> `/opt/codify/runtime-source` 生成）。改动 `deploy/worker-entrypoint/**` 或 `deploy/entrypoint.worker.sh` 后必须重建
> backend 镜像并 recreate scheduler，retry 任务复用旧 bundle digest，要验证新改动必须新建任务。
> 详见 [dev-env-api-regression.md](dev-env-api-regression.md) §8。

---

## 运行测试

### 本地直跑（不通过 Docker）

```bash
cd backend
pip install -r requirements.txt
pip install -r tests/e2e/requirements-e2e.txt
playwright install chromium

pytest tests/e2e/ -v
```

从 `backend/` 传路径时 pytest 会把 rootdir 定到 `backend/tests/e2e`，因此自动使用该目录下的 `pytest.ini`，`-n auto --dist=loadfile` 也照常生效。本机直跑需要三样东西：

- 可访问的后端（`E2E_BACKEND_URL`，默认 `http://backend:8000`）
- 可访问的 PostgreSQL（`E2E_POSTGRES_URL`）
- 可访问的前端（`E2E_BASE_URL`）

### 只跑一个用例

```bash
cd backend
pytest tests/e2e/tests/test_dashboard.py -v
pytest tests/e2e/tests/test_dashboard.py::TestDashboardPage::test_dashboard_page_loads -v
pytest tests/e2e/tests/ -k "bootstrap" -v
```

### 使用可见浏览器

镜像里没有 X server，也没有 Xvfb，容器内的 Chromium 只能无头运行。需要在屏幕上看操作过程时，用本机直跑并加 `--headed`：

```bash
cd backend && pytest tests/e2e/tests/test_dashboard.py -v --headed
```

### 查看 HTML 报告

`docker-compose run --rm` 会在结束后删除容器，先给容器固定名字再拷报告：

```bash
cd deploy
docker-compose -f docker-compose.e2e.yml run --name codify-e2e-report e2e \
  pytest tests/e2e/tests/ -v --html=report.html --self-contained-html
docker cp codify-e2e-report:/app/report.html ./
docker rm codify-e2e-report
```

### 录制视频

```bash
make test-e2e RECORD_VIDEO=1
```

Makefile 用固定容器名 `codify-e2e-recorder` 启动测试，结束后把容器内 `/videos/` 拷到 `deploy/e2e-videos/`（已加入 `.gitignore`）。只有使用 `logged_in_page` 的用例会录，文件名是 `<用例名>_<worker>.webm`。

---

## 并行 / 串行架构

套件用 pytest-xdist 并行执行（`pytest.ini` 默认 `-n auto --dist=loadfile`）。状态无关的用例并行跑，状态相关的用例串行跑。

```
pytest -n auto --dist=loadfile
      │
      ├─ gw0 ── test_dashboard.py ──── test_admin_gw0 用户
      ├─ gw1 ── test_navigation.py ─── test_admin_gw1 用户
      ├─ gw2 ── test_config_tabs.py ── test_admin_gw2 用户
      └─ gw3 ── test_task_view.py ──── test_admin_gw3 用户
```

串行与并行使用不同的实现，区别如下：

| 组件 | 串行（`-m serial`） | 并行（xdist） |
|------|---------------------|---------------|
| 管理员用户 | `test_admin`，由 `POST /api/auth/local/register` 创建 | `test_admin_gw0/gw1/…`，session 级直插数据库 |
| 密码 Hash | 600,000 次 PBKDF2（后端的 `hash_password`） | 1 次 PBKDF2（后端从 hash 字符串读取迭代次数） |
| `reset_database` | 清空 `user_sessions` + `users`，并把 `system_bootstrap` 重置为未初始化 | 空操作，`_reset_db` 检测到 `PYTEST_XDIST_WORKER` 直接返回 |
| `_api_login` | 先 register 再 fallback login | 直接用本 worker 账号调 `/api/auth/local/login` |
| 分组 | 由 `make test-e2e-serial` 的 `-m serial` 选中 | 由 `make test-e2e-parallel` 的 `-m "not serial"` 排除串行组 |

`test_bootstrap.py` 需要系统处于未初始化状态，xdist 下不可能满足，因此模块顶部直接 `pytest.skip(..., allow_module_level=True)`。

串行组共 29 个用例：`test_bootstrap.py`（10）、`test_prompt_template.py`（8）、`test_access_management.py` 的 `TestAccessManagement`（2）、`test_slot_capacity.py` 里三个标记了 `serial` 的类（9）。其余 292 个用例属于并行组。

---

## 测试结构

### 测试标记 (Markers)

标记在 `pytest.ini` 里注册，`--strict-markers` 生效，新标记必须先注册再使用。当前标记与文件的对应关系：

| 标记 | 文件 |
|------|------|
| `access` | test_access_management.py |
| `analytics` | test_analytics.py |
| `bootstrap` | test_bootstrap.py |
| `config_tabs` | test_config_tabs.py，test_slot_capacity.py |
| `create_issue` | test_create_issue.py |
| `dashboard` | test_dashboard.py |
| `issue_list` | test_issue_list.py |
| `issue_view` | test_issue_view.py |
| `login` | test_login.py |
| `monitor` | test_monitor.py |
| `navigation` | test_navigation.py |
| `oidc_diagnostics` | test_oidc_diagnostics.py |
| `prompt_template` | test_prompt_template.py |
| `schedule_overview` | test_schedule_overview.py，test_slot_capacity.py |
| `serial` | 需要独占数据库状态的用例 |
| `sessions` | test_sessions.py |
| `shell` | test_shell.py |
| `slot_capacity` | test_slot_capacity.py |
| `task_details` | test_task_details.py |
| `task_list` | test_task_queue.py |
| `task_view` | test_task_view.py |

`pytest.ini` 里还注册了 `auth` 与 `slow`：UI 套件当前没有用到这两个，`slow` 由 `tests/gitlab_e2e/test_manual_task.py` 使用。

### 测试文件模板

```python
"""
测试文件描述

Tests for the [功能模块] page functionality including:
- 功能点1
- 功能点2
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.dashboard
class TestDashboardPage:
    """Tests for the dashboard page functionality."""

    def test_page_loads(self, class_page: Page):
        class_page.goto("/dashboard")
        class_page.wait_for_load_state("networkidle")
        expect(class_page.get_by_test_id("dashboard-page")).to_be_visible()

    def test_summary_is_displayed(self, class_page: Page):
        class_page.goto("/dashboard")
        expect(class_page.get_by_test_id("dashboard-summary")).to_be_visible(timeout=30000)
```

写只读断言用 `class_page`，需要干净数据库状态的用例才换成 `logged_in_page` 加 `reset_database`。

---

## 编写测试

### 1. 先判断分组：并行还是串行？

可以并行，放入现有并行文件或新建并行文件：
- 只读取页面 UI 元素（导航、布局、静态内容）
- 不创建或修改数据库记录
- 不依赖 `system_bootstrap.initialized` 的值

必须串行，用 `pytest.mark.serial` 标记：
- 修改 `system_bootstrap`（bootstrap 流程测试）
- 在共享表中创建或删除命名记录（如 prompt_templates）
- 修改其他用户的角色或权限
- 依赖数据库里只有一个用户的假设

模块级串行标记，参考 `test_prompt_template.py`：

```python
import pytest

# Modifies shared config state; requires serial execution.
# Run with: make test-e2e-serial
pytestmark = pytest.mark.serial
```

如果整个模块在并行模式下会产生错误状态，再补一个模块级跳过，参考 `test_bootstrap.py`：

```python
import os
import pytest

pytestmark = pytest.mark.serial

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "Bootstrap tests require exclusive DB access; run with -m serial",
        allow_module_level=True,
    )
```

只让某个类串行时，直接把 `@pytest.mark.serial` 加在类上（见 `test_access_management.py`、`test_slot_capacity.py`）。

### 2. 选对 fixture

只读用例用 `class_page`，它在一个文件内复用同一个已登录 context，省掉每个用例的登录和 context 创建：

```python
def test_something(self, class_page: Page):
    class_page.goto("/dashboard")
    expect(class_page.get_by_test_id("dashboard-page")).to_be_visible()
```

需要干净数据状态、或者会写数据的用例用 `logged_in_page` 加 `reset_database`：

```python
def test_something(self, logged_in_page: Page, reset_database):
    logged_in_page.goto("/issues/create")
    # ...
```

会破坏共享登录态的用例（例如登出）用 `fresh_page`，它每个用例新建 context 但不重置数据库。

不要手工驱动 bootstrap 或登录页，`_api_login` 已经通过 API 拿到 cookie 并注入 context。

### 3. 用确定性等待，不用 `wait_for_timeout`

```python
# 正确：等待具体元素或状态
page.wait_for_selector(".my-component", state="visible", timeout=10000)
page.wait_for_load_state("networkidle")
expect(page.get_by_role("button", name="Save")).to_be_visible()

# 错误：硬编码延迟
page.wait_for_timeout(2000)
```

并行轮里多个 worker 抢同一台 nginx 与 backend，渲染可能变慢，给关键断言加 `timeout`（例如 `timeout=30000`）比加睡眠可靠。

### 4. 选择器：优先 data-testid，其次 Naive UI 的结构类名

前端在组件上写 `data-testid`，包括 Naive UI 组件。测试里优先用它：

```python
page.get_by_test_id("dashboard-summary")
page.get_by_test_id("access-management-revoke-button").click()
```

`data-testid` 落在组件根元素上，所以行为随组件而变：

- `n-button` 的根就是 `<button>`，可以直接 click
- `n-input`、`n-select` 的根是外层包裹 div，要往里找真正的控件：

```python
# n-input：testid 在外层，输入框在内部
search = page.get_by_test_id("access-management-search").locator("input")
search.fill("alice")

# n-data-table：testid 在容器上，表格本身要再定位
table = page.get_by_test_id("dashboard-recent-issues").locator(".n-data-table")
headers = table.locator("thead th")
```

没有 testid 的地方用 Naive UI 的类名：

```python
# n-select 的可点击区域
page.locator(".n-base-selection").filter(has_text="Select a project")

# n-tabs 的标签页
page.locator(".n-tabs-tab").nth(6)

# n-popconfirm / n-popover 渲染在 body 级 portal
page.locator(".n-popover").get_by_role("button", name="Delete")
```

### 5. 配置页面的 Tab 导航

通过 URL query 参数导航并等待内容加载：

```python
page.goto("/config?tab=prompt-templates")
page.wait_for_load_state("networkidle")
```

`/config` 会重定向到 `/configuration`，query 会带上，两种写法等价。可用的 tab 值见 `frontend/src/views/Config.vue` 的 `n-tab-pane name`：`runtime`、`auth`、`gitlab`、`ai-providers`、`prompt-templates`、`worker`、`skills`、`notifications`、`announcement`、`maintenance`、`webhook-events`。

---

## Fixtures 详解

### logged_in_page

每个用例一个已登录的浏览器 context，认证走 API 而不是 UI，当前有 77 个用例用它：

```python
def test_requires_auth(self, logged_in_page: Page, reset_database):
    logged_in_page.goto("/dashboard")
    # ...
```

工作流程：
1. 依赖 `reset_database`，先把数据库恢复成干净状态
2. 调 `_api_login`：xdist 下用 `test_admin_<worker>` 登录，非 xdist 下先 register 再 fallback login
3. 把拿到的 `codify_session` cookie 作为 `storage_state` 注入新的 context，直接落到已登录状态
4. 用例结束后关闭 context；开了 `E2E_RECORD_VIDEO` 时先把视频改名成 `<用例名>_<worker>.webm`

### class_page

文件级（`scope="module"`）的已登录页面，一个文件只登录一次。只适合只读用例：它不重置数据库，也不会在用例之间重建 context。当前有 217 个用例用它。

### fresh_page

每个用例新建一个已登录 context，但不重置数据库。给会破坏共享登录态的用例用，例如登出。

### reset_database

每个用例前后重置数据库状态。非 xdist 模式下删除 `user_sessions`、`users`，并把 `system_bootstrap` 置回未初始化；xdist 模式下是空操作，隔离靠每个用例新建 context 和各自的管理员账号。

### db_cursor / worker_admin_setup

- `db_cursor`：session 级 psycopg2 连接（`AUTOCOMMIT`），直接读写数据库用
- `worker_admin_setup`：session 级 fixture，xdist 下为每个 worker 直插 `test_admin_<worker>`（`ON CONFLICT DO NOTHING`），非 xdist 下是空操作，因此串行行为不变

### page

pytest-playwright 提供的基础 fixture，未登录。`test_bootstrap.py`、`test_login.py`、`test_navigation.py` 用它，共 26 个用例。

### API 辅助函数

`tests/e2e/conftest.py` 里可以直接 import 使用：

| 函数 | 作用 |
|------|------|
| `api_get_first_project(backend_url, cookies)` | 取第一个可用项目，没有则 skip |
| `api_create_issue(backend_url, cookies, project_id, title, description)` | 建 issue，自动挑一个 enabled 的 worker profile |
| `api_create_task(backend_url, cookies, issue_id, prompt, priority, scheduled_datetime)` | 建任务，默认排到 48 小时后保持 pending |
| `_get_cookies(page)` | 从 Playwright context 取 cookie dict |

---

## 常见问题

### Playwright 测试类

**1. 测试超时**

原因：页面加载慢或元素未及时出现。

```python
# 方案1：增加超时
page.wait_for_load_state("networkidle", timeout=30000)

# 方案2：等待元素
page.wait_for_selector(".element", timeout=10000)
```

**2. 严格模式冲突**

原因：选择器匹配到多个元素。错误：`Error: strict mode violation: locator(".n-card") resolved to 6 elements`。

```python
expect(page.locator(".n-card").first).to_be_visible()
expect(page.locator(".n-modal")).to_be_visible()
expect(page.get_by_role("dialog").get_by_text("Name")).to_be_visible()
```

**3. URL 匹配失败**

```python
assert "/dashboard" in page.url
expect(page).to_have_url("**/dashboard", timeout=5000)
```

**4. 表名不存在**

错误：`relation "sessions" does not exist`。数据库表名是 `user_sessions`。

```bash
docker exec codify-e2e-postgres psql -U codify -d codify -c "\dt"
```

**5. 滚动元素不可见**

```python
element = page.locator(".n-tabs-tab").nth(6)
element.scroll_into_view_if_needed()
element.click()
```

### 基础设施 / 集成调试类

**6. Token 泄露问题**

症状：错误日志中暴露了 GitLab Token (`glpat-xxx`) 或 API Key (`sk-xxx`)。

原因：日志直接输出敏感信息；数据库错误信息未脱敏。

解决：worker 日志在存储前统一经 `backend/app/core/worker.py` 的 `sanitize_sensitive_data()` 处理，它先按 token 形态打码（`glpat-*`、`sk-ant-*`、`sk-or-v1-*`、`Bearer`、`AIza*`、`ghp_*`、`hf_*`、`xox*`、`api_key = ...`），再剥掉 ANSI 转义与非法 Unicode 码点。

**7. 数据库编码错误**

症状：`CharacterNotInRepertoireError: invalid byte sequence for encoding "UTF8": 0x00`。

原因：日志中包含 null 字节 (`\x00`)，`scrub_sensitive_data()` 里已 `text.replace('\x00', '')`。

**8. 任务状态卡住**

症状：任务状态一直是 `running`，但容器已退出。

```bash
# 检查任务状态
docker exec codify-e2e-postgres psql -U codify -d codify -c "SELECT id, status FROM tasks ORDER BY id DESC LIMIT 5;"

# 检查容器状态与日志
docker ps -a | grep codify
docker logs <container_id>
```

> 定位 CLI 层问题的第一现场是 archive 里的 `harness-events/<harness>.jsonl`，详见
> [multi-harness-debugging.md](multi-harness-debugging.md)。

**9. 日志截断问题**

症状：错误信息不完整，只看到部分日志。

解决：增加日志存储长度（`error_message` 与 `TaskLog.message` 的截断上限）。

**10. Shell Heredoc 语法错误**

症状：Python 脚本报 `SyntaxError: unmatched ')'`。

原因：在 `<<'PYTHON_SCRIPT'` heredoc 内错误放置了 bash 代码。bash 代码应放在 heredoc 结束后。

---

## 调试技巧

### 添加截图

```python
def test_debug(self, class_page: Page):
    class_page.goto("/dashboard")
    class_page.wait_for_load_state("networkidle")
    class_page.screenshot(path="/tmp/dashboard.png")
    print("Screenshot saved")
```

容器里写的 `/tmp/dashboard.png` 会随容器一起消失，留档时把宿主机目录挂进去，或者直接用 `RECORD_VIDEO=1` 录视频：

```bash
cd deploy && docker-compose -f docker-compose.e2e.yml run --rm \
  -v "$PWD/e2e-videos:/tmp/shots" e2e pytest tests/e2e/tests/test_dashboard.py -v
```

### 打印页面内容

```python
def test_debug(self, class_page: Page):
    class_page.goto("/dashboard")
    class_page.wait_for_load_state("networkidle")
    body_text = class_page.locator("body").inner_text()
    print(f"Page content: {body_text[:500]}")
```

### 交互式调试

```python
def test_debug(self, class_page: Page):
    class_page.goto("/dashboard")
    class_page.wait_for_load_state("networkidle")
    import pdb; pdb.set_trace()
```

本机直跑并加 `--headed` 才有意义，容器里没有显示输出。

### 检查元素状态

```python
def test_debug(self, class_page: Page):
    class_page.goto("/config")
    class_page.wait_for_load_state("networkidle")
    tabs = class_page.locator(".n-tabs-tab")
    print(f"Total tabs: {tabs.count()}")
    for i in range(tabs.count()):
        tab = tabs.nth(i)
        print(f"Tab {i}: {tab.inner_text()}, visible: {tab.is_visible()}")
```

---

## 调试命令速查

```bash
# 1. 启动 E2E 环境
make test-e2e-up

# 2. 跑并行组 + 串行组
make test-e2e-ui

# 3. 跑单个测试文件
make test-e2e-specific TEST_FILE=test_dashboard.py

# 4. 跑单个方法
make test-e2e-specific TEST_FILE=test_dashboard.py::TestDashboardPage::test_dashboard_page_loads

# 5. 按标记运行
cd deploy && docker-compose -f docker-compose.e2e.yml run --rm e2e pytest tests/e2e/tests/ -m dashboard -v

# 6. 查看容器日志
docker logs codify-e2e-backend --tail 100
docker logs codify-e2e-backend --tail 100 2>&1 | grep -iE "task|error"

# 7. 查看数据库任务状态
docker exec codify-e2e-postgres psql -U codify -d codify -c "SELECT id, status, error_message FROM tasks ORDER BY id DESC LIMIT 3;"

# 8. 查看任务日志（完整输出）
docker exec codify-e2e-postgres psql -U codify -d codify -c "SELECT message FROM task_logs WHERE task_id = <id>;"

# 9. 检查数据库表
docker exec codify-e2e-postgres psql -U codify -d codify -c "\dt"

# 10. 查看当前运行的容器
docker ps -a | grep codify

# 11. 清理环境
make test-e2e-down

# 12. 重新构建 E2E 测试镜像
docker build --no-cache -f deploy/Dockerfile.e2e -t codify-e2e:latest .
```

---

## GitLab 集成验证

真实 GitLab E2E 测试（`tests/gitlab_e2e/`）验证完整 worker 链路（真实 GitLab + 真实 Harness CLI）。
此类测试**只应跑在隔离测试环境**，可能创建任务、分支、MR、Issue 评论。

运行方式和环境变量见 [TESTING.md](TESTING.md) §6。

### 测试检查清单

运行集成测试后，验证以下项目：

- [ ] Issue 评论显示开始通知
- [ ] Issue 评论显示完成通知（带 MR 链接）
- [ ] MR 有实际提交（SHA 不为 null）
- [ ] MR 无冲突
- [ ] 任务状态为 completed（不是 running/failed）
- [ ] 错误日志中无 Token 泄露
- [ ] archive 的 `harness-events/<harness>.jsonl` 可回放（canonical 事件一致）

### 常用 GitLab API 端点（开发环境）

```
GitLab 地址: http://192.168.50.129:8080

# Issue 相关
GET  /api/v4/projects/1/issues              # 列出 Issue
GET  /api/v4/projects/1/issues/{iid}        # 获取 Issue
POST /api/v4/projects/1/issues              # 创建 Issue
GET  /api/v4/projects/1/issues/{iid}/notes  # 获取 Issue 评论

# MR 相关
GET  /api/v4/projects/1/merge_requests              # 列出 MR
GET  /api/v4/projects/1/merge_requests/{iid}        # 获取 MR
GET  /api/v4/projects/1/repository/commits?ref_name=branch  # 查看提交

# 项目相关
GET  /api/v4/projects/1                     # 获取项目信息
GET  /api/v4/projects/1/repository/branches # 列出分支
```

---

## 相关文件

- `backend/tests/e2e/conftest.py` - Fixtures 和配置
- `backend/tests/e2e/pytest.ini` - E2E pytest 配置与 markers
- `backend/tests/e2e/requirements-e2e.txt` - 测试依赖
- `backend/tests/gitlab_e2e/` - 真实 GitLab 集成测试
- `deploy/docker-compose.e2e.yml` - 测试环境配置
- `deploy/Dockerfile.e2e` - 测试容器构建
