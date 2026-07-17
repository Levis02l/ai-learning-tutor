from datetime import datetime, timedelta

from app.models.quiz import QuizItem
from app.models.review import ReviewRecord
from app.services.learner_state import _build_learner_state


def test_learner_state_empty_course_has_zero_state() -> None:
    state = _build_learner_state(
        user_id="demo-user",
        course_id=1,
        quiz_items=[],
        reviews=[],
        now=datetime(2026, 7, 17, 12, 0, 0),
    )

    assert state.mastery_score == 0.0
    assert state.recent_accuracy == 0.0
    assert state.attempt_count == 0
    assert state.consecutive_errors == 0
    assert state.last_reviewed_at is None
    assert state.review_due is False


def test_learner_state_tracks_recent_accuracy_and_error_streak() -> None:
    now = datetime(2026, 7, 17, 12, 0, 0)
    item = _quiz_item(item_id=1, course_id=3, created_at=now)
    reviews = [
        _review(
            review_id=3,
            item_id=1,
            course_id=3,
            is_correct=False,
            rating=1,
            reviewed_at=now,
            due_at=now + timedelta(minutes=10),
        ),
        _review(
            review_id=2,
            item_id=1,
            course_id=3,
            is_correct=False,
            rating=2,
            reviewed_at=now - timedelta(minutes=5),
            due_at=now + timedelta(days=1),
        ),
        _review(
            review_id=1,
            item_id=1,
            course_id=3,
            is_correct=True,
            rating=4,
            reviewed_at=now - timedelta(minutes=10),
            due_at=now + timedelta(days=4),
        ),
    ]

    state = _build_learner_state(
        user_id="demo-user",
        course_id=3,
        quiz_items=[item],
        reviews=reviews,
        now=now,
    )

    assert state.attempt_count == 3
    assert state.recent_accuracy == 0.333
    assert state.consecutive_errors == 2
    assert state.last_reviewed_at == now
    assert state.review_due is False
    assert 0.0 < state.mastery_score < 1.0


def test_learner_state_marks_unreviewed_items_due() -> None:
    now = datetime(2026, 7, 17, 12, 0, 0)

    state = _build_learner_state(
        user_id="demo-user",
        course_id=3,
        quiz_items=[
            _quiz_item(item_id=1, course_id=3, created_at=now),
            _quiz_item(item_id=2, course_id=3, created_at=now),
        ],
        reviews=[
            _review(
                review_id=1,
                item_id=1,
                course_id=3,
                is_correct=True,
                rating=4,
                reviewed_at=now,
                due_at=now + timedelta(days=4),
            )
        ],
        now=now,
    )

    assert state.review_due is True


def _quiz_item(*, item_id: int, course_id: int, created_at: datetime) -> QuizItem:
    return QuizItem(
        id=item_id,
        user_id="demo-user",
        course_id=course_id,
        question="Question?",
        answer="Answer.",
        difficulty="medium",
        source_chunk_ids=[1],
        evidence_quote="Evidence.",
        question_type="conceptual",
        traceability_label="fully_traceable",
        created_at=created_at,
    )


def _review(
    *,
    review_id: int,
    item_id: int,
    course_id: int,
    is_correct: bool,
    rating: int,
    reviewed_at: datetime,
    due_at: datetime,
) -> ReviewRecord:
    return ReviewRecord(
        id=review_id,
        user_id="demo-user",
        course_id=course_id,
        item_id=item_id,
        rating=rating,
        is_correct=is_correct,
        reviewed_at=reviewed_at,
        stability=2.0,
        difficulty=5.0,
        due_at=due_at,
    )

