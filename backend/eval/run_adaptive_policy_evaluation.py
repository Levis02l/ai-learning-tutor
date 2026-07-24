from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter, sleep
from typing import Any, Iterator, Literal, cast
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine
from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import LLMProvider, LLMProviderError, LLMResponse
from app.models.document import Chunk, Document
from app.models.quiz import QuizItem
from app.services.concepts import ConceptLearnerState
from app.services.learner_state import LearnerState
from app.services.policy import (
    PolicyDecision,
    PolicyEvidenceState,
    decide_teaching_action,
)
from app.services.retrieval import RetrievedChunk
from app.services.tutor_response import TutorResponse, execute_tutor_decision
from eval.run_answer_evaluation import create_run_dir, file_sha256
from eval.validate_adaptive_policy_dataset import EvidenceFixture, ExpectedPolicy
from eval.validate_adaptive_policy_pilot import (
    DEFAULT_DATASET_PATH,
    AdaptivePolicyPilotDataset,
    PilotReviewFixture,
    PilotScenario,
    load_and_validate_pilot,
    verify_production_pilot_inputs,
)

DEFAULT_CONFIG_PATH = (
    Path(__file__).parent / "configs" / "adaptive_policy_v1.config.json"
)
DEFAULT_OUTPUT_ROOT = Path(__file__).parent / "results" / "adaptive_policy"
RUNNER_VERSION = "adaptive_eval_v1_b_pilot_1"
BASELINE_POLICY_VERSION = "intent_state_blind_v1"
GENERATION_ADAPTER_VERSION = "policy_treatment_only_v1"
Condition = Literal["adaptive", "baseline"]


@dataclass(frozen=True)
class _FrozenPolicyEvidence:
    evidence_strength: str
    source_coverage: float
    retrieved_chunk_count: int
    top_similarity: float | None
    requires_evidence: bool
    reason: str
    retrieval_scope: str
    source_chunk_ids: list[int]


class RecordingRetryProvider:
    def __init__(
        self,
        delegate: LLMProvider,
        *,
        max_retries: int,
        retry_initial_delay: float,
    ) -> None:
        self.delegate = delegate
        self.max_retries = max_retries
        self.retry_initial_delay = retry_initial_delay
        self.events: list[dict[str, Any]] = []
        self._case_id = ""
        self._condition: Condition = "adaptive"

    def set_context(self, *, case_id: str, condition: Condition) -> None:
        self._case_id = case_id
        self._condition = condition

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> LLMResponse:
        event_id = f"provider_call_{len(self.events) + 1:04d}"
        attempts: list[dict[str, Any]] = []
        started = perf_counter()
        for attempt_index in range(self.max_retries + 1):
            try:
                response = self.delegate.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                attempts.append(
                    {
                        "attempt": attempt_index + 1,
                        "status": "success",
                        "error": None,
                    }
                )
                self.events.append(
                    {
                        "event_id": event_id,
                        "case_id": self._case_id,
                        "condition": self._condition,
                        "system_prompt_sha256": _text_sha256(system_prompt),
                        "user_prompt_sha256": _text_sha256(user_prompt),
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "attempts": attempts,
                        "retry_count": attempt_index,
                        "latency_seconds": round(
                            perf_counter() - started,
                            3,
                        ),
                        "raw_response": response.text,
                        "error": None,
                    }
                )
                return response
            except LLMProviderError as exc:
                attempts.append(
                    {
                        "attempt": attempt_index + 1,
                        "status": "error",
                        "error": {
                            "type": type(exc).__name__,
                            "message": str(exc),
                        },
                    }
                )
                if attempt_index >= self.max_retries:
                    self.events.append(
                        {
                            "event_id": event_id,
                            "case_id": self._case_id,
                            "condition": self._condition,
                            "system_prompt_sha256": _text_sha256(system_prompt),
                            "user_prompt_sha256": _text_sha256(user_prompt),
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                            "attempts": attempts,
                            "retry_count": attempt_index,
                            "latency_seconds": round(
                                perf_counter() - started,
                                3,
                            ),
                            "raw_response": None,
                            "error": attempts[-1]["error"],
                        }
                    )
                    raise
                delay = self.retry_initial_delay * (2**attempt_index)
                if delay > 0:
                    sleep(delay)

        raise RuntimeError("Unreachable provider retry state")


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError("Adaptive evaluation config must be a JSON object")
    return payload


def build_adaptive_decision(
    *,
    dataset: AdaptivePolicyPilotDataset,
    scenario: PilotScenario,
    chunks: list[RetrievedChunk],
) -> PolicyDecision:
    learner_state, concept_state = _materialize_learner_state(
        dataset=dataset,
        scenario=scenario,
    )
    fixture = _fixture_for(dataset=dataset, scenario=scenario)
    if scenario.review_fixture_id is not None:
        evidence = _FrozenPolicyEvidence(
            evidence_strength="not_required",
            source_coverage=1.0,
            retrieved_chunk_count=0,
            top_similarity=0.0,
            requires_evidence=False,
            reason=(
                "The evaluation-only frozen review item is already "
                "source-traceable, so new retrieval is not required."
            ),
            retrieval_scope="not_required",
            source_chunk_ids=[],
        )
        decision_chunks: list[RetrievedChunk] = []
    else:
        evidence = _frozen_sufficient_evidence(
            fixture=fixture,
            chunks=chunks,
        )
        decision_chunks = chunks
    decision = decide_teaching_action(
        query=scenario.question,
        user_id=dataset.course.user_id,
        course_id=dataset.course.course_id,
        learner_state=learner_state,
        evidence_state=cast(PolicyEvidenceState, evidence),
        detected_intent=scenario.detected_intent,
        learner_state_scope="concept",
        concept_state=concept_state,
        misconception_snapshot=None,
        evidence_chunks=decision_chunks,
    )
    _assert_policy_matches(
        decision=decision,
        expected=scenario.expected_adaptive_policy,
        label=f"{scenario.case_id} Adaptive",
    )
    return decision


def build_baseline_decision(
    *,
    adaptive_decision: PolicyDecision,
    dataset: AdaptivePolicyPilotDataset,
    scenario: PilotScenario,
    chunks: list[RetrievedChunk],
) -> PolicyDecision:
    expected = scenario.expected_baseline_policy
    fixture = _fixture_for(dataset=dataset, scenario=scenario)
    baseline_evidence = _frozen_sufficient_evidence(
        fixture=fixture,
        chunks=chunks,
    )
    identical_policy = expected == scenario.expected_adaptive_policy
    if identical_policy:
        decision = replace(
            adaptive_decision,
            decision_id=None,
            policy_version=BASELINE_POLICY_VERSION,
        )
    else:
        decision = replace(
            adaptive_decision,
            decision_id=None,
            selected_action=expected.selected_action,
            response_strategy=expected.response_strategy,
            primary_reason="intent_aware_state_blind_baseline",
            teaching_reason=(
                "The intent-aware baseline follows its frozen pedagogical "
                "mapping without using learner mastery, recent performance, "
                "consecutive errors, or review-due status to select the action "
                "or response strategy."
            ),
            suggested_next_step=_baseline_next_step(expected),
            policy_version=BASELINE_POLICY_VERSION,
            evidence_state_snapshot=asdict(baseline_evidence),
            evidence_chunks=chunks,
        )
    _assert_policy_matches(
        decision=decision,
        expected=expected,
        label=f"{scenario.case_id} Baseline",
    )
    return decision


def build_generation_decision(decision: PolicyDecision) -> PolicyDecision:
    concept_snapshot = decision.concept_state_snapshot
    generation_concept_snapshot = (
        {
            "concept_id": concept_snapshot["concept_id"],
            "concept_name": concept_snapshot["concept_name"],
            "state_status": concept_snapshot["state_status"],
            "learner_performance": "withheld_by_evaluation_adapter",
        }
        if concept_snapshot is not None
        else None
    )
    return replace(
        decision,
        decision_id=None,
        primary_reason="evaluation_policy_treatment",
        teaching_reason=_generation_teaching_reason(decision),
        learner_state_snapshot={
            "learner_performance": "withheld_by_evaluation_adapter",
        },
        concept_state_snapshot=generation_concept_snapshot,
        misconception_snapshot=None,
    )


def run_scenario(
    *,
    dataset: AdaptivePolicyPilotDataset,
    scenario: PilotScenario,
    provider: RecordingRetryProvider,
) -> dict[str, Any]:
    started = perf_counter()
    fixture = _fixture_for(dataset=dataset, scenario=scenario)
    with rollback_only_session() as db:
        chunks = load_frozen_chunks(
            db=db,
            dataset=dataset,
            fixture=fixture,
        )
        adaptive = build_adaptive_decision(
            dataset=dataset,
            scenario=scenario,
            chunks=chunks,
        )
        baseline = build_baseline_decision(
            adaptive_decision=adaptive,
            dataset=dataset,
            scenario=scenario,
            chunks=chunks,
        )
        review_fixture = _review_fixture_for(
            dataset=dataset,
            scenario=scenario,
        )
        identical_policy = (
            scenario.expected_adaptive_policy
            == scenario.expected_baseline_policy
        )
        if identical_policy and not _generation_inputs_match(
            adaptive=adaptive,
            baseline=baseline,
        ):
            raise ValueError(
                f"{scenario.case_id} is marked for reuse but effective "
                "generation inputs differ"
            )

        adaptive_artifact = _execute_condition_safely(
            db=db,
            case_id=scenario.case_id,
            condition="adaptive",
            decision=adaptive,
            fixture=fixture,
            review_fixture=review_fixture,
            provider=provider,
        )
        if identical_policy:
            baseline_artifact = _reuse_condition_artifact(
                source=adaptive_artifact,
                condition="baseline",
                decision=baseline,
            )
        else:
            baseline_artifact = _execute_condition_safely(
                db=db,
                case_id=scenario.case_id,
                condition="baseline",
                decision=baseline,
                fixture=fixture,
                review_fixture=None,
                provider=provider,
            )

    return {
        "case_id": scenario.case_id,
        "group_id": scenario.group_id,
        "scenario_position": scenario.scenario_position,
        "question": scenario.question,
        "learner_state": scenario.learner_state.model_dump(mode="json"),
        "learner_vignette": scenario.annotation_context.learner_vignette,
        "concept": scenario.concept.model_dump(mode="json"),
        "evidence_fixture_id": scenario.evidence_fixture_id,
        "review_fixture_id": scenario.review_fixture_id,
        "identical_policy_control": identical_policy,
        "conditions": {
            "adaptive": adaptive_artifact,
            "baseline": baseline_artifact,
        },
        "latency_seconds": round(perf_counter() - started, 3),
        "error": _condition_error(
            adaptive=adaptive_artifact,
            baseline=baseline_artifact,
        ),
    }


def load_frozen_chunks(
    *,
    db: Session,
    dataset: AdaptivePolicyPilotDataset,
    fixture: EvidenceFixture,
) -> list[RetrievedChunk]:
    expected_ids = [chunk.chunk_id for chunk in fixture.ordered_chunks]
    rows = db.execute(
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.id.in_(expected_ids),
            Document.id == dataset.course.document_id,
            Document.course_id == dataset.course.course_id,
            Document.user_id == dataset.course.user_id,
        )
    ).all()
    by_id = {chunk.id: (chunk, document) for chunk, document in rows}
    if set(by_id) != set(expected_ids):
        raise ValueError(f"{fixture.fixture_id} contains unavailable chunks")

    materialized: list[RetrievedChunk] = []
    for expected in fixture.ordered_chunks:
        chunk, document = by_id[expected.chunk_id]
        actual_hash = _text_sha256(chunk.content)
        if actual_hash != expected.content_sha256:
            raise ValueError(f"Chunk {chunk.id} content hash changed")
        if chunk.chunk_metadata.get("chunk_index") != expected.chunk_index:
            raise ValueError(f"Chunk {chunk.id} index changed")
        materialized.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=document.id,
                course_id=document.course_id,
                filename=document.filename,
                content=chunk.content,
                metadata={
                    **chunk.chunk_metadata,
                    "evaluation_provenance": (
                        "human_audited_frozen_fixture"
                    ),
                    "live_similarity_measured": False,
                },
                distance=cast(float, None),
                similarity=cast(float, None),
            )
        )
    return materialized


@contextmanager
def rollback_only_session(
    bind_engine: Engine = engine,
) -> Iterator[Session]:
    connection = bind_engine.connect()
    outer_transaction = connection.begin()
    db = Session(
        bind=connection,
        join_transaction_mode="rollback_only",
    )
    try:
        yield db
    finally:
        db.close()
        if outer_transaction.is_active:
            outer_transaction.rollback()
        connection.close()


def run_pilot(
    *,
    dataset: AdaptivePolicyPilotDataset,
    provider: RecordingRetryProvider,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for scenario in dataset.scenarios:
        try:
            results.append(
                run_scenario(
                    dataset=dataset,
                    scenario=scenario,
                    provider=provider,
                )
            )
        except Exception as exc:
            results.append(
                {
                    "case_id": scenario.case_id,
                    "group_id": scenario.group_id,
                    "scenario_position": scenario.scenario_position,
                    "question": scenario.question,
                    "learner_state": scenario.learner_state.model_dump(
                        mode="json"
                    ),
                    "learner_vignette": (
                        scenario.annotation_context.learner_vignette
                    ),
                    "concept": scenario.concept.model_dump(mode="json"),
                    "evidence_fixture_id": scenario.evidence_fixture_id,
                    "review_fixture_id": scenario.review_fixture_id,
                    "identical_policy_control": (
                        scenario.expected_adaptive_policy
                        == scenario.expected_baseline_policy
                    ),
                    "conditions": {},
                    "latency_seconds": None,
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                }
            )
    return results


def write_run_artifacts(
    *,
    output_dir: Path,
    dataset: AdaptivePolicyPilotDataset,
    config: dict[str, Any],
    dataset_path: Path,
    config_path: Path,
    results: list[dict[str, Any]],
    provider_events: list[dict[str, Any]],
    run_id: str,
    git_commit: str,
    git_clean: bool,
    effective_max_retries: int,
    effective_retry_initial_delay: float,
) -> None:
    dataset_hash = file_sha256(dataset_path)
    config_hash = file_sha256(config_path)
    generated_at = datetime.now(timezone.utc).isoformat()
    blinded_pairs, reveal_key = build_blinded_artifacts(
        results=results,
        seed=str(config["blinding"]["seed"]),
    )
    adaptive_as_a_count = sum(
        1 for entry in reveal_key if entry["A"] == "adaptive"
    )
    failed_cases = [
        result["case_id"] for result in results if result.get("error")
    ]
    canonical_execution_count = _canonical_execution_count(results)
    expected_canonical_execution_count = (
        dataset.topology.planned_canonical_response_execution_count
    )
    provider_event_count = len(provider_events)
    expected_provider_event_count = (
        dataset.topology.expected_successful_provider_generation_count
    )
    manifest = {
        "run_id": run_id,
        "run_type": "pilot",
        "runner_version": RUNNER_VERSION,
        "generation_adapter_version": GENERATION_ADAPTER_VERSION,
        "generated_at": generated_at,
        "git_commit": git_commit,
        "git": {
            "commit": git_commit,
            "clean": git_clean,
        },
        "dataset_path": str(dataset_path),
        "dataset_sha256": dataset_hash,
        "config_path": str(config_path),
        "config_sha256": config_hash,
        "formal_candidate_lock": dataset.formal_candidate_lock.model_dump(),
        "model": {
            "provider": "openai",
            "name": settings.openai_chat_model,
        },
        "embedding_model": settings.openai_embedding_model,
        "effective_generation_runtime": {
            "max_retries": effective_max_retries,
            "retry_initial_delay_seconds": (
                effective_retry_initial_delay
            ),
        },
        "blinding": {
            "algorithm": config["blinding"]["algorithm"],
            "seed": config["blinding"]["seed"],
            "eligible_pair_count": len(reveal_key),
            "adaptive_as_a_count": adaptive_as_a_count,
            "adaptive_as_b_count": len(reveal_key) - adaptive_as_a_count,
        },
        "condition_artifact_count": sum(
            len(result.get("conditions", {})) for result in results
        ),
        "canonical_response_execution_count": canonical_execution_count,
        "expected_canonical_response_execution_count": (
            expected_canonical_execution_count
        ),
        "canonical_response_execution_count_matches_plan": (
            canonical_execution_count == expected_canonical_execution_count
        ),
        "provider_event_count": provider_event_count,
        "expected_provider_event_count_before_retries": (
            expected_provider_event_count
        ),
        "provider_event_count_matches_plan": (
            provider_event_count == expected_provider_event_count
        ),
        "provider_attempt_count": sum(
            len(event["attempts"]) for event in provider_events
        ),
        "successful_case_count": len(results) - len(failed_cases),
        "failed_case_count": len(failed_cases),
        "failed_cases": failed_cases,
        "output_files": {
            "raw_results": "raw_results.json",
            "raw_results_jsonl": "raw_results.jsonl",
            "provider_events": "provider_events.json",
            "manifest": "manifest.json",
            "run_config": "run_config.json",
            "blinded_pairs": "blinded_pairs.json",
            "reveal_key": "reveal_key.json",
        },
    }
    run_config = {
        **config,
        "runtime": {
            "run_id": run_id,
            "run_type": "pilot",
            "dataset_path": str(dataset_path),
            "dataset_sha256": dataset_hash,
            "config_sha256": config_hash,
            "git_commit": git_commit,
            "git_clean": git_clean,
            "model_name": settings.openai_chat_model,
            "embedding_model": settings.openai_embedding_model,
            "effective_generation_runtime": {
                "max_retries": effective_max_retries,
                "retry_initial_delay_seconds": (
                    effective_retry_initial_delay
                ),
            },
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "raw_results.json", results)
    (output_dir / "raw_results.jsonl").write_text(
        "".join(
            json.dumps(result, ensure_ascii=False) + "\n"
            for result in results
        ),
        encoding="utf-8",
    )
    _write_json(output_dir / "provider_events.json", provider_events)
    _write_json(output_dir / "manifest.json", manifest)
    _write_json(output_dir / "run_config.json", run_config)
    _write_json(output_dir / "blinded_pairs.json", blinded_pairs)
    _write_json(output_dir / "reveal_key.json", reveal_key)


def build_blinded_artifacts(
    *,
    results: list[dict[str, Any]],
    seed: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blinded: list[dict[str, Any]] = []
    reveal: list[dict[str, Any]] = []
    eligible_case_ids = sorted(
        result["case_id"]
        for result in results
        if set(result.get("conditions", {})) == {"adaptive", "baseline"}
    )
    if len(eligible_case_ids) != len(set(eligible_case_ids)):
        raise ValueError("Blinding requires unique case IDs")
    randomizer = random.Random(seed)
    randomizer.shuffle(eligible_case_ids)
    adaptive_as_a = set(eligible_case_ids[: len(eligible_case_ids) // 2])

    for result in results:
        conditions = result.get("conditions", {})
        if set(conditions) != {"adaptive", "baseline"}:
            continue
        adaptive = conditions["adaptive"]
        baseline = conditions["baseline"]
        adaptive_is_a = result["case_id"] in adaptive_as_a
        mapping = (
            {"A": "adaptive", "B": "baseline"}
            if adaptive_is_a
            else {"A": "baseline", "B": "adaptive"}
        )
        by_condition = {
            "adaptive": adaptive,
            "baseline": baseline,
        }
        blinded.append(
            {
                "case_id": result["case_id"],
                "group_id": result["group_id"],
                "learner_vignette": result["learner_vignette"],
                "question": result["question"],
                "response_A": _annotation_response_view(
                    by_condition[mapping["A"]]
                ),
                "response_B": _annotation_response_view(
                    by_condition[mapping["B"]]
                ),
                "pairwise_preference": "",
                "response_A_pedagogical_appropriateness": "",
                "response_B_pedagogical_appropriateness": "",
                "response_A_learner_state_tailoring": "",
                "response_B_learner_state_tailoring": "",
                "response_A_intent_fidelity": "",
                "response_B_intent_fidelity": "",
                "response_A_response_relevance": "",
                "response_B_response_relevance": "",
                "annotation_notes": "",
            }
        )
        reveal.append(
            {
                "case_id": result["case_id"],
                "A": mapping["A"],
                "B": mapping["B"],
                "structural_identical_policy_control": result[
                    "identical_policy_control"
                ],
            }
        )
    return blinded, reveal


def _execute_condition_safely(
    *,
    db: Session,
    case_id: str,
    condition: Condition,
    decision: PolicyDecision,
    fixture: EvidenceFixture,
    review_fixture: PilotReviewFixture | None,
    provider: RecordingRetryProvider,
) -> dict[str, Any]:
    if decision.selected_action == "review":
        if review_fixture is None:
            raise ValueError(f"{case_id} review action lacks frozen fixture")
        if decision.evidence_state_snapshot["evidence_strength"] != "not_required":
            raise ValueError("Evaluation review must use frozen review evidence")

    provider.set_context(case_id=case_id, condition=condition)
    event_start = len(provider.events)
    started = perf_counter()
    execution_id = f"{case_id}_{condition}_execution"
    generation_decision = build_generation_decision(decision)
    try:
        with _frozen_review_queue(
            decision=generation_decision,
            review_fixture=review_fixture,
        ):
            response = execute_tutor_decision(
                db=db,
                decision=generation_decision,
                top_k=len(fixture.ordered_chunks),
                llm_provider=provider,
            )
        return {
            "condition": condition,
            "generation_execution_id": execution_id,
            "reused_generation": False,
            "canonical_condition": condition,
            "decision": serialize_decision(decision),
            "generation_decision": serialize_decision(generation_decision),
            "response": serialize_response(response),
            "provider_event_ids": [
                event["event_id"] for event in provider.events[event_start:]
            ],
            "latency_seconds": round(perf_counter() - started, 3),
            "error": None,
        }
    except Exception as exc:
        return {
            "condition": condition,
            "generation_execution_id": execution_id,
            "reused_generation": False,
            "canonical_condition": condition,
            "decision": serialize_decision(decision),
            "generation_decision": serialize_decision(generation_decision),
            "response": None,
            "provider_event_ids": [
                event["event_id"] for event in provider.events[event_start:]
            ],
            "latency_seconds": round(perf_counter() - started, 3),
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }


def _reuse_condition_artifact(
    *,
    source: dict[str, Any],
    condition: Condition,
    decision: PolicyDecision,
) -> dict[str, Any]:
    artifact = json.loads(json.dumps(source, ensure_ascii=False))
    artifact["condition"] = condition
    artifact["reused_generation"] = True
    artifact["canonical_condition"] = source["condition"]
    artifact["decision"] = serialize_decision(decision)
    artifact["generation_decision"] = serialize_decision(
        build_generation_decision(decision)
    )
    return artifact


def serialize_decision(decision: PolicyDecision) -> dict[str, Any]:
    return {
        "decision_id": decision.decision_id,
        "user_id": decision.user_id,
        "course_id": decision.course_id,
        "query": decision.query,
        "detected_intent": decision.detected_intent,
        "selected_action": decision.selected_action,
        "response_strategy": decision.response_strategy,
        "primary_reason": decision.primary_reason,
        "teaching_reason": decision.teaching_reason,
        "suggested_next_step": decision.suggested_next_step,
        "policy_version": decision.policy_version,
        "learner_state_snapshot": decision.learner_state_snapshot,
        "evidence_state_snapshot": decision.evidence_state_snapshot,
        "learner_state_scope": decision.learner_state_scope,
        "concept_state_snapshot": decision.concept_state_snapshot,
        "misconception_snapshot": decision.misconception_snapshot,
        "evidence_chunk_ids": [
            chunk.chunk_id for chunk in decision.evidence_chunks
        ],
    }


def serialize_response(response: TutorResponse) -> dict[str, Any]:
    return {
        "answer_status": response.answer_status,
        "answer": response.answer,
        "claims": [asdict(claim) for claim in response.claims],
        "sources": [asdict(source) for source in response.sources],
        "quiz_items": [
            {
                "id": item.id,
                "question": item.question,
                "answer": item.answer,
                "difficulty": item.difficulty,
                "origin": item.origin,
                "source_chunk_ids": item.source_chunk_ids,
                "evidence_quote": item.evidence_quote,
                "options": item.options,
                "correct_option_id": item.correct_option_id,
                "explanation": item.explanation,
                "question_type": item.question_type,
                "traceability_label": item.traceability_label,
                "concept_id": item.concept_id,
            }
            for item in response.quiz_items
        ],
        "review_items": [
            {
                "quiz_item_id": item.id,
                "question": item.question,
                "review_record_id": record.id if record is not None else None,
            }
            for item, record in response.review_items
        ],
        "suggested_next_step": response.suggested_next_step,
    }


def _materialize_learner_state(
    *,
    dataset: AdaptivePolicyPilotDataset,
    scenario: PilotScenario,
) -> tuple[LearnerState, ConceptLearnerState]:
    state = scenario.learner_state
    learner = LearnerState(
        user_id=dataset.course.user_id,
        course_id=dataset.course.course_id,
        mastery_score=state.mastery_score,
        recent_accuracy=state.recent_accuracy,
        attempt_count=state.attempt_count,
        consecutive_errors=state.consecutive_errors,
        last_reviewed_at=None,
        review_due=state.review_due,
    )
    concept = ConceptLearnerState(
        concept_id=scenario.concept.concept_id,
        concept_name=scenario.concept.name,
        state_status="observed",
        mastery_score=state.mastery_score,
        recent_accuracy=state.recent_accuracy,
        attempt_count=state.attempt_count,
        consecutive_errors=state.consecutive_errors,
        last_attempted_at=None,
        review_due=state.review_due,
        needs_attention=state.mastery_score < 0.4,
    )
    return learner, concept


def _frozen_sufficient_evidence(
    *,
    fixture: EvidenceFixture,
    chunks: list[RetrievedChunk],
) -> _FrozenPolicyEvidence:
    return _FrozenPolicyEvidence(
        evidence_strength=fixture.evidence_state.evidence_strength,
        source_coverage=fixture.evidence_state.source_coverage,
        retrieved_chunk_count=fixture.evidence_state.retrieved_chunk_count,
        top_similarity=None,
        requires_evidence=fixture.evidence_state.requires_evidence,
        reason="Human-audited frozen pilot evidence fixture.",
        retrieval_scope=fixture.evidence_state.retrieval_scope,
        source_chunk_ids=[chunk.chunk_id for chunk in chunks],
    )


def _fixture_for(
    *,
    dataset: AdaptivePolicyPilotDataset,
    scenario: PilotScenario,
) -> EvidenceFixture:
    return next(
        fixture
        for fixture in dataset.evidence_fixtures
        if fixture.fixture_id == scenario.evidence_fixture_id
    )


def _review_fixture_for(
    *,
    dataset: AdaptivePolicyPilotDataset,
    scenario: PilotScenario,
) -> PilotReviewFixture | None:
    if scenario.review_fixture_id is None:
        return None
    return next(
        fixture
        for fixture in dataset.review_fixtures
        if fixture.fixture_id == scenario.review_fixture_id
    )


@contextmanager
def _frozen_review_queue(
    *,
    decision: PolicyDecision,
    review_fixture: PilotReviewFixture | None,
) -> Iterator[None]:
    if decision.selected_action != "review":
        yield
        return
    if review_fixture is None:
        raise ValueError("Frozen review fixture is required")

    item = QuizItem(
        id=-review_fixture.concept_id,
        user_id=decision.user_id,
        course_id=decision.course_id,
        concept_id=review_fixture.concept_id,
        question=review_fixture.question,
        answer=review_fixture.reference_answer,
        difficulty="medium",
        origin=review_fixture.origin,
        source_chunk_ids=review_fixture.source_chunk_ids,
        evidence_quote="",
        options=[],
        correct_option_id=None,
        explanation=review_fixture.reference_answer,
        question_type="conceptual",
        traceability_label="fully_traceable",
    )
    with patch(
        "app.services.tutor_response.get_due_review_items",
        return_value=[(item, None)],
    ):
        yield


def _assert_policy_matches(
    *,
    decision: PolicyDecision,
    expected: ExpectedPolicy,
    label: str,
) -> None:
    if (
        decision.selected_action != expected.selected_action
        or decision.response_strategy != expected.response_strategy
    ):
        raise ValueError(
            f"{label} produced {decision.selected_action}/"
            f"{decision.response_strategy}, expected "
            f"{expected.selected_action}/{expected.response_strategy}"
        )


def _generation_teaching_reason(decision: PolicyDecision) -> str:
    return (
        "Execute the registered "
        f"{decision.selected_action}/{decision.response_strategy} "
        "pedagogical treatment using the supplied course evidence."
    )


def _generation_inputs_match(
    *,
    adaptive: PolicyDecision,
    baseline: PolicyDecision,
) -> bool:
    return _generation_input_signature(
        build_generation_decision(adaptive)
    ) == _generation_input_signature(build_generation_decision(baseline))


def _generation_input_signature(
    decision: PolicyDecision,
) -> dict[str, Any]:
    return {
        "query": decision.query,
        "selected_action": decision.selected_action,
        "response_strategy": decision.response_strategy,
        "teaching_reason": decision.teaching_reason,
        "learner_state_snapshot": decision.learner_state_snapshot,
        "learner_state_scope": decision.learner_state_scope,
        "concept_state_snapshot": decision.concept_state_snapshot,
        "misconception_snapshot": decision.misconception_snapshot,
        "evidence_state_snapshot": decision.evidence_state_snapshot,
        "evidence_chunk_ids": [
            chunk.chunk_id for chunk in decision.evidence_chunks
        ],
    }


def _baseline_next_step(expected: ExpectedPolicy) -> str:
    if expected.selected_action == "quiz":
        return "Generate one source-grounded practice question."
    if expected.selected_action == "hint":
        return "Offer one source-grounded hint and invite another attempt."
    if expected.selected_action == "review":
        return "Provide one short source-grounded review drill."
    return "Provide a source-grounded guided explanation."


def _annotation_response_view(artifact: dict[str, Any]) -> dict[str, Any] | None:
    response = artifact.get("response")
    if response is None:
        return None
    return {
        "answer_status": response["answer_status"],
        "answer": response["answer"],
        "quiz_items": [
            {
                "question": item["question"],
                "options": item["options"],
            }
            for item in response.get("quiz_items", [])
        ],
        "review_items": [
            {
                "question": item["question"],
            }
            for item in response.get("review_items", [])
        ],
        "suggested_next_step": response["suggested_next_step"],
    }


def _canonical_execution_count(results: list[dict[str, Any]]) -> int:
    execution_ids = {
        artifact["generation_execution_id"]
        for result in results
        for artifact in result.get("conditions", {}).values()
        if artifact.get("generation_execution_id")
    }
    return len(execution_ids)


def _condition_error(
    *,
    adaptive: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any] | None:
    errors = {
        condition: artifact["error"]
        for condition, artifact in {
            "adaptive": adaptive,
            "baseline": baseline,
        }.items()
        if artifact.get("error")
    }
    if not errors:
        return None
    return {
        "type": "ConditionExecutionError",
        "conditions": errors,
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def git_commit_hash() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        check=False,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def git_worktree_is_clean() -> bool:
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Unable to inspect Git worktree status")
    return not result.stdout.strip()


def _default_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"adaptive_policy_v1_pilot_{timestamp}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the isolated V1-B adaptive-policy pilot."
    )
    parser.add_argument(
        "--run-type",
        choices=["pilot", "formal"],
        default="pilot",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id")
    parser.add_argument("--max-retries", type=int)
    parser.add_argument("--retry-initial-delay", type=float)
    parser.add_argument(
        "--confirm-pilot-generation",
        action="store_true",
        help="Required explicit guard before any model-generation call.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.run_type != "pilot":
        raise ValueError(
            "Formal V1-B execution is disabled until the final formal freeze"
        )
    if not args.confirm_pilot_generation:
        raise ValueError(
            "Pilot model generation requires --confirm-pilot-generation"
        )

    dataset = load_and_validate_pilot(args.dataset)
    config = load_config(args.config)
    with rollback_only_session() as db:
        verify_production_pilot_inputs(dataset, db)

    git_commit = git_commit_hash()
    git_clean = git_worktree_is_clean()
    if not git_clean:
        raise ValueError(
            "Pilot generation requires a clean Git worktree"
        )
    run_id = args.run_id or _default_run_id()
    output_dir = create_run_dir(
        output_root=args.output_root,
        run_type="pilot",
        run_id=run_id,
        explicit_run_id=args.run_id is not None,
    )
    generation_config = config["generation"]
    max_retries = (
        args.max_retries
        if args.max_retries is not None
        else int(generation_config["max_retries"])
    )
    retry_delay = (
        args.retry_initial_delay
        if args.retry_initial_delay is not None
        else float(generation_config["retry_initial_delay_seconds"])
    )
    provider = RecordingRetryProvider(
        OpenAIProvider(),
        max_retries=max_retries,
        retry_initial_delay=retry_delay,
    )
    results = run_pilot(
        dataset=dataset,
        provider=provider,
    )
    write_run_artifacts(
        output_dir=output_dir,
        dataset=dataset,
        config=config,
        dataset_path=args.dataset,
        config_path=args.config,
        results=results,
        provider_events=provider.events,
        run_id=run_id,
        git_commit=git_commit,
        git_clean=git_clean,
        effective_max_retries=max_retries,
        effective_retry_initial_delay=retry_delay,
    )
    print(f"Wrote V1-B pilot artifacts to {output_dir}")


if __name__ == "__main__":
    main()
