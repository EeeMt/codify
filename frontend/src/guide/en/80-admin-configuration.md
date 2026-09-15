---
title: Admin Configuration
section: Admin Guide
tier: core
---

## Configuration overview

**Configuration** at /configuration is for platform administrators. It is the control surface for runtime, authentication, GitLab, AI Providers, Worker Profiles, Skills, notifications, announcements, and maintenance.

| Tab | Use it for |
|---|---|
| **Runtime** | Scheduler, concurrency, timeouts, retries, slot capacity, CI repair, shared pages |
| **Authentication** | GitLab OIDC, sessions, bootstrap, diagnostics |
| **GitLab** | API connection and project webhooks |
| **AI Providers** | Model endpoints |
| **Requirement Templates** | Reusable task and issue prompt bodies |
| **Worker** | Shared runtime, Worker Profiles, cleanup, artifacts |
| **Skills** | Managed Skill packages |
| **Notifications** | Mattermost and notification profiles |
| **Announcement** | The top-bar message |
| **Maintenance** | Reload, reset, and cleanup actions |
| **Webhook Events** | Received GitLab event history |

Saved values are runtime overrides. Existing Tasks use their frozen snapshots, so a configuration edit affects new Tasks only.

### How a saved value takes effect

The page marks each value as **DB override**, **env fallback**, or **default fallback**. Saving a section persists the override. **Reset to env/defaults** removes all persisted overrides after confirmation.

### Secrets

Secrets are encrypted server-side and are never returned to the browser. A blank secret field keeps the stored value; use its clear action to remove it. The encryption key is deployment configuration and must remain stable. If it is lost or changed, stored secrets must be entered again.

## Run the first task

Verify the execution path in this order:

1. Set **GitLab URL** and **GitLab Bot Token**, test the connection, and grant the bot push and MR permissions in a test project.
2. Create and enable one AI Provider, then run its connection test.
3. Save one enabled Worker Profile and verify its runtime. Confirm that the required Harness is available.
4. Create a small Implementation Task and confirm branch push and MR creation.

Tune OIDC, capacity, Skills, notifications, and cleanup after this path works. Use a new Task to validate configuration changes.

## Runtime and capacity {deep}

### Scheduler

**Max Concurrency** controls how many Tasks run at once. **Scheduler Interval (seconds)** controls how often the scheduler checks for eligible work. **Default Target Branch** fills in when a Task does not specify a target.

The supported ranges are 1–20 for concurrency and 1–60 seconds for the interval. Raising concurrency also raises demand on Workers, the model endpoint, and GitLab.

### Task timeout policy

The policy has a business timezone, a peak window, a peak timeout, and an off-peak timeout. Start is inclusive and end is exclusive; the values use 24-hour HH:mm. Each timeout is 60–28800 seconds.

The tier is selected when a Task enters **Running** and stays fixed for that run. The Task page records **Execution timeout** and **Execution deadline** when available.

### Retry and alerts

**Max Retries** accepts 0–10 and **Retry Delay (seconds)** accepts 1–3600. A retry is an explicit Task action that creates a new Task; it does not rewrite the source record.

**Alert on Failure** sends a notification to **Alert Webhook URL**. The URL is secret and the page shows only its configured status.

### Slot capacity

**Max Tasks per Hour Slot** limits scheduled Tasks in one hour; 0 means unlimited. **Enforce Slot Limit** rejects a full slot when enabled and warns when disabled.

### CI Auto-repair

**Max CI Repair Attempts** caps automatic repair Tasks per tracked MR; 0 disables them. The project webhook must also have a managed secret, SSL verification, MR events, and pipeline events enabled.

### Page permissions

**Shared Page Access** controls whether non-admin users can open Monitor, Schedule Overview, and Analytics. These switches apply when OIDC login is enabled; without OIDC, signed-in users can access the pages. OIDC Diagnostics remains administrator-only.

## GitLab and webhooks

### GitLab connection

**GitLab URL** is used for API calls, links, and repository operations. **GitLab Bot Token** runs Tasks. **GitLab Admin Token** manages project webhooks.

**Test GitLab connection** checks the values currently in the form and reports the GitLab version and authenticated user. **Invalidate project cache** forces the next project request to refresh.

### Webhook automation

Codify registers the backend callback at /api/webhook/gitlab. Use **Set up project webhook** for a project visible to the admin token. Codify manages a separate encrypted secret for each project.

### Webhook overview

The overview scans projects visible to the GitLab Admin Token.

| Status | Condition |
|---|---|
| **Configured** | Hook exists with SSL, MR events, and pipeline events enabled |
| **Needs attention** | One of those checks is missing or disabled |
| **Missing** | No matching hook |
| **Error** | The project or hook could not be checked |

If MR events are disabled, auto-close cannot work. If the overview does not load, check GitLab URL and the stored admin token first.

### Webhook Events

**Webhook Events** records the project, event type, action, MR or pipeline identity, Issue match, processing result, and detail. Filter by result or project ID. An authentication failure means the hook secret did not match; run project webhook setup again.

## Login and OIDC {deep}

### Provider basics

Enabling OIDC makes the dashboard and its APIs require GitLab sign-in. The provider needs **Issuer URL**, **Client ID**, **Client Secret**, and **Redirect URI**. The OAuth application must allow openid, profile, email, and read_api scopes. The redirect normally ends in /api/auth/callback.

**Test OIDC connection** performs discovery using the current form values. It does not enable OIDC.

### Session and access

**Session Cookie Name**, **Session TTL (seconds)**, and **Session Retention (days)** control the browser cookie and session records. TTL accepts 300–604800 seconds. Keep **Cookie Secure** enabled for HTTPS. **Cookie SameSite** must match the deployment; SameSite=None requires secure cookies.

### Admin bootstrap

**Admin Usernames** and **Admin GitLab Groups** grant the admin role at login to accounts without a manual role override. Group bootstrap works only when GitLab includes groups in claims or userinfo. A manual role change wins over later bootstrap evaluations.

### OIDC diagnostics

**OIDC Diagnostics** checks discovery, provider endpoints, redirect URI, required scopes, and cookie policy. It also shows the effective auth mode, client-secret status, session TTL, and provider metadata. Use it first for sign-in loops or an unexpected role.

Break-glass login is deployment-controlled. Keep it off during normal operation and use it only for OIDC recovery or administrator lockout.

## AI providers

### Provider fields

| Field | Rule |
|---|---|
| **Name** | Unique identifier starting with a letter or digit; letters, digits, hyphens, and underscores |
| **Base URL** | Must use http or https |
| **Model** | Identifier sent to the endpoint |
| **Max Turns** | 1–1000 |
| **API Key** | Secret; blank keeps the stored key |
| **System Prompt** | Added to each execution; at most 10,000 characters |
| **Status** | Enabled or Disabled |

### Provider kind and wire protocol

| Provider Kind | Wire Protocol | Harnesses |
|---|---|---|
| anthropic_compatible | anthropic_messages | Claude, Pi, OpenCode |
| openai_compatible | openai_responses | Codex, Pi, OpenCode |
| openai_compatible | openai_chat_completions | Pi, OpenCode |

The API checks this pair when saving. A mismatch never reaches a Worker.

### Default, enable, and delete rules

There is one default Provider. The first enabled Provider becomes default. A default Provider cannot be disabled, and an active Task prevents deletion. The last remaining enabled Provider cannot be removed.

### Connection test and advanced parameters

**Test connection** sends a minimal authenticated request and reports latency or the upstream error. **Advanced request parameters** is a JSON object merged into compatible requests; harness-owned fields and secrets are rejected. These values are frozen into new Task snapshots.

## Worker profiles

### Shared configuration and inheritance

Shared configuration is the system baseline for the Worker Kit, mounts, environment, scripts, and run instructions. Its revision increases on every save. A profile can inherit a value, override it, mask it, or add a profile-only value.

Saving shared configuration validates enabled profiles as a group. If another administrator saved a newer revision, reload before saving.

### Profile fields

A Worker Profile defines the image, runtime delivery, mounts, environment, scripts, CodeGraph, Harnesses, Default Harness, Skills, and mode-specific run instructions.

Mounted Worker Kit is the supported delivery mode. Baked-image delivery is deprecated and does not support Skills. Worker Kit version and path form one setting group; the path is an absolute Docker-host path mounted in the container at /opt/codify-kit.

Profile environment names must match the platform pattern and cannot use reserved runtime namespaces such as ANTHROPIC_, CLAUDE_, CODEX_, CODIFY_, OPENAI_, OPENCODE_, or PI_. Secret variables are stored encrypted. Pre Script runs after checkout; Post Script runs after a successful AI execution and before commit.

Disabling a Profile is blocked while open Issues use it. **Force disable** closes those Issues, so confirm the impact. The default Profile cannot be disabled or deleted.

### Docker target

A Profile can use the system Docker target or its own target. A custom target exposes Docker Host and optional TLS paths. **Test connection** checks the daemon; remote TCP without TLS is warned.

### Runtime verification

**Verify runtime** probes the image, Worker Kit, and Harness inventory. A successful Profile is **Verified** and **Ready** with a last-checked time. Changes to the image, Kit, mounts, or Harness selection require verification again.

### Workspace cleanup and artifacts

Workspace cleanup controls the issue workspace path and retention. The host path is deployment configuration and is read-only here; 0 disables ordinary automatic cleanup.

Task Artifacts controls total size, single-file size, entry count, and runtime-archive retention. The single-file limit cannot exceed the total limit. Expired archives do not delete Tasks or Issues.

### Task Snapshot and Runtime Bundle

When a Task is created, Codify resolves the Profile and binds an immutable Task Snapshot and content-addressed Runtime Bundle. Editing a Profile, Provider, Skill, or shared script affects later Tasks only.

![You edit a Worker Profile; a task runs a frozen snapshot](assets/diagrams/en/profile-to-bundle.svg)

Use the Task Snapshot and the Profile verification result when a run appears to use the wrong runtime. See [Worker Runtime](/guide/92-worker-runtime) for filesystem details.

## Prompt templates and skills {deep}

### Requirement templates

Requirement Templates stores reusable prompt bodies, variables, tags, active state, and order. Inactive templates stay stored but are hidden from creation. A variable tip is invalid when its placeholder is not in the template.

### Skills catalog

Skills are directory packages with a root SKILL.md and optional supporting files. The SKILL.md name must match its frontmatter. Safe relative paths are required.

| Limit | Value |
|---|---:|
| SKILL.md | 100,000 characters |
| Supporting files | 128 |
| One supporting file | 2 MiB |
| Complete package | 8 MiB |
| Path length | 240 characters |

Disabling a Skill affects new Task snapshots only. Skills require mounted Worker Kit delivery at the minimum version in [Platform reference](/guide/96-platform-reference).

## Notifications and announcements {deep}

### Mattermost integration

Set the Mattermost server URL and bot token. The token is stored server-side; a blank field keeps it. **Test Mattermost connection** reports the authenticated bot.

### Notification profiles

A profile targets a Mattermost channel or the Task initiator's direct message. Channel targets must resolve the Team and Channel before saving. Select at least one event and one field.

Available events include completed, failed, rescheduled, switched to Execute Now, retry scheduled, and cancelled. Available fields include Task ID, Project, Issue, MR, Initiator, Status, Branch, Target branch, schedule, schedule change, error summary, and Task link.

### Announcement

**System Announcement** shows a message in the top bar for authenticated users. Enable it, enter the message, and choose Info, Warning, Error, or Success. Disable it when the message is no longer current.
