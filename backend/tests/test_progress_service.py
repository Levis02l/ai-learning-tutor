from datetime import datetime

from app.models.misconception import Misconception
from app.services.concepts import ConceptLearnerState
from app.services.progress import (
    ProgressSocraticActivity,
    get_course_progress,
)


def test_progress_marks_unobserved_without_zero_mastery(monkeypatch) -> None:
    captured: dict[str, int | str] = {}

    def fake_validate(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["validated_user_id"] = kwargs["user_id"]
        captured["validated_course_id"] = kwargs["course_id"]

    monkeypatch.setattr("app.services.progress.validate_course_scope", fake_validate)
    monkeypatch.setattr(
        "app.services.progress.list_concept_learner_states",
        lambda **kwargs: [
            _state(
                concept_id=1,
                concept_name="Neural Networks",
                state_status="unobserved",
                mastery_score=None,
                recent_accuracy=None,
                attempt_count=0,
                consecutive_errors=0,
                needs_attention=False,
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.progress._load_prerequisites_by_concept",
        lambda **kwargs: {},
    )
    monkeypatch.setattr(
        "app.services.progress._load_socratic_activity_by_concept",
        lambda **kwargs: {},
    )
    monkeypatch.setattr(
        "app.services.progress.get_relevant_misconception",
        lambda **kwargs: None,
    )

    progress = get_course_progress(
        db=object(),  # type: ignore[arg-type]
        user_id="demo-user",
        course_id=4,
    )

    assert captured == {"validated_user_id": "demo-user", "validated_course_id": 4}
    assert progress.summary.total_concepts == 1
    assert progress.summary.unobserved_concepts == 1
    concept = progress.concepts[0]
    assert concept.status == "unobserved"
    assert concept.learner_state.mastery_score is None
    assert concept.learner_state.recent_accuracy is None
    assert concept.attention_reasons == []


def test_progress_uses_relevant_misconception_as_attention_signal(
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.services.progress.validate_course_scope", lambda **_: None)
    monkeypatch.setattr(
        "app.services.progress.list_concept_learner_states",
        lambda **kwargs: [
            _state(
                concept_id=2,
                concept_name="WSS-BSS Decomposition",
                state_status="observed",
                mastery_score=0.32,
                recent_accuracy=0.25,
                attempt_count=4,
                consecutive_errors=2,
                needs_attention=True,
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.progress._load_prerequisites_by_concept",
        lambda **kwargs: {},
    )
    monkeypatch.setattr(
        "app.services.progress._load_socratic_activity_by_concept",
        lambda **kwargs: {},
    )
    monkeypatch.setattr(
        "app.services.progress.get_relevant_misconception",
        lambda **kwargs: _misconception(concept_id=kwargs["concept_id"]),
    )

    progress = get_course_progress(
        db=object(),  # type: ignore[arg-type]
        user_id="demo-user",
        course_id=4,
    )

    concept = progress.concepts[0]
    assert concept.status == "needs_attention"
    assert concept.latest_misconception is not None
    assert concept.latest_misconception.misconception_type == "missing_prerequisite"
    assert "recent_learning_signal" in concept.attention_reasons
    assert "low_estimated_mastery" in concept.attention_reasons
    assert "low_recent_accuracy" in concept.attention_reasons
    assert progress.summary.needs_attention_count == 1


def test_progress_marks_stable_high_performance_as_strong(monkeypatch) -> None:
    monkeypatch.setattr("app.services.progress.validate_course_scope", lambda **_: None)
    monkeypatch.setattr(
        "app.services.progress.list_concept_learner_states",
        lambda **kwargs: [
            _state(
                concept_id=3,
                concept_name="K-means Clustering",
                state_status="observed",
                mastery_score=0.86,
                recent_accuracy=0.8,
                attempt_count=8,
                consecutive_errors=0,
                needs_attention=False,
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.progress._load_prerequisites_by_concept",
        lambda **kwargs: {},
    )
    monkeypatch.setattr(
        "app.services.progress._load_socratic_activity_by_concept",
        lambda **kwargs: {
            3: ProgressSocraticActivity(
                completed_sessions=2,
                completion_attempts=1,
                latest_session_id=12,
                latest_completed_at="2026-07-21T12:00:00",
                latest_completion_quiz_item_id=77,
                latest_completion_quiz_attempt_id=88,
                latest_completion_correct=True,
            )
        },
    )
    monkeypatch.setattr(
        "app.services.progress.get_relevant_misconception",
        lambda **kwargs: None,
    )

    progress = get_course_progress(
        db=object(),  # type: ignore[arg-type]
        user_id="demo-user",
        course_id=4,
    )

    concept = progress.concepts[0]
    assert concept.status == "strong"
    assert concept.socratic_activity.completed_sessions == 2
    assert concept.socratic_activity.completion_attempts == 1
    assert concept.socratic_activity.latest_completion_correct is True
    assert progress.summary.strong_count == 1
    assert progress.summary.socratic_completed_count == 2
    assert progress.summary.socratic_completion_attempt_count == 1


def _state(
    *,
    concept_id: int,
    concept_name: str,
    state_status: str,
    mastery_score: float | None,
    recent_accuracy: float | None,
    attempt_count: int,
    consecutive_errors: int,
    needs_attention: bool,
) -> ConceptLearnerState:
    return ConceptLearnerState(
        concept_id=concept_id,
        concept_name=concept_name,
        state_status=state_status,  # type: ignore[arg-type]
        mastery_score=mastery_score,
        recent_accuracy=recent_accuracy,
        attempt_count=attempt_count,
        consecutive_errors=consecutive_errors,
        last_attempted_at=datetime(2026, 7, 21, 12, 0, 0)
        if state_status == "observed"
        else None,
        review_due=False,
        needs_attention=needs_attention,
    )


def _misconception(*, concept_id: int) -> Misconception:
    return Misconception(
        id=9,
        user_id="demo-user",
        course_id=4,
        concept_id=concept_id,
        quiz_attempt_id=22,
        misconception_type="missing_prerequisite",
        description="The learner may need the prerequisite variance concept.",
        confidence=0.82,
        evidence_snapshot={},
        created_at=datetime(2026, 7, 21, 12, 5, 0),
    )
