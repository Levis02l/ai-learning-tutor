from typing import Literal

from pydantic import BaseModel, Field

DetectedIntent = Literal["explain", "hint", "practice", "review", "unknown"]
TeachingAction = Literal["explain", "hint", "quiz", "review", "refuse"]
ResponseStrategy = Literal[
    "scaffolded",
    "guided",
    "concise",
    "challenging",
    "refusal",
    "review_drill",
]
PolicyEvidenceStrength = Literal[
    "high",
    "medium",
    "low",
    "insufficient",
    "not_required",
]


class TutorDecisionRequest(BaseModel):
    query: str = Field(..., min_length=1)
    user_id: str = "demo-user"
    course_id: int | None = None
    top_k: int = Field(default=5, ge=1, le=10)


class TutorLearnerStateSnapshot(BaseModel):
    user_id: str
    course_id: int | None = None
    mastery_score: float
    recent_accuracy: float
    attempt_count: int
    consecutive_errors: int
    last_reviewed_at: str | None = None
    review_due: bool


class TutorEvidenceStateSnapshot(BaseModel):
    evidence_strength: PolicyEvidenceStrength
    source_coverage: float
    retrieved_chunk_count: int
    top_similarity: float
    requires_evidence: bool
    reason: str


class TutorDecisionResponse(BaseModel):
    decision_id: int
    user_id: str
    course_id: int | None = None
    query: str
    detected_intent: DetectedIntent
    selected_action: TeachingAction
    response_strategy: ResponseStrategy
    primary_reason: str
    teaching_reason: str
    suggested_next_step: str
    policy_version: str
    learner_state_snapshot: TutorLearnerStateSnapshot
    evidence_state_snapshot: TutorEvidenceStateSnapshot
