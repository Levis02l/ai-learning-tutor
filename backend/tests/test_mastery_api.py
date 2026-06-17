from fastapi.testclient import TestClient

from app.main import app
from app.services.mastery import MasteryItem, MasterySnapshot, MasterySummary


def test_mastery_endpoint_returns_snapshot(monkeypatch) -> None:
    def fake_snapshot(*args, **kwargs):  # type: ignore[no-untyped-def]
        return MasterySnapshot(
            user_id="demo-user",
            summary=MasterySummary(
                total_items=1,
                reviewed_items=0,
                due_items=1,
                average_mastery=0.0,
            ),
            items=[
                MasteryItem(
                    item_id=1,
                    question="What is AI?",
                    difficulty="medium",
                    mastery_probability=0.0,
                    review_count=0,
                    latest_rating=None,
                    latest_is_correct=None,
                    due_at=None,
                    is_due=True,
                )
            ],
        )

    monkeypatch.setattr("app.api.mastery.get_mastery_snapshot", fake_snapshot)
    client = TestClient(app)

    response = client.get("/mastery")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total_items"] == 1
    assert body["items"][0]["is_due"] is True
