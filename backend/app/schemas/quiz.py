from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Difficulty = Literal["easy", "medium", "hard"]
QuestionType = Literal["definition", "conceptual", "application", "comparison"]
TraceabilityLabel = Literal[
    "fully_traceable",
    "partially_traceable",
    "weakly_traceable",
    "not_traceable",
]


class QuizGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    user_id: str = "demo-user"
    course_id: int | None = None
    count: int = Field(default=5, ge=1, le=10)
    difficulty: Difficulty = "medium"
    top_k: int = Field(default=5, ge=1, le=10)


class QuizItemResponse(BaseModel):
    id: int
    user_id: str
    course_id: int | None = None
    question: str
    answer: str
    difficulty: str
    source_chunk_ids: list[int]
    evidence_quote: str
    question_type: str
    traceability_label: str
    created_at: datetime


class QuizGenerateResponse(BaseModel):
    topic: str
    user_id: str
    course_id: int | None = None
    items: list[QuizItemResponse]
