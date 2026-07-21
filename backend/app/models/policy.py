from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PolicyDecisionRecord(Base):
    __tablename__ = "policy_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    course_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("courses.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    query: Mapped[str] = mapped_column(Text)
    detected_intent: Mapped[str] = mapped_column(String)
    learner_state_snapshot: Mapped[dict] = mapped_column(JSON)
    learner_state_scope: Mapped[str] = mapped_column(
        String,
        default="course",
        server_default="course",
    )
    concept_state_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    misconception_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_state_snapshot: Mapped[dict] = mapped_column(JSON)
    selected_action: Mapped[str] = mapped_column(String)
    response_strategy: Mapped[str] = mapped_column(String)
    primary_reason: Mapped[str] = mapped_column(String)
    teaching_reason: Mapped[str] = mapped_column(Text)
    suggested_next_step: Mapped[str] = mapped_column(Text)
    policy_version: Mapped[str] = mapped_column(String, index=True)
    outcome: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
