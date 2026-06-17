from datetime import datetime, timedelta

from app.models.quiz import QuizItem
from app.models.review import ReviewRecord
from app.services.mastery import _build_mastery_item, _estimate_mastery


def test_build_mastery_item_marks_unreviewed_item_due() -> None:
    item = QuizItem(
        id=1,
        user_id="demo-user",
        question="What is AI?",
        answer="A field studying intelligent agents.",
        difficulty="medium",
        source_chunk_ids=[82],
        created_at=datetime(2026, 6, 17, 12, 0, 0),
    )

    mastery_item = _build_mastery_item(
        item=item,
        stats=None,
        current_time=datetime(2026, 6, 17, 13, 0, 0),
    )

    assert mastery_item.mastery_probability == 0.0
    assert mastery_item.review_count == 0
    assert mastery_item.is_due is True


def test_estimate_mastery_increases_for_correct_good_review() -> None:
    review = ReviewRecord(
        id=1,
        user_id="demo-user",
        item_id=1,
        rating=4,
        is_correct=True,
        reviewed_at=datetime(2026, 6, 17, 12, 0, 0),
        stability=4.0,
        difficulty=4.4,
        due_at=datetime(2026, 6, 21, 12, 0, 0),
    )

    mastery = _estimate_mastery(latest_review=review, review_count=2)

    assert mastery > 0.7


def test_build_mastery_item_marks_future_review_not_due() -> None:
    current_time = datetime(2026, 6, 17, 12, 0, 0)
    item = QuizItem(
        id=1,
        user_id="demo-user",
        question="What is AI?",
        answer="A field studying intelligent agents.",
        difficulty="medium",
        source_chunk_ids=[82],
        created_at=current_time,
    )
    review = ReviewRecord(
        id=1,
        user_id="demo-user",
        item_id=1,
        rating=3,
        is_correct=True,
        reviewed_at=current_time,
        stability=2.3,
        difficulty=4.8,
        due_at=current_time + timedelta(days=2),
    )

    mastery_item = _build_mastery_item(
        item=item,
        stats=(1, review),
        current_time=current_time,
    )

    assert mastery_item.review_count == 1
    assert mastery_item.latest_rating == 3
    assert mastery_item.is_due is False
