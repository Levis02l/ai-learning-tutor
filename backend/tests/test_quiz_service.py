import pytest

from app.services.quiz import (
    GeneratedQuizItem,
    QuizGenerationError,
    _parse_generated_quiz,
    _to_quiz_item,
)


def test_parse_generated_quiz_accepts_json() -> None:
    payload = _parse_generated_quiz(
        '{"items": [{"question": "Q?", "answer": "A.", "source_chunk_ids": [1], '
        '"evidence_quote": "Evidence.", "question_type": "definition", '
        '"traceability_label": "fully_traceable"}]}'
    )

    assert payload.items[0].question == "Q?"
    assert payload.items[0].source_chunk_ids == [1]
    assert payload.items[0].evidence_quote == "Evidence."


def test_parse_generated_quiz_accepts_markdown_json_fence() -> None:
    payload = _parse_generated_quiz(
        '```json\n{"items": [{"question": "Q?", "answer": "A."}]}\n```'
    )

    assert payload.items[0].answer == "A."


def test_parse_generated_quiz_rejects_invalid_json() -> None:
    with pytest.raises(QuizGenerationError):
        _parse_generated_quiz("not json")


def test_to_quiz_item_preserves_traceable_sources() -> None:
    item = GeneratedQuizItem(
        question="Q?",
        answer="A.",
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


def test_to_quiz_item_downgrades_item_without_valid_sources() -> None:
    item = GeneratedQuizItem(
        question="Q?",
        answer="A.",
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
