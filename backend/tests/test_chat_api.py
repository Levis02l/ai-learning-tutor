from fastapi.testclient import TestClient

from app.llm.provider import LLMConfigurationError, LLMProviderError
from app.main import app
from app.services.rag import RagAnswer, RagClaim, RagSource


def test_chat_validation_rejects_empty_query() -> None:
    client = TestClient(app)

    response = client.post("/chat", json={"query": ""})

    assert response.status_code == 422


def test_chat_returns_grounded_answer(monkeypatch) -> None:
    def fake_answer_question(*args, **kwargs):  # type: ignore[no-untyped-def]
        return RagAnswer(
            mode="grounded_strict",
            answer_status="answered",
            answer=(
                "Artificial intelligence studies computational agents "
                "that act intelligently. [S1]"
            ),
            claims=[
                RagClaim(
                    claim=(
                        "Artificial intelligence studies computational agents "
                        "that act intelligently."
                    ),
                    source_chunk_ids=[82],
                    support_level="fully_supported",
                    evidence_quote=(
                        "AI is the field that studies computational agents."
                    ),
                )
            ],
            overall_groundedness=1.0,
            sources=[
                RagSource(
                    chunk_id=82,
                    document_id=2,
                    filename="lecture.pdf",
                    content="AI is the field that studies computational agents.",
                    metadata={"chunk_index": 8},
                    distance=0.4,
                    similarity=0.6,
                )
            ],
        )

    monkeypatch.setattr("app.api.chat.answer_question", fake_answer_question)
    client = TestClient(app)

    response = client.post("/chat", json={"query": "What is AI?", "top_k": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"].endswith("[S1]")
    assert body["answer_status"] == "answered"
    assert body["claims"][0]["support_level"] == "fully_supported"
    assert body["overall_groundedness"] == 1.0
    assert body["sources"][0]["chunk_id"] == 82


def test_chat_returns_503_when_llm_key_is_missing(monkeypatch) -> None:
    def raise_missing_key(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise LLMConfigurationError("OPENAI_API_KEY is required for chat generation")

    monkeypatch.setattr("app.api.chat.answer_question", raise_missing_key)
    client = TestClient(app)

    response = client.post("/chat", json={"query": "What is AI?"})

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "OPENAI_API_KEY is required for chat generation"
    )


def test_chat_returns_502_when_llm_generation_fails(monkeypatch) -> None:
    def raise_generation_error(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise LLMProviderError("OpenAI generation failed: model not found")

    monkeypatch.setattr("app.api.chat.answer_question", raise_generation_error)
    client = TestClient(app)

    response = client.post("/chat", json={"query": "What is AI?"})

    assert response.status_code == 502
    assert response.json()["detail"] == "OpenAI generation failed: model not found"
