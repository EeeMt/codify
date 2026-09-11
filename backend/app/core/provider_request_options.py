"""Provider request options contract.

``provider_options`` is an arbitrary, non-sensitive JSON object that a Provider
administrator wants merged into the Harness' model request body.  The Backend
validates it at Provider write time and merges it into the connection-test
body; the Worker's Task-local egress proxy performs the identical merge on the
live Harness request.

Both implementations are pinned by one set of golden vectors
(``deploy/worker-kit/model-proxy/testdata/golden_vectors.json``) so Backend
validation cannot drift from the Worker's actual wire behavior.
"""

from __future__ import annotations

from typing import Any

# Harness/Model-Endpoint owned request fields.  These carry the conversation,
# tool declarations and streaming contract, so a Provider option must never
# replace them; the merge drops them and Provider write APIs reject them.
RESERVED_REQUEST_FIELDS = frozenset(
    {
        "model",
        "messages",
        "input",
        "instructions",
        "tools",
        "tool_choice",
        "stream",
        "stream_options",
    }
)


def reserved_request_fields(options: Any) -> list[str]:
    """Return the reserved top-level keys present in ``options``."""
    if not isinstance(options, dict):
        return []
    return sorted(key for key in options if key in RESERVED_REQUEST_FIELDS)


def validate_provider_request_options(options: Any) -> None:
    """Validate the stored ``provider_options`` contract.

    Raises ``ValueError`` with a stable, field-naming message so Provider
    create/update and connection test all report the same 422 detail.
    """
    if not isinstance(options, dict):
        raise ValueError("provider_options must be an object")
    reserved = reserved_request_fields(options)
    if reserved:
        raise ValueError(
            "provider_options may not set reserved request fields: "
            + ", ".join(reserved)
        )


def merge_provider_request_options(body: dict, options: dict) -> dict:
    """Recursively merge non-reserved ``options`` over the Harness ``body``.

    Objects merge recursively; arrays, scalars and ``null`` replace the base
    value wholesale.  The base object and the options are never mutated.
    """
    merged: dict[str, Any] = dict(body)
    for key, value in options.items():
        if key in RESERVED_REQUEST_FIELDS:
            continue
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = merge_provider_request_options(current, value)
        else:
            merged[key] = value
    return merged
