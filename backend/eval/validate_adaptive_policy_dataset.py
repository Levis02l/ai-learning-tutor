from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Chunk, Document
from app.services.concepts import (
    ConceptLearnerState,
    resolve_concept_for_focus,
)
from app.services.learner_state import LearnerState
from app.services.policy import (
    DetectedIntent,
    PolicyEvidenceState,
    ResponseStrategy,
    TeachingAction,
    decide_teaching_action,
    detect_intent,
)

DEFAULT_DATASET_PATH = (
    Path(__file__).parent
    / "datasets"
    / "adaptive_policy_v1_formal_candidate.json"
)
DEFAULT_SCHEMA_PATH = (
    Path(__file__).parent / "datasets" / "adaptive_policy_v1.schema.json"
)

EXPECTED_GROUP_POSITIONS = {
    **{
        f"AP_G{group_number:02d}": {"low", "high"}
        for group_number in [1, 2, 3, 4, 5, 6, 10, 11]
    },
    "AP_G07": {"low", "medium", "high"},
    "AP_G08": {"low", "medium", "high"},
    "AP_G09": {"review_false", "review_true"},
}
EXPECTED_GROUP_TYPES = {
    **{
        f"AP_G{group_number:02d}": "state_adaptation_pair"
        for group_number in range(1, 7)
    },
    "AP_G07": "mastery_ordinal_triplet",
    "AP_G08": "mastery_ordinal_triplet",
    "AP_G09": "review_due_pair",
    "AP_G10": "explicit_intent_fidelity_pair",
    "AP_G11": "explicit_intent_fidelity_pair",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CourseDefinition(StrictModel):
    course_id: int
    course_name: str
    user_id: str
    document_id: int
    source_filename: str


class ExpectedPolicy(StrictModel):
    selected_action: TeachingAction
    response_strategy: ResponseStrategy


class PolicyDefinition(StrictModel):
    adaptive_policy_version: Literal["rule_v2"]
    misconception: None
    evidence_condition: Literal["sufficient"]
    baseline_mapping: dict[DetectedIntent, ExpectedPolicy]


class TopologyDefinition(StrictModel):
    group_count: int
    scenario_count: int
    adaptive_baseline_comparisons: int
    generated_output_count: int
    state_adaptation_directional_pairs: int
    mastery_ordinal_triplets: int
    review_due_pairs: int
    explicit_intent_fidelity_pairs: int
    condition_artifact_count: int
    planned_model_generation_call_count: int


class GenerationControl(StrictModel):
    identical_policy_handling: Literal["single_generation_reuse"]
    independent_condition_scenarios: int
    identical_policy_scenarios: int
    identical_policy_case_ids: list[str]
    condition_artifact_count: int
    planned_model_generation_call_count: int
    analysis_role: Literal["expected_no_treatment_tie_controls"]
    rule: str


class LearnerStateDefinition(StrictModel):
    mastery_score: float = Field(ge=0.0, le=1.0)
    recent_accuracy: float = Field(ge=0.0, le=1.0)
    attempt_count: int = Field(ge=0)
    consecutive_errors: int = Field(ge=0)
    last_reviewed_at: str | None
    review_due: bool


class ConceptRegistryEntry(StrictModel):
    concept_id: int
    name: str
    production_attempt_count: int = Field(ge=0)
    production_state_status: Literal["observed", "unobserved"]
    evaluation_state_status: Literal["observed"]


class EvidenceChunkDefinition(StrictModel):
    chunk_id: int
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_index: int = Field(ge=0)


class FrozenEvidenceState(StrictModel):
    evidence_strength: Literal["high"]
    source_coverage: float = Field(ge=0.0, le=1.0)
    retrieved_chunk_count: int = Field(ge=1)
    top_similarity: None
    requires_evidence: Literal[True]
    retrieval_scope: Literal["concept"]
    sufficiency_assessment: Literal["human_audited_frozen_fixture"]


class EvidenceFixture(StrictModel):
    fixture_id: str
    course_id: int
    concept_id: int
    page_targets: list[int] = Field(min_length=1)
    ordered_chunks: list[EvidenceChunkDefinition] = Field(min_length=1)
    evidence_state: FrozenEvidenceState
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReviewFixture(StrictModel):
    fixture_id: str
    course_id: int
    concept_id: int
    question: str
    reference_answer: str
    source_chunk_ids: list[int] = Field(min_length=1)
    origin: Literal["evaluation_frozen_review_fixture"]


class ScenarioConcept(StrictModel):
    concept_id: int
    name: str
    state_status: Literal["observed"]
    resolver_confidence: float = Field(ge=0.72, le=1.0)
    resolver_reason: str


class AnnotationContext(StrictModel):
    learner_vignette: str


class AdaptivePolicyScenario(StrictModel):
    case_id: str
    group_id: str
    group_type: Literal[
        "state_adaptation_pair",
        "mastery_ordinal_triplet",
        "review_due_pair",
        "explicit_intent_fidelity_pair",
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


class AdaptivePolicyDataset(StrictModel):
    schema_version: Literal["adaptive_policy_v1_candidate_1.0"]
    dataset_id: Literal["adaptive_policy_v1_formal_candidate"]
    status: Literal["candidate_not_frozen"]
    created_date: str
    course: CourseDefinition
    policy: PolicyDefinition
    topology: TopologyDefinition
    generation_control: GenerationControl
    learner_profiles: dict[
        Literal["low", "medium", "high"],
        LearnerStateDefinition,
    ]
    concept_registry: list[ConceptRegistryEntry]
    evidence_fixtures: list[EvidenceFixture]
    review_fixtures: list[ReviewFixture]
    scenarios: list[AdaptivePolicyScenario]

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


def load_and_validate_dataset(
    path: Path = DEFAULT_DATASET_PATH,
) -> AdaptivePolicyDataset:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    return AdaptivePolicyDataset.model_validate(payload)


def verify_production_concept_resolution(
    dataset: AdaptivePolicyDataset,
    db: Session,
) -> None:
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
            raise ValueError(
                f"{group_id} resolved to concept {resolved.concept.id} "
                f"({resolved.concept.name}), not {scenario.concept.concept_id} "
                f"({scenario.concept.name})"
            )
        if resolved.confidence < 0.72:
            raise ValueError(f"{group_id} resolver confidence is below 0.72")
        if round(resolved.confidence, 3) != scenario.concept.resolver_confidence:
            raise ValueError(f"{group_id} resolver confidence is stale")
        if resolved.reason != scenario.concept.resolver_reason:
            raise ValueError(f"{group_id} resolver reason is stale")


def verify_production_dataset_inputs(
    dataset: AdaptivePolicyDataset,
    db: Session,
) -> None:
    verify_production_concept_resolution(dataset, db)
    for fixture in dataset.evidence_fixtures:
        _verify_fixture_chunks(db=db, dataset=dataset, fixture=fixture)


def planned_canonical_response_execution_count(
    dataset: AdaptivePolicyDataset,
) -> int:
    return sum(
        1
        + int(
            scenario.expected_baseline_policy
            != scenario.expected_adaptive_policy
        )
        for scenario in dataset.scenarios
    )


def expected_successful_provider_generation_count(
    dataset: AdaptivePolicyDataset,
) -> int:
    return sum(
        _provider_generation_count(policy)
        for scenario in dataset.scenarios
        for policy in _canonical_policies_for_scenario(scenario)
    )


def write_json_schema(path: Path = DEFAULT_SCHEMA_PATH) -> None:
    path.write_text(
        json.dumps(AdaptivePolicyDataset.model_json_schema(), indent=2) + "\n",
        encoding="utf-8",
    )


def _validate_topology(dataset: AdaptivePolicyDataset) -> None:
    scenarios = dataset.scenarios
    case_ids = [scenario.case_id for scenario in scenarios]
    if len(scenarios) != 24 or len(set(case_ids)) != 24:
        raise ValueError("Dataset must contain 24 unique scenario instances")

    grouped = _group_scenarios(scenarios)
    if set(grouped) != set(EXPECTED_GROUP_POSITIONS):
        raise ValueError("Dataset must contain exactly AP_G01 through AP_G11")

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

    topology = dataset.topology
    expected_values = {
        "group_count": 11,
        "scenario_count": 24,
        "adaptive_baseline_comparisons": 24,
        "generated_output_count": 48,
        "state_adaptation_directional_pairs": 6,
        "mastery_ordinal_triplets": 2,
        "review_due_pairs": 1,
        "explicit_intent_fidelity_pairs": 2,
        "condition_artifact_count": 48,
    }
    for field_name, expected in expected_values.items():
        if getattr(topology, field_name) != expected:
            raise ValueError(f"topology.{field_name} must be {expected}")


def _validate_references(dataset: AdaptivePolicyDataset) -> None:
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
            raise ValueError(f"{scenario.case_id} has the wrong course ID")
        registry_concept = concepts.get(scenario.concept.concept_id)
        if registry_concept is None or registry_concept.name != scenario.concept.name:
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
            review_fixture = review_fixtures.get(scenario.review_fixture_id)
            if review_fixture is None:
                raise ValueError(f"{scenario.case_id} has an unknown review fixture")
            if review_fixture.course_id != course_id:
                raise ValueError(f"{scenario.case_id} review has the wrong course")
            if review_fixture.concept_id != scenario.concept.concept_id:
                raise ValueError(f"{scenario.case_id} review/concept mismatch")
            fixture_chunk_ids = {
                chunk.chunk_id for chunk in fixture.ordered_chunks
            }
            if not set(review_fixture.source_chunk_ids).issubset(
                fixture_chunk_ids
            ):
                raise ValueError(
                    f"{scenario.case_id} review/evidence chunks mismatch"
                )
            if not scenario.learner_state.review_due:
                raise ValueError(
                    f"{scenario.case_id} uses a review fixture when review is not due"
                )


def _validate_group_invariants(dataset: AdaptivePolicyDataset) -> None:
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
            serializer=lambda value: (value.concept_id, value.name, value.state_status),
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
                    f"{scenario.case_id} does not match its canonical learner profile"
                )

    review_scenarios = grouped["AP_G09"]
    base_profile = profiles["medium"].model_dump()
    for scenario in review_scenarios:
        state = scenario.learner_state.model_dump()
        expected_review_due = scenario.scenario_position == "review_true"
        if state["review_due"] != expected_review_due:
            raise ValueError(f"{scenario.case_id} has the wrong review_due value")
        state["review_due"] = False
        if state != base_profile:
            raise ValueError("AP_G09 may vary only review_due")

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
        raise ValueError("AP_G09 review_true requires a frozen review fixture")
    if review_false.review_fixture_id is not None:
        raise ValueError("AP_G09 review_false must not use a review fixture")


def _validate_expected_policies(dataset: AdaptivePolicyDataset) -> None:
    baseline_mapping = dataset.policy.baseline_mapping
    if set(baseline_mapping) != {
        "explain",
        "hint",
        "practice",
        "review",
        "unknown",
    }:
        raise ValueError("Baseline mapping must define all canonical intents")

    fixtures = {
        fixture.fixture_id: fixture for fixture in dataset.evidence_fixtures
    }
    for scenario in dataset.scenarios:
        actual_intent = detect_intent(scenario.question)
        if actual_intent != scenario.detected_intent:
            raise ValueError(
                f"{scenario.case_id} intent is {actual_intent}, "
                f"not {scenario.detected_intent}"
            )
        if (
            scenario.expected_baseline_policy
            != baseline_mapping[scenario.detected_intent]
        ):
            raise ValueError(f"{scenario.case_id} has the wrong Baseline policy")

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
            reason="Human-audited frozen evidence fixture.",
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
            raise ValueError(f"{scenario.case_id} does not match production rule_v2")


def _validate_generation_control(dataset: AdaptivePolicyDataset) -> None:
    identical_case_ids = sorted(
        scenario.case_id
        for scenario in dataset.scenarios
        if scenario.expected_adaptive_policy
        == scenario.expected_baseline_policy
    )
    control = dataset.generation_control
    if identical_case_ids != sorted(control.identical_policy_case_ids):
        raise ValueError("identical_policy_case_ids does not match dataset policies")

    identical_count = len(identical_case_ids)
    independent_count = len(dataset.scenarios) - identical_count
    planned_calls = planned_canonical_response_execution_count(dataset)
    if control.identical_policy_scenarios != identical_count:
        raise ValueError("identical_policy_scenarios is inconsistent")
    if control.independent_condition_scenarios != independent_count:
        raise ValueError("independent_condition_scenarios is inconsistent")
    if control.condition_artifact_count != len(dataset.scenarios) * 2:
        raise ValueError("condition_artifact_count is inconsistent")
    if control.planned_model_generation_call_count != planned_calls:
        raise ValueError("planned_model_generation_call_count is inconsistent")
    if dataset.topology.planned_model_generation_call_count != planned_calls:
        raise ValueError("topology generation call count is inconsistent")


def _canonical_policies_for_scenario(
    scenario: AdaptivePolicyScenario,
) -> list[ExpectedPolicy]:
    policies = [scenario.expected_adaptive_policy]
    if scenario.expected_baseline_policy != scenario.expected_adaptive_policy:
        policies.append(scenario.expected_baseline_policy)
    return policies


def _provider_generation_count(policy: ExpectedPolicy) -> int:
    if policy.selected_action in {"review", "refuse"}:
        return 0
    return 1 + int(
        policy.selected_action == "explain"
        and policy.response_strategy == "scaffolded"
    )


def _validate_fixture_hashes(dataset: AdaptivePolicyDataset) -> None:
    for fixture in dataset.evidence_fixtures:
        payload = fixture.model_dump(
            mode="json",
            exclude={"fixture_sha256"},
        )
        actual_hash = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        if actual_hash != fixture.fixture_sha256:
            raise ValueError(f"{fixture.fixture_id} fixture SHA256 is invalid")


def _verify_fixture_chunks(
    *,
    db: Session,
    dataset: AdaptivePolicyDataset,
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
    scenarios: list[AdaptivePolicyScenario],
) -> dict[str, list[AdaptivePolicyScenario]]:
    grouped: dict[str, list[AdaptivePolicyScenario]] = {}
    for scenario in scenarios:
        grouped.setdefault(scenario.group_id, []).append(scenario)
    return grouped


def _require_single_value(
    group_id: str,
    scenarios: list[AdaptivePolicyScenario],
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the V1-B adaptive-policy dataset candidate."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--write-schema", type=Path)
    parser.add_argument(
        "--verify-production-resolution",
        action="store_true",
        help="Re-run every group through the live production concept resolver.",
    )
    args = parser.parse_args()

    dataset = load_and_validate_dataset(args.dataset)
    if args.verify_production_resolution:
        from app.db import SessionLocal

        with SessionLocal() as db:
            verify_production_concept_resolution(dataset, db)
        print("Verified production concept resolution for 11 groups.")
    if args.write_schema is not None:
        write_json_schema(args.write_schema)
    print(
        "Validated "
        f"{len(dataset.scenarios)} scenarios across "
        f"{dataset.topology.group_count} groups."
    )


if __name__ == "__main__":
    main()
