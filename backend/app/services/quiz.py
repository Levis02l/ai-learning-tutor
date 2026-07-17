import json
import re

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import LLMProvider
from app.models.document import Chunk, Document
from app.models.quiz import QuizItem
from app.schemas.quiz import Difficulty, QuestionType, TraceabilityLabel
from app.services.retrieval import RetrievedChunk, retrieve_relevant_chunks


class QuizGenerationError(RuntimeError):
    pass


class GeneratedQuizItem(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    source_chunk_ids: list[int] = Field(default_factory=list)
    evidence_quote: str = ""
    question_type: QuestionType = "conceptual"
    traceability_label: TraceabilityLabel = "not_traceable"


class GeneratedQuizPayload(BaseModel):
    items: list[GeneratedQuizItem] = Field(..., min_length=1)


SYSTEM_PROMPT = (
    "You generate study quiz questions for a student's uploaded course materials.\n"
    "Use only the provided source excerpts.\n"
    "Return valid JSON only. Do not include markdown fences or commentary.\n"
    "Every item must include question, answer, source_chunk_ids, evidence_quote, "
    "question_type, and traceability_label.\n"
    "Allowed question_type values: definition, conceptual, application, comparison.\n"
    "Allowed traceability_label values: fully_traceable, partially_traceable, "
    "weakly_traceable, not_traceable."
)


def generate_quiz_items(
    db: Session,
    *,
    topic: str | None = None,
    user_id: str = "demo-user",
    course_id: int | None = None,
    count: int = 5,
    difficulty: Difficulty = "medium",
    top_k: int = 5,
    llm_provider: LLMProvider | None = None,
) -> list[QuizItem]:
    focus = topic.strip() if topic else ""
    chunks = _retrieve_quiz_chunks(
        db=db,
        focus=focus,
        user_id=user_id,
        top_k=top_k,
        course_id=course_id,
    )
    if not chunks:
        raise QuizGenerationError("No uploaded materials found in this scope")

    provider = llm_provider or OpenAIProvider()
    response = provider.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=_build_quiz_prompt(
            topic=focus or "current course materials",
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
        _to_quiz_item(
            item=item,
            user_id=user_id,
            course_id=course_id,
            difficulty=difficulty,
            valid_source_ids=source_ids,
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
    course_id: int | None = None,
    limit: int = 50,
) -> list[QuizItem]:
    query = select(QuizItem).where(QuizItem.user_id == user_id)
    if course_id is not None:
        query = query.where(QuizItem.course_id == course_id)

    return list(
        db.scalars(
            query.order_by(QuizItem.created_at.desc()).limit(limit)
        )
    )


def _retrieve_quiz_chunks(
    *,
    db: Session,
    focus: str,
    user_id: str,
    top_k: int,
    course_id: int | None,
) -> list[RetrievedChunk]:
    if focus:
        return retrieve_relevant_chunks(
            db=db,
            query=focus,
            user_id=user_id,
            top_k=top_k,
            course_id=course_id,
        )

    query = (
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.user_id == user_id)
    )
    if course_id is not None:
        query = query.where(Document.course_id == course_id)

    rows = db.execute(
        query.order_by(Document.created_at.desc(), Chunk.id.asc()).limit(top_k)
    ).all()

    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=document.id,
            course_id=document.course_id,
            filename=document.filename,
            content=chunk.content,
            metadata=chunk.chunk_metadata,
            distance=0.0,
            similarity=1.0,
        )
        for chunk, document in rows
    ]


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
      "source_chunk_ids": [123],
      "evidence_quote": "short quote or close paraphrase from the source",
      "question_type": "conceptual",
      "traceability_label": "fully_traceable"
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


def _to_quiz_item(
    *,
    item: GeneratedQuizItem,
    user_id: str,
    difficulty: Difficulty,
    valid_source_ids: set[int],
    course_id: int | None = None,
) -> QuizItem:
    source_chunk_ids = [
        chunk_id for chunk_id in item.source_chunk_ids if chunk_id in valid_source_ids
    ]
    traceability_label = item.traceability_label
    if not source_chunk_ids:
        traceability_label = "not_traceable"
    elif traceability_label == "not_traceable":
        traceability_label = "weakly_traceable"

    return QuizItem(
        user_id=user_id,
        course_id=course_id,
        question=item.question,
        answer=item.answer,
        difficulty=difficulty,
        source_chunk_ids=source_chunk_ids,
        evidence_quote=item.evidence_quote,
        question_type=item.question_type,
        traceability_label=traceability_label,
    )
