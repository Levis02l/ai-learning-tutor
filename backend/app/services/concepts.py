import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import LLMProvider
from app.models.concept import Concept, ConceptPrerequisite, ConceptSourceChunk
from app.models.course import Course
from app.models.document import Chunk, Document
from app.models.quiz import QuizAttempt, QuizItem
from app.models.review import ReviewRecord
from app.services.learner_state import _calculate_attempt_state_metrics
from app.services.retrieval import RetrievedChunk


class ConceptExtractionError(RuntimeError):
    pass


class ConceptNotFoundError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConceptExtractionStats:
    course_id: int
    concepts_created: int
    concepts_reused: int
    source_links_created: int
    prerequisites_created: int
    candidates_skipped: int


@dataclass(frozen=True)
class ConceptSummary:
    concept: Concept
    source_count: int
    prerequisite_count: int


@dataclass(frozen=True)
class ConceptSource:
    chunk_id: int
    document_id: int
    filename: str
    content: str
    metadata: dict
    relevance_score: float


@dataclass(frozen=True)
class ConceptPrerequisiteDetail:
    concept: Concept
    confidence: float


@dataclass(frozen=True)
class ConceptDetail:
    concept: Concept
    sources: list[ConceptSource]
    prerequisites: list[ConceptPrerequisiteDetail]


ConceptLearnerStateStatus = Literal["observed", "unobserved"]


@dataclass(frozen=True)
class ConceptLearnerState:
    concept_id: int
    concept_name: str
    state_status: ConceptLearnerStateStatus
    mastery_score: float | None
    recent_accuracy: float | None
    attempt_count: int
    consecutive_errors: int
    last_attempted_at: datetime | None
    review_due: bool
    needs_attention: bool


@dataclass(frozen=True)
class ResolvedConcept:
    concept: Concept
    confidence: float
    reason: str


@dataclass(frozen=True)
class _SourceChunk:
    chunk_id: int
    document_id: int
    filename: str
    content: str
    metadata: dict


@dataclass(frozen=True)
class _ConceptCandidate:
    name: str
    normalized_name: str
    description: str
    extraction_confidence: float
    source_chunk_ids: list[int]
    prerequisites: list[str]


class _GeneratedConcept(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    extraction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_chunk_ids: list[int] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)


class _GeneratedConceptPayload(BaseModel):
    concepts: list[_GeneratedConcept] = Field(..., min_length=1)


SYSTEM_PROMPT = (
    "You extract a lightweight concept graph from course material excerpts.\n"
    "Use only the supplied excerpts.\n"
    "Return valid JSON only. Do not include markdown fences or commentary.\n"
    "Use canonical, non-duplicate concept names.\n"
    "Each concept must include name, description, extraction_confidence, "
    "source_chunk_ids, and prerequisites.\n"
    "source_chunk_ids must reference only chunk ids shown in the excerpts.\n"
    "Prerequisites should be conservative candidate relationships, not guesses."
)


def extract_course_concepts(
    db: Session,
    *,
    user_id: str,
    course_id: int,
    max_chunks: int = 24,
    max_concepts: int = 20,
    llm_provider: LLMProvider | None = None,
) -> ConceptExtractionStats:
    chunks = _load_course_chunks(
        db=db,
        user_id=user_id,
        course_id=course_id,
        limit=max_chunks,
    )
    if not chunks:
        raise ConceptExtractionError("No processed chunks found for this course")

    provider = llm_provider or OpenAIProvider()
    response = provider.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=_build_extraction_prompt(
            chunks=chunks,
            max_concepts=max_concepts,
        ),
        max_tokens=2600,
        temperature=0.2,
    )
    payload = _parse_generated_concepts(response.text)
    candidates = _deduplicate_candidates(
        _to_candidates(payload.concepts),
        max_concepts=max_concepts,
    )

    return _upsert_concept_graph(
        db=db,
        course_id=course_id,
        candidates=candidates,
        valid_chunk_ids={chunk.chunk_id for chunk in chunks},
    )


def list_course_concepts(
    db: Session,
    *,
    user_id: str,
    course_id: int,
) -> list[ConceptSummary]:
    _require_course(db=db, user_id=user_id, course_id=course_id)
    concepts = list(
        db.scalars(
            select(Concept)
            .where(Concept.course_id == course_id)
            .order_by(Concept.name.asc())
        )
    )
    return [
        ConceptSummary(
            concept=concept,
            source_count=_count_sources(db=db, concept_id=concept.id),
            prerequisite_count=_count_prerequisites(db=db, concept_id=concept.id),
        )
        for concept in concepts
    ]


def get_concept_detail(
    db: Session,
    *,
    user_id: str,
    concept_id: int,
) -> ConceptDetail:
    concept = db.scalar(
        select(Concept)
        .join(Course, Course.id == Concept.course_id)
        .where(Concept.id == concept_id, Course.user_id == user_id)
    )
    if concept is None:
        raise ConceptNotFoundError("Concept not found for this user")

    source_rows = db.execute(
        select(ConceptSourceChunk, Chunk, Document)
        .join(Chunk, Chunk.id == ConceptSourceChunk.chunk_id)
        .join(Document, Document.id == Chunk.document_id)
        .where(ConceptSourceChunk.concept_id == concept.id)
        .order_by(ConceptSourceChunk.relevance_score.desc(), Chunk.id.asc())
    ).all()
    prerequisite_rows = db.execute(
        select(ConceptPrerequisite, Concept)
        .join(
            Concept,
            Concept.id == ConceptPrerequisite.prerequisite_concept_id,
        )
        .where(ConceptPrerequisite.concept_id == concept.id)
        .order_by(Concept.name.asc())
    ).all()

    return ConceptDetail(
        concept=concept,
        sources=[
            ConceptSource(
                chunk_id=chunk.id,
                document_id=document.id,
                filename=document.filename,
                content=chunk.content,
                metadata=chunk.chunk_metadata,
                relevance_score=link.relevance_score,
            )
            for link, chunk, document in source_rows
        ],
        prerequisites=[
            ConceptPrerequisiteDetail(
                concept=prerequisite,
                confidence=link.confidence,
            )
            for link, prerequisite in prerequisite_rows
        ],
    )


def list_concept_learner_states(
    db: Session,
    *,
    user_id: str,
    course_id: int,
    now: datetime | None = None,
) -> list[ConceptLearnerState]:
    _require_course(db=db, user_id=user_id, course_id=course_id)
    current_time = now or datetime.utcnow()
    concepts = list(
        db.scalars(
            select(Concept)
            .where(Concept.course_id == course_id)
            .order_by(Concept.name.asc())
        )
    )
    concept_ids = [concept.id for concept in concepts]
    if not concept_ids:
        return []

    quiz_items_by_concept = _load_quiz_items_by_concept(
        db=db,
        user_id=user_id,
        course_id=course_id,
        concept_ids=concept_ids,
    )
    attempts_by_concept = _load_attempts_by_concept(
        db=db,
        user_id=user_id,
        course_id=course_id,
        concept_ids=concept_ids,
    )
    reviews_by_concept = _load_reviews_by_concept(
        db=db,
        user_id=user_id,
        course_id=course_id,
        concept_ids=concept_ids,
    )

    states: list[ConceptLearnerState] = []
    for concept in concepts:
        states.append(
            _build_concept_learner_state(
                concept=concept,
                quiz_items=quiz_items_by_concept.get(concept.id, []),
                attempts=attempts_by_concept.get(concept.id, []),
                reviews=reviews_by_concept.get(concept.id, []),
                now=current_time,
            )
        )

    return states


def resolve_concept_for_focus(
    db: Session,
    *,
    user_id: str,
    course_id: int,
    focus: str,
    confidence_threshold: float = 0.72,
) -> ResolvedConcept | None:
    normalized_focus = _normalize_name(focus)
    if not normalized_focus:
        return None

    concepts = list(
        db.scalars(
            select(Concept)
            .join(Course, Course.id == Concept.course_id)
            .where(Concept.course_id == course_id, Course.user_id == user_id)
            .order_by(Concept.name.asc())
        )
    )
    scored: list[ResolvedConcept] = []
    for concept in concepts:
        score = _score_concept_match(
            normalized_focus=normalized_focus,
            concept=concept,
        )
        if score is not None:
            scored.append(score)
    if not scored:
        return None

    best = max(
        scored,
        key=lambda result: (
            result.confidence,
            len(result.concept.normalized_name),
        ),
    )
    if best.confidence < confidence_threshold:
        return None
    return best


def get_concept_quiz_chunks(
    db: Session,
    *,
    user_id: str,
    course_id: int,
    concept_id: int,
    limit: int,
) -> list[RetrievedChunk]:
    rows = db.execute(
        select(ConceptSourceChunk, Chunk, Document)
        .join(Chunk, Chunk.id == ConceptSourceChunk.chunk_id)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            ConceptSourceChunk.concept_id == concept_id,
            Document.user_id == user_id,
            Document.course_id == course_id,
        )
        .order_by(ConceptSourceChunk.relevance_score.desc(), Chunk.id.asc())
        .limit(limit)
    ).all()

    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=document.id,
            course_id=document.course_id,
            filename=document.filename,
            content=chunk.content,
            metadata=chunk.chunk_metadata,
            distance=round(1.0 - link.relevance_score, 3),
            similarity=link.relevance_score,
        )
        for link, chunk, document in rows
    ]


def _load_quiz_items_by_concept(
    *,
    db: Session,
    user_id: str,
    course_id: int,
    concept_ids: list[int],
) -> dict[int, list[QuizItem]]:
    rows = list(
        db.scalars(
            select(QuizItem)
            .where(
                QuizItem.user_id == user_id,
                QuizItem.course_id == course_id,
                QuizItem.concept_id.in_(concept_ids),
                QuizItem.archived_at.is_(None),
            )
            .order_by(QuizItem.created_at.asc(), QuizItem.id.asc())
        )
    )
    by_concept: dict[int, list[QuizItem]] = {}
    for item in rows:
        if item.concept_id is not None:
            by_concept.setdefault(item.concept_id, []).append(item)
    return by_concept


def _load_attempts_by_concept(
    *,
    db: Session,
    user_id: str,
    course_id: int,
    concept_ids: list[int],
) -> dict[int, list[QuizAttempt]]:
    rows = db.execute(
        select(QuizAttempt, QuizItem.concept_id)
        .join(QuizItem, QuizItem.id == QuizAttempt.quiz_item_id)
        .where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.course_id == course_id,
            QuizItem.user_id == user_id,
            QuizItem.course_id == course_id,
            QuizItem.concept_id.in_(concept_ids),
        )
        .order_by(QuizAttempt.attempted_at.desc(), QuizAttempt.id.desc())
    ).all()
    by_concept: dict[int, list[QuizAttempt]] = {}
    for attempt, concept_id in rows:
        if concept_id is not None:
            by_concept.setdefault(concept_id, []).append(attempt)
    return by_concept


def _load_reviews_by_concept(
    *,
    db: Session,
    user_id: str,
    course_id: int,
    concept_ids: list[int],
) -> dict[int, list[ReviewRecord]]:
    rows = db.execute(
        select(ReviewRecord, QuizItem.concept_id)
        .join(QuizItem, QuizItem.id == ReviewRecord.item_id)
        .where(
            ReviewRecord.user_id == user_id,
            ReviewRecord.course_id == course_id,
            QuizItem.user_id == user_id,
            QuizItem.course_id == course_id,
            QuizItem.concept_id.in_(concept_ids),
        )
        .order_by(ReviewRecord.reviewed_at.desc(), ReviewRecord.id.desc())
    ).all()
    by_concept: dict[int, list[ReviewRecord]] = {}
    for review, concept_id in rows:
        if concept_id is not None:
            by_concept.setdefault(concept_id, []).append(review)
    return by_concept


def _has_due_concept_review(
    *,
    quiz_items: list[QuizItem],
    reviews: list[ReviewRecord],
    now: datetime,
) -> bool:
    if not quiz_items:
        return False

    latest_by_item: dict[int, ReviewRecord] = {}
    for review in reviews:
        latest_by_item.setdefault(review.item_id, review)

    for item in quiz_items:
        latest_review = latest_by_item.get(item.id)
        if latest_review is None or latest_review.due_at <= now:
            return True
    return False


def _build_concept_learner_state(
    *,
    concept: Concept,
    quiz_items: list[QuizItem],
    attempts: list[QuizAttempt],
    reviews: list[ReviewRecord],
    now: datetime,
) -> ConceptLearnerState:
    if not attempts:
        return ConceptLearnerState(
            concept_id=concept.id,
            concept_name=concept.name,
            state_status="unobserved",
            mastery_score=None,
            recent_accuracy=None,
            attempt_count=0,
            consecutive_errors=0,
            last_attempted_at=None,
            review_due=False,
            needs_attention=False,
        )

    review_due = _has_due_concept_review(
        quiz_items=quiz_items,
        reviews=reviews,
        now=now,
    )
    metrics = _calculate_attempt_state_metrics(
        quiz_items=quiz_items,
        attempts=attempts,
        due_penalty=review_due,
    )
    return ConceptLearnerState(
        concept_id=concept.id,
        concept_name=concept.name,
        state_status="observed",
        mastery_score=metrics.mastery_score,
        recent_accuracy=metrics.recent_accuracy,
        attempt_count=metrics.attempt_count,
        consecutive_errors=metrics.consecutive_errors,
        last_attempted_at=metrics.last_attempted_at,
        review_due=review_due,
        needs_attention=metrics.needs_attention or review_due,
    )


def _load_course_chunks(
    *,
    db: Session,
    user_id: str,
    course_id: int,
    limit: int,
) -> list[_SourceChunk]:
    rows = db.execute(
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Document.user_id == user_id,
            Document.course_id == course_id,
            Document.status == "done",
        )
        .order_by(Document.created_at.desc(), Chunk.id.asc())
        .limit(limit)
    ).all()

    return [
        _SourceChunk(
            chunk_id=chunk.id,
            document_id=document.id,
            filename=document.filename,
            content=chunk.content,
            metadata=chunk.chunk_metadata,
        )
        for chunk, document in rows
    ]


def _build_extraction_prompt(
    *,
    chunks: list[_SourceChunk],
    max_concepts: int,
) -> str:
    context = "\n\n".join(
        f"[chunk_id={chunk.chunk_id}; document={chunk.filename}]\n"
        f"{chunk.content.strip()}"
        for chunk in chunks
    )
    return f"""Extract up to {max_concepts} important course concepts.

Prefer concepts that are useful for tutoring, quiz generation, and mastery tracking.
Avoid administrative topics unless they are academically important.
For prerequisites, include only concept names that also appear in this extraction.

Return JSON in this exact shape:
{{
  "concepts": [
    {{
      "name": "canonical concept name",
      "description": "one-sentence course-grounded description",
      "extraction_confidence": 0.0,
      "source_chunk_ids": [1, 2],
      "prerequisites": ["other extracted concept name"]
    }}
  ]
}}

Course excerpts:
{context}
"""


def _parse_generated_concepts(text: str) -> _GeneratedConceptPayload:
    raw = text.strip()
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        raw = match.group(0)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConceptExtractionError(
            "Concept extraction returned invalid JSON"
        ) from exc

    try:
        return _GeneratedConceptPayload.model_validate(payload)
    except ValidationError as exc:
        raise ConceptExtractionError(
            "Concept extraction JSON failed validation"
        ) from exc


def _to_candidates(concepts: Iterable[_GeneratedConcept]) -> list[_ConceptCandidate]:
    candidates: list[_ConceptCandidate] = []
    for concept in concepts:
        normalized_name = _normalize_name(concept.name)
        if not normalized_name:
            continue
        candidates.append(
            _ConceptCandidate(
                name=_clean_name(concept.name),
                normalized_name=normalized_name,
                description=concept.description.strip(),
                extraction_confidence=round(concept.extraction_confidence, 3),
                source_chunk_ids=_unique_ints(concept.source_chunk_ids),
                prerequisites=[
                    prerequisite.strip()
                    for prerequisite in concept.prerequisites
                    if _normalize_name(prerequisite)
                ],
            )
        )
    return candidates


def _deduplicate_candidates(
    candidates: Iterable[_ConceptCandidate],
    *,
    max_concepts: int,
) -> list[_ConceptCandidate]:
    by_name: dict[str, _ConceptCandidate] = {}
    for candidate in candidates:
        existing = by_name.get(candidate.normalized_name)
        if existing is None:
            by_name[candidate.normalized_name] = candidate
            continue

        by_name[candidate.normalized_name] = _ConceptCandidate(
            name=existing.name,
            normalized_name=existing.normalized_name,
            description=_prefer_description(
                existing.description,
                candidate.description,
            ),
            extraction_confidence=max(
                existing.extraction_confidence,
                candidate.extraction_confidence,
            ),
            source_chunk_ids=_unique_ints(
                [*existing.source_chunk_ids, *candidate.source_chunk_ids]
            ),
            prerequisites=_unique_names(
                [*existing.prerequisites, *candidate.prerequisites]
            ),
        )

    return list(by_name.values())[:max_concepts]


def _upsert_concept_graph(
    *,
    db: Session,
    course_id: int,
    candidates: list[_ConceptCandidate],
    valid_chunk_ids: set[int],
) -> ConceptExtractionStats:
    created = 0
    reused = 0
    skipped = 0
    source_links_created = 0
    prerequisites_created = 0

    existing_by_name = {
        concept.normalized_name: concept
        for concept in db.scalars(
            select(Concept).where(Concept.course_id == course_id)
        )
    }
    concept_by_name = dict(existing_by_name)
    candidate_by_name: dict[str, _ConceptCandidate] = {}

    for candidate in candidates:
        source_ids = [
            chunk_id
            for chunk_id in candidate.source_chunk_ids
            if chunk_id in valid_chunk_ids
        ]
        if not source_ids:
            skipped += 1
            continue

        concept = concept_by_name.get(candidate.normalized_name)
        if concept is None:
            concept = Concept(
                course_id=course_id,
                name=candidate.name,
                normalized_name=candidate.normalized_name,
                description=candidate.description,
                extraction_confidence=candidate.extraction_confidence,
            )
            db.add(concept)
            db.flush()
            concept_by_name[candidate.normalized_name] = concept
            created += 1
        else:
            concept.description = _prefer_description(
                concept.description,
                candidate.description,
            )
            concept.extraction_confidence = max(
                concept.extraction_confidence,
                candidate.extraction_confidence,
            )
            db.add(concept)
            reused += 1

        candidate_by_name[candidate.normalized_name] = candidate
        for chunk_id in source_ids:
            source_link = db.get(ConceptSourceChunk, (concept.id, chunk_id))
            if source_link is None:
                db.add(
                    ConceptSourceChunk(
                        concept_id=concept.id,
                        chunk_id=chunk_id,
                        relevance_score=candidate.extraction_confidence,
                    )
                )
                source_links_created += 1
            else:
                source_link.relevance_score = max(
                    source_link.relevance_score,
                    candidate.extraction_confidence,
                )
                db.add(source_link)

    db.flush()
    for normalized_name, candidate in candidate_by_name.items():
        concept = concept_by_name[normalized_name]
        for prerequisite_name in candidate.prerequisites:
            prerequisite = concept_by_name.get(_normalize_name(prerequisite_name))
            if prerequisite is None or prerequisite.id == concept.id:
                continue
            prerequisite_link = db.get(
                ConceptPrerequisite,
                (concept.id, prerequisite.id),
            )
            if prerequisite_link is None:
                db.add(
                    ConceptPrerequisite(
                        concept_id=concept.id,
                        prerequisite_concept_id=prerequisite.id,
                        confidence=candidate.extraction_confidence,
                    )
                )
                prerequisites_created += 1
            else:
                prerequisite_link.confidence = max(
                    prerequisite_link.confidence,
                    candidate.extraction_confidence,
                )
                db.add(prerequisite_link)

    db.commit()
    return ConceptExtractionStats(
        course_id=course_id,
        concepts_created=created,
        concepts_reused=reused,
        source_links_created=source_links_created,
        prerequisites_created=prerequisites_created,
        candidates_skipped=skipped,
    )


def _require_course(*, db: Session, user_id: str, course_id: int) -> None:
    exists = db.scalar(
        select(func.count(Course.id)).where(
            Course.id == course_id,
            Course.user_id == user_id,
        )
    )
    if int(exists or 0) == 0:
        raise ConceptNotFoundError("Course not found for this user")


def _count_sources(*, db: Session, concept_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(ConceptSourceChunk.chunk_id)).where(
                ConceptSourceChunk.concept_id == concept_id
            )
        )
        or 0
    )


def _count_prerequisites(*, db: Session, concept_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(ConceptPrerequisite.prerequisite_concept_id)).where(
                ConceptPrerequisite.concept_id == concept_id
            )
        )
        or 0
    )


def _normalize_name(name: str) -> str:
    value = name.strip().lower()
    value = re.sub(r"^introduction to\s+", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    aliases = {
        "ai": "artificial intelligence",
        "ml": "machine learning",
        "nlp": "natural language processing",
    }
    return aliases.get(value, value)


def _score_concept_match(
    *,
    normalized_focus: str,
    concept: Concept,
) -> ResolvedConcept | None:
    concept_name = concept.normalized_name
    if not concept_name:
        return None
    if normalized_focus == concept_name:
        return ResolvedConcept(
            concept=concept,
            confidence=1.0,
            reason="exact_normalized_match",
        )

    compact_focus = normalized_focus.replace(" ", "")
    compact_concept = concept_name.replace(" ", "")
    if len(compact_concept) >= 4 and compact_concept in compact_focus:
        return ResolvedConcept(
            concept=concept,
            confidence=0.9,
            reason="compact_name_match",
        )

    focus_tokens = set(normalized_focus.split())
    concept_tokens = set(concept_name.split())
    if not focus_tokens or not concept_tokens:
        return None

    overlap = focus_tokens & concept_tokens
    coverage = len(overlap) / len(concept_tokens)
    if len(overlap) >= 2 and coverage >= 0.75:
        return ResolvedConcept(
            concept=concept,
            confidence=round(0.72 + min(coverage, 1.0) * 0.15, 3),
            reason="token_coverage_match",
        )
    return None


def _clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip())


def _unique_ints(values: Iterable[int]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _unique_names(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = _normalize_name(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(_clean_name(value))
    return result


def _prefer_description(first: str, second: str) -> str:
    first = first.strip()
    second = second.strip()
    if not first:
        return second
    if not second:
        return first
    return second if len(second) > len(first) else first
