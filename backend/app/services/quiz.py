import json
import re

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import LLMProvider
from app.models.quiz import QuizItem
from app.schemas.quiz import Difficulty
from app.services.retrieval import RetrievedChunk, retrieve_relevant_chunks


class QuizGenerationError(RuntimeError):
    pass


class GeneratedQuizItem(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    source_chunk_ids: list[int] = Field(default_factory=list)


class GeneratedQuizPayload(BaseModel):
    items: list[GeneratedQuizItem] = Field(..., min_length=1)


SYSTEM_PROMPT = (
    "You generate study quiz questions for a student's uploaded course materials.\n"
    "Use only the provided source excerpts.\n"
    "Return valid JSON only. Do not include markdown fences or commentary.\n"
    "Every item must include question, answer, and source_chunk_ids."
)


def generate_quiz_items(
    db: Session,
    *,
    topic: str,
    user_id: str = "demo-user",
    count: int = 5,
    difficulty: Difficulty = "medium",
    top_k: int = 5,
    llm_provider: LLMProvider | None = None,
) -> list[QuizItem]:
    chunks = retrieve_relevant_chunks(db=db, query=topic, user_id=user_id, top_k=top_k)
    if not chunks:
        raise QuizGenerationError("No relevant uploaded materials found for this topic")

    provider = llm_provider or OpenAIProvider()
    response = provider.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=_build_quiz_prompt(
            topic=topic,
            count=count,
            difficulty=difficulty,
            chunks=chunks,
        ),
        max_tokens=1200,
        temperature=0.3,
    )
    payload = _parse_generated_quiz(response.text)
    source_ids = {chunk.chunk_id for chunk in chunks}

    quiz_items = [
        QuizItem(
            user_id=user_id,
            question=item.question,
            answer=item.answer,
            difficulty=difficulty,
            source_chunk_ids=[
                chunk_id for chunk_id in item.source_chunk_ids if chunk_id in source_ids
            ],
        )
        for item in payload.items[:count]
    ]

    if not quiz_items:
        raise QuizGenerationError("The model did not generate any valid quiz items")

    db.add_all(quiz_items)
    db.commit()
    for item in quiz_items:
        db.refresh(item)

    return quiz_items


def list_quiz_items(
    db: Session,
    *,
    user_id: str = "demo-user",
    limit: int = 50,
) -> list[QuizItem]:
    return list(
        db.scalars(
            select(QuizItem)
            .where(QuizItem.user_id == user_id)
            .order_by(QuizItem.created_at.desc())
            .limit(limit)
        )
    )


def _build_quiz_prompt(
    *,
    topic: str,
    count: int,
    difficulty: Difficulty,
    chunks: list[RetrievedChunk],
) -> str:
    context = "\n\n".join(
        f"[chunk_id={chunk.chunk_id}] {chunk.content.strip()}" for chunk in chunks
    )
    return f"""Topic:
{topic}

Difficulty:
{difficulty}

Number of questions:
{count}

Source excerpts:
{context}

Return this exact JSON shape:
{{
  "items": [
    {{
      "question": "question text",
      "answer": "answer text",
      "source_chunk_ids": [123]
    }}
  ]
}}"""


def _parse_generated_quiz(text: str) -> GeneratedQuizPayload:
    cleaned = _strip_markdown_fence(text)
    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise QuizGenerationError("The model did not return valid quiz JSON") from exc

    try:
        return GeneratedQuizPayload.model_validate(raw)
    except ValidationError as exc:
        raise QuizGenerationError("The generated quiz JSON failed validation") from exc


def _strip_markdown_fence(text: str) -> str:
    cleaned = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return cleaned
