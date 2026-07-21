from app.models.concept import Concept
from app.services.concepts import ResolvedConcept
from app.services.retrieval import RetrievedChunk
from app.services.tutor_context import build_tutor_evidence_context


def test_concept_evidence_is_used_without_course_fallback(monkeypatch) -> None:
    fallback_called = False

    def fake_concept_chunks(*args, **kwargs):  # type: ignore[no-untyped-def]
        return [
            _chunk(chunk_id=11, similarity=0.91),
            _chunk(chunk_id=12, similarity=0.82),
        ]

    def fake_retrieve(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal fallback_called
        fallback_called = True
        return []

    monkeypatch.setattr(
        "app.services.tutor_context.get_concept_quiz_chunks",
        fake_concept_chunks,
    )
    monkeypatch.setattr(
        "app.services.tutor_context.retrieve_relevant_chunks",
        fake_retrieve,
    )

    context = build_tutor_evidence_context(
        db=None,  # type: ignore[arg-type]
        query="Explain K-means clustering",
        user_id="demo-user",
        course_id=4,
        top_k=2,
        resolved_concept=_resolved_concept(),
    )

    assert fallback_called is False
    assert [chunk.chunk_id for chunk in context.chunks] == [11, 12]
    assert context.evidence_state.retrieval_scope == "concept"
    assert context.evidence_state.source_chunk_ids == [11, 12]


def test_concept_evidence_falls_back_and_deduplicates_course_chunks(
    monkeypatch,
) -> None:
    def fake_concept_chunks(*args, **kwargs):  # type: ignore[no-untyped-def]
        return [_chunk(chunk_id=11, similarity=0.32)]

    def fake_retrieve(*args, **kwargs):  # type: ignore[no-untyped-def]
        return [
            _chunk(chunk_id=12, similarity=0.88),
            _chunk(chunk_id=11, similarity=0.7),
            _chunk(chunk_id=13, similarity=0.61),
        ]

    monkeypatch.setattr(
        "app.services.tutor_context.get_concept_quiz_chunks",
        fake_concept_chunks,
    )
    monkeypatch.setattr(
        "app.services.tutor_context.retrieve_relevant_chunks",
        fake_retrieve,
    )

    context = build_tutor_evidence_context(
        db=None,  # type: ignore[arg-type]
        query="Explain K-means initialization",
        user_id="demo-user",
        course_id=4,
        top_k=3,
        resolved_concept=_resolved_concept(),
    )

    assert [chunk.chunk_id for chunk in context.chunks] == [12, 11, 13]
    assert context.evidence_state.retrieval_scope == "concept_with_course_fallback"
    assert context.evidence_state.source_chunk_ids == [12, 11, 13]
    assert "fallback evidence" in context.evidence_state.reason


def test_missing_concept_uses_course_retrieval(monkeypatch) -> None:
    def fake_retrieve(*args, **kwargs):  # type: ignore[no-untyped-def]
        return [_chunk(chunk_id=21, similarity=0.76)]

    monkeypatch.setattr(
        "app.services.tutor_context.retrieve_relevant_chunks",
        fake_retrieve,
    )

    context = build_tutor_evidence_context(
        db=None,  # type: ignore[arg-type]
        query="Help me study this lecture",
        user_id="demo-user",
        course_id=4,
        top_k=5,
        resolved_concept=None,
    )

    assert [chunk.chunk_id for chunk in context.chunks] == [21]
    assert context.evidence_state.retrieval_scope == "course"
    assert context.evidence_state.source_chunk_ids == [21]


def _resolved_concept() -> ResolvedConcept:
    return ResolvedConcept(
        concept=Concept(
            id=7,
            course_id=4,
            name="K-means Clustering",
            normalized_name="k means clustering",
            description="Clustering concept.",
            extraction_confidence=0.9,
        ),
        confidence=0.93,
        reason="exact normalized match",
    )


def _chunk(*, chunk_id: int, similarity: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=2,
        course_id=4,
        filename="lecture.pdf",
        content=f"Evidence chunk {chunk_id}.",
        metadata={},
        distance=round(1.0 - similarity, 3),
        similarity=similarity,
    )
