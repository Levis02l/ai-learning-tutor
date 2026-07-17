from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm.provider import LLMConfigurationError, LLMProviderError
from app.models.quiz import QuizItem
from app.schemas.quiz import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizItemResponse,
)
from app.services.courses import CourseNotFoundError, validate_course_scope
from app.services.embeddings import EmbeddingConfigurationError
from app.services.quiz import QuizGenerationError, generate_quiz_items, list_quiz_items

router = APIRouter(prefix="/quiz", tags=["quiz"])


@router.post("/generate", response_model=QuizGenerateResponse)
def generate_quiz(
    request: QuizGenerateRequest,
    db: Session = Depends(get_db),
) -> QuizGenerateResponse:
    try:
        validate_course_scope(
            db=db, user_id=request.user_id, course_id=request.course_id
        )
        items = generate_quiz_items(
            db=db,
            topic=request.topic,
            user_id=request.user_id,
            course_id=request.course_id,
            count=request.count,
            difficulty=request.difficulty,
            top_k=request.top_k,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except QuizGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )
    except (EmbeddingConfigurationError, LLMConfigurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )

    return QuizGenerateResponse(
        topic=request.topic,
        user_id=request.user_id,
        course_id=request.course_id,
        items=[_to_response(item) for item in items],
    )


@router.get("/items", response_model=list[QuizItemResponse])
def get_quiz_items(
    user_id: str = "demo-user",
    course_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[QuizItemResponse]:
    try:
        validate_course_scope(db=db, user_id=user_id, course_id=course_id)
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    items = list_quiz_items(db, user_id=user_id, course_id=course_id, limit=limit)
    return [_to_response(item) for item in items]


def _to_response(item: QuizItem) -> QuizItemResponse:
    return QuizItemResponse(
        id=item.id,
        user_id=item.user_id,
        course_id=item.course_id,
        question=item.question,
        answer=item.answer,
        difficulty=item.difficulty,
        source_chunk_ids=item.source_chunk_ids,
        evidence_quote=item.evidence_quote,
        question_type=item.question_type,
        traceability_label=item.traceability_label,
        created_at=item.created_at,
    )
