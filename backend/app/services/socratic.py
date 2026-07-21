import json
import re
from datetime import datetime
from typing import Literal, cast

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import LLMProvider, LLMProviderError
from app.models.document import Chunk, Document
from app.models.policy import PolicyDecisionRecord
from app.models.quiz import QuizAttempt, QuizItem
from app.models.socratic import SocraticSession, SocraticTurn
from app.services.policy import (
    POLICY_VERSION,
    DetectedIntent,
    LearnerStateScope,
    PolicyDecision,
    ResponseStrategy,
    TeachingAction,
    create_policy_decision,
)
from app.services.quiz import (
    generate_quiz_items_from_chunks,
    submit_quiz_attempt,
)
from app.services.retrieval import RetrievedChunk

SocraticStage = Literal[
    "diagnostic",
    "hint_1",
    "hint_2",
    "final_explanation",
    "grounded_summary",
]
SocraticAssessment = Literal[
    "correct",
    "partially_correct",
    "incorrect",
    "off_topic",
]

SYSTEM_PROMPT = (
    "You are running a bounded Socratic tutoring session.\n"
    "Use only the frozen course evidence supplied by the backend.\n"
    "Treat learner-state and misconception metadata as private teaching signals. "
    "Do not reveal internal labels, confidence scores, JSON fields, policy names, "
    "or quiz attempt IDs to the learner.\n"
    "Return valid JSON only. Do not include markdown fences or commentary."
)


class SocraticSessionError(RuntimeError):
    pass


class SocraticSessionNotFoundError(RuntimeError):
    pass


class SocraticSessionClosedError(RuntimeError):
    pass


class SocraticMessagePayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=1200)


class SocraticAssessmentPayload(BaseModel):
    assessment: SocraticAssessment
    assessment_reason: str = Field(..., min_length=1, max_length=600)


def start_socratic_session(
    db: Session,
    *,
    query: str,
    user_id: str = "demo-user",
    course_id: int | None = None,
    source_policy_decision_id: int | None = None,
    top_k: int = 5,
    max_turns: int = 3,
    llm_provider: LLMProvider | None = None,
) -> SocraticSession:
    if max_turns < 1 or max_turns > 3:
        raise SocraticSessionError("Socratic sessions support 1 to 3 learner attempts")

    decision = _resolve_source_decision(
        db=db,
        query=query,
        user_id=user_id,
        course_id=course_id,
        source_policy_decision_id=source_policy_decision_id,
        top_k=top_k,
    )
    _validate_socratic_decision(decision)
    evidence_chunks = decision.evidence_chunks or _load_decision_evidence_chunks(
        db=db,
        decision=decision,
    )
    if not evidence_chunks:
        raise SocraticSessionError("Socratic sessions require frozen course evidence")

    concept_snapshot = decision.concept_state_snapshot
    assert concept_snapshot is not None
    provider = llm_provider or OpenAIProvider()
    diagnostic_message = _generate_tutor_message(
        provider=provider,
        stage="diagnostic",
        query=query,
        learner_attempt_count=0,
        learner_answer=None,
        assessment=None,
        assessment_reason=None,
        learner_state_snapshot=decision.learner_state_snapshot,
        concept_snapshot=concept_snapshot,
        misconception_snapshot=decision.misconception_snapshot,
        evidence_state_snapshot=decision.evidence_state_snapshot,
        evidence_chunks=evidence_chunks,
    )
    session = SocraticSession(
        user_id=user_id,
        course_id=decision.course_id,
        concept_id=concept_snapshot["concept_id"],
        source_policy_decision_id=decision.decision_id,
        query=query,
        status="active",
        current_stage="diagnostic",
        turn_count=0,
        max_turns=max_turns,
        learner_state_snapshot=decision.learner_state_snapshot,
        concept_snapshot=concept_snapshot,
        misconception_snapshot=decision.misconception_snapshot,
        evidence_state_snapshot=decision.evidence_state_snapshot,
        evidence_chunks_snapshot=_evidence_chunk_snapshots(evidence_chunks),
    )
    session.turns.append(
        SocraticTurn(
            turn_number=1,
            stage="diagnostic",
            tutor_message=diagnostic_message,
        )
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def respond_to_socratic_session(
    db: Session,
    *,
    session_id: int,
    answer: str,
    user_id: str = "demo-user",
    course_id: int | None = None,
    llm_provider: LLMProvider | None = None,
) -> SocraticSession:
    session = get_socratic_session(
        db=db,
        session_id=session_id,
        user_id=user_id,
        course_id=course_id,
    )
    if session.status != "active":
        raise SocraticSessionClosedError("Socratic session is already closed")

    current_turn = _latest_turn(session)
    if current_turn.student_response is not None:
        raise SocraticSessionError("Socratic session is not waiting for an answer")

    provider = llm_provider or OpenAIProvider()
    assessment = _assess_student_response(
        provider=provider,
        session=session,
        current_turn=current_turn,
        answer=answer,
    )
    current_turn.student_response = answer
    current_turn.assessment = assessment.assessment
    current_turn.assessment_reason = assessment.assessment_reason
    session.turn_count += 1

    next_stage, completed = _next_stage(
        current_stage=cast(SocraticStage, current_turn.stage),
        assessment=assessment.assessment,
        turn_count=session.turn_count,
        max_turns=session.max_turns,
    )
    next_message = _generate_tutor_message(
        provider=provider,
        stage=next_stage,
        query=session.query,
        learner_attempt_count=session.turn_count,
        learner_answer=answer,
        assessment=assessment.assessment,
        assessment_reason=assessment.assessment_reason,
        learner_state_snapshot=session.learner_state_snapshot,
        concept_snapshot=session.concept_snapshot or {},
        misconception_snapshot=session.misconception_snapshot,
        evidence_state_snapshot=session.evidence_state_snapshot,
        evidence_chunks=_retrieved_chunks_from_snapshot(
            session.evidence_chunks_snapshot
        ),
    )

    session.current_stage = next_stage
    if completed:
        session.status = "completed"
        session.completed_at = datetime.utcnow()

    session.turns.append(
        SocraticTurn(
            turn_number=len(session.turns) + 1,
            stage=next_stage,
            tutor_message=next_message,
        )
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def generate_socratic_completion_check(
    db: Session,
    *,
    session_id: int,
    user_id: str = "demo-user",
    course_id: int | None = None,
    llm_provider: LLMProvider | None = None,
) -> tuple[SocraticSession, QuizItem]:
    session = get_socratic_session(
        db=db,
        session_id=session_id,
        user_id=user_id,
        course_id=course_id,
    )
    _validate_completion_check_session(session)

    existing_item = _load_existing_completion_check(db=db, session=session)
    if existing_item is not None:
        return session, existing_item

    evidence_chunks = _retrieved_chunks_from_snapshot(
        session.evidence_chunks_snapshot
    )
    if not evidence_chunks:
        raise SocraticSessionError(
            "Socratic completion checks require frozen course evidence"
        )

    concept_name = _session_concept_name(session)
    items = generate_quiz_items_from_chunks(
        db=db,
        topic=f"Socratic completion check for {concept_name}: {session.query}",
        user_id=session.user_id,
        course_id=session.course_id,
        concept_id=session.concept_id,
        chunks=evidence_chunks,
        count=1,
        difficulty="medium",
        origin="socratic_completion_check",
        require_traceable=True,
        llm_provider=llm_provider,
    )
    item = items[0]
    session.completion_quiz_item_id = item.id
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, item


def submit_socratic_completion_attempt(
    db: Session,
    *,
    session_id: int,
    selected_option_id: str,
    user_id: str = "demo-user",
    course_id: int | None = None,
) -> tuple[SocraticSession, QuizAttempt]:
    session = get_socratic_session(
        db=db,
        session_id=session_id,
        user_id=user_id,
        course_id=course_id,
    )
    _validate_completion_check_session(session)
    if session.completion_quiz_item_id is None:
        raise SocraticSessionError("No Socratic completion check has been created")

    existing_attempt = _load_existing_completion_attempt(db=db, session=session)
    if existing_attempt is not None:
        return session, existing_attempt

    attempt = submit_quiz_attempt(
        db=db,
        user_id=session.user_id,
        course_id=session.course_id,
        quiz_item_id=session.completion_quiz_item_id,
        selected_option_id=selected_option_id,
    )
    session.completion_quiz_attempt_id = attempt.id
    db.add(session)
    db.commit()
    db.refresh(session)
    db.refresh(attempt)
    return session, attempt


def get_socratic_session(
    db: Session,
    *,
    session_id: int,
    user_id: str = "demo-user",
    course_id: int | None = None,
) -> SocraticSession:
    query = select(SocraticSession).where(
        SocraticSession.id == session_id,
        SocraticSession.user_id == user_id,
    )
    if course_id is not None:
        query = query.where(SocraticSession.course_id == course_id)

    session = db.scalar(query)
    if session is None:
        raise SocraticSessionNotFoundError("Socratic session not found")
    return session


def _resolve_source_decision(
    *,
    db: Session,
    query: str,
    user_id: str,
    course_id: int | None,
    source_policy_decision_id: int | None,
    top_k: int,
) -> PolicyDecision:
    if source_policy_decision_id is None:
        return create_policy_decision(
            db=db,
            query=query,
            user_id=user_id,
            course_id=course_id,
            top_k=top_k,
        )

    record_query = select(PolicyDecisionRecord).where(
        PolicyDecisionRecord.id == source_policy_decision_id,
        PolicyDecisionRecord.user_id == user_id,
    )
    if course_id is not None:
        record_query = record_query.where(PolicyDecisionRecord.course_id == course_id)

    record = db.scalar(record_query)
    if record is None:
        raise SocraticSessionNotFoundError("Source policy decision not found")

    decision = _decision_from_record(record)
    return PolicyDecision(
        decision_id=decision.decision_id,
        user_id=decision.user_id,
        course_id=decision.course_id,
        query=query or decision.query,
        detected_intent=decision.detected_intent,
        selected_action=decision.selected_action,
        response_strategy=decision.response_strategy,
        primary_reason=decision.primary_reason,
        teaching_reason=decision.teaching_reason,
        suggested_next_step=decision.suggested_next_step,
        policy_version=decision.policy_version,
        learner_state_snapshot=decision.learner_state_snapshot,
        evidence_state_snapshot=decision.evidence_state_snapshot,
        learner_state_scope=decision.learner_state_scope,
        concept_state_snapshot=decision.concept_state_snapshot,
        misconception_snapshot=decision.misconception_snapshot,
        evidence_chunks=_load_decision_evidence_chunks(db=db, decision=decision),
    )


def _decision_from_record(record: PolicyDecisionRecord) -> PolicyDecision:
    return PolicyDecision(
        decision_id=record.id,
        user_id=record.user_id,
        course_id=record.course_id,
        query=record.query,
        detected_intent=cast(DetectedIntent, record.detected_intent),
        selected_action=cast(TeachingAction, record.selected_action),
        response_strategy=cast(ResponseStrategy, record.response_strategy),
        primary_reason=record.primary_reason,
        teaching_reason=record.teaching_reason,
        suggested_next_step=record.suggested_next_step,
        policy_version=record.policy_version or POLICY_VERSION,
        learner_state_snapshot=record.learner_state_snapshot,
        evidence_state_snapshot=record.evidence_state_snapshot,
        learner_state_scope=cast(LearnerStateScope, record.learner_state_scope),
        concept_state_snapshot=record.concept_state_snapshot,
        misconception_snapshot=record.misconception_snapshot,
        evidence_chunks=[],
    )


def _validate_socratic_decision(decision: PolicyDecision) -> None:
    if decision.selected_action == "refuse":
        raise SocraticSessionError("Cannot start Socratic mode without evidence")
    if decision.concept_state_snapshot is None:
        raise SocraticSessionError("Socratic mode requires a resolved concept")
    if decision.evidence_state_snapshot.get("evidence_strength") in {
        "insufficient",
        "not_required",
    }:
        raise SocraticSessionError("Socratic mode requires grounded course evidence")


def _validate_completion_check_session(session: SocraticSession) -> None:
    if session.status != "completed":
        raise SocraticSessionError(
            "Socratic completion checks require a completed session"
        )
    if session.concept_id is None:
        raise SocraticSessionError(
            "Socratic completion checks require a resolved concept"
        )
    if not session.evidence_chunks_snapshot:
        raise SocraticSessionError(
            "Socratic completion checks require frozen course evidence"
        )


def _load_existing_completion_check(
    *,
    db: Session,
    session: SocraticSession,
) -> QuizItem | None:
    if session.completion_quiz_item_id is None:
        return None
    item = db.get(QuizItem, session.completion_quiz_item_id)
    if item is None:
        session.completion_quiz_item_id = None
        return None
    return item


def _load_existing_completion_attempt(
    *,
    db: Session,
    session: SocraticSession,
) -> QuizAttempt | None:
    if session.completion_quiz_attempt_id is None:
        return None
    attempt = db.get(QuizAttempt, session.completion_quiz_attempt_id)
    if attempt is None:
        session.completion_quiz_attempt_id = None
        return None
    return attempt


def _session_concept_name(session: SocraticSession) -> str:
    snapshot = session.concept_snapshot or {}
    return str(snapshot.get("concept_name") or f"concept {session.concept_id}")


def _load_decision_evidence_chunks(
    *,
    db: Session,
    decision: PolicyDecision,
) -> list[RetrievedChunk]:
    source_ids = [
        int(chunk_id)
        for chunk_id in decision.evidence_state_snapshot.get("source_chunk_ids", [])
    ]
    if not source_ids:
        return []

    query = (
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.id.in_(source_ids), Document.user_id == decision.user_id)
    )
    if decision.course_id is not None:
        query = query.where(Document.course_id == decision.course_id)

    rows = db.execute(query).all()
    by_id = {
        chunk.id: RetrievedChunk(
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
    }
    return [by_id[chunk_id] for chunk_id in source_ids if chunk_id in by_id]


def _assess_student_response(
    *,
    provider: LLMProvider,
    session: SocraticSession,
    current_turn: SocraticTurn,
    answer: str,
) -> SocraticAssessmentPayload:
    response = provider.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=_build_assessment_prompt(
            session=session,
            current_turn=current_turn,
            answer=answer,
        ),
        max_tokens=500,
        temperature=0.0,
    )
    return _parse_assessment(response.text)


def _generate_tutor_message(
    *,
    provider: LLMProvider,
    stage: SocraticStage,
    query: str,
    learner_attempt_count: int,
    learner_answer: str | None,
    assessment: SocraticAssessment | None,
    assessment_reason: str | None,
    learner_state_snapshot: dict,
    concept_snapshot: dict,
    misconception_snapshot: dict | None,
    evidence_state_snapshot: dict,
    evidence_chunks: list[RetrievedChunk],
) -> str:
    response = provider.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=_build_message_prompt(
            stage=stage,
            query=query,
            learner_attempt_count=learner_attempt_count,
            learner_answer=learner_answer,
            assessment=assessment,
            assessment_reason=assessment_reason,
            learner_state_snapshot=learner_state_snapshot,
            concept_snapshot=concept_snapshot,
            misconception_snapshot=misconception_snapshot,
            evidence_state_snapshot=evidence_state_snapshot,
            evidence_chunks=evidence_chunks,
        ),
        max_tokens=650,
        temperature=0.2,
    )
    return _parse_message(response.text).message


def _build_assessment_prompt(
    *,
    session: SocraticSession,
    current_turn: SocraticTurn,
    answer: str,
) -> str:
    return f"""Assess the learner's answer to the current Socratic prompt.

Concept snapshot:
{json.dumps(session.concept_snapshot, ensure_ascii=False)}

Private misconception signal:
{_format_private_misconception(session.misconception_snapshot)}

Frozen evidence:
{_format_frozen_context(_retrieved_chunks_from_snapshot(session.evidence_chunks_snapshot))}

Tutor prompt:
{current_turn.tutor_message}

Learner answer:
{answer}

Return this exact JSON shape:
{{
  "assessment": "correct",
  "assessment_reason": "one concise reason grounded in the evidence"
}}

Allowed assessment values: correct, partially_correct, incorrect, off_topic."""


def _build_message_prompt(
    *,
    stage: SocraticStage,
    query: str,
    learner_attempt_count: int,
    learner_answer: str | None,
    assessment: SocraticAssessment | None,
    assessment_reason: str | None,
    learner_state_snapshot: dict,
    concept_snapshot: dict,
    misconception_snapshot: dict | None,
    evidence_state_snapshot: dict,
    evidence_chunks: list[RetrievedChunk],
) -> str:
    return f"""Generate the next tutor message for a bounded Socratic session.

Original learner request:
{query}

Current stage:
{stage}

Learner attempts used:
{learner_attempt_count}

Learner state snapshot:
{json.dumps(learner_state_snapshot, ensure_ascii=False)}

Concept snapshot:
{json.dumps(concept_snapshot, ensure_ascii=False)}

Private misconception signal:
{_format_private_misconception(misconception_snapshot)}

Evidence state snapshot:
{json.dumps(evidence_state_snapshot, ensure_ascii=False)}

Previous learner answer:
{learner_answer or "No learner answer yet."}

Assessment:
{assessment or "not_applicable"}

Assessment reason:
{assessment_reason or "not_applicable"}

Stage instructions:
{_stage_instructions(stage, misconception_snapshot)}

Frozen course excerpts:
{_format_frozen_context(evidence_chunks)}

Return this exact JSON shape:
{{
  "message": "the next Socratic tutor message"
}}"""


def _stage_instructions(
    stage: SocraticStage,
    misconception_snapshot: dict | None,
) -> str:
    misconception_type = (
        misconception_snapshot or {}
    ).get("misconception_type", "unknown")
    if stage == "diagnostic":
        return _diagnostic_instruction(str(misconception_type))
    if stage == "hint_1":
        return (
            "- Give one targeted hint, not the full answer.\n"
            "- Ask the learner to try again.\n"
            "- Keep it grounded in the frozen evidence."
        )
    if stage == "hint_2":
        return (
            "- Give a stronger hint than hint_1.\n"
            "- Reveal one key term or relationship from the evidence.\n"
            "- Still ask the learner to complete the reasoning."
        )
    if stage == "grounded_summary":
        return (
            "- Confirm the learner's answer briefly.\n"
            "- Summarise the key concept using the evidence.\n"
            "- End the session cleanly without asking another question."
        )
    return (
        "- Provide the final grounded explanation.\n"
        "- Explain the correct idea directly using the frozen evidence.\n"
        "- End the session cleanly without asking another question."
    )


def _diagnostic_instruction(misconception_type: str) -> str:
    if misconception_type == "concept_confusion":
        return (
            "- Ask a discriminative question that separates the confused concepts.\n"
            "- Do not reveal the answer yet."
        )
    if misconception_type == "incorrect_definition":
        return "- Ask the learner to define the target concept in their own words."
    if misconception_type == "missing_prerequisite":
        return "- Ask a short question that checks the likely prerequisite first."
    if misconception_type == "incomplete_reasoning":
        return "- Ask for the next reasoning step, not a definition."
    if misconception_type == "source_misinterpretation":
        return (
            "- Refer to one supplied source excerpt and ask what a key phrase means."
        )
    return "- Ask one focused diagnostic question about the target concept."


def _next_stage(
    *,
    current_stage: SocraticStage,
    assessment: SocraticAssessment,
    turn_count: int,
    max_turns: int,
) -> tuple[SocraticStage, bool]:
    if assessment == "correct":
        return "grounded_summary", True
    if turn_count >= max_turns:
        return "final_explanation", True
    if current_stage == "diagnostic":
        return "hint_1", False
    if current_stage == "hint_1":
        return "hint_2", False
    return "final_explanation", True


def _latest_turn(session: SocraticSession) -> SocraticTurn:
    if not session.turns:
        raise SocraticSessionError("Socratic session has no turns")
    return session.turns[-1]


def _parse_message(text: str) -> SocraticMessagePayload:
    cleaned = _strip_markdown_fence(text)
    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMProviderError("The Socratic message was not valid JSON") from exc

    try:
        return SocraticMessagePayload.model_validate(raw)
    except ValidationError as exc:
        raise LLMProviderError("The Socratic message JSON failed validation") from exc


def _parse_assessment(text: str) -> SocraticAssessmentPayload:
    cleaned = _strip_markdown_fence(text)
    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMProviderError("The Socratic assessment was not valid JSON") from exc

    try:
        return SocraticAssessmentPayload.model_validate(raw)
    except ValidationError as exc:
        raise LLMProviderError(
            "The Socratic assessment JSON failed validation"
        ) from exc


def _strip_markdown_fence(text: str) -> str:
    cleaned = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return cleaned


def _evidence_chunk_snapshots(chunks: list[RetrievedChunk]) -> list[dict]:
    return [
        {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "course_id": chunk.course_id,
            "filename": chunk.filename,
            "content": chunk.content,
            "metadata": chunk.metadata,
            "distance": chunk.distance,
            "similarity": chunk.similarity,
        }
        for chunk in chunks
    ]


def _retrieved_chunks_from_snapshot(snapshot: list[dict]) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id=int(chunk["chunk_id"]),
            document_id=int(chunk["document_id"]),
            course_id=chunk.get("course_id"),
            filename=str(chunk.get("filename", "")),
            content=str(chunk.get("content", "")),
            metadata=chunk.get("metadata") or {},
            distance=float(chunk.get("distance", 0.0)),
            similarity=float(chunk.get("similarity", 1.0)),
        )
        for chunk in snapshot
    ]


def _format_frozen_context(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"[chunk_id={chunk.chunk_id}] {chunk.content.strip()}" for chunk in chunks
    )


def _format_private_misconception(snapshot: dict | None) -> str:
    if not snapshot:
        return "No recent high-confidence misconception signal."
    return (
        f"Likely error pattern: {snapshot.get('misconception_type', 'unknown')}\n"
        f"Teaching implication: {snapshot.get('description', '')}\n"
        "Use this only to shape the Socratic prompt. Do not mention internal "
        "labels, confidence scores, or attempt IDs."
    )
