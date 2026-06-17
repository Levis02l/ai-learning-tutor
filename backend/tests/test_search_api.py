from fastapi.testclient import TestClient

from app.main import app
from app.services.embeddings import EmbeddingConfigurationError


def test_search_validation_rejects_empty_query() -> None:
    client = TestClient(app)

    response = client.post("/search", json={"query": ""})

    assert response.status_code == 422


def test_search_returns_503_when_embedding_key_is_missing(monkeypatch) -> None:
    def raise_missing_key(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise EmbeddingConfigurationError("OPENAI_API_KEY is required for embeddings")

    monkeypatch.setattr("app.api.search.retrieve_relevant_chunks", raise_missing_key)
    client = TestClient(app)

    response = client.post("/search", json={"query": "What is AI?"})

    assert response.status_code == 503
    assert response.json()["detail"] == "OPENAI_API_KEY is required for embeddings"
