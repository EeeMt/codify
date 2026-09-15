---
title: 系统配置
section: Admin Guide
tier: core
---

## 配置总览

「系统配置」（/configuration）只对平台管理员开放，用来维护运行时、认证、GitLab、AI Provider、Worker Profile、Skills、通知、公告和维护操作。

| 选项卡 | 用途 |
|---|---|
| **运行与共享** | 调度器、并发、超时、重试、时段容量、CI 修复、共享页面 |
| **认证与会话** | GitLab OIDC、会话、管理员引导、诊断 |
| **GitLab** | API 连接和项目 Webhook |
| **AI 模型服务** | 模型服务端点 |
| **提示词模板** | 可复用的需求和任务提示词 |
| **Worker** | 共享运行时、Worker Profile、清理、制品 |
| **Skills** | 系统管理的 Skill 包 |
| **通知** | Mattermost 和通知配置 |
| **公告** | 顶栏消息 |
| **维护操作** | 重新加载、重置和清理 |
| **Webhook 事件** | GitLab 事件处理记录 |

保存后的值是运行时覆盖。已有任务使用自己的冻结快照，配置修改只影响之后创建的任务。

### 生效方式

页面用 **数据库覆盖**、**环境变量回退** 和 **默认值回退** 标出当前值的来源。保存分区会持久化覆盖；「重置为环境变量/默认值」确认后会删除所有持久化覆盖。

### 敏感密钥

密钥只在服务端加密保存，不会返回浏览器。密钥输入框留空表示保留已存值，需要撤销时使用对应的清除操作。加密根密钥属于部署配置，必须保持不变；丢失或更换后，已存密钥需要重新输入。

## 跑通第一条任务

按这个顺序确认执行链路：

1. 在「GitLab」填写 **GitLab URL** 和 **GitLab Bot Token**，测试连接，并给机器人账号测试项目的推送和 MR 权限。
2. 创建并启用一个 AI Provider，运行连接测试。
3. 保存一个启用中的 Worker Profile，执行运行时验证，确认目标 Harness 可用。
4. 创建一个小的实施任务，确认分支推送和 MR 创建成功。

链路跑通后，再按需要配置 OIDC、容量、Skills、通知和清理。验证配置变更时请创建新任务。

## 运行时与容量 {deep}

### 调度器

**最大并发数**决定同时运行的任务数；**调度间隔（秒）**决定检查频率；**默认目标分支**用于任务未指定目标分支时的回退。支持范围分别为 1–20 和 1–60 秒。

### 任务超时策略

策略包含业务时区、高峰窗口、高峰超时和低峰超时。开始时间包含、结束时间不包含，时间使用 24 小时制 HH:mm，超时值为 60–28800 秒。

任务进入「执行中」时选择一次档位并冻结到本次运行。任务页在有记录时显示「本次超时上限」和「执行截止时间」。

### 重试与告警

**最大重试次数**为 0–10，**重试延迟（秒）**为 1–3600。重试是任务页上的显式操作，会创建新任务，源任务记录不变。

开启「失败时告警」后，失败通知发送到 **告警 Webhook URL**。URL 是敏感值，页面只显示配置状态。

### 时段容量

**每小时时段最大任务数**限制一个小时内的预约任务数，0 表示不限制。「强制执行时段限制」开启时满载会拒绝创建，关闭时只给警告。

### CI 自动修复

**CI 最大修复次数**限制每条被跟踪 MR 自动创建的修复任务数，0 表示关闭。项目 Webhook 还必须有托管 secret、SSL 校验、MR 事件和流水线事件。

### 页面权限

「共享页面访问」决定普通用户能否访问 Monitor、Schedule Overview 和 Analytics。启用 OIDC 时这些开关生效；未启用 OIDC 时，已登录用户可以访问这些页面。「OIDC 诊断」没有普通用户开关，仍只对管理员开放。

## GitLab 与 Webhook

### GitLab 连接

**GitLab URL** 用于 API、链接和仓库操作；**GitLab Bot Token** 用于执行任务；**GitLab Admin Token** 用于管理项目 Webhook。

「测试 GitLab 连接」会用表单中的当前值检查 GitLab，并报告版本和认证用户。「清除项目缓存」会让下一次项目请求重新拉取。

### Webhook 自动配置

Codify 注册的回调地址是后端地址加上 /api/webhook/gitlab。对 Admin Token 可见的项目使用「配置项目 Webhook」，每个项目的 secret 由 Codify 独立加密管理。

### Webhook 总览

总览扫描 Admin Token 可见的项目：

| 状态 | 条件 |
|---|---|
| **已配置** | Hook 存在，且 SSL、MR 事件和流水线事件都开启 |
| **需关注** | 检查项缺失或被关闭 |
| **缺失** | 没有匹配的 Hook |
| **错误** | 项目或 Hook 无法检查 |

MR 事件未开启时，Issue 自动关闭不能工作。总览不加载时，先检查 GitLab URL 和已存储的 Admin Token。

### Webhook 事件

「Webhook 事件日志」记录项目、事件类型、动作、MR 或流水线标识、匹配的 Issue、处理结果和详情，支持按结果或项目 ID 筛选。认证失败说明 secret 校验未通过，重新配置项目 Webhook。

## 登录与 OIDC {deep}

### 提供方基础信息

开启 OIDC 后，控制台和 API 都要求 GitLab 登录。必须填写 **Issuer URL**、**Client ID**、**Client Secret** 和 **Redirect URI**，OAuth 应用还要允许 openid、profile、email、read_api。回调地址通常以 /api/auth/callback 结尾。

「测试 OIDC 连接」只做 issuer discovery，不会自动开启 OIDC。

### 会话与访问

**Session Cookie 名称**、**Session TTL（秒）** 和 **会话保留天数**控制浏览器 Cookie 与会话记录。TTL 支持 300–604800 秒。HTTPS 部署应保持 **Cookie Secure** 开启；SameSite=None 需要安全 Cookie。

### 管理员引导

**管理员用户名**和**管理员 GitLab 组**会在登录时为没有手动角色覆盖的用户授予管理员角色。组引导要求 GitLab 在 claims 或 userinfo 返回 groups；手动改过角色后，以手动设置为准。

### OIDC 诊断

「OIDC 诊断」检查 discovery、Provider 端点、回调地址、所需 scopes 和 Cookie 策略，并显示认证模式、客户端密钥状态、会话 TTL 与 Provider 元数据。遇到登录循环或角色异常时先看这里。

紧急管理员入口由部署环境控制。正常运行时应关闭，只在 OIDC 故障或管理员被锁定时使用。

## AI 模型服务

### Provider 字段

| 字段 | 规则 |
|---|---|
| **名称** | 以字母或数字开头，只允许字母数字、连字符和下划线 |
| **接口地址** | 使用 http 或 https |
| **模型** | 发送给端点的模型标识 |
| **最大轮次** | 1–1000 |
| **API 密钥** | 敏感值；留空保留原值 |
| **系统提示词** | 追加到每次执行，最多 10,000 字符 |
| **状态** | 启用或禁用 |

### Provider 类型与 Wire 协议

| Provider 类型 | Wire 协议 | 兼容 Harness |
|---|---|---|
| anthropic_compatible | anthropic_messages | Claude、Pi、OpenCode |
| openai_compatible | openai_responses | Codex、Pi、OpenCode |
| openai_compatible | openai_chat_completions | Pi、OpenCode |

保存时会校验这组配对，错误配置不会进入 Worker。

### 默认、启用和删除

系统只有一个默认 Provider。第一个启用的 Provider 会成为默认项；默认项不能禁用，活跃任务引用的 Provider 不能删除，最后一个可用 Provider 不能删除。

### 连接测试与高级参数

「测试连通性」发送一次最小认证请求并报告延迟或上游错误。「高级请求参数」必须是 JSON 对象，会合并到兼容 Harness 的请求体；Harness 自己管理的字段和密钥会被拒绝。这些配置会冻结到新任务的快照里。

## Worker Profile

### 共享配置

「共享配置」是 Worker Kit、挂载、环境变量、脚本和运行指令的系统基线。每次保存会增加修订版本；Profile 可以继承、覆盖、屏蔽或新增某个值。

保存共享配置前会一起验证启用中的 Profile。若其他管理员已经保存了新修订，先重新加载再保存。

### Profile 配置

Worker Profile 定义镜像、运行时交付方式、挂载、环境变量、脚本、CodeGraph、Harness、默认 Harness、Skills 和各模式运行指令。

「挂载 Worker Kit」是支持的交付方式；「镜像内置（已过时）」不支持 Skills。Worker Kit 版本和路径属于同一组，路径是 Docker 主机上的绝对路径，容器内挂载到 /opt/codify-kit。

环境变量名必须符合平台格式，不能使用 ANTHROPIC_、CLAUDE_、CODEX_、CODIFY_、OPENAI_、OPENCODE_ 或 PI_ 等运行时保留前缀。密文变量会加密保存。前置脚本在 checkout 后运行，后置脚本在 AI 成功后、提交前运行。

Profile 被未关闭需求使用时不能直接禁用。「强制禁用」会关闭这些需求，操作前要确认影响。默认 Profile 不能禁用或删除。

### Docker 目标

Profile 可以使用系统 Docker 目标，也可以指定自己的目标。自定义目标可配置 Docker Host 和 TLS 路径。「测试连接」会检查 daemon；远程 TCP 未使用 TLS 时会给出警告。

### 运行时验证

「验证运行时」会检查镜像、Worker Kit 和 Harness inventory。成功后显示「已验证」「已就绪」及最近检查时间。修改镜像、Kit、挂载或 Harness 后必须再次验证。

### Workspace 清理与任务产物

Workspace 清理维护需求工作区路径和保留期。宿主机路径属于部署配置，页面只读；保留天数为 0 时关闭普通自动清理。

任务产物设置总大小、单文件大小、条目数量和运行归档保留期。单文件上限不能超过总上限；归档过期不会删除任务或需求。

### Task Snapshot 与 Runtime Bundle

创建任务时，Codify 解析 Profile，并绑定不可变的 Task Snapshot 与内容寻址 Runtime Bundle。编辑 Profile、Provider、Skill 或共享脚本只影响后续任务。

![你编辑的是 Worker Profile，任务拿到的是冻结快照](assets/diagrams/zh-CN/profile-to-bundle.svg)

运行环境不符合预期时，优先比较任务快照和 Profile 验证结果。文件系统细节见[《Worker 运行时》](/guide/92-worker-runtime)。

## 提示词模板与 Skills {deep}

### 提示词模板

「提示词模板」保存可复用的提示词正文、变量、标签、启用状态和顺序。停用模板仍保留，但不会出现在创建流程；模板中不存在的变量说明会被标为无效。

### Skills

Skill 是以 SKILL.md 为根文件、可带附属文件的目录包。SKILL.md 的 name 必须与 frontmatter 一致，附属文件必须使用安全的相对路径。

| 限制 | 值 |
|---|---:|
| SKILL.md | 100,000 字符 |
| 附属文件数 | 128 |
| 单个附属文件 | 2 MiB |
| 完整 Skill 包 | 8 MiB |
| 路径长度 | 240 个字符 |

关闭 Skill 只影响新的任务快照。Skill 需要使用[《平台参考》](/guide/96-platform-reference)要求最低版本的挂载 Worker Kit。

## 通知与公告 {deep}

### Mattermost 连接

填写 Mattermost 服务地址和 Bot Token。令牌只存服务端，留空表示保留原值。「测试 Mattermost 连接」会报告认证后的机器人。

### 通知配置

通知配置可以发到 Mattermost 频道或任务发起人的私聊。频道目标保存前必须解析 Team 和 Channel；每条配置至少选择一个事件和一个字段。

事件包括完成、失败、改期、改为立即执行、安排重试和取消。字段包括任务 ID、项目、Issue、MR、发起人、状态、分支、目标分支、预约时间、时间变更、错误摘要和任务链接。

### 公告

「系统公告」向已登录用户的顶栏显示消息。开启后填写内容并选择信息、警告、错误或成功级别；消息失效后及时关闭。
