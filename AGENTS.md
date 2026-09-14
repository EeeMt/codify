# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Codify — an AI-powered code generation service. Users create issues in the dashboard, launch tasks from them, and Codify schedules execution in isolated Docker containers, where the harness frozen into the task snapshot (Claude, Codex, Pi, or OpenCode) generates code, commits, pushes, and opens Merge Requests.

## Commands

Most commands go through `make`. Run `make help` to see the full list.

### Development

```bash
make help                    # Show all available commands

# Dev environment
make build                   # Build backend and nginx images
make up                     # Start dev environment
make down                   # Stop dev environment
make restart                # Restart dev environment
make logs                   # View logs
make ps                     # Show running containers

# Rebuild specific service
make rebuild-backend         # Rebuild backend image and restart
make rebuild-scheduler       # Rebuild scheduler image and restart
make rebuild-nginx           # Rebuild frontend image and restart
make worker-runtime-image-build  # Rebuild the project-runtime worker image

# Testing
make test-unit              # All unit tests (with coverage)
make test-backend           # Backend unit tests only
make test-frontend          # Frontend unit tests only
make test-mock-e2e         # Mock E2E tests
make test-mock-integration  # Full lifecycle in Docker (mock GitLab + fake harness)
make test-e2e               # All E2E tests (Playwright + GitLab)
make test-e2e-ui            # Playwright UI tests only
make test-e2e-gitlab        # GitLab integration tests only
make test-all               # Unit + mock integration + all E2E tests

# Playwright E2E step-by-step
make test-e2e-up            # Start E2E test environment
make test-e2e-ui            # Run Playwright UI tests
make test-e2e-down          # Stop E2E test environment
```

### Testing & Debugging

See [docs/dev/TESTING.md](docs/dev/TESTING.md) for the detailed testing guide.

Backend `pytest` collects `tests/unit`, `tests/mock_integration`, and `tests/mock_e2e` from `testpaths`, and skips `tests/e2e` and `tests/gitlab_e2e`. Run the skipped suites by path or through their Docker targets (`make test-e2e`, `make test-e2e-gitlab`).

Quick debug commands:
```bash
# View backend logs
docker logs codify-backend --tail 100

# Check task status in database
docker exec codify-postgres psql -U codify -d codify -c "SELECT id, status, error_message FROM tasks ORDER BY id DESC LIMIT 3;"
```

## Architecture

### High-Level Flow

1. User creates an issue in the dashboard, describing the goal and constraints
2. User launches or schedules a task from the issue
3. Scheduler picks up pending tasks (priority queue, respects concurrency limits)
4. WorkerExecutor runs the task in an isolated Docker container
5. Container clones the repo and runs the harness recorded in the frozen runtime bundle
6. Container commits, pushes, and creates/updates the MR
7. Dashboard shows status, logs, and delivery details in real-time

### Core Components

| Component | File | Description |
|-----------|------|-------------|
| Issue API | `backend/app/api/issues.py` | Issue CRUD, close, task creation from issues |
| Task API | `backend/app/api/tasks.py` | Task CRUD, cancel, retry, execute, schedule |
| Models | `backend/app/models.py` | SQLAlchemy models (Task, TaskLog, Issue, etc.) |
| Scheduler | `backend/app/scheduler.py` | Priority queue with P0/P1/P2, crash recovery |
| Worker | `backend/app/core/worker.py` | Executes tasks in Docker containers |
| Harness Registry | `backend/app/core/harness_registry.py` | Harness allowlist, capability policy, manifest validation |
| Docker Client | `backend/app/core/docker_client.py` | Container lifecycle management |
| GitLab Client | `backend/app/core/gitlab_client.py` | GitLab API interactions (repos, branches, MRs) |
| AI Providers | `backend/app/api/providers.py` | Multi-provider AI configuration |
| Stats | `backend/app/api/stats.py` | Analytics, heatmap, scheduled task stats |
| Migration Runner | `backend/app/migrations.py` | Auto-run migrations on startup |

### Database

Async SQLAlchemy (`AsyncSession`) throughout. Alembic manages migrations in `backend/alembic/versions/`, numbered sequentially as `NNN_description.py`. Current revision: `080_task_command_created_by`.

Task lifecycle: `PENDING → QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED`

### Service split in Docker Compose

- **backend** (`codify-backend`): FastAPI HTTP server, `AUTO_MIGRATE=false`
- **scheduler** (`codify-scheduler`): same image, runs `app.scheduler_service`, `AUTO_MIGRATE=true` (owns migrations)
- **nginx** (`codify-nginx`): serves built frontend and proxies `/api` to backend
- **postgres** (`codify-postgres`): PostgreSQL 16 on the `postgres_data` volume; a `migrate` service under the `maintenance` profile runs explicit migrations

### Frontend (Vue 3)

- `Dashboard.vue` (`/dashboard`) — task list with summary cards, filters, and the My Work Board
- `IssueList.vue` / `IssueView.vue` — issue management and task creation
- `CreateIssue.vue` — new issue with prompt templates (`/issues/create`; `/create-task` redirects here)
- `TaskList.vue` / `TaskView.vue` — task details and live logs
- `ScheduleOverview.vue` — scheduling queue
- `Analytics.vue` — execution trends and success rates
- `Config.vue` — runtime configuration
- `Monitor.vue` — system health (runtime, debug, health tabs)
- `Sessions.vue` — session management
- `AccessManagement.vue` — users and permissions
- `UsageManagement.vue` — daily and weekly quotas
- `SystemStatistics.vue` — system lifecycle statistics
- `OidcDiagnostics.vue` — SSO debugging
- `Guide.vue` — the in-app guide at `/guide`
- `Login.vue` / `Bootstrap.vue` — sign-in and first-run setup

### Runtime configuration

Settings have two layers:
- `get_settings()` — reads `.env` / environment variables (cached with `@lru_cache`)
- `get_effective_settings()` — applies DB-persisted overrides from `system_config` table on top

**Always use `get_effective_settings()`** in application code so runtime changes via `/api/config` take effect without restart. Secret config keys (`gitlab_bot_token`, `anthropic_api_key`, etc.) are stored encrypted.

### Configuration (env vars)

- `BACKEND_URL` — Backend service URL, used for the webhook endpoint and task links (default: http://localhost:8000)
- `FRONTEND_URL` — Dashboard URL for task links; falls back to `BACKEND_URL` when empty
- `GITLAB_URL`, `GITLAB_BOT_TOKEN` — GitLab connection and bot credentials
- `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` — default model endpoint, used when no AI Provider overrides it
- `DATABASE_URL` — PostgreSQL connection
- `DOCKER_HOST` — Docker Engine API (default: tcp://localhost:2376)
- `WORKER_IMAGE` — Project-runtime worker image (default: codify-worker/java21-maven:2026.07)
- `WORKER_WORKSPACE_HOST_PATH` — host path bind-mounted into backend and scheduler for issue workspaces
- `WORKER_WORKSPACE_RETENTION_DAYS` (default: 14) and `WORKER_FAILED_WORKSPACE_RETENTION_DAYS` (default: 30) — workspace cleanup windows
- `MAX_CONCURRENCY` — Max parallel tasks (default: 3)
- `TASK_TIMEOUT_PEAK_SECONDS` (default: 1800) and `TASK_TIMEOUT_OFF_PEAK_SECONDS` (default: 3600) — task timeouts for the peak and off-peak windows
- `TASK_TIMEOUT_PEAK_START` (default: 09:00) and `TASK_TIMEOUT_PEAK_END` (default: 18:00) — peak window boundaries
- `SCHEDULER_INTERVAL` — Scheduler poll interval in seconds (default: 5)
- `DEFAULT_TARGET_BRANCH` — Default branch for MRs (default: main)
- `HARNESS_EXECUTION_MODE` — Harness execution path (default: v2_only)
- `CONFIG_ENCRYPTION_KEY` — encrypts persisted secret config, falling back to `SESSION_SECRET`
- `AUTO_MIGRATE` — Run migrations on startup (default: false; the compose scheduler sets true and owns migrations)

## Key Conventions

### Backend patterns

- All DB operations use `AsyncSession`; pass sessions via `Depends(get_db)` in API routes
- Add new Alembic migrations as `backend/alembic/versions/NNN_description.py` incrementing the number prefix
- Issue mutex: the scheduler tracks running work in `_running_tasks: set[int]` (task IDs) and `_running_issues: set[int]` (issue IDs) so one issue never runs two tasks at once
- Worker logs are sanitized by `sanitize_sensitive_data()` before storage — strips `glpat-*` tokens and `sk-ant-*` keys
- Python target: 3.11+, line length 100 (ruff), `asyncio_mode = "auto"` in pytest

### Frontend patterns

- Vue 3 + Naive UI component library + `vue-i18n` for i18n
- All API calls go through the shared `axios` instance in `src/api/index.ts` (base `/api`, 401 → redirects to `/login`)
- Two locales: `src/i18n/messages/en.ts` and `src/i18n/messages/zh-CN.ts` — add keys to both when adding UI text
- `npm run build` runs `vue-tsc` type-check; use it to validate frontend changes before committing

### Container naming

Worker containers follow the pattern `{worker_container_prefix}-{task_id}-issue{issue_id}` (prefix defaults to `codify`; matched by the scheduler's `^{prefix}-(\d+)-issue(\d+)$` regex in `backend/app/scheduler.py`). Crash recovery on scheduler startup identifies and cleans up stale containers by this pattern.

### Priority levels

Tasks use integer priority: `0` = P0 (highest), `1` = P1, `2` = P2. The scheduler orders the queue by priority ascending, and the task list filters and sorts on priority.
