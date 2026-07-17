from datetime import datetime

from pydantic import BaseModel, Field


class CourseCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    user_id: str = "demo-user"


class CourseResponse(BaseModel):
    id: int
    user_id: str
    name: str
    created_at: datetime
