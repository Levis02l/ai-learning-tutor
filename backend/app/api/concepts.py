from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm.provider import LLMConfigurationError, LLMProviderError
from app.schemas.concept import (
    ConceptDetailResponse,
    ConceptExtractRequest,
    ConceptExtractResponse,
    ConceptPrerequisiteResponse,
    ConceptSourceResponse,
    ConceptSummaryResponse,
)
from app.services.concepts import (
    ConceptDetail,
    ConceptExtractionError,
    ConceptExtractionStats,
    ConceptNotFoundError,
    ConceptSummary,
    extract_course_concepts,
    get_concept_detail,
    list_course_concepts,
)
from app.services.courses import CourseNotFoundError, validate_course_scope

router = APIRouter(tags=["concepts"])


@router.post(
    "/courses/{course_id}/concepts/extract",
    response_model=ConceptExtractResponse,
)
def extract_concepts(
    course_id: int,
    request: ConceptExtractRequest,
    db: Session = Depends(get_db),
) -> ConceptExtractResponse:
    try:
        validate_course_scope(db=db, user_id=request.user_id, course_id=course_id)
        stats = extract_course_concepts(
            db=db,
            user_id=request.user_id,
            course_id=course_id,
            max_chunks=request.max_chunks,
            max_concepts=request.max_concepts,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConceptExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )

    return _extract_response(stats)


@router.get(
    "/courses/{course_id}/concepts",
    response_model=list[ConceptSummaryResponse],
)
def get_course_concepts(
    course_id: int,
    user_id: str = "demo-user",
    db: Session = Depends(get_db),
) -> list[ConceptSummaryResponse]:
    try:
        validate_course_scope(db=db, user_id=user_id, course_id=course_id)
        concepts = list_course_concepts(db=db, user_id=user_id, course_id=course_id)
    except (CourseNotFoundError, ConceptNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return [_summary_response(summary) for summary in concepts]


@router.get("/concepts/{concept_id}", response_model=ConceptDetailResponse)
def get_concept(
    concept_id: int,
    user_id: str = "demo-user",
    db: Session = Depends(get_db),
) -> ConceptDetailResponse:
    try:
        detail = get_concept_detail(db=db, user_id=user_id, concept_id=concept_id)
    except ConceptNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return _detail_response(detail)


def _extract_response(stats: ConceptExtractionStats) -> ConceptExtractResponse:
    return ConceptExtractResponse(
        course_id=stats.course_id,
        concepts_created=stats.concepts_created,
        concepts_reused=stats.concepts_reused,
        source_links_created=stats.source_links_created,
        prerequisites_created=stats.prerequisites_created,
        candidates_skipped=stats.candidates_skipped,
    )


def _summary_response(summary: ConceptSummary) -> ConceptSummaryResponse:
    concept = summary.concept
    return ConceptSummaryResponse(
        id=concept.id,
        course_id=concept.course_id,
        name=concept.name,
        description=concept.description,
        extraction_confidence=concept.extraction_confidence,
        source_count=summary.source_count,
        prerequisite_count=summary.prerequisite_count,
        created_at=concept.created_at,
        updated_at=concept.updated_at,
    )


def _detail_response(detail: ConceptDetail) -> ConceptDetailResponse:
    concept = detail.concept
    return ConceptDetailResponse(
        id=concept.id,
        course_id=concept.course_id,
        name=concept.name,
        description=concept.description,
        extraction_confidence=concept.extraction_confidence,
        sources=[
            ConceptSourceResponse(
                chunk_id=source.chunk_id,
                document_id=source.document_id,
                filename=source.filename,
                content=source.content,
                metadata=source.metadata,
                relevance_score=source.relevance_score,
            )
            for source in detail.sources
        ],
        prerequisites=[
            ConceptPrerequisiteResponse(
                id=prerequisite.concept.id,
                name=prerequisite.concept.name,
                description=prerequisite.concept.description,
                confidence=prerequisite.confidence,
            )
            for prerequisite in detail.prerequisites
        ],
        created_at=concept.created_at,
        updated_at=concept.updated_at,
    )
