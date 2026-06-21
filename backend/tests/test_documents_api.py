from fastapi.testclient import TestClient

from app.main import app
from app.services.documents import DocumentNotFoundError


def test_delete_document_returns_204(monkeypatch) -> None:
    calls: list[tuple[int, str]] = []

    def fake_delete_document(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((kwargs["document_id"], kwargs["user_id"]))

    monkeypatch.setattr("app.api.documents.delete_document", fake_delete_document)
    client = TestClient(app)

    response = client.delete("/documents/12?user_id=demo-user")

    assert response.status_code == 204
    assert calls == [(12, "demo-user")]


def test_delete_document_returns_404_when_missing(monkeypatch) -> None:
    def fake_delete_document(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise DocumentNotFoundError("Document not found for this user")

    monkeypatch.setattr("app.api.documents.delete_document", fake_delete_document)
    client = TestClient(app)

    response = client.delete("/documents/999?user_id=demo-user")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found for this user"
