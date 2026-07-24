import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.llm.provider import LLMProviderError, LLMResponse
from app.services.retrieval import RetrievedChunk
from eval.run_adaptive_policy_evaluation import (
    DEFAULT_FORMAL_CONFIG_PATH,
    RecordingRetryProvider,
    _annotation_response_view,
    _execute_condition_safely,
    _expected_provider_event_count,
    _fixture_for,
    _planned_canonical_execution_count,
    _reuse_condition_artifact,
    _review_fixture_for,
    _validate_runtime_config,
    build_adaptive_decision,
    build_baseline_decision,
    build_blinded_artifacts,
    load_config,
    rollback_only_session,
    write_run_artifacts,
)
from eval.validate_adaptive_policy_dataset import (
    DEFAULT_DATASET_PATH as DEFAULT_FORMAL_DATASET_PATH,
)
from eval.validate_adaptive_policy_dataset import (
    load_and_validate_dataset,
)
from eval.validate_adaptive_policy_pilot import (
    DEFAULT_DATASET_PATH,
    load_and_validate_pilot,
)


class _FailOnceProvider:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.calls == 1:
            raise LLMProviderError("temporary provider failure")
        return LLMResponse(text='{"answer": "ok"}')


class _StaticTutorProvider:
    def generate(self, **kwargs):  # type: ignore[no-untyped-def]
        return LLMResponse(
            text=(
                '{"answer_status":"answered","answer":"Tutor response",'
                '"claims":[]}'
            )
        )


def test_frozen_state_builds_expected_adaptive_and_baseline_decisions() -> None:
    dataset = load_and_validate_pilot()
    scenario = next(
        item
        for item in dataset.scenarios
        if item.case_id == "adaptive_pilot_p02_high"
    )
    chunks = [_chunk(chunk_id) for chunk_id in [98, 99, 100]]

    adaptive = build_adaptive_decision(
        dataset=dataset,
        scenario=scenario,
        chunks=chunks,
    )
    baseline = build_baseline_decision(
        adaptive_decision=adaptive,
        dataset=dataset,
        scenario=scenario,
        chunks=chunks,
    )

    assert (adaptive.selected_action, adaptive.response_strategy) == (
        "quiz",
        "challenging",
    )
    assert (baseline.selected_action, baseline.response_strategy) == (
        "explain",
        "guided",
    )
    assert adaptive.learner_state_snapshot == baseline.learner_state_snapshot
    assert adaptive.evidence_state_snapshot["top_similarity"] is None
    assert baseline.misconception_snapshot is None


def test_identical_policy_reuses_one_generation_artifact() -> None:
    dataset = load_and_validate_pilot()
    scenario = next(
        item
        for item in dataset.scenarios
        if item.case_id == "adaptive_pilot_p01_medium"
    )
    decision = build_adaptive_decision(
        dataset=dataset,
        scenario=scenario,
        chunks=[_chunk(chunk_id) for chunk_id in [91, 92, 93]],
    )
    baseline = build_baseline_decision(
        adaptive_decision=decision,
        dataset=dataset,
        scenario=scenario,
        chunks=[_chunk(chunk_id) for chunk_id in [91, 92, 93]],
    )
    source = {
        "condition": "adaptive",
        "generation_execution_id": "one_execution",
        "reused_generation": False,
        "canonical_condition": "adaptive",
        "decision": {},
        "response": {"answer": "same response"},
        "provider_event_ids": ["provider_call_0001"],
        "latency_seconds": 0.1,
        "error": None,
    }

    reused = _reuse_condition_artifact(
        source=source,
        condition="baseline",
        decision=baseline,
    )

    assert reused["generation_execution_id"] == "one_execution"
    assert reused["reused_generation"] is True
    assert reused["response"] == source["response"]
    assert reused["provider_event_ids"] == source["provider_event_ids"]


def test_baseline_prompts_are_invariant_across_learner_states() -> None:
    dataset = load_and_validate_pilot()
    provider = RecordingRetryProvider(
        _StaticTutorProvider(),
        max_retries=0,
        retry_initial_delay=0.0,
    )
    artifacts = []
    raw_state_snapshots = []
    test_engine = create_engine("sqlite+pysqlite:///:memory:")

    for case_id in ["adaptive_pilot_p02_medium", "adaptive_pilot_p02_high"]:
        scenario = next(
            item for item in dataset.scenarios if item.case_id == case_id
        )
        chunks = [_chunk(chunk_id) for chunk_id in [98, 99, 100]]
        adaptive = build_adaptive_decision(
            dataset=dataset,
            scenario=scenario,
            chunks=chunks,
        )
        baseline = build_baseline_decision(
            adaptive_decision=adaptive,
            dataset=dataset,
            scenario=scenario,
            chunks=chunks,
        )
        raw_state_snapshots.append(baseline.learner_state_snapshot)
        with rollback_only_session(test_engine) as db:
            artifacts.append(
                _execute_condition_safely(
                    db=db,
                    case_id=case_id,
                    condition="baseline",
                    decision=baseline,
                    fixture=_fixture_for(
                        dataset=dataset,
                        scenario=scenario,
                    ),
                    review_fixture=None,
                    provider=provider,
                )
            )

    assert raw_state_snapshots[0] != raw_state_snapshots[1]
    assert all(artifact["error"] is None for artifact in artifacts)
    assert (
        artifacts[0]["generation_decision"]["learner_state_snapshot"]
        == artifacts[1]["generation_decision"]["learner_state_snapshot"]
    )
    assert len(provider.events) == 2
    assert (
        provider.events[0]["system_prompt_sha256"]
        == provider.events[1]["system_prompt_sha256"]
    )
    assert (
        provider.events[0]["user_prompt_sha256"]
        == provider.events[1]["user_prompt_sha256"]
    )


def test_review_condition_uses_frozen_queue_without_provider_call() -> None:
    dataset = load_and_validate_pilot()
    scenario = next(
        item
        for item in dataset.scenarios
        if item.case_id == "adaptive_pilot_p03_review_true"
    )
    chunks = [_chunk(chunk_id) for chunk_id in [104, 105, 106]]
    decision = build_adaptive_decision(
        dataset=dataset,
        scenario=scenario,
        chunks=chunks,
    )
    delegate = _FailOnceProvider()
    provider = RecordingRetryProvider(
        delegate,
        max_retries=0,
        retry_initial_delay=0.0,
    )
    test_engine = create_engine("sqlite+pysqlite:///:memory:")

    with rollback_only_session(test_engine) as db:
        artifact = _execute_condition_safely(
            db=db,
            case_id=scenario.case_id,
            condition="adaptive",
            decision=decision,
            fixture=_fixture_for(dataset=dataset, scenario=scenario),
            review_fixture=_review_fixture_for(
                dataset=dataset,
                scenario=scenario,
            ),
            provider=provider,
        )

    assert artifact["error"] is None
    assert artifact["response"]["answer_status"] == "review_ready"
    assert artifact["response"]["review_items"][0]["question"].startswith(
        "How does the Silhouette Method"
    )
    assert artifact["provider_event_ids"] == []
    assert delegate.calls == 0


def test_recording_provider_retries_and_records_raw_output() -> None:
    delegate = _FailOnceProvider()
    provider = RecordingRetryProvider(
        delegate,
        max_retries=2,
        retry_initial_delay=0.0,
    )
    provider.set_context(case_id="pilot_case", condition="adaptive")

    response = provider.generate(
        system_prompt="system",
        user_prompt="user",
        max_tokens=100,
        temperature=0.2,
    )

    assert response.text == '{"answer": "ok"}'
    assert delegate.calls == 2
    assert len(provider.events) == 1
    assert provider.events[0]["retry_count"] == 1
    assert provider.events[0]["raw_response"] == '{"answer": "ok"}'
    assert len(provider.events[0]["attempts"]) == 2


def test_rollback_only_session_does_not_persist_commits() -> None:
    test_engine = create_engine("sqlite+pysqlite:///:memory:")
    with test_engine.begin() as connection:
        connection.execute(text("CREATE TABLE records (id INTEGER PRIMARY KEY)"))

    with rollback_only_session(test_engine) as db:
        db.execute(text("INSERT INTO records (id) VALUES (1)"))
        db.commit()
        assert db.scalar(text("SELECT COUNT(*) FROM records")) == 1

    with test_engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM records")) == 0


def test_blinded_artifacts_are_deterministic_and_hide_conditions() -> None:
    results = [
        {
            "case_id": f"pilot_case_{index}",
            "group_id": "P01",
            "learner_vignette": "Frozen learner context.",
            "question": "Question?",
            "identical_policy_control": False,
            "conditions": {
                "adaptive": _condition_artifact("response one"),
                "baseline": _condition_artifact("response two"),
            },
        }
        for index in range(8)
    ]

    blinded_one, reveal_one = build_blinded_artifacts(
        results=results,
        seed="fixed-seed",
    )
    blinded_two, reveal_two = build_blinded_artifacts(
        results=results,
        seed="fixed-seed",
    )

    assert blinded_one == blinded_two
    assert reveal_one == reveal_two
    assert "adaptive" not in str(blinded_one).lower()
    assert sum(item["A"] == "adaptive" for item in reveal_one) == 4
    assert sum(item["B"] == "adaptive" for item in reveal_one) == 4
    assert {
        "response_A_intent_fidelity",
        "response_B_intent_fidelity",
        "response_A_response_relevance",
        "response_B_response_relevance",
    }.issubset(blinded_one[0])


def test_blinded_projection_contains_only_initial_learner_visible_items() -> None:
    artifact = _condition_artifact("Ready.")
    artifact["response"]["quiz_items"] = [
        {
            "id": 10,
            "question": "Which objective is minimized?",
            "options": [
                {"id": "A", "text": "WCSS"},
                {"id": "B", "text": "Entropy"},
            ],
            "answer": "WCSS",
            "correct_option_id": "A",
            "explanation": "K-means minimizes WCSS.",
        }
    ]
    artifact["response"]["review_items"] = [
        {
            "quiz_item_id": 20,
            "question": "How is silhouette width interpreted?",
            "review_record_id": 30,
        }
    ]

    projected = _annotation_response_view(artifact)

    assert projected is not None
    assert projected["quiz_items"] == [
        {
            "question": "Which objective is minimized?",
            "options": [
                {"id": "A", "text": "WCSS"},
                {"id": "B", "text": "Entropy"},
            ],
        }
    ]
    assert projected["review_items"] == [
        {"question": "How is silhouette width interpreted?"}
    ]
    assert "explanation" not in projected["quiz_items"][0]
    assert "quiz_item_id" not in projected["review_items"][0]


def test_run_artifacts_record_effective_runtime_and_git_state(
    tmp_path: Path,
) -> None:
    dataset = load_and_validate_pilot()
    config_path = (
        DEFAULT_DATASET_PATH.parent.parent
        / "configs"
        / "adaptive_policy_v1.config.json"
    )
    config = load_config(config_path)

    write_run_artifacts(
        output_dir=tmp_path,
        dataset=dataset,
        config=config,
        dataset_path=DEFAULT_DATASET_PATH,
        config_path=config_path,
        results=[],
        provider_events=[],
        run_id="provenance_test",
        run_type="pilot",
        git_commit="abc123",
        git_clean=True,
        effective_max_retries=5,
        effective_retry_initial_delay=0.25,
    )

    manifest = json.loads(
        (tmp_path / "manifest.json").read_text(encoding="utf-8")
    )
    run_config = json.loads(
        (tmp_path / "run_config.json").read_text(encoding="utf-8")
    )

    assert manifest["git"] == {"commit": "abc123", "clean": True}
    assert manifest["effective_generation_runtime"] == {
        "max_retries": 5,
        "retry_initial_delay_seconds": 0.25,
    }
    assert run_config["runtime"]["effective_generation_runtime"] == {
        "max_retries": 5,
        "retry_initial_delay_seconds": 0.25,
    }


def test_formal_runtime_config_locks_dataset_model_and_execution_counts() -> None:
    dataset = load_and_validate_dataset()
    config = load_config(DEFAULT_FORMAL_CONFIG_PATH)

    _validate_runtime_config(
        run_type="formal",
        dataset=dataset,
        dataset_path=DEFAULT_FORMAL_DATASET_PATH,
        config=config,
    )

    assert _planned_canonical_execution_count(dataset) == 44
    assert _expected_provider_event_count(dataset) == 49


def test_formal_runtime_config_rejects_changed_dataset_hash() -> None:
    dataset = load_and_validate_dataset()
    config = load_config(DEFAULT_FORMAL_CONFIG_PATH)
    config["formal_freeze"]["dataset_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="dataset SHA256"):
        _validate_runtime_config(
            run_type="formal",
            dataset=dataset,
            dataset_path=DEFAULT_FORMAL_DATASET_PATH,
            config=config,
        )


def test_formal_dataset_builds_registered_adaptive_and_baseline_decisions() -> None:
    dataset = load_and_validate_dataset()
    scenario = next(
        item
        for item in dataset.scenarios
        if item.case_id == "adaptive_formal_g01_low"
    )
    fixture = _fixture_for(dataset=dataset, scenario=scenario)
    chunks = [_chunk(item.chunk_id) for item in fixture.ordered_chunks]

    adaptive = build_adaptive_decision(
        dataset=dataset,
        scenario=scenario,
        chunks=chunks,
    )
    baseline = build_baseline_decision(
        adaptive_decision=adaptive,
        dataset=dataset,
        scenario=scenario,
        chunks=chunks,
    )

    assert (adaptive.selected_action, adaptive.response_strategy) == (
        "explain",
        "scaffolded",
    )
    assert (baseline.selected_action, baseline.response_strategy) == (
        "explain",
        "guided",
    )


def test_formal_artifacts_record_the_frozen_dataset_lock(
    tmp_path: Path,
) -> None:
    dataset = load_and_validate_dataset()
    config = load_config(DEFAULT_FORMAL_CONFIG_PATH)

    write_run_artifacts(
        output_dir=tmp_path,
        dataset=dataset,
        config=config,
        dataset_path=DEFAULT_FORMAL_DATASET_PATH,
        config_path=DEFAULT_FORMAL_CONFIG_PATH,
        results=[],
        provider_events=[],
        run_id="formal_provenance_test",
        run_type="formal",
        git_commit="freeze123",
        git_clean=True,
        effective_max_retries=2,
        effective_retry_initial_delay=2.0,
    )

    manifest = json.loads(
        (tmp_path / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["run_type"] == "formal"
    assert manifest["formal_dataset_lock"] == {
        "dataset_id": "adaptive_policy_v1_formal_candidate",
        "dataset_sha256": (
            "3221a85d87ebb788a603e93d3e48343edaf02d2c1595a3574558c4be30bf36db"
        ),
        "freeze_version": "v1_b_final_freeze_1",
        "candidate_commit": "7ab5be7923e1cd1a8d9b85b8432278f855c588a2",
    }


def test_recording_provider_raises_after_bounded_retries() -> None:
    class AlwaysFail:
        def generate(self, **kwargs):  # type: ignore[no-untyped-def]
            raise LLMProviderError("still failing")

    provider = RecordingRetryProvider(
        AlwaysFail(),
        max_retries=1,
        retry_initial_delay=0.0,
    )
    provider.set_context(case_id="pilot_case", condition="baseline")

    with pytest.raises(LLMProviderError, match="still failing"):
        provider.generate(system_prompt="s", user_prompt="u")

    assert len(provider.events) == 1
    assert provider.events[0]["retry_count"] == 1
    assert provider.events[0]["error"]["type"] == "LLMProviderError"


def _chunk(chunk_id: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=3,
        course_id=2,
        filename="lecture.pdf",
        content=f"Frozen evidence {chunk_id}.",
        metadata={"chunk_index": chunk_id},
        distance=0.0,
        similarity=0.0,
    )


def _condition_artifact(answer: str) -> dict:
    return {
        "condition": "hidden",
        "generation_execution_id": answer,
        "reused_generation": False,
        "canonical_condition": "hidden",
        "decision": {},
        "response": {
            "answer_status": "answered",
            "answer": answer,
            "quiz_items": [],
            "suggested_next_step": "",
        },
        "provider_event_ids": [],
        "latency_seconds": 0.1,
        "error": None,
    }
