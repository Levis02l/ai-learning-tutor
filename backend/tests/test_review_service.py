from datetime import datetime

from app.services.review import _schedule_next_review


def test_schedule_next_review_repeats_failed_item_quickly() -> None:
    reviewed_at = datetime(2026, 6, 17, 12, 0, 0)

    state = _schedule_next_review(
        rating=1,
        is_correct=False,
        reviewed_at=reviewed_at,
    )

    assert state.due_at == datetime(2026, 6, 17, 12, 10, 0)
    assert state.difficulty > 5.0


def test_schedule_next_review_extends_easy_item() -> None:
    reviewed_at = datetime(2026, 6, 17, 12, 0, 0)

    state = _schedule_next_review(
        rating=4,
        is_correct=True,
        reviewed_at=reviewed_at,
    )

    assert state.due_at == datetime(2026, 6, 21, 12, 0, 0)
    assert state.stability == 4.0
    assert state.difficulty < 5.0
