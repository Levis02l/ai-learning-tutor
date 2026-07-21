from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.services.concepts import ConceptLearnerState
from app.services.progress import (
    CourseProgress,
    ProgressConcept,
    ProgressMisconception,
    ProgressPrerequisite,
    ProgressSocraticActivity,
    ProgressSummary,
)


def test_course_progress_endpoint_returns_summary_and_concepts(monkeypatch) -> None:
    captured: dict[str, int | str] = {}

    def fake_progress(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["user_id"] = kwargs["user_id"]
        captured["course_id"] = kwargs["course_id"]
        return _course_progress()

    monkeypatch.setattr("app.api.progress.get_course_progress", fake_progress)
    client = TestClient(app)

    response = client.get("/courses/4/progress?user_id=demo-user")

    assert response.status_code == 200
    assert captured == {"user_id": "demo-user", "course_id": 4}
    body = response.json()
    assert body["summary"]["total_concepts"] == 2
    assert body["summary"]["unobserved_concepts"] == 1
    assert body["concepts"][0]["status"] == "strong"
    assert body["concepts"][0]["socratic_activity"]["completed_sessions"] == 1
    assert body["concepts"][0]["latest_misconception"] is None
    assert body["concepts"][1]["status"] == "unobserved"
    assert body["concepts"][1]["mastery_score"] is None
    assert body["concepts"][1]["prerequisites"][0]["name"] == "Linear Algebra"


def _course_progress() -> CourseProgress:
    return CourseProgress(
        user_id="demo-user",
        course_id=4,
        summary=ProgressSummary(
            total_concepts=2,
            observed_concepts=1,
            unobserved_concepts=1,
            needs_attention_count=0,
            review_due_count=0,
            strong_count=1,
            developing_count=0,
            socratic_completed_count=1,
            socratic_completion_attempt_count=1,
        ),
        concepts=[
            ProgressConcept(
                learner_state=ConceptLearnerState(
                    concept_id=1,
                    concept_name="K-means Clustering",
                    state_status="observed",
                    mastery_score=0.86,
                    recent_accuracy=0.8,
                    attempt_count=8,
                    consecutive_errors=0,
                    last_attempted_at=datetime(2026, 7, 21, 12, 0, 0),
                    review_due=False,
                    needs_attention=False,
                ),
                status="strong",
                attention_reasons=[],
                latest_misconception=None,
                prerequisites=[],
                socratic_activity=ProgressSocraticActivity(
                    completed_sessions=1,
                    completion_attempts=1,
                    latest_session_id=12,
                    latest_completed_at="2026-07-21T12:00:00",
                    latest_completion_quiz_item_id=77,
                    latest_completion_quiz_attempt_id=88,
                    latest_completion_correct=True,
                ),
            ),
            ProgressConcept(
                learner_state=ConceptLearnerState(
                    concept_id=2,
                    concept_name="PCA",
                    state_status="unobserved",
                    mastery_score=None,
                    recent_accuracy=None,
                    attempt_count=0,
                    consecutive_errors=0,
                    last_attempted_at=None,
                    review_due=False,
                    needs_attention=False,
                ),
                status="unobserved",
                attention_reasons=[],
                latest_misconception=ProgressMisconception(
                    id=4,
                    misconception_type="unknown",
                    description="Not enough information.",
                    confidence=0.61,
                    quiz_attempt_id=30,
                    created_at="2026-07-21T11:00:00",
                ),
                prerequisites=[
                    ProgressPrerequisite(
                        id=5,
                        name="Linear Algebra",
                        confidence=0.74,
                    )
                ],
                socratic_activity=ProgressSocraticActivity(
                    completed_sessions=0,
                    completion_attempts=0,
                ),
            ),
        ],
    )
