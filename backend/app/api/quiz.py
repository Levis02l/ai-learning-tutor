from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm.provider import LLMConfigurationError, LLMProviderError
from app.models.quiz import QuizAttempt, QuizItem
from app.schemas.quiz import (
    QuizAttemptRequest,
    QuizAttemptResponse,
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizItemRemovalResponse,
    QuizItemResponse,
    QuizOptionResponse,
)
from app.services.courses import CourseNotFoundError, validate_course_scope
from app.services.embeddings import EmbeddingConfigurationError
from app.services.quiz import (
    QuizAttemptError,
    QuizGenerationError,
    QuizItemRemovalError,
    generate_quiz_items,
    list_quiz_items,
    remove_quiz_item,
    submit_quiz_attempt,
)

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
        topic=request.topic.strip() or "current course materials",
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


@router.post("/attempts", response_model=QuizAttemptResponse)
def create_quiz_attempt(
    request: QuizAttemptRequest,
    db: Session = Depends(get_db),
) -> QuizAttemptResponse:
    try:
        validate_course_scope(
            db=db, user_id=request.user_id, course_id=request.course_id
        )
        attempt = submit_quiz_attempt(
            db=db,
            user_id=request.user_id,
            course_id=request.course_id,
            quiz_item_id=request.quiz_item_id,
            selected_option_id=request.selected_option_id,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except QuizAttemptError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )

    item = attempt.quiz_item
    return _attempt_to_response(attempt=attempt, item=item)


@router.delete("/items/{item_id}", response_model=QuizItemRemovalResponse)
def delete_quiz_item(
    item_id: int,
    user_id: str = "demo-user",
    course_id: int | None = None,
    db: Session = Depends(get_db),
) -> QuizItemRemovalResponse:
    try:
        validate_course_scope(db=db, user_id=user_id, course_id=course_id)
        result = remove_quiz_item(
            db=db,
            user_id=user_id,
            item_id=item_id,
            course_id=course_id,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except QuizItemRemovalError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return QuizItemRemovalResponse(
        item_id=result.item_id,
        action=result.action,
        archived_at=result.archived_at,
    )


def _to_response(item: QuizItem) -> QuizItemResponse:
    return QuizItemResponse(
        id=item.id,
        user_id=item.user_id,
        course_id=item.course_id,
        concept_id=item.concept_id,
        question=item.question,
        answer=item.answer,
        difficulty=item.difficulty,
        source_chunk_ids=item.source_chunk_ids,
        evidence_quote=item.evidence_quote,
        options=[QuizOptionResponse(**option) for option in item.options or []],
        explanation=item.explanation or item.answer,
        question_type=item.question_type,
        traceability_label=item.traceability_label,
        created_at=item.created_at,
        archived_at=item.archived_at,
    )


def _attempt_to_response(
    *,
    attempt: QuizAttempt,
    item: QuizItem,
) -> QuizAttemptResponse:
    return QuizAttemptResponse(
        id=attempt.id,
        user_id=attempt.user_id,
        course_id=attempt.course_id,
        quiz_item_id=attempt.quiz_item_id,
        selected_option_id=attempt.selected_option_id,
        selected_option_text=attempt.selected_option_text,
        correct_option_id=attempt.correct_option_id,
        correct_option_text=attempt.correct_option_text,
        is_correct=attempt.is_correct,
        explanation=item.explanation or item.answer,
        source_chunk_ids=item.source_chunk_ids,
        attempted_at=attempt.attempted_at,
    )
