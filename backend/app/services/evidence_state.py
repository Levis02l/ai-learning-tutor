from dataclasses import dataclass

from app.services.rag import AnswerStatus, RagAnswer, SupportLevel


@dataclass(frozen=True)
class EvidenceState:
    evidence_strength: str
    source_coverage: float
    supported_claim_count: int
    unsupported_claim_count: int
    contradicted_claim_count: int
    answer_status: AnswerStatus


def build_evidence_state(answer: RagAnswer) -> EvidenceState:
    claim_count = len(answer.claims)
    supported_claim_count = sum(
        1 for claim in answer.claims if _is_supported(claim.support_level)
    )
    unsupported_claim_count = sum(
        1 for claim in answer.claims if claim.support_level == "unsupported"
    )
    contradicted_claim_count = sum(
        1 for claim in answer.claims if claim.support_level == "contradicted"
    )
    source_coverage = (
        round(supported_claim_count / claim_count, 3) if claim_count else 0.0
    )

    return EvidenceState(
        evidence_strength=_classify_evidence_strength(
            answer=answer,
            source_coverage=source_coverage,
            unsupported_claim_count=unsupported_claim_count,
            contradicted_claim_count=contradicted_claim_count,
        ),
        source_coverage=source_coverage,
        supported_claim_count=supported_claim_count,
        unsupported_claim_count=unsupported_claim_count,
        contradicted_claim_count=contradicted_claim_count,
        answer_status=answer.answer_status,
    )


def _is_supported(support_level: SupportLevel) -> bool:
    return support_level in {"fully_supported", "partially_supported"}


def _classify_evidence_strength(
    *,
    answer: RagAnswer,
    source_coverage: float,
    unsupported_claim_count: int,
    contradicted_claim_count: int,
) -> str:
    if answer.answer_status in {"refused_no_evidence", "needs_more_material"}:
        return "none"
    if contradicted_claim_count > 0:
        return "conflicting"
    if not answer.sources or not answer.claims:
        return "none"
    if answer.overall_groundedness >= 0.85 and source_coverage >= 0.8:
        return "high"
    if (
        answer.overall_groundedness >= 0.55
        and source_coverage >= 0.5
        and unsupported_claim_count <= 1
    ):
        return "medium"
    return "low"

