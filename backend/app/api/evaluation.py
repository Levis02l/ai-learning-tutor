from fastapi import APIRouter

from app.schemas.evaluation import (
    AnswerEvaluationRequest,
    AnswerEvaluationResponse,
    QuizEvaluationRequest,
    QuizEvaluationResponse,
)
from app.services.evaluation import evaluate_answer, evaluate_quiz_items

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/answer", response_model=AnswerEvaluationResponse)
def evaluate_answer_response(
    request: AnswerEvaluationRequest,
) -> AnswerEvaluationResponse:
    return evaluate_answer(
        response=request.response,
        expected_answerable=request.expected_answerable,
    )


@router.post("/quiz", response_model=QuizEvaluationResponse)
def evaluate_quiz_response(
    request: QuizEvaluationRequest,
) -> QuizEvaluationResponse:
    return evaluate_quiz_items(items=request.items)
