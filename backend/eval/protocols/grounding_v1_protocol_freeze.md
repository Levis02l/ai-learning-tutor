# Grounding V1-A Evaluation Protocol Freeze

Status: frozen for formal dataset construction

Freeze date: 2026-07-22

Frozen implementation commit: `dcc2fcf6c71be6322eee2be9e5a9d42b7ca6ec5f`

Pilot run: `backend/eval/results/pilot/grounding_v1_pilot_6case`

## Scope

This protocol evaluates whether a course-material-grounded tutor improves reliability, traceability, and refusal behaviour compared with an otherwise equivalent ungrounded LLM baseline.

The primary comparison is:

- Grounded RAG tutor: retrieves course-scoped evidence and answers with citation-backed claims.
- Ungrounded baseline: answers the same question without course evidence or citations.

The pilot set was used only to develop and validate the protocol. Pilot cases must not be included in the main formal results.

## Frozen Configuration

- Runner version: `eval_v1_a2_1`
- Dataset: `backend/eval/datasets/grounding_v1.json`
- Dataset SHA256: `7dbaea2fe77a5b821f92540fc725f4a887df0b0239838144169c3faae395ec99`
- Config: `backend/eval/configs/grounding_v1.config.json`
- LLM provider: `openai`
- LLM model: `gpt-5.4-mini`
- Temperature: `0.0`
- Embedding model: `text-embedding-3-small`
- Retrieval top_k: `5`
- Prompt version: `grounding_v1`
- Policy version: `not_applicable_for_chat_compare`
- Max transient retries per case: `2`
- Initial retry delay: `2.0` seconds
- Conditions: `grounded`, `ungrounded`

## Validated Pilot Properties

The final 6-case pilot validated:

- answerable, partially answerable, and unanswerable case handling;
- course-scoped retrieval;
- grounded citation capture;
- semantic refusal detection, including Unicode apostrophes such as `can't`;
- separation of refusal metrics from factual citation metrics;
- bounded transient retry metadata;
- run reproducibility metadata, including model, embedding, git commit, and dataset hash.

Final pilot outcome:

- case count: `6`
- successful cases: `6`
- failed cases: `0`
- triggered retries: `0`

## Frozen Metrics

For answerable cases:

- answer correctness;
- post-hoc course-supported claim rate;
- unsupported-by-course claim rate;
- citation precision for grounded outputs;
- citation coverage for grounded outputs;
- false refusal rate.

For partially answerable cases:

- supported part answered;
- unsupported part limited;
- answer correctness;
- post-hoc course-supported claim rate;
- unsupported-by-course claim rate;
- citation precision and citation coverage for grounded outputs.

For unanswerable cases:

- semantic refusal;
- correct refusal;
- false answer rate;
- false refusal rate.

Citation metrics are applicable to grounded outputs. Ungrounded outputs do not provide citations, so citation precision and citation coverage should be recorded as `N/A`, not `0`.

Automatic claim and groundedness metrics are diagnostic signals. Dissertation results should use human-reviewed correctness, post-hoc course support, citation verification, and refusal behaviour as the primary evidence.

## Known Pilot Findings

`grounding_003` remained a useful qualitative traceability limitation. The grounded natural-language answer correctly stated that K-means does not guarantee the global optimum, and the user-visible citation supported the core point. However, one internal claim-to-source mapping linked a local-optimum claim to a K-medoids/K-medians chunk. This should be discussed as a traceability limitation, not fixed by tuning prompts against the pilot set.

`grounding_001` showed that generated structured claims can include diagnostic claims that are supported by course evidence but are not central to the final answer. This reinforces that automatic claim metrics should be interpreted alongside human audit.

## Freeze Rules

After this freeze, do not modify the following for the formal V1-A experiment unless a genuine invalidating bug is found:

- grounded prompt;
- ungrounded prompt;
- retrieval top_k;
- grounding thresholds;
- refusal behaviour;
- answerability definitions;
- metric definitions;
- human annotation rubric.

Allowed changes after freeze:

- formal held-out dataset creation;
- bug fixes that do not change experimental behaviour;
- logging and reproducibility improvements;
- documentation;
- human annotation files;
- analysis notebooks or scripts.

## Next Step

Create a new formal held-out dataset. The pilot cases are development cases and should not be included in the main statistical results.

Recommended formal split:

- 30 answerable cases;
- 10 partially answerable cases;
- 10 unanswerable cases.

Each formal case should include:

- `case_id`;
- `course_id`;
- `question`;
- `answerability`;
- `reference_answer`;
- `gold_evidence`;
- `category`;
- `concept`;
- `difficulty`;
- `notes`.
