from datetime import datetime

from pydantic import BaseModel


class MasterySummaryResponse(BaseModel):
    total_items: int
    reviewed_items: int
    due_items: int
    average_mastery: float


class MasteryItemResponse(BaseModel):
    item_id: int
    question: str
    difficulty: str
    mastery_probability: float
    review_count: int
    latest_rating: int | None = None
    latest_is_correct: bool | None = None
    due_at: datetime | None = None
    is_due: bool


class MasteryResponse(BaseModel):
    user_id: str
    course_id: int | None = None
    summary: MasterySummaryResponse
    items: list[MasteryItemResponse]
