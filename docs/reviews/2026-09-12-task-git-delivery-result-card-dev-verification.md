# Task 交付结果卡方案调整 —— 开发环境验收记录

> 日期：2026-09-12
>
> 分支/HEAD：`dev @ 7de4cac4`（本次改动位于工作区，验收时按工作区构建镜像）
>
> 目标 Host：`192.168.50.129`（docker context `remote`）
>
> 触发改动：`docs/superpowers/specs/2026-09-04-task-git-delivery-reconciliation-design.md` 的方案调整
> （§4.2 术语、§8 表格、新增 §9.1–§9.4 展示语义与布局、§10.1 职责表）
>
> 结果：**通过**（前端/后端回归 + 真实 dev Task 页面证据）

## 1. 本次调整内容

| 位置 | 调整前 | 调整后 |
| --- | --- | --- |
| §4.2 / §8 / §9.1 | 恢复交付显示为「已有提交补交/确认」、「前序任务待交付提交」 | 统一显示为 **前序任务提交**，由 `push.status` 独立表达本次交付结果 |
| §9.2 摘要行 | HEAD SHA + 分支 + `+A/-D` 三个信息岛（`space-between`） | 两个视觉区域：左侧目标分支，右侧推送状态 + 变化摘要 |
| §9.2 提交行 | 摘要行单独展示 head SHA 与链接 | SHA 只在提交行展示；已确认链接落到对应提交行，未确认保留复制 |
| §9.2 分支 | 复用可点击 SHA 胶囊样式 | 图标 + 等宽文本，无交互样式 |
| §9.2 统计 | 文件统计独立成行，`+0/-0` 照常渲染 | 文件与行数合并为一段摘要，只显示非零项；采集到的全零显示「无净文件变化」，未采集显示「统计未采集」 |
| §9.2 失败 | 失败原因与状态同处一行并截断 300 字符 | 失败原因在摘要行下方占满可用宽度、完整换行 |
| §9.3 | 无（仅 V1 版一段文字） | 桌面 `minmax(0, 1fr) auto` 两列、窄屏纵向；移动端标题两行截断；44px 触摸目标；无横向滚动 |
| §9.4 / §10.1 | MR 展示「恢复交付列表」 | MR 展示「前序任务提交」列表，与 Task 详情同一归一化对象 |

## 2. 代码改动

| 模块 | 文件 | 改动 |
| --- | --- | --- |
| 结果卡 | `frontend/src/components/TaskResultPanel.vue` | `.git-delivery__summary` 两列网格；移除摘要行 HEAD SHA；`gitDeliveryCommitLinkSha` 把已确认链接落到 head 所在提交行；`gitDeliveryChanges` 合并文件/行数统计；失败原因整行 `pre-wrap`；新增 `--link`/`__branch`/`__outcome`/`__sep`/`__changes` 样式与 768px 断点堆叠 |
| i18n | `frontend/src/i18n/messages/{zh-CN,en}.ts` | `gitDeliveryRecovered` → 前序任务提交 / Previous task commits；新增 `gitDeliveryNewFiles`/`ModifiedFiles`/`DeletedFiles`/`NoNetChanges`；删除不再使用的 `gitDeliveryFilesSummary`/`gitDeliveryBranch`/`gitDeliveryPush` |
| MR 文本 | `backend/app/core/worker_gitlab.py` | `_git_delivery_detail_lines` 的恢复交付标题改为 `**前序任务提交（N）**` |
| 回归 | `TaskResultPanel.behavior.spec.ts`、`test_worker_gitlab_delivery_text.py` | 覆盖 head 行链接/未确认复制、前序任务提交分组、全零「无净文件变化」、MR 新标题 |

## 3. 部署与制品

| 项 | 值 |
|---|---|
| Backend / Scheduler 镜像 | `codify-backend:latest` sha256 `ee095a59093b69771d364c53cd7e69da48edd878fedebe74e15cf4b4829ec5c6` |
| Nginx 镜像（含前端构建） | `codify-nginx:latest` sha256 `90f9d333dc88ec06c50c6c4f3aecf887c10ad579cfc5332ec44f9df7b625ca74` |
| Worker Kit / Worker Image | **未改动**（本次不涉及 `worker-entrypoint`，无需重跑 `verify-runtime`） |

部署方式：`docker-compose --env-file .env.test build --pull=false backend nginx` +
`docker-compose --env-file .env.test up -d`（`codify-backend`/`codify-scheduler`/`codify-nginx` 均在目标机重建并重启，
健康检查通过；`curl /health` = 200）。

## 4. 真实 Task 页面验收

数据来自 dev 库已有真实任务（`tasks.worker_metadata.git_delivery`），页面为 `http://192.168.50.129:8880/tasks/<id>`。

| 场景 | Task | 页面实测（`.result-card--commit` 文本） |
| --- | --- | --- |
| 本次提交 + 前序任务提交，已推送 | 614 | `codify/issue-182 · 已推送 · 新增 1 个文件 · +1` / `本次提交 (1) ab49c40e` / `前序任务提交 (2) e0bf790b, ace02f31` |
| 提交 + 前序提交，推送失败（`push_failed`） | 567 | `codify/issue-145 · 推送失败（交付未确认） · 修改 1 个文件 · +64 · -65` / 失败原因整行 / `本次提交 (1) 3ca90031` |
| 远端分叉失败（`remote_diverged`） | 488 | `codify/issue-131 · 推送失败（交付未确认） · 新增 1 个文件 · +1` + 完整原因 + SHA 复制 |
| 远端不可确认（`remote_unconfirmed`） | 447 | `codify/issue-113 · 推送失败（交付未确认） · 新增 2 个文件 · +4` + 原因；`head_sha=866e68d9` 位于第 3 条提交行，摘要行不重复出现 |
| 仅前序任务提交，已推送 | 452 / 450 | `已推送 · 无净文件变化` / `前序任务提交 (2)` 或 `(1)`；head 链接落在匹配的前序提交行 |
| 仅前序任务提交，未尝试推送 | 455 | `未尝试推送 · 无净文件变化` / `前序任务提交 (1)`；无链接、保留复制 |
| 无交付内容（失败，未进入发布） | 604 | 不渲染「提交记录」卡（`git_delivery` 无提交且非 `failed`） |
| 历史 Task（无 `git_delivery`） | 440 | 保留原单 SHA + 提交说明渲染，无推送状态行 |

关键约束逐条核对：

- 摘要行不含任何 8 位 SHA（`summaryContainsSha=false`），`head_sha` 只在提交行出现；
- 已确认（`pushed`/`already_present`）时才渲染提交行外链：614/452/450 有 1 个 `.git-delivery__commit-sha--link`，
  567/488/447/455 为 0 个、仅保留复制按钮；
- 已推送/已包含为绿色，失败为红色且同一行没有成功色或链接稀释；
- 零值不伪造：450/452/455 的 `diff.additions=0,deletions=0` 显示「无净文件变化」，未出现 `+0`/`-0`。

## 5. 布局与响应式几何证据

Task 567（失败态，最长文本）实测边界（`getBoundingClientRect`，CSS 像素）：

| 断点 | 摘要行 | 失败原因行 | 横向滚动 |
| --- | --- | --- | --- |
| 1440（卡片内容宽 667） | 分支 x=329..527，状态+统计 x=539..996，同一行（y 618..643） | x=329..996，位于摘要行下方（y 651..669） | `scrollWidth == clientWidth == 1440` |
| 768 | 单列堆叠：分支 y858..877、状态/统计 y883..937，均宽 276 | 宽 276，位于摘要下方 | `768 == 768` |
| 390（移动端重载后） | 同上堆叠，分支/状态左对齐 | 宽 276，整行 | `390 == 390` |

- 计算样式：`.git-delivery__summary` 桌面 `grid-template-columns: 455.9px 199.4px`（`minmax(0,1fr) auto`），
  768/390 为单列；`.git-delivery__outcome` 桌面 `justify-content: flex-end`，窄屏 `flex-start`。
- 分支为 `font-family: monospace`、`border: none`、`cursor: auto`，`title` 提供完整值，`overflow: hidden` 受
  `min-width: 0` 约束不撑宽。
- 提交标题：桌面 `white-space: nowrap` + 省略号；`≤768px` 为 `-webkit-line-clamp: 2` + `white-space: normal`
  \+ `overflow-wrap: anywhere`，`title` 保留完整标题。
- 触摸目标：`.git-delivery__commit-sha` 在窄屏 `min-height: 44px`（实测 44–50px）。SHA 复制、外链均为原生
  `button`/`a`，`tabIndex = 0`、`rel="noopener noreferrer"`。

## 6. MR 渲染验证（部署镜像）

在目标机容器内直接调用部署后的渲染函数（任务 614 的形态）：

```text
**本次提交（1）**

- `aaaaaaaaaaaa` docs: add reject recheck 3

**前序任务提交（2）**

- `cccccccccccc` docs: add reject recheck
- `dddddddddddd` docs: add reject recheck 2

**净变更**：+1 -0，新增 1 / 修改 0 / 删除 0 个文件

**推送**：推送成功
```

（MR 文本的零值口径沿用既有 `净变更` 行，本次调整只改分组标题与 Task 详情卡片，不改 MR 统计格式。）

## 7. 单元与合同测试

| 层 | 命令 | 结果 |
| --- | --- | --- |
| Backend 目标用例 | `pytest tests/unit/test_worker_gitlab_delivery_text.py tests/unit/test_mr_stats.py tests/unit/test_worker_git_delivery.py` | 45 passed |
| Backend 相关链路 | `pytest tests/unit/test_worker_results_v2.py tests/unit/test_worker_task_artifacts.py tests/unit/test_worker_coverage.py tests/unit/test_task_api_contract.py` | 191 passed |
| Backend lint | `ruff check app/core/worker_gitlab.py tests/unit/test_worker_gitlab_delivery_text.py` | passed |
| Frontend | `npx vitest run` | 82 files / 1772 tests passed |
| Frontend 构建 | `npm run build`（`vue-tsc` + vite） | passed |

## 8. 已知边界

- **未采集统计无真实样本**：dev 库没有「有提交但 `diff` 为 null」的任务，`统计未采集` 标签由
  `TaskResultPanel.behavior.spec.ts` 的「不伪造零统计」用例覆盖。
- **取消态不渲染结果卡**：`TaskView.vue` 的 `isTerminal` 只含 `completed`/`failed`，因此取消任务（如 613）
  不会出现「提交记录」卡。这是既有视图语义，本次未改动。
- **响应式断点需要重载**：`App.vue` 的 `isMobile` 在运行期只依赖初始视口，用 CDP 改视口后需重新加载页面才生效；
  390px 验收按「重载后」测量。该行为属既有 App Shell，与本卡片无关。
- 视觉截图已生成，但本次可用的视觉模型不可用，页面证据以 DOM 文本与几何测量为准。

## 9. 清理

- 浏览器验收标签页已释放；未改动 Provider/Profile/Kit 配置，未新增数据库字段或迁移。
- 验收使用的 Task 614/452/450/455/567/488/447/604/440 保持原状，作为证据保留。
- `/tmp` 下的临时截图已删除。
