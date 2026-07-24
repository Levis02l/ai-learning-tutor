import json
from pathlib import Path

import pytest

from eval.analyze_adaptive_policy_v1 import (
    clustered_results,
    exact_two_sided_sign_test,
    manipulation_results,
    paired_bootstrap_mean_difference_ci,
    reveal_annotations,
)

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"


def test_exact_two_sided_sign_test_handles_ties_outside_denominator() -> None:
    assert exact_two_sided_sign_test(3, 0) == pytest.approx(0.25)
    assert exact_two_sided_sign_test(2, 2) == pytest.approx(1.0)
    assert exact_two_sided_sign_test(0, 0) == pytest.approx(1.0)


def test_reveal_annotations_preserves_blind_labels_and_maps_scores() -> None:
    annotations = [
        {
            "case_id": "case_1",
            "group_id": "AP_G01",
            "pairwise_preference": "A better",
            "response_A_pedagogical_appropriateness": "2",
            "response_B_pedagogical_appropriateness": "1",
            "response_A_learner_state_tailoring": "2",
            "response_B_learner_state_tailoring": "0",
            "response_A_intent_fidelity": "2",
            "response_B_intent_fidelity": "2",
            "response_A_response_relevance": "2",
            "response_B_response_relevance": "1",
            "annotation_notes": "Frozen blind note",
        }
    ]
    reveal = [
        {
            "case_id": "case_1",
            "A": "baseline",
            "B": "adaptive",
            "structural_identical_policy_control": False,
        }
    ]

    row = reveal_annotations(annotations, reveal)[0]

    assert row["blinded_pairwise_preference"] == "A better"
    assert row["revealed_pairwise_preference"] == "baseline_better"
    assert row["adaptive_pedagogical_appropriateness"] == 1
    assert row["baseline_pedagogical_appropriateness"] == 2


def test_clustered_results_uses_one_direction_per_group() -> None:
    revealed = []
    for index in range(1, 12):
        preference = (
            "adaptive_better"
            if index <= 6
            else "baseline_better"
            if index <= 9
            else "tie"
        )
        revealed.append(
            {
                "case_id": f"case_{index}",
                "group_id": f"AP_G{index:02d}",
                "revealed_pairwise_preference": preference,
            }
        )

    result = clustered_results(revealed)

    assert result["total_group_n"] == 11
    assert result["adaptive_direction_count"] == 6
    assert result["baseline_direction_count"] == 3
    assert result["tied_group_count"] == 2
    assert result["non_tied_group_n"] == 9


def test_paired_bootstrap_is_deterministic_and_preserves_pairing() -> None:
    adaptive = [2.0, 2.0, 1.0, 2.0]
    baseline = [1.0, 1.0, 1.0, 0.0]

    first = paired_bootstrap_mean_difference_ci(
        adaptive,
        baseline,
        metric="test_metric",
    )
    second = paired_bootstrap_mean_difference_ci(
        adaptive,
        baseline,
        metric="test_metric",
    )

    assert first == second
    assert first[0] <= 1.0 <= first[1]


def test_registered_policy_outputs_produce_expected_manipulations() -> None:
    dataset = json.loads(
        (EVAL_DIR / "datasets" / "adaptive_policy_v1_formal_candidate.json")
        .read_text(encoding="utf-8")
    )
    identical_ids = set(
        dataset["generation_control"]["identical_policy_case_ids"]
    )
    raw_results = []
    for scenario in dataset["scenarios"]:
        case_id = scenario["case_id"]
        identical = case_id in identical_ids
        shared_response = {"answer": f"Shared response for {case_id}"}
        conditions = {}
        for condition in ("adaptive", "baseline"):
            expected = scenario[
                (
                    "expected_adaptive_policy"
                    if condition == "adaptive"
                    else "expected_baseline_policy"
                )
            ]
            conditions[condition] = {
                "decision": {
                    "selected_action": expected["selected_action"],
                    "response_strategy": expected["response_strategy"],
                },
                "response": (
                    shared_response
                    if identical
                    else {"answer": f"{condition} response for {case_id}"}
                ),
                "generation_execution_id": (
                    f"{case_id}_shared"
                    if identical
                    else f"{case_id}_{condition}"
                ),
                "reused_generation": identical and condition == "baseline",
            }
        raw_results.append(
            {
                "case_id": case_id,
                "conditions": conditions,
            }
        )

    revealed = [
        {
            "case_id": row["case_id"],
            "revealed_pairwise_preference": (
                "tie" if row["case_id"] in identical_ids else "adaptive_better"
            ),
        }
        for row in dataset["scenarios"]
    ]

    result = manipulation_results(
        dataset=dataset,
        raw_results=raw_results,
        revealed=revealed,
    )

    for condition in ("adaptive", "baseline"):
        assert (
            result["policy_conformance"][condition][
                "exact_policy_match_count"
            ]
            == 24
        )
        assert (
            result["registered_directional_behavior_g01_g06"][condition][
                "success_count"
            ]
            == 6
        )
        assert (
            result["registered_ordinal_behavior_g07_g08"][condition][
                "success_count"
            ]
            == 2
        )
        assert (
            result["supplementary_adjacent_triplet_contrasts"][condition][
                "success_count"
            ]
            == 4
        )
        assert (
            result["review_due_behavior_g09"][condition]["success_count"] == 1
        )
        assert (
            result["explicit_intent_action_fidelity_g10_g11"][condition][
                "success_count"
            ]
            == 2
        )
        assert (
            result["over_adaptation_g10_g11"][condition]["violation_count"]
            == 0
        )

    controls = result["identical_policy_controls"]
    assert controls["registered_count"] == 4
    assert controls["responses_identical_count"] == 4
    assert controls["canonical_reuse_count"] == 4
    assert controls["structural_tie_count"] == 4
