from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from app.services.concepts import (
    ResolvedConcept,
    get_concept_quiz_chunks,
)
from app.services.retrieval import RetrievedChunk, retrieve_relevant_chunks

TutorEvidenceStrength = Literal[
    "high",
    "medium",
    "low",
    "insufficient",
    "not_required",
]
TutorRetrievalScope = Literal[
    "course",
    "concept",
    "concept_with_course_fallback",
    "not_required",
]


@dataclass(frozen=True)
class TutorEvidenceState:
    evidence_strength: TutorEvidenceStrength
    source_coverage: float
    retrieved_chunk_count: int
    top_similarity: float
    requires_evidence: bool
    reason: str
    retrieval_scope: TutorRetrievalScope = "course"
    source_chunk_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class TutorEvidenceContext:
    resolved_concept: ResolvedConcept | None
    chunks: list[RetrievedChunk]
    evidence_state: TutorEvidenceState


def build_tutor_evidence_context(
    db: Session,
    *,
    query: str,
    user_id: str,
    course_id: int | None,
    top_k: int,
    resolved_concept: ResolvedConcept | None = None,
) -> TutorEvidenceContext:
    if course_id is None or resolved_concept is None:
        chunks = retrieve_relevant_chunks(
            db=db,
            query=query,
            user_id=user_id,
            course_id=course_id,
            top_k=top_k,
        )
        return TutorEvidenceContext(
            resolved_concept=resolved_concept,
            chunks=chunks,
            evidence_state=build_evidence_state_from_chunks(
                chunks,
                retrieval_scope="course",
            ),
        )

    concept_chunks = get_concept_quiz_chunks(
        db=db,
        user_id=user_id,
        course_id=course_id,
        concept_id=resolved_concept.concept.id,
        limit=top_k,
    )
    concept_state = build_evidence_state_from_chunks(
        concept_chunks,
        retrieval_scope="concept",
    )
    should_fallback = (
        len(concept_chunks) < top_k
        or concept_state.evidence_strength in {"low", "insufficient"}
    )
    if not should_fallback:
        return TutorEvidenceContext(
            resolved_concept=resolved_concept,
            chunks=concept_chunks,
            evidence_state=concept_state,
        )

    course_chunks = retrieve_relevant_chunks(
        db=db,
        query=query,
        user_id=user_id,
        course_id=course_id,
        top_k=top_k,
    )
    chunks = _merge_and_rerank_chunks(
        concept_chunks=concept_chunks,
        course_chunks=course_chunks,
        top_k=top_k,
    )
    fallback_state = build_evidence_state_from_chunks(
        chunks,
        retrieval_scope="concept_with_course_fallback",
    )
    return TutorEvidenceContext(
        resolved_concept=resolved_concept,
        chunks=chunks,
        evidence_state=TutorEvidenceState(
            evidence_strength=fallback_state.evidence_strength,
            source_coverage=fallback_state.source_coverage,
            retrieved_chunk_count=fallback_state.retrieved_chunk_count,
            top_similarity=fallback_state.top_similarity,
            requires_evidence=fallback_state.requires_evidence,
            reason=(
                "Concept-linked evidence was combined with course-level "
                f"fallback evidence. {fallback_state.reason}"
            ),
            retrieval_scope=fallback_state.retrieval_scope,
            source_chunk_ids=fallback_state.source_chunk_ids,
        ),
    )


def build_not_required_evidence_context(
    *,
    resolved_concept: ResolvedConcept | None = None,
) -> TutorEvidenceContext:
    return TutorEvidenceContext(
        resolved_concept=resolved_concept,
        chunks=[],
        evidence_state=TutorEvidenceState(
            evidence_strength="not_required",
            source_coverage=1.0,
            retrieved_chunk_count=0,
            top_similarity=0.0,
            requires_evidence=False,
            reason=(
                "Existing due review items are already traceable, so new "
                "retrieval evidence is not required for this decision."
            ),
            retrieval_scope="not_required",
            source_chunk_ids=[],
        ),
    )


def build_evidence_state_from_chunks(
    chunks: list[RetrievedChunk],
    *,
    retrieval_scope: TutorRetrievalScope = "course",
) -> TutorEvidenceState:
    if not chunks:
        return TutorEvidenceState(
            evidence_strength="insufficient",
            source_coverage=0.0,
            retrieved_chunk_count=0,
            top_similarity=0.0,
            requires_evidence=True,
            reason="No relevant course chunks were retrieved.",
            retrieval_scope=retrieval_scope,
            source_chunk_ids=[],
        )

    top_similarity = round(max(chunk.similarity for chunk in chunks), 3)
    source_coverage = round(
        sum(1 for chunk in chunks if chunk.similarity >= 0.35) / len(chunks),
        3,
    )
    if top_similarity >= 0.55:
        evidence_strength: TutorEvidenceStrength = "high"
    elif top_similarity >= 0.4:
        evidence_strength = "medium"
    elif top_similarity >= 0.3:
        evidence_strength = "low"
    else:
        evidence_strength = "insufficient"

    return TutorEvidenceState(
        evidence_strength=evidence_strength,
        source_coverage=source_coverage,
        retrieved_chunk_count=len(chunks),
        top_similarity=top_similarity,
        requires_evidence=True,
        reason=f"Top retrieval similarity is {top_similarity}.",
        retrieval_scope=retrieval_scope,
        source_chunk_ids=[chunk.chunk_id for chunk in chunks],
    )


def _merge_and_rerank_chunks(
    *,
    concept_chunks: list[RetrievedChunk],
    course_chunks: list[RetrievedChunk],
    top_k: int,
) -> list[RetrievedChunk]:
    by_chunk_id: dict[int, RetrievedChunk] = {}
    for chunk in [*concept_chunks, *course_chunks]:
        existing = by_chunk_id.get(chunk.chunk_id)
        if existing is None or chunk.similarity > existing.similarity:
            by_chunk_id[chunk.chunk_id] = chunk

    return sorted(
        by_chunk_id.values(),
        key=lambda chunk: (-chunk.similarity, chunk.chunk_id),
    )[:top_k]
