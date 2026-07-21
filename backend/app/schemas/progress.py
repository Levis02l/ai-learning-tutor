from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ProgressConceptStatus = Literal[
    "unobserved",
    "needs_attention",
    "developing",
    "strong",
]


class ProgressMisconceptionResponse(BaseModel):
    id: int
    misconception_type: str
    description: str
    confidence: float
    quiz_attempt_id: int
    created_at: str | None = None


class ProgressPrerequisiteResponse(BaseModel):
    id: int
    name: str
    confidence: float


class ProgressSocraticActivityResponse(BaseModel):
    completed_sessions: int
    completion_attempts: int
    latest_session_id: int | None = None
    latest_completed_at: str | None = None
    latest_completion_quiz_item_id: int | None = None
    latest_completion_quiz_attempt_id: int | None = None
    latest_completion_correct: bool | None = None


class ProgressConceptResponse(BaseModel):
    concept_id: int
    concept_name: str
    state_status: Literal["observed", "unobserved"]
    status: ProgressConceptStatus
    mastery_score: float | None = None
    recent_accuracy: float | None = None
    attempt_count: int
    consecutive_errors: int
    last_attempted_at: datetime | None = None
    review_due: bool
    needs_attention: bool
    attention_reasons: list[str] = Field(default_factory=list)
    latest_misconception: ProgressMisconceptionResponse | None = None
    prerequisites: list[ProgressPrerequisiteResponse] = Field(default_factory=list)
    socratic_activity: ProgressSocraticActivityResponse


class ProgressSummaryResponse(BaseModel):
    total_concepts: int
    observed_concepts: int
    unobserved_concepts: int
    needs_attention_count: int
    review_due_count: int
    strong_count: int
    developing_count: int
    socratic_completed_count: int
    socratic_completion_attempt_count: int


class CourseProgressResponse(BaseModel):
    user_id: str
    course_id: int
    summary: ProgressSummaryResponse
    concepts: list[ProgressConceptResponse]
