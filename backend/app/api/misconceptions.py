from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.misconception import Misconception
from app.schemas.misconception import MisconceptionResponse, MisconceptionType
from app.services.courses import CourseNotFoundError, validate_course_scope
from app.services.misconceptions import MisconceptionSummary, list_misconceptions

router = APIRouter(tags=["misconceptions"])


@router.get(
    "/courses/{course_id}/misconceptions",
    response_model=list[MisconceptionResponse],
)
def get_course_misconceptions(
    course_id: int,
    user_id: str = "demo-user",
    concept_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[MisconceptionResponse]:
    try:
        validate_course_scope(db=db, user_id=user_id, course_id=course_id)
        summaries = list_misconceptions(
            db=db,
            user_id=user_id,
            course_id=course_id,
            concept_id=concept_id,
            limit=limit,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return [_to_response(summary) for summary in summaries]


def _to_response(summary: MisconceptionSummary) -> MisconceptionResponse:
    misconception = summary.misconception
    return MisconceptionResponse(
        id=misconception.id,
        user_id=misconception.user_id,
        course_id=misconception.course_id,
        concept_id=misconception.concept_id,
        concept_name=summary.concept_name,
        quiz_attempt_id=misconception.quiz_attempt_id,
        misconception_type=_misconception_type(misconception),
        description=misconception.description,
        confidence=misconception.confidence,
        evidence_snapshot=misconception.evidence_snapshot,
        created_at=misconception.created_at,
    )


def _misconception_type(misconception: Misconception) -> MisconceptionType:
    value = misconception.misconception_type
    if value == "concept_confusion":
        return "concept_confusion"
    if value == "incorrect_definition":
        return "incorrect_definition"
    if value == "missing_prerequisite":
        return "missing_prerequisite"
    if value == "incomplete_reasoning":
        return "incomplete_reasoning"
    if value == "source_misinterpretation":
        return "source_misinterpretation"
    return "unknown"
