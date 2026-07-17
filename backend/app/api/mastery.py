from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.mastery import (
    MasteryItemResponse,
    MasteryResponse,
    MasterySummaryResponse,
)
from app.services.courses import CourseNotFoundError, validate_course_scope
from app.services.mastery import get_mastery_snapshot

router = APIRouter(prefix="/mastery", tags=["mastery"])


@router.get("", response_model=MasteryResponse)
def get_mastery(
    user_id: str = "demo-user",
    course_id: int | None = None,
    db: Session = Depends(get_db),
) -> MasteryResponse:
    try:
        validate_course_scope(db=db, user_id=user_id, course_id=course_id)
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    snapshot = get_mastery_snapshot(db=db, user_id=user_id, course_id=course_id)
    return MasteryResponse(
        user_id=snapshot.user_id,
        course_id=course_id,
        summary=MasterySummaryResponse(
            total_items=snapshot.summary.total_items,
            reviewed_items=snapshot.summary.reviewed_items,
            due_items=snapshot.summary.due_items,
            average_mastery=snapshot.summary.average_mastery,
        ),
        items=[
            MasteryItemResponse(
                item_id=item.item_id,
                question=item.question,
                difficulty=item.difficulty,
                mastery_probability=item.mastery_probability,
                review_count=item.review_count,
                latest_rating=item.latest_rating,
                latest_is_correct=item.latest_is_correct,
                due_at=item.due_at,
                is_due=item.is_due,
            )
            for item in snapshot.items
        ],
    )
