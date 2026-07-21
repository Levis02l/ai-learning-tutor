from datetime import datetime

import pytest

from app.models.policy import PolicyDecisionRecord
from app.models.quiz import QuizAttempt, QuizItem
from app.services.learner_state import LearnerState
from app.services.tutor_outcome import (
    TutorOutcomeCompatibilityError,
    TutorOutcomeScopeError,
    record_tutor_outcome,
)


def test_record_quiz_outcome_links_attempt_without_regrading(monkeypatch) -> None:
    decision = _decision(selected_action="quiz")
    attempt = QuizAttempt(
        id=9,
        user_id="demo-user",
        course_id=4,
        quiz_item_id=22,
        selected_option_id="A",
        selected_option_text="wrong answer",
        correct_option_id="B",
        correct_option_text="right answer",
        is_correct=False,
        attempted_at=datetime(2026, 7, 21, 10, 0, 0),
    )
    db = _FakeSession(decision=decision, event=attempt)

    monkeypatch.setattr(
        "app.services.tutor_outcome.compute_learner_state",
        lambda **kwargs: LearnerState(
            user_id="demo-user",
            course_id=4,
            mastery_score=0.42,
            recent_accuracy=0.4,
            attempt_count=5,
            consecutive_errors=2,
            last_reviewed_at=datetime(2026, 7, 21, 10, 0, 0),
            review_due=True,
        ),
    )

    outcome = record_tutor_outcome(
        db,  # type: ignore[arg-type]
        decision_id=12,
        outcome_type="quiz_attempt",
        quiz_attempt_id=9,
    )

    assert outcome["type"] == "quiz_attempt"
    assert outcome["quiz_attempt_id"] == 9
    assert outcome["is_correct"] is False
    assert outcome["learner_state_after"]["mastery_score"] == 0.42
    assert decision.outcome == outcome
    assert db.committed is True


def test_record_quiz_outcome_rejects_non_quiz_decision() -> None:
    attempt = QuizAttempt(
        id=9,
        user_id="demo-user",
        course_id=4,
        quiz_item_id=22,
        selected_option_id="A",
        selected_option_text="wrong answer",
        correct_option_id="B",
        correct_option_text="right answer",
        is_correct=False,
        attempted_at=datetime(2026, 7, 21, 10, 0, 0),
    )
    attempt.quiz_item = _quiz_item(origin="manual_practice")
    db = _FakeSession(
        decision=_decision(selected_action="explain"),
        event=attempt,
    )

    with pytest.raises(TutorOutcomeCompatibilityError):
        record_tutor_outcome(
            db,  # type: ignore[arg-type]
            decision_id=12,
            outcome_type="quiz_attempt",
            quiz_attempt_id=9,
        )


def test_record_comprehension_check_outcome_links_to_explain_decision(
    monkeypatch,
) -> None:
    decision = _decision(selected_action="explain")
    attempt = QuizAttempt(
        id=9,
        user_id="demo-user",
        course_id=4,
        quiz_item_id=22,
        selected_option_id="B",
        selected_option_text="right answer",
        correct_option_id="B",
        correct_option_text="right answer",
        is_correct=True,
        attempted_at=datetime(2026, 7, 21, 10, 0, 0),
    )
    attempt.quiz_item = _quiz_item(origin="comprehension_check")
    db = _FakeSession(decision=decision, event=attempt)

    monkeypatch.setattr(
        "app.services.tutor_outcome.compute_learner_state",
        lambda **kwargs: LearnerState(
            user_id="demo-user",
            course_id=4,
            mastery_score=0.64,
            recent_accuracy=1.0,
            attempt_count=1,
            consecutive_errors=0,
            last_reviewed_at=datetime(2026, 7, 21, 10, 0, 0),
            review_due=False,
        ),
    )

    outcome = record_tutor_outcome(
        db,  # type: ignore[arg-type]
        decision_id=12,
        outcome_type="quiz_attempt",
        quiz_attempt_id=9,
    )

    assert outcome["quiz_origin"] == "comprehension_check"
    assert outcome["is_correct"] is True
    assert outcome["learner_state_after"]["mastery_score"] == 0.64
    assert decision.outcome == outcome


def test_record_quiz_outcome_rejects_different_course() -> None:
    decision = _decision(selected_action="quiz")
    attempt = QuizAttempt(
        id=9,
        user_id="demo-user",
        course_id=8,
        quiz_item_id=22,
        selected_option_id="A",
        selected_option_text="wrong answer",
        correct_option_id="B",
        correct_option_text="right answer",
        is_correct=False,
        attempted_at=datetime(2026, 7, 21, 10, 0, 0),
    )
    db = _FakeSession(decision=decision, event=attempt)

    with pytest.raises(TutorOutcomeScopeError):
        record_tutor_outcome(
            db,  # type: ignore[arg-type]
            decision_id=12,
            outcome_type="quiz_attempt",
            quiz_attempt_id=9,
        )


class _FakeSession:
    def __init__(
        self,
        *,
        decision: PolicyDecisionRecord | None,
        event: object | None,
    ) -> None:
        self.decision = decision
        self.event = event
        self.committed = False

    def get(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self.decision

    def scalar(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self.event

    def add(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    def commit(self) -> None:
        self.committed = True

    def refresh(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None


def _decision(*, selected_action: str) -> PolicyDecisionRecord:
    return PolicyDecisionRecord(
        id=12,
        user_id="demo-user",
        course_id=4,
        query="Practice this",
        detected_intent="practice",
        learner_state_snapshot={},
        evidence_state_snapshot={},
        selected_action=selected_action,
        response_strategy="challenging",
        primary_reason="explicit_practice_request",
        teaching_reason="Practice requested.",
        suggested_next_step="Answer one traceable question.",
        policy_version="rule_v1",
    )


def _quiz_item(*, origin: str) -> QuizItem:
    return QuizItem(
        id=22,
        user_id="demo-user",
        course_id=4,
        question="Question?",
        answer="Answer.",
        difficulty="easy",
        origin=origin,
        source_chunk_ids=[1],
        evidence_quote="Evidence.",
        options=[],
        correct_option_id="B",
        explanation="Explanation.",
        question_type="conceptual",
        traceability_label="fully_traceable",
    )
