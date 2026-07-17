import json
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import LLMProvider, LLMProviderError
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
    course_id: int | None = None


AnswerStatus = Literal[
    "answered",
    "partially_answered",
    "refused_no_evidence",
    "refused_ambiguous_material",
    "needs_more_material",
]
SupportLevel = Literal[
    "fully_supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "not_enough_information",
]


@dataclass(frozen=True)
class RagClaim:
    claim: str
    source_chunk_ids: list[int]
    support_level: SupportLevel
    evidence_quote: str


@dataclass(frozen=True)
class RagAnswer:
    mode: str
    answer_status: AnswerStatus
    answer: str
    claims: list[RagClaim]
    overall_groundedness: float
    sources: list[RagSource]


@dataclass(frozen=True)
class RagComparison:
    grounded: RagAnswer
    ungrounded: RagAnswer


class EvidenceClaimPayload(BaseModel):
    claim: str = Field(..., min_length=1)
    source_chunk_ids: list[int] = Field(default_factory=list)
    support_level: SupportLevel
    evidence_quote: str = ""


class EvidenceAnswerPayload(BaseModel):
    answer_status: AnswerStatus
    answer: str = Field(..., min_length=1)
    claims: list[EvidenceClaimPayload] = Field(default_factory=list)


SYSTEM_PROMPT = (
    "You are an AI learning tutor for a student's uploaded course materials.\n"
    "Answer only using the provided source excerpts.\n"
    "Return valid JSON only. Do not include markdown fences or commentary.\n"
    "Use the same language as the student's question when possible.\n"
    "For each factual claim, provide source_chunk_ids, a support_level, and "
    "a short evidence_quote copied or closely paraphrased from the source.\n"
    "Allowed support_level values: fully_supported, partially_supported, "
    "unsupported, contradicted, not_enough_information.\n"
    "If the sources do not contain enough evidence, set answer_status to "
    "refused_no_evidence or needs_more_material and explain the limitation."
)

UNGROUNDED_SYSTEM_PROMPT = (
    "You are an AI learning tutor answering from general model knowledge.\n"
    "Do not use uploaded course material or citations.\n"
    "Return valid JSON only. Do not include markdown fences or commentary.\n"
    "Use the same language as the student's question when possible.\n"
    "For each factual claim, include the claim text. Since no source evidence "
    "is provided, use an empty source_chunk_ids list and support_level "
    '"unsupported".'
)


def answer_question(
    db: Session,
    query: str,
    user_id: str = "demo-user",
    top_k: int = 5,
    course_id: int | None = None,
    llm_provider: LLMProvider | None = None,
) -> RagAnswer:
    chunks = retrieve_relevant_chunks(
        db=db,
        query=query,
        user_id=user_id,
        top_k=top_k,
        course_id=course_id,
    )
    sources = [_to_rag_source(chunk) for chunk in chunks]

    if not chunks:
        return RagAnswer(
            mode="grounded_strict",
            answer_status="refused_no_evidence",
            answer=(
                "The uploaded materials do not contain enough information "
                "to answer this question."
            ),
            claims=[],
            overall_groundedness=0.0,
            sources=[],
        )

    provider = llm_provider or OpenAIProvider()
    response = provider.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=_build_user_prompt(query=query, chunks=chunks),
        max_tokens=1200,
        temperature=0.2,
    )
    payload = _parse_evidence_answer(response.text)
    claims = _sanitize_claims(
        payload.claims,
        valid_chunk_ids={chunk.chunk_id for chunk in chunks},
    )

    return RagAnswer(
        mode="grounded_strict",
        answer_status=payload.answer_status,
        answer=payload.answer,
        claims=claims,
        overall_groundedness=_calculate_groundedness(claims),
        sources=sources,
    )


def answer_question_ungrounded(
    query: str,
    llm_provider: LLMProvider | None = None,
) -> RagAnswer:
    provider = llm_provider or OpenAIProvider()
    response = provider.generate(
        system_prompt=UNGROUNDED_SYSTEM_PROMPT,
        user_prompt=_build_ungrounded_prompt(query=query),
        max_tokens=1000,
        temperature=0.2,
    )
    payload = _parse_evidence_answer(response.text)
    claims = _sanitize_claims(payload.claims, valid_chunk_ids=set())

    return RagAnswer(
        mode="ungrounded",
        answer_status=payload.answer_status,
        answer=payload.answer,
        claims=claims,
        overall_groundedness=_calculate_groundedness(claims),
        sources=[],
    )


def compare_answers(
    db: Session,
    *,
    query: str,
    user_id: str = "demo-user",
    top_k: int = 5,
    course_id: int | None = None,
    llm_provider: LLMProvider | None = None,
) -> RagComparison:
    provider = llm_provider or OpenAIProvider()
    grounded = answer_question(
        db=db,
        query=query,
        user_id=user_id,
        top_k=top_k,
        course_id=course_id,
        llm_provider=provider,
    )
    ungrounded = answer_question_ungrounded(query=query, llm_provider=provider)

    return RagComparison(grounded=grounded, ungrounded=ungrounded)


def _to_rag_source(chunk: RetrievedChunk) -> RagSource:
    return RagSource(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        course_id=chunk.course_id,
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

Return this exact JSON shape:
{{
  "answer_status": "answered",
  "answer": "clear learning-focused answer with inline references like [S1]",
  "claims": [
    {{
      "claim": "one factual claim from the answer",
      "source_chunk_ids": [123],
      "support_level": "fully_supported",
      "evidence_quote": "short evidence quote from the source"
    }}
  ]
}}

If evidence is insufficient, do not invent an answer. Use answer_status
"refused_no_evidence", "partially_answered", or "needs_more_material"."""


def _build_ungrounded_prompt(query: str) -> str:
    return f"""Student question:
{query}

Return this exact JSON shape:
{{
  "answer_status": "answered",
  "answer": "clear learning-focused answer without citations",
  "claims": [
    {{
      "claim": "one factual claim from the answer",
      "source_chunk_ids": [],
      "support_level": "unsupported",
      "evidence_quote": ""
    }}
  ]
}}"""


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


def _parse_evidence_answer(text: str) -> EvidenceAnswerPayload:
    cleaned = _strip_markdown_fence(text)
    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMProviderError("The model did not return valid evidence JSON") from exc

    try:
        return EvidenceAnswerPayload.model_validate(raw)
    except ValidationError as exc:
        raise LLMProviderError("The evidence answer JSON failed validation") from exc


def _strip_markdown_fence(text: str) -> str:
    cleaned = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return cleaned


def _sanitize_claims(
    claims: list[EvidenceClaimPayload],
    *,
    valid_chunk_ids: set[int],
) -> list[RagClaim]:
    sanitized: list[RagClaim] = []
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
            RagClaim(
                claim=claim.claim,
                source_chunk_ids=source_chunk_ids,
                support_level=support_level,
                evidence_quote=claim.evidence_quote,
            )
        )

    return sanitized


def _calculate_groundedness(claims: list[RagClaim]) -> float:
    if not claims:
        return 0.0

    support_scores = {
        "fully_supported": 1.0,
        "partially_supported": 0.5,
        "unsupported": 0.0,
        "contradicted": 0.0,
        "not_enough_information": 0.0,
    }
    return round(
        sum(support_scores[claim.support_level] for claim in claims) / len(claims),
        3,
    )
