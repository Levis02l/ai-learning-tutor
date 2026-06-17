from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.embeddings import EmbeddingConfigurationError
from app.services.retrieval import retrieve_relevant_chunks

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    try:
        chunks = retrieve_relevant_chunks(
            db=db,
            query=request.query,
            user_id=request.user_id,
            top_k=request.top_k,
        )
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    return SearchResponse(
        query=request.query,
        user_id=request.user_id,
        results=[
            SearchResult(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                filename=chunk.filename,
                content=chunk.content,
                metadata=chunk.metadata,
                distance=chunk.distance,
                similarity=chunk.similarity,
            )
            for chunk in chunks
        ],
    )
