from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.quiz import QuizItem
from app.models.review import ReviewRecord


@dataclass(frozen=True)
class MasterySummary:
    total_items: int
    reviewed_items: int
    due_items: int
    average_mastery: float


@dataclass(frozen=True)
class MasteryItem:
    item_id: int
    question: str
    difficulty: str
    mastery_probability: float
    review_count: int
    latest_rating: int | None
    latest_is_correct: bool | None
    due_at: datetime | None
    is_due: bool


@dataclass(frozen=True)
class MasterySnapshot:
    user_id: str
    summary: MasterySummary
    items: list[MasteryItem]


def get_mastery_snapshot(
    db: Session,
    *,
    user_id: str = "demo-user",
    course_id: int | None = None,
    now: datetime | None = None,
) -> MasterySnapshot:
    current_time = now or datetime.utcnow()
    quiz_query = select(QuizItem).where(QuizItem.user_id == user_id)
    if course_id is not None:
        quiz_query = quiz_query.where(QuizItem.course_id == course_id)

    quiz_items = list(
        db.scalars(
            quiz_query.order_by(QuizItem.created_at.asc())
        )
    )
    review_stats = _load_review_stats(
        db=db, user_id=user_id, course_id=course_id
    )

    items = [
        _build_mastery_item(
            item=item,
            stats=review_stats.get(item.id),
            current_time=current_time,
        )
        for item in quiz_items
    ]
    total_items = len(items)
    reviewed_items = sum(1 for item in items if item.review_count > 0)
    due_items = sum(1 for item in items if item.is_due)
    average_mastery = (
        round(sum(item.mastery_probability for item in items) / total_items, 3)
        if total_items
        else 0.0
    )

    return MasterySnapshot(
        user_id=user_id,
        summary=MasterySummary(
            total_items=total_items,
            reviewed_items=reviewed_items,
            due_items=due_items,
            average_mastery=average_mastery,
        ),
        items=items,
    )


def _load_review_stats(
    db: Session,
    *,
    user_id: str,
    course_id: int | None = None,
) -> dict[int, tuple[int, ReviewRecord]]:
    latest_query = select(func.max(ReviewRecord.id).label("latest_id")).where(
        ReviewRecord.user_id == user_id
    )
    count_query = select(
        ReviewRecord.item_id.label("item_id"),
        func.count(ReviewRecord.id).label("review_count"),
    ).where(ReviewRecord.user_id == user_id)

    if course_id is not None:
        latest_query = latest_query.where(ReviewRecord.course_id == course_id)
        count_query = count_query.where(ReviewRecord.course_id == course_id)

    latest_ids = latest_query.group_by(ReviewRecord.item_id).subquery()
    review_counts = count_query.group_by(ReviewRecord.item_id).subquery()

    rows = db.execute(
        select(ReviewRecord, review_counts.c.review_count)
        .join(latest_ids, ReviewRecord.id == latest_ids.c.latest_id)
        .join(review_counts, ReviewRecord.item_id == review_counts.c.item_id)
    ).all()

    return {
        review.item_id: (int(review_count), review)
        for review, review_count in rows
    }


def _build_mastery_item(
    *,
    item: QuizItem,
    stats: tuple[int, ReviewRecord] | None,
    current_time: datetime,
) -> MasteryItem:
    if stats is None:
        return MasteryItem(
            item_id=item.id,
            question=item.question,
            difficulty=item.difficulty,
            mastery_probability=0.0,
            review_count=0,
            latest_rating=None,
            latest_is_correct=None,
            due_at=None,
            is_due=True,
        )

    review_count, latest_review = stats
    mastery = _estimate_mastery(latest_review=latest_review, review_count=review_count)
    return MasteryItem(
        item_id=item.id,
        question=item.question,
        difficulty=item.difficulty,
        mastery_probability=mastery,
        review_count=review_count,
        latest_rating=latest_review.rating,
        latest_is_correct=latest_review.is_correct,
        due_at=latest_review.due_at,
        is_due=latest_review.due_at <= current_time,
    )


def _estimate_mastery(*, latest_review: ReviewRecord, review_count: int) -> float:
    rating_component = latest_review.rating / 4
    correctness_component = 1.0 if latest_review.is_correct else 0.0
    stability_component = min(latest_review.stability / 10, 1.0)
    practice_component = min(review_count / 5, 1.0)

    mastery = (
        rating_component * 0.35
        + correctness_component * 0.35
        + stability_component * 0.2
        + practice_component * 0.1
    )
    return round(max(0.0, min(mastery, 1.0)), 3)
