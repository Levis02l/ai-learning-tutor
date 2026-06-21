import pytest

from app.llm.provider import LLMProviderError
from app.services.rag import (
    EvidenceClaimPayload,
    RagClaim,
    _calculate_groundedness,
    _parse_evidence_answer,
    _sanitize_claims,
)


def test_parse_evidence_answer_accepts_json() -> None:
    payload = _parse_evidence_answer(
        '{"answer_status": "answered", "answer": "A. [S1]", '
        '"claims": [{"claim": "A.", "source_chunk_ids": [1], '
        '"support_level": "fully_supported", "evidence_quote": "A."}]}'
    )

    assert payload.answer_status == "answered"
    assert payload.claims[0].source_chunk_ids == [1]


def test_parse_evidence_answer_accepts_markdown_json_fence() -> None:
    payload = _parse_evidence_answer(
        '```json\n{"answer_status": "refused_no_evidence", '
        '"answer": "Not enough evidence.", "claims": []}\n```'
    )

    assert payload.answer_status == "refused_no_evidence"


def test_parse_evidence_answer_rejects_invalid_json() -> None:
    with pytest.raises(LLMProviderError):
        _parse_evidence_answer("not json")


def test_sanitize_claims_filters_invalid_chunk_ids() -> None:
    claims = [
        EvidenceClaimPayload(
            claim="AI studies intelligent agents.",
            source_chunk_ids=[82, 999],
            support_level="fully_supported",
            evidence_quote="AI is the field...",
        )
    ]

    sanitized = _sanitize_claims(claims, valid_chunk_ids={82})

    assert sanitized[0].source_chunk_ids == [82]


def test_sanitize_claims_marks_supported_claim_without_sources_unsupported() -> None:
    claims = [
        EvidenceClaimPayload(
            claim="AI studies intelligent agents.",
            source_chunk_ids=[999],
            support_level="fully_supported",
            evidence_quote="AI is the field...",
        )
    ]

    sanitized = _sanitize_claims(claims, valid_chunk_ids={82})

    assert sanitized[0].support_level == "unsupported"


def test_calculate_groundedness_scores_claim_support() -> None:
    claims = [
        RagClaim(
            claim="A",
            source_chunk_ids=[1],
            support_level="fully_supported",
            evidence_quote="A",
        ),
        RagClaim(
            claim="B",
            source_chunk_ids=[2],
            support_level="partially_supported",
            evidence_quote="B",
        ),
        RagClaim(
            claim="C",
            source_chunk_ids=[],
            support_level="unsupported",
            evidence_quote="",
        ),
    ]

    assert _calculate_groundedness(claims) == 0.5
