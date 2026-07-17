from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.services.courses import CourseNotFoundError
from app.services.learner_state import LearnerState


def test_learner_state_api_returns_state(monkeypatch) -> None:
    captured: dict[str, int | None] = {}
    reviewed_at = datetime(2026, 7, 17, 12, 0, 0)

    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["validated_course_id"] = kwargs["course_id"]

    def fake_compute(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["computed_course_id"] = kwargs["course_id"]
        return LearnerState(
            user_id="demo-user",
            course_id=4,
            mastery_score=0.64,
            recent_accuracy=0.7,
            attempt_count=10,
            consecutive_errors=1,
            last_reviewed_at=reviewed_at,
            review_due=True,
        )

    monkeypatch.setattr("app.api.learner_state.validate_course_scope", fake_validate)
    monkeypatch.setattr("app.api.learner_state.compute_learner_state", fake_compute)
    client = TestClient(app)

    response = client.get("/learner-state?user_id=demo-user&course_id=4")

    assert response.status_code == 200
    assert captured == {"validated_course_id": 4, "computed_course_id": 4}
    body = response.json()
    assert body["mastery_score"] == 0.64
    assert body["recent_accuracy"] == 0.7
    assert body["attempt_count"] == 10
    assert body["consecutive_errors"] == 1
    assert body["review_due"] is True


def test_learner_state_api_rejects_unknown_course(monkeypatch) -> None:
    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise CourseNotFoundError("Course not found for this user")

    monkeypatch.setattr("app.api.learner_state.validate_course_scope", fake_validate)
    client = TestClient(app)

    response = client.get("/learner-state?user_id=demo-user&course_id=999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Course not found for this user"

