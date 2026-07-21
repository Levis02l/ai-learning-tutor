from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Difficulty = Literal["easy", "medium", "hard"]
QuizOrigin = Literal[
    "manual_practice",
    "policy_quiz",
    "comprehension_check",
    "socratic_completion_check",
]
QuestionType = Literal["definition", "conceptual", "application", "comparison"]
TraceabilityLabel = Literal[
    "fully_traceable",
    "partially_traceable",
    "weakly_traceable",
    "not_traceable",
]


class QuizGenerateRequest(BaseModel):
    topic: str = Field(default="", max_length=200)
    user_id: str = "demo-user"
    course_id: int | None = None
    count: int = Field(default=5, ge=1, le=10)
    difficulty: Difficulty = "medium"
    top_k: int = Field(default=5, ge=1, le=10)


class QuizOptionResponse(BaseModel):
    id: str
    text: str


class QuizItemResponse(BaseModel):
    id: int
    user_id: str
    course_id: int | None = None
    concept_id: int | None = None
    question: str
    answer: str
    difficulty: str
    origin: QuizOrigin = "manual_practice"
    source_chunk_ids: list[int]
    evidence_quote: str
    options: list[QuizOptionResponse] = Field(default_factory=list)
    explanation: str = ""
    question_type: str
    traceability_label: str
    created_at: datetime
    archived_at: datetime | None = None


class QuizGenerateResponse(BaseModel):
    topic: str
    user_id: str
    course_id: int | None = None
    items: list[QuizItemResponse]


class QuizAttemptRequest(BaseModel):
    quiz_item_id: int
    selected_option_id: str = Field(..., min_length=1, max_length=8)
    user_id: str = "demo-user"
    course_id: int | None = None


class QuizAttemptResponse(BaseModel):
    id: int
    user_id: str
    course_id: int | None = None
    quiz_item_id: int
    selected_option_id: str
    selected_option_text: str
    correct_option_id: str
    correct_option_text: str
    is_correct: bool
    explanation: str
    source_chunk_ids: list[int]
    attempted_at: datetime


class QuizItemRemovalResponse(BaseModel):
    item_id: int
    action: Literal["deleted", "archived"]
    archived_at: datetime | None = None
