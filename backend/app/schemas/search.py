from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    user_id: str = "demo-user"
    course_id: int | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    chunk_id: int
    document_id: int
    course_id: int | None = None
    filename: str
    content: str
    metadata: dict
    distance: float
    similarity: float


class SearchResponse(BaseModel):
    query: str
    user_id: str
    course_id: int | None = None
    results: list[SearchResult]
