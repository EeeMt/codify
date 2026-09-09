# Open-Harness V2 R4.6 开发环境硬切证据

**执行日期：** 2026-09-09  
**范围：** Codify 开发环境 `remote` Docker context
**结论：** R4.6 在开发环境 `GO`；线上 R5 未执行。

本记录只保留可复核的身份、状态和结果，不包含 GitLab、Provider、OAuth 或模型凭据。逐条事件仍以远端
Task receipt、runtime archive、数据库和 GitLab MR 为准。

## 1. RC 与测试

- 代码 RC source anchor：`504f937d1bc11450a07069235501d8614c8c37d8`。
- 本轮相关提交：`f50f901a`（Analytics fixture）、`504f937d`（开发环境切换 `v2_only`）、
  `36d2543b`（开发 GitLab 地址修正）、`5bd12616`（Scheduler 启动自动迁移与 NGINX health gate）。
- `dev` 未 push；文档提交前相对 `origin/dev` 为 ahead 66。
- Backend unit suite 分拆结果：主单元集 `3411 passed, 4 skipped`；Scheduler `5 passed`；Migration 068
  `6 passed`，合计 `3422 passed, 4 skipped`。
- Frontend：`80 files / 1753 passed`；production build、Backend lint、deploy shell syntax 和
  `git diff --check` 均通过。

### Exact composition

| 组件 | 固定身份 |
| --- | --- |
| Backend image | `sha256:2d6b8ebab2d9a9b51704918817bae007de20530fa50e9140d5f2045eba8dfad3` |
| NGINX image | `sha256:d0247713acfa678eb22463f13aecc1a77f3acb663bb7a4df06027c1f7a7d36e3` |
| Worker image | `127.0.0.1:5000/codify-worker/java21-maven@sha256:234582c692d1ebb00ba8e882160618c2258463149d968009ac81c545e63a538b` |
| Worker image local ID | `sha256:b07ac48b129c35876c044079f8e9cd7aa7558dbb0ade2e50e856d4ab980f5e71` |
| Worker Kit | `0.6.16`, `/home/codify/worker-kits/0.6.16-linux-amd64-4866812149bd` |
| Kit manifest | `4866812149bd240af4802ab1aa11b8364cc49b400a8d4a71d2721b8ac9ef5f9c`，`linux/amd64` |

Backend/NGINX image 没有 OCI Git revision label，因此用构建时 source anchor 建立映射。远端没有可用的
`nginx:alpine` 基础镜像；NGINX 使用 `node:22-alpine` builder 加现有 `codify-nginx` runtime base
重建静态资源，未改变运行时服务配置。

Kit inventory：

| Harness | CLI version | path | sha256 |
| --- | --- | --- | --- |
| Claude | `2.1.153` | `/opt/codify-kit/harness/claude/claude` | `214f603f31942162dac9a65f18d43b3ac646ae215240fad481c4aad6c60f2e38` |
| Codex | `0.146.0` | `/opt/codify-kit/harness/codex/bin/codex` | `2e863156ed35ecc5253b1e2f907a9143077b9f7cb51942070c61996471ff6e04` |
| OpenCode | `1.18.19` | `/opt/codify-kit/harness/opencode/opencode` | `fd4cfd76ca65a706d0138886dd23094dd07e35460080024b1467baaf32dcee2e` |
| Pi | `0.84.2` | `/opt/codify-kit/harness/pi/bin/pi` | `9a2d20fab3caacbe3517d91e59d495ccc49fd4b51a1a72dcec6e8c1f4b7d6ab2` |

## 2. Hard-cut 维护窗口

- Backend、Scheduler、NGINX 使用开发 RC；Backend/Scheduler `/health` 均报告
  `harness_execution_mode=v2_only`，preflight 返回 `PREFLIGHT OK`。
- R4.6 首次切换时数据库 revision 从 `077_v2_worker_kit_identity` 迁移到
  `078_remove_provider_driver`；随后提交 `5bd12616` 将正常启动拓扑收敛为 Backend
  `AUTO_MIGRATE=false`、Scheduler `AUTO_MIGRATE=true`，并让 NGINX 等待 Scheduler health。远端重启验证中
  Scheduler 日志执行了 migration 检查并报告 database up to date，未重复改动 078 数据。
- PostgreSQL 备份保留在远端 `/tmp/codify-r4-6-precut.dump`：49,003,240 bytes，SHA256
  `1cca441b4e42d7d9c0aab38a8dbc785acaedfaed0736f67554f8e1a132dd5212`；`pg_restore -l` 输出 463 行，
  其中 448 行为非注释 TOC entry。
- Migration 078 删除了唯一命中的 `openai_compatible + anthropic_messages` Provider（原 Provider 11），
  删除 `provider_driver` 列；当前命中数为 0，受外键影响的历史 Task 中 `provider_id IS NULL` 为 24。
- Task #543 在切换前按原参数取消；切换后以同一 Issue、预约时间、Provider、`freeform/fresh` 和 V2
  Profile 重建为 Task #551。Task #551 保持 `pending`，未被 promotion。
- Profile 4 `v2-canary-0.6.11-four-harness` 已启用并设为全局默认，默认 Harness 为 Pi；一次完整
  `Verify` 后 generation 为 103，四 Harness inventory 均 `present`。
- 当前 readiness：fingerprint `ed0a0a7627e243bc104329ce57c20474cd22a334004be69addea89c4a321e456`，
  `status=ready`，`ready_until=null`，`check_generation=6`，Kit/image identity 与上表一致。
- 开发配置原为不可解析的 `gitlab.example.test`；已按 `deploy/dev-env-info.md` 修正为
  `http://192.168.50.129:8080`（提交 `36d2543b`）。从 Backend 容器经现有加密运行时 token 读取 MR
  成功，未在日志或文件中输出 token。

## 3. 四 Harness release smoke

| Harness / Task | 结果与关键断言 | Delivery / MR |
| --- | --- | --- |
| Pi / #544 | `completed`；steer command HTTP 201，DB `delivered`，native request `1000001`，无 rejection；receipts 2135，`finalization=1`，`terminal=1`，`reasoning_interrupted=0` | commit `8f20fd9011a4309210595692d6f4e1f3e752806e`，canonical `remote_sha` 相同，MR !104 `opened / mergeable` |
| Claude / #546 | `completed`；receipts 125，连续 seq 1–125，`finalization=1`，`terminal=1`，`reasoning_interrupted=0` | commit `7675097febf75ac8e43bde76de1f43eddd2b4ba7`，canonical `remote_sha` 相同，MR !106 `opened / mergeable` |
| Codex / #547 | `completed`；zero-change，`commit_sha=null`，`head_sha=start_sha`，diff 0，push `not_needed`；receipts 28，`finalization=1`，`terminal=1` | 没有伪造 commit/SHA；Issue 的既有 MR !107 未作为本 Task 的新 delivery |
| OpenCode / #548 | 在 `last_seq>5` 后取消；`cancelled`，`MessageAbortedError`；同一 reasoning id `started → interrupted`，`reason=aborted`，无 completed；receipts 82，`finalization=1`，`terminal=1` | push `not_attempted`；MR !108 `opened / draft_status`，与取消探针一致 |

四条 Task 的 Snapshot 均为 `codify.worker.harness/v2`、Profile 4、Worker image、Kit 0.6.16；对应
Bundle 为 #218（Pi）、#220（Claude）、#221（Codex）、#219（OpenCode），均为 orchestration `1.0.0`、
size 665600 bytes。Task #544/#546 的 GitLab MR 通过认证 API 返回 `can_be_merged / mergeable`，并与
canonical remote SHA 一致。

### Archive 与浏览器验收

| Task | archive | size / SHA256 |
| --- | --- | --- |
| #544 | `/opt/codify-archives/task-544-runtime-archive.tar.gz` | 165610 / `5b2cf181de379277726b1459abb16e4a31c5e112c3eb1e5e04bc9580ddaf5349` |
| #546 | `/opt/codify-archives/task-546-runtime-archive.tar.gz` | 38448 / `4a5bd90ca1163da522d7a0e9950d324485217e7cada3a33689872ff515640acd` |
| #547 | `/opt/codify-archives/task-547-runtime-archive.tar.gz` | 17188 / `7dc9036ea2d9080477561185bbc696c76e0e3b6ad21b554ac36e497b931de16` |
| #548 | `/opt/codify-archives/task-548-runtime-archive.tar.gz` | 12107 / `a006f915fec1d4eb6b842203565b775ca562d85f9b97c7a9017c1a00f8cf8878` |

浏览器在实际开发地址打开 Task #548，刷新/重连后仍显示 `Cancelled`、`Thinking interrupted`、Profile 4、
OpenCode 和 MR !108；打开历史 Task #399 显示 `Legacy V1 · Read-only`，历史详情和 raw logs 可读。

Task #545 是 OpenCode 的过早取消预检：在 attempt 产生有效事件前取消，随后无 archive，因此不计入上述
release smoke；它仅保留为“取消接口可达”的负向证据。

## 4. V1 fail-closed 探针

历史 V1 Task #399 的读取返回 `codify.worker.harness/v1`、`legacy=true`、`read_only=true`、
`reason=legacy_contract_not_executable`。

- V1 create 与 resume/continue：HTTP 422，detail code `legacy_contract_not_executable`；
- V1 retry：HTTP 409，同一 detail code；
- V1 execute 与 schedule：HTTP 400，因目标 Task 已是 terminal lifecycle，未进入执行路径；
- 探针没有创建新 Task、Worker 或锁。

## 5. 清理与退出结论

- 当前活动 Task：`pending=1`（仅 #551），`queued=0`，`running=0`；Issue execution lock=0。
- 当前没有标准命名的 Codify Worker 容器；旧 `quirky_allen` 已确认是无挂载、无重启策略的 OpenCode
  API 诊断容器，已精确删除，未执行 Docker prune，Worker image 和 Kit 未删除。
- 没有遗漏 terminal、finalization 或 archive；四个 smoke archive 均存在且可读。
- R4.6 开发环境结论为 `GO`。R5 仍需独立维护窗口、同一套 exact identity 和线上四 Harness smoke，
  不得把本证据当作线上已切换证明。

## 6. 安全边界

本文件、runtime archive 和提交中没有写入原始凭据。浏览器自动化过程中一次工具 trace 曾回显开发管理员
密码；该值未写入文件或最终答复，但应立即轮换该开发凭据。
