from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.learner_state import LearnerStateResponse
from app.services.courses import CourseNotFoundError, validate_course_scope
from app.services.learner_state import LearnerState, compute_learner_state

router = APIRouter(prefix="/learner-state", tags=["learner-state"])


@router.get("", response_model=LearnerStateResponse)
def get_learner_state(
    user_id: str = "demo-user",
    course_id: int | None = None,
    db: Session = Depends(get_db),
) -> LearnerStateResponse:
    try:
        validate_course_scope(db=db, user_id=user_id, course_id=course_id)
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    state = compute_learner_state(db=db, user_id=user_id, course_id=course_id)
    return _to_response(state)


def _to_response(state: LearnerState) -> LearnerStateResponse:
    return LearnerStateResponse(
        user_id=state.user_id,
        course_id=state.course_id,
        mastery_score=state.mastery_score,
        recent_accuracy=state.recent_accuracy,
        attempt_count=state.attempt_count,
        consecutive_errors=state.consecutive_errors,
        last_reviewed_at=state.last_reviewed_at,
        review_due=state.review_due,
    )

