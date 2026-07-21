from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MisconceptionType = Literal[
    "concept_confusion",
    "incorrect_definition",
    "missing_prerequisite",
    "incomplete_reasoning",
    "source_misinterpretation",
    "unknown",
]


class MisconceptionResponse(BaseModel):
    id: int
    user_id: str
    course_id: int | None = None
    concept_id: int
    concept_name: str | None = None
    quiz_attempt_id: int
    misconception_type: MisconceptionType
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_snapshot: dict
    created_at: datetime
