from datetime import datetime

from app.schemas.chat import ChatClaim, ChatResponse
from app.schemas.evidence_state import EvidenceStateResponse
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
        evidence_state=_evidence_state(),
        sources=[],
    )

    result = evaluate_answer(response=response, answerability="answerable")

    assert result.claim_count == 2
    assert result.supported_claim_count == 1
    assert result.generated_unsupported_claim_rate == 0.5
    assert result.automatic_cited_claim_support_rate == 1.0
    assert result.citation_coverage == 0.5
    assert result.citation_applicable is True
    assert result.automatic_refusal_correctness is True


def test_evaluate_answer_marks_correct_refusal_for_unanswerable_question() -> None:
    response = ChatResponse(
        query="What did the lecturer say about topic not in notes?",
        user_id="demo-user",
        mode="grounded_strict",
        answer_status="refused_no_evidence",
        answer="The uploaded materials do not contain enough information.",
        claims=[],
        overall_groundedness=0.0,
        evidence_state=_evidence_state(
            evidence_strength="none",
            source_coverage=0.0,
            supported_claim_count=0,
            answer_status="refused_no_evidence",
        ),
        sources=[],
    )

    result = evaluate_answer(response=response, answerability="unanswerable")

    assert result.refused_by_status is True
    assert result.effective_refusal is True
    assert result.automatic_refusal_correctness is True


def test_evaluate_answer_detects_semantic_refusal_when_status_is_answered() -> None:
    response = ChatResponse(
        query="What is the exam date?",
        user_id="demo-user",
        mode="ungrounded",
        answer_status="answered",
        answer="I cannot determine the final exam date from the uploaded material.",
        claims=[
            ChatClaim(
                claim=(
                    "I cannot determine the final exam date from the uploaded "
                    "material."
                ),
                source_chunk_ids=[],
                support_level="unsupported",
                evidence_quote="",
            )
        ],
        overall_groundedness=0.0,
        evidence_state=_evidence_state(
            evidence_strength="none",
            source_coverage=0.0,
            supported_claim_count=0,
            answer_status="answered",
        ),
        sources=[],
    )

    result = evaluate_answer(response=response, answerability="unanswerable")

    assert result.refused_by_status is False
    assert result.semantic_refusal is True
    assert result.effective_refusal is True
    assert result.automatic_refusal_correctness is True
    assert result.citation_applicable is False
    assert result.automatic_cited_claim_support_rate is None


def test_evaluate_answer_marks_ungrounded_citation_as_not_applicable() -> None:
    response = ChatResponse(
        query="What objective does K-means minimise?",
        user_id="demo-user",
        mode="ungrounded",
        answer_status="answered",
        answer="K-means minimises within-cluster sum of squares.",
        claims=[
            ChatClaim(
                claim="K-means minimises within-cluster sum of squares.",
                source_chunk_ids=[],
                support_level="unsupported",
                evidence_quote="",
            )
        ],
        overall_groundedness=0.0,
        evidence_state=_evidence_state(
            evidence_strength="none",
            source_coverage=0.0,
            supported_claim_count=0,
            answer_status="answered",
        ),
        sources=[],
    )

    result = evaluate_answer(response=response, answerability="answerable")

    assert result.citation_applicable is False
    assert result.automatic_cited_claim_support_rate is None
    assert result.citation_coverage is None


def test_partial_answerability_is_not_scored_as_correct_or_false_refusal() -> None:
    response = ChatResponse(
        query="What K does the course recommend and how should K be chosen?",
        user_id="demo-user",
        mode="grounded_strict",
        answer_status="answered",
        answer=(
            "The material states K is chosen externally, but the exact "
            "selection rule is not provided in the uploaded excerpts."
        ),
        claims=[
            ChatClaim(
                claim="K is chosen externally.",
                source_chunk_ids=[94],
                support_level="fully_supported",
                evidence_quote="K is fixed externally.",
            ),
            ChatClaim(
                claim="The exact selection rule is not provided.",
                source_chunk_ids=[],
                support_level="not_enough_information",
                evidence_quote="",
            ),
        ],
        overall_groundedness=0.5,
        evidence_state=_evidence_state(
            evidence_strength="medium",
            source_coverage=0.5,
            supported_claim_count=1,
            answer_status="partially_answered",
        ),
        sources=[],
    )

    result = evaluate_answer(
        response=response,
        answerability="partially_answerable",
    )

    assert result.semantic_refusal is True
    assert result.effective_refusal is True
    assert result.automatic_refusal_correctness is None


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


def _evidence_state(
    *,
    evidence_strength: str = "medium",
    source_coverage: float = 0.5,
    supported_claim_count: int = 1,
    answer_status: str = "answered",
) -> EvidenceStateResponse:
    return EvidenceStateResponse(
        evidence_strength=evidence_strength,  # type: ignore[arg-type]
        source_coverage=source_coverage,
        supported_claim_count=supported_claim_count,
        unsupported_claim_count=1,
        contradicted_claim_count=0,
        answer_status=answer_status,  # type: ignore[arg-type]
    )
