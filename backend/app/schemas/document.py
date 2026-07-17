from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    course_id: int | None = None
    filename: str
    file_type: str
    status: str
    created_at: datetime
    chunk_count: int = 0


class ChunkPreview(BaseModel):
    id: int
    document_id: int
    content: str
    metadata: dict


class DocumentUploadResponse(DocumentResponse):
    pass
