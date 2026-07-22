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

The main intended variable is whether the answer is produced with access to
course evidence and grounding constraints. This must not be confused with
post-hoc evidence support. An ungrounded answer may still make claims that are
consistent with the course material, even though it did not retrieve or cite
that material during generation.

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
- course-supported claim rate;
- unsupported-by-course claim rate;
- citation precision, where citations are applicable;
- citation coverage, where citations are applicable;
- correct refusal rate;
- false refusal rate;
- false answer rate.

Do not interpret "no citation" as "unsupported by course material". These are
different concepts:

- `course-supported claim rate`: post-hoc judgement of whether the final claims
  are supported by the uploaded course material. This applies to both grounded
  and ungrounded conditions.
- `citation precision` and `citation coverage`: judgement of whether supplied
  citations support the claims. These are mainly applicable to grounded answers;
  for ungrounded answers they should normally be marked `N/A`, not `0`.

Automated metrics can assist with scoring, but answer correctness,
course-evidence support, citation correctness, and refusal correctness should be
human-reviewed for the final reported dataset.

## Human Annotation Rubric

Answer correctness:

- `2`: correct and sufficiently complete for the course material;
- `1`: partially correct but incomplete, vague, or missing an important caveat;
- `0`: incorrect, unsupported, or misleading.

Post-hoc course evidence support:

- `supported`: the final claim is supported by the uploaded course material,
  whether or not the answer explicitly cited it;
- `partially_supported`: the final claim is directionally supported but omits an
  important caveat or requires inference;
- `unsupported_by_course`: the final claim is not supported by the uploaded
  course material;
- `contradicted_by_course`: the final claim conflicts with the uploaded course
  material.

Generated claim support labels:

- `fully_supported`: directly supported by cited course evidence;
- `partially_supported`: plausible but requires inference or omits conditions;
- `unsupported`: not supported by the uploaded course material;
- `contradicted`: conflicts with the uploaded course material;
- `not_enough_information`: the case cannot be judged from available evidence.

Citation correctness:

- a citation is correct only if the cited evidence supports the specific claim;
- a citation is not correct merely because it comes from the same document or
  general topic.
- citation metrics are not applicable to the ungrounded condition unless an
  ungrounded baseline explicitly produces citations.

Refusal correctness:

- answerable cases should be answered from evidence;
- unanswerable cases should be refused or explicitly limited;
- partially answerable cases should answer the supported part and identify the
  limitation.
- semantic refusals count as refusals even if an API `answer_status` field says
  `answered`, for example "I cannot determine this from the uploaded material."

## Result Format

Each formal run should create a unique directory under
`backend/eval/results/{pilot|formal}/`, for example:

```text
backend/eval/results/pilot/grounding_v1_20260722_153012/
├── run_config.json
├── raw_results.json
├── raw_results.jsonl
├── summary.json
├── summary.csv
└── manifest.json
```

Each run should save:

- experiment config: model, temperature, top-k, prompt version, policy version,
  git commit, timestamp;
- raw outputs for both conditions;
- automatic metrics;
- human annotations;
- summary JSON and CSV.

Use a pilot run before a formal run:

```bash
cd backend
.venv/bin/python -m eval.run_answer_evaluation --run-type pilot --limit 5
```

Formal runs should use the frozen dataset and config:

```bash
cd backend
.venv/bin/python -m eval.run_answer_evaluation --run-type formal
```

The runner should preserve this result structure so summaries can be recomputed
from raw outputs later.

Automatic summaries separate answerable and unanswerable cases. Do not average
correct refusals into factual groundedness or citation precision. For final
reporting, use the human annotation template in
`backend/eval/annotations/grounding_v1_template.csv` to add post-hoc
course-evidence support and citation judgements.
