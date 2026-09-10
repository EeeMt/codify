#!/bin/bash
set -u

# Minimal Codex runner: drive one Codex App Server thread over stdio, stream
# native JSON-RPC notifications through the Codex event translator, and persist
# a canonical harness result.
#
# Privilege model mirrors claude-run.sh: the Codex CLI subprocess runs as the
# worker runtime user (CODIFY_CODEX_RUN_AS, i.e. codify), while the bridge,
# translator, and audit stream stay in the root orchestration context.

CODIFY_CODEX_BIN="${CODIFY_CODEX_BIN:?CODIFY_CODEX_BIN is required (resolved by the codex adapter from the Kit inventory or an authorized host_mount)}"
CODIFY_CODEX_RAW_EVENT_JSONL="${CODIFY_CODEX_RAW_EVENT_JSONL:-${CODIFY_RUNTIME_DIR}/harness-events/codex.jsonl}"
CODIFY_CODEX_EVENT_TRANSLATOR="${CODIFY_CODEX_EVENT_TRANSLATOR:-${CODIFY_ORCHESTRATION_DIR}/worker-entrypoint/harness/adapters/codex_events.py}"
CODIFY_CODEX_BRIDGE="${CODIFY_CODEX_BRIDGE:-${CODIFY_ORCHESTRATION_DIR}/worker-entrypoint/harness/adapters/codex_bridge.py}"
PROMPT_FILE="${PROMPT_FILE:-${CODIFY_HARNESS_PROMPT_FILE:-}}"
CODIFY_RESUME_SESSION="${CODIFY_RESUME_SESSION:-${RESUME_SESSION:-}}"

mkdir -p "$(dirname "${CODIFY_CODEX_RAW_EVENT_JSONL}")"

if [ -z "${PROMPT_FILE}" ] || [ ! -s "${PROMPT_FILE}" ]; then
    echo "Codex prompt file is missing: ${PROMPT_FILE}" >&2
    exit 1
fi

export CODEX_HOME="${CODEX_HOME:-${CODIFY_RUNTIME_DIR}/codex-home}"
mkdir -p "${CODEX_HOME}"

STREAM_DIR=$(mktemp -d)
STREAM_FIFO="${STREAM_DIR}/codex-stream.fifo"
mkfifo "${STREAM_FIFO}"
trap 'rm -rf "${STREAM_DIR}"' EXIT

set +e
# Keep bridge and translator as separate processes so the bridge contains no
# event projection logic. The FIFO gives the translator the native server
# stream immediately while preserving independent exit codes.
python3 "${CODIFY_CODEX_EVENT_TRANSLATOR}" \
    --raw-file "${CODIFY_CODEX_RAW_EVENT_JSONL}" < "${STREAM_FIFO}" &
translator_pid=$!

BRIDGE_COMMAND=(
    python3 "${CODIFY_CODEX_BRIDGE}"
    --codex-bin "${CODIFY_CODEX_BIN}"
    --prompt-file "${PROMPT_FILE}"
)
if [ -n "${CODIFY_RESUME_SESSION:-}" ]; then
    BRIDGE_COMMAND+=(--resume-session "${CODIFY_RESUME_SESSION}")
fi
"${BRIDGE_COMMAND[@]}" > "${STREAM_FIFO}" &
bridge_pid=$!

wait "${bridge_pid}"
bridge_exit_code=$?
wait "${translator_pid}"
translator_exit_code=$?
set -e

# Stream the authoritative result on stdout (the same contract as the Claude
# runner) so main.sh can read `.result` for the delivery summary and commit
# prompts, then decide the exit code from the result status.
CODIFY_HARNESS_RESULT_FILE="${CODIFY_HARNESS_RESULT_FILE:-${CODIFY_RUNTIME_DIR}/harness-result.json}"
result_status="$(jq -r '.status // empty' "${CODIFY_HARNESS_RESULT_FILE}" 2>/dev/null || true)"
if [ -n "${result_status}" ] && [ -s "${CODIFY_HARNESS_RESULT_FILE}" ]; then
    cat "${CODIFY_HARNESS_RESULT_FILE}"
fi
case "${result_status}" in
    completed)
        # codex may still exit non-zero on benign per-item errors after a
        # completed turn; a completed turn is authoritative for delivery.
        exit 0
        ;;
    failed)
        # A failed turn means the agent did not finish its work: the attempt fails.
        exit 1
        ;;
esac

if [ "${bridge_exit_code}" -ne 0 ]; then
    exit "${bridge_exit_code}"
fi
exit "${translator_exit_code}"
