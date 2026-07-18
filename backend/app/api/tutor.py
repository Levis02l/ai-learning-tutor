from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.tutor import (
    TutorDecisionRequest,
    TutorDecisionResponse,
    TutorEvidenceStateSnapshot,
    TutorLearnerStateSnapshot,
)
from app.services.courses import CourseNotFoundError, validate_course_scope
from app.services.embeddings import EmbeddingConfigurationError
from app.services.policy import PolicyDecision, create_policy_decision

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
        learner_state_snapshot=TutorLearnerStateSnapshot(
            **decision.learner_state_snapshot
        ),
        evidence_state_snapshot=TutorEvidenceStateSnapshot(
            **decision.evidence_state_snapshot
        ),
    )
