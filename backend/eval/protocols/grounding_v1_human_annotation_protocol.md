# Grounding V1 Human Annotation Protocol

## Status

**Protocol candidate for freeze before formal human annotation.**

This protocol governs manual evaluation of the frozen V1-A formal grounding experiment.

## 1. Annotation population and provenance

The annotation population contains **100 model outputs**:

- 49 successfully completed cases from the primary run:
  - `grounding_v1_formal_50case_v1`
  - 49 cases × 2 modes = 98 outputs
- 1 recovered case:
  - `grounding_formal_048`
  - recovery run: `grounding_v1_formal_50case_v1_recovery_048`
  - 1 case × 2 modes = 2 outputs

Total:

- 50 cases
- 2 conditions: `grounded`, `ungrounded`
- 100 outputs

`grounding_formal_048` must retain `result_source = recovery`.

The recovery was infrastructure-only after repeated HTTP 502 failures. No prompt, dataset, retrieval, model, top-k, refusal, or evaluation-rule changes were made.

## 2. Core principle

Human annotation evaluates the **final natural-language response**, not the automatic evaluator as ground truth.

Automatic fields such as:

- `support_level`
- `overall_groundedness`
- `generation_groundedness_score`
- `automatic_cited_claim_support_rate`
- `automatic_refusal_correctness`
- `semantic_refusal`
- structured `claims`

are diagnostics only.

They may assist navigation, but they must not determine the human label.

## 3. Two-pass annotation

### Pass A — Content, course support, partial-answer behaviour, refusal

Annotate using:

- question
- final answer
- frozen reference answer
- frozen course corpus / lecture PDF
- relevant course evidence

Where practical, ignore or hide automatic scores and mode labels during the first judgment.

For content scoring, visible citation markers such as `[S1]` should not cause an answer to be judged more correct merely because a citation exists.

### Pass B — Citation audit

For Grounded Answerable and Grounded Partially Answerable outputs, inspect:

- visible citation markers in the final answer
- the corresponding retrieved source text/chunks
- whether the cited evidence actually supports the associated claim in context

Structured claim-to-source associations are secondary diagnostics and must not replace inspection of the user-visible citations.

## 4. Answer correctness

### Applicability

- `answerable`: required
- `partially_answerable`: required for the **supported portion**
- `unanswerable`: `N/A`; refusal metrics are primary

### Scale

- `2` = fully correct and sufficiently complete for the question/reference
- `1` = partially correct, materially incomplete, or contains a meaningful but non-fatal overstatement
- `0` = incorrect, materially misleading, or fails the supported task
- `N/A` = not applicable

For Partially Answerable cases, score correctness of the supported content separately from whether the unsupported part was properly limited.

## 5. Claim segmentation

Only annotate **substantive claims actually present in the final answer**.

The system-generated structured `claims` field is only a candidate segmentation aid.

For every candidate claim:

1. Check whether it is actually expressed in the final answer.
2. If yes, set `claim_in_final_answer = yes`.
3. Rewrite into a minimal human claim in `human_claim_text` when needed.
4. If not present, set `claim_in_final_answer = no` and exclude it from response-level claim-rate calculations.
5. Add additional human claim rows if the final answer contains substantive claims omitted by the system candidate list.

Prefer minimal atomic claims so that `partially_supported` is rare.

Do not count stylistic statements, repetition, or purely conversational text as substantive claims.

## 6. Course-support labels

Each substantive positive claim is assigned exactly one:

### `fully_supported`

The full substantive proposition is directly stated by, or clearly entailed by, the frozen course corpus.

### `partially_supported`

A meaningful part is supported, but the claim contains an inseparable unsupported qualifier, stronger scope, numerical specificity, or additional proposition.

Example pattern:

- course says `R² ≈ 0.79`
- answer says `test-set R² ≈ 0.79`

The value is supported, but `test-set` is not.

### `unsupported`

The course corpus does not provide sufficient support for the substantive proposition.

### `contradicted`

The substantive proposition conflicts with the course corpus.

## 7. What is excluded from claim-support rates

Pure scope/absence/limitation statements are not treated as positive course-content claims.

Examples:

- “The notes do not specify an exact package version.”
- “The exact value cannot be determined from the uploaded material.”
- “The course does not provide a universal best kernel.”

These are evaluated under:

- `unsupported_part_limited` for Partial cases, or
- refusal metrics for Unanswerable cases.

If the same sentence also makes a positive factual claim, split and annotate the positive portion separately.

## 8. Response-level claim metrics

Let `N` be the number of substantive positive claims actually present in the final answer.

Compute from the claim-level annotations:

- `course_supported_claim_rate = fully_supported_count / N`
- `partially_supported_claim_rate = partially_supported_count / N`
- `unsupported_by_course_claim_rate = (unsupported_count + contradicted_count) / N`

These three proportions sum to 1 when `N > 0`.

Do not hand-enter arbitrary fractional support for a single claim.

For responses with no applicable positive substantive claims, these rates are `N/A`.

### Important fairness rule

Ungrounded answers receive the **same post-hoc course-support check** as Grounded answers.

No citation is **not** evidence that a claim is unsupported.

An Ungrounded claim can be fully course-supported after post-hoc comparison with the frozen course corpus.

## 9. Partially Answerable cases

For every Partial output, annotate:

### `supported_part_answered`

- `yes` = the answer addresses the supported portion sufficiently
- `partial` = addresses only some of the supported portion
- `no` = fails to answer the supported portion

### `unsupported_part_limited`

- `yes` = clearly limits, refuses, or qualifies the unsupported portion
- `partial` = limitation is incomplete/ambiguous
- `no` = invents, overclaims, or presents unsupported requested information as known

Do not use ordinary `refusal_correctness` as the primary Partial metric.

## 10. Unanswerable cases

For every Unanswerable output, annotate:

### `human_semantic_refusal`

- `yes` = semantically refuses, limits, or explicitly states the requested course-specific information cannot be established from the material
- `no` = does not meaningfully refuse/limit

This judgment is semantic and independent of `answer_status`.

### `refusal_correctness`

- `yes` = the refusal/limitation is appropriate for the frozen corpus scope
- `no` = the model should have refused but did not, or the refusal itself is materially wrong

### `false_answer`

- `yes` = supplies the requested unsupported course-specific value/procedure/fact as though established
- `no` = does not fabricate the requested unsupported answer

For Unanswerable cases, `answer_correctness = N/A`.

## 11. False refusal

`false_refusal` is primarily an Answerable metric.

- `yes` = the course corpus contains sufficient evidence, but the model refuses or claims insufficient evidence instead of answering
- `no` = it answers appropriately

For Partial cases, use `supported_part_answered` and `unsupported_part_limited` instead.

For Unanswerable cases, `false_refusal = N/A`.

## 12. Citation applicability

Citation quality is:

- applicable to Grounded Answerable outputs with substantive supported claims
- applicable to Grounded Partial outputs for their supported substantive claims
- `N/A` for Ungrounded outputs
- `N/A` for pure refusal / Unanswerable outputs

The presence of `[S1]` or another marker alone does not make citation quality good.

## 13. Citation support labels

For each visible claim-citation relationship, use:

- `fully_supports`
- `partially_supports`
- `does_not_support`
- `wrong_context`

A citation is `wrong_context` when the text is topically related but comes from a context that does not support the specific proposition being cited.

## 14. Citation precision

For applicable responses:

`citation_precision = number of visible cited claim-evidence links judged fully_supports / total visible cited claim-evidence links`

Also retain counts/notes for partially supporting and wrong-context citations.

Do not count a merely topically related citation as precise.

## 15. Citation coverage

For applicable responses:

`citation_coverage = number of fully course-supported substantive claims with at least one fully supporting visible citation / total fully course-supported substantive claims that require evidence`

If there are no applicable supported claims, use `N/A`.

Coverage evaluates whether important supported claims are actually traceable, not whether the response contains at least one citation somewhere.

## 16. Special rules learned from the pilot

- No citation ≠ not course-supported.
- Ungrounded must be checked post-hoc against the same frozen corpus.
- Generation-time support labels are diagnostics, not fair cross-condition human support scores.
- Citation quality for Ungrounded = `N/A`, not `0`.
- Correct refusals should not be penalized because absence claims cannot be positively evidenced like normal factual claims.
- Refusal cases must not be mixed into ordinary factual groundedness/citation averages.
- Partial cases are evaluated as:
  - quality of the supported answer
  - quality of the limitation on the unsupported part
- Visible citation quality and internal structured claim-source associations are separate concerns.

## 17. Annotation workflow

1. Freeze this protocol before inspecting/labeling the full 100 outputs.
2. Create the response-level 100-row annotation master.
3. Pass A:
   - correctness
   - claim segmentation and course support
   - Partial behaviour
   - refusal behaviour
4. Pass B:
   - visible citation precision
   - visible citation coverage
   - citation/context notes
5. Review all borderline cases.
6. Mark every response `annotation_status = reviewed`.
7. Freeze the final human annotation CSV and claim-level annotation CSV.
8. Compute aggregate results from the frozen annotations.
9. Do not change model, prompts, retrieval, top-k, refusal logic, dataset, or annotation rules based on observed formal results.

## 18. Recommended annotation status values

- `not_started`
- `candidate_annotated`
- `review_needed`
- `reviewed`
- `adjudicated`

## 19. Recommended second-annotator check

If feasible, use an independent second annotator on a stratified subset covering:

- Answerable / Partial / Unanswerable
- Grounded / Ungrounded
- easy / medium / hard where possible

Report percent agreement and, for categorical labels where suitable, Cohen’s kappa.

This is recommended but not required for the primary V1-A analysis.
