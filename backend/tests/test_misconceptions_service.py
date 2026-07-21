from datetime import datetime

from app.llm.provider import LLMProviderError, LLMResponse
from app.models.concept import Concept
from app.models.document import Chunk, Document
from app.models.misconception import Misconception
from app.models.quiz import QuizAttempt, QuizItem
from app.services.misconceptions import (
    detect_misconception_for_attempt,
    get_relevant_misconception,
    try_detect_misconception_for_attempt,
)


def test_detect_misconception_stores_structured_error() -> None:
    concept = _concept()
    item = _quiz_item(concept_id=concept.id)
    attempt = _attempt(is_correct=False)
    db = _DetectionSession(concept=concept)
    provider = _Provider(
        '{"misconception_type": "concept_confusion", '
        '"description": "The learner confused clustering with classification.", '
        '"confidence": 0.82}'
    )

    misconception = detect_misconception_for_attempt(
        db=db,  # type: ignore[arg-type]
        attempt=attempt,
        item=item,
        llm_provider=provider,
    )

    assert misconception is not None
    assert misconception.misconception_type == "concept_confusion"
    assert misconception.description == (
        "The learner confused clustering with classification."
    )
    assert misconception.confidence == 0.82
    assert misconception.evidence_snapshot["concept_name"] == "K-means Clustering"
    assert misconception.evidence_snapshot["selected_option_id"] == "A"
    assert misconception.evidence_snapshot["correct_option_id"] == "B"
    assert db.added == [misconception]
    assert db.commits == 1


def test_detect_misconception_skips_correct_attempt() -> None:
    item = _quiz_item(concept_id=7)
    attempt = _attempt(is_correct=True)
    db = _DetectionSession(concept=_concept())

    result = detect_misconception_for_attempt(
        db=db,  # type: ignore[arg-type]
        attempt=attempt,
        item=item,
        llm_provider=_Provider("{}"),
    )

    assert result is None
    assert db.added == []


def test_detect_misconception_skips_unbound_quiz_item() -> None:
    item = _quiz_item(concept_id=None)
    attempt = _attempt(is_correct=False)
    db = _DetectionSession(concept=_concept())

    result = detect_misconception_for_attempt(
        db=db,  # type: ignore[arg-type]
        attempt=attempt,
        item=item,
        llm_provider=_Provider("{}"),
    )

    assert result is None
    assert db.added == []


def test_try_detect_misconception_is_failure_safe() -> None:
    item = _quiz_item(concept_id=7)
    attempt = _attempt(is_correct=False)
    db = _DetectionSession(concept=_concept())

    result = try_detect_misconception_for_attempt(
        db=db,  # type: ignore[arg-type]
        attempt=attempt,
        item=item,
        llm_provider=_FailingProvider(),
    )

    assert result is None
    assert db.rollbacks == 1


def test_get_relevant_misconception_filters_scope_and_confidence() -> None:
    db = _CaptureScalarSession()

    get_relevant_misconception(
        db=db,  # type: ignore[arg-type]
        user_id="demo-user",
        course_id=4,
        concept_id=7,
        min_confidence=0.6,
    )

    assert "misconceptions.user_id = 'demo-user'" in db.sql
    assert "misconceptions.course_id = 4" in db.sql
    assert "misconceptions.concept_id = 7" in db.sql
    assert "misconceptions.confidence >= 0.6" in db.sql
    assert "ORDER BY misconceptions.created_at DESC" in db.sql


def test_get_relevant_misconception_scopes_uncoursed_records() -> None:
    db = _CaptureScalarSession()

    get_relevant_misconception(
        db=db,  # type: ignore[arg-type]
        user_id="demo-user",
        course_id=None,
        concept_id=7,
    )

    assert "misconceptions.course_id IS NULL" in db.sql


class _Provider:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate(self, **kwargs):  # type: ignore[no-untyped-def]
        return LLMResponse(text=self.text)


class _FailingProvider:
    def generate(self, **kwargs):  # type: ignore[no-untyped-def]
        raise LLMProviderError("provider unavailable")


class _DetectionSession:
    def __init__(self, *, concept: Concept) -> None:
        self.concept = concept
        self.scalar_calls = 0
        self.added: list[Misconception] = []
        self.commits = 0
        self.rollbacks = 0

    def scalar(self, query):  # type: ignore[no-untyped-def]
        self.scalar_calls += 1
        if self.scalar_calls == 1:
            return None
        return self.concept

    def execute(self, query):  # type: ignore[no-untyped-def]
        return _Rows(
            [
                (
                    Chunk(
                        id=82,
                        document_id=2,
                        content="K-means minimizes within-cluster sum of squares.",
                        chunk_metadata={},
                    ),
                    Document(
                        id=2,
                        user_id="demo-user",
                        course_id=4,
                        filename="lecture.pdf",
                        file_type="pdf",
                        status="done",
                    ),
                )
            ]
        )

    def add(self, obj: Misconception) -> None:
        obj.id = 5
        self.added.append(obj)

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, obj: object) -> None:
        return None

    def rollback(self) -> None:
        self.rollbacks += 1


class _CaptureScalarSession:
    def __init__(self) -> None:
        self.sql = ""

    def scalar(self, query):  # type: ignore[no-untyped-def]
        self.sql = str(query.compile(compile_kwargs={"literal_binds": True}))
        return None


class _Rows:
    def __init__(self, rows: list[tuple[Chunk, Document]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[Chunk, Document]]:
        return self._rows


def _concept() -> Concept:
    return Concept(
        id=7,
        course_id=4,
        name="K-means Clustering",
        normalized_name="k means clustering",
        description="A clustering method.",
        extraction_confidence=0.9,
        created_at=datetime(2026, 7, 21, 12, 0, 0),
        updated_at=datetime(2026, 7, 21, 12, 0, 0),
    )


def _quiz_item(*, concept_id: int | None) -> QuizItem:
    return QuizItem(
        id=1,
        user_id="demo-user",
        course_id=4,
        concept_id=concept_id,
        question="What does K-means minimize?",
        answer="Within-cluster sum of squares.",
        difficulty="medium",
        origin="manual_practice",
        source_chunk_ids=[82],
        evidence_quote="K-means minimizes within-cluster sum of squares.",
        options=[
            {"id": "A", "text": "Classification error"},
            {"id": "B", "text": "Within-cluster sum of squares"},
            {"id": "C", "text": "Number of clusters"},
            {"id": "D", "text": "Database joins"},
        ],
        correct_option_id="B",
        explanation="K-means minimizes within-cluster sum of squares.",
        question_type="conceptual",
        traceability_label="fully_traceable",
    )


def _attempt(*, is_correct: bool) -> QuizAttempt:
    return QuizAttempt(
        id=9,
        user_id="demo-user",
        course_id=4,
        quiz_item_id=1,
        selected_option_id="A",
        selected_option_text="Classification error",
        correct_option_id="B",
        correct_option_text="Within-cluster sum of squares",
        is_correct=is_correct,
        attempted_at=datetime(2026, 7, 21, 12, 30, 0),
    )
