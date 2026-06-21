from eval.run_answer_evaluation import summarize_results


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
