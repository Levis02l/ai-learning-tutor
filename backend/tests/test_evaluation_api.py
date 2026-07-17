from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app


def test_evaluation_answer_endpoint() -> None:
    client = TestClient(app)

    response = client.post(
        "/evaluation/answer",
        json={
            "expected_answerable": True,
            "response": {
                "query": "What is AI?",
                "user_id": "demo-user",
                "mode": "grounded_strict",
                "answer_status": "answered",
                "answer": "AI studies intelligent agents.",
                "claims": [
                    {
                        "claim": "AI studies intelligent agents.",
                        "source_chunk_ids": [82],
                        "support_level": "fully_supported",
                        "evidence_quote": "AI is the field...",
                    }
                ],
                "overall_groundedness": 1.0,
                "evidence_state": {
                    "evidence_strength": "high",
                    "source_coverage": 1.0,
                    "supported_claim_count": 1,
                    "unsupported_claim_count": 0,
                    "contradicted_claim_count": 0,
                    "answer_status": "answered",
                },
                "sources": [],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["supported_claim_count"] == 1


def test_evaluation_quiz_endpoint() -> None:
    client = TestClient(app)
    created_at = datetime(2026, 6, 21, 12, 0, 0).isoformat()

    response = client.post(
        "/evaluation/quiz",
        json={
            "items": [
                {
                    "id": 1,
                    "user_id": "demo-user",
                    "question": "Q?",
                    "answer": "A.",
                    "difficulty": "medium",
                    "source_chunk_ids": [82],
                    "evidence_quote": "Evidence.",
                    "question_type": "conceptual",
                    "traceability_label": "fully_traceable",
                    "created_at": created_at,
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["traceable_item_rate"] == 1.0
