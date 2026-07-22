# Evaluation Protocol

This directory contains the formal evaluation assets for the dissertation. The
project is now in feature freeze: new code here should support experiment
validity, reproducibility, result export, or bug fixes only.

## Evaluation Roadmap

1. V1-A Grounding and reliability
   - Compare grounded RAG tutoring with an otherwise equivalent ungrounded LLM
     baseline.
   - Focus on reliability, citation traceability, unsupported claims, and
     refusal behaviour.
2. V1-B Adaptive policy
   - Evaluate whether learner state changes the selected teaching strategy in
     controlled scenarios.
3. V1-C Misconception-aware teaching
   - Evaluate whether responses address detected misconception types without
     weakening grounding.
4. V1-D Closed-loop Socratic outcome
   - Evaluate whether Socratic interventions produce objective completion-check
     evidence and feed future policy decisions.

## V1-A Research Question

Does evidence-grounded tutoring improve reliability, traceability, and refusal
behaviour compared with an otherwise equivalent ungrounded LLM baseline?

## V1-A Conditions

Each evaluation case is run under two conditions:

- `ungrounded`: the same question is answered without course retrieval.
- `grounded`: the question is answered using course-scoped retrieval, evidence
  constraints, citations, and refusal rules.

For a fair comparison, keep these settings aligned across both conditions:

- same LLM provider and model;
- same temperature;
- same question text;
- same user and course;
- same output schema where applicable.

The main intended variable is whether the answer is grounded in uploaded course
evidence.

## Dataset Schema

The formal V1-A dataset lives in
`backend/eval/datasets/grounding_v1.json` and is described by
`backend/eval/datasets/grounding_v1.schema.json`.

Each case should include:

- `case_id`: stable case identifier, such as `grounding_001`;
- `course_id`: local course workspace used for the run;
- `question`: exact prompt shown to both conditions;
- `answerability`: `answerable`, `partially_answerable`, or `unanswerable`;
- `reference_answer`: concise human-written answer, empty only for
  unanswerable cases;
- `gold_evidence`: source content that supports the reference answer;
- `category`: question type, for example `factual`, `definition`,
  `comparison`, `application`, or `refusal`;
- `concept`: target concept name when known;
- `difficulty`: `easy`, `medium`, or `hard`;
- `notes`: evaluator notes, expected caveats, or ambiguity.

Do not treat raw database `chunk_id` values as the only gold standard. Chunk IDs
are implementation details and may change after re-ingestion. Use
`gold_evidence.relevant_text` as the human-readable evidence definition. Optional
chunk IDs may be included only as a convenience for automation.

## V1-A Metrics

Use a small number of metrics that can be explained clearly in the dissertation:

- answer correctness;
- claim support rate;
- unsupported claim rate;
- citation precision;
- citation coverage;
- correct refusal rate;
- false refusal rate;
- false answer rate.

Automated metrics can assist with scoring, but answer correctness, citation
correctness, and refusal correctness should be human-reviewed for the final
reported dataset.

## Human Annotation Rubric

Answer correctness:

- `2`: correct and sufficiently complete for the course material;
- `1`: partially correct but incomplete, vague, or missing an important caveat;
- `0`: incorrect, unsupported, or misleading.

Claim support:

- `fully_supported`: directly supported by cited course evidence;
- `partially_supported`: plausible but requires inference or omits conditions;
- `unsupported`: not supported by the uploaded course material;
- `contradicted`: conflicts with the uploaded course material;
- `not_enough_information`: the case cannot be judged from available evidence.

Citation correctness:

- a citation is correct only if the cited evidence supports the specific claim;
- a citation is not correct merely because it comes from the same document or
  general topic.

Refusal correctness:

- answerable cases should be answered from evidence;
- unanswerable cases should be refused or explicitly limited;
- partially answerable cases should answer the supported part and identify the
  limitation.

## Result Format

Each formal run should save:

- experiment config: model, temperature, top-k, prompt version, policy version,
  git commit, timestamp;
- raw outputs for both conditions;
- automatic metrics;
- human annotations;
- summary JSON and CSV.

The first implementation can continue using `run_answer_evaluation.py`, but
future runner changes should preserve this result structure.
