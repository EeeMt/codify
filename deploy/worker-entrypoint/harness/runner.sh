#!/bin/bash

codify_harness_initialize() {
    if [ "${CODIFY_HARNESS_INITIALIZED:-0}" -eq 1 ]; then
        return 0
    fi
    CODIFY_HARNESS_KEY="${CODIFY_HARNESS_KEY:-claude}"
    local adapter_path capabilities command_path frozen_adapter_version operation
    local resolved_adapter_version
    adapter_path="${CODIFY_ORCHESTRATION_DIR}/worker-entrypoint/harness/adapters/${CODIFY_HARNESS_KEY}.sh"
    [ -r "${adapter_path}" ] || {
        echo "Unsupported frozen Harness Adapter: ${CODIFY_HARNESS_KEY}" >&2
        return 1
    }
    # shellcheck source=/dev/null
    source "${adapter_path}"
    for operation in \
        metadata \
        verify_runtime \
        detect_capabilities \
        prepare_config \
        build_command \
        materialize_skills \
        stream_events \
        normalize_result \
        terminate \
        run
    do
        declare -F "adapter_${operation}" >/dev/null 2>&1 || {
            echo "Harness Adapter is missing required operation: ${operation}" >&2
            return 1
        }
    done
    local metadata
    metadata="$(adapter_metadata)" || return 1
    resolved_adapter_version="$(printf '%s' "${metadata}" | jq -er '.adapter_version')" || return 1
    frozen_adapter_version="${CODIFY_ADAPTER_VERSION:-}"
    if [ -n "${frozen_adapter_version}" ] \
        && [ "${frozen_adapter_version}" != "${resolved_adapter_version}" ]; then
        echo "Frozen Adapter version does not match Runtime Bundle metadata" >&2
        return 1
    fi
    CODIFY_ADAPTER_VERSION="${resolved_adapter_version}"
    CODIFY_CLI_VERSION="${CODIFY_CLI_VERSION:-unknown}"
    export CODIFY_HARNESS_KEY CODIFY_ADAPTER_VERSION
    export CODIFY_CLI_VERSION
    adapter_verify_runtime || return 1
    capabilities="$(adapter_detect_capabilities)" || return 1
    printf '%s' "${capabilities}" | jq -e 'type == "object"' >/dev/null || {
        echo "Harness Adapter capabilities must be a JSON object" >&2
        return 1
    }
    CODIFY_HARNESS_CAPABILITIES="${capabilities}"
    export CODIFY_HARNESS_CAPABILITIES
    # Ordered common step: validate the frozen provider_options, start the
    # Task-local egress proxy and mirror the frozen Base URL before the Adapter
    # maps its protocol endpoint. Adapters only consume the mirrored variable.
    codify_model_proxy_start || return 1
    adapter_prepare_config || return 1
    adapter_materialize_skills || return 1
    command_path="$(adapter_build_command)" || return 1
    case "${command_path}" in
        /*) ;;
        *) echo "Harness Adapter command must be an absolute path" >&2; return 1 ;;
    esac
    [ -x "${command_path}" ] || {
        echo "Harness Adapter command is unavailable: ${command_path}" >&2
        return 1
    }
    CODIFY_HARNESS_COMMAND="${command_path}"
    export CODIFY_HARNESS_COMMAND
    local event_bytes
    event_bytes=$(wc -c < "${CODIFY_RUNTIME_DIR}/event.jsonl" 2>/dev/null || printf 'unreadable')
    echo "Canonical event stream before initialization: ${event_bytes} bytes"
    if [ ! -s "${CODIFY_RUNTIME_DIR}/event.jsonl" ]; then
        # A fresh container can inherit no canonical events. Reset only the
        # advisory writer lock in that case; a recovered live container keeps
        # its stream intact (seq is derived from the stream, not a side file).
        rm -f "${CODIFY_RUNTIME_DIR}/.event.lock"
        if [ -n "${CODIFY_HARNESS_SANDBOX_MODE:-}" ]; then
            codify_emit_event "run.started" \
                "$(jq -nc --arg runtime_bundle_digest "${CODIFY_RUNTIME_BUNDLE_DIGEST:-}" --arg sandbox_mode "${CODIFY_HARNESS_SANDBOX_MODE:-}" '{runtime_bundle_digest:$runtime_bundle_digest, sandbox_mode:$sandbox_mode}')" \
                || return 1
        else
            codify_emit_event "run.started" \
                "$(jq -nc --arg runtime_bundle_digest "${CODIFY_RUNTIME_BUNDLE_DIGEST:-}" '{runtime_bundle_digest:$runtime_bundle_digest}')" \
                || return 1
        fi
        echo "Canonical attempt initialized: ${CODIFY_ATTEMPT_ID}"
    fi
    CODIFY_HARNESS_INITIALIZED=1
}

codify_harness_capability_enabled() {
    local capability="$1"
    [ -n "${CODIFY_HARNESS_CAPABILITIES:-}" ] \
        && printf '%s' "${CODIFY_HARNESS_CAPABILITIES}" \
            | jq -e --arg capability "${capability}" '.[$capability] == true' >/dev/null
}

codify_harness_run() {
    local prompt_file="$1"
    local result_file="$2"
    local errexit_enabled=0
    case "$-" in
        *e*) errexit_enabled=1 ;;
    esac
    if ! codify_harness_initialize; then
        CODIFY_HARNESS_KEY="${CODIFY_HARNESS_KEY:-unknown}"
        CODIFY_ADAPTER_VERSION="${CODIFY_ADAPTER_VERSION:-unknown}"
        CODIFY_CLI_VERSION="${CODIFY_CLI_VERSION:-unknown}"
        export CODIFY_HARNESS_KEY CODIFY_ADAPTER_VERSION CODIFY_CLI_VERSION
        if ! codify_event_type_exists "run.started"; then
            if ! codify_emit_event "run.started" \
                "$(jq -nc --arg runtime_bundle_digest "${CODIFY_RUNTIME_BUNDLE_DIGEST:-}" '{runtime_bundle_digest:$runtime_bundle_digest}')"; then
                echo "Could not initialize canonical attempt" >&2
                CODIFY_HARNESS_TERMINAL_SEEN=1
                return 1
            fi
        fi
        if ! codify_event_type_exists "harness.completed" \
            && ! codify_event_type_exists "harness.failed"; then
            codify_emit_event "harness.failed" \
                '{"failure":{"kind":"configuration_error","message":"Harness Adapter initialization failed"}}'
        fi
        CODIFY_HARNESS_TERMINAL_SEEN=1
        return 1
    fi
    set +e
    # Run the adapter as a background job and wait on it so the SIGTERM trap
    # interrupts immediately. A foreground child would otherwise defer the trap
    # until the CLI exits, letting `docker stop` escalate to SIGKILL before the
    # finalizer can emit a cancelled terminal.
    adapter_run "${prompt_file}" "${result_file}" &
    CODIFY_HARNESS_ADAPTER_PID=$!
    export CODIFY_HARNESS_ADAPTER_PID
    local adapter_pid="${CODIFY_HARNESS_ADAPTER_PID}"
    wait "${adapter_pid}"
    local result=$?
    CODIFY_HARNESS_ADAPTER_PID=""
    export CODIFY_HARNESS_ADAPTER_PID
    adapter_normalize_result "${result_file}"
    local normalize_result=$?
    if [ "${errexit_enabled}" -eq 1 ]; then
        set -e
    else
        set +e
    fi
    if [ "${normalize_result}" -ne 0 ]; then
        if ! codify_event_type_exists "harness.completed" \
            && ! codify_event_type_exists "harness.failed"; then
            local normalization_failure_kind="protocol_error"
            case "${result}" in
                124) normalization_failure_kind="timeout" ;;
                130 | 137 | 143) normalization_failure_kind="cancelled" ;;
            esac
            # The Adapter's legacy result carries the CLI error text when it
            # aborted before producing a canonical result. Preserve it instead
            # of reporting a generic normalization failure.
            local adapter_failure_message
            adapter_failure_message=$(jq -r \
                'select(.success == false) | .result // empty' \
                "${result_file}" 2>/dev/null | tail -n 1)
            adapter_failure_message="${adapter_failure_message:0:2000}"
            codify_emit_event "harness.failed" \
                "$(jq -nc \
                    --arg kind "${normalization_failure_kind}" \
                    --arg message "${adapter_failure_message:-Harness result normalization failed}" \
                    '{failure:{kind:$kind,message:$message}}')"
        fi
        result=1
    fi
    if codify_event_type_exists "harness.completed" || codify_event_type_exists "harness.failed"; then
        CODIFY_HARNESS_TERMINAL_SEEN=1
    else
        codify_emit_event "harness.failed" \
            "$(jq -nc --argjson exit_code "${result}" '{failure:{kind:"protocol_error",message:"Harness stream ended without result",exit_code:$exit_code}}')"
        CODIFY_HARNESS_TERMINAL_SEEN=1
    fi
    # A Harness process can exit cleanly after reporting a provider or runtime
    # failure (Pi's owner deliberately uses a clean exit for a settled turn).
    # The canonical terminal event is authoritative for the worker boundary;
    # never let a zero process exit enter delivery after `harness.failed`.
    if [ "${result}" -eq 0 ] && codify_event_type_exists "harness.failed"; then
        result=1
    fi
    # The proxy stays up for the rest of the worker lifetime: the harness also
    # serves the commit-message and MR-summary run_text calls during delivery,
    # and every one of them must observe the same frozen request options. The
    # signal trap and EXIT finalizer stop it.
    return "${result}"
}

codify_harness_run_text() {
    # The frozen V2 manifest no longer advertises run_text/codegraph, so judge
    # the optional capability by the Adapter actually exporting it (codex
    # exports a stub that returns non-zero and falls back, as before).
    if ! declare -F adapter_run_text >/dev/null 2>&1; then
        echo "Harness Adapter does not support run_text" >&2
        return 1
    fi
    adapter_run_text "$@"
}

# ---------------------------------------------------------------------------
# Task-local model request options proxy.
#
# The Backend freezes the Provider's non-sensitive provider_options into
# CODIFY_MODEL_PROVIDER_OPTIONS_JSON. When it is non-empty the common runner
# starts the Kit's Task-local egress proxy, mirrors the frozen upstream Base
# URL onto the loopback listener, and lets every Adapter keep consuming its
# normal ANTHROPIC_BASE_URL / OPENAI_BASE_URL variable. Adapters never parse,
# filter or merge provider_options themselves.
# ---------------------------------------------------------------------------

CODIFY_MODEL_PROXY_BIN="${CODIFY_MODEL_PROXY_BIN:-${CODIFY_KIT_HOME:-/opt/codify-kit}/bin/codify-model-proxy}"
CODIFY_MODEL_PROXY_READINESS="${CODIFY_RUNTIME_DIR}/model-proxy-readiness.json"
CODIFY_MODEL_PROXY_OPTIONS_FILE="${CODIFY_RUNTIME_DIR}/model-proxy-options.json"
CODIFY_MODEL_PROXY_PID=""
CODIFY_MODEL_PROXY_PROTOCOL=""

# Preserve the frozen upstream path: only the scheme and authority are
# replaced, so Adapter URL normalization produces the same final request path
# as the direct-connection path.
codify_model_proxy_mirror_base_url() {
    local upstream="$1"
    local authority="$2"
    local rest="${upstream#*://}"
    local path=""
    case "${rest}" in
        */*) path="/${rest#*/}" ;;
    esac
    case "${path}" in
        *'?'*) path="${path%%\?*}" ;;
    esac
    printf 'http://%s%s' "${authority}" "${path}"
}

codify_model_proxy_upstream_base_url() {
    case "${CODIFY_MODEL_PROXY_PROTOCOL}" in
        anthropic_messages) printf '%s' "${ANTHROPIC_BASE_URL:-}" ;;
        openai_responses | openai_chat_completions) printf '%s' "${OPENAI_BASE_URL:-}" ;;
        *) printf '' ;;
    esac
}

codify_model_proxy_start() {
    local options_json="${CODIFY_MODEL_PROVIDER_OPTIONS_JSON:-}"
    if [ -z "${options_json}" ]; then
        return 0
    fi
    if ! printf '%s' "${options_json}" | jq -e 'type == "object" and length > 0' >/dev/null 2>&1; then
        echo "Frozen provider_options is not a non-empty JSON object" >&2
        return 1
    fi
    local protocol="${CODIFY_MODEL_PROTOCOL:-anthropic_messages}"
    case "${protocol}" in
        anthropic_messages | openai_responses | openai_chat_completions) ;;
        *)
            echo "Frozen model protocol has no proxy target path: ${protocol}" >&2
            return 1
            ;;
    esac
    CODIFY_MODEL_PROXY_PROTOCOL="${protocol}"
    local upstream
    upstream="$(codify_model_proxy_upstream_base_url)"
    if [ -z "${upstream}" ]; then
        echo "Frozen model Base URL is unavailable for protocol ${protocol}" >&2
        return 1
    fi
    if [ ! -x "${CODIFY_MODEL_PROXY_BIN}" ]; then
        echo "Model request options proxy is unavailable: ${CODIFY_MODEL_PROXY_BIN}" >&2
        return 1
    fi
    if ! printf '%s' "${options_json}" | jq -S -c '.' > "${CODIFY_MODEL_PROXY_OPTIONS_FILE}" 2>/dev/null; then
        echo "Frozen provider_options could not be materialized" >&2
        return 1
    fi
    chmod 600 "${CODIFY_MODEL_PROXY_OPTIONS_FILE}" 2>/dev/null || true
    rm -f "${CODIFY_MODEL_PROXY_READINESS}"
    "${CODIFY_MODEL_PROXY_BIN}" \
        --listen 127.0.0.1:0 \
        --upstream "${upstream}" \
        --protocol "${protocol}" \
        --options-file "${CODIFY_MODEL_PROXY_OPTIONS_FILE}" \
        --readiness "${CODIFY_MODEL_PROXY_READINESS}" &
    CODIFY_MODEL_PROXY_PID=$!
    export CODIFY_MODEL_PROXY_PID
    local attempt=0
    while [ "${attempt}" -lt 200 ]; do
        attempt=$((attempt + 1))
        if [ -s "${CODIFY_MODEL_PROXY_READINESS}" ]; then
            break
        fi
        if ! kill -0 "${CODIFY_MODEL_PROXY_PID}" 2>/dev/null; then
            echo "Model request options proxy exited before readiness" >&2
            CODIFY_MODEL_PROXY_PID=""
            export CODIFY_MODEL_PROXY_PID
            return 1
        fi
        sleep 0.05
    done
    local listen_addr
    listen_addr="$(jq -r '.listen // empty' "${CODIFY_MODEL_PROXY_READINESS}" 2>/dev/null)"
    if [ -z "${listen_addr}" ]; then
        echo "Model request options proxy did not become ready" >&2
        codify_model_proxy_stop
        return 1
    fi
    local mirror
    mirror="$(codify_model_proxy_mirror_base_url "${upstream}" "${listen_addr}")"
    case "${protocol}" in
        anthropic_messages)
            export ANTHROPIC_BASE_URL="${mirror}"
            ;;
        *)
            export OPENAI_BASE_URL="${mirror}"
            ;;
    esac
    echo "Model request options proxy active for protocol ${protocol}"
    return 0
}

codify_model_proxy_stop() {
    if [ -z "${CODIFY_MODEL_PROXY_PID:-}" ]; then
        return 0
    fi
    local pid="${CODIFY_MODEL_PROXY_PID}"
    CODIFY_MODEL_PROXY_PID=""
    export CODIFY_MODEL_PROXY_PID
    if kill -0 "${pid}" 2>/dev/null; then
        kill -TERM "${pid}" 2>/dev/null || true
        local attempt=0
        while [ "${attempt}" -lt 100 ] && kill -0 "${pid}" 2>/dev/null; do
            attempt=$((attempt + 1))
            sleep 0.05
        done
        kill -KILL "${pid}" 2>/dev/null || true
    fi
    wait "${pid}" 2>/dev/null || true
    rm -f "${CODIFY_MODEL_PROXY_READINESS}" 2>/dev/null || true
    return 0
}
