import json

import pytest

from eval.run_answer_evaluation import (
    answerability_for_case,
    build_manifest,
    build_run_config,
    create_run_dir,
    expected_answerable_for,
    file_sha256,
    load_cases,
    run_case,
    run_case_safely,
    summarize_results,
    write_outputs,
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


def test_answerability_for_case_preserves_partial_cases() -> None:
    assert (
        answerability_for_case({"answerability": "partially_answerable"})
        == "partially_answerable"
    )
    assert answerability_for_case({"expected_answerable": True}) == "answerable"
    assert answerability_for_case({"expected_answerable": False}) == "unanswerable"


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
    assert grounded_eval_payload["answerability"] == "partially_answerable"
    assert result["case"]["case_id"] == "grounding_003"


def test_run_case_safely_records_error_and_continues() -> None:
    client = _FailingClient()
    case = {
        "case_id": "broken",
        "course_id": 2,
        "question": "Q?",
        "answerability": "answerable",
    }

    result = run_case_safely(
        client=client,  # type: ignore[arg-type]
        base_url="http://testserver",
        case=case,
        user_id="demo-user",
        top_k=5,
    )

    assert result["case_id"] == "broken"
    assert result["error"]["type"] == "RuntimeError"
    assert result["evaluations"] == {}


def test_summarize_results_aggregates_mode_metrics() -> None:
    results = [
        {
            "answerability": "answerable",
            "evaluations": {
                "grounded": {
                    "generation_groundedness_score": 1.0,
                    "generated_unsupported_claim_rate": 0.0,
                    "automatic_cited_claim_support_rate": 1.0,
                    "citation_coverage": 1.0,
                    "effective_refusal": False,
                    "claim_count": 2,
                },
                "ungrounded": {
                    "generation_groundedness_score": 0.0,
                    "generated_unsupported_claim_rate": 1.0,
                    "automatic_cited_claim_support_rate": None,
                    "citation_coverage": None,
                    "effective_refusal": False,
                    "claim_count": 2,
                },
            }
        },
        {
            "answerability": "answerable",
            "evaluations": {
                "grounded": {
                    "generation_groundedness_score": 0.5,
                    "generated_unsupported_claim_rate": 0.5,
                    "automatic_cited_claim_support_rate": 1.0,
                    "citation_coverage": 1.0,
                    "effective_refusal": False,
                    "claim_count": 4,
                },
                "ungrounded": {
                    "generation_groundedness_score": 0.0,
                    "generated_unsupported_claim_rate": 1.0,
                    "automatic_cited_claim_support_rate": None,
                    "citation_coverage": None,
                    "effective_refusal": False,
                    "claim_count": 3,
                },
            }
        },
        {
            "answerability": "partially_answerable",
            "evaluations": {
                "grounded": {
                    "generation_groundedness_score": 0.5,
                    "generated_unsupported_claim_rate": 0.0,
                    "automatic_cited_claim_support_rate": 1.0,
                    "citation_coverage": 0.5,
                    "effective_refusal": True,
                    "semantic_refusal": True,
                    "refused_by_status": False,
                    "claim_count": 2,
                },
                "ungrounded": {
                    "generation_groundedness_score": 0.0,
                    "generated_unsupported_claim_rate": 1.0,
                    "automatic_cited_claim_support_rate": None,
                    "citation_coverage": None,
                    "effective_refusal": False,
                    "semantic_refusal": False,
                    "refused_by_status": False,
                    "claim_count": 3,
                },
            },
        },
        {
            "answerability": "unanswerable",
            "evaluations": {
                "grounded": {
                    "generation_groundedness_score": 0.0,
                    "generated_unsupported_claim_rate": 0.0,
                    "automatic_cited_claim_support_rate": None,
                    "citation_coverage": None,
                    "automatic_refusal_correctness": True,
                    "effective_refusal": True,
                    "semantic_refusal": True,
                    "refused_by_status": True,
                    "claim_count": 1,
                },
                "ungrounded": {
                    "generation_groundedness_score": 0.0,
                    "generated_unsupported_claim_rate": 1.0,
                    "automatic_cited_claim_support_rate": None,
                    "citation_coverage": None,
                    "automatic_refusal_correctness": False,
                    "effective_refusal": False,
                    "semantic_refusal": False,
                    "refused_by_status": False,
                    "claim_count": 1,
                },
            },
        },
    ]

    summary = summarize_results(results)

    assert summary["case_count"] == 4
    assert summary["modes"]["grounded"]["answerable_case_count"] == 2
    assert summary["modes"]["grounded"]["partial_case_count"] == 1
    assert summary["modes"]["grounded"]["unanswerable_case_count"] == 1
    assert (
        summary["modes"]["grounded"]["answerable_metrics"][
            "average_generation_groundedness"
        ]
        == 0.75
    )
    assert (
        summary["modes"]["grounded"]["refusal_metrics"][
            "automatic_correct_refusal_rate"
        ]
        == 1.0
    )
    assert (
        summary["modes"]["ungrounded"]["answerable_metrics"][
            "average_automatic_cited_claim_support_rate"
        ]
        is None
    )
    assert (
        summary["modes"]["ungrounded"]["refusal_metrics"][
            "automatic_false_answer_rate"
        ]
        == 1.0
    )
    assert (
        summary["modes"]["grounded"]["partial_metrics"][
            "automatic_limitation_or_refusal_rate"
        ]
        == 1.0
    )


def test_summarize_results_tracks_failed_cases() -> None:
    summary = summarize_results(
        [
            {
                "case_id": "ok",
                "answerability": "answerable",
                "evaluations": {
                    "grounded": {
                        "generation_groundedness_score": 1.0,
                        "generated_unsupported_claim_rate": 0.0,
                        "automatic_cited_claim_support_rate": 1.0,
                        "citation_coverage": 1.0,
                        "effective_refusal": False,
                        "claim_count": 2,
                    },
                    "ungrounded": {
                        "generation_groundedness_score": 0.0,
                        "generated_unsupported_claim_rate": 1.0,
                        "automatic_cited_claim_support_rate": None,
                        "citation_coverage": None,
                        "effective_refusal": False,
                        "claim_count": 2,
                    },
                },
                "error": None,
            },
            {
                "case_id": "failed",
                "evaluations": {},
                "error": {"type": "RuntimeError", "message": "boom"},
            },
        ]
    )

    assert summary["case_count"] == 2
    assert summary["successful_case_count"] == 1
    assert summary["failed_case_count"] == 1
    assert summary["failed_cases"][0]["case_id"] == "failed"
    assert summary["modes"]["grounded"]["evaluated_case_count"] == 1


def test_create_run_dir_prevents_explicit_overwrite(tmp_path) -> None:
    run_dir = create_run_dir(
        output_root=tmp_path,
        run_type="pilot",
        run_id="grounding_v1_test",
        explicit_run_id=True,
    )

    assert run_dir.exists()
    with pytest.raises(FileExistsError):
        create_run_dir(
            output_root=tmp_path,
            run_type="pilot",
            run_id="grounding_v1_test",
            explicit_run_id=True,
        )


def test_create_run_dir_suffixes_generated_collisions(tmp_path) -> None:
    first = create_run_dir(
        output_root=tmp_path,
        run_type="pilot",
        run_id="grounding_v1_test",
        explicit_run_id=False,
    )
    second = create_run_dir(
        output_root=tmp_path,
        run_type="pilot",
        run_id="grounding_v1_test",
        explicit_run_id=False,
    )

    assert first.name == "grounding_v1_test"
    assert second.name == "grounding_v1_test_01"


def test_write_outputs_creates_reproducible_run_snapshot(tmp_path) -> None:
    results = [
        {
            "case_id": "grounding_001",
            "answerability": "answerable",
            "evaluations": {
                "grounded": {
                    "generation_groundedness_score": 1.0,
                    "generated_unsupported_claim_rate": 0.0,
                    "automatic_cited_claim_support_rate": 1.0,
                    "citation_coverage": 1.0,
                    "effective_refusal": False,
                    "claim_count": 2,
                },
                "ungrounded": {
                    "generation_groundedness_score": 0.0,
                    "generated_unsupported_claim_rate": 1.0,
                    "automatic_cited_claim_support_rate": None,
                    "citation_coverage": None,
                    "effective_refusal": False,
                    "claim_count": 2,
                },
            },
            "error": None,
        }
    ]
    summary = summarize_results(results)
    manifest = {
        "run_id": "grounding_v1_test",
        "dataset_sha256": "abc",
        "git_commit": "deadbeef",
    }
    run_config = {"runner_version": "eval_v1_a1"}

    write_outputs(
        output_dir=tmp_path,
        results=results,
        summary=summary,
        manifest=manifest,
        run_config=run_config,
    )

    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "raw_results.jsonl").read_text(encoding="utf-8").count(
        "\n"
    ) == 1
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))[
        "git_commit"
    ] == "deadbeef"
    assert (tmp_path / "summary.csv").exists()


def test_build_run_config_and_manifest_capture_dataset_hash(tmp_path) -> None:
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text('[{"case_id": "case"}]', encoding="utf-8")
    dataset_hash = file_sha256(dataset_path)
    args = _Args(
        base_url="http://testserver",
        user_id="demo-user",
        course_id=2,
        top_k=5,
        timeout=120.0,
        run_type="pilot",
        limit=1,
        cases=dataset_path,
        config=tmp_path / "config.json",
    )
    cases = [{"case_id": "case"}]
    summary = {
        "successful_case_count": 1,
        "failed_case_count": 0,
    }

    run_config = build_run_config(
        args=args,  # type: ignore[arg-type]
        experiment_config={"experiment_id": "grounding_v1"},
        dataset_hash=dataset_hash,
        cases=cases,
        generated_at="2026-07-22T12:00:00+00:00",
    )
    manifest = build_manifest(
        run_id="grounding_v1_test",
        generated_at="2026-07-22T12:00:00+00:00",
        args=args,  # type: ignore[arg-type]
        dataset_hash=dataset_hash,
        cases=cases,
        summary=summary,
    )

    assert run_config["dataset_sha256"] == dataset_hash
    assert manifest["dataset_sha256"] == dataset_hash
    assert manifest["case_count"] == 1


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
                "generation_groundedness_score": 1.0,
                "generated_unsupported_claim_rate": 0.0,
                "automatic_cited_claim_support_rate": 1.0,
                "citation_coverage": 1.0,
                "automatic_refusal_correctness": True,
                "effective_refusal": False,
                "semantic_refusal": False,
                "refused_by_status": False,
                "claim_count": 1,
            }
        )


class _FailingClient:
    def post(self, url: str, json: dict) -> _FakeResponse:
        raise RuntimeError("boom")


class _Args:
    def __init__(
        self,
        *,
        base_url: str,
        user_id: str,
        course_id: int | None,
        top_k: int,
        timeout: float,
        run_type: str,
        limit: int | None,
        cases,
        config,
    ) -> None:
        self.base_url = base_url
        self.user_id = user_id
        self.course_id = course_id
        self.top_k = top_k
        self.timeout = timeout
        self.run_type = run_type
        self.limit = limit
        self.cases = cases
        self.config = config
