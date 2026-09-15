---
title: How Codify Works Under the Hood
section: User Guide
tier: deep
---

This chapter builds a mental model from the inside out: first the model that predicts the next token, then the Harness that turns predictions into an agent turn, and finally Codify that makes the turn durable, observable, and deliverable. It is a high-level explanation of ownership boundaries, not a replacement for the implementation details in [Harness Support](/guide/65-harness-support) or [Delivery Internals](/guide/75-delivery-internals).

## The map: from token to change

The same run can be read at three layers. A model answers what might come next. A Harness makes that answer part of a useful loop. Codify gives the loop a Task, a Worker, a timeline, and a delivery path.

| Layer | Core question | Owns |
|---|---|---|
| Model | What should come next? | Token probabilities, context processing, and decoding |
| Harness | How does this turn make progress? | Instructions, tool calls, session state, Skills, and event normalization |
| Codify | How does work become durable delivery? | Issues, Tasks, snapshots, scheduling, Workers, evidence, and Git delivery |

Read the surrounding concepts in [Concepts](/guide/20-concepts), then go deeper into [Harness Support](/guide/65-harness-support) and the routine delivery flow in [Delivery](/guide/50-delivery).

## What a large language model does

A large language model receives a sequence of tokens: pieces of text that may be words, punctuation, or smaller fragments. It processes the sequence inside a finite context window and produces scores for possible next tokens. Decoding turns those scores into one selected token. The selected token is appended to the context, and the model runs again. Repeating that cycle produces a response, a code block, or a structured request such as a tool call.

The Transformer architecture is the broad mechanism behind this process. Attention lets the model weigh relationships among the tokens in the current context, while learned parameters convert those relationships into a probability distribution. The model does not retrieve a durable conversation from nowhere: anything it can use for this prediction must be present in the context supplied to the current request, subject to the model and provider limits.

Sampling settings change how the distribution is decoded. A more deterministic choice tends to repeat the highest-scoring continuation; more variation can explore lower-scoring choices. Neither setting gives the model authority to modify a repository. The model can emit a tool-call request, but a host must validate and execute that request, then return the observation.

> [!info] A useful boundary: the model proposes the next piece of output. It does not own the filesystem, the shell, the session, or the final commit.

## What a Harness adds

A Harness is the coding-agent host that keeps a turn moving. It combines the model with system instructions, the current prompt, conversation history, provider protocol, workspace tools, session state, and a policy for which capabilities are available. In Codify, Claude, Codex, Pi, and OpenCode each have an adapter that presents this shared contract while respecting the Harness's own CLI and wire protocol.

The central loop is small but important: the Harness sends context to the model; the model returns text or a tool request; the Harness checks the request and runs an approved tool; the tool produces an observation; and the Harness feeds that observation back into the next model request. A Skill can add reusable instructions or tools to this environment, while a capability gate can keep unsupported steering, follow-up, or subagent behavior closed.

Sessions make the loop continuous across Tasks when the selected Harness supports continuation. Event and result normalization gives Codify a stable way to display model output, tool activity, usage, completion, and failure even when the underlying CLIs differ. Task Mode still belongs to the Task: Implementation, Analysis, and Freeform describe the outcome the turn should pursue; they are not different models.

See [Harness Support](/guide/65-harness-support) for the adapter operations, provider protocol pairing, session directories, Skills, and per-Harness capability differences.

## What Codify adds

Codify puts the Harness loop inside a durable control plane. An Issue keeps the requirement and the long-lived workspace, session, and branch. Each concrete move becomes an ordered Task with a prompt, mode, session choice, and execution identity. When the Task is created, Codify resolves the Worker Profile and binds a Task snapshot and immutable Runtime Bundle so later configuration changes do not rewrite an existing run.

The scheduler chooses when the Task can run, observes capacity and per-Issue order, and starts an isolated Worker container. The Worker prepares the repository, mounts the frozen runtime and shared Issue state, invokes the selected Harness, and projects normalized events into the Task timeline. At the end, Codify records the result, commits, usage, run statistics, and archive evidence, then publishes the working branch and creates or updates the Merge Request when delivery is enabled.

Codify does not become another model in this picture. It orchestrates the provider, Harness, workspace, and Git lifecycle around the model. For the user-facing creation path, see [Create a Task](/guide/30-create-task); for queue behavior see [Scheduling](/guide/60-scheduling); for evidence see [Observability](/guide/70-observability); and for the final publish/archive boundary see [Delivery Internals](/guide/75-delivery-internals).

## How the layers compose

The layers answer different questions and hand off different artifacts. Keeping that distinction clear makes both product behavior and debugging easier to explain.

| Layer | Input | Main operation | Output | Primary owner |
|---|---|---|---|---|
| Model | Context tokens and generation settings | Predict and decode the next token | Text or a structured tool-call proposal | Model provider |
| Harness | Prompt, history, provider, workspace, and policy | Run the agent turn and execute approved tools | Observations, normalized events, and a final result | Harness adapter/runtime |
| Codify | Issue, Task snapshot, Runtime Bundle, and scheduling state | Orchestrate, isolate, observe, and deliver | Task evidence, commits, branch state, and Merge Request | Codify control plane and Worker |

The lower layer should not be asked to explain a higher-layer decision. A model may explain why text was generated, but not why a Task waited in a queue. A Harness may explain why a tool request was rejected, but not why a branch publish lost its lease. Codify can connect these records into one timeline without collapsing their ownership boundaries.

## Where to look when something goes wrong

Start with the symptom and inspect the layer that owns it:

| Symptom | First lens | Useful guide |
|---|---|---|
| The answer is off-target, incomplete, or missing context | Prompt, model, provider, and context window | [Create a Task](/guide/30-create-task) |
| A tool did not run, a session would not continue, or a protocol was rejected | Harness adapter, capability gate, session, or Skill materialization | [Harness Support](/guide/65-harness-support) |
| A Task is waiting, a container failed, events are missing, or a commit/Merge Request was not delivered | Scheduler, Worker runtime, event projection, or delivery state | [Scheduling](/guide/60-scheduling), [Observability](/guide/70-observability), [Delivery Internals](/guide/75-delivery-internals) |

This lens keeps the investigation narrow while preserving the path across layers: inspect the model and prompt for quality, the Harness for execution, and Codify for orchestration and delivery. Once the owning layer is clear, the surrounding guide chapters provide the concrete fields, logs, and state transitions to verify.
