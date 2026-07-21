from datetime import datetime

from app.models.concept import Concept
from app.models.policy import PolicyDecisionRecord
from app.services.concepts import ConceptLearnerState, ResolvedConcept
from app.services.learner_state import LearnerState
from app.services.policy import (
    PolicyEvidenceState,
    create_policy_decision,
    decide_teaching_action,
    detect_intent,
)
from app.services.retrieval import RetrievedChunk
from app.services.tutor_context import TutorEvidenceContext


def test_detect_intent_prioritises_hint_before_explain() -> None:
    assert detect_intent("Give me a hint, don't tell me the answer") == "hint"


def test_policy_refuses_when_evidence_is_insufficient() -> None:
    decision = _decision(
        query="Quiz me on this missing topic",
        learner_state=_learner_state(mastery_score=0.8),
        evidence_state=_evidence("insufficient"),
    )

    assert decision.detected_intent == "practice"
    assert decision.selected_action == "refuse"
    assert decision.response_strategy == "refusal"
    assert decision.primary_reason == "insufficient_evidence"


def test_explicit_explain_with_low_mastery_uses_scaffolded_explanation() -> None:
    decision = _decision(
        query="Explain TCP congestion control",
        learner_state=_learner_state(mastery_score=0.2, consecutive_errors=2),
        evidence_state=_evidence("high"),
    )

    assert decision.detected_intent == "explain"
    assert decision.selected_action == "explain"
    assert decision.response_strategy == "scaffolded"
    assert decision.primary_reason == "explicit_explanation_request"


def test_explicit_explain_with_high_mastery_stays_explain_but_concise() -> None:
    decision = _decision(
        query="Explain TCP congestion control",
        learner_state=_learner_state(mastery_score=0.9, review_due=True),
        evidence_state=_evidence("high"),
    )

    assert decision.selected_action == "explain"
    assert decision.response_strategy == "concise"
    assert decision.primary_reason == "explicit_explanation_request"


def test_explicit_hint_returns_hint() -> None:
    decision = _decision(
        query="Give me a hint about routing",
        learner_state=_learner_state(mastery_score=0.55),
        evidence_state=_evidence("medium"),
    )

    assert decision.selected_action == "hint"
    assert decision.response_strategy == "guided"
    assert decision.primary_reason == "explicit_hint_request"


def test_explicit_practice_returns_quiz() -> None:
    decision = _decision(
        query="Quiz me on transport protocols",
        learner_state=_learner_state(mastery_score=0.82),
        evidence_state=_evidence("high"),
    )

    assert decision.detected_intent == "practice"
    assert decision.selected_action == "quiz"
    assert decision.response_strategy == "challenging"
    assert decision.primary_reason == "explicit_practice_request"


def test_unknown_with_due_review_items_returns_review() -> None:
    decision = _decision(
        query="What should I do next?",
        learner_state=_learner_state(mastery_score=0.7, review_due=True),
        evidence_state=_evidence("not_required", requires_evidence=False),
    )

    assert decision.detected_intent == "unknown"
    assert decision.selected_action == "review"
    assert decision.response_strategy == "review_drill"
    assert decision.primary_reason == "review_due"


def test_unknown_with_low_mastery_returns_explain() -> None:
    decision = _decision(
        query="I am stuck",
        learner_state=_learner_state(mastery_score=0.25),
        evidence_state=_evidence("medium"),
    )

    assert decision.selected_action == "explain"
    assert decision.response_strategy == "scaffolded"
    assert decision.primary_reason == "low_mastery"


def test_unknown_with_high_mastery_returns_quiz() -> None:
    decision = _decision(
        query="Next",
        learner_state=_learner_state(mastery_score=0.86),
        evidence_state=_evidence("high"),
    )

    assert decision.selected_action == "quiz"
    assert decision.response_strategy == "challenging"
    assert decision.primary_reason == "high_mastery"


def test_explicit_review_can_use_not_required_evidence() -> None:
    decision = _decision(
        query="Review the due questions with me",
        learner_state=_learner_state(mastery_score=0.6, review_due=True),
        evidence_state=_evidence("not_required", requires_evidence=False),
    )

    assert decision.detected_intent == "review"
    assert decision.selected_action == "review"
    assert decision.response_strategy == "review_drill"
    assert decision.primary_reason == "explicit_review_request"


def test_unknown_unobserved_concept_returns_diagnostic_quiz() -> None:
    decision = decide_teaching_action(
        query="I want to study K-means clustering",
        user_id="demo-user",
        course_id=7,
        learner_state=_learner_state(mastery_score=0.5),
        evidence_state=_evidence("high"),
        detected_intent="unknown",
        learner_state_scope="concept",
        concept_state=ConceptLearnerState(
            concept_id=3,
            concept_name="K-means Clustering",
            state_status="unobserved",
            mastery_score=None,
            recent_accuracy=None,
            attempt_count=0,
            consecutive_errors=0,
            last_attempted_at=None,
            review_due=False,
            needs_attention=False,
        ),
    )

    assert decision.learner_state_scope == "concept"
    assert decision.concept_state_snapshot is not None
    assert decision.concept_state_snapshot["state_status"] == "unobserved"
    assert decision.selected_action == "quiz"
    assert decision.response_strategy == "guided"
    assert decision.primary_reason == "unobserved_concept"


def test_create_policy_decision_uses_observed_concept_state(monkeypatch) -> None:
    db = _PolicySession()

    monkeypatch.setattr(
        "app.services.policy.compute_learner_state",
        lambda **kwargs: _learner_state(mastery_score=0.2, consecutive_errors=2),
    )
    monkeypatch.setattr("app.services.policy.get_due_review_items", lambda **kwargs: [])
    monkeypatch.setattr(
        "app.services.policy.build_tutor_evidence_context",
        lambda **kwargs: TutorEvidenceContext(
            resolved_concept=kwargs["resolved_concept"],
            chunks=[_chunk(chunk_id=41)],
            evidence_state=_evidence("high", source_chunk_ids=[41]),
        ),
    )
    monkeypatch.setattr(
        "app.services.policy.resolve_concept_for_focus",
        lambda **kwargs: ResolvedConcept(
            concept=_concept(concept_id=9, name="K-means Clustering"),
            confidence=0.94,
            reason="exact normalized match",
        ),
    )
    monkeypatch.setattr(
        "app.services.policy.get_concept_learner_state",
        lambda **kwargs: ConceptLearnerState(
            concept_id=9,
            concept_name="K-means Clustering",
            state_status="observed",
            mastery_score=0.88,
            recent_accuracy=0.9,
            attempt_count=5,
            consecutive_errors=0,
            last_attempted_at=datetime(2026, 7, 21, 11, 30, 0),
            review_due=False,
            needs_attention=False,
        ),
    )

    decision = create_policy_decision(
        db=db,  # type: ignore[arg-type]
        query="Explain K-means clustering",
        user_id="demo-user",
        course_id=7,
    )

    assert decision.learner_state_scope == "concept"
    assert decision.learner_state_snapshot["mastery_score"] == 0.88
    assert decision.concept_state_snapshot is not None
    assert decision.concept_state_snapshot["concept_id"] == 9
    assert decision.evidence_state_snapshot["source_chunk_ids"] == [41]
    assert [chunk.chunk_id for chunk in decision.evidence_chunks] == [41]
    assert decision.selected_action == "explain"
    assert decision.response_strategy == "concise"
    assert db.record is not None
    assert db.record.learner_state_scope == "concept"
    assert db.record.concept_state_snapshot["concept_name"] == "K-means Clustering"


def test_create_policy_decision_falls_back_to_course_state(monkeypatch) -> None:
    db = _PolicySession()

    monkeypatch.setattr(
        "app.services.policy.compute_learner_state",
        lambda **kwargs: _learner_state(mastery_score=0.84),
    )
    monkeypatch.setattr("app.services.policy.get_due_review_items", lambda **kwargs: [])
    monkeypatch.setattr(
        "app.services.policy.build_tutor_evidence_context",
        lambda **kwargs: TutorEvidenceContext(
            resolved_concept=kwargs["resolved_concept"],
            chunks=[_chunk(chunk_id=51)],
            evidence_state=_evidence("high", source_chunk_ids=[51]),
        ),
    )
    monkeypatch.setattr(
        "app.services.policy.resolve_concept_for_focus",
        lambda **kwargs: None,
    )

    decision = create_policy_decision(
        db=db,  # type: ignore[arg-type]
        query="Next",
        user_id="demo-user",
        course_id=7,
    )

    assert decision.learner_state_scope == "course"
    assert decision.concept_state_snapshot is None
    assert decision.selected_action == "quiz"
    assert decision.response_strategy == "challenging"
    assert db.record is not None
    assert db.record.learner_state_scope == "course"
    assert db.record.concept_state_snapshot is None


def _decision(
    *,
    query: str,
    learner_state: LearnerState,
    evidence_state: PolicyEvidenceState,
):
    return decide_teaching_action(
        query=query,
        user_id="demo-user",
        course_id=1,
        learner_state=learner_state,
        evidence_state=evidence_state,
    )


def _concept(*, concept_id: int, name: str) -> Concept:
    return Concept(
        id=concept_id,
        course_id=7,
        name=name,
        normalized_name=name.lower(),
        description=f"{name} description.",
        extraction_confidence=0.9,
    )


class _PolicySession:
    def __init__(self) -> None:
        self.record: PolicyDecisionRecord | None = None

    def add(self, item):  # type: ignore[no-untyped-def]
        if isinstance(item, PolicyDecisionRecord):
            item.id = 101
            self.record = item

    def commit(self) -> None:
        return None

    def refresh(self, item):  # type: ignore[no-untyped-def]
        return None


def _learner_state(
    *,
    mastery_score: float,
    review_due: bool = False,
    consecutive_errors: int = 0,
) -> LearnerState:
    return LearnerState(
        user_id="demo-user",
        course_id=1,
        mastery_score=mastery_score,
        recent_accuracy=mastery_score,
        attempt_count=4,
        consecutive_errors=consecutive_errors,
        last_reviewed_at=datetime(2026, 7, 18, 12, 0, 0),
        review_due=review_due,
    )


def _evidence(
    evidence_strength,
    *,
    requires_evidence: bool = True,
    source_chunk_ids: list[int] | None = None,
) -> PolicyEvidenceState:
    return PolicyEvidenceState(
        evidence_strength=evidence_strength,
        source_coverage=1.0 if evidence_strength != "insufficient" else 0.0,
        retrieved_chunk_count=3 if evidence_strength != "not_required" else 0,
        top_similarity=0.7 if evidence_strength != "insufficient" else 0.0,
        requires_evidence=requires_evidence,
        reason="test evidence",
        source_chunk_ids=source_chunk_ids or [],
    )


def _chunk(*, chunk_id: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=2,
        course_id=7,
        filename="lecture.pdf",
        content=f"Evidence chunk {chunk_id}.",
        metadata={},
        distance=0.2,
        similarity=0.8,
    )
