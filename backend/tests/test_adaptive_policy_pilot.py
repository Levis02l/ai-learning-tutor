import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from eval.validate_adaptive_policy_pilot import (
    DEFAULT_DATASET_PATH,
    load_and_validate_pilot,
)


def test_pilot_dataset_validates_and_is_separate_from_formal() -> None:
    dataset = load_and_validate_pilot()

    assert dataset.status == "development_pilot_not_formal"
    assert len(dataset.scenarios) == 8
    assert dataset.topology.group_count == 4
    assert dataset.topology.condition_artifact_count == 16
    assert (
        dataset.topology.planned_canonical_response_execution_count
        == 15
    )
    assert dataset.topology.expected_successful_provider_generation_count == 15
    assert dataset.generation_control.identical_policy_case_ids == [
        "adaptive_pilot_p01_medium"
    ]


def test_pilot_rejects_locked_formal_question() -> None:
    payload = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
    payload["scenarios"][0]["question"] = (
        "Explain why Lloyd's algorithm for K-means Clustering can converge "
        "to a local rather than a global minimum."
    )
    payload["scenarios"][1]["question"] = payload["scenarios"][0]["question"]

    path = _write_payload(payload)
    with pytest.raises(ValueError, match="duplicates formal questions"):
        load_and_validate_pilot(path)


def test_pilot_requires_null_similarity_for_frozen_evidence() -> None:
    payload = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
    payload["evidence_fixtures"][0]["evidence_state"][
        "top_similarity"
    ] = 0.9

    path = _write_payload(payload)
    with pytest.raises(ValidationError):
        load_and_validate_pilot(path)


def test_pilot_fixture_hash_covers_metadata() -> None:
    payload = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
    payload["evidence_fixtures"][0]["page_targets"] = [999]

    path = _write_payload(payload)
    with pytest.raises(ValidationError, match="fixture SHA256"):
        load_and_validate_pilot(path)


def test_pilot_recomputes_provider_call_accounting() -> None:
    payload = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
    payload["generation_control"][
        "expected_successful_provider_generation_count"
    ] = 14
    payload["topology"]["expected_successful_provider_generation_count"] = 14

    path = _write_payload(payload)
    with pytest.raises(ValidationError, match="provider generation count"):
        load_and_validate_pilot(path)


def test_pilot_review_fixture_hash_covers_content() -> None:
    payload = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
    payload["review_fixtures"][0]["question"] = "Changed review question"

    path = _write_payload(payload)
    with pytest.raises(ValidationError, match="fixture SHA256"):
        load_and_validate_pilot(path)


def _write_payload(payload: dict) -> Path:
    path = Path("/tmp/adaptive_policy_v1_pilot_invalid_test.json")
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
