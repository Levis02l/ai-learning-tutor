from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_CASES_PATH = Path(__file__).parent / "datasets" / "grounding_v1.json"
DEFAULT_OUTPUT_DIR = Path(__file__).with_name("results")
MODES = ("grounded", "ungrounded")
ANSWERABILITY_TO_EXPECTED_ANSWERABLE = {
    "answerable": True,
    "partially_answerable": True,
    "unanswerable": False,
}


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        cases = json.load(file)

    if not isinstance(cases, list):
        raise ValueError("Evaluation cases file must contain a JSON list")

    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Each evaluation case must be a JSON object")
        _validate_case(case)

    return cases


def _validate_case(case: dict[str, Any]) -> None:
    if "question" not in case:
        raise ValueError("Evaluation case is missing required field: question")

    has_legacy_answerable = "expected_answerable" in case
    has_answerability = "answerability" in case
    if not has_legacy_answerable and not has_answerability:
        raise ValueError(
            "Evaluation case must define answerability or expected_answerable"
        )

    if has_answerability:
        answerability = case["answerability"]
        if answerability not in ANSWERABILITY_TO_EXPECTED_ANSWERABLE:
            raise ValueError(
                "answerability must be one of: "
                "answerable, partially_answerable, unanswerable"
            )

    if "case_id" not in case and "id" not in case:
        raise ValueError("Evaluation case is missing required field: case_id")


def expected_answerable_for(case: dict[str, Any]) -> bool:
    if "answerability" in case:
        return ANSWERABILITY_TO_EXPECTED_ANSWERABLE[case["answerability"]]
    return bool(case["expected_answerable"])


def run_case(
    *,
    client: httpx.Client,
    base_url: str,
    case: dict[str, Any],
    user_id: str,
    top_k: int,
    course_id_override: int | None = None,
) -> dict[str, Any]:
    course_id = course_id_override if course_id_override is not None else case.get(
        "course_id"
    )
    compare_payload: dict[str, Any] = {
        "query": case["question"],
        "user_id": user_id,
        "top_k": top_k,
    }
    if course_id is not None:
        compare_payload["course_id"] = course_id

    compare_response = client.post(
        f"{base_url}/chat/compare",
        json=compare_payload,
    )
    compare_response.raise_for_status()
    comparison = compare_response.json()

    evaluations: dict[str, Any] = {}
    for mode in MODES:
        evaluation_payload: dict[str, Any] = {
            "user_id": user_id,
            "expected_answerable": expected_answerable_for(case),
            "response": comparison[mode],
        }
        if course_id is not None:
            evaluation_payload["course_id"] = course_id

        eval_response = client.post(
            f"{base_url}/evaluation/answer",
            json=evaluation_payload,
        )
        eval_response.raise_for_status()
        evaluations[mode] = eval_response.json()

    return {
        "case": case,
        "comparison": comparison,
        "evaluations": evaluations,
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(results),
        "modes": {},
    }

    for mode in MODES:
        evaluations = [result["evaluations"][mode] for result in results]
        summary["modes"][mode] = {
            "average_groundedness": _average(
                evaluations,
                "groundedness_score",
            ),
            "average_unsupported_claim_rate": _average(
                evaluations,
                "unsupported_claim_rate",
            ),
            "average_citation_precision": _average(
                evaluations,
                "citation_precision",
            ),
            "correct_refusal_rate": _rate(evaluations, "correct_refusal"),
            "average_claim_count": _average(evaluations, "claim_count"),
        }

    return summary


def write_outputs(
    *,
    output_dir: Path,
    results: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "answer_eval_results.json"
    summary_json_path = output_dir / "answer_eval_summary.json"
    summary_csv_path = output_dir / "answer_eval_summary.csv"

    results_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary_json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_summary_csv(summary_csv_path, summary)


def _write_summary_csv(path: Path, summary: dict[str, Any]) -> None:
    rows: list[dict[str, Any]] = []
    for mode, metrics in summary["modes"].items():
        row = {"mode": mode}
        row.update(metrics)
        rows.append(row)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "mode",
                "average_groundedness",
                "average_unsupported_claim_rate",
                "average_citation_precision",
                "correct_refusal_rate",
                "average_claim_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _average(evaluations: list[dict[str, Any]], key: str) -> float:
    if not evaluations:
        return 0.0
    return round(
        sum(float(evaluation.get(key, 0.0)) for evaluation in evaluations)
        / len(evaluations),
        3,
    )


def _rate(evaluations: list[dict[str, Any]], key: str) -> float:
    if not evaluations:
        return 0.0
    return round(
        sum(1 for evaluation in evaluations if evaluation.get(key)) / len(evaluations),
        3,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run grounded vs ungrounded answer evaluation through the API."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--user-id", default="demo-user")
    parser.add_argument(
        "--course-id",
        type=int,
        default=None,
        help="Optional course_id override for every case.",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = load_cases(args.cases)
    base_url = args.base_url.rstrip("/")

    with httpx.Client(timeout=args.timeout) as client:
        results = [
            run_case(
                client=client,
                base_url=base_url,
                case=case,
                user_id=args.user_id,
                top_k=args.top_k,
                course_id_override=args.course_id,
            )
            for case in cases
        ]

    summary = summarize_results(results)
    write_outputs(output_dir=args.output_dir, results=results, summary=summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
