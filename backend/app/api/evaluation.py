from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.evaluation import (
    Answerability,
    AnswerEvaluationRequest,
    AnswerEvaluationResponse,
    QuizEvaluationRequest,
    QuizEvaluationResponse,
)
from app.services.courses import CourseNotFoundError, validate_course_scope
from app.services.evaluation import evaluate_answer, evaluate_quiz_items

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/answer", response_model=AnswerEvaluationResponse)
def evaluate_answer_response(
    request: AnswerEvaluationRequest,
    db: Session = Depends(get_db),
) -> AnswerEvaluationResponse:
    course_id = _resolve_response_course_id(
        explicit_course_id=request.course_id,
        response_course_id=request.response.course_id,
    )
    try:
        validate_course_scope(db=db, user_id=request.user_id, course_id=course_id)
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    evaluation = evaluate_answer(
        response=request.response,
        answerability=_resolve_answerability(request),
    )
    return evaluation.model_copy(
        update={"user_id": request.user_id, "course_id": course_id}
    )


@router.post("/quiz", response_model=QuizEvaluationResponse)
def evaluate_quiz_response(
    request: QuizEvaluationRequest,
    db: Session = Depends(get_db),
) -> QuizEvaluationResponse:
    course_id = _resolve_quiz_course_id(request)
    try:
        validate_course_scope(db=db, user_id=request.user_id, course_id=course_id)
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    evaluation = evaluate_quiz_items(items=request.items)
    return evaluation.model_copy(
        update={"user_id": request.user_id, "course_id": course_id}
    )


def _resolve_response_course_id(
    *,
    explicit_course_id: int | None,
    response_course_id: int | None,
) -> int | None:
    if (
        explicit_course_id is not None
        and response_course_id is not None
        and explicit_course_id != response_course_id
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Evaluation course_id does not match response course_id",
        )
    return explicit_course_id if explicit_course_id is not None else response_course_id


def _resolve_answerability(request: AnswerEvaluationRequest) -> Answerability:
    if request.answerability is not None:
        return request.answerability
    if request.expected_answerable is True:
        return "answerable"
    return "unanswerable"


def _resolve_quiz_course_id(request: QuizEvaluationRequest) -> int | None:
    item_course_ids = {
        item.course_id for item in request.items if item.course_id is not None
    }
    if request.course_id is not None:
        mismatches = item_course_ids - {request.course_id}
        if mismatches:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Evaluation course_id does not match quiz item course_id",
            )
        return request.course_id

    if len(item_course_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Quiz evaluation items belong to multiple courses",
        )
    return next(iter(item_course_ids), None)
