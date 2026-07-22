import json

import pytest

from eval.run_answer_evaluation import (
    expected_answerable_for,
    load_cases,
    run_case,
    summarize_results,
)


def test_load_cases_accepts_grounding_v1_schema(tmp_path) -> None:
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "grounding_001",
                    "course_id": 2,
                    "question": "What objective does K-means minimise?",
                    "answerability": "answerable",
                    "reference_answer": "Within-cluster sum of squares.",
                    "gold_evidence": [
                        {
                            "document": "Lecture",
                            "relevant_text": "K-means minimises WCSS.",
                        }
                    ],
                    "category": "factual",
                    "concept": "K-means Clustering",
                    "difficulty": "easy",
                    "notes": "",
                }
            ]
        ),
        encoding="utf-8",
    )

    cases = load_cases(cases_path)

    assert cases[0]["case_id"] == "grounding_001"
    assert expected_answerable_for(cases[0]) is True


def test_load_cases_rejects_unknown_answerability(tmp_path) -> None:
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "bad",
                    "question": "Q?",
                    "answerability": "maybe",
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="answerability"):
        load_cases(cases_path)


def test_expected_answerable_for_supports_legacy_cases() -> None:
    assert expected_answerable_for({"expected_answerable": True}) is True
    assert expected_answerable_for({"expected_answerable": False}) is False


def test_expected_answerable_for_partially_answerable_case() -> None:
    assert expected_answerable_for({"answerability": "partially_answerable"}) is True


def test_run_case_passes_course_scope_and_answerability() -> None:
    client = _FakeClient()
    case = {
        "case_id": "grounding_003",
        "course_id": 2,
        "question": (
            "According to the course material, does K-means guarantee the "
            "global optimum?"
        ),
        "answerability": "partially_answerable",
    }

    result = run_case(
        client=client,  # type: ignore[arg-type]
        base_url="http://testserver",
        case=case,
        user_id="demo-user",
        top_k=5,
    )

    compare_payload = client.posts[0]["json"]
    grounded_eval_payload = client.posts[1]["json"]
    assert compare_payload["course_id"] == 2
    assert grounded_eval_payload["course_id"] == 2
    assert grounded_eval_payload["expected_answerable"] is True
    assert result["case"]["case_id"] == "grounding_003"


def test_summarize_results_aggregates_mode_metrics() -> None:
    results = [
        {
            "evaluations": {
                "grounded": {
                    "groundedness_score": 1.0,
                    "unsupported_claim_rate": 0.0,
                    "citation_precision": 1.0,
                    "correct_refusal": True,
                    "claim_count": 2,
                },
                "ungrounded": {
                    "groundedness_score": 0.0,
                    "unsupported_claim_rate": 1.0,
                    "citation_precision": 0.0,
                    "correct_refusal": False,
                    "claim_count": 2,
                },
            }
        },
        {
            "evaluations": {
                "grounded": {
                    "groundedness_score": 0.5,
                    "unsupported_claim_rate": 0.5,
                    "citation_precision": 1.0,
                    "correct_refusal": True,
                    "claim_count": 4,
                },
                "ungrounded": {
                    "groundedness_score": 0.0,
                    "unsupported_claim_rate": 1.0,
                    "citation_precision": 0.0,
                    "correct_refusal": False,
                    "claim_count": 3,
                },
            }
        },
    ]

    summary = summarize_results(results)

    assert summary["case_count"] == 2
    assert summary["modes"]["grounded"]["average_groundedness"] == 0.75
    assert summary["modes"]["grounded"]["correct_refusal_rate"] == 1.0
    assert summary["modes"]["ungrounded"]["average_unsupported_claim_rate"] == 1.0


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class _FakeClient:
    def __init__(self) -> None:
        self.posts: list[dict] = []

    def post(self, url: str, json: dict) -> _FakeResponse:
        self.posts.append({"url": url, "json": json})
        if url.endswith("/chat/compare"):
            return _FakeResponse(
                {
                    "grounded": {"mode": "grounded"},
                    "ungrounded": {"mode": "ungrounded"},
                }
            )
        return _FakeResponse(
            {
                "groundedness_score": 1.0,
                "unsupported_claim_rate": 0.0,
                "citation_precision": 1.0,
                "correct_refusal": True,
                "claim_count": 1,
            }
        )
