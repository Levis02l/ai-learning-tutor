from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.models.socratic import SocraticSession, SocraticTurn


def test_start_socratic_endpoint_returns_session(monkeypatch) -> None:
    captured: dict[str, int | str | None] = {}

    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["validated_user_id"] = kwargs["user_id"]
        captured["validated_course_id"] = kwargs["course_id"]

    def fake_start(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["started_query"] = kwargs["query"]
        captured["source_policy_decision_id"] = kwargs["source_policy_decision_id"]
        captured["max_turns"] = kwargs["max_turns"]
        return _session()

    monkeypatch.setattr("app.api.socratic.validate_course_scope", fake_validate)
    monkeypatch.setattr("app.api.socratic.start_socratic_session", fake_start)
    client = TestClient(app)

    response = client.post(
        "/tutor/socratic/start",
        json={
            "query": "Guide me through K-means",
            "user_id": "demo-user",
            "course_id": 4,
            "source_policy_decision_id": 101,
            "max_turns": 3,
        },
    )

    assert response.status_code == 200
    assert captured == {
        "validated_user_id": "demo-user",
        "validated_course_id": 4,
        "started_query": "Guide me through K-means",
        "source_policy_decision_id": 101,
        "max_turns": 3,
    }
    body = response.json()
    assert body["id"] == 1
    assert body["status"] == "active"
    assert body["current_stage"] == "diagnostic"
    assert body["message"] == "What does K-means optimize?"
    assert body["turns"][0]["stage"] == "diagnostic"


def test_respond_socratic_endpoint_returns_latest_assessment(monkeypatch) -> None:
    captured: dict[str, int | str | None] = {}

    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    def fake_respond(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["session_id"] = kwargs["session_id"]
        captured["answer"] = kwargs["answer"]
        return _session_after_hint()

    monkeypatch.setattr("app.api.socratic.validate_course_scope", fake_validate)
    monkeypatch.setattr("app.api.socratic.respond_to_socratic_session", fake_respond)
    client = TestClient(app)

    response = client.post(
        "/tutor/socratic/1/respond",
        json={
            "answer": "Classification accuracy",
            "user_id": "demo-user",
            "course_id": 4,
        },
    )

    assert response.status_code == 200
    assert captured == {"session_id": 1, "answer": "Classification accuracy"}
    body = response.json()
    assert body["current_stage"] == "hint_1"
    assert body["assessment"] == "incorrect"
    assert body["assessment_reason"] == (
        "Still confusing clustering with classification."
    )
    assert body["message"] == "Hint one."


def test_get_socratic_endpoint_returns_turn_history(monkeypatch) -> None:
    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    def fake_get(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _session_after_hint()

    monkeypatch.setattr("app.api.socratic.validate_course_scope", fake_validate)
    monkeypatch.setattr("app.api.socratic.get_socratic_session", fake_get)
    client = TestClient(app)

    response = client.get("/tutor/socratic/1?user_id=demo-user&course_id=4")

    assert response.status_code == 200
    body = response.json()
    assert len(body["turns"]) == 2
    assert body["turns"][0]["student_response"] == "Classification accuracy"
    assert body["turns"][1]["tutor_message"] == "Hint one."


def _session() -> SocraticSession:
    session = SocraticSession(
        id=1,
        user_id="demo-user",
        course_id=4,
        concept_id=9,
        source_policy_decision_id=101,
        query="Guide me through K-means",
        status="active",
        current_stage="diagnostic",
        turn_count=0,
        max_turns=3,
        learner_state_snapshot={"mastery_score": 0.3},
        concept_snapshot={"concept_id": 9, "concept_name": "K-means Clustering"},
        misconception_snapshot={"misconception_type": "concept_confusion"},
        evidence_state_snapshot={"evidence_strength": "high"},
        evidence_chunks_snapshot=[{"chunk_id": 7, "content": "Evidence."}],
        created_at=datetime(2026, 7, 21, 12, 0, 0),
    )
    session.turns.append(
        SocraticTurn(
            id=1,
            session_id=1,
            turn_number=1,
            stage="diagnostic",
            tutor_message="What does K-means optimize?",
            created_at=datetime(2026, 7, 21, 12, 0, 1),
        )
    )
    return session


def _session_after_hint() -> SocraticSession:
    session = _session()
    session.current_stage = "hint_1"
    session.turn_count = 1
    session.turns[0].student_response = "Classification accuracy"
    session.turns[0].assessment = "incorrect"
    session.turns[0].assessment_reason = (
        "Still confusing clustering with classification."
    )
    session.turns.append(
        SocraticTurn(
            id=2,
            session_id=1,
            turn_number=2,
            stage="hint_1",
            tutor_message="Hint one.",
            created_at=datetime(2026, 7, 21, 12, 1, 0),
        )
    )
    return session
