from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings
from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import LLMProvider
from app.services.retrieval import RetrievedChunk, retrieve_relevant_chunks


@dataclass(frozen=True)
class RagSource:
    chunk_id: int
    document_id: int
    filename: str
    content: str
    metadata: dict
    distance: float
    similarity: float


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    sources: list[RagSource]


SYSTEM_PROMPT = (
    "You are an AI learning tutor for a student's uploaded course materials.\n"
    "Answer only using the provided source excerpts.\n"
    "Cite supporting evidence inline with labels such as [S1] and [S2].\n"
    "If the sources do not contain enough evidence, say that the uploaded "
    "materials do not contain enough information.\n"
    "Use the same language as the student's question when possible."
)


def answer_question(
    db: Session,
    query: str,
    user_id: str = "demo-user",
    top_k: int = 5,
    llm_provider: LLMProvider | None = None,
) -> RagAnswer:
    chunks = retrieve_relevant_chunks(db=db, query=query, user_id=user_id, top_k=top_k)
    sources = [_to_rag_source(chunk) for chunk in chunks]

    if not chunks:
        return RagAnswer(
            answer=(
                "The uploaded materials do not contain enough information "
                "to answer this question."
            ),
            sources=[],
        )

    provider = llm_provider or OpenAIProvider()
    response = provider.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=_build_user_prompt(query=query, chunks=chunks),
        max_tokens=800,
        temperature=0.2,
    )

    return RagAnswer(answer=response.text, sources=sources)


def _to_rag_source(chunk: RetrievedChunk) -> RagSource:
    return RagSource(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        filename=chunk.filename,
        content=chunk.content,
        metadata=chunk.metadata,
        distance=chunk.distance,
        similarity=chunk.similarity,
    )


def _build_user_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    context = _format_context(chunks)
    return f"""Student question:
{query}

Source excerpts:
{context}

Write a clear learning-focused answer. Every factual claim that comes from
the source excerpts should cite the relevant source label."""


def _format_context(chunks: list[RetrievedChunk]) -> str:
    remaining_chars = settings.rag_max_context_chars
    formatted_chunks: list[str] = []

    for index, chunk in enumerate(chunks, start=1):
        if remaining_chars <= 0:
            break

        content = chunk.content.strip()
        if len(content) > remaining_chars:
            content = content[:remaining_chars].rsplit(" ", 1)[0].strip()

        if not content:
            continue

        metadata = ", ".join(f"{key}: {value}" for key, value in chunk.metadata.items())
        header = f"[S{index}] filename: {chunk.filename}; chunk_id: {chunk.chunk_id}"
        if metadata:
            header = f"{header}; {metadata}"

        block = f"{header}\n{content}"
        formatted_chunks.append(block)
        remaining_chars -= len(content)

    return "\n\n".join(formatted_chunks)
