from datetime import datetime

from app.schemas.chat import ChatClaim, ChatResponse
from app.schemas.quiz import QuizItemResponse
from app.services.evaluation import evaluate_answer, evaluate_quiz_items


def test_evaluate_answer_scores_claim_support_and_refusal() -> None:
    response = ChatResponse(
        query="What is AI?",
        user_id="demo-user",
        mode="grounded_strict",
        answer_status="answered",
        answer="AI studies intelligent agents.",
        claims=[
            ChatClaim(
                claim="AI studies intelligent agents.",
                source_chunk_ids=[82],
                support_level="fully_supported",
                evidence_quote="AI is the field...",
            ),
            ChatClaim(
                claim="AI was invented in 2020.",
                source_chunk_ids=[],
                support_level="unsupported",
                evidence_quote="",
            ),
        ],
        overall_groundedness=0.5,
        sources=[],
    )

    result = evaluate_answer(response=response, expected_answerable=True)

    assert result.claim_count == 2
    assert result.supported_claim_count == 1
    assert result.unsupported_claim_rate == 0.5
    assert result.citation_precision == 1.0
    assert result.correct_refusal is True


def test_evaluate_answer_marks_correct_refusal_for_unanswerable_question() -> None:
    response = ChatResponse(
        query="What did the lecturer say about topic not in notes?",
        user_id="demo-user",
        mode="grounded_strict",
        answer_status="refused_no_evidence",
        answer="The uploaded materials do not contain enough information.",
        claims=[],
        overall_groundedness=0.0,
        sources=[],
    )

    result = evaluate_answer(response=response, expected_answerable=False)

    assert result.correct_refusal is True


def test_evaluate_quiz_items_counts_traceability_labels() -> None:
    created_at = datetime(2026, 6, 21, 12, 0, 0)
    items = [
        QuizItemResponse(
            id=1,
            user_id="demo-user",
            question="Q1?",
            answer="A1.",
            difficulty="medium",
            source_chunk_ids=[82],
            evidence_quote="Evidence.",
            question_type="conceptual",
            traceability_label="fully_traceable",
            created_at=created_at,
        ),
        QuizItemResponse(
            id=2,
            user_id="demo-user",
            question="Q2?",
            answer="A2.",
            difficulty="medium",
            source_chunk_ids=[],
            evidence_quote="",
            question_type="conceptual",
            traceability_label="not_traceable",
            created_at=created_at,
        ),
    ]

    result = evaluate_quiz_items(items=items)

    assert result.total_items == 2
    assert result.fully_traceable_count == 1
    assert result.not_traceable_count == 1
    assert result.traceable_item_rate == 0.5
