"""Provider request options contract, pinned by the shared golden vectors.

The same vectors drive the Worker's Task-local Go proxy
(``deploy/worker-kit/model-proxy``), so Backend validation and merge semantics
cannot drift from the actual wire behavior of the Worker.
"""

import json
from pathlib import Path

import pytest

from app.core.provider_request_options import (
    RESERVED_REQUEST_FIELDS,
    merge_provider_request_options,
    reserved_request_fields,
    validate_provider_request_options,
)

GOLDEN_VECTORS_PATH = (
    Path(__file__).resolve().parents[3]
    / "deploy"
    / "worker-kit"
    / "model-proxy"
    / "testdata"
    / "golden_vectors.json"
)


@pytest.fixture(scope="module")
def golden_vectors() -> dict:
    return json.loads(GOLDEN_VECTORS_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "case",
    json.loads(GOLDEN_VECTORS_PATH.read_text(encoding="utf-8"))["merge_cases"],
    ids=lambda case: case["name"],
)
def test_merge_matches_shared_golden_vectors(case):
    body = dict(case["body"])
    options = dict(case["options"])

    merged = merge_provider_request_options(body, options)

    assert merged == case["expected"]
    assert body == case["body"], "merge must not mutate the Harness body"
    assert options == case["options"], "merge must not mutate provider_options"


def test_reserved_field_set_matches_golden_vectors(golden_vectors):
    assert sorted(RESERVED_REQUEST_FIELDS) == sorted(golden_vectors["reserved_request_fields"])


@pytest.mark.parametrize(
    "case",
    json.loads(GOLDEN_VECTORS_PATH.read_text(encoding="utf-8"))["reserved_rejection_cases"],
    ids=lambda case: case["name"],
)
def test_reserved_rejection_cases_report_the_declared_fields(case):
    options = case["options"]

    assert reserved_request_fields(options) == case["fields"]
    if case["fields"]:
        with pytest.raises(ValueError) as error:
            validate_provider_request_options(options)
        for field in case["fields"]:
            assert field in str(error.value)
    else:
        validate_provider_request_options(options)


@pytest.mark.parametrize(
    "case",
    json.loads(GOLDEN_VECTORS_PATH.read_text(encoding="utf-8"))["invalid_options_cases"],
    ids=lambda case: case["name"],
)
def test_non_object_provider_options_are_rejected(case):
    with pytest.raises(ValueError, match="must be an object"):
        validate_provider_request_options(case["options"])


def test_empty_options_are_valid_and_leave_the_body_unchanged():
    body = {"model": "qwen3", "messages": [{"role": "user", "content": "hi"}]}

    validate_provider_request_options({})

    assert merge_provider_request_options(body, {}) == body


def test_reserved_fields_never_replace_harness_structure():
    body = {
        "model": "qwen3",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
    }

    merged = merge_provider_request_options(
        body,
        {"model": "hijack", "messages": [], "stream": False, "temperature": 0.6},
    )

    assert merged == {**body, "temperature": 0.6}
