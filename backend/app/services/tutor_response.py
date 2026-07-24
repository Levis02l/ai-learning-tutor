import json
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import LLMProvider, LLMProviderError
from app.models.quiz import QuizItem
from app.models.review import ReviewRecord
from app.schemas.chat import AnswerStatus, SupportLevel
from app.schemas.quiz import Difficulty
from app.services.policy import PolicyDecision, create_policy_decision
from app.services.quiz import (
    QuizGenerationError,
    generate_comprehension_check,
    generate_quiz_items,
    generate_quiz_items_from_chunks,
)
from app.services.retrieval import RetrievedChunk, retrieve_relevant_chunks
from app.services.review import get_due_review_items

TutorAnswerStatus = Literal[
    "answered",
    "partially_answered",
    "refused_no_evidence",
    "refused_ambiguous_material",
    "needs_more_material",
    "review_ready",
    "quiz_ready",
]


@dataclass(frozen=True)
class TutorResponseClaim:
    claim: str
    source_chunk_ids: list[int]
    support_level: SupportLevel
    evidence_quote: str


@dataclass(frozen=True)
class TutorResponseSource:
    chunk_id: int
    document_id: int
    course_id: int | None
    filename: str
    content: str
    metadata: dict
    distance: float
    similarity: float


@dataclass(frozen=True)
class TutorResponse:
    decision: PolicyDecision
    answer_status: TutorAnswerStatus
    answer: str
    claims: list[TutorResponseClaim] = field(default_factory=list)
    sources: list[TutorResponseSource] = field(default_factory=list)
    quiz_items: list[QuizItem] = field(default_factory=list)
    review_items: list[tuple[QuizItem, ReviewRecord | None]] = field(
        default_factory=list
    )
    suggested_next_step: str = ""


class TutorClaimPayload(BaseModel):
    claim: str = Field(..., min_length=1)
    source_chunk_ids: list[int] = Field(default_factory=list)
    support_level: SupportLevel
    evidence_quote: str = ""


class TutorAnswerPayload(BaseModel):
    answer_status: AnswerStatus
    answer: str = Field(..., min_length=1)
    claims: list[TutorClaimPayload] = Field(default_factory=list)


SYSTEM_PROMPT = (
    "You are an evidence-grounded AI learning tutor.\n"
    "Use only the provided course excerpts.\n"
    "Treat policy, learner-state, and misconception metadata as private teaching "
    "signals. Do not reveal internal labels, confidence scores, JSON fields, or "
    "policy names to the learner.\n"
    "Return valid JSON only. Do not include markdown fences or commentary.\n"
    "For every factual claim, include source_chunk_ids, support_level, and "
    "evidence_quote.\n"
    "Allowed support_level values: fully_supported, partially_supported, "
    "unsupported, contradicted, not_enough_information.\n"
    "If evidence is insufficient, set answer_status to refused_no_evidence."
)


def create_tutor_response(
    db: Session,
    *,
    query: str,
    user_id: str = "demo-user",
    course_id: int | None = None,
    top_k: int = 5,
    llm_provider: LLMProvider | None = None,
) -> TutorResponse:
    decision = create_policy_decision(
        db=db,
        query=query,
        user_id=user_id,
        course_id=course_id,
        top_k=top_k,
    )
    return execute_tutor_decision(
        db=db,
        decision=decision,
        top_k=top_k,
        llm_provider=llm_provider,
    )


def execute_tutor_decision(
    db: Session,
    *,
    decision: PolicyDecision,
    top_k: int = 5,
    llm_provider: LLMProvider | None = None,
) -> TutorResponse:
    if decision.selected_action == "refuse":
        return _deterministic_refusal(decision)

    if _can_use_deterministic_review(decision):
        return _review_queue_response(db=db, decision=decision)

    if decision.selected_action == "quiz":
        return _quiz_response(
            db=db,
            decision=decision,
            top_k=top_k,
            llm_provider=llm_provider,
        )

    if decision.selected_action in {"explain", "hint", "review"}:
        return _llm_tutor_response(
            db=db,
            decision=decision,
            top_k=top_k,
            llm_provider=llm_provider,
        )

    return _deterministic_refusal(decision)


def _deterministic_refusal(decision: PolicyDecision) -> TutorResponse:
    return TutorResponse(
        decision=decision,
        answer_status="refused_no_evidence",
        answer=(
            "I could not find enough reliable support in the selected course "
            "materials to answer this safely. Try uploading more relevant "
            "material, narrowing the question, or switching to the right course "
            "workspace."
        ),
        suggested_next_step=decision.suggested_next_step,
    )


def _can_use_deterministic_review(decision: PolicyDecision) -> bool:
    evidence_strength = decision.evidence_state_snapshot.get("evidence_strength")
    return (
        decision.selected_action == "review"
        and evidence_strength == "not_required"
    )


def _review_queue_response(db: Session, *, decision: PolicyDecision) -> TutorResponse:
    review_items = get_due_review_items(
        db=db,
        user_id=decision.user_id,
        course_id=decision.course_id,
        limit=5,
    )
    due_count = len(review_items)
    if due_count == 0:
        answer = "There are no due review items in this course right now."
    elif due_count == 1:
        answer = "1 traceable item is due for review."
    else:
        answer = f"{due_count} traceable items are due for review."

    return TutorResponse(
        decision=decision,
        answer_status="review_ready",
        answer=answer,
        review_items=review_items,
        suggested_next_step="Start with the first due review item.",
    )


def _quiz_response(
    *,
    db: Session,
    decision: PolicyDecision,
    top_k: int,
    llm_provider: LLMProvider | None,
) -> TutorResponse:
    concept_snapshot = decision.concept_state_snapshot or {}
    if decision.evidence_chunks:
        quiz_items = generate_quiz_items_from_chunks(
            db=db,
            topic=decision.query,
            user_id=decision.user_id,
            course_id=decision.course_id,
            concept_id=concept_snapshot.get("concept_id"),
            chunks=decision.evidence_chunks,
            count=1,
            difficulty=_quiz_difficulty(decision),
            origin="policy_quiz",
            llm_provider=llm_provider,
        )
    else:
        quiz_items = generate_quiz_items(
            db=db,
            topic=decision.query,
            user_id=decision.user_id,
            course_id=decision.course_id,
            count=1,
            difficulty=_quiz_difficulty(decision),
            top_k=top_k,
            origin="policy_quiz",
            llm_provider=llm_provider,
        )
    return TutorResponse(
        decision=decision,
        answer_status="quiz_ready",
        answer="I generated one traceable practice question for you.",
        quiz_items=quiz_items,
        suggested_next_step=(
            "Answer the question, then use the feedback to update mastery."
        ),
    )


def _llm_tutor_response(
    *,
    db: Session,
    decision: PolicyDecision,
    top_k: int,
    llm_provider: LLMProvider | None,
) -> TutorResponse:
    chunks = decision.evidence_chunks or retrieve_relevant_chunks(
        db=db,
        query=decision.query,
        user_id=decision.user_id,
        course_id=decision.course_id,
        top_k=top_k,
    )
    if not chunks:
        return _deterministic_refusal(decision)

    provider = llm_provider or OpenAIProvider()
    response = provider.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=_build_policy_aware_prompt(decision=decision, chunks=chunks),
        max_tokens=1000,
        temperature=0.2,
    )
    payload = _parse_tutor_answer(response.text)
    claims = _sanitize_claims(
        payload.claims,
        valid_chunk_ids={chunk.chunk_id for chunk in chunks},
    )

    return TutorResponse(
        decision=decision,
        answer_status=payload.answer_status,
        answer=payload.answer,
        claims=claims,
        sources=[_to_source(chunk) for chunk in chunks],
        quiz_items=_maybe_generate_comprehension_check(
            db=db,
            decision=decision,
            chunks=chunks,
            llm_provider=llm_provider,
        ),
        suggested_next_step=decision.suggested_next_step,
    )


def _quiz_difficulty(decision: PolicyDecision) -> Difficulty:
    if decision.response_strategy == "challenging":
        return "hard"
    if decision.response_strategy == "scaffolded":
        return "easy"
    return "medium"


def _maybe_generate_comprehension_check(
    *,
    db: Session,
    decision: PolicyDecision,
    chunks: list[RetrievedChunk],
    llm_provider: LLMProvider | None,
) -> list[QuizItem]:
    if not _should_generate_comprehension_check(decision=decision, chunks=chunks):
        return []

    concept_snapshot = decision.concept_state_snapshot or {}
    try:
        return [
            generate_comprehension_check(
                db=db,
                topic=concept_snapshot["concept_name"],
                user_id=decision.user_id,
                course_id=decision.course_id,
                concept_id=concept_snapshot["concept_id"],
                chunks=chunks,
                difficulty="easy",
                llm_provider=llm_provider,
            )
        ]
    except (KeyError, QuizGenerationError, LLMProviderError):
        return []


def _should_generate_comprehension_check(
    *,
    decision: PolicyDecision,
    chunks: list[RetrievedChunk],
) -> bool:
    evidence_strength = decision.evidence_state_snapshot.get("evidence_strength")
    return (
        decision.selected_action == "explain"
        and decision.response_strategy == "scaffolded"
        and decision.concept_state_snapshot is not None
        and evidence_strength in {"high", "medium"}
        and bool(chunks)
    )


def _build_policy_aware_prompt(
    *,
    decision: PolicyDecision,
    chunks: list[RetrievedChunk],
) -> str:
    instructions = _strategy_instructions(decision)
    context = _format_context(chunks)
    misconception_context = _format_private_misconception_context(decision)
    return f"""Student query:
{decision.query}

Teaching action:
{decision.selected_action}

Response strategy:
{decision.response_strategy}

Policy reason:
{decision.teaching_reason}

Learner state snapshot:
{json.dumps(decision.learner_state_snapshot, ensure_ascii=False)}

Learner state scope:
{decision.learner_state_scope}

Concept learner state snapshot:
{json.dumps(decision.concept_state_snapshot, ensure_ascii=False)}

Private misconception teaching signal:
{misconception_context}

Evidence state snapshot:
{json.dumps(decision.evidence_state_snapshot, ensure_ascii=False)}

Strategy instructions:
{instructions}

Course excerpts:
{context}

Return this exact JSON shape:
{{
  "answer_status": "answered",
  "answer": "the tutoring response",
  "claims": [
    {{
      "claim": "one factual claim",
      "source_chunk_ids": [123],
      "support_level": "fully_supported",
      "evidence_quote": "short supporting quote"
    }}
  ]
}}"""


def _strategy_instructions(decision: PolicyDecision) -> str:
    if decision.response_strategy == "contrastive":
        return (
            "- Explicitly contrast the confused concepts or objectives.\n"
            "- Name the key distinction before giving details.\n"
            "- Use a concrete discriminative example.\n"
            "- Do not simply repeat the original explanation.\n"
            "- Use only the supplied course evidence."
        )
    if decision.response_strategy == "definition_clarification":
        return (
            "- Start by correcting the mistaken definition.\n"
            "- Give the accurate definition in simple language.\n"
            "- Break down the important terms in the definition.\n"
            "- Use one short example grounded in the supplied evidence."
        )
    if decision.response_strategy == "prerequisite_scaffolded":
        return (
            "- Briefly establish the likely missing prerequisite first.\n"
            "- Then connect that prerequisite to the target concept.\n"
            "- Keep the prerequisite explanation short and source-grounded.\n"
            "- End with one check that links prerequisite to target concept."
        )
    if decision.response_strategy == "reasoning_guidance":
        return (
            "- Focus on the reasoning step the learner likely missed.\n"
            "- Ask one guiding question before revealing the conclusion.\n"
            "- Explain the chain of reasoning one step at a time.\n"
            "- Use only the supplied course evidence."
        )
    if decision.response_strategy == "source_correction":
        return (
            "- Point to the relevant source excerpt first.\n"
            "- Explain what the source actually says.\n"
            "- Identify the likely misreading without overclaiming.\n"
            "- Rephrase the source meaning in simpler language."
        )
    if (
        decision.selected_action == "explain"
        and decision.response_strategy == "scaffolded"
    ):
        return (
            "- Start with intuition.\n"
            "- Break the explanation into small steps.\n"
            "- Avoid assuming advanced prior knowledge.\n"
            "- Use only the supplied course evidence.\n"
            "- End with one short diagnostic check."
        )
    if decision.selected_action == "explain":
        return (
            "- Give a direct, compact explanation.\n"
            "- Avoid unnecessary basics.\n"
            "- Highlight the key distinction or mechanism.\n"
            "- Use only the supplied course evidence.\n"
            "- Offer a challenge question as the next step."
        )
    if decision.selected_action == "hint":
        return (
            "- Do not reveal the final answer.\n"
            "- Provide only one useful hint.\n"
            "- Encourage the learner to attempt the problem again.\n"
            "- Use the supplied evidence to guide the hint."
        )
    if decision.selected_action == "review":
        return (
            "- Produce a short review drill grounded in the supplied excerpts.\n"
            "- Focus on retrieval practice, not a full lecture.\n"
            "- Include one quick check question."
        )
    return "- Use only the supplied course evidence."


def _format_private_misconception_context(decision: PolicyDecision) -> str:
    snapshot = decision.misconception_snapshot
    if not snapshot:
        return "No recent high-confidence misconception signal."

    misconception_type = snapshot.get("misconception_type", "unknown")
    description = snapshot.get("description", "")
    return (
        f"Likely error pattern: {misconception_type}\n"
        f"Teaching implication: {description}\n"
        "Use this only to shape the tutoring response. Do not mention the "
        "internal label, confidence score, or quiz attempt ID."
    )


def _format_context(chunks: list[RetrievedChunk]) -> str:
    formatted: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        formatted.append(
            f"[S{index}] filename: {chunk.filename}; chunk_id: {chunk.chunk_id}\n"
            f"{chunk.content.strip()}"
        )
    return "\n\n".join(formatted)


def _parse_tutor_answer(text: str) -> TutorAnswerPayload:
    cleaned = _strip_markdown_fence(text)
    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMProviderError("The tutor response was not valid JSON") from exc

    try:
        return TutorAnswerPayload.model_validate(raw)
    except ValidationError as exc:
        raise LLMProviderError("The tutor response JSON failed validation") from exc


def _strip_markdown_fence(text: str) -> str:
    cleaned = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return cleaned


def _sanitize_claims(
    claims: list[TutorClaimPayload],
    *,
    valid_chunk_ids: set[int],
) -> list[TutorResponseClaim]:
    sanitized: list[TutorResponseClaim] = []
    for claim in claims:
        source_chunk_ids = [
            chunk_id
            for chunk_id in claim.source_chunk_ids
            if chunk_id in valid_chunk_ids
        ]
        support_level = claim.support_level
        if not source_chunk_ids and support_level in {
            "fully_supported",
            "partially_supported",
        }:
            support_level = "unsupported"

        sanitized.append(
            TutorResponseClaim(
                claim=claim.claim,
                source_chunk_ids=source_chunk_ids,
                support_level=support_level,
                evidence_quote=claim.evidence_quote,
            )
        )
    return sanitized


def _to_source(chunk: RetrievedChunk) -> TutorResponseSource:
    return TutorResponseSource(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        course_id=chunk.course_id,
        filename=chunk.filename,
        content=chunk.content,
        metadata=chunk.metadata,
        distance=chunk.distance,
        similarity=chunk.similarity,
    )
