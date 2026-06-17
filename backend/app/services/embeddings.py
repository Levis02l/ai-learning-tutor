from openai import OpenAI

from app.config import settings

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingConfigurationError(RuntimeError):
    pass


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not settings.openai_api_key:
        raise EmbeddingConfigurationError("OPENAI_API_KEY is required for embeddings")

    if not texts:
        return []

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)

    return [item.embedding for item in response.data]
