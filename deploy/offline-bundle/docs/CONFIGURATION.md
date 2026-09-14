# Offline Deployment Configuration Guide

This document explains the configuration items required by `config/.env.offline`.

## 1. Host prerequisites

- Docker Engine installed and running
- Docker Compose available
- Enough disk space for:
  - Docker images
  - PostgreSQL data volume
  - task logs and generated repositories
- The host user can access `/var/run/docker.sock`
- Create the daemon-local Issue workspace root and the control-plane CI staging directory:
  ```bash
  mkdir -p /opt/codify-workspaces /opt/codify-ci-failures
  ```
- (Optional) If your environment uses a custom CA, place the PEM file at `/opt/ca.crt`. The compose file mounts this file into `backend` and `scheduler` with `create_host_path: false`, so the stack fails to start while the file is missing.
- (Optional) `docker-compose.yml` also binds `${DOCKER_CERTS_HOST_PATH:-/opt/codify-docker-certs}` read-only into both services. It stays unused while `DOCKER_TLS_CA`, `DOCKER_TLS_CERT`, and `DOCKER_TLS_KEY` are empty.

## 2. Network prerequisites

The deployed services must be able to reach:

- GitLab API/UI at `GITLAB_URL`
- A Claude-compatible API endpoint at `ANTHROPIC_BASE_URL`

If the environment is fully offline, both endpoints must exist inside the intranet.

## 3. Required configuration

### GitLab

- `GITLAB_URL`: base URL of the GitLab instance
- `GITLAB_BOT_TOKEN`: token used for webhook handling, repository clone/push, issue comments, and MR creation
- `GITLAB_ADMIN_TOKEN`: token used for managed webhook setup / status checks

### Claude-compatible API

- `ANTHROPIC_BASE_URL`: base URL of the internal/external Claude-compatible endpoint
- `ANTHROPIC_API_KEY`: API key for that endpoint
- `ANTHROPIC_MODEL`: model identifier to use for new tasks
- `CLAUDE_MAX_TURNS`: max agentic turns allowed per task

### Application secrets

- `SESSION_SECRET`: signs dashboard session tokens. Generate a long random value.
- `CONFIG_ENCRYPTION_KEY`: encrypts sensitive configuration stored in the database. When left empty the app falls back to `SESSION_SECRET`; if both are missing or still hold the built-in default, saving a secret from the Config page fails.
- `SECRET_KEY`: the application never reads it, and the template no longer ships it. `SESSION_SECRET` is the value that matters.

Values written through the dashboard Config page are encrypted with Fernet before they reach `system_config`. The encrypted keys are `gitlab_bot_token`, `gitlab_admin_token`, `anthropic_api_key`, `oidc_client_secret`, `mattermost_bot_token`, and `alert_webhook_url`. Every other key in `system_config` is stored as plain text.

### URLs

- `BACKEND_URL`: API URL used for webhook callback generation
- `FRONTEND_URL`: dashboard URL used for task links posted back to GitLab

### Database

- `POSTGRES_USER`: PostgreSQL username, usually `codify`
- `POSTGRES_DB`: database name
- `POSTGRES_PASSWORD`: password for the `codify` PostgreSQL user
- `DATABASE_URL`: backend/scheduler connection string; keep it consistent with the PostgreSQL values above

### Worker/scheduler

- `WORKER_IMAGE`: must match the loaded worker image tag
- `WORKER_WORKSPACE_HOST_PATH`: absolute Issue workspace root (default `/opt/codify-workspaces`). Worker containers get this path as their workspace root on the Docker host, and every host in the deployment must use the same value. In `docker-compose.yml` it also anchors the CI staging bind, which `backend` and `scheduler` mount at `<path>/ci-failures`.
- `CI_FAILURE_BUNDLE_HOST_PATH`: control-plane staging directory for CI failure inputs (default `/opt/codify-ci-failures`). It is bound into `backend` and `scheduler`; worker containers receive runtime bundles through the Docker API instead.
- `MAX_CONCURRENCY`: max number of concurrent tasks (default `3`)
- `TASK_TIMEOUT_PEAK_SECONDS`: max seconds a task may run during the peak window (default `1800`)
- `TASK_TIMEOUT_OFF_PEAK_SECONDS`: max seconds a task may run outside the peak window (default `3600`)
- `TASK_TIMEOUT_PEAK_START`: peak window start in `HH:mm` (`Asia/Shanghai`, default `09:00`)
- `TASK_TIMEOUT_PEAK_END`: peak window end in `HH:mm` (`Asia/Shanghai`, default `18:00`)
- `SCHEDULER_INTERVAL`: polling interval in seconds (default `5`)
- `DEFAULT_TARGET_BRANCH`: fallback branch when a task does not specify one (default `main`)
- `HARNESS_EXECUTION_MODE`: not in the template. `v2_only` is the only accepted value, and both `backend` and `scheduler` fall back to it.
- `SESSION_STORAGE_ROOT`: fallback location for Issue session data when no workspace path can be derived (default `/var/codify/sessions`). Issues created with a workspace persist under `WORKER_WORKSPACE_HOST_PATH` instead.

### Slot capacity

- `SLOT_MAX_TASKS`: max tasks allowed per 1-hour time window (default `0` = unlimited)
- `SLOT_MAX_TASKS_ENFORCE`: when `true`, new tasks are rejected once the slot is full; when `false`, only a warning is logged (default `false`)

These limits are also configurable at runtime via the dashboard Config page, and a value stored there wins over the environment.

### How the compose file reads this file

`scripts/start.sh` runs `docker compose --env-file config/.env.offline -f docker-compose.yml up -d`, so `${...}` references in the compose file resolve from `config/.env.offline`. Start the stack through that script; a bare `docker compose up` falls back to the `${VAR:-default}` values in the compose file.

Variables listed under a service's `environment:` take precedence over `env_file`. Most of them interpolate from the same file, so editing `config/.env.offline` still changes the container value. These are pinned outright and cannot be changed from the env file:

| Pinned value | Services |
|---|---|
| `DOCKER_HOST=unix:///var/run/docker.sock` | `backend`, `scheduler` |
| `AUTO_MIGRATE=false` | `backend` (the `migrate` service also forces `false`) |
| `AUTO_MIGRATE=true` | `scheduler` (single startup migration owner) |
| `COOKIE_SECURE=false` | `backend` |
| `CUSTOM_CA_BUNDLE=/etc/ssl/certs/custom-ca.crt` | `backend`, `scheduler` |

## 4. Optional configuration

### Retry / alerting

- `MAX_RETRIES`
- `RETRY_DELAY`
- `ALERT_ON_FAILURE`
- `ALERT_WEBHOOK_URL`

### Mattermost notifications

- `MATTERMOST_SERVER_URL`
- `MATTERMOST_BOT_TOKEN`

These are optional. Configure them if you want Mattermost integration available immediately after the offline deployment starts. Notification profiles themselves are managed in the dashboard and stored in PostgreSQL.

### Worker container mounts

- `WORKER_CA_CERT_HOST_PATH`: absolute path on the Docker host to a PEM-encoded CA cert file. When set, this certificate is automatically mounted into every spawned worker container and trusted by git, Python, Node.js, and the JDK.
- `WORKER_VOLUME_MOUNTS`: JSON array of extra volume mounts to inject into worker containers. Each element has `host_path`, `container_path`, and `mode` keys (e.g., `[{"host_path": "/data/cache", "container_path": "/cache", "mode": "rw"}]`).

### Custom CA certificate

- `CUSTOM_CA_BUNDLE`: path inside the container to a PEM-encoded CA certificate file. The setting itself has no default; `docker-compose.yml` pins it to `/etc/ssl/certs/custom-ca.crt`, the path the host certificate is mounted at

Use this when GitLab, the LLM gateway, Mattermost, or any other service uses a certificate signed by an internal or self-signed CA.

**The CA cert bind mount is pre-configured** in `docker-compose.yml` for both `backend` and `scheduler`:
```yaml
volumes:
  - type: bind
    source: /opt/ca.crt
    target: /etc/ssl/certs/custom-ca.crt
    read_only: true
    bind:
      create_host_path: false
```

**Setup:** place your PEM CA certificate at `/opt/ca.crt` on the Docker host. If the path differs, edit `docker-compose.yml` to match. If no CA is needed, comment out the bind mount block and remove `CUSTOM_CA_BUNDLE` from the environment block.

`CUSTOM_CA_BUNDLE` is pinned to `/etc/ssl/certs/custom-ca.crt` by the `environment:` blocks of `backend` and `scheduler`, which override `env_file`. Setting the variable in `config/.env.offline` does not move the path the containers use; change the compose value together with the bind target if you need a different one.

When this variable is set, the following components inside every spawned **worker container** will trust the CA:

| Component | Mechanism |
|-----------|-----------|
| System (curl, wget, etc.) | `update-ca-certificates` installs the cert to the system store; skipped when the container runs with a mounted Kit |
| git | `http.sslCAInfo` |
| Python (requests / httpx) | `REQUESTS_CA_BUNDLE` + `SSL_CERT_FILE` env vars |
| Node.js / Claude CLI | `NODE_EXTRA_CA_CERTS` env var |
| JDK (Maven, Gradle, Java) | `keytool -importcert` into `$JAVA_HOME/lib/security/cacerts`; skipped when the container runs with a mounted Kit, where the runtime image owns its truststore |

The entrypoint applies this only when the file exists inside the worker container. If `CUSTOM_CA_BUNDLE` is unset, or it points at a path that is not mounted into the worker, the entrypoint falls back to `git config http.sslVerify=false`.

The **backend and scheduler** HTTP clients (GitLab API, Mattermost, OIDC) also use `CUSTOM_CA_BUNDLE` as the `verify=` parameter for all requests.

### OIDC / auth

Only configure these if the dashboard will use GitLab OIDC in the offline environment:

- `OIDC_ENABLED` (default `false`)
- `OIDC_ISSUER_URL`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET` (encrypted at rest when saved from the Config page)
- `OIDC_REDIRECT_URI`
- `COOKIE_SECURE` (default `true`; the `backend` service pins it to `false`)
- `COOKIE_SAMESITE` (default `lax`)
- `SESSION_COOKIE_NAME` (default `codify_session`)
- `SESSION_TTL_SECONDS` (default `28800`)

These keys are also persisted in `system_config` when changed from the Config page, and the stored value wins over the env file.

### Break-glass admin login

All three values are required; `break_glass_enabled` resolves to false when the username or the hash is empty.

- `AUTH_BREAK_GLASS_ENABLED` (default `false`)
- `AUTH_BREAK_GLASS_USERNAME`
- `AUTH_BREAK_GLASS_PASSWORD_HASH`: accepts `sha256$<hex_digest>` or `pbkdf2_sha256$<iterations>$<salt_hex>$<digest_hex>`

### Optional admin / page access defaults

- `AUTH_ADMIN_USERNAMES`
- `AUTH_ADMIN_GITLAB_GROUPS`
- `ALLOW_MONITOR_FOR_USERS`
- `ALLOW_SCHEDULE_OVERVIEW_FOR_USERS`
- `ALLOW_ANALYTICS_FOR_USERS`
- `ALLOW_OIDC_DIAGNOSTICS_FOR_USERS`

## 5. Deployment steps

1. Copy this bundle to the target host.
2. Create required host directories:
   ```bash
   mkdir -p /opt/codify-workspaces /opt/codify-ci-failures
   ```
3. Create `config/.env.offline` from the example template.
4. Load the exported images (`./scripts/load-images.sh`).
5. If using an internal CA, place the cert at `/opt/ca.crt` (or adjust the bind mount in `docker-compose.yml`). If not, comment out the bind mount and `CUSTOM_CA_BUNDLE`.
6. Start the stack: `./scripts/start.sh`.
7. Confirm health with `./scripts/health-check.sh`, which reads `BACKEND_URL` and `FRONTEND_URL` from `config/.env.offline` and prints the status code of `/health` and `/`. Both should print `200`. `./scripts/stop.sh` stops the stack against the same env file.
8. Log into the dashboard and verify runtime config.
9. Configure GitLab project webhooks if they are not already present.

## 6. Post-deployment checklist

- Health endpoint returns `200`
- Dashboard loads successfully
- Backend can list GitLab projects
- Scheduler is running without crash recovery errors
- A test task can create a worker container named `codify-<task_id>-issue<issue_id>`
- The worker can clone/push to GitLab and reach the LLM endpoint
