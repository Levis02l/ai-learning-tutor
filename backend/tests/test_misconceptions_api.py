from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.models.misconception import Misconception
from app.services.misconceptions import MisconceptionSummary


def test_list_course_misconceptions_returns_records(monkeypatch) -> None:
    created_at = datetime(2026, 7, 21, 12, 0, 0)
    captured: dict[str, int | str | None] = {}

    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["validated_user_id"] = kwargs["user_id"]
        captured["validated_course_id"] = kwargs["course_id"]

    def fake_list(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["listed_user_id"] = kwargs["user_id"]
        captured["listed_course_id"] = kwargs["course_id"]
        captured["listed_concept_id"] = kwargs["concept_id"]
        return [
            MisconceptionSummary(
                misconception=Misconception(
                    id=5,
                    user_id="demo-user",
                    course_id=4,
                    concept_id=7,
                    quiz_attempt_id=9,
                    misconception_type="concept_confusion",
                    description=(
                        "The learner confused clustering with classification."
                    ),
                    confidence=0.82,
                    evidence_snapshot={"selected_option_id": "A"},
                    created_at=created_at,
                ),
                concept_name="K-means Clustering",
            )
        ]

    monkeypatch.setattr(
        "app.api.misconceptions.validate_course_scope",
        fake_validate,
    )
    monkeypatch.setattr(
        "app.api.misconceptions.list_misconceptions",
        fake_list,
    )
    client = TestClient(app)

    response = client.get(
        "/courses/4/misconceptions?user_id=demo-user&concept_id=7"
    )

    assert response.status_code == 200
    assert captured == {
        "validated_user_id": "demo-user",
        "validated_course_id": 4,
        "listed_user_id": "demo-user",
        "listed_course_id": 4,
        "listed_concept_id": 7,
    }
    body = response.json()
    assert body[0]["concept_name"] == "K-means Clustering"
    assert body[0]["misconception_type"] == "concept_confusion"
    assert body[0]["confidence"] == 0.82
