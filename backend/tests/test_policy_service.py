from datetime import datetime

from app.services.learner_state import LearnerState
from app.services.policy import (
    PolicyEvidenceState,
    decide_teaching_action,
    detect_intent,
)


def test_detect_intent_prioritises_hint_before_explain() -> None:
    assert detect_intent("Give me a hint, don't tell me the answer") == "hint"


def test_policy_refuses_when_evidence_is_insufficient() -> None:
    decision = _decision(
        query="Quiz me on this missing topic",
        learner_state=_learner_state(mastery_score=0.8),
        evidence_state=_evidence("insufficient"),
    )

    assert decision.detected_intent == "practice"
    assert decision.selected_action == "refuse"
    assert decision.response_strategy == "refusal"
    assert decision.primary_reason == "insufficient_evidence"


def test_explicit_explain_with_low_mastery_uses_scaffolded_explanation() -> None:
    decision = _decision(
        query="Explain TCP congestion control",
        learner_state=_learner_state(mastery_score=0.2, consecutive_errors=2),
        evidence_state=_evidence("high"),
    )

    assert decision.detected_intent == "explain"
    assert decision.selected_action == "explain"
    assert decision.response_strategy == "scaffolded"
    assert decision.primary_reason == "explicit_explanation_request"


def test_explicit_explain_with_high_mastery_stays_explain_but_concise() -> None:
    decision = _decision(
        query="Explain TCP congestion control",
        learner_state=_learner_state(mastery_score=0.9, review_due=True),
        evidence_state=_evidence("high"),
    )

    assert decision.selected_action == "explain"
    assert decision.response_strategy == "concise"
    assert decision.primary_reason == "explicit_explanation_request"


def test_explicit_hint_returns_hint() -> None:
    decision = _decision(
        query="Give me a hint about routing",
        learner_state=_learner_state(mastery_score=0.55),
        evidence_state=_evidence("medium"),
    )

    assert decision.selected_action == "hint"
    assert decision.response_strategy == "guided"
    assert decision.primary_reason == "explicit_hint_request"


def test_explicit_practice_returns_quiz() -> None:
    decision = _decision(
        query="Quiz me on transport protocols",
        learner_state=_learner_state(mastery_score=0.82),
        evidence_state=_evidence("high"),
    )

    assert decision.detected_intent == "practice"
    assert decision.selected_action == "quiz"
    assert decision.response_strategy == "challenging"
    assert decision.primary_reason == "explicit_practice_request"


def test_unknown_with_due_review_items_returns_review() -> None:
    decision = _decision(
        query="What should I do next?",
        learner_state=_learner_state(mastery_score=0.7, review_due=True),
        evidence_state=_evidence("not_required", requires_evidence=False),
    )

    assert decision.detected_intent == "unknown"
    assert decision.selected_action == "review"
    assert decision.response_strategy == "review_drill"
    assert decision.primary_reason == "review_due"


def test_unknown_with_low_mastery_returns_explain() -> None:
    decision = _decision(
        query="I am stuck",
        learner_state=_learner_state(mastery_score=0.25),
        evidence_state=_evidence("medium"),
    )

    assert decision.selected_action == "explain"
    assert decision.response_strategy == "scaffolded"
    assert decision.primary_reason == "low_mastery"


def test_unknown_with_high_mastery_returns_quiz() -> None:
    decision = _decision(
        query="Next",
        learner_state=_learner_state(mastery_score=0.86),
        evidence_state=_evidence("high"),
    )

    assert decision.selected_action == "quiz"
    assert decision.response_strategy == "challenging"
    assert decision.primary_reason == "high_mastery"


def test_explicit_review_can_use_not_required_evidence() -> None:
    decision = _decision(
        query="Review the due questions with me",
        learner_state=_learner_state(mastery_score=0.6, review_due=True),
        evidence_state=_evidence("not_required", requires_evidence=False),
    )

    assert decision.detected_intent == "review"
    assert decision.selected_action == "review"
    assert decision.response_strategy == "review_drill"
    assert decision.primary_reason == "explicit_review_request"


def _decision(
    *,
    query: str,
    learner_state: LearnerState,
    evidence_state: PolicyEvidenceState,
):
    return decide_teaching_action(
        query=query,
        user_id="demo-user",
        course_id=1,
        learner_state=learner_state,
        evidence_state=evidence_state,
    )


def _learner_state(
    *,
    mastery_score: float,
    review_due: bool = False,
    consecutive_errors: int = 0,
) -> LearnerState:
    return LearnerState(
        user_id="demo-user",
        course_id=1,
        mastery_score=mastery_score,
        recent_accuracy=mastery_score,
        attempt_count=4,
        consecutive_errors=consecutive_errors,
        last_reviewed_at=datetime(2026, 7, 18, 12, 0, 0),
        review_due=review_due,
    )


def _evidence(
    evidence_strength,
    *,
    requires_evidence: bool = True,
) -> PolicyEvidenceState:
    return PolicyEvidenceState(
        evidence_strength=evidence_strength,
        source_coverage=1.0 if evidence_strength != "insufficient" else 0.0,
        retrieved_chunk_count=3 if evidence_strength != "not_required" else 0,
        top_similarity=0.7 if evidence_strength != "insufficient" else 0.0,
        requires_evidence=requires_evidence,
        reason="test evidence",
    )
