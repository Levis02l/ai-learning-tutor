from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.quiz import QuizItemResponse


class ReviewSubmitRequest(BaseModel):
    item_id: int
    user_id: str = "demo-user"
    course_id: int | None = None
    rating: int = Field(..., ge=1, le=4)
    is_correct: bool


class ReviewRecordResponse(BaseModel):
    id: int
    user_id: str
    item_id: int
    course_id: int | None = None
    rating: int
    is_correct: bool
    reviewed_at: datetime
    stability: float
    difficulty: float
    due_at: datetime


class DueReviewItemResponse(BaseModel):
    item: QuizItemResponse
    latest_review: ReviewRecordResponse | None = None
