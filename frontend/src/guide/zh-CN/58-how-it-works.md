---
title: Codify 工作原理：从大模型到交付
section: User Guide
tier: deep
---

这页只讲一次运行中三层的职责：模型、Harness 和 Codify。用户对象见[《概念》](/guide/20-concepts)，适配器差异见[《Harness 支持》](/guide/65-harness-support)，推送边界见[《交付内部》](/guide/75-delivery-internals)。

## 总图：从 token 到改动

一次运行可以分成三层来看：

| 层次 | 要回答的问题 | 负责什么 |
|---|---|---|
| 模型层 | 下一步应该输出什么？ | 上下文处理、token 概率和解码 |
| Harness 层 | 这一回合如何继续推进？ | 指令、工具、会话状态、Skills 和事件归一化 |
| Codify 层 | 如何得到可评审的结果？ | 需求、任务、快照、调度、Worker、证据和 Git 交付 |

## 大语言模型做什么

模型在有限的上下文窗口里读取一串 token，并为可能的下一个 token 计算分数。解码选出一个 token，把它追加回上下文，然后重复这个过程。输出可以是文字、代码或结构化的工具调用请求。

注意力和训练参数属于模型的预测过程。模型只能使用当前请求收到的上下文，并受模型和 Provider 限制。采样设置会改变 token 的选择方式，却不会让模型获得仓库访问权限。

> [!info] 模型提出输出，不负责文件系统、Shell、会话或最终提交。

## Harness 增加了什么

Harness 把模型输出变成一次编码回合。它组合系统指令、任务提示词、对话历史、Provider 协议、工作区工具、会话状态和能力策略。

它的循环是：把上下文发给模型，校验并执行获准的工具请求，把观察结果返回，再询问模型下一步。Skills 可以加入可复用的指令或工具；能力门控会关闭不支持的实时引导、后续指令或子代理能力。

Claude、Codex、Pi 和 OpenCode 使用各自的适配器。Codify 将它们的事件、结果、用量和失败归一化为一条任务时间线。任务模式仍然是 Task 的选择，不是另一种模型。

## Codify 增加了什么

Codify 为 Harness 循环提供持久状态。需求拥有长期工作区、会话线代和分支；每条任务携带自己的提示词、模式、会话选择和执行身份。

创建任务时，Codify 解析 Worker Profile，并绑定 Task Snapshot 与不可变的 Runtime Bundle。调度器检查回合顺序和容量后，才启动隔离的 Worker 容器。Worker 准备仓库、运行选中的 Harness，并把归一化事件写回任务。

任务结束时，Codify 记录结果、提交、用量、统计和运行归档。开启交付后，再发布工作分支并创建或更新该需求的 Merge Request。

## 三层如何合起来

每层收到的输入和产生的输出不同：

| 层次 | 输入 | 主要动作 | 输出 | 负责方 |
|---|---|---|---|---|
| 模型层 | 上下文 token 和生成设置 | 预测并解码 | 文本或工具调用建议 | 模型 Provider |
| Harness 层 | 提示词、历史、Provider、工作区和策略 | 执行回合与获准工具 | 观察结果、事件和最终结果 | Harness 适配器/运行时 |
| Codify 层 | 需求、Task Snapshot、Runtime Bundle 和调度状态 | 编排、隔离、观测和交付 | 任务证据、提交、分支状态和 MR | Codify 控制平面与 Worker |

模型可以解释生成了什么，却不能解释任务为什么排队；Harness 可以解释工具请求为何被拒绝，却不能解释推送为什么失去租约。Codify 会连接这些记录，但保留每层的责任边界。

## 出现问题时从哪里查

| 症状 | 首先检查 |
|---|---|
| 回答偏题或缺少上下文 | 提示词、模型、Provider 和上下文窗口，见[《创建任务》](/guide/30-create-task) |
| 工具没执行、会话无法继续或协议被拒绝 | Harness 适配器、能力门控、会话或 Skill，见[《Harness 支持》](/guide/65-harness-support) |
| 任务等待、容器失败、事件缺失或交付未完成 | 调度器、Worker 运行时、事件投影或交付状态，见[《调度》](/guide/60-scheduling)、[《可观测性》](/guide/70-observability) 和[《交付内部》](/guide/75-delivery-internals) |
