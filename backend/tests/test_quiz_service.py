import pytest

from app.services.quiz import QuizGenerationError, _parse_generated_quiz


def test_parse_generated_quiz_accepts_json() -> None:
    payload = _parse_generated_quiz(
        '{"items": [{"question": "Q?", "answer": "A.", "source_chunk_ids": [1]}]}'
    )

    assert payload.items[0].question == "Q?"
    assert payload.items[0].source_chunk_ids == [1]


def test_parse_generated_quiz_accepts_markdown_json_fence() -> None:
    payload = _parse_generated_quiz(
        '```json\n{"items": [{"question": "Q?", "answer": "A."}]}\n```'
    )

    assert payload.items[0].answer == "A."


def test_parse_generated_quiz_rejects_invalid_json() -> None:
    with pytest.raises(QuizGenerationError):
        _parse_generated_quiz("not json")
