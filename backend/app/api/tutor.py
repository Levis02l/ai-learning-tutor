from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.quiz import _to_response as quiz_to_response
from app.api.reviews import _review_to_response
from app.db import get_db
from app.llm.provider import LLMConfigurationError, LLMProviderError
from app.schemas.chat import ChatClaim, ChatSource
from app.schemas.review import DueReviewItemResponse
from app.schemas.tutor import (
    TutorConceptLearnerStateSnapshot,
    TutorDecisionRequest,
    TutorDecisionResponse,
    TutorEvidenceStateSnapshot,
    TutorLearnerStateSnapshot,
    TutorOutcomeRequest,
    TutorOutcomeResponse,
    TutorResponseRequest,
    TutorResponseResponse,
)
from app.services.courses import CourseNotFoundError, validate_course_scope
from app.services.embeddings import EmbeddingConfigurationError
from app.services.policy import PolicyDecision, create_policy_decision
from app.services.quiz import QuizGenerationError
from app.services.tutor_outcome import (
    TutorOutcomeCompatibilityError,
    TutorOutcomeNotFoundError,
    TutorOutcomeScopeError,
    record_tutor_outcome,
)
from app.services.tutor_response import TutorResponse, create_tutor_response

router = APIRouter(prefix="/tutor", tags=["tutor"])


@router.post("/decide", response_model=TutorDecisionResponse)
def decide_tutor_action(
    request: TutorDecisionRequest,
    db: Session = Depends(get_db),
) -> TutorDecisionResponse:
    try:
        validate_course_scope(
            db=db,
            user_id=request.user_id,
            course_id=request.course_id,
        )
        decision = create_policy_decision(
            db=db,
            query=request.query,
            user_id=request.user_id,
            course_id=request.course_id,
            top_k=request.top_k,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    return _to_response(decision)


@router.post("/respond", response_model=TutorResponseResponse)
def respond_as_tutor(
    request: TutorResponseRequest,
    db: Session = Depends(get_db),
) -> TutorResponseResponse:
    try:
        validate_course_scope(
            db=db,
            user_id=request.user_id,
            course_id=request.course_id,
        )
        response = create_tutor_response(
            db=db,
            query=request.query,
            user_id=request.user_id,
            course_id=request.course_id,
            top_k=request.top_k,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (EmbeddingConfigurationError, LLMConfigurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except (LLMProviderError, QuizGenerationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )

    return _to_tutor_response(response)


@router.post(
    "/decisions/{decision_id}/outcome",
    response_model=TutorOutcomeResponse,
)
def link_tutor_outcome(
    decision_id: int,
    request: TutorOutcomeRequest,
    db: Session = Depends(get_db),
) -> TutorOutcomeResponse:
    try:
        outcome = record_tutor_outcome(
            db=db,
            decision_id=decision_id,
            outcome_type=request.outcome_type,
            quiz_attempt_id=request.quiz_attempt_id,
            review_record_id=request.review_record_id,
        )
    except TutorOutcomeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (TutorOutcomeCompatibilityError, TutorOutcomeScopeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )

    return TutorOutcomeResponse(decision_id=decision_id, outcome=outcome)


def _to_response(decision: PolicyDecision) -> TutorDecisionResponse:
    if decision.decision_id is None:
        raise ValueError("Logged tutor decisions must have a decision_id")

    return TutorDecisionResponse(
        decision_id=decision.decision_id,
        user_id=decision.user_id,
        course_id=decision.course_id,
        query=decision.query,
        detected_intent=decision.detected_intent,
        selected_action=decision.selected_action,
        response_strategy=decision.response_strategy,
        primary_reason=decision.primary_reason,
        teaching_reason=decision.teaching_reason,
        suggested_next_step=decision.suggested_next_step,
        policy_version=decision.policy_version,
        learner_state_scope=decision.learner_state_scope,
        learner_state_snapshot=TutorLearnerStateSnapshot(
            **decision.learner_state_snapshot
        ),
        concept_state_snapshot=(
            TutorConceptLearnerStateSnapshot(**decision.concept_state_snapshot)
            if decision.concept_state_snapshot
            else None
        ),
        evidence_state_snapshot=TutorEvidenceStateSnapshot(
            **decision.evidence_state_snapshot
        ),
    )


def _to_tutor_response(response: TutorResponse) -> TutorResponseResponse:
    return TutorResponseResponse(
        decision=_to_response(response.decision),
        answer_status=response.answer_status,
        answer=response.answer,
        claims=[
            ChatClaim(
                claim=claim.claim,
                source_chunk_ids=claim.source_chunk_ids,
                support_level=claim.support_level,
                evidence_quote=claim.evidence_quote,
            )
            for claim in response.claims
        ],
        sources=[
            ChatSource(
                chunk_id=source.chunk_id,
                document_id=source.document_id,
                course_id=source.course_id,
                filename=source.filename,
                content=source.content,
                metadata=source.metadata,
                distance=source.distance,
                similarity=source.similarity,
            )
            for source in response.sources
        ],
        quiz_items=[quiz_to_response(item) for item in response.quiz_items],
        review_items=[
            DueReviewItemResponse(
                item=quiz_to_response(item),
                latest_review=_review_to_response(review) if review else None,
            )
            for item, review in response.review_items
        ],
        suggested_next_step=response.suggested_next_step,
    )
