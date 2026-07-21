import json
import logging
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import LLMConfigurationError, LLMProvider, LLMProviderError
from app.models.concept import Concept
from app.models.document import Chunk, Document
from app.models.misconception import Misconception
from app.models.quiz import QuizAttempt, QuizItem

MisconceptionType = Literal[
    "concept_confusion",
    "incorrect_definition",
    "missing_prerequisite",
    "incomplete_reasoning",
    "source_misinterpretation",
    "unknown",
]

ALLOWED_MISCONCEPTION_TYPES: set[str] = {
    "concept_confusion",
    "incorrect_definition",
    "missing_prerequisite",
    "incomplete_reasoning",
    "source_misinterpretation",
    "unknown",
}

SYSTEM_PROMPT = (
    "You classify the likely reason for an incorrect quiz answer in a "
    "source-grounded AI tutor.\n"
    "Use only the quiz, selected answer, correct answer, concept, and source "
    "evidence supplied by the backend.\n"
    "Return valid JSON only. Do not include markdown fences or commentary.\n"
    "Allowed misconception_type values: concept_confusion, incorrect_definition, "
    "missing_prerequisite, incomplete_reasoning, source_misinterpretation, "
    "unknown.\n"
    "If the evidence is too weak to identify a specific reason, use unknown."
)

logger = logging.getLogger(__name__)


class MisconceptionDetectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class MisconceptionSummary:
    misconception: Misconception
    concept_name: str | None = None


class MisconceptionPayload(BaseModel):
    misconception_type: MisconceptionType
    description: str = Field(..., min_length=1, max_length=500)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


def detect_misconception_for_attempt(
    db: Session,
    *,
    attempt: QuizAttempt,
    item: QuizItem,
    llm_provider: LLMProvider | None = None,
) -> Misconception | None:
    if attempt.is_correct or item.concept_id is None:
        return None

    existing = db.scalar(
        select(Misconception).where(Misconception.quiz_attempt_id == attempt.id)
    )
    if existing is not None:
        return existing

    concept = _load_attempt_concept(db=db, item=item)
    if concept is None:
        return None

    source_evidence = _load_source_evidence(db=db, item=item)
    provider = llm_provider or OpenAIProvider()
    response = provider.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=_build_detection_prompt(
            item=item,
            attempt=attempt,
            concept=concept,
            source_evidence=source_evidence,
        ),
        max_tokens=500,
        temperature=0.0,
    )
    payload = _parse_misconception_payload(response.text)
    evidence_snapshot = _build_evidence_snapshot(
        item=item,
        attempt=attempt,
        concept=concept,
        source_evidence=source_evidence,
    )
    misconception = Misconception(
        user_id=attempt.user_id,
        course_id=attempt.course_id,
        concept_id=concept.id,
        quiz_attempt_id=attempt.id,
        misconception_type=payload.misconception_type,
        description=payload.description,
        confidence=payload.confidence,
        evidence_snapshot=evidence_snapshot,
    )
    db.add(misconception)
    db.commit()
    db.refresh(misconception)
    return misconception


def try_detect_misconception_for_attempt(
    db: Session,
    *,
    attempt: QuizAttempt,
    item: QuizItem,
    llm_provider: LLMProvider | None = None,
) -> Misconception | None:
    try:
        return detect_misconception_for_attempt(
            db=db,
            attempt=attempt,
            item=item,
            llm_provider=llm_provider,
        )
    except (
        json.JSONDecodeError,
        ValidationError,
        MisconceptionDetectionError,
        LLMConfigurationError,
        LLMProviderError,
    ) as exc:
        db.rollback()
        logger.warning("Misconception detection skipped: %s", exc)
        return None


def list_misconceptions(
    db: Session,
    *,
    user_id: str,
    course_id: int | None = None,
    concept_id: int | None = None,
    limit: int = 50,
) -> list[MisconceptionSummary]:
    query = (
        select(Misconception, Concept.name)
        .join(Concept, Concept.id == Misconception.concept_id)
        .where(Misconception.user_id == user_id)
        .order_by(Misconception.created_at.desc(), Misconception.id.desc())
        .limit(limit)
    )
    if course_id is not None:
        query = query.where(Misconception.course_id == course_id)
    if concept_id is not None:
        query = query.where(Misconception.concept_id == concept_id)

    return [
        MisconceptionSummary(misconception=misconception, concept_name=concept_name)
        for misconception, concept_name in db.execute(query).all()
    ]


def _load_attempt_concept(*, db: Session, item: QuizItem) -> Concept | None:
    if item.concept_id is None:
        return None

    query = select(Concept).where(Concept.id == item.concept_id)
    if item.course_id is not None:
        query = query.where(Concept.course_id == item.course_id)
    return db.scalar(query)


def _load_source_evidence(*, db: Session, item: QuizItem) -> list[dict]:
    source_ids = [int(chunk_id) for chunk_id in item.source_chunk_ids or []]
    if not source_ids:
        return []

    query = (
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.id.in_(source_ids),
            Document.user_id == item.user_id,
        )
        .limit(5)
    )
    if item.course_id is not None:
        query = query.where(Document.course_id == item.course_id)

    evidence: list[dict] = []
    for chunk, document in db.execute(query).all():
        evidence.append(
            {
                "chunk_id": chunk.id,
                "document_id": document.id,
                "filename": document.filename,
                "content": chunk.content[:1200],
            }
        )
    return evidence


def _build_detection_prompt(
    *,
    item: QuizItem,
    attempt: QuizAttempt,
    concept: Concept,
    source_evidence: list[dict],
) -> str:
    options = "\n".join(
        f"{option.get('id')}. {option.get('text')}" for option in item.options or []
    )
    source_text = "\n\n".join(
        f"[chunk_id={source['chunk_id']}] {source['content']}"
        for source in source_evidence
    )
    if not source_text:
        source_text = item.evidence_quote or "No source excerpt snapshot available."

    return f"""Concept:
{concept.name}

Concept description:
{concept.description or "No concept description available."}

Quiz question:
{item.question}

Options:
{options}

Learner selected:
{attempt.selected_option_id}. {attempt.selected_option_text}

Correct answer:
{attempt.correct_option_id}. {attempt.correct_option_text}

Instructor explanation:
{item.explanation or item.answer}

Source evidence:
{source_text}

Return this exact JSON shape:
{{
  "misconception_type": "concept_confusion",
  "description": "one concise sentence explaining the likely error",
  "confidence": 0.0
}}"""


def _parse_misconception_payload(text: str) -> MisconceptionPayload:
    cleaned = _strip_markdown_fence(text)
    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise MisconceptionDetectionError(
            "The model did not return valid misconception JSON"
        ) from exc

    try:
        payload = MisconceptionPayload.model_validate(raw)
    except ValidationError as exc:
        raise MisconceptionDetectionError(
            "The misconception JSON failed validation"
        ) from exc

    if payload.misconception_type not in ALLOWED_MISCONCEPTION_TYPES:
        raise MisconceptionDetectionError("Unknown misconception type")
    return payload


def _build_evidence_snapshot(
    *,
    item: QuizItem,
    attempt: QuizAttempt,
    concept: Concept,
    source_evidence: list[dict],
) -> dict:
    return {
        "concept_id": concept.id,
        "concept_name": concept.name,
        "quiz_item_id": item.id,
        "quiz_origin": item.origin,
        "question": item.question,
        "options": item.options or [],
        "selected_option_id": attempt.selected_option_id,
        "selected_option_text": attempt.selected_option_text,
        "correct_option_id": attempt.correct_option_id,
        "correct_option_text": attempt.correct_option_text,
        "explanation": item.explanation or item.answer,
        "source_chunk_ids": item.source_chunk_ids or [],
        "evidence_quote": item.evidence_quote,
        "source_evidence": source_evidence,
    }


def _strip_markdown_fence(text: str) -> str:
    cleaned = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return cleaned
