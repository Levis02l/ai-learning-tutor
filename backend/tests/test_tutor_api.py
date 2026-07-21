from fastapi.testclient import TestClient

from app.main import app
from app.services.policy import POLICY_VERSION, PolicyDecision
from app.services.tutor_response import TutorResponse


def test_tutor_decide_returns_policy_decision(monkeypatch) -> None:
    captured: dict[str, int | str | None] = {}

    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["validated_course_id"] = kwargs["course_id"]

    def fake_create_decision(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["query"] = kwargs["query"]
        captured["course_id"] = kwargs["course_id"]
        return PolicyDecision(
            decision_id=12,
            user_id="demo-user",
            course_id=4,
            query=kwargs["query"],
            detected_intent="explain",
            selected_action="explain",
            response_strategy="scaffolded",
            primary_reason="explicit_explanation_request",
            teaching_reason="The learner asked for an explanation.",
            suggested_next_step="Explain, then ask one diagnostic question.",
            policy_version=POLICY_VERSION,
            learner_state_snapshot={
                "user_id": "demo-user",
                "course_id": 4,
                "mastery_score": 0.3,
                "recent_accuracy": 0.25,
                "attempt_count": 4,
                "consecutive_errors": 2,
                "last_reviewed_at": None,
                "review_due": False,
            },
            evidence_state_snapshot={
                "evidence_strength": "high",
                "source_coverage": 1.0,
                "retrieved_chunk_count": 3,
                "top_similarity": 0.72,
                "requires_evidence": True,
                "reason": "test evidence",
            },
        )

    monkeypatch.setattr("app.api.tutor.validate_course_scope", fake_validate)
    monkeypatch.setattr("app.api.tutor.create_policy_decision", fake_create_decision)
    client = TestClient(app)

    response = client.post(
        "/tutor/decide",
        json={
            "query": "Explain congestion control",
            "user_id": "demo-user",
            "course_id": 4,
        },
    )

    assert response.status_code == 200
    assert captured == {
        "validated_course_id": 4,
        "query": "Explain congestion control",
        "course_id": 4,
    }
    body = response.json()
    assert body["decision_id"] == 12
    assert body["detected_intent"] == "explain"
    assert body["selected_action"] == "explain"
    assert body["response_strategy"] == "scaffolded"
    assert body["learner_state_snapshot"]["mastery_score"] == 0.3
    assert body["evidence_state_snapshot"]["evidence_strength"] == "high"


def test_tutor_respond_returns_unified_response(monkeypatch) -> None:
    captured: dict[str, int | str | None] = {}
    decision = _policy_decision(query="Explain congestion control")

    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["validated_course_id"] = kwargs["course_id"]

    def fake_create_response(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["query"] = kwargs["query"]
        captured["course_id"] = kwargs["course_id"]
        return TutorResponse(
            decision=decision,
            answer_status="answered",
            answer="Tutor answer.",
            suggested_next_step="Try one question.",
        )

    monkeypatch.setattr("app.api.tutor.validate_course_scope", fake_validate)
    monkeypatch.setattr("app.api.tutor.create_tutor_response", fake_create_response)
    client = TestClient(app)

    response = client.post(
        "/tutor/respond",
        json={
            "query": "Explain congestion control",
            "user_id": "demo-user",
            "course_id": 4,
        },
    )

    assert response.status_code == 200
    assert captured == {
        "validated_course_id": 4,
        "query": "Explain congestion control",
        "course_id": 4,
    }
    body = response.json()
    assert body["decision"]["selected_action"] == "explain"
    assert body["answer_status"] == "answered"
    assert body["answer"] == "Tutor answer."
    assert body["quiz_items"] == []
    assert body["review_items"] == []


def test_tutor_outcome_links_existing_quiz_attempt(monkeypatch) -> None:
    captured: dict[str, int | str | None] = {}

    def fake_record_outcome(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["decision_id"] = kwargs["decision_id"]
        captured["outcome_type"] = kwargs["outcome_type"]
        captured["quiz_attempt_id"] = kwargs["quiz_attempt_id"]
        captured["review_record_id"] = kwargs["review_record_id"]
        return {
            "type": "quiz_attempt",
            "quiz_attempt_id": kwargs["quiz_attempt_id"],
            "is_correct": False,
        }

    monkeypatch.setattr("app.api.tutor.record_tutor_outcome", fake_record_outcome)
    client = TestClient(app)

    response = client.post(
        "/tutor/decisions/12/outcome",
        json={"outcome_type": "quiz_attempt", "quiz_attempt_id": 9},
    )

    assert response.status_code == 200
    assert captured == {
        "decision_id": 12,
        "outcome_type": "quiz_attempt",
        "quiz_attempt_id": 9,
        "review_record_id": None,
    }
    body = response.json()
    assert body["decision_id"] == 12
    assert body["outcome"]["type"] == "quiz_attempt"
    assert body["outcome"]["is_correct"] is False


def _policy_decision(*, query: str) -> PolicyDecision:
    return PolicyDecision(
        decision_id=12,
        user_id="demo-user",
        course_id=4,
        query=query,
        detected_intent="explain",
        selected_action="explain",
        response_strategy="scaffolded",
        primary_reason="explicit_explanation_request",
        teaching_reason="The learner asked for an explanation.",
        suggested_next_step="Explain, then ask one diagnostic question.",
        policy_version=POLICY_VERSION,
        learner_state_snapshot={
            "user_id": "demo-user",
            "course_id": 4,
            "mastery_score": 0.3,
            "recent_accuracy": 0.25,
            "attempt_count": 4,
            "consecutive_errors": 2,
            "last_reviewed_at": None,
            "review_due": False,
        },
        evidence_state_snapshot={
            "evidence_strength": "high",
            "source_coverage": 1.0,
            "retrieved_chunk_count": 3,
            "top_similarity": 0.72,
            "requires_evidence": True,
            "reason": "test evidence",
        },
    )
