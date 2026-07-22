# Grounding V1 Formal Dataset Audit

## Verdict

**READY FOR DATASET FREEZE / FORMAL RUN**, subject only to repository schema validation and copying this file into the project.

- Total cases: 50
- Answerable: 30
- Partially answerable: 10
- Unanswerable: 10
- SHA256 of `grounding_v1_formal.json`: `40e347930fbe0d87268e2a33c14cea215ebd57933173171f412af4d2c1d954bd`

## Source

All answerable and partially answerable cases are grounded in:

`Lecture_notes_in_Unsupervised_Learning_2026_02_19.pdf`

The lecture covers K-means, K selection, K-medians/K-medoids, metric geometry, kernel K-means/RKHS, PCA/PCR, and mathematical background.

## Audit actions performed

1. Checked all 50 cases for answerability semantics and source scope.
2. Preserved the frozen V1-A protocol: 30 answerable / 10 partial / 10 unanswerable.
3. Replaced two partial cases that were too close to pilot-development cases:
   - `grounding_formal_031`: now tests unknown numerical Voronoi boundary vs supported general boundary rule.
   - `grounding_formal_032`: now tests non-uniqueness of the even-sample K-medians minimiser.
4. Strengthened two unanswerable cases:
   - `grounding_formal_041`: scikit-learn default `n_init`, absent from the lecture.
   - `grounding_formal_047`: exact `kernlab` package version, absent from the lecture.
5. Verified by full-text search that the unanswerable targets are not stated in the uploaded lecture (e.g. random seed, Big-O PAM runtime, PCA p-value threshold, confidence interval procedure, train/validation/test split, dropout, GPU requirement, scikit-learn `n_init`, exact kernlab version).
6. Kept the six pilot questions out of the formal dataset as primary test cases.

## Distribution

### Difficulty
{'easy': 7, 'medium': 28, 'hard': 15}

### Category
{'factual': 8, 'explanation': 9, 'reasoning': 3, 'definition': 6, 'comparison': 3, 'application': 1, 'limitation': 10, 'refusal': 10}

## Freeze rules

After this dataset is copied into the repository and its schema validates:

- Do not edit questions, answerability labels, reference answers, evidence pages, or difficulty based on observed formal results.
- Do not tune prompts, retrieval thresholds, top-k, refusal logic, or evaluation metrics using these 50 cases.
- Record dataset SHA256, git commit, model, embedding model, prompt version, top-k, retry policy, and run timestamp in the formal manifest.
- Run Grounded and Ungrounded under the same frozen model/runtime configuration.
- Treat automatic generation-grounding metrics as diagnostics; use human-reviewed correctness, post-hoc course support, citation quality, partial-answer behaviour, and refusal behaviour as the primary evaluation evidence.

## Evidence note

`gold_evidence.relevant_text` is a concise page-anchored evidence summary for auditability, not a replacement for checking the underlying page/chunk during human annotation. `chunk_ids` remain empty so the dataset is not tied to one particular ingestion/chunking run.

## Recommended next action

Copy `grounding_v1_formal.json` into the formal dataset path, run schema/tests only, compute/confirm the SHA256 in-repo, commit a dataset-freeze commit, and then perform the formal 50-case run once under the frozen V1-A protocol.
