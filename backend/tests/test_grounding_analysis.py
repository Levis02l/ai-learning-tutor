from pathlib import Path

import pytest

from eval.analyze_grounding_v1 import (
    DEFAULT_CLAIM_PATH,
    DEFAULT_RESPONSE_PATH,
    bootstrap_mean_ci,
    full_success,
    mcnemar_exact,
    paired_permutation_p_value,
    validate_frozen_inputs,
    write_grouped_bar_svg,
)


def test_frozen_annotations_validate() -> None:
    responses, claims = validate_frozen_inputs(
        DEFAULT_RESPONSE_PATH,
        DEFAULT_CLAIM_PATH,
    )

    assert len(responses) == 100
    assert len(claims) == 300


def test_mcnemar_exact_uses_discordant_pairs() -> None:
    grounded = [1.0, 1.0, 1.0, 0.0]
    ungrounded = [0.0, 0.0, 1.0, 1.0]

    p_value, grounded_only, ungrounded_only = mcnemar_exact(
        grounded,
        ungrounded,
    )

    assert grounded_only == 2
    assert ungrounded_only == 1
    assert p_value == pytest.approx(1.0)


def test_paired_permutation_is_deterministic() -> None:
    grounded = [2.0, 2.0, 1.0, 2.0]
    ungrounded = [1.0, 2.0, 0.0, 1.0]

    first = paired_permutation_p_value(
        grounded,
        ungrounded,
        seed_key="test",
    )
    second = paired_permutation_p_value(
        grounded,
        ungrounded,
        seed_key="test",
    )

    assert first == second
    assert first[1] == "paired sign-flip exact"


def test_bootstrap_interval_is_deterministic() -> None:
    first = bootstrap_mean_ci([0.0, 0.5, 1.0], seed_key="test")
    second = bootstrap_mean_ci([0.0, 0.5, 1.0], seed_key="test")

    assert first == second
    assert 0.0 <= first[0] <= first[1] <= 1.0


def test_full_success_counts_partial_as_not_fully_successful() -> None:
    assert full_success("yes") == 1.0
    assert full_success("partial") == 0.0
    assert full_success("no") == 0.0


def test_grouped_bar_svg_contains_series_and_title(tmp_path: Path) -> None:
    output = tmp_path / "figure.svg"
    write_grouped_bar_svg(
        output,
        title="Test comparison",
        categories=["A", "B"],
        grounded=[0.9, 0.1],
        ungrounded=[0.5, 0.5],
        y_max=1.0,
        y_label="Rate",
        value_format="percent",
    )

    content = output.read_text(encoding="utf-8")
    assert "Test comparison" in content
    assert "Grounded" in content
    assert "Ungrounded" in content
