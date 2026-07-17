from datetime import datetime

from pydantic import BaseModel


class LearnerStateResponse(BaseModel):
    user_id: str
    course_id: int | None = None
    mastery_score: float
    recent_accuracy: float
    attempt_count: int
    consecutive_errors: int
    last_reviewed_at: datetime | None = None
    review_due: bool

