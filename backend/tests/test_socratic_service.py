from datetime import datetime

import pytest

from app.llm.provider import LLMResponse
from app.models.quiz import QuizAttempt, QuizItem
from app.models.socratic import SocraticSession, SocraticTurn
from app.services.policy import POLICY_VERSION, PolicyDecision
from app.services.retrieval import RetrievedChunk
from app.services.socratic import (
    SocraticSessionClosedError,
    SocraticSessionError,
    generate_socratic_completion_check,
    respond_to_socratic_session,
    start_socratic_session,
    submit_socratic_completion_attempt,
)


def test_start_socratic_session_freezes_context(monkeypatch) -> None:
    decision = _decision()
    db = _SessionStore()
    provider = _SocraticProvider(messages=["Diagnostic question?"])
    monkeypatch.setattr(
        "app.services.socratic.create_policy_decision",
        lambda **kwargs: decision,
    )

    session = start_socratic_session(
        db=db,  # type: ignore[arg-type]
        query="Guide me through K-means",
        user_id="demo-user",
        course_id=4,
        llm_provider=provider,
    )

    assert session.status == "active"
    assert session.current_stage == "diagnostic"
    assert session.turn_count == 0
    assert session.max_turns == 3
    assert session.course_id == 4
    assert session.concept_id == 9
    assert session.source_policy_decision_id == 101
    assert session.evidence_chunks_snapshot[0]["chunk_id"] == 7
    assert "K-means minimizes within-cluster variance" in provider.prompts[0]
    assert session.turns[0].tutor_message == "Diagnostic question?"


def test_start_socratic_session_requires_grounded_concept(monkeypatch) -> None:
    decision = _decision(with_concept=False)
    monkeypatch.setattr(
        "app.services.socratic.create_policy_decision",
        lambda **kwargs: decision,
    )

    with pytest.raises(SocraticSessionError, match="resolved concept"):
        start_socratic_session(
            db=_SessionStore(),  # type: ignore[arg-type]
            query="Guide me",
            user_id="demo-user",
            course_id=4,
            llm_provider=_SocraticProvider(messages=["Diagnostic?"]),
        )


def test_socratic_incorrect_answers_progress_to_final_explanation() -> None:
    session = _session()
    db = _SessionStore(session=session)
    provider = _SocraticProvider(
        assessments=["incorrect", "incorrect", "incorrect"],
        messages=["Hint one.", "Hint two.", "Final explanation."],
    )

    first = respond_to_socratic_session(
        db=db,  # type: ignore[arg-type]
        session_id=1,
        answer="Classification accuracy",
        user_id="demo-user",
        course_id=4,
        llm_provider=provider,
    )
    assert first.status == "active"
    assert first.current_stage == "hint_1"
    assert first.turn_count == 1
    assert first.turns[-1].tutor_message == "Hint one."

    second = respond_to_socratic_session(
        db=db,  # type: ignore[arg-type]
        session_id=1,
        answer="Maybe labels",
        user_id="demo-user",
        course_id=4,
        llm_provider=provider,
    )
    assert second.status == "active"
    assert second.current_stage == "hint_2"
    assert second.turn_count == 2

    third = respond_to_socratic_session(
        db=db,  # type: ignore[arg-type]
        session_id=1,
        answer="Still labels",
        user_id="demo-user",
        course_id=4,
        llm_provider=provider,
    )
    assert third.status == "completed"
    assert third.current_stage == "final_explanation"
    assert third.turn_count == 3
    assert third.completed_at is not None
    assert len(third.turns) == 4
    assert third.turns[-1].tutor_message == "Final explanation."


def test_socratic_correct_answer_completes_early() -> None:
    session = _session()
    db = _SessionStore(session=session)
    provider = _SocraticProvider(
        assessments=["correct"],
        messages=["Good, K-means minimizes within-cluster variation."],
    )

    result = respond_to_socratic_session(
        db=db,  # type: ignore[arg-type]
        session_id=1,
        answer="It minimizes within-cluster sum of squares.",
        user_id="demo-user",
        course_id=4,
        llm_provider=provider,
    )

    assert result.status == "completed"
    assert result.current_stage == "grounded_summary"
    assert result.turn_count == 1
    assert len(result.turns) == 2
    assert result.turns[0].assessment == "correct"


def test_socratic_closed_session_rejects_more_answers() -> None:
    session = _session(status="completed")

    with pytest.raises(SocraticSessionClosedError):
        respond_to_socratic_session(
            db=_SessionStore(session=session),  # type: ignore[arg-type]
            session_id=1,
            answer="Another answer",
            user_id="demo-user",
            course_id=4,
            llm_provider=_SocraticProvider(),
        )


def test_socratic_prompts_use_frozen_evidence_snapshot() -> None:
    session = _session()
    db = _SessionStore(session=session)
    provider = _SocraticProvider(
        assessments=["partially_correct"],
        messages=["Use the frozen evidence."],
    )

    respond_to_socratic_session(
        db=db,  # type: ignore[arg-type]
        session_id=1,
        answer="It groups points.",
        user_id="demo-user",
        course_id=4,
        llm_provider=provider,
    )

    assessment_prompt = provider.prompts[0]
    message_prompt = provider.prompts[1]
    assert "Frozen evidence" in assessment_prompt
    assert "K-means minimizes within-cluster variance" in assessment_prompt
    assert "Frozen course excerpts" in message_prompt
    assert "K-means minimizes within-cluster variance" in message_prompt


def test_completion_check_requires_completed_session() -> None:
    session = _session(status="active")

    with pytest.raises(SocraticSessionError, match="completed session"):
        generate_socratic_completion_check(
            db=_SessionStore(session=session),  # type: ignore[arg-type]
            session_id=1,
            user_id="demo-user",
            course_id=4,
            llm_provider=_SocraticProvider(),
        )


def test_completion_check_uses_frozen_evidence_and_socratic_origin(
    monkeypatch,
) -> None:
    session = _session(status="completed")
    db = _SessionStore(session=session)
    captured: dict[str, object] = {}

    def fake_generate_quiz_items_from_chunks(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["topic"] = kwargs["topic"]
        captured["chunks"] = kwargs["chunks"]
        captured["concept_id"] = kwargs["concept_id"]
        captured["origin"] = kwargs["origin"]
        captured["require_traceable"] = kwargs["require_traceable"]
        return [_quiz_item()]

    monkeypatch.setattr(
        "app.services.socratic.generate_quiz_items_from_chunks",
        fake_generate_quiz_items_from_chunks,
    )

    updated_session, item = generate_socratic_completion_check(
        db=db,  # type: ignore[arg-type]
        session_id=1,
        user_id="demo-user",
        course_id=4,
        llm_provider=_SocraticProvider(),
    )

    assert item.id == 77
    assert item.origin == "socratic_completion_check"
    assert item.concept_id == 9
    assert updated_session.completion_quiz_item_id == 77
    assert captured["origin"] == "socratic_completion_check"
    assert captured["concept_id"] == 9
    assert captured["require_traceable"] is True
    chunks = captured["chunks"]
    assert isinstance(chunks, list)
    assert chunks[0].chunk_id == 7


def test_completion_check_is_idempotent(monkeypatch) -> None:
    session = _session(status="completed")
    session.completion_quiz_item_id = 77
    db = _SessionStore(session=session, quiz_item=_quiz_item())

    def fail_generate(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("completion check should be reused")

    monkeypatch.setattr(
        "app.services.socratic.generate_quiz_items_from_chunks",
        fail_generate,
    )

    _, item = generate_socratic_completion_check(
        db=db,  # type: ignore[arg-type]
        session_id=1,
        user_id="demo-user",
        course_id=4,
        llm_provider=_SocraticProvider(),
    )

    assert item.id == 77


def test_completion_attempt_updates_session_link(monkeypatch) -> None:
    session = _session(status="completed")
    session.completion_quiz_item_id = 77
    db = _SessionStore(session=session, quiz_item=_quiz_item())
    captured: dict[str, object] = {}

    def fake_submit_quiz_attempt(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["quiz_item_id"] = kwargs["quiz_item_id"]
        captured["selected_option_id"] = kwargs["selected_option_id"]
        return _quiz_attempt()

    monkeypatch.setattr(
        "app.services.socratic.submit_quiz_attempt",
        fake_submit_quiz_attempt,
    )

    updated_session, attempt = submit_socratic_completion_attempt(
        db=db,  # type: ignore[arg-type]
        session_id=1,
        selected_option_id="B",
        user_id="demo-user",
        course_id=4,
    )

    assert captured == {"quiz_item_id": 77, "selected_option_id": "B"}
    assert attempt.id == 88
    assert updated_session.completion_quiz_attempt_id == 88


class _SocraticProvider:
    def __init__(
        self,
        *,
        messages: list[str] | None = None,
        assessments: list[str] | None = None,
    ) -> None:
        self.messages = messages or ["Tutor message."]
        self.assessments = assessments or ["incorrect"]
        self.prompts: list[str] = []

    def generate(self, **kwargs):  # type: ignore[no-untyped-def]
        prompt = kwargs["user_prompt"]
        self.prompts.append(prompt)
        if prompt.startswith("Assess the learner"):
            assessment = self.assessments.pop(0)
            return LLMResponse(
                text=(
                    '{"assessment": "'
                    + assessment
                    + '", "assessment_reason": "Grounded assessment."}'
                )
            )

        message = self.messages.pop(0)
        return LLMResponse(text='{"message": "' + message + '"}')


class _SessionStore:
    def __init__(
        self,
        *,
        session: SocraticSession | None = None,
        quiz_item: QuizItem | None = None,
        quiz_attempt: QuizAttempt | None = None,
    ) -> None:
        self.session = session
        self.quiz_item = quiz_item
        self.quiz_attempt = quiz_attempt
        self.added: list[object] = []

    def scalar(self, query):  # type: ignore[no-untyped-def]
        return self.session

    def get(self, model, item_id):  # type: ignore[no-untyped-def]
        if model is QuizItem and self.quiz_item and self.quiz_item.id == item_id:
            return self.quiz_item
        if (
            model is QuizAttempt
            and self.quiz_attempt
            and self.quiz_attempt.id == item_id
        ):
            return self.quiz_attempt
        return None

    def execute(self, query):  # type: ignore[no-untyped-def]
        return _Rows([])

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if isinstance(obj, SocraticSession):
            self.session = obj
            obj.id = obj.id or 1
            obj.created_at = obj.created_at or datetime(2026, 7, 21, 12, 0, 0)
            for index, turn in enumerate(obj.turns, start=1):
                turn.id = turn.id or index
                turn.session_id = obj.id
                turn.created_at = turn.created_at or datetime(2026, 7, 21, 12, index)

    def commit(self) -> None:
        if self.session is None:
            return
        for index, turn in enumerate(self.session.turns, start=1):
            turn.id = turn.id or index
            turn.session_id = self.session.id
            turn.created_at = turn.created_at or datetime(2026, 7, 21, 12, index)

    def refresh(self, obj: object) -> None:
        return None


def _quiz_item() -> QuizItem:
    return QuizItem(
        id=77,
        user_id="demo-user",
        course_id=4,
        concept_id=9,
        question="What does K-means minimize?",
        answer="Within-cluster variance.",
        difficulty="medium",
        origin="socratic_completion_check",
        source_chunk_ids=[7],
        evidence_quote="K-means minimizes within-cluster variance.",
        options=[
            {"id": "A", "text": "Classification accuracy"},
            {"id": "B", "text": "Within-cluster variance"},
            {"id": "C", "text": "Network latency"},
            {"id": "D", "text": "Database size"},
        ],
        correct_option_id="B",
        explanation="The source states that K-means minimizes within-cluster variance.",
        question_type="conceptual",
        traceability_label="fully_traceable",
        created_at=datetime(2026, 7, 21, 12, 2, 0),
    )


def _quiz_attempt() -> QuizAttempt:
    return QuizAttempt(
        id=88,
        user_id="demo-user",
        course_id=4,
        quiz_item_id=77,
        selected_option_id="B",
        selected_option_text="Within-cluster variance",
        correct_option_id="B",
        correct_option_text="Within-cluster variance",
        is_correct=True,
        attempted_at=datetime(2026, 7, 21, 12, 3, 0),
        quiz_item=_quiz_item(),
    )


class _Rows:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return self._rows


def _session(*, status: str = "active") -> SocraticSession:
    session = SocraticSession(
        id=1,
        user_id="demo-user",
        course_id=4,
        concept_id=9,
        source_policy_decision_id=101,
        query="Guide me through K-means",
        status=status,
        current_stage="diagnostic",
        turn_count=0,
        max_turns=3,
        learner_state_snapshot=_learner_snapshot(),
        concept_snapshot=_concept_snapshot(),
        misconception_snapshot=_misconception_snapshot(),
        evidence_state_snapshot=_evidence_snapshot(),
        evidence_chunks_snapshot=[
            {
                "chunk_id": 7,
                "document_id": 2,
                "course_id": 4,
                "filename": "lecture.pdf",
                "content": "K-means minimizes within-cluster variance.",
                "metadata": {},
                "distance": 0.0,
                "similarity": 1.0,
            }
        ],
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


def _decision(*, with_concept: bool = True) -> PolicyDecision:
    concept_snapshot = _concept_snapshot() if with_concept else None
    return PolicyDecision(
        decision_id=101,
        user_id="demo-user",
        course_id=4,
        query="Guide me through K-means",
        detected_intent="explain",
        selected_action="explain",
        response_strategy="contrastive",
        primary_reason="explicit_explanation_request",
        teaching_reason="Use contrastive teaching.",
        suggested_next_step="Guide step by step.",
        policy_version=POLICY_VERSION,
        learner_state_snapshot=_learner_snapshot(),
        evidence_state_snapshot=_evidence_snapshot(),
        learner_state_scope="concept",
        concept_state_snapshot=concept_snapshot,
        misconception_snapshot=_misconception_snapshot(),
        evidence_chunks=[
            RetrievedChunk(
                chunk_id=7,
                document_id=2,
                course_id=4,
                filename="lecture.pdf",
                content="K-means minimizes within-cluster variance.",
                metadata={},
                distance=0.0,
                similarity=1.0,
            )
        ],
    )


def _learner_snapshot() -> dict:
    return {
        "user_id": "demo-user",
        "course_id": 4,
        "mastery_score": 0.3,
        "recent_accuracy": 0.25,
        "attempt_count": 4,
        "consecutive_errors": 2,
        "last_reviewed_at": None,
        "review_due": False,
    }


def _concept_snapshot() -> dict:
    return {
        "concept_id": 9,
        "concept_name": "K-means Clustering",
        "state_status": "observed",
        "mastery_score": 0.3,
        "recent_accuracy": 0.25,
        "attempt_count": 4,
        "consecutive_errors": 2,
        "last_attempted_at": None,
        "review_due": False,
        "needs_attention": True,
    }


def _misconception_snapshot() -> dict:
    return {
        "id": 13,
        "misconception_type": "concept_confusion",
        "description": "The learner confuses clustering with classification.",
        "confidence": 0.86,
        "quiz_attempt_id": 22,
        "concept_id": 9,
        "created_at": "2026-07-21T12:00:00",
    }


def _evidence_snapshot() -> dict:
    return {
        "evidence_strength": "high",
        "source_coverage": 1.0,
        "retrieved_chunk_count": 1,
        "top_similarity": 0.9,
        "requires_evidence": True,
        "reason": "test evidence",
        "retrieval_scope": "concept",
        "source_chunk_ids": [7],
    }
