"""V2-only execution contract policy.

Historical V1 contracts stay available to read APIs, but every executable
writer boundary requires an exact canonical V2 Task/Bundle identity.
"""

from __future__ import annotations

from app.core.harness_protocol import (
    CANONICAL_EVENT_SCHEMA_V2,
    HARNESS_CONTRACT_VERSION_V2,
)
from app.core.harness_registry import HarnessRegistryError, runtime_bundle_model_protocols

HARNESS_EXECUTION_MODES = frozenset({"v2_only"})

# Unified code for a legacy V1 contract that is not executable (v2_only).
LEGACY_CONTRACT_NOT_EXECUTABLE = "legacy_contract_not_executable"
MISSING_EXECUTION_ATTEMPT = "missing_execution_attempt"


class ExecutionPolicyError(ValueError):
    """A contract cannot be executed under the active harness execution mode."""

    def __init__(self, message: str, *, code: str = LEGACY_CONTRACT_NOT_EXECUTABLE) -> None:
        super().__init__(message)
        self.code = code


def validate_harness_execution_mode(mode: str) -> str:
    """Validate a harness execution mode, raising on unknowns.

    Called by Backend and Scheduler at startup so a misconfigured deployment
    fails fast instead of silently running under the wrong policy.
    """
    if mode not in HARNESS_EXECUTION_MODES:
        raise ExecutionPolicyError(
            f"HARNESS_EXECUTION_MODE must be one of {sorted(HARNESS_EXECUTION_MODES)}; "
            f"got {mode!r}",
            code="invalid_harness_execution_mode",
        )
    return mode


def require_explicit_harness_execution_mode(settings) -> str:
    """Fail startup when deployment omitted ``HARNESS_EXECUTION_MODE``.

    ``Settings`` retains a development-friendly typed default so pure imports
    and tooling remain usable, but long-running Backend/Scheduler processes must
    prove that their mode came from explicit configuration.
    """
    if "harness_execution_mode" not in getattr(settings, "model_fields_set", set()):
        raise ExecutionPolicyError(
            "HARNESS_EXECUTION_MODE must be explicitly configured for Backend and Scheduler",
            code="missing_harness_execution_mode",
        )
    return validate_harness_execution_mode(settings.harness_execution_mode)


def is_v2_only(mode: str) -> bool:
    """Return whether the only supported execution mode is selected."""
    return mode == "v2_only"


def _contract_is_v2(contract_version: str | None) -> bool:
    return contract_version == HARNESS_CONTRACT_VERSION_V2


def _attempt_is_v2(attempt) -> bool:
    return getattr(attempt, "event_schema", None) == CANONICAL_EVENT_SCHEMA_V2


def require_executable_contract(bundle) -> None:
    """Require an executable canonical contract on a bound Runtime Bundle.

    A bundle with no frozen contract is never executable. V1 bundles are
    historical read-only data and are rejected by the executable writer gate.
    """
    version = getattr(bundle, "contract_version", None)
    if version != HARNESS_CONTRACT_VERSION_V2:
        raise ExecutionPolicyError(
            f"Runtime Bundle has no executable canonical contract (contract_version={version!r})",
            code=(
                LEGACY_CONTRACT_NOT_EXECUTABLE
                if version == "codify.worker.harness/v1"
                else "missing_executable_contract"
            ),
        )


def require_executable_contract_v2(attempt, bundle) -> None:
    """Require an exact canonical V2 attempt AND a V2 Runtime Bundle."""
    require_executable_contract(bundle)
    if not _attempt_is_v2(attempt):
        raise ExecutionPolicyError(
            f"attempt {getattr(attempt, 'attempt_id', '?')} is not an exact V2 "
            f"attempt (event_schema={getattr(attempt, 'event_schema', None)!r})",
            code=LEGACY_CONTRACT_NOT_EXECUTABLE,
        )
    if getattr(bundle, "contract_version", None) != HARNESS_CONTRACT_VERSION_V2:
        raise ExecutionPolicyError(
            f"attempt {getattr(attempt, 'attempt_id', '?')} requires a V2 Runtime "
            f"Bundle (contract_version={getattr(bundle, 'contract_version', None)!r})",
            code=LEGACY_CONTRACT_NOT_EXECUTABLE,
        )


def require_task_executable_contract(
    task,
    bundle,
    mode: str,
    *,
    attempt=None,
    require_attempt_for_v2: bool = False,
) -> None:
    """Validate the complete frozen execution identity at a writer boundary.

    This is the central policy used by API writers, Scheduler claim/promotion,
    Worker start, and recovery.  It intentionally validates the immutable Task
    snapshot against the bound Bundle instead of trusting a route that happened
    to validate an earlier version of either row.
    """
    validate_harness_execution_mode(mode)
    require_executable_contract(bundle)

    snapshot = getattr(task, "worker_profile_snapshot", None)
    if snapshot is None:
        raise ExecutionPolicyError(
            f"task {getattr(task, 'id', '?')} has no immutable Worker snapshot",
            code="missing_execution_snapshot",
        )

    bundle_contract = getattr(bundle, "contract_version", None)
    snapshot_contract = getattr(snapshot, "runtime_contract_version", None)
    if snapshot_contract != bundle_contract:
        raise ExecutionPolicyError(
            f"task {getattr(task, 'id', '?')} snapshot/Bundle contract mismatch "
            f"(snapshot={snapshot_contract!r}, bundle={bundle_contract!r})",
            code="execution_contract_mismatch",
        )

    bundle_digest = getattr(bundle, "digest", None)
    snapshot_digest = getattr(snapshot, "runtime_bundle_digest", None)
    if not bundle_digest or snapshot_digest != bundle_digest:
        raise ExecutionPolicyError(
            f"task {getattr(task, 'id', '?')} snapshot/Bundle digest mismatch",
            code="execution_contract_mismatch",
        )

    harness_key = getattr(snapshot, "harness_key", None)
    adapters = (getattr(bundle, "manifest", None) or {}).get("adapters") or {}
    if not harness_key or harness_key not in adapters:
        raise ExecutionPolicyError(
            f"task {getattr(task, 'id', '?')} freezes an Adapter not present in its Bundle",
            code="execution_contract_mismatch",
        )

    endpoint_snapshot = getattr(snapshot, "model_endpoint_snapshot", None)
    if isinstance(endpoint_snapshot, dict):
        model_protocol = endpoint_snapshot.get("model_protocol")
        if model_protocol is None:
            # V1 snapshots used the pre-rename field.  The Bundle declaration
            # remains authoritative for this compatibility reader.
            model_protocol = endpoint_snapshot.get("wire_protocol")
        if not isinstance(model_protocol, str) or not model_protocol:
            raise ExecutionPolicyError(
                f"task {getattr(task, 'id', '?')} has an invalid model endpoint snapshot",
                code="execution_contract_mismatch",
            )
        try:
            declared_protocols = runtime_bundle_model_protocols(bundle, harness_key)
        except HarnessRegistryError as exc:
            raise ExecutionPolicyError(
                f"task {getattr(task, 'id', '?')} has an invalid frozen Bundle protocol declaration",
                code="execution_contract_mismatch",
            ) from exc
        if model_protocol.replace("-", "_") not in declared_protocols:
            raise ExecutionPolicyError(
                f"task {getattr(task, 'id', '?')} endpoint protocol is not declared by its frozen Bundle",
                code="execution_contract_mismatch",
            )

    if attempt is None:
        if require_attempt_for_v2:
            raise ExecutionPolicyError(
                f"task {getattr(task, 'id', '?')} has no durable execution attempt for V2 "
                "resume/recovery",
                code=MISSING_EXECUTION_ATTEMPT,
            )
        return

    if getattr(attempt, "harness_key", None) != harness_key:
        raise ExecutionPolicyError(
            f"attempt {getattr(attempt, 'attempt_id', '?')} does not match the "
            "Task snapshot Harness",
            code="execution_contract_mismatch",
        )
    require_executable_contract_v2(attempt, bundle)


def execution_rejection_detail(error: ExecutionPolicyError, *, action: str, subject) -> dict:
    """Return the stable structured API/Scheduler rejection payload."""
    return {
        "code": error.code,
        "message": str(error),
        "action": action,
        "subject": str(subject),
    }


def require_creatable_bundle_v2(bundle, mode: str, subject=None) -> None:
    """Refuse to create a Task that pins a non-V2 contract.

    Runs at the task-creation entry so a legacy V1 contract is rejected up
    front (``legacy_contract_not_executable``) instead of accepted and then
    terminalized by recovery.
    """
    validate_harness_execution_mode(mode)
    if getattr(bundle, "contract_version", None) != HARNESS_CONTRACT_VERSION_V2:
        raise ExecutionPolicyError(
            f"task {('for ' + str(subject)) if subject else ''}pins a non-V2 "
            f"Runtime Bundle and is not creatable under HARNESS_EXECUTION_MODE="
            f"v2_only (contract_version={getattr(bundle, 'contract_version', None)!r})",
            code=LEGACY_CONTRACT_NOT_EXECUTABLE,
        )


def is_legacy_snapshot(snapshot) -> bool:
    """True if a frozen Task snapshot pins a legacy V1 (or V1-carried) contract.

    A snapshot with ``runtime_contract_version == v2`` is V2 canonical; anything
    else (V1, null, unknown) is treated as legacy for startup remediation.
    """
    return not _contract_is_v2(getattr(snapshot, "runtime_contract_version", None))


def legacy_rejection_detail(attempt_or_task_id) -> dict:
    """Structured detail for the unified ``legacy_contract_not_executable`` code."""
    return {
        "code": LEGACY_CONTRACT_NOT_EXECUTABLE,
        "message": (
            "legacy V1 contract is not executable under HARNESS_EXECUTION_MODE="
            "v2_only; the container is stopped and the task terminalized"
        ),
        "subject": str(attempt_or_task_id),
    }
