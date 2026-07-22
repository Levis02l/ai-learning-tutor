from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_RESPONSE_PATH = (
    EVAL_DIR / "annotations" / "grounding_v1_formal_human_annotations.csv"
)
DEFAULT_CLAIM_PATH = (
    EVAL_DIR / "annotations" / "grounding_v1_formal_claim_annotations.csv"
)
DEFAULT_OUTPUT_DIR = EVAL_DIR / "analysis" / "grounding_v1_final"

EXPECTED_RESPONSE_SHA256 = (
    "ccf559b474427b0fbbb11aabdbdeb5c117cb0fdcf3d2bd4100b401522ee06974"
)
EXPECTED_CLAIM_SHA256 = (
    "6b3993ffb76a297280bec94af9dd11dfe0b06c6b534270d41bfe991addea3729"
)
ANALYSIS_VERSION = "grounding-v1-a-final-1"
BOOTSTRAP_RESAMPLES = 20_000
PERMUTATION_RESAMPLES = 50_000

ModeRows = dict[str, dict[str, str]]


@dataclass(frozen=True)
class Estimate:
    n: int
    value: float
    ci_low: float
    ci_high: float


@dataclass(frozen=True)
class Comparison:
    n_pairs: int
    grounded: float
    ungrounded: float
    difference: float
    ci_low: float
    ci_high: float
    test: str
    p_value: float


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def validate_frozen_inputs(
    response_path: Path,
    claim_path: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    response_hash = sha256_file(response_path)
    claim_hash = sha256_file(claim_path)
    if response_hash != EXPECTED_RESPONSE_SHA256:
        raise ValueError(
            "Response annotations do not match the author-signed frozen SHA256"
        )
    if claim_hash != EXPECTED_CLAIM_SHA256:
        raise ValueError(
            "Claim annotations do not match the author-signed frozen SHA256"
        )

    responses = read_csv(response_path)
    claims = read_csv(claim_path)

    if len(responses) != 100:
        raise ValueError(f"Expected 100 response annotations, found {len(responses)}")
    if len(claims) != 300:
        raise ValueError(f"Expected 300 claim annotations, found {len(claims)}")
    if Counter(row["mode"] for row in responses) != Counter(
        {"grounded": 50, "ungrounded": 50}
    ):
        raise ValueError("Expected 50 grounded and 50 ungrounded responses")

    pairs = {(row["case_id"], row["mode"]) for row in responses}
    if len(pairs) != 100:
        raise ValueError("Response case/mode pairs are not unique")
    if any(row["annotation_status"] != "reviewed" for row in responses):
        raise ValueError("Every response annotation must be reviewed")
    if any(row["annotation_status"] != "reviewed" for row in claims):
        raise ValueError("Every claim annotation must be reviewed")

    recovery = [
        row for row in responses if row["case_id"] == "grounding_formal_048"
    ]
    if len(recovery) != 2 or any(
        row["result_source"] != "recovery" for row in recovery
    ):
        raise ValueError("grounding_formal_048 must contain two recovery responses")
    primary = [
        row for row in responses if row["case_id"] != "grounding_formal_048"
    ]
    if len({row["case_id"] for row in primary}) != 49 or any(
        row["result_source"] != "primary" for row in primary
    ):
        raise ValueError("The other 49 cases must come from the primary run")

    return responses, claims


def optional_float(value: str) -> float | None:
    if value in {"", "N/A"}:
        return None
    return float(value)


def yes_no(value: str) -> float | None:
    if value == "yes":
        return 1.0
    if value == "no":
        return 0.0
    if value in {"", "N/A"}:
        return None
    raise ValueError(f"Expected yes/no/N/A, found {value!r}")


def partial_score(value: str) -> float | None:
    if value == "yes":
        return 1.0
    if value == "partial":
        return 0.5
    if value == "no":
        return 0.0
    if value in {"", "N/A"}:
        return None
    raise ValueError(f"Expected yes/partial/no/N/A, found {value!r}")


def full_success(value: str) -> float | None:
    if value == "yes":
        return 1.0
    if value in {"partial", "no"}:
        return 0.0
    if value in {"", "N/A"}:
        return None
    raise ValueError(f"Expected yes/partial/no/N/A, found {value!r}")


def stable_seed(key: str) -> int:
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big")


def percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("Cannot compute a percentile from an empty sequence")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def bootstrap_mean_ci(
    values: Sequence[float],
    *,
    seed_key: str,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> tuple[float, float]:
    if not values:
        raise ValueError("Cannot bootstrap an empty sequence")
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(stable_seed(seed_key))
    n = len(values)
    estimates = [
        sum(values[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(resamples)
    ]
    estimates.sort()
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def bootstrap_paired_difference_ci(
    grounded: Sequence[float],
    ungrounded: Sequence[float],
    *,
    seed_key: str,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> tuple[float, float]:
    if len(grounded) != len(ungrounded) or not grounded:
        raise ValueError("Paired bootstrap requires equal non-empty sequences")
    differences = [left - right for left, right in zip(grounded, ungrounded)]
    return bootstrap_mean_ci(
        differences,
        seed_key=f"paired:{seed_key}",
        resamples=resamples,
    )


def paired_permutation_p_value(
    grounded: Sequence[float],
    ungrounded: Sequence[float],
    *,
    seed_key: str,
    resamples: int = PERMUTATION_RESAMPLES,
) -> tuple[float, str]:
    if len(grounded) != len(ungrounded) or not grounded:
        raise ValueError("Paired permutation requires equal non-empty sequences")
    differences = [
        left - right
        for left, right in zip(grounded, ungrounded)
        if not math.isclose(left, right, abs_tol=1e-12)
    ]
    if not differences:
        return 1.0, "paired sign-flip exact"

    observed = abs(sum(differences) / len(differences))
    count = len(differences)
    tolerance = 1e-12

    if count <= 18:
        total = 1 << count
        extreme = 0
        for mask in range(total):
            signed_sum = sum(
                value if mask & (1 << index) else -value
                for index, value in enumerate(differences)
            )
            if abs(signed_sum / count) >= observed - tolerance:
                extreme += 1
        return extreme / total, "paired sign-flip exact"

    rng = random.Random(stable_seed(f"permutation:{seed_key}"))
    extreme = 0
    for _ in range(resamples):
        signed_mean = sum(
            value if rng.random() < 0.5 else -value for value in differences
        ) / count
        if abs(signed_mean) >= observed - tolerance:
            extreme += 1
    return (extreme + 1) / (resamples + 1), "paired sign-flip Monte Carlo"


def wilson_ci(
    successes: int,
    total: int,
    z: float = 1.959963984540054,
) -> tuple[float, float]:
    if total <= 0:
        raise ValueError("Wilson interval requires a positive denominator")
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return max(0.0, centre - margin), min(1.0, centre + margin)


def mcnemar_exact(
    grounded: Sequence[float],
    ungrounded: Sequence[float],
) -> tuple[float, int, int]:
    if len(grounded) != len(ungrounded) or not grounded:
        raise ValueError("McNemar test requires equal non-empty sequences")
    pairs = list(zip(grounded, ungrounded))
    grounded_only = sum(left == 1.0 and right == 0.0 for left, right in pairs)
    ungrounded_only = sum(left == 0.0 and right == 1.0 for left, right in pairs)
    discordant = grounded_only + ungrounded_only
    if discordant == 0:
        return 1.0, grounded_only, ungrounded_only
    tail = sum(
        math.comb(discordant, index)
        for index in range(min(grounded_only, ungrounded_only) + 1)
    ) / (2**discordant)
    return min(1.0, 2 * tail), grounded_only, ungrounded_only


def group_matches(row: dict[str, str], group: str) -> bool:
    if group == "factual_combined":
        return row["answerability"] in {
            "answerable",
            "partially_answerable",
        }
    return row["answerability"] == group


def pair_rows(
    rows: Iterable[dict[str, str]],
    group: str,
) -> list[tuple[dict[str, str], dict[str, str]]]:
    cases: dict[str, ModeRows] = {}
    for row in rows:
        if group_matches(row, group):
            cases.setdefault(row["case_id"], {})[row["mode"]] = row
    pairs = []
    for case_id in sorted(cases):
        modes = cases[case_id]
        if set(modes) != {"grounded", "ungrounded"}:
            raise ValueError(f"Case {case_id} does not contain both conditions")
        pairs.append((modes["grounded"], modes["ungrounded"]))
    return pairs


def values_for_mode(
    rows: Iterable[dict[str, str]],
    group: str,
    mode: str,
    extractor: Callable[[dict[str, str]], float | None],
) -> list[float]:
    values = []
    for row in rows:
        if group_matches(row, group) and row["mode"] == mode:
            value = extractor(row)
            if value is not None:
                values.append(value)
    return values


def paired_values(
    rows: Iterable[dict[str, str]],
    group: str,
    extractor: Callable[[dict[str, str]], float | None],
) -> tuple[list[float], list[float]]:
    grounded_values = []
    ungrounded_values = []
    for grounded, ungrounded in pair_rows(rows, group):
        left = extractor(grounded)
        right = extractor(ungrounded)
        if left is None or right is None:
            continue
        grounded_values.append(left)
        ungrounded_values.append(right)
    return grounded_values, ungrounded_values


def mean_estimate(values: Sequence[float], key: str) -> Estimate:
    value = sum(values) / len(values)
    ci_low, ci_high = bootstrap_mean_ci(values, seed_key=key)
    return Estimate(len(values), value, ci_low, ci_high)


def binary_estimate(values: Sequence[float]) -> Estimate:
    successes = sum(value == 1.0 for value in values)
    ci_low, ci_high = wilson_ci(successes, len(values))
    return Estimate(len(values), successes / len(values), ci_low, ci_high)


def compare_continuous(
    rows: Sequence[dict[str, str]],
    group: str,
    metric: str,
    extractor: Callable[[dict[str, str]], float | None],
) -> Comparison:
    grounded, ungrounded = paired_values(rows, group, extractor)
    ci_low, ci_high = bootstrap_paired_difference_ci(
        grounded,
        ungrounded,
        seed_key=f"{group}:{metric}",
    )
    p_value, test = paired_permutation_p_value(
        grounded,
        ungrounded,
        seed_key=f"{group}:{metric}",
    )
    grounded_mean = sum(grounded) / len(grounded)
    ungrounded_mean = sum(ungrounded) / len(ungrounded)
    return Comparison(
        n_pairs=len(grounded),
        grounded=grounded_mean,
        ungrounded=ungrounded_mean,
        difference=grounded_mean - ungrounded_mean,
        ci_low=ci_low,
        ci_high=ci_high,
        test=test,
        p_value=p_value,
    )


def compare_binary(
    rows: Sequence[dict[str, str]],
    group: str,
    extractor: Callable[[dict[str, str]], float | None],
) -> tuple[Comparison, int, int]:
    grounded, ungrounded = paired_values(rows, group, extractor)
    ci_low, ci_high = bootstrap_paired_difference_ci(
        grounded,
        ungrounded,
        seed_key=f"binary:{group}",
    )
    p_value, grounded_only, ungrounded_only = mcnemar_exact(
        grounded,
        ungrounded,
    )
    grounded_mean = sum(grounded) / len(grounded)
    ungrounded_mean = sum(ungrounded) / len(ungrounded)
    return (
        Comparison(
            n_pairs=len(grounded),
            grounded=grounded_mean,
            ungrounded=ungrounded_mean,
            difference=grounded_mean - ungrounded_mean,
            ci_low=ci_low,
            ci_high=ci_high,
            test="McNemar exact",
            p_value=p_value,
        ),
        grounded_only,
        ungrounded_only,
    )


def response_metric_definitions() -> list[
    tuple[str, str, Callable[[dict[str, str]], float | None], str]
]:
    return [
        (
            "mean_answer_correctness",
            "score_0_to_2",
            lambda row: optional_float(row["answer_correctness"]),
            "continuous",
        ),
        (
            "fully_correct_rate",
            "proportion",
            lambda row: (
                None
                if optional_float(row["answer_correctness"]) is None
                else float(optional_float(row["answer_correctness"]) == 2.0)
            ),
            "binary",
        ),
        (
            "course_supported_claim_rate",
            "proportion",
            lambda row: optional_float(row["course_supported_claim_rate"]),
            "continuous",
        ),
        (
            "unsupported_by_course_claim_rate",
            "proportion",
            lambda row: optional_float(row["unsupported_by_course_claim_rate"]),
            "continuous",
        ),
    ]


def parse_metric_column(
    row: dict[str, str],
    *,
    parser: Callable[[str], float | None],
    column: str,
) -> float | None:
    return parser(row[column])


def build_response_metrics(
    responses: Sequence[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    estimates: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    groups = ["answerable", "partially_answerable", "factual_combined"]

    for group in groups:
        for metric, unit, extractor, metric_type in response_metric_definitions():
            for mode in ("grounded", "ungrounded"):
                values = values_for_mode(responses, group, mode, extractor)
                estimate = (
                    binary_estimate(values)
                    if metric_type == "binary"
                    else mean_estimate(values, f"{group}:{metric}:{mode}")
                )
                estimates.append(
                    {
                        "group": group,
                        "metric": metric,
                        "mode": mode,
                        "n": estimate.n,
                        "estimate": estimate.value,
                        "ci_95_low": estimate.ci_low,
                        "ci_95_high": estimate.ci_high,
                        "unit": unit,
                    }
                )

            if metric_type == "binary":
                comparison, grounded_only, ungrounded_only = compare_binary(
                    responses,
                    group,
                    extractor,
                )
            else:
                comparison = compare_continuous(
                    responses,
                    group,
                    metric,
                    extractor,
                )
                grounded_only = None
                ungrounded_only = None
            comparisons.append(
                comparison_row(
                    group,
                    metric,
                    comparison,
                    grounded_only,
                    ungrounded_only,
                )
            )

    extra_metrics = [
        (
            "partially_answerable",
            "supported_part_score",
            partial_score,
            "supported_part_answered",
            "continuous",
        ),
        (
            "partially_answerable",
            "supported_part_fully_answered_rate",
            full_success,
            "supported_part_answered",
            "binary",
        ),
        (
            "partially_answerable",
            "unsupported_part_limitation_score",
            partial_score,
            "unsupported_part_limited",
            "continuous",
        ),
        (
            "partially_answerable",
            "unsupported_part_fully_limited_rate",
            full_success,
            "unsupported_part_limited",
            "binary",
        ),
        (
            "unanswerable",
            "correct_refusal_rate",
            yes_no,
            "refusal_correctness",
            "binary",
        ),
        (
            "unanswerable",
            "false_answer_rate",
            yes_no,
            "false_answer",
            "binary",
        ),
        (
            "unanswerable",
            "semantic_refusal_rate",
            yes_no,
            "human_semantic_refusal",
            "binary",
        ),
        (
            "answerable",
            "false_refusal_rate",
            yes_no,
            "false_refusal",
            "binary",
        ),
    ]
    for group, metric, parser, column, metric_type in extra_metrics:
        extractor = partial(parse_metric_column, parser=parser, column=column)
        for mode in ("grounded", "ungrounded"):
            values = values_for_mode(responses, group, mode, extractor)
            estimate = (
                binary_estimate(values)
                if metric_type == "binary"
                else mean_estimate(values, f"{group}:{metric}:{mode}")
            )
            estimates.append(
                {
                    "group": group,
                    "metric": metric,
                    "mode": mode,
                    "n": estimate.n,
                    "estimate": estimate.value,
                    "ci_95_low": estimate.ci_low,
                    "ci_95_high": estimate.ci_high,
                    "unit": "proportion",
                }
            )

        if metric_type == "binary":
            comparison, grounded_only, ungrounded_only = compare_binary(
                responses,
                group,
                extractor,
            )
        else:
            comparison = compare_continuous(
                responses,
                group,
                metric,
                extractor,
            )
            grounded_only = None
            ungrounded_only = None
        comparisons.append(
            comparison_row(
                group,
                metric,
                comparison,
                grounded_only,
                ungrounded_only,
            )
        )

    for group in groups:
        for metric, column in (
            ("citation_precision", "citation_precision"),
            ("citation_coverage", "citation_coverage"),
        ):
            values = values_for_mode(
                responses,
                group,
                "grounded",
                partial(
                    parse_metric_column,
                    parser=optional_float,
                    column=column,
                ),
            )
            estimate = mean_estimate(values, f"citation:{group}:{metric}")
            estimates.append(
                {
                    "group": group,
                    "metric": metric,
                    "mode": "grounded",
                    "n": estimate.n,
                    "estimate": estimate.value,
                    "ci_95_low": estimate.ci_low,
                    "ci_95_high": estimate.ci_high,
                    "unit": "proportion",
                }
            )

    return estimates, comparisons


def comparison_row(
    group: str,
    metric: str,
    comparison: Comparison,
    grounded_only: int | None,
    ungrounded_only: int | None,
) -> dict[str, Any]:
    return {
        "group": group,
        "metric": metric,
        "n_pairs": comparison.n_pairs,
        "grounded_estimate": comparison.grounded,
        "ungrounded_estimate": comparison.ungrounded,
        "difference_grounded_minus_ungrounded": comparison.difference,
        "difference_ci_95_low": comparison.ci_low,
        "difference_ci_95_high": comparison.ci_high,
        "paired_test": comparison.test,
        "p_value_two_sided": comparison.p_value,
        "discordant_grounded_only": grounded_only,
        "discordant_ungrounded_only": ungrounded_only,
    }


def build_claim_metrics(
    claims: Sequence[dict[str, str]],
) -> list[dict[str, Any]]:
    rows = []
    groups = ["answerable", "partially_answerable", "factual_combined"]
    for group in groups:
        for mode in ("grounded", "ungrounded"):
            selected = [
                row
                for row in claims
                if group_matches(row, group)
                and row["mode"] == mode
                and row["claim_in_final_answer"] == "yes"
                and row["claim_support_label"]
            ]
            counts = Counter(row["claim_support_label"] for row in selected)
            total = len(selected)
            rows.append(
                {
                    "group": group,
                    "mode": mode,
                    "substantive_claims": total,
                    "fully_supported": counts["fully_supported"],
                    "partially_supported": counts["partially_supported"],
                    "unsupported": counts["unsupported"],
                    "contradicted": counts["contradicted"],
                    "fully_supported_rate": counts["fully_supported"] / total,
                    "any_supported_rate": (
                        counts["fully_supported"]
                        + counts["partially_supported"]
                    )
                    / total,
                    "unsupported_or_contradicted_rate": (
                        counts["unsupported"] + counts["contradicted"]
                    )
                    / total,
                }
            )
    return rows


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write an empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def rounded(value: object, digits: int = 6) -> object:
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {key: rounded(item, digits) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded(item, digits) for item in value]
    return value


def metric_lookup(
    estimates: Sequence[dict[str, Any]],
    group: str,
    metric: str,
    mode: str,
) -> dict[str, Any]:
    return next(
        row
        for row in estimates
        if row["group"] == group
        and row["metric"] == metric
        and row["mode"] == mode
    )


def comparison_lookup(
    comparisons: Sequence[dict[str, Any]],
    group: str,
    metric: str,
) -> dict[str, Any]:
    return next(
        row
        for row in comparisons
        if row["group"] == group and row["metric"] == metric
    )


def format_estimate(row: dict[str, Any], *, percent: bool = False) -> str:
    value = float(row["estimate"])
    low = float(row["ci_95_low"])
    high = float(row["ci_95_high"])
    if percent:
        return f"{value * 100:.1f}% [{low * 100:.1f}, {high * 100:.1f}]"
    return f"{value:.3f} [{low:.3f}, {high:.3f}]"


def format_p_value(value: float) -> str:
    if value < 0.001:
        return "<0.001"
    return f"{value:.3f}"


def format_difference(
    comparison: dict[str, Any],
    *,
    percent: bool,
) -> str:
    value = float(comparison["difference_grounded_minus_ungrounded"])
    low = float(comparison["difference_ci_95_low"])
    high = float(comparison["difference_ci_95_high"])
    if percent:
        return f"{value * 100:.1f} pp [{low * 100:.1f}, {high * 100:.1f}]"
    return f"{value:.3f} [{low:.3f}, {high:.3f}]"


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def write_grouped_bar_svg(
    path: Path,
    *,
    title: str,
    categories: Sequence[str],
    grounded: Sequence[float],
    ungrounded: Sequence[float],
    y_max: float,
    y_label: str,
    value_format: str,
) -> None:
    width = 960
    height = 560
    left = 100
    right = 40
    top = 90
    bottom = 110
    plot_width = width - left - right
    plot_height = height - top - bottom
    group_width = plot_width / len(categories)
    bar_width = min(72, group_width * 0.28)
    grounded_color = "#0F766E"
    ungrounded_color = "#C2410C"
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">'
        ),
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        (
            f'<text x="{width / 2}" y="38" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="22" font-weight="700" '
            f'fill="#17212B">{escape_xml(title)}</text>'
        ),
    ]
    for tick in range(6):
        value = y_max * tick / 5
        y = top + plot_height - plot_height * tick / 5
        parts.extend(
            [
                (
                    f'<line x1="{left}" y1="{y:.2f}" '
                    f'x2="{width - right}" y2="{y:.2f}" '
                    'stroke="#DCE3E8" stroke-width="1"/>'
                ),
                (
                    f'<text x="{left - 14}" y="{y + 5:.2f}" '
                    'text-anchor="end" font-family="Arial, sans-serif" '
                    'font-size="13" fill="#53616D">'
                    f'{format_axis(value, value_format)}</text>'
                ),
            ]
        )

    for index, category in enumerate(categories):
        centre = left + group_width * (index + 0.5)
        for offset, value, color in (
            (-bar_width * 0.58, grounded[index], grounded_color),
            (bar_width * 0.58, ungrounded[index], ungrounded_color),
        ):
            bar_height = plot_height * value / y_max
            x = centre + offset - bar_width / 2
            y = top + plot_height - bar_height
            parts.extend(
                [
                    (
                        f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" '
                        f'height="{bar_height:.2f}" fill="{color}" rx="2"/>'
                    ),
                    (
                        f'<text x="{x + bar_width / 2:.2f}" y="{y - 9:.2f}" '
                        'text-anchor="middle" font-family="Arial, sans-serif" '
                        f'font-size="13" font-weight="700" fill="#17212B">'
                        f'{format_axis(value, value_format)}</text>'
                    ),
                ]
            )
        parts.append(
            f'<text x="{centre:.2f}" y="{height - 66}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="14" fill="#17212B">'
            f'{escape_xml(category)}</text>'
        )

    parts.extend(
        [
            (
                f'<text x="24" y="{top + plot_height / 2}" '
                f'transform="rotate(-90 24 {top + plot_height / 2})" '
                'text-anchor="middle" font-family="Arial, sans-serif" '
                f'font-size="14" fill="#53616D">{escape_xml(y_label)}</text>'
            ),
            (
                f'<rect x="{width / 2 - 128}" y="{height - 30}" '
                f'width="14" height="14" fill="{grounded_color}"/>'
            ),
            (
                f'<text x="{width / 2 - 106}" y="{height - 18}" '
                'font-family="Arial, sans-serif" font-size="14" '
                'fill="#17212B">Grounded</text>'
            ),
            (
                f'<rect x="{width / 2 + 22}" y="{height - 30}" '
                f'width="14" height="14" fill="{ungrounded_color}"/>'
            ),
            (
                f'<text x="{width / 2 + 44}" y="{height - 18}" '
                'font-family="Arial, sans-serif" font-size="14" '
                'fill="#17212B">Ungrounded</text>'
            ),
            "</svg>",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def format_axis(value: float, value_format: str) -> str:
    if value_format == "percent":
        return f"{value * 100:.0f}%"
    return f"{value:.2f}"


def write_figures(
    output_dir: Path,
    estimates: Sequence[dict[str, Any]],
) -> None:
    figures = output_dir / "figures"
    groups = [
        ("answerable", "Answerable"),
        ("partially_answerable", "Partial"),
        ("factual_combined", "Combined"),
    ]
    write_grouped_bar_svg(
        figures / "figure_1_answer_correctness.svg",
        title="Answer correctness by answerability",
        categories=[label for _, label in groups],
        grounded=[
            float(
                metric_lookup(
                    estimates,
                    group,
                    "mean_answer_correctness",
                    "grounded",
                )["estimate"]
            )
            for group, _ in groups
        ],
        ungrounded=[
            float(
                metric_lookup(
                    estimates,
                    group,
                    "mean_answer_correctness",
                    "ungrounded",
                )["estimate"]
            )
            for group, _ in groups
        ],
        y_max=2.0,
        y_label="Mean correctness score (0-2)",
        value_format="score",
    )
    write_grouped_bar_svg(
        figures / "figure_2_claim_support.svg",
        title="Course support of factual answer claims",
        categories=["Course-supported", "Unsupported"],
        grounded=[
            float(
                metric_lookup(
                    estimates,
                    "factual_combined",
                    "course_supported_claim_rate",
                    "grounded",
                )["estimate"]
            ),
            float(
                metric_lookup(
                    estimates,
                    "factual_combined",
                    "unsupported_by_course_claim_rate",
                    "grounded",
                )["estimate"]
            ),
        ],
        ungrounded=[
            float(
                metric_lookup(
                    estimates,
                    "factual_combined",
                    "course_supported_claim_rate",
                    "ungrounded",
                )["estimate"]
            ),
            float(
                metric_lookup(
                    estimates,
                    "factual_combined",
                    "unsupported_by_course_claim_rate",
                    "ungrounded",
                )["estimate"]
            ),
        ],
        y_max=1.0,
        y_label="Macro-averaged response rate",
        value_format="percent",
    )
    write_grouped_bar_svg(
        figures / "figure_3_refusal_behavior.svg",
        title="Behaviour on unanswerable questions",
        categories=["Correct refusal", "False answer", "Semantic refusal"],
        grounded=[
            float(
                metric_lookup(
                    estimates,
                    "unanswerable",
                    metric,
                    "grounded",
                )["estimate"]
            )
            for metric in (
                "correct_refusal_rate",
                "false_answer_rate",
                "semantic_refusal_rate",
            )
        ],
        ungrounded=[
            float(
                metric_lookup(
                    estimates,
                    "unanswerable",
                    metric,
                    "ungrounded",
                )["estimate"]
            )
            for metric in (
                "correct_refusal_rate",
                "false_answer_rate",
                "semantic_refusal_rate",
            )
        ],
        y_max=1.0,
        y_label="Proportion of cases",
        value_format="percent",
    )


def write_failure_cases(
    output_dir: Path,
    responses: Sequence[dict[str, str]],
) -> list[dict[str, Any]]:
    selected_ids = {
        "grounding_formal_020",
        "grounding_formal_022",
        "grounding_formal_032",
        "grounding_formal_034",
        "grounding_formal_040",
        "grounding_formal_048",
    }
    rows = [
        {
            "case_id": row["case_id"],
            "mode": row["mode"],
            "answerability": row["answerability"],
            "answer_correctness": row["answer_correctness"],
            "course_supported_claim_rate": row["course_supported_claim_rate"],
            "unsupported_by_course_claim_rate": row[
                "unsupported_by_course_claim_rate"
            ],
            "citation_precision": row["citation_precision"],
            "citation_coverage": row["citation_coverage"],
            "human_semantic_refusal": row["human_semantic_refusal"],
            "refusal_correctness": row["refusal_correctness"],
            "human_notes": row["human_notes"],
        }
        for row in responses
        if row["case_id"] in selected_ids
    ]
    write_csv(output_dir / "qualitative_failure_cases.csv", rows)
    return rows


def build_results_markdown(
    estimates: Sequence[dict[str, Any]],
    comparisons: Sequence[dict[str, Any]],
    claim_metrics: Sequence[dict[str, Any]],
) -> str:
    factual_metrics = [
        ("Mean answer correctness (0-2)", "mean_answer_correctness", False),
        ("Fully correct rate", "fully_correct_rate", True),
        ("Course-supported claim rate", "course_supported_claim_rate", True),
        (
            "Unsupported-by-course claim rate",
            "unsupported_by_course_claim_rate",
            True,
        ),
    ]
    table_one = []
    for label, metric, percent in factual_metrics:
        grounded = metric_lookup(
            estimates,
            "factual_combined",
            metric,
            "grounded",
        )
        ungrounded = metric_lookup(
            estimates,
            "factual_combined",
            metric,
            "ungrounded",
        )
        comparison = comparison_lookup(
            comparisons,
            "factual_combined",
            metric,
        )
        table_one.append(
            [
                label,
                format_estimate(grounded, percent=percent),
                format_estimate(ungrounded, percent=percent),
                format_difference(comparison, percent=percent),
                format_p_value(float(comparison["p_value_two_sided"])),
            ]
        )

    table_two = []
    for group, group_label in (
        ("answerable", "Answerable (n=30)"),
        ("partially_answerable", "Partially answerable (n=10)"),
    ):
        for metric, metric_label, percent in (
            (
                "mean_answer_correctness",
                "Mean answer correctness (0-2)",
                False,
            ),
            ("fully_correct_rate", "Fully correct rate", True),
            (
                "course_supported_claim_rate",
                "Course-supported claim rate",
                True,
            ),
            (
                "unsupported_by_course_claim_rate",
                "Unsupported claim rate",
                True,
            ),
        ):
            grounded = metric_lookup(estimates, group, metric, "grounded")
            ungrounded = metric_lookup(estimates, group, metric, "ungrounded")
            comparison = comparison_lookup(comparisons, group, metric)
            table_two.append(
                [
                    group_label,
                    metric_label,
                    format_estimate(grounded, percent=percent),
                    format_estimate(ungrounded, percent=percent),
                    format_p_value(float(comparison["p_value_two_sided"])),
                ]
            )
        if group == "answerable":
            grounded = metric_lookup(
                estimates,
                group,
                "false_refusal_rate",
                "grounded",
            )
            ungrounded = metric_lookup(
                estimates,
                group,
                "false_refusal_rate",
                "ungrounded",
            )
            comparison = comparison_lookup(
                comparisons,
                group,
                "false_refusal_rate",
            )
            table_two.append(
                [
                    group_label,
                    "False refusal rate",
                    format_estimate(grounded, percent=True),
                    format_estimate(ungrounded, percent=True),
                    format_p_value(float(comparison["p_value_two_sided"])),
                ]
            )

    partial_rows = []
    for metric, label in (
        ("supported_part_score", "Supported part score"),
        ("supported_part_fully_answered_rate", "Supported part fully answered"),
        ("unsupported_part_limitation_score", "Unsupported part limitation score"),
        ("unsupported_part_fully_limited_rate", "Unsupported part fully limited"),
    ):
        grounded = metric_lookup(
            estimates,
            "partially_answerable",
            metric,
            "grounded",
        )
        ungrounded = metric_lookup(
            estimates,
            "partially_answerable",
            metric,
            "ungrounded",
        )
        comparison = comparison_lookup(
            comparisons,
            "partially_answerable",
            metric,
        )
        partial_rows.append(
            [
                label,
                format_estimate(grounded, percent=True),
                format_estimate(ungrounded, percent=True),
                format_p_value(float(comparison["p_value_two_sided"])),
            ]
        )

    refusal_rows = []
    for metric, label in (
        ("correct_refusal_rate", "Correct refusal rate"),
        ("false_answer_rate", "False answer rate"),
        ("semantic_refusal_rate", "Semantic refusal rate"),
    ):
        grounded = metric_lookup(estimates, "unanswerable", metric, "grounded")
        ungrounded = metric_lookup(
            estimates,
            "unanswerable",
            metric,
            "ungrounded",
        )
        comparison = comparison_lookup(comparisons, "unanswerable", metric)
        refusal_rows.append(
            [
                label,
                format_estimate(grounded, percent=True),
                format_estimate(ungrounded, percent=True),
                format_p_value(float(comparison["p_value_two_sided"])),
            ]
        )

    citation_rows = []
    for group, label in (
        ("answerable", "Answerable (n=30 Grounded outputs)"),
        (
            "partially_answerable",
            "Partially answerable (n=10 Grounded outputs)",
        ),
        ("factual_combined", "Combined (n=40 Grounded outputs)"),
    ):
        citation_rows.append(
            [
                label,
                format_estimate(
                    metric_lookup(
                        estimates,
                        group,
                        "citation_precision",
                        "grounded",
                    ),
                    percent=True,
                ),
                format_estimate(
                    metric_lookup(
                        estimates,
                        group,
                        "citation_coverage",
                        "grounded",
                    ),
                    percent=True,
                ),
            ]
        )

    claim_rows = []
    for row in claim_metrics:
        if row["group"] != "factual_combined":
            continue
        claim_rows.append(
            [
                str(row["mode"]).title(),
                str(row["substantive_claims"]),
                f"{float(row['fully_supported_rate']) * 100:.1f}%",
                f"{float(row['any_supported_rate']) * 100:.1f}%",
                f"{float(row['unsupported_or_contradicted_rate']) * 100:.1f}%",
            ]
        )

    failure_rows = [
        [
            "020",
            "Ungrounded",
            "Kernel behaviour differed from the reported experiment.",
        ],
        [
            "022",
            "Ungrounded",
            "Used a general covariance convention rather than the course convention.",
        ],
        [
            "032",
            "Ungrounded",
            "Invented a unique K-medians centroid for an even sample.",
        ],
        [
            "034",
            "Both",
            "Overextended breakdown-point evidence into exact outlier counts.",
        ],
        [
            "040",
            "Both",
            "Grounded overclaimed test-set semantics; ungrounded fabricated values.",
        ],
        [
            "048",
            "Neither",
            "Both conditions correctly refused; recovered run provenance retained.",
        ],
    ]

    return "\n\n".join(
        [
            "# V1-A Final Grounding Results",
            (
                "This report is generated only from the frozen, author-signed "
                "response and claim annotations. Grounded and ungrounded answers "
                "are paired by evaluation case."
            ),
            "## Denominators and applicability",
            (
                "Answer correctness and fully correct rates use 40 paired factual "
                "cases: 30 answerable and 10 partially answerable. Response-level "
                "course-support rates are macro-averages of each factual output's "
                "annotated substantive claims; unanswerable refusal outputs are "
                "excluded. Partial-answer behaviour uses 10 paired partial cases. "
                "Refusal and false-answer rates use 10 paired unanswerable cases. "
                "Citation precision and coverage use only the 40 applicable "
                "Grounded factual outputs; the Ungrounded condition produced no "
                "source citations by design, so its citation metrics are N/A, not "
                "zero. Claim-level pooled denominators are reported separately in "
                "Table 6."
            ),
            "## Table 1. Overall factual-answer results",
            markdown_table(
                [
                    "Metric",
                    "Grounded, estimate [95% CI]",
                    "Ungrounded, estimate [95% CI]",
                    "Paired difference [95% CI]",
                    "Two-sided p",
                ],
                table_one,
            ),
            (
                "Factual results combine 30 answerable and 10 partially answerable "
                "cases. Differences are Grounded minus Ungrounded. The response-"
                "level course-supported claim rate counts fully supported claims; "
                "partial support is reported separately in the claim annotations."
            ),
            "![Answer correctness](figures/figure_1_answer_correctness.svg)",
            "## Table 2. Results by answerability",
            markdown_table(
                [
                    "Group",
                    "Metric",
                    "Grounded [95% CI]",
                    "Ungrounded [95% CI]",
                    "Two-sided p",
                ],
                table_two,
            ),
            "![Claim support](figures/figure_2_claim_support.svg)",
            "## Table 3. Partially answerable cases (n=10 paired cases)",
            markdown_table(
                [
                    "Metric",
                    "Grounded [95% CI]",
                    "Ungrounded [95% CI]",
                    "Two-sided p",
                ],
                partial_rows,
            ),
            (
                "Partial judgements use 1 for yes, 0.5 for partial, and 0 for no "
                "in score metrics. Full rates count only yes."
            ),
            "## Table 4. Unanswerable cases (n=10 paired cases)",
            markdown_table(
                [
                    "Metric",
                    "Grounded [95% CI]",
                    "Ungrounded [95% CI]",
                    "McNemar exact p",
                ],
                refusal_rows,
            ),
            "![Refusal behaviour](figures/figure_3_refusal_behavior.svg)",
            "## Table 5. Grounded citation quality",
            markdown_table(
                ["Group", "Citation precision [95% CI]", "Citation coverage [95% CI]"],
                citation_rows,
            ),
            (
                "Citation metrics are Grounded-only. Ungrounded citation values are "
                "not applicable and are not encoded as zero."
            ),
            "## Table 6. Claim-level micro analysis",
            markdown_table(
                [
                    "Mode",
                    "Claims",
                    "Fully supported",
                    "Any support",
                    "Unsupported or contradicted",
                ],
                claim_rows,
            ),
            "## Qualitative failure analysis",
            markdown_table(["Case", "Affected condition", "Finding"], failure_rows),
            (
                "Full signed-off notes for these cases are exported in "
                "`qualitative_failure_cases.csv`."
            ),
            "## Statistical interpretation",
            (
                "Continuous and ordinal paired outcomes use paired sign-flip tests "
                "with paired bootstrap 95% confidence intervals. Binary paired "
                "outcomes use exact McNemar tests and Wilson intervals for each "
                "condition. Bootstrap and Monte Carlo procedures use deterministic "
                "seeds. Because partial and unanswerable groups contain only ten "
                "cases each, effect sizes and confidence intervals should be "
                "emphasised; p-values are exploratory and are not adjusted for "
                "multiple comparisons."
            ),
        ]
    ) + "\n"


def build_results_discussion(
    estimates: Sequence[dict[str, Any]],
    comparisons: Sequence[dict[str, Any]],
    claim_metrics: Sequence[dict[str, Any]],
) -> str:
    def estimate(group: str, metric: str, mode: str) -> float:
        return float(metric_lookup(estimates, group, metric, mode)["estimate"])

    def difference(group: str, metric: str) -> dict[str, Any]:
        return comparison_lookup(comparisons, group, metric)

    overall_correctness = difference(
        "factual_combined",
        "mean_answer_correctness",
    )
    overall_full = difference("factual_combined", "fully_correct_rate")
    overall_support = difference(
        "factual_combined",
        "course_supported_claim_rate",
    )
    overall_unsupported = difference(
        "factual_combined",
        "unsupported_by_course_claim_rate",
    )
    partial_correctness = difference(
        "partially_answerable",
        "mean_answer_correctness",
    )
    partial_support = difference(
        "partially_answerable",
        "course_supported_claim_rate",
    )
    partial_limitation = difference(
        "partially_answerable",
        "unsupported_part_fully_limited_rate",
    )
    refusal = difference("unanswerable", "correct_refusal_rate")
    false_answer = difference("unanswerable", "false_answer_rate")
    grounded_claims = next(
        row
        for row in claim_metrics
        if row["group"] == "factual_combined" and row["mode"] == "grounded"
    )
    ungrounded_claims = next(
        row
        for row in claim_metrics
        if row["group"] == "factual_combined" and row["mode"] == "ungrounded"
    )
    full_difference_pp = (
        float(overall_full["difference_grounded_minus_ungrounded"]) * 100
    )
    support_difference_pp = (
        float(overall_support["difference_grounded_minus_ungrounded"]) * 100
    )

    return f"""# V1-A Results and Discussion

## Results

### Overall reliability on answerable content

The paired formal evaluation contained 50 questions: 30 answerable, 10
partially answerable, and 10 unanswerable. Each question was answered under a
Grounded condition and an otherwise equivalent Ungrounded condition. The 40
answerable or partially answerable cases formed the factual-answer analysis.
Response-level claim rates macro-averaged the annotated substantive claims in
these 40 outputs per condition; refusal outputs were excluded. Refusal metrics
used the 10 unanswerable paired cases. Citation metrics used only the 40
applicable Grounded factual outputs because the Ungrounded baseline did not
produce source citations by design.

Within this frozen corpus and evaluation set, Grounding improved factual answer
quality. Mean human-rated correctness was
{overall_correctness['grounded_estimate']:.3f} out of 2 for Grounded responses
and {overall_correctness['ungrounded_estimate']:.3f} for Ungrounded responses,
a paired difference of {overall_correctness['difference_grounded_minus_ungrounded']:.3f}
(95% CI {overall_correctness['difference_ci_95_low']:.3f} to
{overall_correctness['difference_ci_95_high']:.3f},
p {format_p_for_prose(float(overall_correctness['p_value_two_sided']))}). The
fully correct rate was {overall_full['grounded_estimate'] * 100:.1f}% under
Grounding and {overall_full['ungrounded_estimate'] * 100:.1f}% without
Grounding, corresponding to a {full_difference_pp:.1f} percentage-point paired
difference
(p {format_p_for_prose(float(overall_full['p_value_two_sided']))}).

The same pattern appeared in post-hoc course-evidence support. The mean rate of
fully course-supported claims was {overall_support['grounded_estimate'] * 100:.1f}%
for Grounded responses and {overall_support['ungrounded_estimate'] * 100:.1f}%
for Ungrounded responses, a {support_difference_pp:.1f} percentage-point
difference
(p {format_p_for_prose(float(overall_support['p_value_two_sided']))}). The mean
unsupported-by-course claim rate was
{overall_unsupported['grounded_estimate'] * 100:.1f}% for Grounded responses
and {overall_unsupported['ungrounded_estimate'] * 100:.1f}% for Ungrounded
responses (paired difference
{overall_unsupported['difference_grounded_minus_ungrounded'] * 100:.1f}
percentage points, p
{format_p_for_prose(float(overall_unsupported['p_value_two_sided']))}).

At claim level, {grounded_claims['fully_supported_rate'] * 100:.1f}% of the
{grounded_claims['substantive_claims']} Grounded substantive claims were fully
supported, compared with {ungrounded_claims['fully_supported_rate'] * 100:.1f}%
of {ungrounded_claims['substantive_claims']} Ungrounded claims. No Grounded
substantive claim was annotated as unsupported or contradicted, whereas
{ungrounded_claims['unsupported_or_contradicted_rate'] * 100:.1f}% of
Ungrounded claims fell into those categories.

### Differences by answerability

For the 30 fully answerable questions, Grounded responses achieved a mean
correctness score of
{estimate('answerable', 'mean_answer_correctness', 'grounded'):.3f}, compared
with {estimate('answerable', 'mean_answer_correctness', 'ungrounded'):.3f} for
Ungrounded responses. Both conditions had a 0% false-refusal rate on these
questions, showing that the reliability advantage did not result from refusing
questions that the course corpus could answer.

The difference was larger on the 10 partially answerable questions. Grounded
mean correctness was {partial_correctness['grounded_estimate']:.3f}, compared
with {partial_correctness['ungrounded_estimate']:.3f} for Ungrounded responses
(p {format_p_for_prose(float(partial_correctness['p_value_two_sided']))}). The
Grounded course-supported claim rate was
{partial_support['grounded_estimate'] * 100:.1f}%, compared with
{partial_support['ungrounded_estimate'] * 100:.1f}% without Grounding
(p {format_p_for_prose(float(partial_support['p_value_two_sided']))}). Grounded
responses fully limited the unsupported portion in
{partial_limitation['grounded_estimate'] * 100:.1f}% of cases, compared with
{partial_limitation['ungrounded_estimate'] * 100:.1f}% for Ungrounded responses.
This difference was not statistically detectable in the small partial subset
(p {format_p_for_prose(float(partial_limitation['p_value_two_sided']))}).

### Refusal behaviour

Grounding produced a marked difference on the 10 unanswerable questions. The
Grounded tutor correctly refused all 10 cases
({refusal['grounded_estimate'] * 100:.1f}%), whereas the Ungrounded condition
correctly refused {refusal['ungrounded_estimate'] * 100:.1f}%
(McNemar exact p {format_p_for_prose(float(refusal['p_value_two_sided']))}). No
Grounded response falsely answered an unanswerable question, while the
Ungrounded false-answer rate was {false_answer['ungrounded_estimate'] * 100:.1f}%
(McNemar exact p
{format_p_for_prose(float(false_answer['p_value_two_sided']))}).

### Citation traceability

Citation quality was evaluated only for Grounded factual responses because the
Ungrounded baseline was not designed to produce citations. Across the 40
answerable and partially answerable Grounded responses, mean citation precision
was {estimate('factual_combined', 'citation_precision', 'grounded') * 100:.1f}%
and mean citation coverage was
{estimate('factual_combined', 'citation_coverage', 'grounded') * 100:.1f}%.
Precision was lower for partially answerable questions
({estimate('partially_answerable', 'citation_precision', 'grounded') * 100:.1f}%)
than for fully answerable questions
({estimate('answerable', 'citation_precision', 'grounded') * 100:.1f}%),
indicating that citation attribution became harder when a question extended
beyond what the source fully specified.

## Discussion

### Contribution of evidence grounding

Within the frozen course corpus and evaluation set, the results support the
claim that evidence-aware tutoring improved course-specific reliability and
traceability relative to the otherwise comparable Ungrounded baseline. The
Ungrounded model often answered general
conceptual questions correctly, but it was less reliable when a question
depended on a course-specific convention, experimental result, or explicit
scope limitation. Cases 020 and 022 illustrate this distinction: the
Ungrounded answers were plausible as general machine-learning explanations but
did not match the experiment or covariance convention used in the uploaded
notes. Grounding therefore contributed more than generic factual recall; it
aligned answers with the local instructional source.

The refusal results provide the clearest evidence of calibrated behaviour. A
general-purpose model may possess relevant world knowledge, but using that
knowledge violates the task when the tutor is expected to answer only from the
student's materials. The Grounded tutor refused every unanswerable case and
made no false answers, while the Ungrounded condition supplied unsupported
answers in six of ten cases. Case 048 also demonstrates that Grounding did not
create an artificial difference when both systems appropriately recognised
missing information: both conditions refused, and the recovered infrastructure
run retained explicit provenance.

### Grounding does not guarantee perfect interpretation

High course-support and citation scores should not be interpreted as proof that
every Grounded response was semantically perfect. Cases 034 and 040 expose two
important limitations. In case 034, the response extended a source statement
about a 50% breakdown point into an exact finite-sample outlier count. In case
040, the Grounded answer cited a reported R-squared value but incorrectly
described it as a test-set result. These failures show that a citation may be
topically relevant while the generated wording overstates what the evidence
entails. Claim-level review and citation precision are therefore both necessary;
the mere presence of a source marker is insufficient.

Partially answerable questions remain a further challenge. Grounding
substantially improved correctness and support for the answerable portion, but
the difference in fully limiting the unsupported portion was smaller and
uncertain. This suggests that retrieval and citation constraints help the tutor
identify usable evidence, while deciding exactly where to stop an answer still
requires careful uncertainty and refusal policies.

### Implications for trustworthy educational AI

For educational use, the practical value of Grounding is not that it makes an
LLM universally knowledgeable. Its value is that it constrains explanations to
the learner's course context, exposes the evidence behind substantive claims,
and improves refusal when the material is insufficient. This supports an
evidence-aware design in which answer correctness, post-hoc course support,
citation quality, and refusal behaviour are measured separately. In
particular, an Ungrounded answer without citations is not automatically wrong,
and a Grounded answer with citations is not automatically correct.

### Limitations

The evaluation used one uploaded course corpus, one configured language model,
and 50 paired questions. The answerable group was larger than the partial and
unanswerable groups, each of which contained only 10 cases. Confidence intervals
for those smaller groups are consequently wide. Inferential p-values were
treated as exploratory and were not adjusted for multiple comparisons; effect
sizes and confidence intervals should carry greater interpretive weight.

The final annotations were AI-assisted and received final author sign-off, but
the study did not include a second independent annotator. Inter-rater agreement
therefore cannot be reported. The paired design controls question difficulty
between conditions, but broader claims will require replication across courses,
document formats, subject areas, models, and independent evaluators. Finally,
the study evaluates response reliability rather than long-term learning gain;
the adaptive-policy and closed-loop evaluations address different parts of the
system and should be reported separately.
"""


def format_p_for_prose(value: float) -> str:
    if value < 0.001:
        return "< .001"
    return f"= {value:.3f}"


def build_analysis(
    response_path: Path = DEFAULT_RESPONSE_PATH,
    claim_path: Path = DEFAULT_CLAIM_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    responses, claims = validate_frozen_inputs(response_path, claim_path)
    estimates, comparisons = build_response_metrics(responses)
    claim_metrics = build_claim_metrics(claims)
    output_dir.mkdir(parents=True, exist_ok=True)

    rounded_estimates = rounded(estimates)
    rounded_comparisons = rounded(comparisons)
    rounded_claim_metrics = rounded(claim_metrics)
    assert isinstance(rounded_estimates, list)
    assert isinstance(rounded_comparisons, list)
    assert isinstance(rounded_claim_metrics, list)

    write_csv(output_dir / "response_metrics.csv", rounded_estimates)
    write_csv(output_dir / "paired_comparisons.csv", rounded_comparisons)
    write_csv(output_dir / "claim_metrics.csv", rounded_claim_metrics)
    failure_cases = write_failure_cases(output_dir, responses)
    write_figures(output_dir, estimates)

    summary: dict[str, Any] = {
        "analysis_version": ANALYSIS_VERSION,
        "design": "paired grounded versus ungrounded",
        "case_counts": {
            "total": 50,
            "answerable": 30,
            "partially_answerable": 10,
            "unanswerable": 10,
        },
        "response_metrics": rounded_estimates,
        "paired_comparisons": rounded_comparisons,
        "claim_metrics": rounded_claim_metrics,
        "qualitative_case_ids": sorted({row["case_id"] for row in failure_cases}),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "analysis_version": ANALYSIS_VERSION,
        "frozen_inputs": {
            "response_annotations": {
                "path": str(response_path.relative_to(EVAL_DIR.parent)),
                "sha256": sha256_file(response_path),
                "rows": len(responses),
            },
            "claim_annotations": {
                "path": str(claim_path.relative_to(EVAL_DIR.parent)),
                "sha256": sha256_file(claim_path),
                "rows": len(claims),
            },
        },
        "methods": {
            "confidence_level": 0.95,
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "permutation_resamples": PERMUTATION_RESAMPLES,
            "continuous_paired_test": "paired sign-flip permutation",
            "binary_paired_test": "McNemar exact",
            "binary_condition_ci": "Wilson score",
            "random_seed": "deterministic SHA256-derived per metric",
            "multiple_comparison_adjustment": "none; exploratory p-values",
        },
    }
    (output_dir / "analysis_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "results_tables.md").write_text(
        build_results_markdown(estimates, comparisons, claim_metrics),
        encoding="utf-8",
    )
    (output_dir / "results_and_discussion.md").write_text(
        build_results_discussion(estimates, comparisons, claim_metrics),
        encoding="utf-8",
    )
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyse frozen V1-A human annotations.",
    )
    parser.add_argument("--responses", type=Path, default=DEFAULT_RESPONSE_PATH)
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIM_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    summary = build_analysis(args.responses, args.claims, args.output_dir)
    counts = summary["case_counts"]
    print(
        "V1-A final analysis complete: "
        f"{counts['total']} paired cases -> {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
