from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class QuizItem(Base):
    __tablename__ = "quiz_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    course_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("courses.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    concept_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("concepts.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String)
    source_chunk_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    evidence_quote: Mapped[str] = mapped_column(Text, default="")
    options: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    correct_option_id: Mapped[str | None] = mapped_column(String, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, default="")
    question_type: Mapped[str] = mapped_column(String, default="conceptual")
    traceability_label: Mapped[str] = mapped_column(String, default="not_traceable")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        index=True,
        nullable=True,
    )

    course = relationship("Course", back_populates="quiz_items")
    concept = relationship("Concept")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    course_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("courses.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    quiz_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("quiz_items.id", ondelete="CASCADE"),
        index=True,
    )
    selected_option_id: Mapped[str] = mapped_column(String)
    selected_option_text: Mapped[str] = mapped_column(Text)
    correct_option_id: Mapped[str] = mapped_column(String)
    correct_option_text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    quiz_item = relationship("QuizItem")
