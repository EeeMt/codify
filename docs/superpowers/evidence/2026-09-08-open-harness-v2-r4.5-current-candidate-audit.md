# Open-Harness V2 R4.5 当前 Candidate 审计边界

**复核日期：** 2026-09-08  
**Host：** `192.168.50.129`（开发环境，Docker context `remote`）  
**结论：** 技术审计项可复核；R4.5 未签署，R4.6 保持 `NO-GO`

本记录是当前 candidate 的收敛审计，不是 owner 批准或 release authorization。旧 generation
审计保留在[历史 R4.5 审计](2026-09-04-open-harness-v2-r4.5-security-release-audit.md)，不把旧
identity 误当作当前发布包。

## 当前 exact identity

| 项 | 当前值 |
| --- | --- |
| Runtime source anchor | `4249fcc4`；当前分支后续仅增加测试夹具与文档，不改变已部署 runtime |
| Profile / Verify | Profile 4 `v2-canary-0.6.11-four-harness`，generation `99`，状态 ready |
| Worker Kit | `0.6.16-linux-amd64-4866812149bd`；manifest SHA `4866812149bd240af4802ab1aa11b8364cc49b400a8d4a71d2721b8ac9ef5f9c` |
| Backend / NGINX | `sha256:029384d710497c768bd6ca23ef6fa62fcd4751670d03d7aa0c35d990e91ed81e` / `sha256:aa09c11639f0f5838c085006c0690344f32536c1dcbd91dda37681cd6e253f2` |
| Worker image | `127.0.0.1:5000/codify-worker/java21-maven@sha256:234582c692d1ebb00ba8e882160618c2258463149d968009ac81c545e63a538b` |
| Runtime Bundle | `216` / `c374ef5a009c53d2fc469a262e5cabcb23efff97f9d6176655992198bba946a7` |
| Current real Task | #539；Provider 4 `opencode-luna / gpt-5.6-luna`，`openai_responses`；`reasoning_effort=high` |

## 已由当前环境证明的边界

- Profile 4、Kit、四 Harness inventory、Backend/NGINX/Worker image 和 Bundle identity 已在真实
  Task snapshot 中一致；Backend/Scheduler/NGINX/Postgres healthy，没有 `pending`、`queued` 或
  `running` Task。
- Task #539 有连续 Canonical receipts `1..34`，11/11 reasoning `started → completed`，单段
  `5.204–6.349s`，最终 `+0/-0`、`commit_sha=null`，无远端写入；固定 8 行技术 evidence 见
  [当前真实 Task 矩阵](2026-09-08-open-harness-v2-current-bundle-real-task-matrix.md)。
- 当前 source 的 Backend lint、完整 Backend unit suite（`3419 passed, 4 skipped, 99 subtests`）、
  Frontend unit suite（`1748 passed`）、Frontend production build、受影响 Harness tests、shell
  syntax 和 `git diff --check` 均通过。
- 当前 Docker state 为 Images `20/9`、`7.991GB`、可回收 `961.5MB`，Build cache 可回收 `380MB`；
  未清理服务、volume、active/unknown Worker 或不确定归属的 image/archive。当前没有磁盘满触发。
- Provider/Task snapshot 只记录 endpoint、model、protocol 和 `credential_ref`，本记录不读取或复制
  API key。未执行 migration 078、`v2_only`、R5 或任何 release cutover。

这些证据证明 candidate 的运行时、交付和测试边界；它们不等价于 owner 签署、最小权限批准或签名发布包。

## 仍需 owner 提供的 R4.5 输入

| Owner | 当前状态 | 未能从本 workspace 推导的结果 |
| --- | --- | --- |
| Provider/GitLab/OAuth credential owner | 未签署 | 最小权限 scope、有效凭据来源、最近轮换时间、撤销/恢复流程和账户控制确认 |
| Migration owner | 未签署 | 数据库备份/恢复点、migration 078 执行决定，以及 Provider 11/历史引用的复验计划 |
| Release owner | 未签署 | 精确 release notes、签名 package/manifest、签名 identity，并绑定上表 exact identity |
| Operations owner | 未签署 | Kit/image retention 与退役日期、维护窗口、rollback owner、观察窗口 |
| Independent reviewer | 未签署 | 当前 R4.3–R4.5 P0/P1、例外和明确的 R4.6 `GO`/`NO-GO` |

在上述输入到位并绑定当前 identity 前，不能把开发 Host 健康、测试通过、真实 Task 成功或 Docker
可回收空间当作 release authorization。系统继续保持 `dual_canary`；R4.6、migration 078、`v2_only`
和 R5 保持未执行。
