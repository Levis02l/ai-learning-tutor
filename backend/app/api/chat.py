from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm.provider import LLMConfigurationError, LLMProviderError
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource
from app.services.embeddings import EmbeddingConfigurationError
from app.services.rag import answer_question

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat_with_documents(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    try:
        result = answer_question(
            db=db,
            query=request.query,
            user_id=request.user_id,
            top_k=request.top_k,
        )
    except (EmbeddingConfigurationError, LLMConfigurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )

    return ChatResponse(
        query=request.query,
        user_id=request.user_id,
        answer=result.answer,
        sources=[
            ChatSource(
                chunk_id=source.chunk_id,
                document_id=source.document_id,
                filename=source.filename,
                content=source.content,
                metadata=source.metadata,
                distance=source.distance,
                similarity=source.similarity,
            )
            for source in result.sources
        ],
    )
