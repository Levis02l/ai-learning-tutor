# Grounding V1-A Formal Dataset Freeze

Status: frozen for formal experiment execution

Freeze date: 2026-07-22

## Repository Files

- Formal dataset: `backend/eval/datasets/grounding_v1_formal.json`
- Human review copy: `backend/eval/annotations/grounding_v1_formal_review.csv`
- Dataset audit: `backend/eval/protocols/grounding_v1_formal_dataset_audit.md`

## Repository SHA256

`backend/eval/datasets/grounding_v1_formal.json`

```text
40e347930fbe0d87268e2a33c14cea215ebd57933173171f412af4d2c1d954bd
```

This matches the approved source file hash recorded before repository placement.

## Validation

Validation performed after repository placement:

- runner loader accepted the dataset;
- total cases: `50`;
- answerable cases: `30`;
- partially answerable cases: `10`;
- unanswerable cases: `10`;
- all `case_id` values are unique;
- formal case IDs do not overlap with the 6 pilot case IDs;
- all answerable and partially answerable cases include a non-empty `reference_answer`;
- all answerable and partially answerable cases include non-empty `gold_evidence`;
- all unanswerable cases have empty `reference_answer` and empty `gold_evidence`;
- review CSV contains 50 rows and matches the JSON case IDs.

## Plumbing Notes

The approved formal dataset includes optional `gold_evidence.page` integers for auditability. The dataset schema was updated to allow this optional field. No question, answerability label, reference answer, gold evidence text, category, concept, difficulty, or note was rewritten, regenerated, paraphrased, reordered, or rebalanced.

The existing evaluation runner already supports selecting this dataset with `--cases`; no runner semantics were changed.

## Formal Run Command

Do not run until ready for the formal V1-A experiment.

```bash
cd backend
.venv/bin/python -m eval.run_answer_evaluation \
  --run-type formal \
  --cases eval/datasets/grounding_v1_formal.json \
  --course-id 2 \
  --timeout 180 \
  --run-id grounding_v1_formal
```

## Freeze Rules

After this freeze, do not edit the formal dataset based on observed formal results. Do not tune prompts, retrieval thresholds, top-k, refusal logic, or evaluation metrics using these 50 formal cases.
