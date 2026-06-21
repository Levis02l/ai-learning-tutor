from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm.provider import LLMConfigurationError, LLMProviderError
from app.schemas.chat import (
    ChatClaim,
    ChatCompareResponse,
    ChatRequest,
    ChatResponse,
    ChatSource,
)
from app.services.embeddings import EmbeddingConfigurationError
from app.services.rag import RagAnswer, answer_question, compare_answers

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
        **_to_chat_payload(result),
    )


@router.post("/compare", response_model=ChatCompareResponse)
def compare_chat_modes(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatCompareResponse:
    try:
        result = compare_answers(
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

    return ChatCompareResponse(
        query=request.query,
        user_id=request.user_id,
        grounded=ChatResponse(
            query=request.query,
            user_id=request.user_id,
            **_to_chat_payload(result.grounded),
        ),
        ungrounded=ChatResponse(
            query=request.query,
            user_id=request.user_id,
            **_to_chat_payload(result.ungrounded),
        ),
    )


def _to_chat_payload(result: RagAnswer) -> dict:
    return {
        "mode": result.mode,
        "answer_status": result.answer_status,
        "answer": result.answer,
        "claims": [
            ChatClaim(
                claim=claim.claim,
                source_chunk_ids=claim.source_chunk_ids,
                support_level=claim.support_level,
                evidence_quote=claim.evidence_quote,
            )
            for claim in result.claims
        ],
        "overall_groundedness": result.overall_groundedness,
        "sources": [
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
    }
