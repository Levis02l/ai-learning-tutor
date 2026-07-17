from app.services.evidence_state import build_evidence_state
from app.services.rag import RagAnswer, RagClaim, RagSource


def test_evidence_state_marks_high_when_claims_are_supported() -> None:
    answer = RagAnswer(
        mode="grounded_strict",
        answer_status="answered",
        answer="AI studies intelligent agents. [S1]",
        claims=[
            RagClaim(
                claim="AI studies intelligent agents.",
                source_chunk_ids=[1],
                support_level="fully_supported",
                evidence_quote="AI is the field...",
            )
        ],
        overall_groundedness=1.0,
        sources=[
            RagSource(
                chunk_id=1,
                document_id=1,
                filename="lecture.pdf",
                content="AI is the field...",
                metadata={},
                distance=0.1,
                similarity=0.9,
            )
        ],
    )

    state = build_evidence_state(answer)

    assert state.evidence_strength == "high"
    assert state.source_coverage == 1.0
    assert state.supported_claim_count == 1
    assert state.unsupported_claim_count == 0


def test_evidence_state_marks_conflicting_when_any_claim_contradicts() -> None:
    answer = RagAnswer(
        mode="grounded_strict",
        answer_status="answered",
        answer="Claim.",
        claims=[
            RagClaim(
                claim="Claim.",
                source_chunk_ids=[1],
                support_level="contradicted",
                evidence_quote="Opposite evidence.",
            )
        ],
        overall_groundedness=0.0,
        sources=[
            RagSource(
                chunk_id=1,
                document_id=1,
                filename="lecture.pdf",
                content="Opposite evidence.",
                metadata={},
                distance=0.1,
                similarity=0.9,
            )
        ],
    )

    state = build_evidence_state(answer)

    assert state.evidence_strength == "conflicting"
    assert state.contradicted_claim_count == 1


def test_evidence_state_marks_none_for_refusal() -> None:
    answer = RagAnswer(
        mode="grounded_strict",
        answer_status="refused_no_evidence",
        answer="Not enough evidence.",
        claims=[],
        overall_groundedness=0.0,
        sources=[],
    )

    state = build_evidence_state(answer)

    assert state.evidence_strength == "none"
    assert state.source_coverage == 0.0

