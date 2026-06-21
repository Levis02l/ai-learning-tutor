from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    filename: Mapped[str] = mapped_column(String)
    file_type: Mapped[str] = mapped_column(String)  # pdf, pptx, docx, audio
    storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    # pending, processing, done, error
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE")
    )
    content: Mapped[str] = mapped_column(Text)
    # Vector column uses Column() style — pgvector type not compatible with Mapped[]
    embedding = Column(Vector(1536), nullable=True)
    chunk_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
