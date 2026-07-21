from datetime import datetime, timedelta

from app.models.quiz import QuizAttempt, QuizItem
from app.services.learner_state import LearnerState, _build_learner_state
from app.services.policy import PolicyEvidenceState, decide_teaching_action


def test_neutral_request_changes_from_challenge_to_review_after_wrong_answers() -> None:
    before_state = _state_from_attempts(
        [
            _attempt(attempt_id=2, item_id=2, is_correct=True, minutes_ago=0),
            _attempt(attempt_id=1, item_id=1, is_correct=True, minutes_ago=5),
        ]
    )
    before_decision = _decision(query="Next", learner_state=before_state)

    assert before_state.mastery_score >= 0.75
    assert before_state.review_due is False
    assert before_decision.detected_intent == "unknown"
    assert before_decision.selected_action == "quiz"
    assert before_decision.response_strategy == "challenging"

    after_state = _state_from_attempts(
        [
            _attempt(attempt_id=4, item_id=2, is_correct=False, minutes_ago=0),
            _attempt(attempt_id=3, item_id=1, is_correct=False, minutes_ago=5),
            _attempt(attempt_id=2, item_id=2, is_correct=True, minutes_ago=10),
            _attempt(attempt_id=1, item_id=1, is_correct=True, minutes_ago=15),
        ]
    )
    after_decision = _decision(query="Next", learner_state=after_state)

    assert after_state.consecutive_errors == 2
    assert after_state.review_due is True
    assert after_decision.learner_state_snapshot["consecutive_errors"] == 2
    assert after_decision.learner_state_snapshot["review_due"] is True
    assert after_decision.selected_action == "review"
    assert after_decision.response_strategy == "review_drill"
    assert after_decision.primary_reason == "review_due"


def test_explicit_explain_keeps_action_but_changes_strategy_after_errors() -> None:
    before_state = _state_from_attempts(
        [
            _attempt(attempt_id=2, item_id=2, is_correct=True, minutes_ago=0),
            _attempt(attempt_id=1, item_id=1, is_correct=True, minutes_ago=5),
        ]
    )
    before_decision = _decision(
        query="Explain artificial intelligence",
        learner_state=before_state,
    )

    assert before_decision.selected_action == "explain"
    assert before_decision.response_strategy == "concise"

    after_state = _state_from_attempts(
        [
            _attempt(attempt_id=4, item_id=2, is_correct=False, minutes_ago=0),
            _attempt(attempt_id=3, item_id=1, is_correct=False, minutes_ago=5),
            _attempt(attempt_id=2, item_id=2, is_correct=True, minutes_ago=10),
            _attempt(attempt_id=1, item_id=1, is_correct=True, minutes_ago=15),
        ]
    )
    after_decision = _decision(
        query="Explain artificial intelligence",
        learner_state=after_state,
    )

    assert after_decision.detected_intent == "explain"
    assert after_decision.selected_action == "explain"
    assert after_decision.response_strategy == "scaffolded"
    assert after_decision.primary_reason == "explicit_explanation_request"


def test_explicit_quiz_keeps_action_when_mastery_is_low() -> None:
    low_state = _state_from_attempts(
        [
            _attempt(attempt_id=3, item_id=1, is_correct=False, minutes_ago=0),
            _attempt(attempt_id=2, item_id=2, is_correct=False, minutes_ago=5),
            _attempt(attempt_id=1, item_id=1, is_correct=False, minutes_ago=10),
        ]
    )
    decision = _decision(
        query="Quiz me on artificial intelligence",
        learner_state=low_state,
    )

    assert low_state.mastery_score < 0.75
    assert decision.detected_intent == "practice"
    assert decision.selected_action == "quiz"
    assert decision.response_strategy == "guided"
    assert decision.primary_reason == "explicit_practice_request"


def test_correct_answers_raise_explicit_quiz_strategy_to_challenging() -> None:
    weak_state = _state_from_attempts(
        [
            _attempt(attempt_id=2, item_id=2, is_correct=False, minutes_ago=0),
            _attempt(attempt_id=1, item_id=1, is_correct=False, minutes_ago=5),
        ]
    )
    weak_decision = _decision(
        query="Quiz me on artificial intelligence",
        learner_state=weak_state,
    )

    assert weak_decision.selected_action == "quiz"
    assert weak_decision.response_strategy == "guided"

    improved_state = _state_from_attempts(
        [
            _attempt(attempt_id=4, item_id=2, is_correct=True, minutes_ago=0),
            _attempt(attempt_id=3, item_id=1, is_correct=True, minutes_ago=5),
            _attempt(attempt_id=2, item_id=2, is_correct=True, minutes_ago=10),
            _attempt(attempt_id=1, item_id=1, is_correct=True, minutes_ago=15),
        ]
    )
    improved_decision = _decision(
        query="Quiz me on artificial intelligence",
        learner_state=improved_state,
    )

    assert improved_state.mastery_score >= 0.75
    assert improved_decision.selected_action == "quiz"
    assert improved_decision.response_strategy == "challenging"


def _state_from_attempts(attempts: list[QuizAttempt]) -> LearnerState:
    return _build_learner_state(
        user_id="demo-user",
        course_id=1,
        quiz_items=[
            _quiz_item(item_id=1),
            _quiz_item(item_id=2),
        ],
        attempts=attempts,
        now=datetime(2026, 7, 21, 12, 0, 0),
    )


def _decision(*, query: str, learner_state: LearnerState):
    return decide_teaching_action(
        query=query,
        user_id="demo-user",
        course_id=1,
        learner_state=learner_state,
        evidence_state=PolicyEvidenceState(
            evidence_strength="high",
            source_coverage=1.0,
            retrieved_chunk_count=3,
            top_similarity=0.7,
            requires_evidence=True,
            reason="Test evidence is sufficient.",
        ),
    )


def _quiz_item(*, item_id: int) -> QuizItem:
    return QuizItem(
        id=item_id,
        user_id="demo-user",
        course_id=1,
        question=f"Question {item_id}?",
        answer="Answer.",
        difficulty="medium",
        source_chunk_ids=[item_id],
        evidence_quote="Evidence.",
        options=[
            {"id": "A", "text": "Wrong option"},
            {"id": "B", "text": "Correct option"},
            {"id": "C", "text": "Distractor"},
            {"id": "D", "text": "Distractor"},
        ],
        correct_option_id="B",
        explanation="Explanation.",
        question_type="conceptual",
        traceability_label="fully_traceable",
        created_at=datetime(2026, 7, 20, 12, 0, 0),
    )


def _attempt(
    *,
    attempt_id: int,
    item_id: int,
    is_correct: bool,
    minutes_ago: int,
) -> QuizAttempt:
    attempted_at = datetime(2026, 7, 21, 12, 0, 0) - timedelta(minutes=minutes_ago)
    return QuizAttempt(
        id=attempt_id,
        user_id="demo-user",
        course_id=1,
        quiz_item_id=item_id,
        selected_option_id="B" if is_correct else "A",
        selected_option_text="Correct option" if is_correct else "Wrong option",
        correct_option_id="B",
        correct_option_text="Correct option",
        is_correct=is_correct,
        attempted_at=attempted_at,
    )
