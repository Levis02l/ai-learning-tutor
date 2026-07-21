from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
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


class Concept(Base):
    __tablename__ = "concepts"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "normalized_name",
            name="uq_concepts_course_normalized_name",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("courses.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String)
    normalized_name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    extraction_confidence: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    course = relationship("Course")
    source_chunks: Mapped[list["ConceptSourceChunk"]] = relationship(
        "ConceptSourceChunk",
        back_populates="concept",
        cascade="all, delete-orphan",
    )
    prerequisite_links: Mapped[list["ConceptPrerequisite"]] = relationship(
        "ConceptPrerequisite",
        foreign_keys="ConceptPrerequisite.concept_id",
        back_populates="concept",
        cascade="all, delete-orphan",
    )


class ConceptSourceChunk(Base):
    __tablename__ = "concept_source_chunks"

    concept_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("concepts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    chunk_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chunks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relevance_score: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    concept = relationship("Concept", back_populates="source_chunks")
    chunk = relationship("Chunk")


class ConceptPrerequisite(Base):
    __tablename__ = "concept_prerequisites"
    __table_args__ = (
        CheckConstraint(
            "concept_id <> prerequisite_concept_id",
            name="ck_concept_prerequisites_not_self",
        ),
    )

    concept_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("concepts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    prerequisite_concept_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("concepts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    concept = relationship(
        "Concept",
        foreign_keys=[concept_id],
        back_populates="prerequisite_links",
    )
    prerequisite = relationship("Concept", foreign_keys=[prerequisite_concept_id])
