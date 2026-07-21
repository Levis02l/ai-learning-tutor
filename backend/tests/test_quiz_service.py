import pytest

from app.models.quiz import QuizItem
from app.services.quiz import (
    GeneratedQuizItem,
    GeneratedQuizOption,
    QuizAttemptError,
    QuizGenerationError,
    _grade_quiz_attempt,
    _parse_generated_quiz,
    _retrieve_quiz_chunks,
    _to_quiz_item,
)
from app.services.retrieval import RetrievedChunk


def test_parse_generated_quiz_accepts_json() -> None:
    payload = _parse_generated_quiz(
        '{"items": [{"question": "Q?", "answer": "A.", "source_chunk_ids": [1], '
        '"options": [{"id": "A", "text": "Wrong"}, '
        '{"id": "B", "text": "Correct"}, {"id": "C", "text": "Wrong"}, '
        '{"id": "D", "text": "Wrong"}], "correct_option_id": "B", '
        '"explanation": "Because.", "evidence_quote": "Evidence.", '
        '"question_type": "definition", '
        '"traceability_label": "fully_traceable"}]}'
    )

    assert payload.items[0].question == "Q?"
    assert payload.items[0].source_chunk_ids == [1]
    assert payload.items[0].evidence_quote == "Evidence."
    assert payload.items[0].correct_option_id == "B"


def test_parse_generated_quiz_accepts_markdown_json_fence() -> None:
    payload = _parse_generated_quiz(
        '```json\n{"items": [{"question": "Q?", "answer": "A.", '
        '"options": [{"id": "A", "text": "Wrong"}, '
        '{"id": "B", "text": "Correct"}, {"id": "C", "text": "Wrong"}, '
        '{"id": "D", "text": "Wrong"}], "correct_option_id": "B"}]}\n```'
    )

    assert payload.items[0].answer == "A."


def test_parse_generated_quiz_rejects_invalid_json() -> None:
    with pytest.raises(QuizGenerationError):
        _parse_generated_quiz("not json")


def test_to_quiz_item_preserves_traceable_sources() -> None:
    item = GeneratedQuizItem(
        question="Q?",
        answer="A.",
        options=_options(),
        correct_option_id="B",
        explanation="Because B is supported.",
        source_chunk_ids=[1, 999],
        evidence_quote="Evidence.",
        question_type="conceptual",
        traceability_label="fully_traceable",
    )

    quiz_item = _to_quiz_item(
        item=item,
        user_id="demo-user",
        difficulty="medium",
        valid_source_ids={1},
    )

    assert quiz_item.source_chunk_ids == [1]
    assert quiz_item.traceability_label == "fully_traceable"
    assert quiz_item.options[1] == {"id": "B", "text": "Correct answer"}
    assert quiz_item.correct_option_id == "B"
    assert quiz_item.explanation == "Because B is supported."


def test_to_quiz_item_sets_concept_id_when_sources_are_traceable() -> None:
    item = GeneratedQuizItem(
        question="Q?",
        answer="A.",
        options=_options(),
        correct_option_id="B",
        explanation="Because B is supported.",
        source_chunk_ids=[1],
        evidence_quote="Evidence.",
        question_type="conceptual",
        traceability_label="fully_traceable",
    )

    quiz_item = _to_quiz_item(
        item=item,
        user_id="demo-user",
        difficulty="medium",
        valid_source_ids={1},
        concept_id=7,
    )

    assert quiz_item.concept_id == 7


def test_to_quiz_item_downgrades_item_without_valid_sources() -> None:
    item = GeneratedQuizItem(
        question="Q?",
        answer="A.",
        options=_options(),
        correct_option_id="B",
        explanation="Because B is supported.",
        source_chunk_ids=[999],
        evidence_quote="Evidence.",
        question_type="conceptual",
        traceability_label="fully_traceable",
    )

    quiz_item = _to_quiz_item(
        item=item,
        user_id="demo-user",
        difficulty="medium",
        valid_source_ids={1},
    )

    assert quiz_item.source_chunk_ids == []
    assert quiz_item.traceability_label == "not_traceable"
    assert quiz_item.concept_id is None


def test_to_quiz_item_rejects_invalid_option_count() -> None:
    item = GeneratedQuizItem(
        question="Q?",
        answer="A.",
        options=_options()[:3],
        correct_option_id="B",
        explanation="Because B is supported.",
        source_chunk_ids=[1],
    )

    with pytest.raises(QuizGenerationError):
        _to_quiz_item(
            item=item,
            user_id="demo-user",
            difficulty="medium",
            valid_source_ids={1},
        )


def test_to_quiz_item_rejects_duplicate_option_ids() -> None:
    item = GeneratedQuizItem(
        question="Q?",
        answer="A.",
        options=[
            GeneratedQuizOption(id="A", text="Wrong answer A"),
            GeneratedQuizOption(id="A", text="Duplicate answer"),
            GeneratedQuizOption(id="C", text="Wrong answer C"),
            GeneratedQuizOption(id="D", text="Wrong answer D"),
        ],
        correct_option_id="A",
        explanation="Because A is supported.",
        source_chunk_ids=[1],
    )

    with pytest.raises(QuizGenerationError):
        _to_quiz_item(
            item=item,
            user_id="demo-user",
            difficulty="medium",
            valid_source_ids={1},
        )


def test_retrieve_quiz_chunks_prefers_concept_sources(monkeypatch) -> None:
    concept_chunk = RetrievedChunk(
        chunk_id=11,
        document_id=2,
        course_id=4,
        filename="lecture.pdf",
        content="Supervised learning content.",
        metadata={},
        distance=0.1,
        similarity=0.9,
    )
    fallback_called = False

    def fake_concept_chunks(*args, **kwargs):  # type: ignore[no-untyped-def]
        return [concept_chunk]

    def fake_retrieve(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal fallback_called
        fallback_called = True
        return []

    monkeypatch.setattr(
        "app.services.quiz.get_concept_quiz_chunks",
        fake_concept_chunks,
    )
    monkeypatch.setattr("app.services.quiz.retrieve_relevant_chunks", fake_retrieve)

    chunks = _retrieve_quiz_chunks(
        db=None,  # type: ignore[arg-type]
        focus="supervised learning",
        user_id="demo-user",
        top_k=5,
        course_id=4,
        concept_id=7,
    )

    assert chunks == [concept_chunk]
    assert fallback_called is False


def test_grade_quiz_attempt_marks_correct_answer() -> None:
    item = _quiz_item()

    result = _grade_quiz_attempt(item=item, selected_option_id="b")

    assert result["selected_option_id"] == "B"
    assert result["selected_option_text"] == "Correct answer"
    assert result["correct_option_id"] == "B"
    assert result["is_correct"] is True


def test_grade_quiz_attempt_rejects_invalid_selection() -> None:
    item = _quiz_item()

    with pytest.raises(QuizAttemptError):
        _grade_quiz_attempt(item=item, selected_option_id="Z")


def _options() -> list[GeneratedQuizOption]:
    return [
        GeneratedQuizOption(id="A", text="Wrong answer A"),
        GeneratedQuizOption(id="B", text="Correct answer"),
        GeneratedQuizOption(id="C", text="Wrong answer C"),
        GeneratedQuizOption(id="D", text="Wrong answer D"),
    ]


def _quiz_item() -> QuizItem:
    return QuizItem(
        id=1,
        user_id="demo-user",
        question="Q?",
        answer="Correct answer",
        difficulty="medium",
        options=[option.model_dump() for option in _options()],
        correct_option_id="B",
        explanation="Because B is supported.",
        source_chunk_ids=[1],
        evidence_quote="Evidence.",
        question_type="conceptual",
        traceability_label="fully_traceable",
    )
