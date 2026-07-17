from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.models.quiz import QuizItem
from app.models.review import ReviewRecord
from app.services.courses import CourseNotFoundError
from app.services.retrieval import retrieve_relevant_chunks_by_embedding


class _EmptyResult:
    def all(self):  # type: ignore[no-untyped-def]
        return []


class _CaptureExecuteDb:
    statement = None

    def execute(self, statement):  # type: ignore[no-untyped-def]
        self.statement = statement
        return _EmptyResult()


def test_retrieval_filters_by_course_in_sql_query() -> None:
    db = _CaptureExecuteDb()

    retrieve_relevant_chunks_by_embedding(
        db=db,  # type: ignore[arg-type]
        query_embedding=[0.0] * 1536,
        user_id="demo-user",
        course_id=42,
    )

    assert db.statement is not None
    assert "documents.course_id =" in str(db.statement)


def test_search_rejects_unknown_course_before_retrieval(monkeypatch) -> None:
    def raise_missing_course(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise CourseNotFoundError("Course not found for this user")

    def fail_retrieve(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("retrieval should not run for an invalid course")

    monkeypatch.setattr("app.api.search.validate_course_scope", raise_missing_course)
    monkeypatch.setattr("app.api.search.retrieve_relevant_chunks", fail_retrieve)
    client = TestClient(app)

    response = client.post(
        "/search",
        json={"query": "What is AI?", "course_id": 999},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Course not found for this user"


def test_quiz_generate_keeps_generated_items_in_course(monkeypatch) -> None:
    created_at = datetime(2026, 6, 17, 12, 0, 0)
    captured: dict[str, int | None] = {}

    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["validated_course_id"] = kwargs["course_id"]

    def fake_generate_quiz_items(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["generated_course_id"] = kwargs["course_id"]
        return [
            QuizItem(
                id=1,
                user_id="demo-user",
                course_id=12,
                question="What is an intelligent agent?",
                answer="An entity that perceives and acts in an environment.",
                difficulty="medium",
                source_chunk_ids=[82],
                evidence_quote="An agent is an entity that perceives and acts.",
                question_type="definition",
                traceability_label="fully_traceable",
                created_at=created_at,
            )
        ]

    monkeypatch.setattr("app.api.quiz.validate_course_scope", fake_validate)
    monkeypatch.setattr("app.api.quiz.generate_quiz_items", fake_generate_quiz_items)
    client = TestClient(app)

    response = client.post(
        "/quiz/generate",
        json={"topic": "agents", "course_id": 12, "count": 1},
    )

    assert response.status_code == 200
    assert captured == {"validated_course_id": 12, "generated_course_id": 12}
    body = response.json()
    assert body["course_id"] == 12
    assert body["items"][0]["course_id"] == 12


def test_review_submit_records_course_scope(monkeypatch) -> None:
    reviewed_at = datetime(2026, 6, 17, 12, 0, 0)
    due_at = datetime(2026, 6, 19, 12, 0, 0)
    captured: dict[str, int | None] = {}

    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["validated_course_id"] = kwargs["course_id"]

    def fake_submit_review(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["submitted_course_id"] = kwargs["course_id"]
        return ReviewRecord(
            id=1,
            user_id="demo-user",
            course_id=7,
            item_id=1,
            rating=3,
            is_correct=True,
            reviewed_at=reviewed_at,
            stability=2.3,
            difficulty=4.8,
            due_at=due_at,
        )

    monkeypatch.setattr("app.api.reviews.validate_course_scope", fake_validate)
    monkeypatch.setattr("app.api.reviews.submit_review", fake_submit_review)
    client = TestClient(app)

    response = client.post(
        "/reviews",
        json={"item_id": 1, "course_id": 7, "rating": 3, "is_correct": True},
    )

    assert response.status_code == 200
    assert captured == {"validated_course_id": 7, "submitted_course_id": 7}
    assert response.json()["course_id"] == 7


def test_delete_course_returns_204(monkeypatch) -> None:
    calls: list[tuple[int, str]] = []

    def fake_delete_course(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((kwargs["course_id"], kwargs["user_id"]))

    monkeypatch.setattr("app.api.courses.delete_course", fake_delete_course)
    client = TestClient(app)

    response = client.delete("/courses/3?user_id=demo-user")

    assert response.status_code == 204
    assert calls == [(3, "demo-user")]


def test_delete_course_returns_404_when_missing(monkeypatch) -> None:
    def fake_delete_course(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise CourseNotFoundError("Course not found for this user")

    monkeypatch.setattr("app.api.courses.delete_course", fake_delete_course)
    client = TestClient(app)

    response = client.delete("/courses/999?user_id=demo-user")

    assert response.status_code == 404
    assert response.json()["detail"] == "Course not found for this user"
