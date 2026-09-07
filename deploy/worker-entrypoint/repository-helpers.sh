# Repository delivery, timing, and preparation artifact helpers.

repo_log() {
    printf '[repo] %s\n' "$*"
}

# ---------------------------------------------------------------------------
# Git-delivery reconciliation: pinned start points, fact collection, remote
# verification and safe fast-forward publishing. Facts are structured by
# git-delivery.py; the shell drives network operations (fetch/push) that need
# the task credentials and records the outcome back into the snapshot.
# ---------------------------------------------------------------------------


repo_now_ms() {
    local now
    now=$(date +%s%3N 2>/dev/null || true)
    case "${now}" in
        *[!0-9]* | "") printf '%s000\n' "$(date +%s)" ;;
        *) printf '%s\n' "${now}" ;;
    esac
}

repo_delivery_snapshot_value() {
    # repo_delivery_snapshot_value <jq-filter> [default]
    local filter="$1"
    local default_value="${2:-}"
    jq -r "${filter} // empty" "${GIT_DELIVERY_SNAPSHOT_FILE}" 2>/dev/null \
        | { IFS= read -r value || value="${default_value}"; printf '%s\n' "${value}"; }
}
repo_delivery_run_python() {
    # Git work runs as the unprivileged workspace owner; printf %q keeps empty
    # values, spaces and punctuation intact through the clean inner shell.
    local helper_args
    helper_args=$(printf '%q ' "$@")
    codify_run_shell "python3 '${GIT_DELIVERY_HELPER}' ${helper_args}" nonlogin
}

repo_delivery_prepare_state_dir() {
    local meta_dir="${CODIFY_ISSUE_META_DIR:-/opt/codify-issue-meta}"
    local state_dir="${meta_dir}/git-delivery"
    [ -d "${meta_dir}" ] && [ ! -L "${meta_dir}" ] || {
        repo_log "error delivery_pending reason=meta_dir_missing"
        return 1
    }
    if [ "${CODIFY_DELIVERY_TEST_MODE:-0}" = "1" ]; then
        mkdir -p "${state_dir}" && chmod 700 "${state_dir}"
        return
    fi
    if [ -L "${state_dir}" ] \
        || { [ -e "${state_dir}" ] && [ ! -d "${state_dir}" ]; } \
        || { [ -d "${state_dir}" ] \
            && [ "$(stat -c '%u:%g' "${state_dir}" 2>/dev/null || printf invalid)" != "0:0" ]; }; then
        rm -rf "${state_dir}" || return 1
    fi
    mkdir -p "${state_dir}" || return 1
    chown 0:0 "${meta_dir}" "${state_dir}" || return 1
    chmod 755 "${meta_dir}" && chmod 700 "${state_dir}"
}

repo_delivery_root_seal() {
    local path="$1" mode="$2"
    if chown 0:0 "${path}" 2>/dev/null && chmod "${mode}" "${path}" 2>/dev/null; then
        return 0
    fi
    [ "${CODIFY_DELIVERY_TEST_MODE:-0}" = "1" ] || return 1
    chmod "${mode}" "${path}" 2>/dev/null
}

repo_delivery_install_snapshot() {
    local candidate="$1"
    if ! jq -e \
        'type == "object" and (.git_delivery | type == "object")' \
        "${candidate}" >/dev/null 2>&1; then
        rm -f "${candidate}"
        return 1
    fi
    repo_delivery_root_seal "${candidate}" 444 || return 1
    mv -f "${candidate}" "${GIT_DELIVERY_SNAPSHOT_FILE}" || return 1
    repo_delivery_root_seal "${GIT_DELIVERY_SNAPSHOT_FILE}" 444
}

repo_delivery_freeze_pending() {
    local pending="${CODIFY_ISSUE_META_DIR:-/opt/codify-issue-meta}/git-delivery/pending.json"
    rm -f "${GIT_DELIVERY_PENDING_FROZEN_FILE}"
    [ -f "${pending}" ] || return 0
    local state schema branch head attempt task
    state=$(jq -r '.state // empty' "${pending}" 2>/dev/null || true)
    schema=$(jq -r '.schema // empty' "${pending}" 2>/dev/null || true)
    [ "${state}" = "pending" ] || return 0
    [ "${schema}" = "codify.git-delivery.pending/v1" ] || return 0
    branch=$(jq -r '.branch // empty' "${pending}" 2>/dev/null || true)
    head=$(jq -r '.head_sha // empty' "${pending}" 2>/dev/null || true)
    attempt=$(jq -r '.attempt_id // empty' "${pending}" 2>/dev/null || true)
    task=$(jq -r '.task_id // empty' "${pending}" 2>/dev/null || true)
    case "${branch}:${head}:${attempt}:${task}" in
        *:*:*:) return 0 ;;
    esac
    [ "${branch}" = "${BRANCH_NAME}" ] || return 0
    printf '%s\n' "${head}" | grep -Eq '^[0-9a-f]{40}$' || return 0
    if ! codify_run_shell "cd /workspace && git cat-file -e '${head}^{commit}'" 2>/dev/null; then
        return 0
    fi
    cp "${pending}" "${GIT_DELIVERY_PENDING_FROZEN_FILE}" || return 1
    repo_delivery_root_seal "${GIT_DELIVERY_PENDING_FROZEN_FILE}" 444 || return 1
}

repo_delivery_network_env() {
    # Network Git must not read the Harness-controlled repository config. Keep
    # only transport settings that are intentionally supplied by the worker.
    local network_command="${GIT_DELIVERY_GIT_BIN:-git}"
    if [ "${1:-}" = "python3" ]; then
        network_command="${GIT_DELIVERY_PYTHON_BIN:-python3}"
        shift
    elif [ "${1:-}" = "git" ]; then
        shift
    fi
    env -i \
        PATH="${PATH}" HOME=/root \
        GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
        GIT_CONFIG_COUNT=4 \
        GIT_CONFIG_KEY_0=http.sslVerify GIT_CONFIG_VALUE_0="${GIT_DELIVERY_SSL_VERIFY}" \
        GIT_CONFIG_KEY_1=http.sslCAInfo GIT_CONFIG_VALUE_1="${GIT_DELIVERY_SSL_CAINFO}" \
        GIT_CONFIG_KEY_2=protocol.ext.allow GIT_CONFIG_VALUE_2=never \
        GIT_CONFIG_KEY_3=http.extraHeader GIT_CONFIG_VALUE_3="PRIVATE-TOKEN: ${GIT_DELIVERY_TOKEN:-}" \
        GIT_NO_REPLACE_OBJECTS=1 GIT_NO_LAZY_FETCH=1 GIT_TERMINAL_PROMPT=0 \
        GIT_ALTERNATE_OBJECT_DIRECTORIES="${GIT_DELIVERY_OBJECTS_DIR}" \
        HTTP_PROXY="${HTTP_PROXY:-}" HTTPS_PROXY="${HTTPS_PROXY:-}" ALL_PROXY="${ALL_PROXY:-}" \
        NO_PROXY="${NO_PROXY:-}" http_proxy="${http_proxy:-}" https_proxy="${https_proxy:-}" \
        all_proxy="${all_proxy:-}" no_proxy="${no_proxy:-}" \
        REAL_GIT="${REAL_GIT:-}" \
        REQUESTS_CA_BUNDLE="${REQUESTS_CA_BUNDLE:-}" SSL_CERT_FILE="${SSL_CERT_FILE:-}" \
        "${network_command}" "$@"
}

repo_delivery_init_remote_repo() {
    if [ -n "${GIT_DELIVERY_REMOTE_REPO:-}" ] && [ -d "${GIT_DELIVERY_REMOTE_REPO}" ]; then
        return 0
    fi
    GIT_DELIVERY_REMOTE_REPO="${CODIFY_RUNTIME_DIR}/git-delivery-remote.git"
    GIT_DELIVERY_OBJECTS_DIR="/workspace/.git/objects"
    export GIT_DELIVERY_REMOTE_REPO GIT_DELIVERY_OBJECTS_DIR
    if [ ! -d "${GIT_DELIVERY_OBJECTS_DIR}" ]; then
        repo_log "error delivery_remote_repo reason=objects_missing"
        return 1
    fi
    mkdir -p "${GIT_DELIVERY_REMOTE_REPO}"
    if [ ! -f "${GIT_DELIVERY_REMOTE_REPO}/HEAD" ]; then
        repo_delivery_network_env init --bare -q "${GIT_DELIVERY_REMOTE_REPO}" || return 1
    fi
    chmod 700 "${GIT_DELIVERY_REMOTE_REPO}" || return 1
}

repo_delivery_ensure_pinned_remote() {
    repo_delivery_init_remote_repo
}

repo_delivery_remote_tip() {
    # Work-branch tip of the frozen repository URL; failures remain unconfirmed.
    local refs tip
    repo_delivery_init_remote_repo || return 1
    set +e
    refs=$(repo_delivery_network_env git --git-dir "${GIT_DELIVERY_REMOTE_REPO}" \
        ls-remote --heads "${GIT_DELIVERY_REMOTE_URL}" "refs/heads/${BRANCH_NAME}" 2>/dev/null)
    local query_result=$?
    set -e
    [ "${query_result}" -eq 0 ] || return 1
    tip=$(printf '%s\n' "${refs}" \
        | awk -v ref="refs/heads/${BRANCH_NAME}" '$2 == ref {print $1; exit}')
    [ -z "${tip}" ] || printf '%s\n' "${tip}"
}

repo_delivery_fetch_branch() {
    repo_delivery_init_remote_repo || return 1
    local depth_args=()
    if [ -n "${CODIFY_GIT_CLONE_DEPTH}" ]; then
        depth_args=(--depth "${CODIFY_GIT_CLONE_DEPTH}")
    fi
    repo_delivery_network_env git --git-dir "${GIT_DELIVERY_REMOTE_REPO}" \
        fetch "${depth_args[@]}" "${GIT_DELIVERY_REMOTE_URL}" \
        "+refs/heads/${BRANCH_NAME}:refs/remotes/codify-delivery/${BRANCH_NAME}" 2>/dev/null
}

repo_delivery_local_tip() {
    repo_delivery_network_env git --git-dir "${GIT_DELIVERY_REMOTE_REPO}" \
        rev-parse "refs/remotes/codify-delivery/${BRANCH_NAME}" 2>/dev/null || true
}

repo_delivery_pending_write() {
    local head_sha="$1" tmp
    local pending_dir="${CODIFY_ISSUE_META_DIR:-/opt/codify-issue-meta}/git-delivery"
    [ -d "${pending_dir}" ] || return 1
    tmp="${pending_dir}/pending.json.$$.tmp"
    jq -nc --arg task_id "${TASK_ID:-}" --arg attempt_id "${CODIFY_ATTEMPT_ID:-}" \
        --arg branch "${BRANCH_NAME}" --arg head_sha "${head_sha}" \
        '{schema:"codify.git-delivery.pending/v1",state:"pending",task_id:$task_id,attempt_id:$attempt_id,branch:$branch,head_sha:$head_sha}' \
        > "${tmp}" || return 1
    if ! chown 0:0 "${tmp}" 2>/dev/null; then
        [ "${CODIFY_DELIVERY_TEST_MODE:-0}" = "1" ] || return 1
    fi
    chmod 600 "${tmp}" 2>/dev/null || return 1
    mv -f "${tmp}" "${pending_dir}/pending.json" || return 1
    if ! chown 0:0 "${pending_dir}/pending.json" 2>/dev/null; then
        [ "${CODIFY_DELIVERY_TEST_MODE:-0}" = "1" ] || return 1
    fi
    chmod 600 "${pending_dir}/pending.json" 2>/dev/null || return 1
}

repo_delivery_pending_confirmed_and_clear() {
    local pending_dir="${CODIFY_ISSUE_META_DIR:-/opt/codify-issue-meta}/git-delivery"
    [ -d "${pending_dir}" ] || return 0
    local pending="${pending_dir}/pending.json" tmp
    [ -f "${pending}" ] || return 0
    tmp="${pending}.confirmed.$$.tmp"
    jq '.state = "confirmed"' "${pending}" > "${tmp}" || return 1
    if ! chown 0:0 "${tmp}" 2>/dev/null; then
        [ "${CODIFY_DELIVERY_TEST_MODE:-0}" = "1" ] || return 1
    fi
    chmod 600 "${tmp}" 2>/dev/null || return 1
    mv -f "${tmp}" "${pending}" || return 1
    if ! chown 0:0 "${pending}" 2>/dev/null; then
        [ "${CODIFY_DELIVERY_TEST_MODE:-0}" = "1" ] || return 1
    fi
    chmod 600 "${pending}" 2>/dev/null || return 1
    rm -f "${pending}" || return 1
}
repo_delivery_classify() {
    # repo_delivery_classify <head_sha> <remote_tip> <start_remote>
    # Prints the classify_remote decision JSON. Exit 0 on success.
    repo_delivery_network_env python3 "${GIT_DELIVERY_HELPER}" \
        classify_remote \
        --work-dir "${GIT_DELIVERY_REMOTE_REPO}" \
        --head "$1" \
        --remote-tip "$2" \
        --start-remote "$3"
}

repo_write_preparation_artifact() {
    local elapsed_ms="$1"
    local actual_shallow="$2"
    local effective_filter="$3"
    local commit_sha="$4"
    local pack_size="$5"
    local status="$6"
    local phase="$7"
    local exit_code="$8"

    jq -n \
        --arg status "${status}" \
        --arg phase "${phase}" \
        --arg action "${REPO_ACTION}" \
        --arg workspace "${REPO_WORKSPACE_STATE}" \
        --arg configured_depth "${CODIFY_GIT_CLONE_DEPTH}" \
        --arg configured_filter "${CODIFY_GIT_CLONE_FILTER}" \
        --arg actual_shallow "${actual_shallow}" \
        --arg effective_filter "${effective_filter}" \
        --arg fallback "${REPO_FALLBACK}" \
        --arg remote_work_branch "${REPO_REMOTE_WORK_BRANCH}" \
        --arg previous_remote_work_sha "${REPO_PREVIOUS_REMOTE_WORK_SHA}" \
        --arg remote_work_sha "${REPO_REMOTE_WORK_SHA}" \
        --arg work_branch_relation "${REPO_WORK_BRANCH_RELATION}" \
        --arg sync_action "${REPO_SYNC_ACTION}" \
        --arg base_branch "${BASE_BRANCH}" \
        --arg work_branch "${BRANCH_NAME}" \
        --arg commit_sha "${commit_sha}" \
        --arg pack_size "${pack_size}" \
        --argjson elapsed_ms "${elapsed_ms}" \
        --argjson exit_code "${exit_code}" \
        '{
            status: $status,
            phase: $phase,
            exit_code: $exit_code,
            action: $action,
            workspace_reused: ($workspace == "reused"),
            configured_depth: (
                if $configured_depth == "" then null else ($configured_depth | tonumber) end
            ),
            configured_filter: (
                if $configured_filter == "" then null else $configured_filter end
            ),
            actual_shallow: (
                if $actual_shallow == "true" then true
                elif $actual_shallow == "false" then false
                else null end
            ),
            effective_filter: (
                if $effective_filter == "" then null else $effective_filter end
            ),
            fallback: (if $fallback == "" then null else $fallback end),
            remote_work_branch: ($remote_work_branch == "true"),
            previous_remote_work_sha: (
                if $previous_remote_work_sha == "" then null else $previous_remote_work_sha end
            ),
            remote_work_sha: (
                if $remote_work_sha == "" then null else $remote_work_sha end
            ),
            work_branch_relation: (
                if $work_branch_relation == "" then null else $work_branch_relation end
            ),
            sync_action: (if $sync_action == "" then null else $sync_action end),
            base_branch: $base_branch,
            work_branch: $work_branch,
            commit_sha: $commit_sha,
            pack_size: (if $pack_size == "" then null else $pack_size end),
            elapsed_ms: $elapsed_ms
        }' > "${REPOSITORY_PREPARATION_FILE}"
    chmod 644 "${REPOSITORY_PREPARATION_FILE}" 2>/dev/null || true
    codify_chown "${REPOSITORY_PREPARATION_FILE}" 2>/dev/null || true
    REPO_PREPARATION_ARTIFACT_WRITTEN=1
}

repo_finalize_preparation_on_exit() {
    local exit_code="${1:-1}"
    if [ "${REPO_PREPARATION_ACTIVE:-0}" -ne 1 ] \
        || [ "${REPO_PREPARATION_ARTIFACT_WRITTEN:-0}" -eq 1 ]; then
        return 0
    fi

    local finished_ms elapsed_ms actual_shallow effective_filter commit_sha pack_size
    finished_ms=$(repo_now_ms)
    elapsed_ms=$((finished_ms - REPO_PREPARE_STARTED_MS))
    actual_shallow="unknown"
    effective_filter=""
    commit_sha="unknown"
    pack_size=""
    if [ -d /workspace/.git ]; then
        actual_shallow=$(codify_run_shell 'cd /workspace && git rev-parse --is-shallow-repository' 2>/dev/null || echo "unknown")
        effective_filter=$(codify_run_shell 'cd /workspace && git config --get remote.origin.partialclonefilter' 2>/dev/null || true)
        commit_sha=$(codify_run_shell 'cd /workspace && git rev-parse --short HEAD' 2>/dev/null || echo "unknown")
        pack_size=$(codify_run_shell 'cd /workspace && git count-objects -vH' 2>/dev/null | awk -F': ' '$1 == "size-pack" {print $2}' || true)
    fi
    repo_log "failed action=${REPO_ACTION} phase=${REPO_PREPARATION_PHASE} exit=${exit_code} elapsed_ms=${elapsed_ms}"
    repo_write_preparation_artifact \
        "${elapsed_ms}" \
        "${actual_shallow}" \
        "${effective_filter}" \
        "${commit_sha}" \
        "${pack_size}" \
        "failed" \
        "${REPO_PREPARATION_PHASE}" \
        "${exit_code}"
}
