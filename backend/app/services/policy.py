from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.misconception import Misconception
from app.models.policy import PolicyDecisionRecord
from app.services.concepts import (
    ConceptLearnerState,
    ResolvedConcept,
    get_concept_learner_state,
    resolve_concept_for_focus,
)
from app.services.learner_state import LearnerState, compute_learner_state
from app.services.misconceptions import get_relevant_misconception
from app.services.retrieval import RetrievedChunk, retrieve_relevant_chunks
from app.services.review import get_due_review_items
from app.services.tutor_context import (
    TutorEvidenceContext,
    TutorEvidenceState,
    TutorEvidenceStrength,
    build_evidence_state_from_chunks,
    build_not_required_evidence_context,
    build_tutor_evidence_context,
)

POLICY_VERSION = "rule_v2"

DetectedIntent = Literal["explain", "hint", "practice", "review", "unknown"]
TeachingAction = Literal["explain", "hint", "quiz", "review", "refuse"]
LearnerStateScope = Literal["course", "concept"]
ResponseStrategy = Literal[
    "scaffolded",
    "guided",
    "concise",
    "challenging",
    "refusal",
    "review_drill",
    "contrastive",
    "definition_clarification",
    "prerequisite_scaffolded",
    "reasoning_guidance",
    "source_correction",
]
PolicyEvidenceStrength = TutorEvidenceStrength
PolicyEvidenceState = TutorEvidenceState


@dataclass(frozen=True)
class PolicyDecision:
    decision_id: int | None
    user_id: str
    course_id: int | None
    query: str
    detected_intent: DetectedIntent
    selected_action: TeachingAction
    response_strategy: ResponseStrategy
    primary_reason: str
    teaching_reason: str
    suggested_next_step: str
    policy_version: str
    learner_state_snapshot: dict[str, Any]
    evidence_state_snapshot: dict[str, Any]
    learner_state_scope: LearnerStateScope = "course"
    concept_state_snapshot: dict[str, Any] | None = None
    misconception_snapshot: dict[str, Any] | None = None
    evidence_chunks: list[RetrievedChunk] = field(default_factory=list)


@dataclass(frozen=True)
class _PolicyLearnerContext:
    state: LearnerState
    scope: LearnerStateScope
    concept_state: ConceptLearnerState | None


def create_policy_decision(
    db: Session,
    *,
    query: str,
    user_id: str = "demo-user",
    course_id: int | None = None,
    top_k: int = 5,
) -> PolicyDecision:
    course_learner_state = compute_learner_state(
        db=db,
        user_id=user_id,
        course_id=course_id,
    )
    detected_intent = detect_intent(query)
    resolved_concept = _resolve_query_concept(
        db=db,
        query=query,
        user_id=user_id,
        course_id=course_id,
    )
    learner_context = _resolve_policy_learner_context(
        db=db,
        user_id=user_id,
        course_id=course_id,
        course_learner_state=course_learner_state,
        resolved_concept=resolved_concept,
    )
    misconception_snapshot = _resolve_misconception_snapshot(
        db=db,
        user_id=user_id,
        course_id=course_id,
        resolved_concept=resolved_concept,
    )
    has_due_review_item = bool(
        get_due_review_items(
            db=db,
            user_id=user_id,
            course_id=course_id,
            limit=1,
        )
    )
    evidence_context = _resolve_evidence_context(
        db=db,
        query=query,
        user_id=user_id,
        course_id=course_id,
        top_k=top_k,
        detected_intent=detected_intent,
        learner_state=learner_context.state,
        has_due_review_item=has_due_review_item,
        resolved_concept=resolved_concept,
    )
    decision = decide_teaching_action(
        query=query,
        user_id=user_id,
        course_id=course_id,
        learner_state=learner_context.state,
        evidence_state=evidence_context.evidence_state,
        detected_intent=detected_intent,
        learner_state_scope=learner_context.scope,
        concept_state=learner_context.concept_state,
        misconception_snapshot=misconception_snapshot,
        evidence_chunks=evidence_context.chunks,
    )
    record = PolicyDecisionRecord(
        user_id=user_id,
        course_id=course_id,
        query=query,
        detected_intent=decision.detected_intent,
        learner_state_snapshot=decision.learner_state_snapshot,
        learner_state_scope=decision.learner_state_scope,
        concept_state_snapshot=decision.concept_state_snapshot,
        misconception_snapshot=decision.misconception_snapshot,
        evidence_state_snapshot=decision.evidence_state_snapshot,
        selected_action=decision.selected_action,
        response_strategy=decision.response_strategy,
        primary_reason=decision.primary_reason,
        teaching_reason=decision.teaching_reason,
        suggested_next_step=decision.suggested_next_step,
        policy_version=decision.policy_version,
        outcome=None,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return PolicyDecision(
        decision_id=record.id,
        user_id=decision.user_id,
        course_id=decision.course_id,
        query=decision.query,
        detected_intent=decision.detected_intent,
        selected_action=decision.selected_action,
        response_strategy=decision.response_strategy,
        primary_reason=decision.primary_reason,
        teaching_reason=decision.teaching_reason,
        suggested_next_step=decision.suggested_next_step,
        policy_version=decision.policy_version,
        learner_state_snapshot=decision.learner_state_snapshot,
        evidence_state_snapshot=decision.evidence_state_snapshot,
        learner_state_scope=decision.learner_state_scope,
        concept_state_snapshot=decision.concept_state_snapshot,
        misconception_snapshot=decision.misconception_snapshot,
        evidence_chunks=decision.evidence_chunks,
    )


def detect_intent(query: str) -> DetectedIntent:
    normalized = f" {query.lower().strip()} "
    hint_phrases = [
        " hint ",
        " clue ",
        " don't tell me ",
        " do not tell me ",
        " give me a hint ",
    ]
    practice_phrases = [
        " quiz me ",
        " test me ",
        " practice ",
        " question ",
        " questions ",
        " exam ",
        " assess me ",
    ]
    review_phrases = [
        " review ",
        " revise ",
        " revision ",
        " go over ",
        " recap ",
    ]
    explain_phrases = [
        " explain ",
        " what is ",
        " what are ",
        " why ",
        " how does ",
        " how do ",
        " help me understand ",
        " teach me ",
    ]

    if _contains_phrase(normalized, hint_phrases):
        return "hint"
    if _contains_phrase(normalized, review_phrases):
        return "review"
    if _contains_phrase(normalized, practice_phrases):
        return "practice"
    if _contains_phrase(normalized, explain_phrases):
        return "explain"
    return "unknown"


def decide_teaching_action(
    *,
    query: str,
    user_id: str,
    course_id: int | None,
    learner_state: LearnerState,
    evidence_state: PolicyEvidenceState,
    detected_intent: DetectedIntent | None = None,
    learner_state_scope: LearnerStateScope = "course",
    concept_state: ConceptLearnerState | None = None,
    misconception_snapshot: dict[str, Any] | None = None,
    evidence_chunks: list[RetrievedChunk] | None = None,
) -> PolicyDecision:
    intent = detected_intent or detect_intent(query)
    learner_snapshot = _learner_state_snapshot(learner_state)
    evidence_snapshot = _evidence_state_snapshot(evidence_state)
    final_evidence_chunks = evidence_chunks or []
    concept_snapshot = (
        _concept_state_snapshot(concept_state) if concept_state is not None else None
    )

    if _is_evidence_insufficient(evidence_state):
        return _build_decision(
            query=query,
            user_id=user_id,
            course_id=course_id,
            detected_intent=intent,
            selected_action="refuse",
            response_strategy="refusal",
            primary_reason="insufficient_evidence",
            teaching_reason=(
                "The requested teaching action needs course evidence, but the "
                "retrieved materials are not strong enough to support it."
            ),
            suggested_next_step=(
                "Upload more relevant material or ask about a topic covered by "
                "the current course workspace."
            ),
            learner_state_snapshot=learner_snapshot,
            evidence_state_snapshot=evidence_snapshot,
            learner_state_scope=learner_state_scope,
            concept_state_snapshot=concept_snapshot,
            misconception_snapshot=misconception_snapshot,
            evidence_chunks=final_evidence_chunks,
        )

    if intent == "explain":
        return _explicit_decision(
            query=query,
            user_id=user_id,
            course_id=course_id,
            learner_state=learner_state,
            learner_snapshot=learner_snapshot,
            evidence_snapshot=evidence_snapshot,
            detected_intent=intent,
            selected_action="explain",
            primary_reason="explicit_explanation_request",
            learner_state_scope=learner_state_scope,
            concept_state_snapshot=concept_snapshot,
            misconception_snapshot=misconception_snapshot,
            evidence_chunks=final_evidence_chunks,
        )
    if intent == "hint":
        return _explicit_decision(
            query=query,
            user_id=user_id,
            course_id=course_id,
            learner_state=learner_state,
            learner_snapshot=learner_snapshot,
            evidence_snapshot=evidence_snapshot,
            detected_intent=intent,
            selected_action="hint",
            primary_reason="explicit_hint_request",
            learner_state_scope=learner_state_scope,
            concept_state_snapshot=concept_snapshot,
            misconception_snapshot=misconception_snapshot,
            evidence_chunks=final_evidence_chunks,
        )
    if intent == "practice":
        return _explicit_decision(
            query=query,
            user_id=user_id,
            course_id=course_id,
            learner_state=learner_state,
            learner_snapshot=learner_snapshot,
            evidence_snapshot=evidence_snapshot,
            detected_intent=intent,
            selected_action="quiz",
            primary_reason="explicit_practice_request",
            learner_state_scope=learner_state_scope,
            concept_state_snapshot=concept_snapshot,
            misconception_snapshot=misconception_snapshot,
            evidence_chunks=final_evidence_chunks,
        )
    if intent == "review":
        return _explicit_decision(
            query=query,
            user_id=user_id,
            course_id=course_id,
            learner_state=learner_state,
            learner_snapshot=learner_snapshot,
            evidence_snapshot=evidence_snapshot,
            detected_intent=intent,
            selected_action="review",
            primary_reason="explicit_review_request",
            learner_state_scope=learner_state_scope,
            concept_state_snapshot=concept_snapshot,
            misconception_snapshot=misconception_snapshot,
            evidence_chunks=final_evidence_chunks,
        )

    if _is_unobserved_concept(concept_snapshot):
        assert concept_snapshot is not None
        concept_name = concept_snapshot["concept_name"]
        return _implicit_decision(
            query=query,
            user_id=user_id,
            course_id=course_id,
            learner_snapshot=learner_snapshot,
            evidence_snapshot=evidence_snapshot,
            selected_action="quiz",
            response_strategy="guided",
            primary_reason="unobserved_concept",
            teaching_reason=(
                f"The query maps to {concept_name}, but there are no observed "
                "attempts for this concept yet. A traceable diagnostic question "
                "is the most useful next step."
            ),
            suggested_next_step=(
                "Generate one diagnostic practice question for this concept."
            ),
            learner_state_scope=learner_state_scope,
            concept_state_snapshot=concept_snapshot,
            misconception_snapshot=misconception_snapshot,
            evidence_chunks=final_evidence_chunks,
        )

    if learner_state.review_due:
        return _implicit_decision(
            query=query,
            user_id=user_id,
            course_id=course_id,
            learner_snapshot=learner_snapshot,
            evidence_snapshot=evidence_snapshot,
            selected_action="review",
            response_strategy="review_drill",
            primary_reason="review_due",
            teaching_reason=(
                "The learner has due or unattempted practice items, so review "
                "should be prioritised before introducing more new content."
            ),
            suggested_next_step="Open the review queue and work through due questions.",
            learner_state_scope=learner_state_scope,
            concept_state_snapshot=concept_snapshot,
            misconception_snapshot=misconception_snapshot,
            evidence_chunks=final_evidence_chunks,
        )

    if learner_state.mastery_score < 0.4 or learner_state.consecutive_errors >= 2:
        return _implicit_decision(
            query=query,
            user_id=user_id,
            course_id=course_id,
            learner_snapshot=learner_snapshot,
            evidence_snapshot=evidence_snapshot,
            selected_action="explain",
            response_strategy="scaffolded",
            primary_reason="low_mastery",
            teaching_reason=(
                "The learner's mastery is low or recent answers show repeated "
                "errors, so a scaffolded explanation is the safest next move."
            ),
            suggested_next_step=(
                "Give a step-by-step explanation, then ask one short diagnostic "
                "question."
            ),
            learner_state_scope=learner_state_scope,
            concept_state_snapshot=concept_snapshot,
            misconception_snapshot=misconception_snapshot,
            evidence_chunks=final_evidence_chunks,
        )

    if learner_state.mastery_score < 0.75:
        return _implicit_decision(
            query=query,
            user_id=user_id,
            course_id=course_id,
            learner_snapshot=learner_snapshot,
            evidence_snapshot=evidence_snapshot,
            selected_action="hint",
            response_strategy="guided",
            primary_reason="medium_mastery",
            teaching_reason=(
                "The learner shows partial mastery, so a guided hint should "
                "support retrieval without giving away the full answer."
            ),
            suggested_next_step=(
                "Offer one targeted hint and invite the learner to try."
            ),
            learner_state_scope=learner_state_scope,
            concept_state_snapshot=concept_snapshot,
            misconception_snapshot=misconception_snapshot,
            evidence_chunks=final_evidence_chunks,
        )

    return _implicit_decision(
        query=query,
        user_id=user_id,
        course_id=course_id,
        learner_snapshot=learner_snapshot,
        evidence_snapshot=evidence_snapshot,
        selected_action="quiz",
        response_strategy="challenging",
        primary_reason="high_mastery",
        teaching_reason=(
            "The learner has high mastery and no explicit request, so a "
            "challenge question is appropriate."
        ),
        suggested_next_step="Generate a higher-challenge practice question.",
        learner_state_scope=learner_state_scope,
        concept_state_snapshot=concept_snapshot,
        misconception_snapshot=misconception_snapshot,
        evidence_chunks=final_evidence_chunks,
    )


def build_retrieval_evidence_state(
    db: Session,
    *,
    query: str,
    user_id: str = "demo-user",
    course_id: int | None = None,
    top_k: int = 5,
) -> PolicyEvidenceState:
    chunks = retrieve_relevant_chunks(
        db=db,
        query=query,
        user_id=user_id,
        course_id=course_id,
        top_k=top_k,
    )
    return build_evidence_state_from_chunks(chunks, retrieval_scope="course")


def _resolve_evidence_context(
    *,
    db: Session,
    query: str,
    user_id: str,
    course_id: int | None,
    top_k: int,
    detected_intent: DetectedIntent,
    learner_state: LearnerState,
    has_due_review_item: bool,
    resolved_concept: ResolvedConcept | None,
) -> TutorEvidenceContext:
    if has_due_review_item and (
        detected_intent == "review"
        or (detected_intent == "unknown" and learner_state.review_due)
    ):
        return build_not_required_evidence_context(
            resolved_concept=resolved_concept,
        )

    return build_tutor_evidence_context(
        db=db,
        query=query,
        user_id=user_id,
        course_id=course_id,
        top_k=top_k,
        resolved_concept=resolved_concept,
    )


def _resolve_query_concept(
    *,
    db: Session,
    query: str,
    user_id: str,
    course_id: int | None,
) -> ResolvedConcept | None:
    if course_id is None:
        return None
    return resolve_concept_for_focus(
        db=db,
        user_id=user_id,
        course_id=course_id,
        focus=query,
    )


def _resolve_misconception_snapshot(
    *,
    db: Session,
    user_id: str,
    course_id: int | None,
    resolved_concept: ResolvedConcept | None,
) -> dict[str, Any] | None:
    if course_id is None or resolved_concept is None:
        return None

    misconception = get_relevant_misconception(
        db=db,
        user_id=user_id,
        course_id=course_id,
        concept_id=resolved_concept.concept.id,
    )
    if misconception is None:
        return None

    return _misconception_snapshot(misconception)


def _resolve_policy_learner_context(
    *,
    db: Session,
    user_id: str,
    course_id: int | None,
    course_learner_state: LearnerState,
    resolved_concept: ResolvedConcept | None,
) -> _PolicyLearnerContext:
    if course_id is None or resolved_concept is None:
        return _PolicyLearnerContext(
            state=course_learner_state,
            scope="course",
            concept_state=None,
        )

    concept_state = get_concept_learner_state(
        db=db,
        user_id=user_id,
        course_id=course_id,
        concept_id=resolved_concept.concept.id,
    )
    return _PolicyLearnerContext(
        state=_learner_state_from_concept_state(
            course_learner_state=course_learner_state,
            concept_state=concept_state,
        ),
        scope="concept",
        concept_state=concept_state,
    )


def _learner_state_from_concept_state(
    *,
    course_learner_state: LearnerState,
    concept_state: ConceptLearnerState,
) -> LearnerState:
    if concept_state.state_status == "unobserved":
        return LearnerState(
            user_id=course_learner_state.user_id,
            course_id=course_learner_state.course_id,
            mastery_score=0.5,
            recent_accuracy=0.5,
            attempt_count=0,
            consecutive_errors=0,
            last_reviewed_at=None,
            review_due=False,
        )

    return LearnerState(
        user_id=course_learner_state.user_id,
        course_id=course_learner_state.course_id,
        mastery_score=concept_state.mastery_score or 0.0,
        recent_accuracy=concept_state.recent_accuracy or 0.0,
        attempt_count=concept_state.attempt_count,
        consecutive_errors=concept_state.consecutive_errors,
        last_reviewed_at=concept_state.last_attempted_at,
        review_due=concept_state.review_due,
    )


def _contains_phrase(normalized_query: str, phrases: list[str]) -> bool:
    return any(phrase in normalized_query for phrase in phrases)


def _is_evidence_insufficient(evidence_state: PolicyEvidenceState) -> bool:
    return (
        evidence_state.requires_evidence
        and evidence_state.evidence_strength == "insufficient"
    )


def _explicit_decision(
    *,
    query: str,
    user_id: str,
    course_id: int | None,
    learner_state: LearnerState,
    learner_snapshot: dict[str, Any],
    evidence_snapshot: dict[str, Any],
    detected_intent: DetectedIntent,
    selected_action: TeachingAction,
    primary_reason: str,
    learner_state_scope: LearnerStateScope,
    concept_state_snapshot: dict[str, Any] | None,
    misconception_snapshot: dict[str, Any] | None,
    evidence_chunks: list[RetrievedChunk],
) -> PolicyDecision:
    response_strategy = _strategy_for_action(
        selected_action=selected_action,
        learner_state=learner_state,
    )
    return _build_decision(
        query=query,
        user_id=user_id,
        course_id=course_id,
        detected_intent=detected_intent,
        selected_action=selected_action,
        response_strategy=response_strategy,
        primary_reason=primary_reason,
        teaching_reason=_explicit_teaching_reason(
            selected_action=selected_action,
            response_strategy=response_strategy,
            learner_state=learner_state,
        ),
        suggested_next_step=_suggested_next_step(
            selected_action=selected_action,
            response_strategy=response_strategy,
        ),
        learner_state_snapshot=learner_snapshot,
        evidence_state_snapshot=evidence_snapshot,
        learner_state_scope=learner_state_scope,
        concept_state_snapshot=concept_state_snapshot,
        misconception_snapshot=misconception_snapshot,
        evidence_chunks=evidence_chunks,
    )


def _implicit_decision(
    *,
    query: str,
    user_id: str,
    course_id: int | None,
    learner_snapshot: dict[str, Any],
    evidence_snapshot: dict[str, Any],
    selected_action: TeachingAction,
    response_strategy: ResponseStrategy,
    primary_reason: str,
    teaching_reason: str,
    suggested_next_step: str,
    learner_state_scope: LearnerStateScope,
    concept_state_snapshot: dict[str, Any] | None,
    misconception_snapshot: dict[str, Any] | None,
    evidence_chunks: list[RetrievedChunk],
) -> PolicyDecision:
    return _build_decision(
        query=query,
        user_id=user_id,
        course_id=course_id,
        detected_intent="unknown",
        selected_action=selected_action,
        response_strategy=response_strategy,
        primary_reason=primary_reason,
        teaching_reason=teaching_reason,
        suggested_next_step=suggested_next_step,
        learner_state_snapshot=learner_snapshot,
        evidence_state_snapshot=evidence_snapshot,
        learner_state_scope=learner_state_scope,
        concept_state_snapshot=concept_state_snapshot,
        misconception_snapshot=misconception_snapshot,
        evidence_chunks=evidence_chunks,
    )


def _build_decision(
    *,
    query: str,
    user_id: str,
    course_id: int | None,
    detected_intent: DetectedIntent,
    selected_action: TeachingAction,
    response_strategy: ResponseStrategy,
    primary_reason: str,
    teaching_reason: str,
    suggested_next_step: str,
    learner_state_snapshot: dict[str, Any],
    evidence_state_snapshot: dict[str, Any],
    learner_state_scope: LearnerStateScope = "course",
    concept_state_snapshot: dict[str, Any] | None = None,
    misconception_snapshot: dict[str, Any] | None = None,
    evidence_chunks: list[RetrievedChunk] | None = None,
) -> PolicyDecision:
    final_strategy = _misconception_aware_strategy(
        selected_action=selected_action,
        response_strategy=response_strategy,
        misconception_snapshot=misconception_snapshot,
    )
    final_teaching_reason = _misconception_aware_teaching_reason(
        teaching_reason=teaching_reason,
        original_strategy=response_strategy,
        final_strategy=final_strategy,
        misconception_snapshot=misconception_snapshot,
    )
    final_next_step = _misconception_aware_next_step(
        suggested_next_step=suggested_next_step,
        original_strategy=response_strategy,
        final_strategy=final_strategy,
    )
    return PolicyDecision(
        decision_id=None,
        user_id=user_id,
        course_id=course_id,
        query=query,
        detected_intent=detected_intent,
        selected_action=selected_action,
        response_strategy=final_strategy,
        primary_reason=primary_reason,
        teaching_reason=final_teaching_reason,
        suggested_next_step=final_next_step,
        policy_version=POLICY_VERSION,
        learner_state_snapshot=learner_state_snapshot,
        evidence_state_snapshot=evidence_state_snapshot,
        learner_state_scope=learner_state_scope,
        concept_state_snapshot=concept_state_snapshot,
        misconception_snapshot=misconception_snapshot,
        evidence_chunks=evidence_chunks or [],
    )


def _strategy_for_action(
    *,
    selected_action: TeachingAction,
    learner_state: LearnerState,
) -> ResponseStrategy:
    if selected_action == "refuse":
        return "refusal"
    if selected_action == "review":
        return "review_drill"
    if selected_action == "quiz":
        return "challenging" if learner_state.mastery_score >= 0.75 else "guided"
    if learner_state.mastery_score < 0.4 or learner_state.consecutive_errors >= 2:
        return "scaffolded"
    if learner_state.mastery_score < 0.75:
        return "guided"
    return "concise"


def _misconception_aware_strategy(
    *,
    selected_action: TeachingAction,
    response_strategy: ResponseStrategy,
    misconception_snapshot: dict[str, Any] | None,
) -> ResponseStrategy:
    if selected_action not in {"explain", "hint"} or misconception_snapshot is None:
        return response_strategy

    misconception_type = misconception_snapshot.get("misconception_type")
    if misconception_type == "concept_confusion":
        return "contrastive"
    if misconception_type == "incorrect_definition":
        return "definition_clarification"
    if misconception_type == "missing_prerequisite":
        return "prerequisite_scaffolded"
    if misconception_type == "incomplete_reasoning":
        return "reasoning_guidance"
    if misconception_type == "source_misinterpretation":
        return "source_correction"
    return response_strategy


def _misconception_aware_teaching_reason(
    *,
    teaching_reason: str,
    original_strategy: ResponseStrategy,
    final_strategy: ResponseStrategy,
    misconception_snapshot: dict[str, Any] | None,
) -> str:
    if final_strategy == original_strategy or misconception_snapshot is None:
        return teaching_reason

    misconception_type = misconception_snapshot.get("misconception_type", "unknown")
    description = misconception_snapshot.get("description", "")
    confidence = misconception_snapshot.get("confidence", 0.0)
    return (
        f"{teaching_reason} Recent misconception evidence suggests "
        f"{misconception_type} with confidence {confidence:.2f}: {description}"
    )


def _misconception_aware_next_step(
    *,
    suggested_next_step: str,
    original_strategy: ResponseStrategy,
    final_strategy: ResponseStrategy,
) -> str:
    if final_strategy == original_strategy:
        return suggested_next_step

    if final_strategy == "contrastive":
        return (
            "Explain the confused concepts side by side, then ask a "
            "discriminative check."
        )
    if final_strategy == "definition_clarification":
        return "Clarify the correct definition, then test the key wording."
    if final_strategy == "prerequisite_scaffolded":
        return "Briefly rebuild the prerequisite before explaining the target concept."
    if final_strategy == "reasoning_guidance":
        return (
            "Guide the learner through the missing reasoning step before giving "
            "the final answer."
        )
    if final_strategy == "source_correction":
        return "Point back to the source excerpt and correct the likely misreading."
    return suggested_next_step


def _explicit_teaching_reason(
    *,
    selected_action: TeachingAction,
    response_strategy: ResponseStrategy,
    learner_state: LearnerState,
) -> str:
    action_text = {
        "explain": "an explanation",
        "hint": "a hint",
        "quiz": "practice",
        "review": "review",
        "refuse": "a refusal",
    }[selected_action]
    return (
        f"The learner explicitly requested {action_text}. The response should use "
        f"a {response_strategy} strategy based on mastery "
        f"{learner_state.mastery_score:.3f} and "
        f"{learner_state.consecutive_errors} consecutive errors."
    )


def _suggested_next_step(
    *,
    selected_action: TeachingAction,
    response_strategy: ResponseStrategy,
) -> str:
    if selected_action == "explain":
        if response_strategy == "scaffolded":
            return (
                "Provide a step-by-step explanation, then ask one diagnostic question."
            )
        return (
            "Provide a concise explanation and invite a follow-up practice question."
        )
    if selected_action == "hint":
        return "Give one targeted hint without revealing the full answer."
    if selected_action == "quiz":
        return (
            "Generate a traceable practice question from the current course evidence."
        )
    if selected_action == "review":
        return "Use due traceable review items before introducing new material."
    return "Ask the learner to provide or select more relevant course material."


def _learner_state_snapshot(state: LearnerState) -> dict[str, Any]:
    return {
        "user_id": state.user_id,
        "course_id": state.course_id,
        "mastery_score": state.mastery_score,
        "recent_accuracy": state.recent_accuracy,
        "attempt_count": state.attempt_count,
        "consecutive_errors": state.consecutive_errors,
        "last_reviewed_at": _serialize_datetime(state.last_reviewed_at),
        "review_due": state.review_due,
    }


def _evidence_state_snapshot(state: PolicyEvidenceState) -> dict[str, Any]:
    return {
        "evidence_strength": state.evidence_strength,
        "source_coverage": state.source_coverage,
        "retrieved_chunk_count": state.retrieved_chunk_count,
        "top_similarity": state.top_similarity,
        "requires_evidence": state.requires_evidence,
        "reason": state.reason,
        "retrieval_scope": state.retrieval_scope,
        "source_chunk_ids": state.source_chunk_ids,
    }


def _concept_state_snapshot(state: ConceptLearnerState) -> dict[str, Any]:
    return {
        "concept_id": state.concept_id,
        "concept_name": state.concept_name,
        "state_status": state.state_status,
        "mastery_score": state.mastery_score,
        "recent_accuracy": state.recent_accuracy,
        "attempt_count": state.attempt_count,
        "consecutive_errors": state.consecutive_errors,
        "last_attempted_at": _serialize_datetime(state.last_attempted_at),
        "review_due": state.review_due,
        "needs_attention": state.needs_attention,
    }


def _misconception_snapshot(misconception: Misconception) -> dict[str, Any]:
    return {
        "id": misconception.id,
        "misconception_type": misconception.misconception_type,
        "description": misconception.description,
        "confidence": misconception.confidence,
        "quiz_attempt_id": misconception.quiz_attempt_id,
        "concept_id": misconception.concept_id,
        "created_at": _serialize_datetime(misconception.created_at),
    }


def _is_unobserved_concept(snapshot: dict[str, Any] | None) -> bool:
    return snapshot is not None and snapshot.get("state_status") == "unobserved"


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
