---
title: Admin Configuration
section: Admin Guide
tier: core
---

## Configuration overview

The Configuration page (`/configuration`, sidebar entry **Configuration**) is restricted to platform admins. It is the only place where you change scheduler behavior, GitLab connectivity, login, AI providers, worker runtimes, notifications, and cleanup. Nothing here needs a file edit or a restart.

> [!info] **Configuration boundary**: saved values affect later runs. Tasks that already exist use their own frozen snapshot and do not change when an administrator edits the configuration afterwards.

Settings are grouped into eleven tabs.

| Tab | What it holds |
| --- | --- |
| **Runtime** | Scheduler concurrency and interval, task timeout policy, retry and alerts, slot capacity, CI auto-repair, shared page access |
| **Authentication** | GitLab OIDC provider, session and cookie policy, admin bootstrap, OIDC diagnostics |
| **GitLab** | GitLab API host and tokens, project webhook overview |
| **AI Providers** | Model endpoints used by tasks |
| **Requirement Templates** | Reusable requirement templates offered during task creation |
| **Worker** | Shared worker configuration, Worker Profiles, workspace cleanup, task artifacts |
| **Skills** | Skill packages available to task harnesses |
| **Notifications** | Mattermost connection and notification profiles |
| **Announcement** | The system-wide banner |
| **Maintenance** | Reset all configuration, delete old system data |
| **Webhook Events** | History of received GitLab webhook events |

### How a saved value takes effect

The page header shows **Unsaved changes** or **In sync** for the page as a whole, next to three origin tags that describe how the loaded values were resolved. **DB override** means a value was saved here and wins over the environment. **env fallback** means no override exists and the value comes from the process environment. **default fallback** means neither is set, so the built-in default applies.

Saving a section writes the override, and from then on the platform uses that override. **Reset to env/defaults** on the **Maintenance** tab deletes every override and returns all sections to environment or default values, after the confirmation **Reset all configuration sections to their environment variable / default values? Unsaved changes will be lost.**

### Secrets

The page banner **Secrets are stored server-side and never returned to the browser. Leave secret fields blank to keep their current stored values.** applies to every secret field. Secret values are encrypted before the platform persists them, and the API returns only a boolean such as `gitlab_bot_token_configured`. Clearing a stored secret is a separate action from saving a new one.

Encryption uses a key that is fixed for the instance. A missing key, or the placeholder value `change-me-in-production`, makes secret writes fail. Keep that key stable across restarts and upgrades: if the key that produced the stored ciphertext changes, existing secrets can no longer be decrypted and must be entered again. The key belongs to deployment-time configuration, and this page cannot change it.

## Run the first task

Configure the execution path before tuning capacity, notifications, or sign-in policy:

1. Enter the service URL and bot token under **GitLab**, then run the connection test. Add the bot to the test project with permission to push branches and open Merge Requests.
2. Create and enable one provider under **AI Providers**. Its connection test should succeed and report the round-trip latency.
3. Save the shared Worker settings and one enabled Worker Profile, then verify its runtime. The result lists the Harnesses available on that Worker.
4. Create a small Issue in the test project. Run an Implementation Task and confirm that Codify pushes the branch and opens the Merge Request.

After that run succeeds, configure OIDC, concurrency and timeouts, Skills, notifications, and cleanup as needed. Existing Tasks keep their frozen snapshots, so use a new Task to check a configuration change.

## Runtime and capacity {deep}

### Scheduler

**Max Concurrency** caps how many tasks execute at the same time; the accepted range is 1 to 20. **Scheduler Interval (seconds)** controls how often the scheduler checks for work; the accepted range is 1 to 60. **Default Target Branch** is used when a task does not name one.

Raising concurrency increases pressure on the workers, the model endpoint, and GitLab. Lower the interval only after confirming the platform keeps up with the task volume.

### Task timeout policy

The panel shows the business timezone as **Business timezone: Asia/Shanghai**. **Peak start time** and **Peak end time** are strict 24-hour `HH:mm` values; start is inclusive and end is exclusive, and the two must differ. **Peak timeout (seconds)** and **Off-peak timeout (seconds)** accept 60 to 28800 seconds.

The panel hint states: **Each task selects one limit when it enters RUNNING and keeps it while running.** A task that exceeds the limit fails with a message of the form `Task timed out after {timeout_seconds}s` followed by the tail of its sanitized logs.

### Retry and alerts

**Max Retries** accepts 0 to 10 and **Retry Delay (seconds)** accepts 1 to 3600. Re-queuing a failed task is an explicit action from the task view: the retry creates a new task that references the failed one, so the original record keeps its error state.

**Alert on Failure** sends a webhook notification when a task fails, using **Alert Webhook URL**. The stored URL is never returned to the browser; the panel shows **Alert Webhook Status** instead, and a blank field keeps the current value. Clearing the stored webhook is a separate action.

### Slot capacity

**Max Tasks per Hour Slot** caps how many tasks may be scheduled into the same one-hour window; `0` means unlimited. **Enforce Slot Limit** decides what happens when the window is full: with enforcement on, task creation is rejected with `Time slot {start}–{end} is at full capacity ({count}/{max} tasks).`; with it off, the same condition is reported as a warning only.

### CI Auto-repair

**Max CI Repair Attempts** limits how many automatic repair tasks may be created per tracked merge request; `0` disables automatic repair tasks. Automatic repair also requires a healthy project webhook: the hook must exist, with a managed secret, SSL verification enabled, merge request events enabled, and pipeline events enabled. If any of these is missing, repair tasks are not created for that project.

### Page permissions

**Shared Page Access** decides which read-only pages platform users may open. Each switch starts disabled, so the page is admin-only until you enable it:

| Control | Effect when enabled |
| --- | --- |
| **Allow Monitor for platform users** | Non-admin users can open the Monitor page with project-scoped stats and containers |
| **Allow Schedule Overview for platform users** | Non-admin users can inspect the scheduled queue for projects they can access |
| **Allow Analytics for platform users** | Non-admin users can open Analytics and only see data for projects they can access |

The page header summarizes how many of these are enabled under **Shared Pages**. These switches only matter while **Enable OIDC Login** is on; with OIDC login disabled every shared page stays open to all signed-in users. **OIDC Diagnostics** has no switch of its own and stays admin-only, because it lives inside the **Authentication** tab. The environment setting `allow_oidc_diagnostics_for_users` can still open its API to normal users; Configuration renders no control for it.

## GitLab and webhooks

### GitLab connection

**GitLab Connection** holds three values:

- **GitLab URL**: the base URL used for API calls, links, and repository operations.
- **GitLab Bot Token**: the token used to execute tasks. Only **GitLab Bot Token Status** is returned to the browser.
- **GitLab Admin Token**: used only for project webhook management, under **Webhook automation**. Only **GitLab Admin Token Status** is returned.

**Test GitLab connection** validates the values currently in the form, including unsaved ones, by calling the GitLab version and user endpoints. A successful test reports the server version and the authenticated username. If the project list looks stale, **Invalidate project cache** forces the next request to fetch a fresh list.

### Webhook automation

The callback URL Codify registers in GitLab is derived from the configured backend URL plus `/api/webhook/gitlab`. Setting up a webhook requires a valid http/https backend URL, **GitLab URL**, and **GitLab Admin Token**; a missing field is reported by name.

Choose a project from the overview table and use its **Set up project webhook** action to create or update the hook. The stored per-project secret is managed by Codify: the **Secret mode** column reports **per-project managed secret** when one exists, and **no local secret configured** when it does not. A rotating encryption key can leave a stored secret unreadable; in that case, re-running the setup issues a new secret for the project.

### Webhook overview

The overview scans every project visible to the configured admin token. The counters are **Projects**, **Configured**, **Needs attention**, and **Missing / error**. The search box filters by project path, status, or secret state, and **Refresh webhook statuses** re-scans.

| Column | Meaning |
| --- | --- |
| **Project** | Project path and ID, with the inline action for that row |
| **Status** | **Configured**, **Needs attention**, **Missing**, or **Error** |
| **Secret mode** | **per-project managed secret** or **no local secret configured** |
| **Checks** | **Hook**, **Notes**, **SSL**, **MR events**, and **Pipeline events** |
| **Detail** | The reason a project needs attention |

A project counts as **Configured** only when the hook exists with SSL verification, merge request events, and pipeline events all enabled. Otherwise it is **Needs attention**, with one of the recorded reasons such as `SSL verification disabled`, `MR events disabled`, or `Pipeline events missing`. A disabled merge request event also shows **MR events disabled — re-configure webhook to enable auto-close**, because issue auto-close depends on it.

The overview loads nothing until **GitLab URL** and a stored **GitLab Admin Token** are available.

### Webhook Events

**Webhook Events** (tab label **Webhook Events**, card title **Webhook Event Log**) lists received GitLab webhook events and their processing result: time, project ID, event type, action, MR IID, pipeline ID, issue, result, and detail. You can filter by result or by project ID and refresh the list.

Results recorded by the handler include **Issue closed**, **Already closed**, **No match**, **Unsupported event**, **Ignored action**, **Auth failed**, **CI failure collecting**, and **Duplicate**. An **Auth failed** row means the hook secret did not match; re-run the project webhook setup to restore it.

## Login and OIDC {deep}

### Provider basics

**Enable OIDC Login** makes the dashboard require GitLab sign-in. Turning it on also makes the dashboard APIs require GitLab sign-in, as the hint notes. Enabling it requires all four provider fields to be present, and the API refuses while any is empty: **Issuer URL**, **Client ID**, **Client Secret**, and **Redirect URI**.

**Client Secret Status** shows **Configured** or **Missing**; the actual secret is never returned to the browser, and leaving the field blank keeps the stored value. **Redirect URI** normally ends with `/api/auth/callback`.

The OAuth application must allow the scopes the dashboard requests: `openid profile email read_api`.

**Test OIDC connection** runs discovery against the values currently in the form, including unsaved ones. The result panel reports **OIDC discovery succeeded for issuer {issuer}. Required scopes: {scopes}.** It does not enable OIDC; configure and test first, then enable.

### Session and access

**Session Cookie Name**, **Session TTL (seconds)**, and **Session Retention (days)** control the session cookie and cleanup: sessions longer than the retention window are deleted after they expire or are revoked. **Cookie Secure** should stay enabled for HTTPS deployments. **Cookie SameSite** offers **Lax**, **Strict**, and **None**; **None** without secure cookies is rejected by many browsers, so the diagnostics surface that combination as a warning.

Session TTL values are clamped to the range 300 to 604800 seconds.

### Admin bootstrap

**Admin Usernames** is a comma-separated list of GitLab usernames that are granted the platform admin role at login. **Admin GitLab Groups** optionally lists group names checked during login; a user in any listed group is granted the admin role.

Bootstrap rules apply to accounts whose role has not been set manually. Changing a role on the **Access Management** page marks that account as a manual override, and later logins no longer recompute it. If group-based bootstrap is enabled while GitLab does not return groups in the claims or userinfo response, the grants never apply, and the diagnostics panel warns when that happens.

### OIDC diagnostics

**OIDC Diagnostics** (also reachable directly, since `/oidc-diagnostics` redirects to the Authentication tab) is a read-only snapshot of the effective runtime configuration:

- **Checks** runs live discovery and validates the authorization, token, and userinfo endpoints, the redirect URI, the required scopes, and the cookie policy.
- **Auth mode summary** shows whether OIDC login and break-glass login are enabled, the client ID and secret state, the cookie policy, and the session TTL.
- **Provider metadata** shows the discovery issuer and the endpoint values currently in use.
- **Required scopes** lists the scopes the GitLab OAuth application must allow.

Individual checks report **OK**, **Warning**, or **Error**. Typical warnings are a redirect URI outside `/api/auth/callback`, `COOKIE_SECURE=true` with an `http` redirect URI, an `https` redirect URI without secure cookies, a session TTL longer than 24 hours, `Cookie SameSite` set to `none` without secure cookies, and group-based bootstrap without groups in the login response.

When the discovery document cannot be fetched, the discovery check reports the error; treat that first, because the endpoint checks depend on it.

Break-glass login is environment-controlled and cannot be edited from this page. Keep it disabled during normal operation and use it only for OIDC recovery or administrator lockout, as the sign-in page states.

## AI providers

### Provider fields

**AI Providers** manages the model endpoints a task can use.

| Field | Notes |
| --- | --- |
| **Name** | Unique identifier (alphanumeric, hyphens, underscores), starting with a letter or digit |
| **Base URL** | Endpoint URL; must start with `http://` or `https://` |
| **Model** | Model identifier used during execution |
| **Max Turns** | Maximum agentic turns per task, 1 to 1000 |
| **API Key** | Not returned to the browser; **API key configured** or **No API key** shows the state, and a blank field keeps the existing key |
| **System Prompt** | System instructions appended to each AI execution, up to 10000 characters |
| **Status** | **Enabled** or **Disabled**; disabled providers cannot be selected when creating new tasks |

### Provider kind and wire protocol

**Provider Kind** and **Wire Protocol** are validated as a pair:

| Provider Kind | Allowed Wire Protocol | Used by |
| --- | --- | --- |
| **Anthropic Compatible** | **Anthropic Messages** | Claude, Pi, OpenCode |
| **OpenAI Compatible** | **OpenAI Responses** | Codex, Pi, OpenCode |
| **OpenAI Compatible** | **OpenAI Chat Completions** | Pi, OpenCode |

Claude accepts **Anthropic Messages** only and Codex accepts **OpenAI Responses** only; Pi and OpenCode accept any of the three. The API rejects a mismatched kind and protocol at save time, so a provider whose endpoint cannot serve its harness never reaches a container. [Harness Support](/guide/65-harness-support) covers the capabilities built on top of the protocol.

### Default, enable, and delete rules

Exactly one provider is the **Default**. **Set as Default** promotes a provider and demotes the previous default in the same operation. The rules the API enforces are:

- The first provider you create becomes the default automatically, and creating that first provider in a disabled state is refused.
- The default provider cannot be disabled while it is the default.
- A disabled provider cannot be set as the default.
- The last remaining provider cannot be deleted.
- A provider referenced by an active task (pending, queued, or running) cannot be deleted.
- Deleting the default provider promotes the lowest-id enabled provider, and is refused when no enabled provider remains.

### Connection test and advanced parameters

**Test connection** builds the smallest authenticated request for the provider's wire protocol and reports the round-trip latency. It fails with an explicit message when the credential is not active, when the request times out, or when the upstream returns a non-2xx status. Connection errors are logged with the endpoint target and a redacted request detail, so you can diagnose a failure without exposing the API key.

**Advanced request parameters** is a JSON object merged into every model request body for compatible harnesses. It is frozen into the task snapshot, which is non-sensitive, so never put API keys or other secrets there. The top level must be a JSON object, and fields owned by the harness are rejected; the error lists them by name.

## Worker profiles

The **Worker** tab separates the system baseline from the profiles built on top of it.

### Shared configuration and inheritance

**Shared configuration** is the system baseline: **Worker Kit**, shared volume mounts, shared environment variables, shared scripts, and shared run instructions. The revision, shown as **Revision {revision}**, increments on every save. **Save shared configuration** validates every enabled profile's combined configuration before committing, so a shared change can never leave an inheriting profile invalid. If another admin saved a newer revision while you were editing, the save is rejected with **The shared configuration changed. Reload this page before saving again.**

Profiles either follow the baseline or override individual entries. Each entry shows its **Source**:

- **System**: inherited unchanged.
- **Profile override**: replaced by this profile.
- **Masked in profile**: overridden with an empty value, disabling the shared entry for this profile.
- **Profile addition**: added by this profile only.

The actions **Override**, **Mask in this Profile**, **Restore system value**, and **Restore inheritance** move an entry between those states. Turning off **Follow system Worker Kit** makes delivery mode, version, and path an atomic group for the profile.

### Profile fields

**Worker Profiles** lists every profile with its name, default marker, disabled marker, and verification state. **Create profile**, **Duplicate**, and **Delete** manage the catalog; **Set default** marks the profile the Harness catalog falls back to when it is queried without a `worker_profile_id`, and **Enable** / **Disable** / **Force disable** control availability.

A profile defines:

- **Profile name** and **Worker image**.
- **Runtime delivery**: **Mounted worker kit** (the supported mode) or **Baked image (deprecated)**, which does not support Skills. **Worker kit version** and **Worker kit path** belong to the same group; the path hint states that it is an absolute path on the Docker host that Codify mounts to `/opt/codify-kit`, along with its `nix/store` to `/nix/store`.
- **Profile volume mounts** and **Profile environment variables**. A secret value is stored encrypted and never shown in the browser. Variable names must match `^[A-Z_][A-Z0-9_]*$`, and names reserved for the worker runtime are rejected, including the `ANTHROPIC_`, `CLAUDE_`, `CODEX_`, `CODIFY_`, `OPENAI_`, `OPENCODE_`, and `PI_` namespaces, which carry frozen provider, bundle, and harness state.
- **Custom Scripts**: **Pre Script** runs in `/workspace` after checkout and before AI execution; **Post Script** runs in `/workspace` after AI execution succeeds and before commit.
- **CodeGraph**, which enables the local CodeGraph MCP server and project index for tasks on the profile.
- **Harnesses** enabled for the profile, with **Default Harness** pre-selected for new tasks.
- **Default Skills**, inherited by new tasks unless the task overrides the selection. Skills require the minimum mounted-kit version listed in [Platform reference](/guide/96-platform-reference).

A profile that is still assigned to open issues cannot be disabled directly: **Disable** is refused while any non-closed issue points at the profile, and **Force disable** first asks for confirmation, naming the profile and warning that all its open issues will be closed. The default profile can neither be disabled nor deleted. Deletion is limited to disabled profiles that are not assigned to any issue.

### Docker target

Each profile can run on the shared execution target or on one of its own. **Use system Docker target** keeps the profile on the target the platform already uses; turning it off exposes **Docker Host** and the optional **TLS CA path**, **TLS client certificate path**, and **TLS client key path**. **Test connection** verifies the target, and a remote TCP endpoint configured without TLS is flagged with **This remote TCP endpoint is configured without TLS.**

### Runtime verification

**Profile runtime verification** records whether the profile's image and Worker Kit were probed. **Verify runtime** runs a deterministic Kit probe and a verification container, then freezes the observed identity into the profile. The badge shows **Verified**, **Unverified**, or **Verifying…**, together with a **Last checked** timestamp; a verification failure clears the state, so a profile cannot keep claiming a runtime that no longer matches.

**Worker Kit readiness** reports the harness inventory of the kit: each harness is **available** or **unavailable**, and an unavailable harness is annotated with one of these reasons: **not selected**, **missing payload**, or **reason unknown**. Readiness also reports **Ready**, **Not verified**, or **Runtime unavailable**.

### Workspace cleanup and artifacts

Two operational budgets sit above the profile list and apply to the whole platform.

**Workspace Cleanup** sets where issue workspaces live and how long issue workspaces and CI evidence bundles survive without file updates. A retention value of `0` disables automatic cleanup. The worker-local path belongs to deployment-time configuration: the field is read-only here, and a config request that carries `worker_workspace_host_path` is refused with a conflict, because workers that are already running would not honor a change.

**Task Artifacts** governs the artifact budget of a run: maximum total size in MiB, maximum single-file size in MiB, maximum files and directories, and how many days runtime archives are kept. The single-file limit cannot exceed the total limit; the panel reports **The single-file limit cannot exceed the total limit.** and the API rejects the pair. Expired runtime archives are deleted without deleting their Tasks or Issues.

### Task Snapshot and Runtime Bundle

Saving a profile does not change tasks that already exist. When a task is created, Codify freezes the profile into an immutable Task Snapshot and binds a content-addressed Runtime Bundle; the pair is what the worker container actually executes.

![You edit a Worker Profile; a task runs a frozen snapshot](assets/diagrams/en/profile-to-bundle.svg)

The Task Snapshot records the resolved values (**Worker image**, runtime mode, Worker Kit version and path, **Profile volume mounts**, **Profile environment variables**, scripts, run instructions, harness key, and the model endpoint), together with the shared configuration revision it was resolved against and a digest of the effective configuration. The Runtime Bundle is stored by digest and holds the frozen runtime source and Harness identity. Because the binding is immutable, editing a profile, a shared script, a Skill, or a provider only affects tasks created afterwards; the hint on the shared configuration card states the same rule for the baseline: **Changes become the baseline for future tasks created from profiles that follow the system value. Existing task snapshots do not change.** A task keeps running when you disable or edit a Skill or a provider, because the snapshot already carries what it needs.

The worker filesystem layout and the per-Harness state directories are documented in [Worker Runtime](/guide/92-worker-runtime).

## Prompt templates and skills {deep}

### Requirement templates

**Requirement Templates** manages the reusable bodies offered when a task is created.

| Field | Notes |
| --- | --- |
| **Name** | Short, reusable name so operators can identify the template |
| **Template Content** | The reusable prompt body, using variable placeholders |
| **Variable Tips** | Per-variable descriptions; variables not found in the content are reported as invalid |
| **Active** | Inactive templates stay stored but are hidden from task creation flows |
| **Tags** | Group templates for filtering in creation drawers |
| **Order** | Drag to reorder; the order is persisted |

Templates are reorderable as a whole list, and a reorder that references an unknown template is rejected. Deleting a template asks for confirmation because the action cannot be undone.

### Skills catalog

**Skills** manages reusable skill packages available to task harnesses. **New skill** opens the editor with **Basic information**, the **SKILL.md** editor, and **Supporting files**.

A skill is a complete directory package. The name must match the SKILL.md frontmatter, and the description comes from that frontmatter. Supporting files use nested relative paths, and importing a full package replaces SKILL.md and every supporting file.

The limits the editor enforces are:

| Limit | Value |
| --- | --- |
| SKILL.md size | 100,000 characters |
| Supporting files per skill | 128 |
| Single supporting file | 2 MiB |
| Complete skill package | 8 MiB |
| Path length | 240 characters |

Paths must be safe relative paths separated by `/`, without empty, `.`, or `..` segments, and a path nested below SKILL.md is invalid. Duplicate paths and paths that conflict with a directory in the hierarchy are both rejected.

**Available for new tasks** is the enable switch; disabling a skill does not affect existing task snapshots. **Download ZIP** exports the package, and the editor refuses to download while unsaved changes exist. **Delete** removes the skill after confirming that existing task snapshots are not affected.

Skills are executed by the worker kit, so a profile must use mounted-kit delivery at the minimum version listed in [Platform reference](/guide/96-platform-reference) to run them; **Default Skills** on a profile makes the selection the default for new tasks.

## Notifications and announcements {deep}

### Mattermost integration

**Mattermost Integration** configures the bot connection used by notification profiles. **Mattermost Server URL** is the base URL of the server, for example `https://mattermost.example.com`. **Mattermost Bot Token** is stored server-side: the panel shows only **Mattermost Bot Token Status**, and a blank field keeps the current token.

**Test Mattermost connection** authenticates against the server and reports the authenticated bot account; the result also confirms which URL was used.

### Notification profiles

**Notification Profiles** turns one connection into multiple delivery profiles, for example one channel notification and one initiator direct message. **Add profile** opens a modal grouped into **Profile basics**, **Target**, **Events**, and **Fields**.

- **Profile name** and **Profile enabled** identify the profile.
- **Target** is either **Mattermost channel** or **Initiator direct message**. An initiator direct message is sent when the username can be matched in Mattermost.
- For a channel target, enter the **Team name** and **Channel name** and use **Resolve channel target**. The profile cannot be saved before the target resolves, and the resolved card reports the team, channel, and channel ID. Channel targets can enable **Mention initiator in channel**, which prefixes the notification with the initiator's username; the switch is unavailable for other target types.
- **Events** must contain at least one subscription: **Task completed**, **Task failed**, **Task rescheduled**, **Task switched to execute now**, **Task retry scheduled**, or **Task cancelled**.
- **Fields** must contain at least one field to include: **Task ID**, **Project**, **Issue**, **Merge Request**, **Initiator**, **Status**, **Branch**, **Target branch**, **Scheduled time**, **Schedule change**, **Error summary**, or **Task link**.

Both validation errors are explicit: **Select at least one event** and **Select at least one field**. Profiles can be edited and deleted from the list.

### Announcement

**System Announcement** configures a system-wide message shown in the top bar for all authenticated users. **Enable Announcement** controls whether the banner appears; **Announcement Message** is the text, and the hint notes that HTML markup is supported. **Announcement Level** controls the style and color and accepts **Info**, **Warning**, **Error**, or **Success**.

The banner is read through an endpoint available to every authenticated user. Disable the announcement when the message no longer applies.
