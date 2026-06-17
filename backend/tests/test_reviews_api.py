from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.models.quiz import QuizItem
from app.models.review import ReviewRecord
from app.services.review import ReviewError


def test_review_submit_validation_rejects_invalid_rating() -> None:
    client = TestClient(app)

    response = client.post(
        "/reviews",
        json={"item_id": 1, "rating": 5, "is_correct": True},
    )

    assert response.status_code == 422


def test_review_submit_returns_record(monkeypatch) -> None:
    reviewed_at = datetime(2026, 6, 17, 12, 0, 0)
    due_at = datetime(2026, 6, 19, 12, 0, 0)

    def fake_submit_review(*args, **kwargs):  # type: ignore[no-untyped-def]
        return ReviewRecord(
            id=1,
            user_id="demo-user",
            item_id=1,
            rating=3,
            is_correct=True,
            reviewed_at=reviewed_at,
            stability=2.3,
            difficulty=4.8,
            due_at=due_at,
        )

    monkeypatch.setattr("app.api.reviews.submit_review", fake_submit_review)
    client = TestClient(app)

    response = client.post(
        "/reviews",
        json={"item_id": 1, "rating": 3, "is_correct": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] == 1
    assert body["due_at"] == "2026-06-19T12:00:00"


def test_review_submit_returns_404_for_missing_item(monkeypatch) -> None:
    def raise_missing_item(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise ReviewError("Quiz item not found for this user")

    monkeypatch.setattr("app.api.reviews.submit_review", raise_missing_item)
    client = TestClient(app)

    response = client.post(
        "/reviews",
        json={"item_id": 999, "rating": 3, "is_correct": True},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Quiz item not found for this user"


def test_due_reviews_returns_items(monkeypatch) -> None:
    created_at = datetime(2026, 6, 17, 12, 0, 0)

    def fake_due_items(*args, **kwargs):  # type: ignore[no-untyped-def]
        return [
            (
                QuizItem(
                    id=1,
                    user_id="demo-user",
                    question="What is AI?",
                    answer="A field studying intelligent agents.",
                    difficulty="medium",
                    source_chunk_ids=[82],
                    created_at=created_at,
                ),
                None,
            )
        ]

    monkeypatch.setattr("app.api.reviews.get_due_review_items", fake_due_items)
    client = TestClient(app)

    response = client.get("/reviews/due")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["item"]["question"] == "What is AI?"
    assert body[0]["latest_review"] is None
