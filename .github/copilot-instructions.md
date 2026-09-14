# Copilot Instructions

## Project

Codify — AI-powered code generation service. Users create issues in the dashboard, launch tasks, and Codify schedules execution in isolated Docker containers, where the harness frozen into the task snapshot (Claude, Codex, Pi, or OpenCode) generates code, commits, pushes, and opens Merge Requests.

## Commands

### Backend

```bash
cd backend && pip install -r requirements.txt      # install deps
cd backend && uvicorn app.main:app --reload        # dev server
cd backend && alembic upgrade head                 # run migrations

cd backend && pytest                               # collects testpaths: tests/unit + tests/mock_integration + tests/mock_e2e
cd backend && pytest tests/unit/ -v               # unit tests only
cd backend && pytest tests/mock_e2e/ -v           # mock E2E (no GitLab needed)
cd backend && pytest tests/gitlab_e2e/ -v         # real GitLab E2E (addopts excludes it from a bare pytest run)

# Single test file:
cd backend && pytest tests/unit/test_scheduler.py -v
```

### Frontend

```bash
cd frontend && npm install
cd frontend && npm run dev                         # dev server
cd frontend && npm run build                       # type-check + build (use to validate changes)
```

### Docker deployment

```bash
cd deploy && docker-compose up -d --build
cd deploy && docker-compose logs -f

# After source changes, rebuild images (from the repository root):
docker build -f deploy/Dockerfile.backend -t codify-backend:latest .
make worker-runtime-image-build    # project-runtime worker image; harness CLIs ship in the Worker Kit (make worker-kit-export)
```

## Architecture

### Request flow

1. User creates an issue in the dashboard describing the goal and constraints
2. User launches or schedules a task from the issue
3. The **Scheduler** (separate process: `python -m app.scheduler_service`) polls for PENDING tasks using a priority queue
4. Scheduler calls `WorkerExecutor`, which spawns a Docker container named `{worker_container_prefix}-{task_id}-issue{issue_id}` (prefix defaults to `codify`, e.g. `codify-670-issue183`)
5. The container (`deploy/entrypoint.worker.sh`) clones the repo and runs the harness recorded in the frozen runtime bundle to generate code, commits, pushes, and creates an MR
6. Worker updates task status; dashboard shows logs and delivery details in real-time

### Service split in Docker Compose

- **backend** (`codify-backend`): FastAPI HTTP server, `AUTO_MIGRATE=false`
- **scheduler** (`codify-scheduler`): same image, runs `app.scheduler_service`, `AUTO_MIGRATE=true` (owns migrations)
- **nginx** (`codify-nginx`): serves built frontend and proxies `/api` to backend
- **postgres** (`codify-postgres`): PostgreSQL 16, the `postgres_data` volume holds all state

### Database

Async SQLAlchemy (`AsyncSession`) throughout. Alembic manages migrations in `backend/alembic/versions/`, numbered sequentially as `NNN_description.py`. Current revision: `080_task_command_created_by`.

Task lifecycle: `PENDING → QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED`

### Runtime configuration

Settings have two layers:
- `get_settings()` — reads `.env` / environment variables (cached with `@lru_cache`)
- `get_effective_settings()` — applies DB-persisted overrides from `system_config` table on top

**Always use `get_effective_settings()`** in application code so runtime changes via `/api/config` take effect without restart. Secret config keys (`gitlab_bot_token`, `anthropic_api_key`, etc.) are stored encrypted.

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
