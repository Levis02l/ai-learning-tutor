from pydantic import BaseModel

from app.schemas.chat import ChatResponse
from app.schemas.quiz import QuizItemResponse


class AnswerEvaluationRequest(BaseModel):
    user_id: str = "demo-user"
    course_id: int | None = None
    expected_answerable: bool
    response: ChatResponse


class AnswerEvaluationResponse(BaseModel):
    user_id: str = "demo-user"
    course_id: int | None = None
    claim_count: int
    supported_claim_count: int
    unsupported_claim_count: int
    contradicted_claim_count: int
    cited_claim_count: int
    citation_applicable: bool
    citation_precision: float | None
    citation_coverage: float | None
    unsupported_claim_rate: float
    groundedness_score: float
    refused_by_status: bool
    semantic_refusal: bool
    effective_refusal: bool
    correct_refusal: bool


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
