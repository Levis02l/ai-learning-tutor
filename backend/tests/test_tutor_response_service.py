from datetime import datetime

import pytest

from app.llm.provider import LLMResponse
from app.models.quiz import QuizItem
from app.services.policy import POLICY_VERSION, PolicyDecision
from app.services.quiz import QuizGenerationError
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


def test_llm_response_reuses_decision_evidence_without_retrieval(monkeypatch) -> None:
    provider = FakeLLMProvider(
        text=(
            '{"answer_status": "answered", "answer": "Tutor answer.", '
            '"claims": [{"claim": "Supported claim", "source_chunk_ids": [7], '
            '"support_level": "fully_supported", "evidence_quote": "Evidence."}]}'
        )
    )

    def fail_retrieval(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Response should reuse decision evidence")

    monkeypatch.setattr(
        "app.services.tutor_response.retrieve_relevant_chunks",
        fail_retrieval,
    )

    response = execute_tutor_decision(
        db=None,  # type: ignore[arg-type]
        decision=_decision(
            selected_action="explain",
            response_strategy="guided",
            evidence_chunks=[_chunk(chunk_id=7)],
        ),
        llm_provider=provider,
    )

    assert [source.chunk_id for source in response.sources] == [7]
    assert response.claims[0].source_chunk_ids == [7]
    prompt = provider.calls[0]["user_prompt"]
    assert "chunk_id: 7" in prompt


def test_scaffolded_concept_explanation_returns_comprehension_check(
    monkeypatch,
) -> None:
    provider = FakeLLMProvider()
    captured: dict[str, object] = {}

    def fake_generate_check(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["concept_id"] = kwargs["concept_id"]
        captured["chunk_ids"] = [chunk.chunk_id for chunk in kwargs["chunks"]]
        captured["difficulty"] = kwargs["difficulty"]
        return _quiz_item(
            item_id=33,
            concept_id=kwargs["concept_id"],
            origin="comprehension_check",
        )

    monkeypatch.setattr(
        "app.services.tutor_response.generate_comprehension_check",
        fake_generate_check,
    )

    response = execute_tutor_decision(
        db=None,  # type: ignore[arg-type]
        decision=_decision(
            selected_action="explain",
            response_strategy="scaffolded",
            evidence_chunks=[_chunk(chunk_id=7)],
            concept_state_snapshot=_concept_snapshot(),
        ),
        llm_provider=provider,
    )

    assert captured == {"concept_id": 9, "chunk_ids": [7], "difficulty": "easy"}
    assert len(response.quiz_items) == 1
    assert response.quiz_items[0].origin == "comprehension_check"
    assert response.quiz_items[0].concept_id == 9


def test_comprehension_check_failure_does_not_fail_explanation(monkeypatch) -> None:
    provider = FakeLLMProvider()

    def raise_generation_error(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise QuizGenerationError("quiz generation failed")

    monkeypatch.setattr(
        "app.services.tutor_response.generate_comprehension_check",
        raise_generation_error,
    )

    response = execute_tutor_decision(
        db=None,  # type: ignore[arg-type]
        decision=_decision(
            selected_action="explain",
            response_strategy="scaffolded",
            evidence_chunks=[_chunk(chunk_id=7)],
            concept_state_snapshot=_concept_snapshot(),
        ),
        llm_provider=provider,
    )

    assert response.answer_status == "answered"
    assert response.answer == "Tutor answer."
    assert response.quiz_items == []


def test_concise_explanation_does_not_force_comprehension_check(monkeypatch) -> None:
    provider = FakeLLMProvider()

    def fail_check(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Concise explanations should not force checks in V1")

    monkeypatch.setattr(
        "app.services.tutor_response.generate_comprehension_check",
        fail_check,
    )

    response = execute_tutor_decision(
        db=None,  # type: ignore[arg-type]
        decision=_decision(
            selected_action="explain",
            response_strategy="concise",
            evidence_chunks=[_chunk(chunk_id=7)],
            concept_state_snapshot=_concept_snapshot(),
        ),
        llm_provider=provider,
    )

    assert response.quiz_items == []


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


def test_contrastive_strategy_uses_misconception_aware_prompt(monkeypatch) -> None:
    provider = FakeLLMProvider()
    monkeypatch.setattr(
        "app.services.tutor_response.retrieve_relevant_chunks",
        lambda **kwargs: [_chunk()],
    )

    execute_tutor_decision(
        db=None,  # type: ignore[arg-type]
        decision=_decision(
            selected_action="explain",
            response_strategy="contrastive",
            misconception_snapshot={
                "id": 13,
                "misconception_type": "concept_confusion",
                "description": "The learner confused clustering with classification.",
                "confidence": 0.86,
                "quiz_attempt_id": 22,
                "concept_id": 9,
                "created_at": "2026-07-21T12:00:00",
            },
        ),
        llm_provider=provider,
    )

    prompt = provider.calls[0]["user_prompt"]
    assert "Response strategy:\ncontrastive" in prompt
    assert "concept_confusion" in prompt
    assert "Private misconception teaching signal" in prompt
    assert "0.86" not in prompt
    assert "quiz_attempt_id" not in prompt
    assert "Explicitly contrast the confused concepts" in prompt


@pytest.mark.parametrize(
    ("strategy", "expected_instruction"),
    [
        ("contrastive", "Explicitly contrast the confused concepts"),
        ("definition_clarification", "Start by correcting the mistaken definition"),
        ("prerequisite_scaffolded", "establish the likely missing prerequisite"),
        ("reasoning_guidance", "Focus on the reasoning step"),
        ("source_correction", "Point to the relevant source excerpt"),
    ],
)
def test_misconception_strategies_have_distinct_prompt_instructions(
    monkeypatch,
    strategy: str,
    expected_instruction: str,
) -> None:
    provider = FakeLLMProvider()
    monkeypatch.setattr(
        "app.services.tutor_response.retrieve_relevant_chunks",
        lambda **kwargs: [_chunk()],
    )

    execute_tutor_decision(
        db=None,  # type: ignore[arg-type]
        decision=_decision(
            selected_action="explain",
            response_strategy=strategy,
            misconception_snapshot=_misconception_snapshot(strategy=strategy),
        ),
        llm_provider=provider,
    )

    prompt = provider.calls[0]["user_prompt"]
    assert f"Response strategy:\n{strategy}" in prompt
    assert expected_instruction in prompt
    assert "Do not mention the internal label" in prompt


def test_quiz_action_reuses_quiz_service_for_one_item(monkeypatch) -> None:
    captured: dict[str, int | str] = {}

    def fake_generate_quiz_items(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["count"] = kwargs["count"]
        captured["difficulty"] = kwargs["difficulty"]
        captured["origin"] = kwargs["origin"]
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

    assert captured == {"count": 1, "difficulty": "hard", "origin": "policy_quiz"}
    assert response.answer_status == "quiz_ready"
    assert response.quiz_items[0].id == 7


def test_policy_quiz_uses_decision_evidence_without_live_retrieval(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_generate_from_chunks(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["chunk_ids"] = [
            chunk.chunk_id for chunk in kwargs["chunks"]
        ]
        captured["concept_id"] = kwargs["concept_id"]
        captured["count"] = kwargs["count"]
        captured["difficulty"] = kwargs["difficulty"]
        captured["origin"] = kwargs["origin"]
        item = _quiz_item(
            item_id=8,
            concept_id=kwargs["concept_id"],
            origin=kwargs["origin"],
        )
        item.source_chunk_ids = [7]
        return [item]

    def fail_live_retrieval(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Policy quiz must not re-run live retrieval")

    monkeypatch.setattr(
        "app.services.tutor_response.generate_quiz_items_from_chunks",
        fake_generate_from_chunks,
    )
    monkeypatch.setattr(
        "app.services.tutor_response.generate_quiz_items",
        fail_live_retrieval,
    )

    response = execute_tutor_decision(
        db=None,  # type: ignore[arg-type]
        decision=_decision(
            selected_action="quiz",
            response_strategy="challenging",
            evidence_chunks=[_chunk(chunk_id=7), _chunk(chunk_id=8)],
            concept_state_snapshot=_concept_snapshot(),
        ),
        llm_provider=FailingLLMProvider(),
    )

    assert captured == {
        "chunk_ids": [7, 8],
        "concept_id": 9,
        "count": 1,
        "difficulty": "hard",
        "origin": "policy_quiz",
    }
    assert response.answer_status == "quiz_ready"
    assert response.quiz_items[0].origin == "policy_quiz"
    assert set(response.quiz_items[0].source_chunk_ids).issubset({7, 8})


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
    evidence_chunks: list[RetrievedChunk] | None = None,
    concept_state_snapshot: dict | None = None,
    misconception_snapshot: dict | None = None,
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
            "retrieval_scope": "course",
            "source_chunk_ids": [chunk.chunk_id for chunk in evidence_chunks or []],
        },
        learner_state_scope="concept" if concept_state_snapshot else "course",
        concept_state_snapshot=concept_state_snapshot,
        misconception_snapshot=misconception_snapshot,
        evidence_chunks=evidence_chunks or [],
    )


def _chunk(*, chunk_id: int = 1) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=2,
        course_id=4,
        filename="lecture.pdf",
        content="Evidence about congestion control.",
        metadata={"chunk_index": 0},
        distance=0.2,
        similarity=0.8,
    )


def _concept_snapshot() -> dict:
    return {
        "concept_id": 9,
        "concept_name": "K-means Clustering",
        "state_status": "observed",
        "mastery_score": 0.25,
        "recent_accuracy": 0.2,
        "attempt_count": 3,
        "consecutive_errors": 2,
        "last_attempted_at": None,
        "review_due": False,
        "needs_attention": True,
    }


def _misconception_snapshot(*, strategy: str) -> dict:
    misconception_type = {
        "contrastive": "concept_confusion",
        "definition_clarification": "incorrect_definition",
        "prerequisite_scaffolded": "missing_prerequisite",
        "reasoning_guidance": "incomplete_reasoning",
        "source_correction": "source_misinterpretation",
    }[strategy]
    return {
        "id": 13,
        "misconception_type": misconception_type,
        "description": "The learner needs targeted corrective teaching.",
        "confidence": 0.86,
        "quiz_attempt_id": 22,
        "concept_id": 9,
        "created_at": "2026-07-21T12:00:00",
    }


def _quiz_item(
    *,
    item_id: int,
    concept_id: int | None = None,
    origin: str = "manual_practice",
) -> QuizItem:
    return QuizItem(
        id=item_id,
        user_id="demo-user",
        course_id=4,
        concept_id=concept_id,
        question="Question?",
        answer="Answer.",
        difficulty="medium",
        origin=origin,
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
