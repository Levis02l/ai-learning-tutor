from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.quiz import QuizAttempt, QuizItem
from app.models.review import ReviewRecord

RECENT_REVIEW_LIMIT = 10
RECENT_ATTEMPT_LIMIT = 10


@dataclass(frozen=True)
class LearnerState:
    user_id: str
    course_id: int | None
    mastery_score: float
    recent_accuracy: float
    attempt_count: int
    consecutive_errors: int
    last_reviewed_at: datetime | None
    review_due: bool


@dataclass(frozen=True)
class AttemptStateMetrics:
    mastery_score: float
    recent_accuracy: float
    attempt_count: int
    consecutive_errors: int
    last_attempted_at: datetime | None
    needs_attention: bool


def compute_learner_state(
    db: Session,
    *,
    user_id: str = "demo-user",
    course_id: int | None = None,
    now: datetime | None = None,
) -> LearnerState:
    current_time = now or datetime.utcnow()
    quiz_query = select(QuizItem).where(
        QuizItem.user_id == user_id,
        QuizItem.archived_at.is_(None),
    )
    if course_id is not None:
        quiz_query = quiz_query.where(QuizItem.course_id == course_id)

    quiz_items = list(db.scalars(quiz_query.order_by(QuizItem.created_at.asc())))

    review_query = select(ReviewRecord).where(ReviewRecord.user_id == user_id)
    if course_id is not None:
        review_query = review_query.where(ReviewRecord.course_id == course_id)

    reviews = list(
        db.scalars(
            review_query.order_by(
                ReviewRecord.reviewed_at.desc(),
                ReviewRecord.id.desc(),
            )
        )
    )
    attempt_query = select(QuizAttempt).where(QuizAttempt.user_id == user_id)
    if course_id is not None:
        attempt_query = attempt_query.where(QuizAttempt.course_id == course_id)

    attempts = list(
        db.scalars(
            attempt_query.order_by(
                QuizAttempt.attempted_at.desc(),
                QuizAttempt.id.desc(),
            )
        )
    )

    return _build_learner_state(
        user_id=user_id,
        course_id=course_id,
        quiz_items=quiz_items,
        attempts=attempts,
        reviews=reviews,
        now=current_time,
    )


def _build_learner_state(
    *,
    user_id: str,
    course_id: int | None,
    quiz_items: list[QuizItem],
    attempts: list[QuizAttempt] | None = None,
    reviews: list[ReviewRecord] | None = None,
    now: datetime | None = None,
) -> LearnerState:
    current_time = now or datetime.utcnow()
    attempts = attempts or []
    reviews = reviews or []
    if attempts:
        return _build_learner_state_from_attempts(
            user_id=user_id,
            course_id=course_id,
            quiz_items=quiz_items,
            attempts=attempts,
        )

    recent_reviews = reviews[:RECENT_REVIEW_LIMIT]
    attempt_count = len(reviews)
    recent_accuracy = _calculate_recent_accuracy(recent_reviews)
    consecutive_errors = _count_consecutive_errors(reviews)
    last_reviewed_at = reviews[0].reviewed_at if reviews else None
    review_due = _has_due_review(
        quiz_items=quiz_items,
        reviews=reviews,
        now=current_time,
    )
    mastery_score = _estimate_mastery_score(
        quiz_items=quiz_items,
        recent_reviews=recent_reviews,
        recent_accuracy=recent_accuracy,
        review_due=review_due,
        consecutive_errors=consecutive_errors,
    )

    return LearnerState(
        user_id=user_id,
        course_id=course_id,
        mastery_score=mastery_score,
        recent_accuracy=recent_accuracy,
        attempt_count=attempt_count,
        consecutive_errors=consecutive_errors,
        last_reviewed_at=last_reviewed_at,
        review_due=review_due,
    )


def _build_learner_state_from_attempts(
    *,
    user_id: str,
    course_id: int | None,
    quiz_items: list[QuizItem],
    attempts: list[QuizAttempt],
) -> LearnerState:
    metrics = _calculate_attempt_state_metrics(
        quiz_items=quiz_items,
        attempts=attempts,
        due_penalty=False,
    )
    review_due = _has_due_attempt(
        quiz_items=quiz_items,
        attempts=attempts,
        recent_accuracy=metrics.recent_accuracy,
        consecutive_errors=metrics.consecutive_errors,
    )
    metrics = _calculate_attempt_state_metrics(
        quiz_items=quiz_items,
        attempts=attempts,
        due_penalty=review_due,
    )

    return LearnerState(
        user_id=user_id,
        course_id=course_id,
        mastery_score=metrics.mastery_score,
        recent_accuracy=metrics.recent_accuracy,
        attempt_count=metrics.attempt_count,
        consecutive_errors=metrics.consecutive_errors,
        last_reviewed_at=metrics.last_attempted_at,
        review_due=review_due,
    )


def _calculate_attempt_state_metrics(
    *,
    quiz_items: list[QuizItem],
    attempts: list[QuizAttempt],
    due_penalty: bool,
) -> AttemptStateMetrics:
    recent_attempts = attempts[:RECENT_ATTEMPT_LIMIT]
    attempt_count = len(attempts)
    recent_accuracy = _calculate_attempt_accuracy(recent_attempts)
    consecutive_errors = _count_consecutive_attempt_errors(attempts)
    mastery_score = _estimate_attempt_mastery_score(
        quiz_items=quiz_items,
        recent_attempts=recent_attempts,
        recent_accuracy=recent_accuracy,
        review_due=due_penalty,
        consecutive_errors=consecutive_errors,
    )
    return AttemptStateMetrics(
        mastery_score=mastery_score,
        recent_accuracy=recent_accuracy,
        attempt_count=attempt_count,
        consecutive_errors=consecutive_errors,
        last_attempted_at=attempts[0].attempted_at if attempts else None,
        needs_attention=(
            attempt_count > 0
            and (
                recent_accuracy < 0.5
                or consecutive_errors >= 2
                or mastery_score < 0.4
            )
        ),
    )


def _calculate_attempt_accuracy(attempts: list[QuizAttempt]) -> float:
    if not attempts:
        return 0.0
    correct = sum(1 for attempt in attempts if attempt.is_correct)
    return round(correct / len(attempts), 3)


def _count_consecutive_attempt_errors(attempts: list[QuizAttempt]) -> int:
    count = 0
    for attempt in attempts:
        if attempt.is_correct:
            break
        count += 1
    return count


def _has_due_attempt(
    *,
    quiz_items: list[QuizItem],
    attempts: list[QuizAttempt],
    recent_accuracy: float,
    consecutive_errors: int,
) -> bool:
    if not quiz_items:
        return False
    attempted_item_ids = {attempt.quiz_item_id for attempt in attempts}
    has_unattempted_item = any(item.id not in attempted_item_ids for item in quiz_items)
    return has_unattempted_item or recent_accuracy < 0.5 or consecutive_errors >= 2


def _estimate_attempt_mastery_score(
    *,
    quiz_items: list[QuizItem],
    recent_attempts: list[QuizAttempt],
    recent_accuracy: float,
    review_due: bool,
    consecutive_errors: int,
) -> float:
    if not quiz_items or not recent_attempts:
        return 0.0

    attempted_item_ids = {attempt.quiz_item_id for attempt in recent_attempts}
    coverage = min(len(attempted_item_ids) / len(quiz_items), 1.0)
    due_penalty = 0.1 if review_due else 0.0
    error_penalty = min(consecutive_errors / 10, 0.2)

    score = recent_accuracy * 0.65 + coverage * 0.35 - due_penalty - error_penalty
    return round(max(0.0, min(score, 1.0)), 3)


def _calculate_recent_accuracy(reviews: list[ReviewRecord]) -> float:
    if not reviews:
        return 0.0
    correct = sum(1 for review in reviews if review.is_correct)
    return round(correct / len(reviews), 3)


def _count_consecutive_errors(reviews: list[ReviewRecord]) -> int:
    count = 0
    for review in reviews:
        if review.is_correct:
            break
        count += 1
    return count


def _has_due_review(
    *,
    quiz_items: list[QuizItem],
    reviews: list[ReviewRecord],
    now: datetime,
) -> bool:
    if not quiz_items:
        return False

    latest_by_item: dict[int, ReviewRecord] = {}
    for review in reviews:
        latest_by_item.setdefault(review.item_id, review)

    for item in quiz_items:
        latest_review = latest_by_item.get(item.id)
        if latest_review is None or latest_review.due_at <= now:
            return True
    return False


def _estimate_mastery_score(
    *,
    quiz_items: list[QuizItem],
    recent_reviews: list[ReviewRecord],
    recent_accuracy: float,
    review_due: bool,
    consecutive_errors: int,
) -> float:
    if not quiz_items or not recent_reviews:
        return 0.0

    reviewed_item_ids = {review.item_id for review in recent_reviews}
    coverage = min(len(reviewed_item_ids) / len(quiz_items), 1.0)
    average_rating = sum(review.rating for review in recent_reviews) / (
        len(recent_reviews) * 4
    )
    due_penalty = 0.1 if review_due else 0.0
    error_penalty = min(consecutive_errors / 10, 0.2)

    score = (
        recent_accuracy * 0.5
        + average_rating * 0.25
        + coverage * 0.25
        - due_penalty
        - error_penalty
    )
    return round(max(0.0, min(score, 1.0)), 3)
