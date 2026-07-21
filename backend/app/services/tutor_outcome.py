from datetime import datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.policy import PolicyDecisionRecord
from app.models.quiz import QuizAttempt
from app.models.review import ReviewRecord
from app.services.learner_state import LearnerState, compute_learner_state

TutorOutcomeType = Literal["quiz_attempt", "review"]


class TutorOutcomeError(RuntimeError):
    pass


class TutorOutcomeNotFoundError(TutorOutcomeError):
    pass


class TutorOutcomeScopeError(TutorOutcomeError):
    pass


class TutorOutcomeCompatibilityError(TutorOutcomeError):
    pass


def record_tutor_outcome(
    db: Session,
    *,
    decision_id: int,
    outcome_type: TutorOutcomeType,
    quiz_attempt_id: int | None = None,
    review_record_id: int | None = None,
) -> dict[str, Any]:
    decision = db.get(PolicyDecisionRecord, decision_id)
    if decision is None:
        raise TutorOutcomeNotFoundError("Tutor decision not found")

    if outcome_type == "quiz_attempt":
        if quiz_attempt_id is None:
            raise TutorOutcomeCompatibilityError("quiz_attempt_id is required")
        outcome = _quiz_attempt_outcome(
            db=db,
            decision=decision,
            quiz_attempt_id=quiz_attempt_id,
        )
    elif outcome_type == "review":
        if review_record_id is None:
            raise TutorOutcomeCompatibilityError("review_record_id is required")
        outcome = _review_outcome(
            db=db,
            decision=decision,
            review_record_id=review_record_id,
        )
    else:
        raise TutorOutcomeCompatibilityError("Unsupported tutor outcome type")

    learner_state_after = compute_learner_state(
        db=db,
        user_id=decision.user_id,
        course_id=decision.course_id,
    )
    outcome["learner_state_after"] = _learner_state_snapshot(learner_state_after)
    outcome["recorded_at"] = datetime.utcnow().isoformat()

    decision.outcome = outcome
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return outcome


def _quiz_attempt_outcome(
    *,
    db: Session,
    decision: PolicyDecisionRecord,
    quiz_attempt_id: int,
) -> dict[str, Any]:
    attempt = db.scalar(select(QuizAttempt).where(QuizAttempt.id == quiz_attempt_id))
    if attempt is None:
        raise TutorOutcomeNotFoundError("Quiz attempt not found")

    _validate_quiz_attempt_compatibility(decision=decision, attempt=attempt)

    _validate_scope(
        decision=decision,
        event_user_id=attempt.user_id,
        event_course_id=attempt.course_id,
    )
    return {
        "type": "quiz_attempt",
        "reference_id": attempt.id,
        "quiz_attempt_id": attempt.id,
        "quiz_item_id": attempt.quiz_item_id,
        "quiz_origin": _quiz_attempt_origin(attempt),
        "is_correct": attempt.is_correct,
        "score": 1 if attempt.is_correct else 0,
        "selected_option_id": attempt.selected_option_id,
        "selected_option_text": attempt.selected_option_text,
        "correct_option_id": attempt.correct_option_id,
        "correct_option_text": attempt.correct_option_text,
        "observed_at": _serialize_datetime(attempt.attempted_at),
    }


def _validate_quiz_attempt_compatibility(
    *,
    decision: PolicyDecisionRecord,
    attempt: QuizAttempt,
) -> None:
    if decision.selected_action == "quiz":
        return
    if (
        decision.selected_action == "explain"
        and _quiz_attempt_origin(attempt) == "comprehension_check"
    ):
        return
    raise TutorOutcomeCompatibilityError(
        "Quiz attempts can only be linked to quiz tutor decisions or "
        "comprehension checks from explain decisions"
    )


def _quiz_attempt_origin(attempt: QuizAttempt) -> str:
    item = getattr(attempt, "quiz_item", None)
    return getattr(item, "origin", None) or "manual_practice"


def _review_outcome(
    *,
    db: Session,
    decision: PolicyDecisionRecord,
    review_record_id: int,
) -> dict[str, Any]:
    if decision.selected_action != "review":
        raise TutorOutcomeCompatibilityError(
            "Review records can only be linked to review tutor decisions"
        )

    review = db.scalar(select(ReviewRecord).where(ReviewRecord.id == review_record_id))
    if review is None:
        raise TutorOutcomeNotFoundError("Review record not found")

    _validate_scope(
        decision=decision,
        event_user_id=review.user_id,
        event_course_id=review.course_id,
    )
    return {
        "type": "review",
        "reference_id": review.id,
        "review_record_id": review.id,
        "item_id": review.item_id,
        "rating": review.rating,
        "is_correct": review.is_correct,
        "score": 1 if review.is_correct else 0,
        "stability": review.stability,
        "difficulty": review.difficulty,
        "due_at": _serialize_datetime(review.due_at),
        "observed_at": _serialize_datetime(review.reviewed_at),
    }


def _validate_scope(
    *,
    decision: PolicyDecisionRecord,
    event_user_id: str,
    event_course_id: int | None,
) -> None:
    if decision.user_id != event_user_id:
        raise TutorOutcomeScopeError("Outcome belongs to a different user")
    if decision.course_id is not None and decision.course_id != event_course_id:
        raise TutorOutcomeScopeError("Outcome belongs to a different course")


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


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
