# Grounding V1 Human Annotation Freeze

## Status

Frozen after explicit final author sign-off.

The annotation set is **AI-assisted with final author sign-off**. It should not be described as an independently double-annotated human dataset unless a separate second annotator is later added.

## Population

- 50 formal cases
- 2 conditions per case: Grounded and Ungrounded
- 100 response-level annotations
- 300 claim-level annotation rows
- 49 primary cases from `grounding_v1_formal_50case_v1`
- `grounding_formal_048` recovered separately after repeated HTTP 502 failures
- Recovery conditions were unchanged; no prompt, model, retrieval, dataset, or evaluation-rule tuning was performed

## Frozen files

### Response-level annotations

`grounding_v1_formal_human_annotations.csv`

SHA256:

`ccf559b474427b0fbbb11aabdbdeb5c117cb0fdcf3d2bd4100b401522ee06974`

Validation:

- rows: 100
- grounded: 50
- ungrounded: 50
- unique case/mode pairs: 100
- all annotation_status: reviewed
- case 048 result_source: recovery
- all other cases result_source: primary

### Claim-level annotations

`grounding_v1_formal_claim_annotations.csv`

SHA256:

`6b3993ffb76a297280bec94af9dd11dfe0b06c6b534270d41bfe991addea3729`

Validation:

- claim rows: 300
- all annotation_status: reviewed

## Methodological wording for dissertation

Recommended wording:

> The formal outputs were annotated using a predefined rubric covering answer correctness, post-hoc course support, unsupported claims, refusal behaviour, partial-answer handling, and citation quality. Annotation was AI-assisted and received final author review/sign-off. Automatic evaluator diagnostics were not treated as human ground truth. Ungrounded answers were assessed post hoc against the same frozen course corpus used to assess grounded answers.

Do not describe this as independent inter-annotator agreement.

## Freeze rule

After this freeze, do not alter labels in response to aggregate results.

Any later correction must be documented as a formal annotation amendment with:
- affected case IDs
- old labels
- new labels
- reason
- date
- new SHA256 values
