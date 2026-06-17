from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.quiz import QuizItem


class ReviewRecord(Base):
    __tablename__ = "review_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("quiz_items.id", ondelete="CASCADE"), index=True
    )
    rating: Mapped[int] = mapped_column(Integer)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    stability: Mapped[float] = mapped_column(Float)
    difficulty: Mapped[float] = mapped_column(Float)
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    item: Mapped[QuizItem] = relationship("QuizItem")
