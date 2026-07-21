from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.chat import ChatClaim, ChatSource
from app.schemas.quiz import QuizItemResponse
from app.schemas.review import DueReviewItemResponse

DetectedIntent = Literal["explain", "hint", "practice", "review", "unknown"]
TeachingAction = Literal["explain", "hint", "quiz", "review", "refuse"]
LearnerStateScope = Literal["course", "concept"]
ResponseStrategy = Literal[
    "scaffolded",
    "guided",
    "concise",
    "challenging",
    "refusal",
    "review_drill",
    "contrastive",
    "definition_clarification",
    "prerequisite_scaffolded",
    "reasoning_guidance",
    "source_correction",
]
PolicyEvidenceStrength = Literal[
    "high",
    "medium",
    "low",
    "insufficient",
    "not_required",
]
TutorRetrievalScope = Literal[
    "course",
    "concept",
    "concept_with_course_fallback",
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
    retrieval_scope: TutorRetrievalScope = "course"
    source_chunk_ids: list[int] = Field(default_factory=list)


class TutorConceptLearnerStateSnapshot(BaseModel):
    concept_id: int
    concept_name: str
    state_status: Literal["observed", "unobserved"]
    mastery_score: float | None = None
    recent_accuracy: float | None = None
    attempt_count: int
    consecutive_errors: int
    last_attempted_at: str | None = None
    review_due: bool
    needs_attention: bool


class TutorMisconceptionSnapshot(BaseModel):
    id: int
    misconception_type: str
    description: str
    confidence: float
    quiz_attempt_id: int
    concept_id: int
    created_at: str | None = None


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
    learner_state_scope: LearnerStateScope = "course"
    learner_state_snapshot: TutorLearnerStateSnapshot
    concept_state_snapshot: TutorConceptLearnerStateSnapshot | None = None
    misconception_snapshot: TutorMisconceptionSnapshot | None = None
    evidence_state_snapshot: TutorEvidenceStateSnapshot


TutorAnswerStatus = Literal[
    "answered",
    "partially_answered",
    "refused_no_evidence",
    "refused_ambiguous_material",
    "needs_more_material",
    "review_ready",
    "quiz_ready",
]


class TutorResponseRequest(TutorDecisionRequest):
    pass


class TutorResponseResponse(BaseModel):
    decision: TutorDecisionResponse
    answer_status: TutorAnswerStatus
    answer: str
    claims: list[ChatClaim] = Field(default_factory=list)
    sources: list[ChatSource] = Field(default_factory=list)
    quiz_items: list[QuizItemResponse] = Field(default_factory=list)
    review_items: list[DueReviewItemResponse] = Field(default_factory=list)
    suggested_next_step: str


TutorOutcomeType = Literal["quiz_attempt", "review"]


class TutorOutcomeRequest(BaseModel):
    outcome_type: TutorOutcomeType
    quiz_attempt_id: int | None = Field(default=None, ge=1)
    review_record_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_reference(self) -> "TutorOutcomeRequest":
        if self.outcome_type == "quiz_attempt":
            if self.quiz_attempt_id is None or self.review_record_id is not None:
                raise ValueError("quiz_attempt outcomes require only quiz_attempt_id")
        if self.outcome_type == "review":
            if self.review_record_id is None or self.quiz_attempt_id is not None:
                raise ValueError("review outcomes require only review_record_id")
        return self


class TutorOutcomeResponse(BaseModel):
    decision_id: int
    outcome: dict[str, Any]
