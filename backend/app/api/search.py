from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.courses import CourseNotFoundError, validate_course_scope
from app.services.embeddings import EmbeddingConfigurationError
from app.services.retrieval import retrieve_relevant_chunks

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    try:
        validate_course_scope(
            db=db, user_id=request.user_id, course_id=request.course_id
        )
        chunks = retrieve_relevant_chunks(
            db=db,
            query=request.query,
            user_id=request.user_id,
            course_id=request.course_id,
            top_k=request.top_k,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    return SearchResponse(
        query=request.query,
        user_id=request.user_id,
        course_id=request.course_id,
        results=[
            SearchResult(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                course_id=chunk.course_id,
                filename=chunk.filename,
                content=chunk.content,
                metadata=chunk.metadata,
                distance=chunk.distance,
                similarity=chunk.similarity,
            )
            for chunk in chunks
        ],
    )
