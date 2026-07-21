from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ConceptLearnerStateStatus = Literal["observed", "unobserved"]


class ConceptExtractRequest(BaseModel):
    user_id: str = "demo-user"
    max_chunks: int = Field(default=24, ge=1, le=80)
    max_concepts: int = Field(default=20, ge=1, le=50)


class ConceptExtractResponse(BaseModel):
    course_id: int
    concepts_created: int
    concepts_reused: int
    source_links_created: int
    prerequisites_created: int
    candidates_skipped: int


class ConceptSummaryResponse(BaseModel):
    id: int
    course_id: int
    name: str
    description: str
    extraction_confidence: float
    source_count: int
    prerequisite_count: int
    created_at: datetime
    updated_at: datetime


class ConceptSourceResponse(BaseModel):
    chunk_id: int
    document_id: int
    filename: str
    content: str
    metadata: dict
    relevance_score: float


class ConceptPrerequisiteResponse(BaseModel):
    id: int
    name: str
    description: str
    confidence: float


class ConceptDetailResponse(BaseModel):
    id: int
    course_id: int
    name: str
    description: str
    extraction_confidence: float
    sources: list[ConceptSourceResponse] = Field(default_factory=list)
    prerequisites: list[ConceptPrerequisiteResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ConceptLearnerStateResponse(BaseModel):
    concept_id: int
    concept_name: str
    state_status: ConceptLearnerStateStatus
    mastery_score: float | None = None
    recent_accuracy: float | None = None
    attempt_count: int
    consecutive_errors: int
    last_attempted_at: datetime | None = None
    review_due: bool
    needs_attention: bool
