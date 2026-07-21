from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.quiz import (
    _attempt_to_response as quiz_attempt_to_response,
)
from app.api.quiz import (
    _to_response as quiz_to_response,
)
from app.db import get_db
from app.llm.provider import LLMConfigurationError, LLMProviderError
from app.schemas.socratic import (
    SocraticAssessment,
    SocraticCompletionAttemptRequest,
    SocraticCompletionAttemptResponse,
    SocraticCompletionCheckResponse,
    SocraticRespondRequest,
    SocraticSessionResponse,
    SocraticStage,
    SocraticStartRequest,
    SocraticStatus,
    SocraticTurnResponse,
)
from app.services.courses import CourseNotFoundError, validate_course_scope
from app.services.embeddings import EmbeddingConfigurationError
from app.services.quiz import QuizAttemptError, QuizGenerationError
from app.services.socratic import (
    SocraticSessionClosedError,
    SocraticSessionError,
    SocraticSessionNotFoundError,
    generate_socratic_completion_check,
    get_socratic_session,
    respond_to_socratic_session,
    start_socratic_session,
    submit_socratic_completion_attempt,
)

router = APIRouter(prefix="/tutor/socratic", tags=["socratic"])


@router.post("/start", response_model=SocraticSessionResponse)
def start_socratic(
    request: SocraticStartRequest,
    db: Session = Depends(get_db),
) -> SocraticSessionResponse:
    try:
        validate_course_scope(
            db=db,
            user_id=request.user_id,
            course_id=request.course_id,
        )
        session = start_socratic_session(
            db=db,
            query=request.query,
            user_id=request.user_id,
            course_id=request.course_id,
            source_policy_decision_id=request.source_policy_decision_id,
            top_k=request.top_k,
            max_turns=request.max_turns,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (EmbeddingConfigurationError, LLMConfigurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except SocraticSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SocraticSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )

    return _to_response(session)


@router.post("/{session_id}/respond", response_model=SocraticSessionResponse)
def respond_socratic(
    session_id: int,
    request: SocraticRespondRequest,
    db: Session = Depends(get_db),
) -> SocraticSessionResponse:
    try:
        validate_course_scope(
            db=db,
            user_id=request.user_id,
            course_id=request.course_id,
        )
        session = respond_to_socratic_session(
            db=db,
            session_id=session_id,
            answer=request.answer,
            user_id=request.user_id,
            course_id=request.course_id,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except SocraticSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SocraticSessionClosedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except SocraticSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )

    return _to_response(session)


@router.post(
    "/{session_id}/completion-check",
    response_model=SocraticCompletionCheckResponse,
)
def create_socratic_completion_check(
    session_id: int,
    user_id: str = "demo-user",
    course_id: int | None = None,
    db: Session = Depends(get_db),
) -> SocraticCompletionCheckResponse:
    try:
        validate_course_scope(db=db, user_id=user_id, course_id=course_id)
        session, item = generate_socratic_completion_check(
            db=db,
            session_id=session_id,
            user_id=user_id,
            course_id=course_id,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (EmbeddingConfigurationError, LLMConfigurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except (LLMProviderError, QuizGenerationError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except SocraticSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SocraticSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )

    return SocraticCompletionCheckResponse(
        session=_to_response(session),
        item=quiz_to_response(item),
    )


@router.post(
    "/{session_id}/completion-check/attempt",
    response_model=SocraticCompletionAttemptResponse,
)
def create_socratic_completion_attempt(
    session_id: int,
    request: SocraticCompletionAttemptRequest,
    db: Session = Depends(get_db),
) -> SocraticCompletionAttemptResponse:
    try:
        validate_course_scope(
            db=db,
            user_id=request.user_id,
            course_id=request.course_id,
        )
        session, attempt = submit_socratic_completion_attempt(
            db=db,
            session_id=session_id,
            selected_option_id=request.selected_option_id,
            user_id=request.user_id,
            course_id=request.course_id,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (QuizAttemptError, SocraticSessionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )
    except SocraticSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return SocraticCompletionAttemptResponse(
        session=_to_response(session),
        attempt=quiz_attempt_to_response(attempt=attempt, item=attempt.quiz_item),
    )


@router.get("/{session_id}", response_model=SocraticSessionResponse)
def get_socratic(
    session_id: int,
    user_id: str = "demo-user",
    course_id: int | None = None,
    db: Session = Depends(get_db),
) -> SocraticSessionResponse:
    try:
        validate_course_scope(db=db, user_id=user_id, course_id=course_id)
        session = get_socratic_session(
            db=db,
            session_id=session_id,
            user_id=user_id,
            course_id=course_id,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SocraticSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return _to_response(session)


def _to_response(session) -> SocraticSessionResponse:  # type: ignore[no-untyped-def]
    turns = list(session.turns or [])
    latest_turn = turns[-1] if turns else None
    latest_assessment_turn = next(
        (turn for turn in reversed(turns) if turn.assessment is not None),
        None,
    )
    return SocraticSessionResponse(
        id=session.id,
        user_id=session.user_id,
        course_id=session.course_id,
        concept_id=session.concept_id,
        source_policy_decision_id=session.source_policy_decision_id,
        completion_quiz_item_id=session.completion_quiz_item_id,
        completion_quiz_attempt_id=session.completion_quiz_attempt_id,
        query=session.query,
        status=cast(SocraticStatus, session.status),
        current_stage=cast(SocraticStage, session.current_stage),
        turn_count=session.turn_count,
        max_turns=session.max_turns,
        message=latest_turn.tutor_message if latest_turn else "",
        assessment=(
            cast(SocraticAssessment, latest_assessment_turn.assessment)
            if latest_assessment_turn
            else None
        ),
        assessment_reason=(
            latest_assessment_turn.assessment_reason
            if latest_assessment_turn
            else None
        ),
        learner_state_snapshot=session.learner_state_snapshot,
        concept_snapshot=session.concept_snapshot,
        misconception_snapshot=session.misconception_snapshot,
        evidence_state_snapshot=session.evidence_state_snapshot,
        evidence_chunks_snapshot=session.evidence_chunks_snapshot,
        turns=[_turn_response(turn) for turn in turns],
        created_at=session.created_at,
        completed_at=session.completed_at,
    )


def _turn_response(turn) -> SocraticTurnResponse:  # type: ignore[no-untyped-def]
    return SocraticTurnResponse(
        id=turn.id,
        session_id=turn.session_id,
        turn_number=turn.turn_number,
        stage=cast(SocraticStage, turn.stage),
        tutor_message=turn.tutor_message,
        student_response=turn.student_response,
        assessment=(
            cast(SocraticAssessment, turn.assessment)
            if turn.assessment
            else None
        ),
        assessment_reason=turn.assessment_reason,
        created_at=turn.created_at,
    )
