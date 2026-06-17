from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Chunk, Document
from app.services.embeddings import embed_texts


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    document_id: int
    filename: str
    content: str
    metadata: dict
    distance: float
    similarity: float


def retrieve_relevant_chunks(
    db: Session,
    query: str,
    user_id: str = "demo-user",
    top_k: int = 5,
) -> list[RetrievedChunk]:
    query_embedding = embed_texts([query])[0]
    return retrieve_relevant_chunks_by_embedding(
        db=db,
        query_embedding=query_embedding,
        user_id=user_id,
        top_k=top_k,
    )


def retrieve_relevant_chunks_by_embedding(
    db: Session,
    query_embedding: list[float],
    user_id: str = "demo-user",
    top_k: int = 5,
) -> list[RetrievedChunk]:
    distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")

    rows = db.execute(
        select(Chunk, Document, distance)
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.user_id == user_id)
        .where(Chunk.embedding.is_not(None))
        .order_by(distance)
        .limit(top_k)
    ).all()

    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=document.id,
            filename=document.filename,
            content=chunk.content,
            metadata=chunk.chunk_metadata,
            distance=float(chunk_distance),
            similarity=1.0 - float(chunk_distance),
        )
        for chunk, document, chunk_distance in rows
    ]
