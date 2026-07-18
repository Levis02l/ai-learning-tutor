from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.policy import PolicyDecisionRecord
from app.services.learner_state import LearnerState, compute_learner_state
from app.services.retrieval import RetrievedChunk, retrieve_relevant_chunks
from app.services.review import get_due_review_items

POLICY_VERSION = "rule_v1"

DetectedIntent = Literal["explain", "hint", "practice", "review", "unknown"]
TeachingAction = Literal["explain", "hint", "quiz", "review", "refuse"]
ResponseStrategy = Literal[
    "scaffolded",
    "guided",
    "concise",
    "challenging",
    "refusal",
    "review_drill",
]
PolicyEvidenceStrength = Literal[
    "high",
    "medium",
    "low",
    "insufficient",
    "not_required",
]


@dataclass(frozen=True)
class PolicyEvidenceState:
    evidence_strength: PolicyEvidenceStrength
    source_coverage: float
    retrieved_chunk_count: int
    top_similarity: float
    requires_evidence: bool
    reason: str


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


def create_policy_decision(
    db: Session,
    *,
    query: str,
    user_id: str = "demo-user",
    course_id: int | None = None,
    top_k: int = 5,
) -> PolicyDecision:
    learner_state = compute_learner_state(
        db=db,
        user_id=user_id,
        course_id=course_id,
    )
    detected_intent = detect_intent(query)
    has_due_review_item = bool(
        get_due_review_items(
            db=db,
            user_id=user_id,
            course_id=course_id,
            limit=1,
        )
    )
    evidence_state = _resolve_evidence_state(
        db=db,
        query=query,
        user_id=user_id,
        course_id=course_id,
        top_k=top_k,
        detected_intent=detected_intent,
        learner_state=learner_state,
        has_due_review_item=has_due_review_item,
    )
    decision = decide_teaching_action(
        query=query,
        user_id=user_id,
        course_id=course_id,
        learner_state=learner_state,
        evidence_state=evidence_state,
        detected_intent=detected_intent,
    )
    record = PolicyDecisionRecord(
        user_id=user_id,
        course_id=course_id,
        query=query,
        detected_intent=decision.detected_intent,
        learner_state_snapshot=decision.learner_state_snapshot,
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
) -> PolicyDecision:
    intent = detected_intent or detect_intent(query)
    learner_snapshot = _learner_state_snapshot(learner_state)
    evidence_snapshot = _evidence_state_snapshot(evidence_state)

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
    return _evidence_from_chunks(chunks)


def _resolve_evidence_state(
    *,
    db: Session,
    query: str,
    user_id: str,
    course_id: int | None,
    top_k: int,
    detected_intent: DetectedIntent,
    learner_state: LearnerState,
    has_due_review_item: bool,
) -> PolicyEvidenceState:
    if has_due_review_item and (
        detected_intent == "review"
        or (detected_intent == "unknown" and learner_state.review_due)
    ):
        return PolicyEvidenceState(
            evidence_strength="not_required",
            source_coverage=1.0,
            retrieved_chunk_count=0,
            top_similarity=0.0,
            requires_evidence=False,
            reason=(
                "Existing due review items are already traceable, so new "
                "retrieval evidence is not required for this decision."
            ),
        )

    return build_retrieval_evidence_state(
        db=db,
        query=query,
        user_id=user_id,
        course_id=course_id,
        top_k=top_k,
    )


def _contains_phrase(normalized_query: str, phrases: list[str]) -> bool:
    return any(phrase in normalized_query for phrase in phrases)


def _evidence_from_chunks(chunks: list[RetrievedChunk]) -> PolicyEvidenceState:
    if not chunks:
        return PolicyEvidenceState(
            evidence_strength="insufficient",
            source_coverage=0.0,
            retrieved_chunk_count=0,
            top_similarity=0.0,
            requires_evidence=True,
            reason="No relevant course chunks were retrieved.",
        )

    top_similarity = round(max(chunk.similarity for chunk in chunks), 3)
    source_coverage = round(
        sum(1 for chunk in chunks if chunk.similarity >= 0.35) / len(chunks),
        3,
    )
    if top_similarity >= 0.55:
        evidence_strength: PolicyEvidenceStrength = "high"
    elif top_similarity >= 0.4:
        evidence_strength = "medium"
    elif top_similarity >= 0.3:
        evidence_strength = "low"
    else:
        evidence_strength = "insufficient"

    return PolicyEvidenceState(
        evidence_strength=evidence_strength,
        source_coverage=source_coverage,
        retrieved_chunk_count=len(chunks),
        top_similarity=top_similarity,
        requires_evidence=True,
        reason=f"Top retrieval similarity is {top_similarity}.",
    )


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
) -> PolicyDecision:
    return PolicyDecision(
        decision_id=None,
        user_id=user_id,
        course_id=course_id,
        query=query,
        detected_intent=detected_intent,
        selected_action=selected_action,
        response_strategy=response_strategy,
        primary_reason=primary_reason,
        teaching_reason=teaching_reason,
        suggested_next_step=suggested_next_step,
        policy_version=POLICY_VERSION,
        learner_state_snapshot=learner_state_snapshot,
        evidence_state_snapshot=evidence_state_snapshot,
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
    }


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
