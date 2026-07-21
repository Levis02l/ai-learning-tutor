from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SocraticStatus = Literal["active", "completed", "abandoned"]
SocraticStage = Literal[
    "diagnostic",
    "hint_1",
    "hint_2",
    "final_explanation",
    "grounded_summary",
]
SocraticAssessment = Literal[
    "correct",
    "partially_correct",
    "incorrect",
    "off_topic",
]


class SocraticStartRequest(BaseModel):
    query: str = Field(..., min_length=1)
    user_id: str = "demo-user"
    course_id: int | None = None
    source_policy_decision_id: int | None = Field(default=None, ge=1)
    top_k: int = Field(default=5, ge=1, le=10)
    max_turns: int = Field(default=3, ge=1, le=3)


class SocraticRespondRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=2000)
    user_id: str = "demo-user"
    course_id: int | None = None


class SocraticTurnResponse(BaseModel):
    id: int
    session_id: int
    turn_number: int
    stage: SocraticStage
    tutor_message: str
    student_response: str | None = None
    assessment: SocraticAssessment | None = None
    assessment_reason: str | None = None
    created_at: datetime


class SocraticSessionResponse(BaseModel):
    id: int
    user_id: str
    course_id: int | None = None
    concept_id: int | None = None
    source_policy_decision_id: int | None = None
    query: str
    status: SocraticStatus
    current_stage: SocraticStage
    turn_count: int
    max_turns: int
    message: str
    assessment: SocraticAssessment | None = None
    assessment_reason: str | None = None
    learner_state_snapshot: dict
    concept_snapshot: dict | None = None
    misconception_snapshot: dict | None = None
    evidence_state_snapshot: dict
    evidence_chunks_snapshot: list[dict]
    turns: list[SocraticTurnResponse]
    created_at: datetime
    completed_at: datetime | None = None
