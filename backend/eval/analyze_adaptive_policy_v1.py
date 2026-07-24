from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_ANNOTATION_PATH = (
    EVAL_DIR
    / "annotations"
    / "adaptive_policy_v1_formal_24case_v2_author_reviewed_blind_annotation.csv"
)
DEFAULT_REVEAL_PATH = (
    EVAL_DIR
    / "results"
    / "adaptive_policy"
    / "formal"
    / "adaptive_policy_v1_formal_24case_v2"
    / "reveal_key.json"
)
DEFAULT_RAW_RESULTS_PATH = DEFAULT_REVEAL_PATH.with_name("raw_results.json")
DEFAULT_VALIDITY_AUDIT_PATH = DEFAULT_REVEAL_PATH.with_name(
    "validity_audit.json"
)
DEFAULT_DATASET_PATH = (
    EVAL_DIR / "datasets" / "adaptive_policy_v1_formal_candidate.json"
)
DEFAULT_OUTPUT_DIR = EVAL_DIR / "analysis" / "adaptive_policy_v1_final"

EXPECTED_SHA256 = {
    "annotation": (
        "38bdb085fe05e967c7a3bbe139815ebb2ecf14679f75ce8f841278f088f3e7e1"
    ),
    "reveal": (
        "0fbc184c65d5d24af4eb702daf36972950d1d9851393efbece45c25089b8bf32"
    ),
    "raw_results": (
        "657af308f091ccd08795b6de6a46f3e96f0c9524d2a30548617d19ca191d4ce6"
    ),
    "validity_audit": (
        "1218e379bf0139d8d4601b13c0ea99b1652191b9ea7cbc9fe796f63a9a269437"
    ),
    "dataset": (
        "3221a85d87ebb788a603e93d3e48343edaf02d2c1595a3574558c4be30bf36db"
    ),
}
ANALYSIS_VERSION = "adaptive-policy-v1-b-final-1"
BOOTSTRAP_RESAMPLES = 20_000
BOOTSTRAP_SEED_NAMESPACE = "adaptive-policy-v1-secondary-bootstrap-v1"
SECONDARY_METRICS = (
    "pedagogical_appropriateness",
    "learner_state_tailoring",
    "intent_fidelity",
    "response_relevance",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def validate_hash(path: Path, expected: str, label: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"{label} SHA256 changed: {actual}")


def validate_and_load_inputs(
    *,
    annotation_path: Path,
    reveal_path: Path,
    raw_results_path: Path,
    validity_audit_path: Path,
    dataset_path: Path,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    paths = {
        "annotation": annotation_path,
        "reveal": reveal_path,
        "raw_results": raw_results_path,
        "validity_audit": validity_audit_path,
        "dataset": dataset_path,
    }
    for label, path in paths.items():
        validate_hash(path, EXPECTED_SHA256[label], label)

    annotations = load_csv(annotation_path)
    reveal = load_json(reveal_path)
    raw_results = load_json(raw_results_path)
    validity_audit = load_json(validity_audit_path)
    dataset = load_json(dataset_path)

    if len(annotations) != 24:
        raise ValueError("Expected 24 frozen annotation rows")
    if len(reveal) != 24 or len(raw_results) != 24:
        raise ValueError("Expected 24 reveal and raw-result rows")
    if validity_audit.get("validity_status") != "PASS_AWAITING_SIGNOFF":
        raise ValueError("Formal V2 validity audit is not eligible for analysis")

    case_sets = {
        "annotation": {row["case_id"] for row in annotations},
        "reveal": {row["case_id"] for row in reveal},
        "raw": {row["case_id"] for row in raw_results},
        "dataset": {row["case_id"] for row in dataset["scenarios"]},
    }
    if any(len(case_ids) != 24 for case_ids in case_sets.values()):
        raise ValueError("Every input must contain 24 unique case IDs")
    if len({frozenset(case_ids) for case_ids in case_sets.values()}) != 1:
        raise ValueError("Analysis input case sets differ")

    allowed_preferences = {"A better", "B better", "Tie"}
    if any(
        row["pairwise_preference"] not in allowed_preferences
        for row in annotations
    ):
        raise ValueError("Frozen annotation contains an invalid preference")

    rating_columns = [
        f"response_{side}_{metric}"
        for side in ("A", "B")
        for metric in SECONDARY_METRICS
    ]
    for row in annotations:
        for column in rating_columns:
            if row[column] not in {"0", "1", "2"}:
                raise ValueError(f"Invalid frozen rating in {column}")

    for row in reveal:
        if {row.get("A"), row.get("B")} != {"adaptive", "baseline"}:
            raise ValueError("Reveal row does not map A/B to both conditions")
    if Counter(row["A"] for row in reveal) != Counter(
        {"adaptive": 12, "baseline": 12}
    ):
        raise ValueError("Reveal balance is not 12/12")
    if any(row.get("error") is not None for row in raw_results):
        raise ValueError("Formal V2 contains failed scenarios")

    return annotations, reveal, raw_results, dataset


def reveal_annotations(
    annotations: list[dict[str, str]],
    reveal: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reveal_by_case = {row["case_id"]: row for row in reveal}
    revealed: list[dict[str, Any]] = []
    for row in annotations:
        mapping = reveal_by_case[row["case_id"]]
        blind_preference = row["pairwise_preference"]
        if blind_preference == "Tie":
            revealed_preference = "tie"
        else:
            side = blind_preference[0]
            revealed_preference = f"{mapping[side]}_better"

        output: dict[str, Any] = {
            "case_id": row["case_id"],
            "group_id": row["group_id"],
            "blinded_pairwise_preference": blind_preference,
            "A_condition": mapping["A"],
            "B_condition": mapping["B"],
            "revealed_pairwise_preference": revealed_preference,
            "structural_identical_policy_control": bool(
                mapping["structural_identical_policy_control"]
            ),
        }
        for metric in SECONDARY_METRICS:
            a_score = int(row[f"response_A_{metric}"])
            b_score = int(row[f"response_B_{metric}"])
            output[f"response_A_{metric}"] = a_score
            output[f"response_B_{metric}"] = b_score
            output[f"adaptive_{metric}"] = (
                a_score if mapping["A"] == "adaptive" else b_score
            )
            output[f"baseline_{metric}"] = (
                a_score if mapping["A"] == "baseline" else b_score
            )
        output["annotation_notes"] = row["annotation_notes"]
        revealed.append(output)
    return revealed


def exact_two_sided_sign_test(adaptive: int, baseline: int) -> float:
    non_ties = adaptive + baseline
    if non_ties == 0:
        return 1.0
    tail = min(adaptive, baseline)
    one_sided = sum(
        math.comb(non_ties, value) for value in range(tail + 1)
    ) / (2**non_ties)
    return min(1.0, 2 * one_sided)


def primary_results(revealed: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(row["revealed_pairwise_preference"] for row in revealed)
    adaptive = counts["adaptive_better"]
    baseline = counts["baseline_better"]
    ties = counts["tie"]
    non_ties = adaptive + baseline
    return {
        "unit": "paired_scenario",
        "total_n": len(revealed),
        "adaptive_better_count": adaptive,
        "baseline_better_count": baseline,
        "tie_count": ties,
        "non_tie_n": non_ties,
        "adaptive_better_rate_all": adaptive / len(revealed),
        "baseline_better_rate_all": baseline / len(revealed),
        "tie_rate_all": ties / len(revealed),
        "adaptive_better_rate_non_ties": (
            adaptive / non_ties if non_ties else None
        ),
        "test": "exact_two_sided_sign_test_on_non_ties",
        "null_probability": 0.5,
        "p_value": exact_two_sided_sign_test(adaptive, baseline),
        "effect_direction": (
            "adaptive"
            if adaptive > baseline
            else "baseline"
            if baseline > adaptive
            else "none"
        ),
    }


def clustered_results(revealed: list[dict[str, Any]]) -> dict[str, Any]:
    encoded = {
        "adaptive_better": 1,
        "tie": 0,
        "baseline_better": -1,
    }
    groups: dict[str, list[int]] = defaultdict(list)
    for row in revealed:
        groups[row["group_id"]].append(
            encoded[row["revealed_pairwise_preference"]]
        )
    if len(groups) != 11:
        raise ValueError("Expected 11 counterfactual groups")

    group_rows: list[dict[str, Any]] = []
    directions: Counter[str] = Counter()
    for group_id in sorted(groups):
        scores = groups[group_id]
        mean = sum(scores) / len(scores)
        direction = (
            "adaptive_direction"
            if mean > 0
            else "baseline_direction"
            if mean < 0
            else "tied_group"
        )
        directions[direction] += 1
        group_rows.append(
            {
                "group_id": group_id,
                "scenario_count": len(scores),
                "score_sum": sum(scores),
                "score_mean": mean,
                "direction": direction,
            }
        )

    adaptive = directions["adaptive_direction"]
    baseline = directions["baseline_direction"]
    ties = directions["tied_group"]
    return {
        "unit": "registered_counterfactual_group",
        "total_group_n": 11,
        "adaptive_direction_count": adaptive,
        "baseline_direction_count": baseline,
        "tied_group_count": ties,
        "non_tied_group_n": adaptive + baseline,
        "test": "exact_two_sided_sign_test_on_nonzero_group_directions",
        "null_probability": 0.5,
        "p_value": exact_two_sided_sign_test(adaptive, baseline),
        "groups": group_rows,
    }


def stable_seed(metric: str) -> int:
    material = f"{BOOTSTRAP_SEED_NAMESPACE}:{metric}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("Cannot calculate an empty percentile")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def paired_bootstrap_mean_difference_ci(
    adaptive: Sequence[float],
    baseline: Sequence[float],
    *,
    metric: str,
) -> tuple[float, float]:
    if len(adaptive) != len(baseline) or not adaptive:
        raise ValueError("Paired bootstrap requires equal non-empty samples")
    differences = [
        left - right for left, right in zip(adaptive, baseline, strict=True)
    ]
    rng = random.Random(stable_seed(metric))
    n = len(differences)
    estimates = [
        sum(differences[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(BOOTSTRAP_RESAMPLES)
    ]
    estimates.sort()
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def score_distribution(values: Iterable[float]) -> dict[str, int]:
    counts = Counter(int(value) for value in values)
    return {str(score): counts[score] for score in range(3)}


def secondary_results(revealed: list[dict[str, Any]]) -> dict[str, Any]:
    metrics: list[dict[str, Any]] = []
    for metric in SECONDARY_METRICS:
        adaptive = [float(row[f"adaptive_{metric}"]) for row in revealed]
        baseline = [float(row[f"baseline_{metric}"]) for row in revealed]
        differences = [
            left - right
            for left, right in zip(adaptive, baseline, strict=True)
        ]
        ci_low, ci_high = paired_bootstrap_mean_difference_ci(
            adaptive,
            baseline,
            metric=metric,
        )
        metrics.append(
            {
                "metric": metric,
                "applicable_pair_n": len(differences),
                "adaptive": {
                    "mean": statistics.fmean(adaptive),
                    "median": statistics.median(adaptive),
                    "distribution": score_distribution(adaptive),
                },
                "baseline": {
                    "mean": statistics.fmean(baseline),
                    "median": statistics.median(baseline),
                    "distribution": score_distribution(baseline),
                },
                "paired_difference_adaptive_minus_baseline": {
                    "mean": statistics.fmean(differences),
                    "median": statistics.median(differences),
                    "ci_95_low": ci_low,
                    "ci_95_high": ci_high,
                    "ci_method": "paired_percentile_bootstrap",
                    "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
                    "seed_namespace": BOOTSTRAP_SEED_NAMESPACE,
                },
            }
        )
    return {
        "secondary_p_values_calculated": False,
        "holm_adjustment": "not_applicable",
        "metrics": metrics,
    }


def expected_policy(
    scenario: dict[str, Any],
    condition: str,
) -> tuple[str, str]:
    key = (
        "expected_adaptive_policy"
        if condition == "adaptive"
        else "expected_baseline_policy"
    )
    policy = scenario[key]
    return policy["selected_action"], policy["response_strategy"]


def actual_policy(
    raw: dict[str, Any],
    condition: str,
) -> tuple[str, str]:
    decision = raw["conditions"][condition]["decision"]
    return decision["selected_action"], decision["response_strategy"]


def policy_conformance(
    *,
    dataset_by_case: dict[str, dict[str, Any]],
    raw_by_case: dict[str, dict[str, Any]],
    condition: str,
) -> dict[str, Any]:
    action_correct = 0
    strategy_correct = 0
    exact = 0
    for case_id, scenario in dataset_by_case.items():
        expected = expected_policy(scenario, condition)
        actual = actual_policy(raw_by_case[case_id], condition)
        action_correct += actual[0] == expected[0]
        strategy_correct += actual[1] == expected[1]
        exact += actual == expected
    return {
        "scenario_n": 24,
        "action_accuracy_count": action_correct,
        "action_accuracy_rate": action_correct / 24,
        "strategy_accuracy_count": strategy_correct,
        "strategy_accuracy_rate": strategy_correct / 24,
        "exact_policy_match_count": exact,
        "exact_policy_match_rate": exact / 24,
    }


def ordered_group_scenarios(
    scenarios: list[dict[str, Any]],
    group_id: str,
    positions: Sequence[str],
) -> list[dict[str, Any]]:
    by_position = {
        row["scenario_position"]: row
        for row in scenarios
        if row["group_id"] == group_id
    }
    if set(by_position) != set(positions):
        raise ValueError(f"{group_id} does not match registered positions")
    return [by_position[position] for position in positions]


def policy_sequence(
    *,
    scenarios: list[dict[str, Any]],
    raw_by_case: dict[str, dict[str, Any]],
    condition: str,
) -> list[tuple[str, str]]:
    return [
        actual_policy(raw_by_case[row["case_id"]], condition)
        for row in scenarios
    ]


def manipulation_results(
    *,
    dataset: dict[str, Any],
    raw_results: list[dict[str, Any]],
    revealed: list[dict[str, Any]],
) -> dict[str, Any]:
    scenarios = dataset["scenarios"]
    dataset_by_case = {row["case_id"]: row for row in scenarios}
    raw_by_case = {row["case_id"]: row for row in raw_results}
    revealed_by_case = {row["case_id"]: row for row in revealed}

    directional: dict[str, list[dict[str, Any]]] = {
        "adaptive": [],
        "baseline": [],
    }
    for group_number in range(1, 7):
        group_id = f"AP_G{group_number:02d}"
        group = ordered_group_scenarios(
            scenarios,
            group_id,
            ("low", "high"),
        )
        for condition in ("adaptive", "baseline"):
            registered = [
                expected_policy(row, condition) for row in group
            ]
            actual = policy_sequence(
                scenarios=group,
                raw_by_case=raw_by_case,
                condition=condition,
            )
            expected_to_change = condition == "adaptive"
            directional[condition].append(
                {
                    "group_id": group_id,
                    "expected_behavior": (
                        "registered_adaptation"
                        if expected_to_change
                        else "registered_nonadaptation"
                    ),
                    "success": (
                        actual == registered
                        and (actual[0] != actual[1]) == expected_to_change
                    ),
                    "actual_sequence": [
                        {"action": action, "strategy": strategy}
                        for action, strategy in actual
                    ],
                }
            )

    triplets: dict[str, list[dict[str, Any]]] = {
        "adaptive": [],
        "baseline": [],
    }
    adjacent: dict[str, list[dict[str, Any]]] = {
        "adaptive": [],
        "baseline": [],
    }
    for group_id in ("AP_G07", "AP_G08"):
        group = ordered_group_scenarios(
            scenarios,
            group_id,
            ("low", "medium", "high"),
        )
        for condition in ("adaptive", "baseline"):
            registered = [
                expected_policy(row, condition) for row in group
            ]
            actual = policy_sequence(
                scenarios=group,
                raw_by_case=raw_by_case,
                condition=condition,
            )
            expected_to_change = condition == "adaptive"
            triplets[condition].append(
                {
                    "group_id": group_id,
                    "expected_behavior": (
                        "registered_ordinal_adaptation"
                        if expected_to_change
                        else "registered_nonadaptation"
                    ),
                    "success": (
                        actual == registered
                        and (
                            len(set(actual)) > 1
                        )
                        == expected_to_change
                    ),
                    "actual_sequence": [
                        {"action": action, "strategy": strategy}
                        for action, strategy in actual
                    ],
                }
            )
            for index, label in enumerate(("low_to_medium", "medium_to_high")):
                adjacent[condition].append(
                    {
                        "group_id": group_id,
                        "contrast": label,
                        "expected_behavior": (
                            "registered_adaptation"
                            if expected_to_change
                            else "registered_nonadaptation"
                        ),
                        "success": (
                            actual[index : index + 2]
                            == registered[index : index + 2]
                            and (
                                actual[index] != actual[index + 1]
                            )
                            == expected_to_change
                        ),
                    }
                )

    explicit_actions = {"AP_G10": "hint", "AP_G11": "quiz"}
    fidelity: dict[str, list[dict[str, Any]]] = {
        "adaptive": [],
        "baseline": [],
    }
    over_adaptation: dict[str, int] = {"adaptive": 0, "baseline": 0}
    for group_id, required_action in explicit_actions.items():
        group = ordered_group_scenarios(
            scenarios,
            group_id,
            ("low", "high"),
        )
        for condition in ("adaptive", "baseline"):
            actions = [
                actual_policy(raw_by_case[row["case_id"]], condition)[0]
                for row in group
            ]
            fidelity[condition].append(
                {
                    "group_id": group_id,
                    "required_action": required_action,
                    "success": all(
                        action == required_action for action in actions
                    ),
                    "actual_actions": actions,
                }
            )
            over_adaptation[condition] += sum(
                action != required_action for action in actions
            )

    review_group = ordered_group_scenarios(
        scenarios,
        "AP_G09",
        ("review_false", "review_true"),
    )
    review_behavior: dict[str, dict[str, Any]] = {}
    for condition in ("adaptive", "baseline"):
        registered_review = [
            expected_policy(row, condition) for row in review_group
        ]
        actual_review = policy_sequence(
            scenarios=review_group,
            raw_by_case=raw_by_case,
            condition=condition,
        )
        expected_to_change = condition == "adaptive"
        success = (
            actual_review == registered_review
            and (actual_review[0] != actual_review[1]) == expected_to_change
        )
        review_behavior[condition] = {
            "expected_behavior": (
                "registered_review_due_adaptation"
                if expected_to_change
                else "registered_nonadaptation"
            ),
            "success_count": int(success),
            "denominator": 1,
            "rate": float(success),
            "actual_sequence": [
                {"action": action, "strategy": strategy}
                for action, strategy in actual_review
            ],
        }

    identical_case_ids = dataset["generation_control"][
        "identical_policy_case_ids"
    ]
    identical_controls: list[dict[str, Any]] = []
    for case_id in identical_case_ids:
        raw = raw_by_case[case_id]
        responses_identical = (
            raw["conditions"]["adaptive"]["response"]
            == raw["conditions"]["baseline"]["response"]
        )
        execution_reused = (
            raw["conditions"]["adaptive"]["generation_execution_id"]
            == raw["conditions"]["baseline"]["generation_execution_id"]
            and raw["conditions"]["baseline"]["reused_generation"] is True
        )
        identical_controls.append(
            {
                "case_id": case_id,
                "responses_identical": responses_identical,
                "canonical_execution_reused": execution_reused,
                "revealed_preference": revealed_by_case[case_id][
                    "revealed_pairwise_preference"
                ],
                "structural_tie": (
                    revealed_by_case[case_id][
                        "revealed_pairwise_preference"
                    ]
                    == "tie"
                ),
            }
        )

    def summarize_groups(rows: list[dict[str, Any]]) -> dict[str, Any]:
        successes = sum(bool(row["success"]) for row in rows)
        return {
            "success_count": successes,
            "denominator": len(rows),
            "rate": successes / len(rows),
            "groups": rows,
        }

    return {
        "policy_conformance": {
            condition: policy_conformance(
                dataset_by_case=dataset_by_case,
                raw_by_case=raw_by_case,
                condition=condition,
            )
            for condition in ("adaptive", "baseline")
        },
        "registered_directional_behavior_g01_g06": {
            condition: summarize_groups(rows)
            for condition, rows in directional.items()
        },
        "registered_ordinal_behavior_g07_g08": {
            condition: summarize_groups(rows)
            for condition, rows in triplets.items()
        },
        "supplementary_adjacent_triplet_contrasts": {
            condition: summarize_groups(rows)
            for condition, rows in adjacent.items()
        },
        "review_due_behavior_g09": review_behavior,
        "explicit_intent_action_fidelity_g10_g11": {
            condition: summarize_groups(rows)
            for condition, rows in fidelity.items()
        },
        "over_adaptation_g10_g11": {
            condition: {
                "violation_count": count,
                "scenario_denominator": 4,
                "rate": count / 4,
            }
            for condition, count in over_adaptation.items()
        },
        "identical_policy_controls": {
            "registered_count": len(identical_controls),
            "responses_identical_count": sum(
                row["responses_identical"] for row in identical_controls
            ),
            "canonical_reuse_count": sum(
                row["canonical_execution_reused"]
                for row in identical_controls
            ),
            "structural_tie_count": sum(
                row["structural_tie"] for row in identical_controls
            ),
            "controls": identical_controls,
        },
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("Cannot write an empty CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_integrity_audit(
    *,
    revealed: list[dict[str, Any]],
    raw_results: list[dict[str, Any]],
    dataset: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "PASS",
        "analysis_version": ANALYSIS_VERSION,
        "input_case_count": len(revealed),
        "unique_case_count": len({row["case_id"] for row in revealed}),
        "group_count": len({row["group_id"] for row in revealed}),
        "raw_result_count": len(raw_results),
        "formal_dataset_scenario_count": len(dataset["scenarios"]),
        "invalidated_formal_v1_used": False,
        "frozen_annotation_overwritten": False,
        "revealed_dataset_is_separate": True,
        "original_blinded_labels_preserved": True,
        "secondary_pairing_preserved": True,
        "input_sha256": EXPECTED_SHA256,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen V1-B reveal and statistical analysis."
    )
    parser.add_argument("--annotation", type=Path, default=DEFAULT_ANNOTATION_PATH)
    parser.add_argument("--reveal", type=Path, default=DEFAULT_REVEAL_PATH)
    parser.add_argument("--raw-results", type=Path, default=DEFAULT_RAW_RESULTS_PATH)
    parser.add_argument(
        "--validity-audit",
        type=Path,
        default=DEFAULT_VALIDITY_AUDIT_PATH,
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(
            f"Analysis output directory is not empty: {args.output_dir}"
        )
    annotations, reveal, raw_results, dataset = validate_and_load_inputs(
        annotation_path=args.annotation,
        reveal_path=args.reveal,
        raw_results_path=args.raw_results,
        validity_audit_path=args.validity_audit,
        dataset_path=args.dataset,
    )
    revealed = reveal_annotations(annotations, reveal)
    primary = primary_results(revealed)
    clustered = clustered_results(revealed)
    secondary = secondary_results(revealed)
    manipulation = manipulation_results(
        dataset=dataset,
        raw_results=raw_results,
        revealed=revealed,
    )
    integrity = build_integrity_audit(
        revealed=revealed,
        raw_results=raw_results,
        dataset=dataset,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    revealed_path = args.output_dir / "revealed_annotations.csv"
    primary_path = args.output_dir / "primary_and_clustered_results.json"
    secondary_path = args.output_dir / "secondary_results.json"
    manipulation_path = args.output_dir / "manipulation_results.json"
    integrity_path = args.output_dir / "integrity_audit.json"
    summary_path = args.output_dir / "summary.json"
    manifest_path = args.output_dir / "analysis_manifest.json"

    write_csv(revealed_path, revealed)
    write_json(
        primary_path,
        {"primary": primary, "clustered_sensitivity": clustered},
    )
    write_json(secondary_path, secondary)
    write_json(manipulation_path, manipulation)
    write_json(integrity_path, integrity)
    write_json(
        summary_path,
        {
            "analysis_version": ANALYSIS_VERSION,
            "claim_boundary": (
                "Controlled policy sensitivity and judged pedagogical "
                "appropriateness; no actual learning-gain claim."
            ),
            "rq2a_policy_sensitivity": {
                "manipulation_and_implementation_checks": manipulation,
            },
            "rq2b_judged_pedagogical_appropriateness": {
                "primary": primary,
                "clustered_sensitivity": clustered,
                "secondary": secondary,
            },
        },
    )

    output_paths = [
        revealed_path,
        primary_path,
        secondary_path,
        manipulation_path,
        integrity_path,
        summary_path,
    ]
    manifest = {
        "analysis_version": ANALYSIS_VERSION,
        "script_path": str(Path(__file__).relative_to(EVAL_DIR.parent.parent)),
        "script_sha256": sha256_file(Path(__file__)),
        "bootstrap": {
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed_namespace": BOOTSTRAP_SEED_NAMESPACE,
        },
        "secondary_p_values_calculated": False,
        "holm_adjustment": "not_applicable",
        "input_paths": {
            "annotation": str(args.annotation),
            "reveal": str(args.reveal),
            "raw_results": str(args.raw_results),
            "validity_audit": str(args.validity_audit),
            "dataset": str(args.dataset),
        },
        "input_sha256": EXPECTED_SHA256,
        "output_sha256": {
            path.name: sha256_file(path) for path in output_paths
        },
    }
    write_json(manifest_path, manifest)

    print(f"Wrote V1-B analysis artifacts to {args.output_dir}")


if __name__ == "__main__":
    main()
