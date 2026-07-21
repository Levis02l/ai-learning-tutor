from app.models.concept import Concept, ConceptPrerequisite, ConceptSourceChunk
from app.services.concepts import (
    _ConceptCandidate,
    _deduplicate_candidates,
    _normalize_name,
    _parse_generated_concepts,
    _to_candidates,
    _upsert_concept_graph,
    resolve_concept_for_focus,
)


def test_parse_and_deduplicate_generated_concepts() -> None:
    payload = _parse_generated_concepts(
        """
        ```json
        {
          "concepts": [
            {
              "name": "Introduction to Artificial Intelligence",
              "description": "Short.",
              "extraction_confidence": 0.6,
              "source_chunk_ids": [1],
              "prerequisites": []
            },
            {
              "name": "Artificial Intelligence",
              "description": "A longer course-grounded description.",
              "extraction_confidence": 0.9,
              "source_chunk_ids": [1, 2],
              "prerequisites": []
            },
            {
              "name": "Machine Learning",
              "description": "Learning from data.",
              "extraction_confidence": 0.8,
              "source_chunk_ids": [3],
              "prerequisites": ["Artificial Intelligence"]
            }
          ]
        }
        ```
        """
    )

    candidates = _deduplicate_candidates(
        _to_candidates(payload.concepts),
        max_concepts=10,
    )

    assert _normalize_name("Introduction to Artificial Intelligence") == (
        "artificial intelligence"
    )
    assert _normalize_name("Introduction to AI") == "artificial intelligence"
    assert len(candidates) == 2
    ai = candidates[0]
    assert ai.normalized_name == "artificial intelligence"
    assert ai.description == "A longer course-grounded description."
    assert ai.extraction_confidence == 0.9
    assert ai.source_chunk_ids == [1, 2]
    assert candidates[1].prerequisites == ["Artificial Intelligence"]


def test_upsert_concept_graph_is_idempotent() -> None:
    db = _FakeSession()
    candidates = [
        _ConceptCandidate(
            name="Artificial Intelligence",
            normalized_name="artificial intelligence",
            description="AI basics.",
            extraction_confidence=0.9,
            source_chunk_ids=[1, 2],
            prerequisites=[],
        ),
        _ConceptCandidate(
            name="Machine Learning",
            normalized_name="machine learning",
            description="Learning from data.",
            extraction_confidence=0.8,
            source_chunk_ids=[2],
            prerequisites=["Artificial Intelligence"],
        ),
    ]

    first = _upsert_concept_graph(
        db=db,  # type: ignore[arg-type]
        course_id=7,
        candidates=candidates,
        valid_chunk_ids={1, 2},
    )
    second = _upsert_concept_graph(
        db=db,  # type: ignore[arg-type]
        course_id=7,
        candidates=candidates,
        valid_chunk_ids={1, 2},
    )

    assert first.concepts_created == 2
    assert first.concepts_reused == 0
    assert first.source_links_created == 3
    assert first.prerequisites_created == 1
    assert second.concepts_created == 0
    assert second.concepts_reused == 2
    assert second.source_links_created == 0
    assert second.prerequisites_created == 0
    assert len(db.concepts) == 2
    assert len(db.source_links) == 3
    assert len(db.prerequisite_links) == 1


def test_upsert_skips_candidates_without_valid_sources() -> None:
    db = _FakeSession()

    stats = _upsert_concept_graph(
        db=db,  # type: ignore[arg-type]
        course_id=7,
        candidates=[
            _ConceptCandidate(
                name="Unsupported Concept",
                normalized_name="unsupported concept",
                description="No source.",
                extraction_confidence=0.4,
                source_chunk_ids=[999],
                prerequisites=[],
            )
        ],
        valid_chunk_ids={1},
    )

    assert stats.candidates_skipped == 1
    assert stats.concepts_created == 0
    assert db.concepts == []


def test_resolve_concept_for_focus_uses_conservative_matching() -> None:
    db = _FakeSession()
    db.concepts = [
        _concept(
            concept_id=1,
            name="Machine Learning",
            normalized_name="machine learning",
        ),
        _concept(
            concept_id=2,
            name="Supervised Learning",
            normalized_name="supervised learning",
        ),
    ]

    resolved = resolve_concept_for_focus(
        db,  # type: ignore[arg-type]
        user_id="demo-user",
        course_id=7,
        focus="Quiz me on supervised learning",
    )
    broad = resolve_concept_for_focus(
        db,  # type: ignore[arg-type]
        user_id="demo-user",
        course_id=7,
        focus="learning",
    )

    assert resolved is not None
    assert resolved.concept.id == 2
    assert resolved.confidence >= 0.72
    assert broad is None


class _FakeSession:
    def __init__(self) -> None:
        self.concepts: list[Concept] = []
        self.source_links: list[ConceptSourceChunk] = []
        self.prerequisite_links: list[ConceptPrerequisite] = []
        self._next_concept_id = 1

    def scalars(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self.concepts

    def add(self, item):  # type: ignore[no-untyped-def]
        if isinstance(item, Concept) and item not in self.concepts:
            self.concepts.append(item)
        if isinstance(item, ConceptSourceChunk) and item not in self.source_links:
            self.source_links.append(item)
        if (
            isinstance(item, ConceptPrerequisite)
            and item not in self.prerequisite_links
        ):
            self.prerequisite_links.append(item)

    def flush(self) -> None:
        for concept in self.concepts:
            if concept.id is None:
                concept.id = self._next_concept_id
                self._next_concept_id += 1

    def get(self, model, key):  # type: ignore[no-untyped-def]
        if model is ConceptSourceChunk:
            concept_id, chunk_id = key
            return next(
                (
                    link
                    for link in self.source_links
                    if link.concept_id == concept_id and link.chunk_id == chunk_id
                ),
                None,
            )
        if model is ConceptPrerequisite:
            concept_id, prerequisite_concept_id = key
            return next(
                (
                    link
                    for link in self.prerequisite_links
                    if link.concept_id == concept_id
                    and link.prerequisite_concept_id == prerequisite_concept_id
                ),
                None,
            )
        return None

    def commit(self) -> None:
        return None


def _concept(*, concept_id: int, name: str, normalized_name: str) -> Concept:
    return Concept(
        id=concept_id,
        course_id=7,
        name=name,
        normalized_name=normalized_name,
        description=f"{name} description.",
        extraction_confidence=0.8,
    )
