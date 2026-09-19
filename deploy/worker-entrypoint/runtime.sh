# Runtime exports, custom hooks, events, and archive lifecycle.

codify_startup_now_ms() {
    local now
    now=$(date +%s%3N 2>/dev/null || true)
    case "${now}" in
        *[!0-9]* | "") printf '%s000\n' "$(date +%s)" ;;
        *) printf '%s\n' "${now}" ;;
    esac
}

codify_startup_log() {
    local phase="$1"
    local started_ms="$2"
    local status="${3:-completed}"
    local finished_ms duration_ms elapsed_ms
    finished_ms="$(codify_startup_now_ms)"
    duration_ms=$((finished_ms - started_ms))
    elapsed_ms=$((finished_ms - CODIFY_STARTUP_STARTED_MS))
    if [ "${duration_ms}" -lt 0 ]; then duration_ms=0; fi
    if [ "${elapsed_ms}" -lt 0 ]; then elapsed_ms=0; fi
    printf '[startup] phase=%s duration_ms=%s elapsed_ms=%s status=%s\n' \
        "${phase}" "${duration_ms}" "${elapsed_ms}" "${status}"
}

export ANTHROPIC_BASE_URL
export ANTHROPIC_API_KEY
export ANTHROPIC_AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-${ANTHROPIC_API_KEY}}"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="${CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:-1}"
export SANDBOX_MODE=1
export CLAUDE_MAX_TURNS="${CLAUDE_MAX_TURNS:-20}"
export CLAUDE_MODEL="${ANTHROPIC_MODEL}"
export APPEND_SYSTEM_PROMPT
FINAL_SUMMARY_CONTENT=""
FINAL_CHANGED_FILES_TEXT=""
FINAL_COMMIT_MESSAGE=""
FINAL_OVERALL_SUMMARY=""

append_runtime_event() {
    local event_json="$1"
    if [ -n "${event_json}" ] && [ -d "${CODIFY_RUNTIME_DIR}" ]; then
        printf '%s\n' "${event_json}" >> "${CODIFY_RUNTIME_DIR}/event.jsonl"
    fi
}

run_worker_script() {
    local phase="$1"
    local script_path="$2"

    if [ ! -s "${script_path}" ]; then
        return 0
    fi

    echo "Running custom ${phase} script..."

    set +e
    codify_run_shell "cd /workspace && export PATH=\"${CODIFY_RUNTIME_PATH}\" && \"${CODIFY_BASH}\" \"${script_path}\""
    local script_result=$?
    set -e

    if [ ${script_result} -ne 0 ]; then
        echo "Custom ${phase} script failed with exit code: ${script_result}"
        return ${script_result}
    fi

    echo "Custom ${phase} script completed successfully"
    return 0
}
