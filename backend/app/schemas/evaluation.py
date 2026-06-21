from pydantic import BaseModel

from app.schemas.chat import ChatResponse
from app.schemas.quiz import QuizItemResponse


class AnswerEvaluationRequest(BaseModel):
    expected_answerable: bool
    response: ChatResponse


class AnswerEvaluationResponse(BaseModel):
    claim_count: int
    supported_claim_count: int
    unsupported_claim_count: int
    contradicted_claim_count: int
    citation_precision: float
    unsupported_claim_rate: float
    groundedness_score: float
    correct_refusal: bool


class QuizEvaluationRequest(BaseModel):
    items: list[QuizItemResponse]


class QuizEvaluationResponse(BaseModel):
    total_items: int
    fully_traceable_count: int
    partially_traceable_count: int
    weakly_traceable_count: int
    not_traceable_count: int
    traceable_item_rate: float
    label_counts: dict[str, int]
