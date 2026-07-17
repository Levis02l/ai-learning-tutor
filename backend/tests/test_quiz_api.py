from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.models.quiz import QuizItem
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
    assert body["items"][0]["traceability_label"] == "fully_traceable"


def test_quiz_generate_returns_422_when_no_materials(monkeypatch) -> None:
    def raise_no_materials(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise QuizGenerationError("No uploaded materials found in this scope")

    monkeypatch.setattr("app.api.quiz.generate_quiz_items", raise_no_materials)
    client = TestClient(app)

    response = client.post("/quiz/generate", json={"topic": "unknown topic"})

    assert response.status_code == 422
    assert response.json()["detail"] == "No uploaded materials found in this scope"
