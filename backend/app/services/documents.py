from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.services.ingestion import UPLOAD_DIR


class DocumentNotFoundError(RuntimeError):
    pass


def delete_document(
    db: Session,
    *,
    document_id: int,
    user_id: str,
) -> None:
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    if document is None:
        raise DocumentNotFoundError("Document not found for this user")

    storage_path = document.storage_path
    db.delete(document)
    db.commit()

    if storage_path:
        _delete_stored_file(storage_path)


def _delete_stored_file(storage_path: str) -> None:
    upload_root = UPLOAD_DIR.resolve()
    path = Path(storage_path)
    candidate = path if path.is_absolute() else Path.cwd() / path

    try:
        resolved = candidate.resolve()
    except OSError:
        return

    if resolved != upload_root and upload_root not in resolved.parents:
        return

    try:
        resolved.unlink(missing_ok=True)
    except OSError:
        return
