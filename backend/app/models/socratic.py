from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SocraticSession(Base):
    __tablename__ = "socratic_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    course_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("courses.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    concept_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("concepts.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    source_policy_decision_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("policy_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    completion_quiz_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("quiz_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    completion_quiz_attempt_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("quiz_attempts.id", ondelete="SET NULL"),
        nullable=True,
    )
    query: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="active", index=True)
    current_stage: Mapped[str] = mapped_column(String, default="diagnostic")
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    max_turns: Mapped[int] = mapped_column(Integer, default=3)
    learner_state_snapshot: Mapped[dict] = mapped_column(JSON)
    concept_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    misconception_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_state_snapshot: Mapped[dict] = mapped_column(JSON)
    evidence_chunks_snapshot: Mapped[list[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    turns: Mapped[list["SocraticTurn"]] = relationship(
        "SocraticTurn",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SocraticTurn.turn_number",
    )


class SocraticTurn(Base):
    __tablename__ = "socratic_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("socratic_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    turn_number: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String)
    tutor_message: Mapped[str] = mapped_column(Text)
    student_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment: Mapped[str | None] = mapped_column(String, nullable=True)
    assessment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session = relationship("SocraticSession", back_populates="turns")
