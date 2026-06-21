from app.schemas.chat import ChatResponse
from app.schemas.evaluation import AnswerEvaluationResponse, QuizEvaluationResponse
from app.schemas.quiz import QuizItemResponse

SUPPORTED_LABELS = {"fully_supported", "partially_supported"}
REFUSAL_STATUSES = {
    "refused_no_evidence",
    "refused_ambiguous_material",
    "needs_more_material",
}
TRACEABLE_LABELS = {"fully_traceable", "partially_traceable"}


def evaluate_answer(
    *,
    response: ChatResponse,
    expected_answerable: bool,
) -> AnswerEvaluationResponse:
    claim_count = len(response.claims)
    supported_claim_count = sum(
        1 for claim in response.claims if claim.support_level in SUPPORTED_LABELS
    )
    unsupported_claim_count = sum(
        1 for claim in response.claims if claim.support_level == "unsupported"
    )
    contradicted_claim_count = sum(
        1 for claim in response.claims if claim.support_level == "contradicted"
    )
    cited_claim_count = sum(1 for claim in response.claims if claim.source_chunk_ids)
    correctly_cited_claim_count = sum(
        1
        for claim in response.claims
        if claim.source_chunk_ids and claim.support_level in SUPPORTED_LABELS
    )
    citation_precision = (
        correctly_cited_claim_count / cited_claim_count if cited_claim_count else 0.0
    )
    unsupported_claim_rate = (
        unsupported_claim_count / claim_count if claim_count else 0.0
    )
    refused = response.answer_status in REFUSAL_STATUSES

    return AnswerEvaluationResponse(
        claim_count=claim_count,
        supported_claim_count=supported_claim_count,
        unsupported_claim_count=unsupported_claim_count,
        contradicted_claim_count=contradicted_claim_count,
        citation_precision=round(citation_precision, 3),
        unsupported_claim_rate=round(unsupported_claim_rate, 3),
        groundedness_score=response.overall_groundedness,
        correct_refusal=(not expected_answerable and refused)
        or (expected_answerable and not refused),
    )


def evaluate_quiz_items(*, items: list[QuizItemResponse]) -> QuizEvaluationResponse:
    label_counts: dict[str, int] = {}
    for item in items:
        label_counts[item.traceability_label] = (
            label_counts.get(item.traceability_label, 0) + 1
        )

    total_items = len(items)
    fully_traceable_count = label_counts.get("fully_traceable", 0)
    partially_traceable_count = label_counts.get("partially_traceable", 0)
    weakly_traceable_count = label_counts.get("weakly_traceable", 0)
    not_traceable_count = label_counts.get("not_traceable", 0)
    traceable_count = sum(
        count for label, count in label_counts.items() if label in TRACEABLE_LABELS
    )

    return QuizEvaluationResponse(
        total_items=total_items,
        fully_traceable_count=fully_traceable_count,
        partially_traceable_count=partially_traceable_count,
        weakly_traceable_count=weakly_traceable_count,
        not_traceable_count=not_traceable_count,
        traceable_item_rate=round(
            traceable_count / total_items if total_items else 0.0,
            3,
        ),
        label_counts=label_counts,
    )
