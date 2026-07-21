from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.models.concept import Concept
from app.services.concepts import (
    ConceptDetail,
    ConceptExtractionStats,
    ConceptPrerequisiteDetail,
    ConceptSource,
    ConceptSummary,
)


def test_extract_concepts_returns_stats(monkeypatch) -> None:
    captured: dict[str, int | str] = {}

    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["validated_course_id"] = kwargs["course_id"]
        captured["validated_user_id"] = kwargs["user_id"]

    def fake_extract(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["extracted_course_id"] = kwargs["course_id"]
        captured["max_chunks"] = kwargs["max_chunks"]
        captured["max_concepts"] = kwargs["max_concepts"]
        return ConceptExtractionStats(
            course_id=4,
            concepts_created=3,
            concepts_reused=1,
            source_links_created=8,
            prerequisites_created=2,
            candidates_skipped=1,
        )

    monkeypatch.setattr("app.api.concepts.validate_course_scope", fake_validate)
    monkeypatch.setattr("app.api.concepts.extract_course_concepts", fake_extract)
    client = TestClient(app)

    response = client.post(
        "/courses/4/concepts/extract",
        json={"user_id": "demo-user", "max_chunks": 12, "max_concepts": 8},
    )

    assert response.status_code == 200
    assert captured == {
        "validated_course_id": 4,
        "validated_user_id": "demo-user",
        "extracted_course_id": 4,
        "max_chunks": 12,
        "max_concepts": 8,
    }
    body = response.json()
    assert body["concepts_created"] == 3
    assert body["source_links_created"] == 8
    assert body["candidates_skipped"] == 1


def test_list_course_concepts_returns_summaries(monkeypatch) -> None:
    now = datetime(2026, 7, 21, 12, 0, 0)

    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    def fake_list(*args, **kwargs):  # type: ignore[no-untyped-def]
        return [
            ConceptSummary(
                concept=_concept(
                    concept_id=1,
                    course_id=kwargs["course_id"],
                    name="Artificial Intelligence",
                    created_at=now,
                ),
                source_count=2,
                prerequisite_count=0,
            )
        ]

    monkeypatch.setattr("app.api.concepts.validate_course_scope", fake_validate)
    monkeypatch.setattr("app.api.concepts.list_course_concepts", fake_list)
    client = TestClient(app)

    response = client.get("/courses/4/concepts?user_id=demo-user")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["name"] == "Artificial Intelligence"
    assert body[0]["source_count"] == 2
    assert body[0]["prerequisite_count"] == 0


def test_get_concept_detail_returns_sources_and_prerequisites(monkeypatch) -> None:
    now = datetime(2026, 7, 21, 12, 0, 0)

    def fake_detail(*args, **kwargs):  # type: ignore[no-untyped-def]
        return ConceptDetail(
            concept=_concept(
                concept_id=2,
                course_id=4,
                name="Machine Learning",
                created_at=now,
            ),
            sources=[
                ConceptSource(
                    chunk_id=11,
                    document_id=3,
                    filename="lecture.pdf",
                    content="Machine learning learns from data.",
                    metadata={"page": 2},
                    relevance_score=0.9,
                )
            ],
            prerequisites=[
                ConceptPrerequisiteDetail(
                    concept=_concept(
                        concept_id=1,
                        course_id=4,
                        name="Artificial Intelligence",
                        created_at=now,
                    ),
                    confidence=0.8,
                )
            ],
        )

    monkeypatch.setattr("app.api.concepts.get_concept_detail", fake_detail)
    client = TestClient(app)

    response = client.get("/concepts/2?user_id=demo-user")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Machine Learning"
    assert body["sources"][0]["chunk_id"] == 11
    assert body["prerequisites"][0]["name"] == "Artificial Intelligence"


def _concept(
    *,
    concept_id: int,
    course_id: int,
    name: str,
    created_at: datetime,
) -> Concept:
    return Concept(
        id=concept_id,
        course_id=course_id,
        name=name,
        normalized_name=name.lower(),
        description=f"{name} description.",
        extraction_confidence=0.8,
        created_at=created_at,
        updated_at=created_at,
    )
