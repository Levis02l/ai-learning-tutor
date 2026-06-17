import pytest

from app.services.ingestion import (
    UnsupportedDocumentTypeError,
    chunk_text,
    clean_text,
    get_file_type,
)


def test_get_file_type_accepts_supported_extensions() -> None:
    assert get_file_type("lecture.PDF") == "pdf"
    assert get_file_type("slides.pptx") == "pptx"
    assert get_file_type("notes.docx") == "docx"
    assert get_file_type("summary.md") == "md"


def test_get_file_type_rejects_unsupported_extensions() -> None:
    with pytest.raises(UnsupportedDocumentTypeError):
        get_file_type("archive.zip")


def test_clean_text_removes_empty_lines_and_null_bytes() -> None:
    assert clean_text(" hello \n\n\x00\n world ") == "hello\nworld"


def test_chunk_text_uses_overlap() -> None:
    chunks = chunk_text("abcdefghij", chunk_size=4, overlap=1)

    assert chunks == ["abcd", "defg", "ghij"]
