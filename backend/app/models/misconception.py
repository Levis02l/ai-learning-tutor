from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Misconception(Base):
    __tablename__ = "misconceptions"
    __table_args__ = (
        UniqueConstraint(
            "quiz_attempt_id",
            name="uq_misconceptions_quiz_attempt_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    course_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("courses.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    concept_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("concepts.id", ondelete="CASCADE"),
        index=True,
    )
    quiz_attempt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"),
        index=True,
    )
    misconception_type: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    concept = relationship("Concept")
    quiz_attempt = relationship("QuizAttempt")
