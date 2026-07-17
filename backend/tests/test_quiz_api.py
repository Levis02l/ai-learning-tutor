from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.models.quiz import QuizAttempt, QuizItem
from app.services.quiz import QuizGenerationError


def test_quiz_generate_allows_empty_focus(monkeypatch) -> None:
    created_at = datetime(2026, 6, 17, 12, 0, 0)
    captured: dict[str, str] = {}

    def fake_generate_quiz_items(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["topic"] = kwargs["topic"]
        return [
            QuizItem(
                id=1,
                user_id="demo-user",
                question="What is an intelligent agent?",
                answer="An entity that perceives and acts in an environment.",
                difficulty="medium",
                source_chunk_ids=[82],
                evidence_quote="An agent is an entity that perceives and acts.",
                options=_options(),
                correct_option_id="B",
                explanation="Because the source defines an agent this way.",
                question_type="definition",
                traceability_label="fully_traceable",
                created_at=created_at,
            )
        ]

    monkeypatch.setattr("app.api.quiz.generate_quiz_items", fake_generate_quiz_items)
    client = TestClient(app)

    response = client.post("/quiz/generate", json={"topic": ""})

    assert response.status_code == 200
    assert captured["topic"] == ""
    assert response.json()["topic"] == "current course materials"


def test_quiz_generate_returns_items(monkeypatch) -> None:
    created_at = datetime(2026, 6, 17, 12, 0, 0)

    def fake_generate_quiz_items(*args, **kwargs):  # type: ignore[no-untyped-def]
        return [
            QuizItem(
                id=1,
                user_id="demo-user",
                question="What is an intelligent agent?",
                answer="An entity that perceives and acts in an environment.",
                difficulty="medium",
                source_chunk_ids=[82],
                evidence_quote="An agent is an entity that perceives and acts.",
                options=_options(),
                correct_option_id="B",
                explanation="Because the source defines an agent this way.",
                question_type="definition",
                traceability_label="fully_traceable",
                created_at=created_at,
            )
        ]

    monkeypatch.setattr("app.api.quiz.generate_quiz_items", fake_generate_quiz_items)
    client = TestClient(app)

    response = client.post(
        "/quiz/generate",
        json={"topic": "artificial intelligence", "count": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["topic"] == "artificial intelligence"
    assert body["items"][0]["question"] == "What is an intelligent agent?"
    assert body["items"][0]["source_chunk_ids"] == [82]
    assert body["items"][0]["options"][1]["id"] == "B"
    assert body["items"][0]["explanation"] == (
        "Because the source defines an agent this way."
    )
    assert body["items"][0]["traceability_label"] == "fully_traceable"


def test_quiz_generate_returns_422_when_no_materials(monkeypatch) -> None:
    def raise_no_materials(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise QuizGenerationError("No uploaded materials found in this scope")

    monkeypatch.setattr("app.api.quiz.generate_quiz_items", raise_no_materials)
    client = TestClient(app)

    response = client.post("/quiz/generate", json={"topic": "unknown topic"})

    assert response.status_code == 422
    assert response.json()["detail"] == "No uploaded materials found in this scope"


def test_quiz_attempt_returns_grading_feedback(monkeypatch) -> None:
    attempted_at = datetime(2026, 6, 17, 12, 30, 0)
    captured: dict[str, int | str | None] = {}
    item = QuizItem(
        id=1,
        user_id="demo-user",
        course_id=4,
        question="What is an intelligent agent?",
        answer="An entity that perceives and acts in an environment.",
        difficulty="medium",
        source_chunk_ids=[82],
        evidence_quote="An agent is an entity that perceives and acts.",
        options=_options(),
        correct_option_id="B",
        explanation="Because the source defines an agent this way.",
        question_type="definition",
        traceability_label="fully_traceable",
        created_at=attempted_at,
    )

    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["validated_course_id"] = kwargs["course_id"]

    def fake_submit_attempt(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["submitted_course_id"] = kwargs["course_id"]
        captured["selected_option_id"] = kwargs["selected_option_id"]
        return QuizAttempt(
            id=9,
            user_id="demo-user",
            course_id=4,
            quiz_item_id=1,
            selected_option_id="A",
            selected_option_text="Wrong answer",
            correct_option_id="B",
            correct_option_text="An entity that perceives and acts",
            is_correct=False,
            attempted_at=attempted_at,
            quiz_item=item,
        )

    monkeypatch.setattr("app.api.quiz.validate_course_scope", fake_validate)
    monkeypatch.setattr("app.api.quiz.submit_quiz_attempt", fake_submit_attempt)
    client = TestClient(app)

    response = client.post(
        "/quiz/attempts",
        json={
            "user_id": "demo-user",
            "course_id": 4,
            "quiz_item_id": 1,
            "selected_option_id": "A",
        },
    )

    assert response.status_code == 200
    assert captured == {
        "validated_course_id": 4,
        "submitted_course_id": 4,
        "selected_option_id": "A",
    }
    body = response.json()
    assert body["id"] == 9
    assert body["is_correct"] is False
    assert body["correct_option_id"] == "B"
    assert body["source_chunk_ids"] == [82]


def _options() -> list[dict[str, str]]:
    return [
        {"id": "A", "text": "Wrong answer"},
        {"id": "B", "text": "An entity that perceives and acts"},
        {"id": "C", "text": "A web page style language"},
        {"id": "D", "text": "A database index"},
    ]
