from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.document import Chunk, Document
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.services.documents import DocumentNotFoundError, delete_document
from app.services.embeddings import EmbeddingConfigurationError, embed_texts
from app.services.ingestion import (
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
    chunk_text,
    extract_text_from_upload,
    get_file_type,
    save_upload_file,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form("demo-user"),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    try:
        file_type = get_file_type(file.filename or "")
        text = await extract_text_from_upload(file)
        chunks = chunk_text(text)
        embeddings = embed_texts(chunks)
        stored_path = await save_upload_file(file)
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except EmptyDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    filename = Path(file.filename or "untitled").name
    document = Document(
        user_id=user_id,
        filename=filename,
        file_type=file_type,
        storage_path=str(stored_path),
        status="done",
    )
    db.add(document)
    db.flush()

    db.add_all(
        Chunk(
            document_id=document.id,
            content=chunk,
            embedding=embedding,
            chunk_metadata={
                "chunk_index": index,
                "source_filename": document.filename,
                "file_type": file_type,
            },
        )
        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True))
    )
    db.commit()
    db.refresh(document)

    return DocumentUploadResponse(
        id=document.id,
        user_id=document.user_id,
        filename=document.filename,
        file_type=document.file_type,
        status=document.status,
        created_at=document.created_at,
        chunk_count=len(chunks),
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    user_id: str = "demo-user",
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    chunk_count = func.count(Chunk.id).label("chunk_count")
    rows = db.execute(
        select(Document, chunk_count)
        .outerjoin(Chunk)
        .where(Document.user_id == user_id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    ).all()

    return [
        DocumentResponse(
            id=document.id,
            user_id=document.user_id,
            filename=document.filename,
            file_type=document.file_type,
            status=document.status,
            created_at=document.created_at,
            chunk_count=count,
        )
        for document, count in rows
    ]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    document_id: int,
    user_id: str = "demo-user",
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_document(db=db, document_id=document_id, user_id=user_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
