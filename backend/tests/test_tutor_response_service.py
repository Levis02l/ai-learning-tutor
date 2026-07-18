from datetime import datetime

import pytest

from app.llm.provider import LLMResponse
from app.models.quiz import QuizItem
from app.services.policy import POLICY_VERSION, PolicyDecision
from app.services.retrieval import RetrievedChunk
from app.services.tutor_response import execute_tutor_decision


class FakeLLMProvider:
    def __init__(self, text: str | None = None) -> None:
        self.calls: list[dict] = []
        self.text = text or (
            '{"answer_status": "answered", "answer": "Tutor answer.", '
            '"claims": [{"claim": "Supported claim", "source_chunk_ids": [1], '
            '"support_level": "fully_supported", "evidence_quote": "Evidence."}]}'
        )

    def generate(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        return LLMResponse(text=self.text)


class FailingLLMProvider:
    def generate(self, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("LLM should not be called")


def test_refuse_returns_deterministic_response_without_llm() -> None:
    response = execute_tutor_decision(
        db=None,  # type: ignore[arg-type]
        decision=_decision(
            selected_action="refuse",
            response_strategy="refusal",
            evidence_strength="insufficient",
        ),
        llm_provider=FailingLLMProvider(),
    )

    assert response.answer_status == "refused_no_evidence"
    assert "not find enough reliable support" in response.answer
    assert response.claims == []
    assert response.sources == []


def test_due_review_returns_summary_without_llm(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.tutor_response.get_due_review_items",
        lambda **kwargs: [(_quiz_item(item_id=1), None), (_quiz_item(item_id=2), None)],
    )

    response = execute_tutor_decision(
        db=None,  # type: ignore[arg-type]
        decision=_decision(
            selected_action="review",
            response_strategy="review_drill",
            evidence_strength="not_required",
            requires_evidence=False,
        ),
        llm_provider=FailingLLMProvider(),
    )

    assert response.answer_status == "review_ready"
    assert response.answer == "2 traceable items are due for review."
    assert len(response.review_items) == 2


def test_scaffolded_explanation_uses_policy_aware_prompt(monkeypatch) -> None:
    provider = FakeLLMProvider()
    monkeypatch.setattr(
        "app.services.tutor_response.retrieve_relevant_chunks",
        lambda **kwargs: [_chunk()],
    )

    response = execute_tutor_decision(
        db=None,  # type: ignore[arg-type]
        decision=_decision(
            selected_action="explain",
            response_strategy="scaffolded",
        ),
        llm_provider=provider,
    )

    assert response.answer_status == "answered"
    assert response.answer == "Tutor answer."
    assert len(provider.calls) == 1
    prompt = provider.calls[0]["user_prompt"]
    assert "Response strategy:\nscaffolded" in prompt
    assert "Break the explanation into small steps" in prompt
    assert response.claims[0].source_chunk_ids == [1]


def test_guided_hint_prompt_forbids_full_answer(monkeypatch) -> None:
    provider = FakeLLMProvider()
    monkeypatch.setattr(
        "app.services.tutor_response.retrieve_relevant_chunks",
        lambda **kwargs: [_chunk()],
    )

    execute_tutor_decision(
        db=None,  # type: ignore[arg-type]
        decision=_decision(
            selected_action="hint",
            response_strategy="guided",
            primary_reason="explicit_hint_request",
        ),
        llm_provider=provider,
    )

    assert len(provider.calls) == 1
    prompt = provider.calls[0]["user_prompt"]
    assert "Do not reveal the final answer" in prompt
    assert "Provide only one useful hint" in prompt


def test_quiz_action_reuses_quiz_service_for_one_item(monkeypatch) -> None:
    captured: dict[str, int | str] = {}

    def fake_generate_quiz_items(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["count"] = kwargs["count"]
        captured["difficulty"] = kwargs["difficulty"]
        return [_quiz_item(item_id=7)]

    monkeypatch.setattr(
        "app.services.tutor_response.generate_quiz_items",
        fake_generate_quiz_items,
    )

    response = execute_tutor_decision(
        db=None,  # type: ignore[arg-type]
        decision=_decision(
            selected_action="quiz",
            response_strategy="challenging",
            primary_reason="high_mastery",
        ),
        llm_provider=FailingLLMProvider(),
    )

    assert captured == {"count": 1, "difficulty": "hard"}
    assert response.answer_status == "quiz_ready"
    assert response.quiz_items[0].id == 7


def test_llm_response_rejects_invalid_json(monkeypatch) -> None:
    provider = FakeLLMProvider(text="not json")
    monkeypatch.setattr(
        "app.services.tutor_response.retrieve_relevant_chunks",
        lambda **kwargs: [_chunk()],
    )

    with pytest.raises(Exception, match="valid JSON"):
        execute_tutor_decision(
            db=None,  # type: ignore[arg-type]
            decision=_decision(selected_action="explain", response_strategy="concise"),
            llm_provider=provider,
        )


def _decision(
    *,
    selected_action: str,
    response_strategy: str,
    primary_reason: str = "test_reason",
    evidence_strength: str = "high",
    requires_evidence: bool = True,
) -> PolicyDecision:
    return PolicyDecision(
        decision_id=1,
        user_id="demo-user",
        course_id=4,
        query="Explain congestion control",
        detected_intent="explain",
        selected_action=selected_action,
        response_strategy=response_strategy,
        primary_reason=primary_reason,
        teaching_reason="Test teaching reason.",
        suggested_next_step="Test next step.",
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
            "evidence_strength": evidence_strength,
            "source_coverage": 1.0,
            "retrieved_chunk_count": 1,
            "top_similarity": 0.7,
            "requires_evidence": requires_evidence,
            "reason": "test evidence",
        },
    )


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=1,
        document_id=2,
        course_id=4,
        filename="lecture.pdf",
        content="Evidence about congestion control.",
        metadata={"chunk_index": 0},
        distance=0.2,
        similarity=0.8,
    )


def _quiz_item(*, item_id: int) -> QuizItem:
    return QuizItem(
        id=item_id,
        user_id="demo-user",
        course_id=4,
        question="Question?",
        answer="Answer.",
        difficulty="medium",
        source_chunk_ids=[1],
        evidence_quote="Evidence.",
        options=[
            {"id": "A", "text": "Answer."},
            {"id": "B", "text": "Wrong."},
            {"id": "C", "text": "Wrong."},
            {"id": "D", "text": "Wrong."},
        ],
        correct_option_id="A",
        explanation="Because.",
        question_type="conceptual",
        traceability_label="fully_traceable",
        created_at=datetime(2026, 7, 18, 12, 0, 0),
    )
