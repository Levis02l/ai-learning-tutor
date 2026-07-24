import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import eval.validate_adaptive_policy_dataset as validator
from eval.validate_adaptive_policy_dataset import (
    DEFAULT_DATASET_PATH,
    load_and_validate_dataset,
    verify_production_concept_resolution,
)


def test_candidate_dataset_validates() -> None:
    dataset = load_and_validate_dataset()

    assert dataset.topology.group_count == 11
    assert len(dataset.scenarios) == 24
    assert dataset.generation_control.planned_model_generation_call_count == 44
    assert dataset.generation_control.identical_policy_case_ids == [
        "adaptive_formal_g03_low",
        "adaptive_formal_g04_low",
        "adaptive_formal_g07_medium",
        "adaptive_formal_g11_low",
    ]


def test_human_audited_evidence_requires_null_similarity() -> None:
    payload = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
    payload["evidence_fixtures"][0]["evidence_state"]["top_similarity"] = 0.91

    path = _write_payload(payload)
    with pytest.raises(ValidationError):
        load_and_validate_dataset(path)


def test_identical_policy_control_list_is_recomputed() -> None:
    payload = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
    payload["generation_control"]["identical_policy_case_ids"] = []

    path = _write_payload(payload)
    with pytest.raises(ValidationError, match="identical_policy_case_ids"):
        load_and_validate_dataset(path)


def test_counterfactual_group_question_must_remain_invariant() -> None:
    payload = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
    payload["scenarios"][1]["question"] = "A different question."

    path = _write_payload(payload)
    with pytest.raises(ValidationError, match="question invariant"):
        load_and_validate_dataset(path)


def test_production_state_status_must_match_attempt_count() -> None:
    payload = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
    payload["concept_registry"][0]["production_state_status"] = "unobserved"

    path = _write_payload(payload)
    with pytest.raises(ValidationError, match="production status/count mismatch"):
        load_and_validate_dataset(path)


def test_review_fixture_must_use_frozen_evidence_chunks() -> None:
    payload = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
    payload["review_fixtures"][0]["source_chunk_ids"] = [999]

    path = _write_payload(payload)
    with pytest.raises(ValidationError, match="review/evidence chunks mismatch"):
        load_and_validate_dataset(path)


def test_fixture_hash_covers_page_and_evidence_metadata() -> None:
    payload = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
    payload["evidence_fixtures"][0]["page_targets"] = [999]

    path = _write_payload(payload)
    with pytest.raises(ValidationError, match="fixture SHA256"):
        load_and_validate_dataset(path)


def test_freeze_check_rejects_changed_production_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = load_and_validate_dataset()
    wrong_resolution = SimpleNamespace(
        concept=SimpleNamespace(id=999, name="Wrong Concept"),
        confidence=0.9,
        reason="compact_name_match",
    )
    monkeypatch.setattr(
        validator,
        "resolve_concept_for_focus",
        lambda *args, **kwargs: wrong_resolution,
    )

    with pytest.raises(ValueError, match="resolved to concept"):
        verify_production_concept_resolution(dataset, SimpleNamespace())


def _write_payload(payload: dict) -> Path:
    path = Path("/tmp/adaptive_policy_v1_invalid_test.json")
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
