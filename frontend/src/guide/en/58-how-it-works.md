---
title: How Codify Works Under the Hood
section: User Guide
tier: deep
---

This page separates the three layers involved in a run: the model, the Harness, and Codify. Use [Concepts](/guide/20-concepts) for the user-facing objects, [Harness Support](/guide/65-harness-support) for adapter differences, and [Delivery Internals](/guide/75-delivery-internals) for the publish boundary.

## The map: from token to change

One run can be read at three layers:

| Layer | Question | Owns |
|---|---|---|
| Model | What should come next? | Context processing, token probabilities, and decoding |
| Harness | How does the turn make progress? | Instructions, tools, session state, Skills, and event normalization |
| Codify | How does the work become a reviewable result? | Issues, Tasks, snapshots, scheduling, Workers, evidence, and Git delivery |

## What a large language model does

A language model reads a sequence of tokens inside a finite context window and scores possible next tokens. Decoding selects one, appends it to the context, and repeats. The result can be text, code, or a structured tool-call request.

Attention and learned parameters are part of the model's prediction process. The model can use only the context supplied for the current request, subject to the model and Provider limits. Sampling changes how the next token is selected; it does not grant access to the repository.

> [!info] The model proposes output. It does not own the filesystem, shell, session, or final commit.

## What a Harness adds

A Harness turns model output into an agent turn. It combines the system instruction, Task prompt, conversation history, Provider protocol, workspace tools, session state, and capability policy.

The loop is: send context to the model, validate and run an approved tool request, return the observation, and ask the model what to do next. Skills add reusable instructions or tools. Capability gates keep unsupported steering, follow-up, or subagent behavior closed.

Claude, Codex, Pi, and OpenCode use separate adapters. Codify normalizes their events, results, usage, and failures so the Task page can show one timeline. Task Mode remains a Task choice; it is not a different model.

## What Codify adds

Codify gives the Harness loop durable state. An Issue owns the long-lived workspace, session lineage, and branch. Each Task carries its prompt, mode, session choice, and execution identity.

At Task creation, Codify resolves the Worker Profile and binds a Task Snapshot and immutable Runtime Bundle. The scheduler then checks turn order and capacity before starting an isolated Worker container. The Worker prepares the repository, runs the selected Harness, and sends normalized events back to the Task.

At the end, Codify records the result, commits, usage, statistics, and archive evidence. When delivery is enabled, it publishes the working branch and creates or updates the Issue's Merge Request.

## How the layers compose

Each layer receives different input and produces a different kind of output:

| Layer | Input | Operation | Output | Owner |
|---|---|---|---|---|
| Model | Context tokens and generation settings | Predict and decode | Text or a tool-call proposal | Model Provider |
| Harness | Prompt, history, Provider, workspace, and policy | Run the turn and approved tools | Observations, events, and final result | Harness adapter/runtime |
| Codify | Issue, Task Snapshot, Runtime Bundle, and schedule state | Orchestrate, isolate, observe, and deliver | Task evidence, commits, branch state, and MR | Codify control plane and Worker |

A model can explain generated output, but not why a Task waited. A Harness can explain a rejected tool request, but not why a push lost its lease. Codify connects these records while keeping ownership clear.

## Where to look when something goes wrong

| Symptom | First place to inspect |
|---|---|
| Answer is off-target or missing context | Prompt, model, Provider, and context window; see [Create a Task](/guide/30-create-task) |
| Tool did not run, session would not continue, or protocol was rejected | Harness adapter, capability gate, session, or Skill; see [Harness Support](/guide/65-harness-support) |
| Task waits, container fails, events are missing, or delivery did not complete | Scheduler, Worker runtime, event projection, or delivery state; see [Scheduling](/guide/60-scheduling), [Observability](/guide/70-observability), and [Delivery Internals](/guide/75-delivery-internals) |
