import pytest

from app.models.quiz import QuizItem
from app.services.quiz import (
    GeneratedQuizItem,
    GeneratedQuizOption,
    QuizAttemptError,
    QuizGenerationError,
    _grade_quiz_attempt,
    _parse_generated_quiz,
    _to_quiz_item,
)


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
