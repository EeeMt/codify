#!/bin/bash
# Pi adapter for the Codify harness contract (V2, open-harness-v2 Phase 2).

CODIFY_PI_TRANSLATOR="${CODIFY_ORCHESTRATION_DIR}/worker-entrypoint/harness/adapters/pi_events.py"
CODIFY_PI_BRIDGE="${CODIFY_ORCHESTRATION_DIR}/worker-entrypoint/harness/adapters/pi_bridge.py"

codify_pi_bin() {
    # Frozen single source: the backend-injected CODIFY_HARNESS_CLI_BIN (Kit
    # inventory path or authorized host_mount), else the Kit manifest's own
    # inventory path. The runtime image and PATH are never consulted.
    if [ -n "${CODIFY_HARNESS_CLI_BIN:-}" ]; then
        printf '%s\n' "${CODIFY_HARNESS_CLI_BIN}"
        return 0
    fi
    if [ -r "${CODIFY_KIT_HOME:-/opt/codify-kit}/manifest.json" ]; then
        local path
        path="$(jq -r --arg k pi '.harness_inventory[$k].path // empty' \
            "${CODIFY_KIT_HOME:-/opt/codify-kit}/manifest.json" 2>/dev/null || true)"
        if [ -n "${path}" ]; then
            printf '%s\n' "${path}"
            return 0
        fi
    fi
    return 1
}

pi_adapter_metadata() {
    jq -c \
        --arg key pi \
        --arg contract "${CODIFY_RUNTIME_CONTRACT_VERSION:-codify.worker.harness/v2}" \
        --arg event_schema "codify.worker.event/v2" \
        '{ key: $key,
           adapter_version: (.adapters.pi.version // .adapters.pi.adapter.version // ""),
           adapter_digest: (.adapters.pi.digest // ""),
           contract_version: $contract,
           event_schema: $event_schema }' \
        "${CODIFY_ORCHESTRATION_DIR}/worker-entrypoint/harness/manifest.json"
}

pi_adapter_verify_runtime() {
    local bin
    bin="$(codify_pi_bin)" || {
        echo "Pi CLI is not available from the Worker Kit inventory" >&2
        return 1
    }
    if [ ! -x "${bin}" ]; then
        echo "Pi CLI is unavailable: ${bin}" >&2
        return 1
    fi
    CODIFY_PI_BIN="${bin}"
    export CODIFY_PI_BIN
    local version_output pinned normalized
    version_output="$("${bin}" --version 2>/dev/null | head -n 1)"
    if [ -z "${version_output}" ]; then
        echo "Could not read Pi CLI version" >&2
        return 1
    fi
    # pi --version may print "pi 0.84.2" or bare "0.84.2"; normalize to the
    # trailing token before comparing against the manifest pin.
    normalized="$(printf '%s\n' "${version_output}" | awk '{print $NF}')"
    CODIFY_CLI_VERSION="${normalized}"
    export CODIFY_CLI_VERSION
    # The Adapter-declared pinned version is the tested/baseline, not a hard
    # gate: an observed difference only logs a sanitized advisory warning and
    # execution continues (§11.2 Compatibility policy).
    local pinned
    pinned="$(jq -r '.adapters.pi.cli_version // empty' \
        "${CODIFY_ORCHESTRATION_DIR}/worker-entrypoint/harness/manifest.json" 2>/dev/null || true)"
    if [ -n "${pinned}" ] && [ "${normalized}" != "${pinned}" ]; then
        echo "WARNING: Pi CLI version ${normalized} differs from the Adapter baseline ${pinned} (advisory, not enforced)" >&2
    fi
    return 0
}

pi_adapter_detect_capabilities() {
    jq -c '.adapters.pi.capabilities // {}' \
        "${CODIFY_ORCHESTRATION_DIR}/worker-entrypoint/harness/manifest.json"
}

pi_adapter_subagent_payload_dir() {
    # Kit-fixed payload root. It lives inside the Kit's immutable runtime
    # closure, so it is resolved from the manifest's own ``runtime_bin`` rather
    # than copied a second time into the image. The root holds Codify's policy
    # (config.json, settings.json, the four agent definitions) plus the pinned
    # upstream package under node_modules/pi-subagents, which is the load path.
    # Absence is not an error: a Bundle built without it runs Pi without
    # delegation.
    local kit_home="${CODIFY_KIT_HOME:-/opt/codify-kit}"
    local runtime_bin candidate
    runtime_bin="$(jq -r '.runtime_bin // empty' "${kit_home}/manifest.json" 2>/dev/null || true)"
    # The manifest reports the in-container store path; resolve it both through
    # /nix/store (when the launcher has linked it) and directly under the
    # mounted Kit so the lookup never depends on that link existing yet.
    local store_relative="${runtime_bin#/nix/store/}"
    store_relative="${store_relative%/bin}"
    for candidate in \
        "$(dirname "${runtime_bin:-/nonexistent}")/../lib/codify-pi-subagents" \
        "${kit_home}/nix/store/${store_relative}/lib/codify-pi-subagents" \
        "${kit_home}/harness/pi/extensions/pi-subagents"; do
        if [ -f "${candidate}/config.json" ] \
            && [ -f "${candidate}/node_modules/pi-subagents/index.ts" ]; then
            (cd "${candidate}" && pwd -P)
            return 0
        fi
    done
    return 0
}

# Materialize the Codify capability ceiling for the Kit-fixed pi-subagents.
#
# The plugin reads its policy from ~/.pi/agent/extensions/subagent/config.json
# and its agent inventory from ~/.pi/agent/agents, while Pi-level switches live
# in ~/.pi/agent/settings.json. Only the four approved agents exist because the
# bundle ships exactly those definitions and `disableBuiltins` hides the
# plugin's own set (open-harness-v2-subagent-adaptation.md §6.4).
pi_adapter_materialize_subagents() {
    local payload_dir extension_dir
    payload_dir="$(pi_adapter_subagent_payload_dir)"
    if [ -z "${payload_dir}" ]; then
        export CODIFY_PI_SUBAGENTS=0
        return 0
    fi
    extension_dir="${payload_dir}/node_modules/pi-subagents"
    export CODIFY_PI_SUBAGENT_EXTENSION="${extension_dir}"
    export CODIFY_PI_SUBAGENTS=1
    # The cloned repository is untrusted: the ceiling hides project agent
    # definitions, project settings and package-provided subagents from the
    # plugin's discovery, so only the four definitions written below can exist
    # (open-harness-v2-subagent-adaptation.md §6.4). Children inherit this
    # variable, and the vendor patch reads it.
    export CODIFY_PI_SUBAGENT_ISOLATED=1

    export CODIFY_PI_CLI_HOME="${CODIFY_PI_CLI_HOME:-/home/codify}"
    local agent_dir="${CODIFY_PI_CLI_HOME}/.pi/agent"
    local ceiling_dir="${agent_dir}/extensions/subagent"
    mkdir -p "${ceiling_dir}" "${agent_dir}/agents"

    cp "${payload_dir}/config.json" "${ceiling_dir}/config.json"
    cp "${payload_dir}/agents/"*.md "${agent_dir}/agents/"

    # Merge only the subagents block so any other Pi setting stays intact.
    local settings_file="${agent_dir}/settings.json"
    local fragment="${payload_dir}/settings.json"
    if [ -f "${settings_file}" ]; then
        jq -s '.[0] * .[1]' "${settings_file}" "${fragment}" > "${settings_file}.merged" \
            && mv "${settings_file}.merged" "${settings_file}"
    else
        cp "${fragment}" "${settings_file}"
    fi

    chown -R "${CODIFY_RUN_UID:-1000}:${CODIFY_RUN_GID:-1000}" \
        "${ceiling_dir}" "${agent_dir}/agents" "${settings_file}" 2>/dev/null || true
    chmod 600 "${settings_file}" 2>/dev/null || true
    printf 'Pi subagents enabled: %s (ceiling applied)\n' "${extension_dir}"
}

pi_adapter_prepare_config() {
    # Persist the Pi session on the issue-shared volume so a later continue task
    # can resume the same conversation across containers. Fall back to the
    # per-task runtime dir when the shared volume is absent.
    if [ -d "/opt/codify-issue-shared" ] && [ -w "/opt/codify-issue-shared" ]; then
        export PI_HOME="/opt/codify-issue-shared/pi-home"
    else
        export PI_HOME="${CODIFY_RUNTIME_DIR}/pi-home"
    fi
    # pi-run.sh passes this directory explicitly through --session-dir. Pi
    # does not use the application-specific PI_HOME variable for native
    # session storage, so keeping the path explicit is part of the adapter
    # contract rather than relying on the CLI subprocess HOME.
    mkdir -p "${PI_HOME}/sessions"
    chown -R "${CODIFY_RUN_UID:-1000}:${CODIFY_RUN_GID:-1000}" "${PI_HOME}" 2>/dev/null || true

    # Export the Pi transport/model identity so events.py forms the correct V2
    # harness envelope. The capability list comes from the frozen manifest;
    # the selected protocol below only chooses the Snapshot endpoint mapping.
    export CODIFY_HARNESS_CONTROL_TRANSPORT_KIND="${CODIFY_HARNESS_CONTROL_TRANSPORT_KIND:-rpc_stdio}"
    export CODIFY_HARNESS_CONTROL_TRANSPORT_PROTOCOL="${CODIFY_HARNESS_CONTROL_TRANSPORT_PROTOCOL:-pi-rpc}"

    # Model endpoint mapping. The Snapshot's model / base URL / credential are
    # frozen by the backend and injected through the environment namespace for
    # the selected protocol. Harness-specific variables and user config cannot
    # override that Snapshot.
    # Pi reads custom providers from ~/.pi/agent/models.json; we
    # translate the frozen snapshot into that file so the CLI uses EXACTLY the
    # Snapshot endpoint. Pi's own native config must never override the Snapshot,
    # so we do not read any pre-existing user models.json (PI_HOME is ephemeral).
    local model_protocol="${CODIFY_MODEL_PROTOCOL:-anthropic_messages}"
    local manifest_path="${CODIFY_ORCHESTRATION_DIR}/worker-entrypoint/harness/manifest.json"
    local declared_model_protocols
    declared_model_protocols="$(jq -er \
        '.adapters.pi.model_protocols | select(type == "array" and length > 0) | join(",")' \
        "${manifest_path}" 2>/dev/null)" || {
        echo "Pi Runtime Bundle manifest has no model protocol declaration" >&2
        return 1
    }
    if ! jq -e --arg protocol "${model_protocol}" \
        '.adapters.pi.model_protocols | index($protocol) != null' \
        "${manifest_path}" >/dev/null 2>&1; then
        echo "Pi Runtime Bundle does not declare model protocol ${model_protocol}" >&2
        return 1
    fi
    export CODIFY_HARNESS_MODEL_PROTOCOLS="${declared_model_protocols}"

    local model base_url api_key api
    case "${model_protocol}" in
        anthropic_messages)
            model="${ANTHROPIC_MODEL:-}"
            base_url="${ANTHROPIC_BASE_URL:-}"
            # Pi's Anthropic implementation passes this value to the Anthropic
            # SDK, whose request path already includes /v1/messages.  The
            # shared Snapshot stores OpenRouter's OpenAI-style /api/v1 root,
            # so remove exactly that suffix for Pi only; otherwise the SDK
            # requests /api/v1/v1/messages and OpenRouter returns 404.
            case "${base_url}" in
                */v1/) base_url="${base_url%/v1/}" ;;
                */v1) base_url="${base_url%/v1}" ;;
            esac
            api_key="${ANTHROPIC_API_KEY:-}"
            api="anthropic-messages"
            ;;
        openai_responses)
            model="${OPENAI_MODEL:-}"
            base_url="${OPENAI_BASE_URL:-}"
            api_key="${OPENAI_API_KEY:-}"
            api="openai-responses"
            ;;
        openai_chat_completions)
            model="${OPENAI_MODEL:-}"
            base_url="${OPENAI_BASE_URL:-}"
            api_key="${OPENAI_API_KEY:-}"
            api="openai-completions"
            ;;
        *)
            echo "Pi does not support model protocol ${model_protocol} in this Runtime Bundle" >&2
            return 1
            ;;
    esac
    # Pi's OpenAI-compatible providers expect a versioned base URL and append
    # the protocol path themselves.  Keep the Snapshot root unchanged for
    # already-versioned endpoints, but match OpenCode's /v1 normalization for
    # providers such as OpenCode Zen whose stored root is /zen/go.
    case "${model_protocol}" in
        openai_responses|openai_chat_completions)
            if [ -n "${base_url}" ]; then
                case "${base_url}" in
                    */v1|*/v1/) base_url="${base_url%/}" ;;
                    *) base_url="${base_url%/}/v1" ;;
                esac
            fi
            ;;
    esac
    if [ -n "${model}" ] && [ -n "${base_url}" ] && [ -n "${api_key}" ]; then
        # pi 0.84.2 reads custom providers only from ~/.pi/agent/models.json
        # (the CLI subprocess HOME); it ignores the PI_HOME env var. Keep the
        # configuration path aligned with the HOME used by pi-run.sh after the
        # CLI drops to the worker identity. PI_HOME above is ONLY for the
        # issue-shared session/skills persistence.
        # The CLI parses only the array form of providers.<name>.models, so the
        # frozen Snapshot must be written in that shape or --list-models is
        # empty and every prompt fails with "Model not found".
        export CODIFY_PI_CLI_HOME="${CODIFY_PI_CLI_HOME:-/home/codify}"
        local models_file="${CODIFY_PI_CLI_HOME}/.pi/agent/models.json"
        mkdir -p "$(dirname "${models_file}")"
        # The provider id/name are namespaced to Codify so Pi never shares state
        # with another harness; baseUrl is the frozen Snapshot endpoint.
        jq -nc \
            --arg model "${model}" \
            --arg base_url "${base_url}" \
            --arg api_key "${api_key}" \
            --arg api "${api}" \
            '{providers:{codify:{baseUrl:$base_url,api:$api,apiKey:$api_key,models:[{id:$model,name:$model,reasoning:false,input:["text"],contextWindow:128000,maxTokens:8192}]}}}' \
            > "${models_file}"
        # The adapter prepares this directory as root before Pi drops to the
        # worker identity. Pi also creates its session directory below it, so
        # the worker must own the directory tree, not only models.json.
        chown -R "${CODIFY_RUN_UID:-1000}:${CODIFY_RUN_GID:-1000}" "$(dirname "${models_file}")" 2>/dev/null || true
        chown "${CODIFY_RUN_UID:-1000}:${CODIFY_RUN_GID:-1000}" "${models_file}" 2>/dev/null || true
        chmod 600 "${models_file}" 2>/dev/null || true
    fi
    pi_adapter_materialize_subagents
    return 0
}

pi_adapter_build_command() {
    echo "${CODIFY_ORCHESTRATION_DIR}/worker-entrypoint/harness/runners/pi-run.sh"
}

pi_adapter_materialize_skills() {
    # Pi discovers skills under its CLI HOME (${CODIFY_PI_CLI_HOME}/.pi/agent/skills)
    # and from the shared agentskills.io layout. Materialize the sealed
    # per-task Skill snapshot (packaged as .claude/skills) there; PI_HOME is an
    # application-private directory Pi never scans.
    if [ -z "${CODIFY_TASK_SKILLS_DIR:-}" ]; then
        return 0
    fi
    local src="${CODIFY_TASK_SKILLS_DIR}/.claude/skills"
    if [ ! -d "${src}" ]; then
        echo "Task Skills snapshot does not contain skills: ${src}" >&2
        return 1
    fi
    local dest="${CODIFY_PI_CLI_HOME:-/home/codify}/.pi/agent/skills"
    mkdir -p "${dest}"
    if ! cp -a "${src}/." "${dest}/" 2>/dev/null; then
        echo "Could not materialize skills into ${dest}" >&2
        return 1
    fi
    chown -R "${CODIFY_RUN_UID:-1000}:${CODIFY_RUN_GID:-1000}" "${dest}" 2>/dev/null || true
    return 0
}

pi_adapter_run() {
    local prompt_file="$1"
    local result_file="$2"
    local raw_file="${CODIFY_HARNESS_RAW_DIR}/pi.jsonl"
    : > "${raw_file}"
    chown 0:0 "${raw_file}"
    chmod 644 "${raw_file}"
    # Keep the root adapter/translator as the audit owner, but run the Pi
    # process itself as the unprivileged workspace user. Otherwise a Harness
    # git commit can leave root-owned .git metadata and make the outer Worker
    # delivery commit fail when runtime-generated files (for example Python
    # __pycache__) are present.
    CODIFY_PI_RUN_AS="${CODIFY_PI_RUN_AS:-${CODIFY_RUN_AS:-}}" \
    CODIFY_PI_BIN="$(codify_pi_bin)" \
    CODIFY_PI_RAW_EVENT_JSONL="${raw_file}" \
    CODIFY_PI_EVENT_TRANSLATOR="${CODIFY_PI_TRANSLATOR}" \
    CODIFY_PI_BRIDGE="${CODIFY_PI_BRIDGE}" \
    CODIFY_CANONICAL_EVENT_WRITER="${CODIFY_CANONICAL_EVENT_WRITER}" \
    ARTIFACT_DIR="${CODIFY_RUNTIME_DIR}" \
    CI_CLAUDE_DISABLE_CONSOLE_TEE=1 \
    PROMPT_FILE="${prompt_file}" \
    PI_SESSION_DIR="${CODIFY_RUNTIME_DIR}/pi-session" \
    timeout "${TASK_TIMEOUT:-1800}" "${CODIFY_HARNESS_COMMAND}" > "${result_file}"
}

pi_adapter_stream_events() {
    local raw_file="$1"
    python3 "${CODIFY_PI_TRANSLATOR}" --raw-file "${raw_file}"
}

pi_adapter_normalize_result() {
    local result_file="$1"
    local authoritative="${CODIFY_HARNESS_RESULT_FILE:-${result_file}}"
    [ -s "${authoritative}" ] || return 1
    # Pi is a V2-only adapter: the harness identity is nested under `harness`.
    jq -e \
        --arg harness_key pi \
        --arg adapter_version "${CODIFY_ADAPTER_VERSION}" \
        --arg cli_version "${CODIFY_CLI_VERSION}" \
        '.schema == "codify.worker.result/v2"
         and .harness.key == $harness_key
         and .harness.adapter_version == $adapter_version
         and .harness.cli_version == $cli_version
         and .harness.control_transport.kind != null
         and (.harness.model_protocols | type == "array")
         and (.harness.model_protocols | length > 0)
         and (.status | IN("completed", "failed", "cancelled", "protocol_error"))
         and (.success | type == "boolean")
         and (.usage | type == "object")
         and (.capability_warnings | type == "array")' \
        "${authoritative}" >/dev/null || return 1
    return 0
}

pi_adapter_terminate() {
    # SIGTERM: prefer a native abort/close over the shared Runner grace -> KILL.
    # The running pi RPC only sees an abort via the request pipe; when this runs
    # under the container signal path the pipe fd may already be gone, so fall
    # back to a TERM to the process group (the shared Runner grace then KILLs).
    local pid="${1:-${PI_PID:-}}"
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
        kill -TERM "${pid}" 2>/dev/null || true
    fi
    return 0
}

adapter_metadata() { pi_adapter_metadata "$@"; }
adapter_verify_runtime() { pi_adapter_verify_runtime "$@"; }
adapter_detect_capabilities() { pi_adapter_detect_capabilities "$@"; }
adapter_prepare_config() { pi_adapter_prepare_config "$@"; }
adapter_build_command() { pi_adapter_build_command "$@"; }
adapter_materialize_skills() { pi_adapter_materialize_skills "$@"; }
adapter_stream_events() { pi_adapter_stream_events "$@"; }
adapter_normalize_result() { pi_adapter_normalize_result "$@"; }
adapter_run() { pi_adapter_run "$@"; }
adapter_terminate() { pi_adapter_terminate "$@"; }
