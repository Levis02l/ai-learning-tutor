from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.concept import Concept, ConceptPrerequisite
from app.models.misconception import Misconception
from app.models.quiz import QuizAttempt
from app.models.socratic import SocraticSession
from app.services.concepts import ConceptLearnerState, list_concept_learner_states
from app.services.courses import validate_course_scope
from app.services.misconceptions import get_relevant_misconception

ProgressConceptStatus = Literal[
    "unobserved",
    "needs_attention",
    "developing",
    "strong",
]

STRONG_MASTERY_THRESHOLD = 0.8
STRONG_ACCURACY_THRESHOLD = 0.75
LOW_MASTERY_THRESHOLD = 0.45
LOW_ACCURACY_THRESHOLD = 0.5


@dataclass(frozen=True)
class ProgressMisconception:
    id: int
    misconception_type: str
    description: str
    confidence: float
    quiz_attempt_id: int
    created_at: str | None


@dataclass(frozen=True)
class ProgressPrerequisite:
    id: int
    name: str
    confidence: float


@dataclass(frozen=True)
class ProgressSocraticActivity:
    completed_sessions: int
    completion_attempts: int = 0
    latest_session_id: int | None = None
    latest_completed_at: str | None = None
    latest_completion_quiz_item_id: int | None = None
    latest_completion_quiz_attempt_id: int | None = None
    latest_completion_correct: bool | None = None


@dataclass(frozen=True)
class ProgressConcept:
    learner_state: ConceptLearnerState
    status: ProgressConceptStatus
    attention_reasons: list[str]
    latest_misconception: ProgressMisconception | None
    prerequisites: list[ProgressPrerequisite]
    socratic_activity: ProgressSocraticActivity


@dataclass(frozen=True)
class ProgressSummary:
    total_concepts: int
    observed_concepts: int
    unobserved_concepts: int
    needs_attention_count: int
    review_due_count: int
    strong_count: int
    developing_count: int
    socratic_completed_count: int
    socratic_completion_attempt_count: int


@dataclass(frozen=True)
class CourseProgress:
    user_id: str
    course_id: int
    summary: ProgressSummary
    concepts: list[ProgressConcept] = field(default_factory=list)


def get_course_progress(
    db: Session,
    *,
    user_id: str,
    course_id: int,
    now: datetime | None = None,
) -> CourseProgress:
    validate_course_scope(db=db, user_id=user_id, course_id=course_id)
    learner_states = list_concept_learner_states(
        db=db,
        user_id=user_id,
        course_id=course_id,
        now=now,
    )
    concept_ids = [state.concept_id for state in learner_states]
    prerequisites_by_concept = _load_prerequisites_by_concept(
        db=db,
        course_id=course_id,
        concept_ids=concept_ids,
    )
    socratic_by_concept = _load_socratic_activity_by_concept(
        db=db,
        user_id=user_id,
        course_id=course_id,
        concept_ids=concept_ids,
    )

    concepts: list[ProgressConcept] = []
    for state in learner_states:
        latest_misconception = get_relevant_misconception(
            db=db,
            user_id=user_id,
            course_id=course_id,
            concept_id=state.concept_id,
        )
        attention_reasons = _attention_reasons(
            state=state,
            latest_misconception=latest_misconception,
        )
        concepts.append(
            ProgressConcept(
                learner_state=state,
                status=_progress_status(
                    state=state,
                    attention_reasons=attention_reasons,
                ),
                attention_reasons=attention_reasons,
                latest_misconception=(
                    _misconception_summary(latest_misconception)
                    if latest_misconception
                    else None
                ),
                prerequisites=prerequisites_by_concept.get(state.concept_id, []),
                socratic_activity=socratic_by_concept.get(
                    state.concept_id,
                    ProgressSocraticActivity(
                        completed_sessions=0,
                        completion_attempts=0,
                    ),
                ),
            )
        )

    return CourseProgress(
        user_id=user_id,
        course_id=course_id,
        summary=_summary(concepts),
        concepts=concepts,
    )


def _progress_status(
    *,
    state: ConceptLearnerState,
    attention_reasons: list[str],
) -> ProgressConceptStatus:
    if state.state_status == "unobserved":
        return "unobserved"
    if attention_reasons:
        return "needs_attention"
    if (
        state.mastery_score is not None
        and state.recent_accuracy is not None
        and state.mastery_score >= STRONG_MASTERY_THRESHOLD
        and state.recent_accuracy >= STRONG_ACCURACY_THRESHOLD
    ):
        return "strong"
    return "developing"


def _attention_reasons(
    *,
    state: ConceptLearnerState,
    latest_misconception: Misconception | None,
) -> list[str]:
    if state.state_status == "unobserved":
        return []

    reasons: list[str] = []
    if state.review_due:
        reasons.append("review_due")
    if state.needs_attention:
        reasons.append("needs_attention")
    if state.consecutive_errors >= 2:
        reasons.append("consecutive_errors")
    if state.mastery_score is not None and state.mastery_score < LOW_MASTERY_THRESHOLD:
        reasons.append("low_estimated_mastery")
    if (
        state.recent_accuracy is not None
        and state.recent_accuracy < LOW_ACCURACY_THRESHOLD
    ):
        reasons.append("low_recent_accuracy")
    if (
        latest_misconception is not None
        and latest_misconception.misconception_type != "unknown"
    ):
        reasons.append("recent_learning_signal")

    return _dedupe(reasons)


def _load_prerequisites_by_concept(
    *,
    db: Session,
    course_id: int,
    concept_ids: list[int],
) -> dict[int, list[ProgressPrerequisite]]:
    if not concept_ids:
        return {}

    rows = (
        db.execute(
            select(ConceptPrerequisite, Concept)
            .join(
                Concept,
                Concept.id == ConceptPrerequisite.prerequisite_concept_id,
            )
            .where(
                ConceptPrerequisite.concept_id.in_(concept_ids),
                Concept.course_id == course_id,
            )
            .order_by(
                ConceptPrerequisite.confidence.desc(),
                Concept.name.asc(),
            )
        )
        .all()
    )
    by_concept: dict[int, list[ProgressPrerequisite]] = {}
    for link, prerequisite in rows:
        by_concept.setdefault(link.concept_id, []).append(
            ProgressPrerequisite(
                id=prerequisite.id,
                name=prerequisite.name,
                confidence=link.confidence,
            )
        )
    return by_concept


def _load_socratic_activity_by_concept(
    *,
    db: Session,
    user_id: str,
    course_id: int,
    concept_ids: list[int],
) -> dict[int, ProgressSocraticActivity]:
    if not concept_ids:
        return {}

    rows = (
        db.execute(
            select(SocraticSession, QuizAttempt.is_correct)
            .outerjoin(
                QuizAttempt,
                QuizAttempt.id == SocraticSession.completion_quiz_attempt_id,
            )
            .where(
                SocraticSession.user_id == user_id,
                SocraticSession.course_id == course_id,
                SocraticSession.concept_id.in_(concept_ids),
                SocraticSession.status == "completed",
            )
            .order_by(
                SocraticSession.concept_id.asc(),
                SocraticSession.completed_at.desc(),
                SocraticSession.id.desc(),
            )
        )
        .all()
    )

    sessions_by_concept: dict[int, list[tuple[SocraticSession, bool | None]]] = {}
    for session, is_correct in rows:
        if session.concept_id is not None:
            sessions_by_concept.setdefault(session.concept_id, []).append(
                (session, is_correct)
            )

    activity_by_concept: dict[int, ProgressSocraticActivity] = {}
    for concept_id, sessions in sessions_by_concept.items():
        latest_session, latest_is_correct = sessions[0]
        completion_attempt_count = sum(
            1 for session, _ in sessions if session.completion_quiz_attempt_id
        )
        activity_by_concept[concept_id] = ProgressSocraticActivity(
            completed_sessions=len(sessions),
            completion_attempts=completion_attempt_count,
            latest_session_id=latest_session.id,
            latest_completed_at=_serialize_datetime(latest_session.completed_at),
            latest_completion_quiz_item_id=latest_session.completion_quiz_item_id,
            latest_completion_quiz_attempt_id=(
                latest_session.completion_quiz_attempt_id
            ),
            latest_completion_correct=latest_is_correct,
        )
    return activity_by_concept


def _misconception_summary(misconception: Misconception) -> ProgressMisconception:
    return ProgressMisconception(
        id=misconception.id,
        misconception_type=misconception.misconception_type,
        description=misconception.description,
        confidence=misconception.confidence,
        quiz_attempt_id=misconception.quiz_attempt_id,
        created_at=_serialize_datetime(misconception.created_at),
    )


def _summary(concepts: list[ProgressConcept]) -> ProgressSummary:
    return ProgressSummary(
        total_concepts=len(concepts),
        observed_concepts=sum(
            1
            for concept in concepts
            if concept.learner_state.state_status == "observed"
        ),
        unobserved_concepts=sum(
            1
            for concept in concepts
            if concept.learner_state.state_status == "unobserved"
        ),
        needs_attention_count=sum(
            1 for concept in concepts if concept.status == "needs_attention"
        ),
        review_due_count=sum(
            1 for concept in concepts if concept.learner_state.review_due
        ),
        strong_count=sum(1 for concept in concepts if concept.status == "strong"),
        developing_count=sum(
            1 for concept in concepts if concept.status == "developing"
        ),
        socratic_completed_count=sum(
            concept.socratic_activity.completed_sessions for concept in concepts
        ),
        socratic_completion_attempt_count=sum(
            concept.socratic_activity.completion_attempts for concept in concepts
        ),
    )


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
