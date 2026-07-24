from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self, cast

from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Chunk, Document
from app.services.concepts import (
    ConceptLearnerState,
    get_concept_quiz_chunks,
    resolve_concept_for_focus,
)
from app.services.learner_state import LearnerState
from app.services.policy import (
    DetectedIntent,
    PolicyEvidenceState,
    decide_teaching_action,
    detect_intent,
)
from eval.validate_adaptive_policy_dataset import (
    AnnotationContext,
    ConceptRegistryEntry,
    CourseDefinition,
    EvidenceFixture,
    ExpectedPolicy,
    LearnerStateDefinition,
    PolicyDefinition,
    ReviewFixture,
    ScenarioConcept,
)

DEFAULT_DATASET_PATH = (
    Path(__file__).parent / "datasets" / "adaptive_policy_v1_pilot.json"
)
DEFAULT_SCHEMA_PATH = (
    Path(__file__).parent / "datasets" / "adaptive_policy_v1_pilot.schema.json"
)
FORMAL_CANDIDATE_PATH = (
    Path(__file__).parent
    / "datasets"
    / "adaptive_policy_v1_formal_candidate.json"
)

EXPECTED_GROUP_POSITIONS = {
    "P01": {"low", "medium"},
    "P02": {"medium", "high"},
    "P03": {"review_false", "review_true"},
    "P04": {"low", "high"},
}
EXPECTED_GROUP_TYPES = {
    "P01": "pilot_state_pair",
    "P02": "pilot_state_pair",
    "P03": "pilot_review_due_pair",
    "P04": "pilot_intent_fidelity_pair",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FormalCandidateLock(StrictModel):
    commit: Literal["7ab5be7923e1cd1a8d9b85b8432278f855c588a2"]
    dataset_sha256: Literal[
        "3221a85d87ebb788a603e93d3e48343edaf02d2c1595a3574558c4be30bf36db"
    ]
    rule: Literal["no_model_generation_or_development_testing"]


class PilotTopology(StrictModel):
    group_count: int
    scenario_count: int
    adaptive_baseline_comparisons: int
    condition_artifact_count: int
    identical_policy_scenarios: int
    planned_canonical_response_execution_count: int
    expected_successful_provider_generation_count: int


class PilotGenerationControl(StrictModel):
    identical_policy_handling: Literal["single_generation_reuse"]
    identical_policy_case_ids: list[str]
    condition_artifact_count: int
    planned_canonical_response_execution_count: int
    expected_successful_provider_generation_count: int
    provider_call_accounting_note: str


class PilotReviewFixture(ReviewFixture):
    fixture_sha256: str


class PilotScenario(StrictModel):
    case_id: str
    group_id: Literal["P01", "P02", "P03", "P04"]
    group_type: Literal[
        "pilot_state_pair",
        "pilot_review_due_pair",
        "pilot_intent_fidelity_pair",
    ]
    scenario_position: str
    course_id: int
    question: str
    concept: ScenarioConcept
    detected_intent: DetectedIntent
    counterfactual_dimension: Literal["learner_state_profile", "review_due"]
    learner_state: LearnerStateDefinition
    misconception: None
    evidence_fixture_id: str
    review_fixture_id: str | None = None
    expected_adaptive_policy: ExpectedPolicy
    expected_baseline_policy: ExpectedPolicy
    annotation_context: AnnotationContext


class AdaptivePolicyPilotDataset(StrictModel):
    schema_version: Literal["adaptive_policy_v1_pilot_1.0"]
    dataset_id: Literal["adaptive_policy_v1_pilot"]
    status: Literal["development_pilot_not_formal"]
    created_date: str
    formal_candidate_lock: FormalCandidateLock
    course: CourseDefinition
    policy: PolicyDefinition
    topology: PilotTopology
    generation_control: PilotGenerationControl
    learner_profiles: dict[
        Literal["low", "medium", "high"],
        LearnerStateDefinition,
    ]
    concept_registry: list[ConceptRegistryEntry]
    evidence_fixtures: list[EvidenceFixture]
    review_fixtures: list[PilotReviewFixture]
    scenarios: list[PilotScenario]

    @model_validator(mode="after")
    def validate_experiment_invariants(self) -> Self:
        _validate_topology(self)
        _validate_references(self)
        _validate_group_invariants(self)
        _validate_expected_policies(self)
        _validate_generation_control(self)
        _validate_fixture_hashes(self)
        return self


@dataclass(frozen=True)
class _FrozenPolicyEvidence:
    evidence_strength: str
    source_coverage: float
    retrieved_chunk_count: int
    top_similarity: None
    requires_evidence: bool
    reason: str
    retrieval_scope: str
    source_chunk_ids: list[int]


def load_and_validate_pilot(
    path: Path = DEFAULT_DATASET_PATH,
) -> AdaptivePolicyPilotDataset:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    dataset = AdaptivePolicyPilotDataset.model_validate(payload)
    _validate_formal_isolation(dataset)
    return dataset


def write_json_schema(path: Path = DEFAULT_SCHEMA_PATH) -> None:
    path.write_text(
        json.dumps(
            AdaptivePolicyPilotDataset.model_json_schema(),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def verify_production_pilot_inputs(
    dataset: AdaptivePolicyPilotDataset,
    db: Session,
) -> None:
    fixtures = {
        fixture.fixture_id: fixture for fixture in dataset.evidence_fixtures
    }
    grouped = _group_scenarios(dataset.scenarios)
    for group_id, scenarios in sorted(grouped.items()):
        scenario = scenarios[0]
        resolved = resolve_concept_for_focus(
            db,
            user_id=dataset.course.user_id,
            course_id=dataset.course.course_id,
            focus=scenario.question,
        )
        if resolved is None:
            raise ValueError(f"{group_id} did not resolve to a production concept")
        if (
            resolved.concept.id != scenario.concept.concept_id
            or resolved.concept.name != scenario.concept.name
        ):
            raise ValueError(f"{group_id} production concept resolution changed")
        if round(resolved.confidence, 3) != scenario.concept.resolver_confidence:
            raise ValueError(f"{group_id} production resolver confidence changed")
        if resolved.reason != scenario.concept.resolver_reason:
            raise ValueError(f"{group_id} production resolver reason changed")

        fixture = fixtures[scenario.evidence_fixture_id]
        _verify_fixture_chunks(
            db=db,
            dataset=dataset,
            fixture=fixture,
        )

    quiz_scenarios = [
        scenario
        for scenario in dataset.scenarios
        if scenario.expected_adaptive_policy.selected_action == "quiz"
        or scenario.expected_baseline_policy.selected_action == "quiz"
    ]
    for scenario in quiz_scenarios:
        fixture = fixtures[scenario.evidence_fixture_id]
        production_chunks = get_concept_quiz_chunks(
            db=db,
            user_id=dataset.course.user_id,
            course_id=dataset.course.course_id,
            concept_id=scenario.concept.concept_id,
            limit=len(fixture.ordered_chunks),
        )
        expected_ids = [chunk.chunk_id for chunk in fixture.ordered_chunks]
        actual_ids = [chunk.chunk_id for chunk in production_chunks]
        if actual_ids != expected_ids:
            raise ValueError(
                f"{scenario.case_id} quiz path uses {actual_ids}, "
                f"not frozen fixture {expected_ids}"
            )


def _validate_topology(dataset: AdaptivePolicyPilotDataset) -> None:
    scenarios = dataset.scenarios
    case_ids = [scenario.case_id for scenario in scenarios]
    if len(scenarios) != 8 or len(set(case_ids)) != 8:
        raise ValueError("Pilot must contain 8 unique scenario instances")

    grouped = _group_scenarios(scenarios)
    if set(grouped) != set(EXPECTED_GROUP_POSITIONS):
        raise ValueError("Pilot must contain exactly P01 through P04")

    expected_counts = {
        "group_count": 4,
        "scenario_count": 8,
        "adaptive_baseline_comparisons": 8,
        "condition_artifact_count": 16,
        "identical_policy_scenarios": 1,
    }
    for field_name, expected in expected_counts.items():
        if getattr(dataset.topology, field_name) != expected:
            raise ValueError(f"topology.{field_name} must be {expected}")

    for group_id, expected_positions in EXPECTED_GROUP_POSITIONS.items():
        positions = {scenario.scenario_position for scenario in grouped[group_id]}
        if positions != expected_positions:
            raise ValueError(
                f"{group_id} positions must be {sorted(expected_positions)}"
            )
        if {scenario.group_type for scenario in grouped[group_id]} != {
            EXPECTED_GROUP_TYPES[group_id]
        }:
            raise ValueError(f"{group_id} has the wrong group_type")


def _validate_references(dataset: AdaptivePolicyPilotDataset) -> None:
    course_id = dataset.course.course_id
    concepts = {entry.concept_id: entry for entry in dataset.concept_registry}
    fixtures = {
        fixture.fixture_id: fixture for fixture in dataset.evidence_fixtures
    }
    review_fixtures = {
        fixture.fixture_id: fixture for fixture in dataset.review_fixtures
    }
    if len(concepts) != len(dataset.concept_registry):
        raise ValueError("concept_registry contains duplicate concept IDs")
    if len(fixtures) != len(dataset.evidence_fixtures):
        raise ValueError("evidence_fixtures contains duplicate fixture IDs")
    if len(review_fixtures) != len(dataset.review_fixtures):
        raise ValueError("review_fixtures contains duplicate fixture IDs")

    for concept in concepts.values():
        expected_status = (
            "observed" if concept.production_attempt_count > 0 else "unobserved"
        )
        if concept.production_state_status != expected_status:
            raise ValueError(
                f"Concept {concept.concept_id} production status/count mismatch"
            )

    for scenario in dataset.scenarios:
        if scenario.course_id != course_id:
            raise ValueError(f"{scenario.case_id} has the wrong course")
        registry_concept = concepts.get(scenario.concept.concept_id)
        if (
            registry_concept is None
            or registry_concept.name != scenario.concept.name
        ):
            raise ValueError(f"{scenario.case_id} has an unknown concept")
        fixture = fixtures.get(scenario.evidence_fixture_id)
        if fixture is None:
            raise ValueError(f"{scenario.case_id} has an unknown evidence fixture")
        if fixture.course_id != course_id:
            raise ValueError(f"{scenario.case_id} fixture has the wrong course")
        if fixture.concept_id != scenario.concept.concept_id:
            raise ValueError(f"{scenario.case_id} fixture/concept mismatch")
        if fixture.evidence_state.retrieved_chunk_count != len(
            fixture.ordered_chunks
        ):
            raise ValueError(f"{fixture.fixture_id} chunk count is inconsistent")
        if fixture.evidence_state.source_coverage != 1.0:
            raise ValueError(f"{fixture.fixture_id} must have full audited coverage")

        if scenario.review_fixture_id is not None:
            review = review_fixtures.get(scenario.review_fixture_id)
            if review is None:
                raise ValueError(f"{scenario.case_id} has an unknown review fixture")
            if review.course_id != course_id:
                raise ValueError(f"{scenario.case_id} review has the wrong course")
            if review.concept_id != scenario.concept.concept_id:
                raise ValueError(f"{scenario.case_id} review/concept mismatch")
            chunk_ids = {chunk.chunk_id for chunk in fixture.ordered_chunks}
            if not set(review.source_chunk_ids).issubset(chunk_ids):
                raise ValueError(f"{scenario.case_id} review/evidence mismatch")
            if not scenario.learner_state.review_due:
                raise ValueError(
                    f"{scenario.case_id} uses review fixture when review is not due"
                )


def _validate_group_invariants(dataset: AdaptivePolicyPilotDataset) -> None:
    grouped = _group_scenarios(dataset.scenarios)
    for group_id, scenarios in grouped.items():
        _require_single_value(group_id, scenarios, "question")
        _require_single_value(group_id, scenarios, "course_id")
        _require_single_value(group_id, scenarios, "detected_intent")
        _require_single_value(group_id, scenarios, "evidence_fixture_id")
        _require_single_value(
            group_id,
            scenarios,
            "concept",
            serializer=lambda value: (
                value.concept_id,
                value.name,
                value.state_status,
            ),
        )
        _require_single_value(
            group_id,
            scenarios,
            "expected_baseline_policy",
            serializer=lambda value: (
                value.selected_action,
                value.response_strategy,
            ),
        )
        if any(scenario.misconception is not None for scenario in scenarios):
            raise ValueError(f"{group_id} must keep misconception disabled")

    profiles = dataset.learner_profiles
    for scenario in dataset.scenarios:
        if scenario.scenario_position in profiles:
            if scenario.learner_state != profiles[scenario.scenario_position]:
                raise ValueError(
                    f"{scenario.case_id} does not match its learner profile"
                )

    review_scenarios = grouped["P03"]
    medium_profile = profiles["medium"].model_dump()
    for scenario in review_scenarios:
        state = scenario.learner_state.model_dump()
        expected_due = scenario.scenario_position == "review_true"
        if state["review_due"] != expected_due:
            raise ValueError(f"{scenario.case_id} has wrong review_due")
        state["review_due"] = False
        if state != medium_profile:
            raise ValueError("P03 may vary only review_due")

    review_true = next(
        scenario
        for scenario in review_scenarios
        if scenario.scenario_position == "review_true"
    )
    review_false = next(
        scenario
        for scenario in review_scenarios
        if scenario.scenario_position == "review_false"
    )
    if review_true.review_fixture_id is None:
        raise ValueError("P03 review_true requires frozen review fixture")
    if review_false.review_fixture_id is not None:
        raise ValueError("P03 review_false must not use review fixture")


def _validate_expected_policies(dataset: AdaptivePolicyPilotDataset) -> None:
    fixtures = {
        fixture.fixture_id: fixture for fixture in dataset.evidence_fixtures
    }
    for scenario in dataset.scenarios:
        actual_intent = detect_intent(scenario.question)
        if actual_intent != scenario.detected_intent:
            raise ValueError(f"{scenario.case_id} intent is {actual_intent}")
        expected_baseline = dataset.policy.baseline_mapping[
            scenario.detected_intent
        ]
        if scenario.expected_baseline_policy != expected_baseline:
            raise ValueError(f"{scenario.case_id} has wrong Baseline policy")

        state = scenario.learner_state
        learner_state = LearnerState(
            user_id=dataset.course.user_id,
            course_id=dataset.course.course_id,
            mastery_score=state.mastery_score,
            recent_accuracy=state.recent_accuracy,
            attempt_count=state.attempt_count,
            consecutive_errors=state.consecutive_errors,
            last_reviewed_at=None,
            review_due=state.review_due,
        )
        concept_state = ConceptLearnerState(
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
        fixture = fixtures[scenario.evidence_fixture_id]
        frozen_evidence = _FrozenPolicyEvidence(
            evidence_strength=fixture.evidence_state.evidence_strength,
            source_coverage=fixture.evidence_state.source_coverage,
            retrieved_chunk_count=fixture.evidence_state.retrieved_chunk_count,
            top_similarity=None,
            requires_evidence=fixture.evidence_state.requires_evidence,
            reason="Human-audited frozen pilot evidence fixture.",
            retrieval_scope=fixture.evidence_state.retrieval_scope,
            source_chunk_ids=[
                chunk.chunk_id for chunk in fixture.ordered_chunks
            ],
        )
        decision = decide_teaching_action(
            query=scenario.question,
            user_id=dataset.course.user_id,
            course_id=dataset.course.course_id,
            learner_state=learner_state,
            evidence_state=cast(PolicyEvidenceState, frozen_evidence),
            detected_intent=scenario.detected_intent,
            learner_state_scope="concept",
            concept_state=concept_state,
            misconception_snapshot=None,
        )
        actual_policy = ExpectedPolicy(
            selected_action=decision.selected_action,
            response_strategy=decision.response_strategy,
        )
        if actual_policy != scenario.expected_adaptive_policy:
            raise ValueError(f"{scenario.case_id} does not match rule_v2")


def _validate_generation_control(dataset: AdaptivePolicyPilotDataset) -> None:
    identical = sorted(
        scenario.case_id
        for scenario in dataset.scenarios
        if scenario.expected_adaptive_policy
        == scenario.expected_baseline_policy
    )
    control = dataset.generation_control
    if identical != sorted(control.identical_policy_case_ids):
        raise ValueError("Pilot identical-policy controls are stale")
    if control.condition_artifact_count != len(dataset.scenarios) * 2:
        raise ValueError("Pilot condition artifact count is inconsistent")
    if dataset.topology.identical_policy_scenarios != len(identical):
        raise ValueError("Pilot identical-policy count is inconsistent")

    canonical_executions = len(dataset.scenarios) * 2 - len(identical)
    if canonical_executions != control.planned_canonical_response_execution_count:
        raise ValueError("Pilot canonical execution count is inconsistent")
    if (
        dataset.topology.planned_canonical_response_execution_count
        != control.planned_canonical_response_execution_count
    ):
        raise ValueError("Pilot canonical execution declarations disagree")

    expected_provider_calls = sum(
        (0 if policy.selected_action in {"review", "refuse"} else 1)
        + (
            1
            if policy.selected_action == "explain"
            and policy.response_strategy == "scaffolded"
            else 0
        )
        for scenario in dataset.scenarios
        for policy in _canonical_policies_for_scenario(scenario)
    )
    if (
        expected_provider_calls
        != control.expected_successful_provider_generation_count
    ):
        raise ValueError("Pilot provider generation count is inconsistent")
    if (
        dataset.topology.expected_successful_provider_generation_count
        != control.expected_successful_provider_generation_count
    ):
        raise ValueError("Pilot provider generation declarations disagree")


def _canonical_policies_for_scenario(
    scenario: PilotScenario,
) -> list[ExpectedPolicy]:
    policies = [scenario.expected_adaptive_policy]
    if scenario.expected_baseline_policy != scenario.expected_adaptive_policy:
        policies.append(scenario.expected_baseline_policy)
    return policies


def _validate_fixture_hashes(dataset: AdaptivePolicyPilotDataset) -> None:
    for fixture in dataset.evidence_fixtures:
        payload = fixture.model_dump(
            mode="json",
            exclude={"fixture_sha256"},
        )
        actual = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        if actual != fixture.fixture_sha256:
            raise ValueError(f"{fixture.fixture_id} fixture SHA256 is invalid")

    for review_fixture in dataset.review_fixtures:
        payload = review_fixture.model_dump(
            mode="json",
            exclude={"fixture_sha256"},
        )
        actual = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        if actual != review_fixture.fixture_sha256:
            raise ValueError(
                f"{review_fixture.fixture_id} fixture SHA256 is invalid"
            )


def _validate_formal_isolation(dataset: AdaptivePolicyPilotDataset) -> None:
    actual_hash = _file_sha256(FORMAL_CANDIDATE_PATH)
    if actual_hash != dataset.formal_candidate_lock.dataset_sha256:
        raise ValueError("Locked formal candidate SHA256 changed")

    with FORMAL_CANDIDATE_PATH.open(encoding="utf-8") as file:
        formal = json.load(file)
    formal_questions = {
        scenario["question"].strip().casefold()
        for scenario in formal["scenarios"]
    }
    duplicated = [
        scenario.case_id
        for scenario in dataset.scenarios
        if scenario.question.strip().casefold() in formal_questions
    ]
    if duplicated:
        raise ValueError(f"Pilot duplicates formal questions: {duplicated}")


def _verify_fixture_chunks(
    *,
    db: Session,
    dataset: AdaptivePolicyPilotDataset,
    fixture: EvidenceFixture,
) -> None:
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

    for expected in fixture.ordered_chunks:
        chunk, _ = by_id[expected.chunk_id]
        if chunk.chunk_metadata.get("chunk_index") != expected.chunk_index:
            raise ValueError(f"Chunk {chunk.id} index changed")
        actual_hash = hashlib.sha256(chunk.content.encode()).hexdigest()
        if actual_hash != expected.content_sha256:
            raise ValueError(f"Chunk {chunk.id} content SHA256 changed")


def _group_scenarios(
    scenarios: list[PilotScenario],
) -> dict[str, list[PilotScenario]]:
    grouped: dict[str, list[PilotScenario]] = {}
    for scenario in scenarios:
        grouped.setdefault(scenario.group_id, []).append(scenario)
    return grouped


def _require_single_value(
    group_id: str,
    scenarios: list[PilotScenario],
    field_name: str,
    *,
    serializer=None,  # type: ignore[no-untyped-def]
) -> None:
    values = {
        serializer(getattr(scenario, field_name))
        if serializer is not None
        else getattr(scenario, field_name)
        for scenario in scenarios
    }
    if len(values) != 1:
        raise ValueError(f"{group_id} must keep {field_name} invariant")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the isolated V1-B adaptive-policy pilot."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--write-schema", type=Path)
    parser.add_argument(
        "--verify-production-inputs",
        action="store_true",
        help="Read-only audit against the live concept graph and course chunks.",
    )
    args = parser.parse_args()

    dataset = load_and_validate_pilot(args.dataset)
    if args.verify_production_inputs:
        from app.db import SessionLocal

        with SessionLocal() as db:
            verify_production_pilot_inputs(dataset, db)
        print("Verified production intent, concepts, evidence, and quiz path.")
    if args.write_schema is not None:
        write_json_schema(args.write_schema)
    print("Validated 8 independent pilot scenarios across 4 groups.")


if __name__ == "__main__":
    main()
