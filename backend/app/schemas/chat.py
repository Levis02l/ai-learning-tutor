from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.evidence_state import EvidenceStateResponse

AnswerStatus = Literal[
    "answered",
    "partially_answered",
    "refused_no_evidence",
    "refused_ambiguous_material",
    "needs_more_material",
]
SupportLevel = Literal[
    "fully_supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "not_enough_information",
]


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    user_id: str = "demo-user"
    course_id: int | None = None
    top_k: int = Field(default=5, ge=1, le=10)


class ChatSource(BaseModel):
    chunk_id: int
    document_id: int
    course_id: int | None = None
    filename: str
    content: str
    metadata: dict
    distance: float
    similarity: float


class ChatClaim(BaseModel):
    claim: str
    source_chunk_ids: list[int]
    support_level: SupportLevel
    evidence_quote: str


class ChatResponse(BaseModel):
    query: str
    user_id: str
    course_id: int | None = None
    mode: str
    answer_status: AnswerStatus
    answer: str
    claims: list[ChatClaim]
    overall_groundedness: float
    evidence_state: EvidenceStateResponse
    sources: list[ChatSource]


class ChatCompareResponse(BaseModel):
    query: str
    user_id: str
    course_id: int | None = None
    grounded: ChatResponse
    ungrounded: ChatResponse
