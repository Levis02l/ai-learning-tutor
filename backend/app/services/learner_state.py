from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.quiz import QuizItem
from app.models.review import ReviewRecord

RECENT_REVIEW_LIMIT = 10


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


def compute_learner_state(
    db: Session,
    *,
    user_id: str = "demo-user",
    course_id: int | None = None,
    now: datetime | None = None,
) -> LearnerState:
    current_time = now or datetime.utcnow()
    quiz_query = select(QuizItem).where(QuizItem.user_id == user_id)
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

    return _build_learner_state(
        user_id=user_id,
        course_id=course_id,
        quiz_items=quiz_items,
        reviews=reviews,
        now=current_time,
    )


def _build_learner_state(
    *,
    user_id: str,
    course_id: int | None,
    quiz_items: list[QuizItem],
    reviews: list[ReviewRecord],
    now: datetime,
) -> LearnerState:
    recent_reviews = reviews[:RECENT_REVIEW_LIMIT]
    attempt_count = len(reviews)
    recent_accuracy = _calculate_recent_accuracy(recent_reviews)
    consecutive_errors = _count_consecutive_errors(reviews)
    last_reviewed_at = reviews[0].reviewed_at if reviews else None
    review_due = _has_due_review(
        quiz_items=quiz_items,
        reviews=reviews,
        now=now,
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

