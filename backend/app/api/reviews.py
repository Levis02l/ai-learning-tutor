from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.quiz import _to_response as quiz_to_response
from app.db import get_db
from app.models.review import ReviewRecord
from app.schemas.review import (
    DueReviewItemResponse,
    ReviewRecordResponse,
    ReviewSubmitRequest,
)
from app.services.review import ReviewError, get_due_review_items, submit_review

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("", response_model=ReviewRecordResponse)
def create_review(
    request: ReviewSubmitRequest,
    db: Session = Depends(get_db),
) -> ReviewRecordResponse:
    try:
        review = submit_review(
            db=db,
            user_id=request.user_id,
            item_id=request.item_id,
            rating=request.rating,
            is_correct=request.is_correct,
        )
    except ReviewError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return _review_to_response(review)


@router.get("/due", response_model=list[DueReviewItemResponse])
def get_due_reviews(
    user_id: str = "demo-user",
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[DueReviewItemResponse]:
    rows = get_due_review_items(db=db, user_id=user_id, limit=limit)
    return [
        DueReviewItemResponse(
            item=quiz_to_response(item),
            latest_review=_review_to_response(review) if review else None,
        )
        for item, review in rows
    ]


def _review_to_response(review: ReviewRecord) -> ReviewRecordResponse:
    return ReviewRecordResponse(
        id=review.id,
        user_id=review.user_id,
        item_id=review.item_id,
        rating=review.rating,
        is_correct=review.is_correct,
        reviewed_at=review.reviewed_at,
        stability=review.stability,
        difficulty=review.difficulty,
        due_at=review.due_at,
    )
