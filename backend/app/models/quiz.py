from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class QuizItem(Base):
    __tablename__ = "quiz_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String)
    source_chunk_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    evidence_quote: Mapped[str] = mapped_column(Text, default="")
    question_type: Mapped[str] = mapped_column(String, default="conceptual")
    traceability_label: Mapped[str] = mapped_column(String, default="not_traceable")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
