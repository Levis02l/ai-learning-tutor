from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_CONFIG_PATH = Path(__file__).parent / "configs" / "grounding_v1.config.json"
DEFAULT_CASES_PATH = Path(__file__).parent / "datasets" / "grounding_v1.json"
DEFAULT_OUTPUT_DIR = Path(__file__).with_name("results")
MODES = ("grounded", "ungrounded")
RUNNER_VERSION = "eval_v1_a1"
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


def case_id_for(case: dict[str, Any]) -> str:
    return str(case.get("case_id", case.get("id")))


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        config = json.load(file)

    if not isinstance(config, dict):
        raise ValueError("Experiment config file must contain a JSON object")
    return config


def run_case(
    *,
    client: httpx.Client,
    base_url: str,
    case: dict[str, Any],
    user_id: str,
    top_k: int,
    course_id_override: int | None = None,
) -> dict[str, Any]:
    started = perf_counter()
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
        "case_id": case_id_for(case),
        "course_id": course_id,
        "question": case["question"],
        "answerability": case.get("answerability"),
        "case": case,
        "comparison": comparison,
        "evaluations": evaluations,
        "latency_seconds": round(perf_counter() - started, 3),
        "error": None,
    }


def run_case_safely(
    *,
    client: httpx.Client,
    base_url: str,
    case: dict[str, Any],
    user_id: str,
    top_k: int,
    course_id_override: int | None = None,
) -> dict[str, Any]:
    started = perf_counter()
    try:
        return run_case(
            client=client,
            base_url=base_url,
            case=case,
            user_id=user_id,
            top_k=top_k,
            course_id_override=course_id_override,
        )
    except Exception as exc:
        course_id = (
            course_id_override if course_id_override is not None else case.get(
                "course_id"
            )
        )
        return {
            "case_id": case_id_for(case),
            "course_id": course_id,
            "question": case.get("question"),
            "answerability": case.get("answerability"),
            "case": case,
            "comparison": None,
            "evaluations": {},
            "latency_seconds": round(perf_counter() - started, 3),
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    successful_results = [result for result in results if not result.get("error")]
    failed_results = [result for result in results if result.get("error")]
    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(results),
        "successful_case_count": len(successful_results),
        "failed_case_count": len(failed_results),
        "modes": {},
        "failed_cases": [
            {
                "case_id": result.get("case_id"),
                "error": result.get("error"),
            }
            for result in failed_results
        ],
    }

    for mode in MODES:
        evaluations = [
            result["evaluations"][mode]
            for result in successful_results
            if mode in result["evaluations"]
        ]
        summary["modes"][mode] = {
            "evaluated_case_count": len(evaluations),
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
    manifest: dict[str, Any],
    run_config: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results_json_path = output_dir / "raw_results.json"
    results_jsonl_path = output_dir / "raw_results.jsonl"
    summary_json_path = output_dir / "summary.json"
    summary_csv_path = output_dir / "summary.csv"
    manifest_path = output_dir / "manifest.json"
    run_config_path = output_dir / "run_config.json"

    results_json_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    results_jsonl_path.write_text(
        "".join(
            json.dumps(result, ensure_ascii=False) + "\n" for result in results
        ),
        encoding="utf-8",
    )
    summary_json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    run_config_path.write_text(
        json.dumps(run_config, indent=2, ensure_ascii=False),
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
                "evaluated_case_count",
                "average_groundedness",
                "average_unsupported_claim_rate",
                "average_citation_precision",
                "correct_refusal_rate",
                "average_claim_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def build_run_config(
    *,
    args: argparse.Namespace,
    experiment_config: dict[str, Any],
    dataset_hash: str,
    cases: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "runner_version": RUNNER_VERSION,
        "generated_at": generated_at,
        "base_url": args.base_url.rstrip("/"),
        "user_id": args.user_id,
        "course_id_override": args.course_id,
        "top_k": args.top_k,
        "timeout": args.timeout,
        "run_type": args.run_type,
        "case_limit": args.limit,
        "cases_path": str(args.cases),
        "config_path": str(args.config),
        "dataset_sha256": dataset_hash,
        "case_count": len(cases),
        "experiment_config": experiment_config,
    }


def build_manifest(
    *,
    run_id: str,
    generated_at: str,
    args: argparse.Namespace,
    dataset_hash: str,
    cases: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_type": args.run_type,
        "runner_version": RUNNER_VERSION,
        "timestamp": generated_at,
        "git_commit": git_commit_hash(),
        "dataset_path": str(args.cases),
        "dataset_sha256": dataset_hash,
        "config_path": str(args.config),
        "base_url": args.base_url.rstrip("/"),
        "user_id": args.user_id,
        "course_id_override": args.course_id,
        "retrieval_top_k": args.top_k,
        "case_count": len(cases),
        "successful_case_count": summary["successful_case_count"],
        "failed_case_count": summary["failed_case_count"],
        "conditions": list(MODES),
        "output_files": {
            "run_config": "run_config.json",
            "raw_results_json": "raw_results.json",
            "raw_results_jsonl": "raw_results.jsonl",
            "summary_json": "summary.json",
            "summary_csv": "summary.csv",
            "manifest": "manifest.json",
        },
    }


def create_run_dir(
    *,
    output_root: Path,
    run_type: str,
    run_id: str,
    explicit_run_id: bool,
) -> Path:
    run_type_dir = output_root / run_type
    candidate = run_type_dir / run_id
    if explicit_run_id:
        if candidate.exists():
            raise FileExistsError(f"Run directory already exists: {candidate}")
        candidate.mkdir(parents=True)
        return candidate

    if not candidate.exists():
        candidate.mkdir(parents=True)
        return candidate

    for suffix in range(1, 100):
        suffixed_candidate = run_type_dir / f"{run_id}_{suffix:02d}"
        if not suffixed_candidate.exists():
            suffixed_candidate.mkdir(parents=True)
            return suffixed_candidate

    raise FileExistsError(f"Could not create unique run directory for {run_id}")


def default_run_id(experiment_id: str, generated_at: str) -> str:
    timestamp = generated_at.replace("-", "").replace(":", "").split(".")[0]
    timestamp = timestamp.replace("T", "_")
    return f"{experiment_id}_{timestamp}"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit_hash() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip()


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
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
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
    parser.add_argument("--run-type", choices=("pilot", "formal"), default="pilot")
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of cases to run, useful for pilot dry runs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated_at = datetime.now(timezone.utc).isoformat()
    experiment_config = load_config(args.config)
    cases = load_cases(args.cases)
    if args.limit is not None:
        cases = cases[: args.limit]

    dataset_hash = file_sha256(args.cases)
    base_url = args.base_url.rstrip("/")
    experiment_id = str(experiment_config.get("experiment_id", "answer_eval"))
    run_id = args.run_id or default_run_id(experiment_id, generated_at)
    run_dir = create_run_dir(
        output_root=args.output_dir,
        run_type=args.run_type,
        run_id=run_id,
        explicit_run_id=args.run_id is not None,
    )

    with httpx.Client(timeout=args.timeout) as client:
        results = [
            run_case_safely(
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
    run_config = build_run_config(
        args=args,
        experiment_config=experiment_config,
        dataset_hash=dataset_hash,
        cases=cases,
        generated_at=generated_at,
    )
    manifest = build_manifest(
        run_id=run_dir.name,
        generated_at=generated_at,
        args=args,
        dataset_hash=dataset_hash,
        cases=cases,
        summary=summary,
    )
    write_outputs(
        output_dir=run_dir,
        results=results,
        summary=summary,
        manifest=manifest,
        run_config=run_config,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Saved evaluation run to {run_dir}")


if __name__ == "__main__":
    main()
