from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    user_id: str = "demo-user"
    top_k: int = Field(default=5, ge=1, le=10)


class ChatSource(BaseModel):
    chunk_id: int
    document_id: int
    filename: str
    content: str
    metadata: dict
    distance: float
    similarity: float


class ChatResponse(BaseModel):
    query: str
    user_id: str
    answer: str
    sources: list[ChatSource]
