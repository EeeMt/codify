# Codify 内网离线迁移实施方案

本文档说明如何把 Codify 从有公网的环境迁移到无公网的内网环境，覆盖镜像与 Worker Kit 的导出、内网部署、内网侧的开发与测试，以及内网重新构建镜像。

> 适用场景：目标环境无法访问 PyPI、npmjs、Docker Hub、GitHub、claude.ai 等任何公网资源。

---

## 目录

- [1. 总览](#1-总览)
- [2. 依赖清单](#2-依赖清单)
- [3. 在线环境导出（Phase A）](#3-在线环境导出phase-a)
- [4. 内网环境部署（Phase B）](#4-内网环境部署phase-b)
- [5. 内网开发环境（Phase C）](#5-内网开发环境phase-c)
- [6. 内网重新构建镜像（Phase D）](#6-内网重新构建镜像phase-d)
- [7. 特殊组件处理](#7-特殊组件处理)
- [8. 验证清单](#8-验证清单)
- [9. 日常维护与更新流程](#9-日常维护与更新流程)
- [10. 故障排查](#10-故障排查)

---

## 1. 总览

### 1.1 迁移分层

| 层 | 用途 | 包含内容 |
|----|------|----------|
| 应用镜像 | 部署运行 | `codify-backend:latest`、`codify-nginx:latest`、`postgres:16-alpine` |
| 项目运行镜像 | Worker 容器 | 由 `config/worker-images.txt` 显式列出，默认不导出 |
| Worker Kit | Harness CLI 与编排脚本 | `kits/codify-worker-kit-<version>-linux-<arch>-<manifest-prefix>.tar.gz` 与同名 `.sha256` |
| 宿主机二进制 | Codex 等固定 CLI | 随包分发，登记在 `config/worker-binaries.txt` |
| 源码 | 内网开发与重新构建 | Git 仓库 |

导出与打包由 `deploy/offline-bundle/scripts/` 下的脚本完成，入口目标是 `make offline-bundle-export`。

### 1.2 内网必备基础设施

| 组件 | 要求 | 备注 |
|------|------|------|
| Docker Engine | 24.0+ | 需要 `docker load` 与 `docker compose` |
| Docker Compose | v2.x | plugin 模式或独立二进制 |
| GitLab | 内网实例 | Codify 的 MR / issue 操作目标 |
| LLM API | Claude 兼容端点 | 内网网关或兼容服务 |
| 存储 | 按实际包体积预留 | 镜像、Kit、数据库、工作区 |
| Python | 3.11+ | 仅内网开发与测试需要 |
| Node.js | 22.x | 仅内网前端开发与构建需要 |

### 1.3 制品身份约定

- 应用镜像用可变 tag 分发（`codify-backend:latest`、`codify-nginx:latest`、`postgres:16-alpine`），加载后按 digest 核对。
- 项目运行镜像是 `codify-worker/<toolchain>:<release>` 形式的 tag，例如 `codify-worker/java21-maven:2026.07`；验收与发布冻结使用 `repo@sha256:...`，不以可变 tag 为准。
- Worker Kit 归档按内容寻址命名，文件名带 manifest 前缀：`codify-worker-kit-<version>-linux-<arch>-<sha12>.tar.gz`，同名 `.sha256` 是归档的完整性和安装边界。
- Harness CLI 由 Worker Kit 提供，运行镜像不再内置任何 CLI。

---

## 2. 依赖清单

### 2.1 Docker 镜像

`make offline-bundle-export` 默认导出三个应用镜像：

```
codify-backend:latest      后端 API + 调度器（共用同一镜像）
codify-nginx:latest        前端静态资源 + 反向代理
postgres:16-alpine         PostgreSQL 数据库
```

项目运行镜像默认不导出。把每个启用 Worker Profile 需要的镜像写到
`deploy/offline-bundle/config/worker-images.txt`（一行一个，复制
`worker-images.txt.example` 起步），导出脚本才会把它并入归档。例如：

```
codify-worker/java21-maven:2026.07
```

重新构建镜像时需要的基础镜像由各自的 Dockerfile 决定（`ubuntu:22.04`、`node:22-alpine`、`nginx:alpine`、`maven:3.9.9-eclipse-temurin-21`）。

### 2.2 Worker Kit

Worker Kit 是内容寻址的归档，包含四个 Harness CLI（`pi`、`opencode`、`claude`、`codex`）与 Codify 编排脚本。默认选择集是 `pi,opencode`，由 `WORKER_KIT_CLI_SELECTION` 控制。manifest 的 `harness_inventory` 逐 key 记录 availability 与 reason_code，未选择的 key 记为 `not_selected`，选中但缺 payload 记为 `missing_payload`。

### 2.3 Python 依赖

- 生产：`backend/requirements.txt`
- 测试：`backend/requirements-test.txt`
- E2E：`backend/tests/e2e/requirements-e2e.txt`

三个文件都用 `>=` 约束，仓库不带 wheels 目录，也不产出 wheels 包。内网要装 Python 依赖，需要自备与目标平台一致的 wheels 目录或内网 PyPI 镜像。

### 2.4 Node.js 依赖

见 `frontend/package.json`，24 个 production 依赖与 10 个 dev 依赖，传递依赖由 `package-lock.json` 锁定。仓库同样不导出 `node_modules`。

### 2.5 特殊二进制

| 文件 | 来源 | 用途 |
|------|------|------|
| 四个 Harness CLI | Worker Kit 归档 | worker 容器内 AI 代码生成，`/opt/codify/worker-kits/` 下 |
| `codex` | 随包分发的宿主机二进制 | Codex Harness，按 Profile 的 `harness_runtimes.codex` 只读挂载 |
| Chromium | Playwright `install chromium` | E2E 浏览器测试（可选） |

### 2.6 系统 APT 包

已 bake 到各 Docker 镜像中（见 `deploy/Dockerfile.backend`、`deploy/Dockerfile.frontend`、`deploy/Dockerfile.worker-java21-maven`、`deploy/Dockerfile.e2e`）。
如果只用预构建镜像，无需单独打包 APT 依赖。

---

## 3. 在线环境导出（Phase A）

> 以下所有操作在有互联网的机器上执行，工作目录是仓库根目录。

### 3.1 一键导出

```bash
make offline-bundle-export WORKER_KIT_VERSION=<release-version>
```

这个目标依次做四件事：

1. `build-app-images` 构建 backend 与 nginx 镜像；
2. 用 `linux/amd64` 和 `linux/arm64` 各跑一次 `deploy/worker-kit/export.sh`，产出两份 Kit 归档；
3. `deploy/offline-bundle/scripts/export-images.sh` 生成 `deploy/offline-bundle/images/codify-offline-images.tar.gz` 与 `images/SHA256SUMS`；
4. `deploy/offline-bundle/scripts/package-bundle.sh` 打包整个 `deploy/offline-bundle/` 目录。

结果是 `deploy/codify-offline-bundle.tar.gz` 和它旁边的 `deploy/codify-offline-bundle.tar.gz.sha256`。
`make export` 是同一目标的别名。

`package-bundle.sh` 会拒绝打包：镜像归档不存在、Kit 归档不存在、Kit 归档缺少 `.sha256`、Kit 文件名不带 manifest 前缀、Kit 内容清单与字节不一致。旧式不带 manifest 前缀的 Kit 归档会被跳过并打印警告。

### 3.2 分步导出

```bash
# 只导出指定平台的 Kit
make worker-kit-export \
  WORKER_KIT_VERSION=<release-version> \
  WORKER_KIT_PLATFORM=linux/amd64 \
  WORKER_KIT_CLI_SELECTION='pi,opencode,claude,codex'

# 只构建项目运行镜像
make worker-runtime-image-build \
  RUNTIME_IMAGE=codify-worker/java21-maven:2026.07 \
  WORKER_KIT_PLATFORM=linux/amd64

# 只重新生成镜像归档
deploy/offline-bundle/scripts/export-images.sh

# 只重新打包 bundle
deploy/offline-bundle/scripts/package-bundle.sh
```

`worker-kit-export` 还接受 `WORKER_KIT_OUTPUT_DIR`，以及逐 Harness 的
`WORKER_KIT_PI_CLI_VERSION`、`WORKER_KIT_OPENCODE_CLI_VERSION`、
`WORKER_KIT_CLAUDE_CLI_VERSION`、`WORKER_KIT_CODEX_CLI_VERSION`。
`WORKER_KIT_CLI_SELECTION=none` 表示不内置任何 CLI。

### 3.3 打包结构

```
deploy/offline-bundle/
├── docker-compose.yml              离线部署编排（只用预构建镜像）
├── README.md                       离线包说明与操作步骤
├── config/
│   ├── .env.offline.example        环境变量模板
│   ├── worker-images.txt.example   项目运行镜像清单模板
│   └── worker-binaries.txt.example 宿主机二进制清单模板
├── docs/
│   └── CONFIGURATION.md            变量说明与部署清单
├── images/
│   ├── codify-offline-images.tar.gz
│   └── SHA256SUMS
├── kits/
│   ├── codify-worker-kit-<version>-linux-amd64-<prefix>.tar.gz
│   └── codify-worker-kit-<version>-linux-arm64-<prefix>.tar.gz
└── scripts/
    ├── export-images.sh            在线侧：重新导出镜像归档
    ├── package-bundle.sh           在线侧：打包整个目录
    ├── load-images.sh              内网侧：加载镜像
    ├── install-worker-kit.sh       内网侧：安装 Worker Kit
    ├── verify-worker-runtime.sh    内网侧：逐 Harness 校验运行镜像
    ├── start.sh                    内网侧：启动
    ├── stop.sh                     内网侧：停止
    └── health-check.sh             内网侧：健康检查
```

### 3.4 传输

把 `deploy/codify-offline-bundle.tar.gz` 与 `deploy/codify-offline-bundle.tar.gz.sha256` 一起传到内网。
离线包里已经带有变量说明（`docs/CONFIGURATION.md`）与操作步骤（`README.md`），部署前先读这两个文件。

---

## 4. 内网环境部署（Phase B）

> 以下操作在内网目标机器上执行。只部署运行，不需要开发环境。

### 4.1 校验并解压

```bash
# 先校验顶层归档，Linux 用 sha256sum，macOS 用 shasum
sha256sum -c codify-offline-bundle.tar.gz.sha256
# macOS: shasum -a 256 -c codify-offline-bundle.tar.gz.sha256

tar xzf codify-offline-bundle.tar.gz
cd offline-bundle
```

校验通过之前不要执行包内任何脚本。`images/SHA256SUMS` 记的是归档文件名，可以直接校验：

```bash
cd images
shasum -a 256 -c SHA256SUMS
cd ..
```

### 4.2 配置环境变量

```bash
cp config/.env.offline.example config/.env.offline
vi config/.env.offline
```

模板里的关键项（模板中这些字段多为空值，按注释填入实际值）：

```env
# === 必填 ===
GITLAB_URL=http://gitlab.internal:8080         # 内网 GitLab 地址
GITLAB_BOT_TOKEN=glpat-xxxxx                   # GitLab Bot Token

ANTHROPIC_BASE_URL=http://llm-gateway.internal/v1  # 内网 LLM API 端点
ANTHROPIC_API_KEY=sk-xxxxx                     # LLM API Key
ANTHROPIC_MODEL=claude-sonnet-4-20250514       # 模型标识

SESSION_SECRET=生成一个随机字符串
CONFIG_ENCRYPTION_KEY=32字节以上随机字符串

POSTGRES_USER=codify
POSTGRES_DB=codify
POSTGRES_PASSWORD=强密码
DATABASE_URL=postgresql+asyncpg://codify:强密码@postgres:5432/codify

BACKEND_URL=http://codify.internal:8000
FRONTEND_URL=http://codify.internal:8880
WORKER_IMAGE=codify-worker/java21-maven:2026.07

# === 自签证书（如需要）===
CUSTOM_CA_BUNDLE=/etc/ssl/certs/custom-ca.crt
WORKER_CA_CERT_HOST_PATH=/opt/ca.crt           # 宿主机上 CA 证书路径
```

`BACKEND_URL` 与 `FRONTEND_URL` 会被 `scripts/health-check.sh` 读取，必须填真实可达地址。

### 4.3 加载镜像

```bash
./scripts/load-images.sh
```

脚本从 `images/codify-offline-images.tar.gz` 加载。加载后用 digest 核对结果：

```bash
docker images --digests | grep -E 'codify|postgres'
```

`config/worker-images.txt` 里列过的项目运行镜像也在同一归档中。如果某个 Worker Profile 的
`WORKER_IMAGE` 不在归档里，需要在每台 Worker 宿主机上单独加载。

### 4.4 安装 Worker Kit

在每台可能被 Worker Profile 选中的 Docker 宿主机上，以 root 安装：

```bash
sudo ./scripts/install-worker-kit.sh kits/codify-worker-kit-<version>-linux-amd64-<prefix>.tar.gz
```

安装器会先校验归档旁边的 `.sha256`，再把 Kit 解到 `/opt/codify/worker-kits/<version>-linux-amd64-<prefix>`，
并把目录收为 root 所有、其他用户不可写。目标目录已存在时安装器拒绝覆盖，所以升级要装到新版本路径。

### 4.5 逐 Harness 校验运行镜像

`verify-worker-runtime.sh` 是离线包里的兼容包装，它先校验已安装 Kit 的内容清单，再调用 Kit 自带的
`verify-runtime.sh`。`--kit` 与宿主机二进制路径都必须是 Docker 宿主机的路径。

```bash
# 逐个 Harness
./scripts/verify-worker-runtime.sh \
  --kit /opt/codify/worker-kits/<version>-linux-amd64-<prefix> \
  --image codify-worker/java21-maven:2026.07 \
  --harness-key claude \
  --smoke 'java -version && mvn -version'

# 冻结 V2 发布时，一次校验 Runtime Bundle 里的全部 Harness
./scripts/verify-worker-runtime.sh \
  --kit /opt/codify/worker-kits/<version>-linux-amd64-<prefix> \
  --image codify-worker/java21-maven:2026.07 \
  --runtime-manifest /srv/codify/releases/<release>/runtime-bundle.v2.json \
  --all-harnesses \
  --smoke 'java -version && mvn -version'
```

`--all-harnesses` 必须同时给 `--runtime-manifest`，且该文档的 schema 是
`codify.worker.runtime-manifest/v2` 或 `codify.worker.runtime-bundle/v2`。旧的
`--claude-host-path <host-claude-bin>` 形式仍然可用。

校验过镜像后，通过 Codify 再跑一次 Profile 级验证，让 Profile 记录不可变的 repo digest 与
`verified_at`：

```http
POST /api/worker-profiles/<profile-id>/verify-runtime
Content-Type: application/json

{"smoke_command":"java -version && mvn -version"}
```

### 4.6 启动服务

```bash
./scripts/start.sh
```

脚本要求 `config/.env.offline` 存在，并以 `--env-file config/.env.offline -f docker-compose.yml`
调用 Compose。手工启动时要带上同一个 `--env-file`，否则编排里的
`${WORKER_WORKSPACE_HOST_PATH:-/opt/codify-workspaces}` 这类插值取不到模板值：

```bash
docker compose --env-file config/.env.offline -f docker-compose.yml up -d
```

调度器是唯一在启动时执行数据库迁移的进程（`AUTO_MIGRATE=true`），backend 侧保持
`AUTO_MIGRATE=false`。

### 4.7 验证部署

```bash
./scripts/health-check.sh

# 手动验证
curl -s http://codify.internal:8000/health      # 应返回 200
curl -s -o /dev/null -w '%{http_code}' http://codify.internal:8880/   # 应返回 200

docker logs codify-backend --tail 20
docker logs codify-scheduler --tail 20

docker exec codify-postgres psql -U codify -d codify -c "SELECT version_num FROM alembic_version;"
```

### 4.8 自签证书

`deploy/offline-bundle/docker-compose.yml` 已经为 backend 与 scheduler 挂载
`/opt/ca.crt` 到 `/etc/ssl/certs/custom-ca.crt`，并把
`WORKER_CA_CERT_HOST_PATH`、`WORKER_VOLUME_MOUNTS` 传给调度器。

```bash
sudo cp your-ca.crt /opt/ca.crt
```

`.env.offline` 里设置：

```env
CUSTOM_CA_BUNDLE=/etc/ssl/certs/custom-ca.crt
WORKER_CA_CERT_HOST_PATH=/opt/ca.crt
```

不使用内网 CA 时，注释掉 compose 里指向 `/opt/ca.crt` 的那两处 bind mount；`CUSTOM_CA_BUNDLE` 由
compose 的 `environment` 固定为 `/etc/ssl/certs/custom-ca.crt`，在 `.env.offline` 里清空它不会生效。

没有真实内网 CA 时，在源码检出目录（导出前）用 `scripts/generate-test-ca.sh` 生成一次性测试 CA，
再把 `/tmp/codify-test-ca/ca.crt` 拷到目标宿主机。该脚本不在离线包内——`package-bundle.sh` 只打包
`deploy/offline-bundle/`：

```bash
scripts/generate-test-ca.sh /tmp/codify-test-ca 127.0.0.1 localhost
```

---

## 5. 内网开发环境（Phase C）

> 在内网机器上进行代码开发、单元测试与前端构建。仓库的导出脚本不产出 Python wheels 和
> `node_modules`，这一步要么连内网镜像源，要么自带离线依赖目录。

### 5.1 后端 Python 环境

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate

# 离线目录（自备，见 2.3）
pip install --no-index --find-links=/path/to/python-wheels -r requirements.txt
pip install --no-index --find-links=/path/to/python-wheels -r requirements-test.txt

python -c "import fastapi, sqlalchemy, uvicorn; print('OK')"
pytest --version
```

内网已有 PyPI 镜像时，直接 `pip install -r requirements.txt -r requirements-test.txt` 并从
`pip config set global.index-url` 指向镜像即可。

### 5.2 前端 Node.js 环境

```bash
cd frontend
npm ci
```

`npm ci` 需要能访问 npm registry 或内网 npm 镜像。完全离线时用自备的 `node_modules` 归档：

```bash
tar xzf /path/to/node_modules.tar.gz
```

### 5.3 运行测试

仓库根目录的 Makefile 提供统一入口：

```bash
make setup            # 后端 venv + 前端 npm 依赖
make test-backend     # 后端单元测试
make test-unit        # 后端 + 前端单元测试
make test-frontend    # 前端单元测试
make test-mock-e2e    # 不需要外部服务的 mock E2E
```

### 5.4 本地开发服务器

```bash
# 后端（需要一个可用的 PostgreSQL，可用内网部署的 postgres）
cd backend
export DATABASE_URL=postgresql+asyncpg://codify:codify_password@localhost:5432/codify
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm run dev
```

---

## 6. 内网重新构建镜像（Phase D）

> 适用场景：在内网修改代码后重新构建镜像。

### 6.1 准备基础镜像

`Dockerfile.backend`、`Dockerfile.frontend`、`Dockerfile.worker-java21-maven` 的 FROM 层分别是
`ubuntu:22.04`、`node:22-alpine`、`nginx:alpine`、`maven:3.9.9-eclipse-temurin-21`。
把这些基础镜像在有网机器上 `docker save` 后带进内网并 `docker load`。

### 6.2 构建命令

```bash
# backend 与 nginx
make build-app-images

# 项目运行镜像
make worker-runtime-image-build RUNTIME_IMAGE=codify-worker/java21-maven:<release>
```

`build-app-images` 在 `deploy/` 下执行 `docker-compose --env-file .env.test build`；
`worker-runtime-image-build` 执行
`docker build --platform $(WORKER_KIT_PLATFORM) -f deploy/Dockerfile.worker-java21-maven -t "$(RUNTIME_IMAGE)"`。

两个 Dockerfile 在构建阶段都要装包（backend 走 `pip install -r requirements.txt`，frontend 走
`npm ci`）。内网重新构建需要把 pip 与 npm 指到内网镜像源，或改用预置依赖目录的本地构建。
最简单的做法是让内网侧的 pip 与 npm 通过配置指向镜像源，不改 Dockerfile。

### 6.3 重新打包

内网构建出的镜像同样可以走离线包的导出流程：

```bash
deploy/offline-bundle/scripts/export-images.sh
deploy/offline-bundle/scripts/package-bundle.sh
```

---

## 7. 特殊组件处理

### 7.1 Worker Kit 与 Harness CLI

四个 Harness CLI 由 Worker Kit 提供，运行镜像只提供项目工具链（Java 21、Maven、Git、SSH、curl、CA 工具）。
Kit 的 manifest 逐 key 记录 availability 与 reason_code，`present` 的 key 记录路径、版本和 SHA-256。
worker 容器从 `/opt/codify/worker-kits/` 下已安装的 Kit 读取 CLI，没有从镜像或 `PATH` 隐式回退。
选择 absent Harness 的 Profile 或 Task 会在 API 侧得到 `harness_cli_unavailable`。

CLI 需要访问 LLM 端点，所以 `ANTHROPIC_BASE_URL` 必须指向内网可达的端点，worker entrypoint 会把这个变量传给 CLI。

### 7.2 Codex CLI

Codex CLI 是固定宿主机二进制，不在运行镜像里。随包分发后，在 `config/worker-binaries.txt` 中登记
`harness_key | host_path | container_path | version | sha256`，并按 Worker Profile 的
`harness_runtimes.codex` 只读挂载。不要依赖在线安装或可变的 `latest` tag。

### 7.3 Playwright / Chromium（E2E 测试）

仅在需要运行 E2E 浏览器测试时才需要。浏览器版本在 `deploy/Dockerfile.e2e` 中固定为
`playwright==1.52.0`。

```bash
export PLAYWRIGHT_BROWSERS_PATH=/path/to/playwright-browsers
```

不需要 E2E 测试时跳过这一节。

### 7.4 Maven 仓库缓存

Worker 容器可能需要构建 Java/Maven 项目，Maven 默认从 Maven Central 下载依赖。

**方案 A：预热 .m2 仓库**（推荐）

```bash
# 在有网环境针对目标项目执行一次构建
mvn dependency:go-offline -f /path/to/target-project/pom.xml

# 打包 .m2 仓库
tar czf maven-repo.tar.gz -C ~/.m2 repository/
```

内网侧解压到宿主机：

```bash
sudo mkdir -p /opt/maven-repo
sudo tar xzf maven-repo.tar.gz -C /opt/maven-repo
```

Maven 缓存与 `settings.xml` 没有专用配置项，用通用的 `WORKER_VOLUME_MOUNTS` 挂到相同的容器路径：

```env
WORKER_VOLUME_MOUNTS=[{"host_path":"/opt/maven-repo","container_path":"/home/codify/.m2/repository","mode":"rw"},{"host_path":"/opt/maven-settings.xml","container_path":"/home/codify/.m2/settings.xml","mode":"ro"}]
```

**方案 B：内网 Maven 私服**（Nexus/Artifactory）

把宿主机上的 `settings.xml` 按上面的方式挂载到 `/home/codify/.m2/settings.xml`，由私服提供依赖。

### 7.5 自签 CA 证书

内网环境通常使用自签 CA。Codify 通过 `CUSTOM_CA_BUNDLE` 统一处理，自动为以下组件信任 CA：

| 组件 | 机制 |
|------|------|
| 系统 (curl/wget) | `update-ca-certificates` |
| Git | `http.sslCAInfo` |
| Python (httpx/requests) | `REQUESTS_CA_BUNDLE` + `SSL_CERT_FILE` |
| Node.js / Claude CLI | `NODE_EXTRA_CA_CERTS` |
| JDK (Maven/Gradle) | `keytool -importcert` |

**配置步骤**：

1. 把 CA 证书放到宿主机 `/opt/ca.crt`；
2. `.env.offline` 设置 `CUSTOM_CA_BUNDLE=/etc/ssl/certs/custom-ca.crt`；
3. `.env.offline` 设置 `WORKER_CA_CERT_HOST_PATH=/opt/ca.crt`；
4. 确认 `docker-compose.yml` 里 backend 与 scheduler 的 CA bind mount 指向同一个宿主路径。

测试用 CA 由 `scripts/generate-test-ca.sh` 生成，脚本自带 `openssl verify` 校验，生成的
`ca.crt`/`ca.key` 只用于本地或隔离开发环境，不得用于生产。

---

## 8. 验证清单

### 8.1 部署验证

| # | 检查项 | 命令 | 预期结果 |
|---|--------|------|----------|
| 1 | 镜像加载 | `docker images \| grep -E 'codify\|postgres'` | 应用镜像与已列出的运行镜像都在 |
| 2 | 服务启动 | `docker ps \| grep codify` | backend、scheduler、nginx、postgres 都在 running |
| 3 | 后端健康 | `curl http://codify.internal:8000/health` | 200 |
| 4 | 前端加载 | `curl -o /dev/null -w '%{http_code}' http://codify.internal:8880/` | 200 |
| 5 | 数据库迁移 | `docker exec codify-postgres psql -U codify -c "SELECT version_num FROM alembic_version;"` | 有版本号 |
| 6 | Kit 安装 | `ls /opt/codify/worker-kits/` | 目标版本目录存在且 root 所有 |
| 7 | 逐 Harness 校验 | `./scripts/verify-worker-runtime.sh --kit <kit> --image <image> ...` | 退出码 0 |
| 8 | GitLab 连通 | Dashboard → 项目列表 | 能看到项目 |
| 9 | Worker 容器 | 创建测试任务 | 容器能启动并完成 |
| 10 | LLM 连通 | Worker 容器执行任务 | Harness CLI 能调用 API |

### 8.2 开发环境验证

| # | 检查项 | 命令 | 预期结果 |
|---|--------|------|----------|
| 1 | Python 依赖 | `python -c "import fastapi"` | 无报错 |
| 2 | 后端测试 | `make test-backend` | 全部通过 |
| 3 | Mock E2E | `make test-mock-e2e` | 全部通过 |
| 4 | 前端测试 | `make test-frontend` | 全部通过 |
| 5 | 前端构建 | `cd frontend && npm run build` | 构建成功 |

### 8.3 镜像重新构建验证

| # | 检查项 | 命令 | 预期结果 |
|---|--------|------|----------|
| 1 | 应用镜像 | `make build-app-images` | 构建成功 |
| 2 | 运行镜像 | `make worker-runtime-image-build` | 构建成功 |
| 3 | 重新部署 | `docker compose --env-file config/.env.offline -f docker-compose.yml up -d` | 服务正常 |

---

## 9. 日常维护与更新流程

### 9.1 代码更新

```bash
# 有网环境：生成增量包
git bundle create update-$(date +%Y%m%d).bundle origin/main ^last-transferred-commit

# 内网环境：应用
git bundle verify update-YYYYMMDD.bundle
git pull update-YYYYMMDD.bundle main
```

### 9.2 依赖更新

`requirements.txt` 或 `package.json` 变更后，重新同步内网镜像源，或重新制作离线依赖目录。
仓库的导出脚本不处理这一层。

### 9.3 镜像与 Worker Kit 更新

```bash
# 有网环境
make offline-bundle-export WORKER_KIT_VERSION=<new-version>

# 内网环境
sha256sum -c codify-offline-bundle.tar.gz.sha256
tar xzf codify-offline-bundle.tar.gz
cd offline-bundle
./scripts/load-images.sh
sudo ./scripts/install-worker-kit.sh kits/codify-worker-kit-<new-version>-linux-amd64-<prefix>.tar.gz
./scripts/verify-worker-runtime.sh --kit /opt/codify/worker-kits/<new-version>-linux-amd64-<prefix> \
  --image <runtime-image> --all-harnesses \
  --runtime-manifest /srv/codify/releases/<release>/runtime-bundle.v2.json
./scripts/start.sh
```

Kit 升级装到新版本路径，旧目录保留，便于回滚。

### 9.4 导出单个已验收 Task 的 Runtime Bundle

```bash
make worker-runtime-bundle-export \
  TASK_ID=<verified-task-id> \
  BUNDLE_EXPORT_DIR=/opt/codify-archives/runtime-bundles
```

目标目录必须存在且可写，导出结果以 `runtime-bundle-v2-<digest>` 目录原子发布。只给
`TASK_ID` 或 `BUNDLE_DIGEST` 其中一个，两个都给或都不给会直接报错退出。

---

## 10. 故障排查

### Q: `docker load` 报错 "no space left on device"
**A**: 清理 Docker 未使用的镜像和容器：`docker system prune -a`

### Q: pip install --no-index 找不到某个包
**A**: 检查离线依赖目录里是否有该包及其全部传递依赖。常见遗漏：`setuptools`、`wheel`、`pip` 自身。

### Q: `npm run build` 报模块找不到
**A**: 确认依赖目录是在相同的 Node.js 大版本下安装的。版本差异大时改用内网 npm 镜像重新 `npm ci`。

### Q: `package-bundle.sh` 报 "Worker kit archive not found"
**A**: 先跑 `make worker-kit-export` 或 `make offline-bundle-export`。归档必须落在
`deploy/offline-bundle/kits/`，并带同名 `.sha256`。

### Q: `install-worker-kit.sh` 报 "Worker kit identity is already installed"
**A**: 目标版本目录已存在。安装器不覆盖既有 Kit，请换新版本号，或先确认旧 Kit 可以删除。

### Q: `verify-worker-runtime.sh` 报 "--all-harnesses requires --runtime-manifest"
**A**: 全量校验必须同时给 Runtime Bundle 或 Runtime Manifest 文档，不能只给 Kit 归档。

### Q: Worker 容器无法访问 GitLab
**A**: 检查：
1. `GITLAB_URL` 是否是内网可达地址；
2. Worker 容器 DNS 能否解析 GitLab 主机名；
3. 使用自签证书时，`CUSTOM_CA_BUNDLE` 与 `WORKER_CA_CERT_HOST_PATH` 是否都已配置，且宿主机上 `/opt/ca.crt` 存在。

### Q: Harness CLI 报 API 连接失败
**A**: 检查：
1. `ANTHROPIC_BASE_URL` 是否指向内网 LLM 端点；
2. Worker 容器能否 `curl` 该端点：`docker exec <worker-container> curl -s $ANTHROPIC_BASE_URL/models`；
3. 使用自签证书时确认 `NODE_EXTRA_CA_CERTS` 已在容器内生效。

### Q: Profile 报 `harness_cli_unavailable`
**A**: 该 Profile 选择的 Harness 在目标宿主机上不可用。检查 Kit manifest 里该 key 的 availability
与 reason_code（`not_selected` 或 `missing_payload`），必要时用包含该 Harness 的选择集重新导出并安装 Kit。

### Q: 前端 Dashboard 能打开但 API 请求全部 502
**A**: 检查 nginx 到 backend 的代理连通性：

```bash
docker exec codify-nginx curl -s http://backend:8000/health
```

失败时检查 Docker 网络与 backend 容器状态。
