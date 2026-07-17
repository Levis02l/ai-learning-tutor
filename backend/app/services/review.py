from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.quiz import QuizItem
from app.models.review import ReviewRecord


class ReviewError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewState:
    stability: float
    difficulty: float
    due_at: datetime


def submit_review(
    db: Session,
    *,
    user_id: str,
    item_id: int,
    rating: int,
    is_correct: bool,
    course_id: int | None = None,
) -> ReviewRecord:
    item_query = select(QuizItem).where(
        QuizItem.id == item_id, QuizItem.user_id == user_id
    )
    if course_id is not None:
        item_query = item_query.where(QuizItem.course_id == course_id)

    item = db.scalar(item_query)
    if item is None:
        raise ReviewError("Quiz item not found for this user")

    previous = _get_latest_review(db, user_id=user_id, item_id=item_id)
    now = datetime.utcnow()
    state = _schedule_next_review(
        rating=rating,
        is_correct=is_correct,
        reviewed_at=now,
        previous=previous,
    )
    review = ReviewRecord(
        user_id=user_id,
        course_id=item.course_id,
        item_id=item_id,
        rating=rating,
        is_correct=is_correct,
        reviewed_at=now,
        stability=state.stability,
        difficulty=state.difficulty,
        due_at=state.due_at,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def get_due_review_items(
    db: Session,
    *,
    user_id: str = "demo-user",
    course_id: int | None = None,
    limit: int = 20,
    now: datetime | None = None,
) -> list[tuple[QuizItem, ReviewRecord | None]]:
    current_time = now or datetime.utcnow()
    latest_review_query = select(func.max(ReviewRecord.id).label("latest_id")).where(
        ReviewRecord.user_id == user_id
    )
    if course_id is not None:
        latest_review_query = latest_review_query.where(
            ReviewRecord.course_id == course_id
        )

    latest_review_ids = latest_review_query.group_by(ReviewRecord.item_id).subquery()

    query = (
        select(QuizItem, ReviewRecord)
        .outerjoin(
            ReviewRecord,
            and_(
                ReviewRecord.item_id == QuizItem.id,
                ReviewRecord.id.in_(select(latest_review_ids.c.latest_id)),
            ),
        )
        .where(QuizItem.user_id == user_id)
        .where(or_(ReviewRecord.id.is_(None), ReviewRecord.due_at <= current_time))
    )
    if course_id is not None:
        query = query.where(QuizItem.course_id == course_id)

    rows = db.execute(
        query.order_by(
            ReviewRecord.due_at.asc().nullsfirst(),
            QuizItem.created_at.asc(),
        )
        .limit(limit)
    ).all()

    return [(item, review) for item, review in rows]


def _get_latest_review(
    db: Session,
    *,
    user_id: str,
    item_id: int,
) -> ReviewRecord | None:
    return db.scalar(
        select(ReviewRecord)
        .where(ReviewRecord.user_id == user_id, ReviewRecord.item_id == item_id)
        .order_by(ReviewRecord.reviewed_at.desc(), ReviewRecord.id.desc())
        .limit(1)
    )


def _schedule_next_review(
    *,
    rating: int,
    is_correct: bool,
    reviewed_at: datetime,
    previous: ReviewRecord | None = None,
) -> ReviewState:
    previous_stability = previous.stability if previous else 1.0
    previous_difficulty = previous.difficulty if previous else 5.0

    if rating == 1 or not is_correct:
        stability = max(0.5, previous_stability * 0.6)
        difficulty = min(10.0, previous_difficulty + 1.0)
        interval = timedelta(minutes=10)
    elif rating == 2:
        stability = max(1.0, previous_stability * 1.2)
        difficulty = min(10.0, previous_difficulty + 0.3)
        interval = timedelta(days=1)
    elif rating == 3:
        stability = max(2.0, previous_stability * 2.3)
        difficulty = max(1.0, previous_difficulty - 0.2)
        interval = timedelta(days=round(stability))
    else:
        stability = max(4.0, previous_stability * 3.0)
        difficulty = max(1.0, previous_difficulty - 0.6)
        interval = timedelta(days=round(stability))

    return ReviewState(
        stability=round(stability, 3),
        difficulty=round(difficulty, 3),
        due_at=reviewed_at + interval,
    )
