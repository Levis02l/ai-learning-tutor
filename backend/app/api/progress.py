from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.progress import (
    CourseProgressResponse,
    ProgressConceptResponse,
    ProgressMisconceptionResponse,
    ProgressPrerequisiteResponse,
    ProgressSocraticActivityResponse,
    ProgressSummaryResponse,
)
from app.services.courses import CourseNotFoundError
from app.services.progress import CourseProgress, ProgressConcept, get_course_progress

router = APIRouter(tags=["progress"])


@router.get(
    "/courses/{course_id}/progress",
    response_model=CourseProgressResponse,
)
def get_progress(
    course_id: int,
    user_id: str = "demo-user",
    db: Session = Depends(get_db),
) -> CourseProgressResponse:
    try:
        progress = get_course_progress(
            db=db,
            user_id=user_id,
            course_id=course_id,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return _progress_response(progress)


def _progress_response(progress: CourseProgress) -> CourseProgressResponse:
    return CourseProgressResponse(
        user_id=progress.user_id,
        course_id=progress.course_id,
        summary=ProgressSummaryResponse(
            total_concepts=progress.summary.total_concepts,
            observed_concepts=progress.summary.observed_concepts,
            unobserved_concepts=progress.summary.unobserved_concepts,
            needs_attention_count=progress.summary.needs_attention_count,
            review_due_count=progress.summary.review_due_count,
            strong_count=progress.summary.strong_count,
            developing_count=progress.summary.developing_count,
            socratic_completed_count=progress.summary.socratic_completed_count,
            socratic_completion_attempt_count=(
                progress.summary.socratic_completion_attempt_count
            ),
        ),
        concepts=[_concept_response(concept) for concept in progress.concepts],
    )


def _concept_response(concept: ProgressConcept) -> ProgressConceptResponse:
    state = concept.learner_state
    return ProgressConceptResponse(
        concept_id=state.concept_id,
        concept_name=state.concept_name,
        state_status=state.state_status,
        status=concept.status,
        mastery_score=state.mastery_score,
        recent_accuracy=state.recent_accuracy,
        attempt_count=state.attempt_count,
        consecutive_errors=state.consecutive_errors,
        last_attempted_at=state.last_attempted_at,
        review_due=state.review_due,
        needs_attention=state.needs_attention,
        attention_reasons=concept.attention_reasons,
        latest_misconception=(
            ProgressMisconceptionResponse(
                id=concept.latest_misconception.id,
                misconception_type=concept.latest_misconception.misconception_type,
                description=concept.latest_misconception.description,
                confidence=concept.latest_misconception.confidence,
                quiz_attempt_id=concept.latest_misconception.quiz_attempt_id,
                created_at=concept.latest_misconception.created_at,
            )
            if concept.latest_misconception
            else None
        ),
        prerequisites=[
            ProgressPrerequisiteResponse(
                id=prerequisite.id,
                name=prerequisite.name,
                confidence=prerequisite.confidence,
            )
            for prerequisite in concept.prerequisites
        ],
        socratic_activity=ProgressSocraticActivityResponse(
            completed_sessions=concept.socratic_activity.completed_sessions,
            completion_attempts=concept.socratic_activity.completion_attempts,
            latest_session_id=concept.socratic_activity.latest_session_id,
            latest_completed_at=concept.socratic_activity.latest_completed_at,
            latest_completion_quiz_item_id=(
                concept.socratic_activity.latest_completion_quiz_item_id
            ),
            latest_completion_quiz_attempt_id=(
                concept.socratic_activity.latest_completion_quiz_attempt_id
            ),
            latest_completion_correct=(
                concept.socratic_activity.latest_completion_correct
            ),
        ),
    )
