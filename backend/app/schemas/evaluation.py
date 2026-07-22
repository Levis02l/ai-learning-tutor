from typing import Literal

from pydantic import BaseModel, model_validator

from app.schemas.chat import ChatResponse
from app.schemas.quiz import QuizItemResponse

Answerability = Literal["answerable", "partially_answerable", "unanswerable"]


class AnswerEvaluationRequest(BaseModel):
    user_id: str = "demo-user"
    course_id: int | None = None
    answerability: Answerability | None = None
    expected_answerable: bool | None = None
    response: ChatResponse

    @model_validator(mode="after")
    def validate_answerability_present(self) -> "AnswerEvaluationRequest":
        if self.answerability is None and self.expected_answerable is None:
            raise ValueError("answerability or expected_answerable is required")
        return self


class AnswerEvaluationResponse(BaseModel):
    user_id: str = "demo-user"
    course_id: int | None = None
    answerability: Answerability
    claim_count: int
    supported_claim_count: int
    unsupported_claim_count: int
    contradicted_claim_count: int
    cited_claim_count: int
    citation_applicable: bool
    automatic_cited_claim_support_rate: float | None
    citation_coverage: float | None
    generated_unsupported_claim_rate: float
    generation_groundedness_score: float
    refused_by_status: bool
    semantic_refusal: bool
    effective_refusal: bool
    automatic_refusal_correctness: bool | None
    # Deprecated compatibility fields for older UI/tests.
    citation_precision: float | None
    unsupported_claim_rate: float
    groundedness_score: float
    correct_refusal: bool | None


class QuizEvaluationRequest(BaseModel):
    user_id: str = "demo-user"
    course_id: int | None = None
    items: list[QuizItemResponse]


class QuizEvaluationResponse(BaseModel):
    user_id: str = "demo-user"
    course_id: int | None = None
    total_items: int
    fully_traceable_count: int
    partially_traceable_count: int
    weakly_traceable_count: int
    not_traceable_count: int
    traceable_item_rate: float
    label_counts: dict[str, int]
