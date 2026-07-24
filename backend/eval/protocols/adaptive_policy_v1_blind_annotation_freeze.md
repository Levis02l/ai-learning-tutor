# Adaptive Policy V1-B Blind Annotation Freeze

## Status

`FINAL_AUTHOR_REVIEWED_FROZEN`

Frozen after explicit final author review and sign-off on 24 July 2026.

The annotation procedure was:

> AI-assisted blinded annotation followed by final author review and sign-off.

The annotation set must not be described as independently double annotated,
human-only annotated, or supported by inter-rater agreement unless a separate
independent annotation study is later completed.

## Formal Run

- Experiment: `adaptive_policy_v1`
- Valid formal run: `adaptive_policy_v1_formal_24case_v2`
- Validity audit status before annotation: `PASS_AWAITING_SIGNOFF`
- Formal V1 remains invalidated and excluded from annotation and outcome
  analysis.

## Frozen Annotation Artifact

Path:

```text
backend/eval/annotations/adaptive_policy_v1_formal_24case_v2_author_reviewed_blind_annotation.csv
```

SHA256:

```text
38bdb085fe05e967c7a3bbe139815ebb2ecf14679f75ce8f841278f088f3e7e1
```

Source blinded artifact:

```text
backend/eval/results/adaptive_policy/formal/adaptive_policy_v1_formal_24case_v2/blinded_pairs.json
SHA256 721af031dcca9230e742518e2a18437fda3d7cb8144aeca4a051a0faf518179f
```

V2 validity audit:

```text
backend/eval/results/adaptive_policy/formal/adaptive_policy_v1_formal_24case_v2/validity_audit.json
SHA256 1218e379bf0139d8d4601b13c0ea99b1652191b9ea7cbc9fe796f63a9a269437
```

## Completeness And Integrity Audit

- rows: 24
- unique case IDs: 24
- expected V2 case IDs present: 24
- missing case IDs: 0
- unexpected case IDs: 0
- complete pairwise preferences: 24
- allowed pairwise values only: `A better`, `B better`, `Tie`
- complete A/B secondary rating fields: 8 per row
- allowed secondary values only: `0`, `1`, `2`
- Adaptive/Baseline condition-label leakage: none
- reveal mapping leakage: none
- selected action, response strategy, or Policy-reason leakage: none

The frozen blinded preference distribution is:

```text
A better  10
B better   3
Tie       11
Total     24
```

This distribution remains blinded. It must not be interpreted as
Adaptive-versus-Baseline performance before the separately controlled reveal
stage.

## Blinding And Methodological Record

- `reveal_key.json` was not used for annotation.
- A/B identities were not mapped for outcome analysis before this freeze.
- Adaptive/Baseline wins, p-values, confidence intervals, and outcome
  statistics were not calculated before this freeze.
- No claim is made of independent double annotation.
- No claim is made of inter-rater agreement.
- No claim is made of independent human-only annotation.

## Preservation

The following source artifacts remain unchanged:

- V2 `blinded_pairs.json`;
- V2 `reveal_key.json`;
- V2 raw results and provider events;
- V2 validity audit;
- any retained AI-assisted annotation draft;
- invalidated Formal V1 artifacts and validity record.

No source artifact was overwritten by this freeze.

## Freeze Rule

Do not modify annotation labels after reveal or in response to aggregate
results.

Any later correction requires a formal annotation amendment documenting:

- affected case IDs;
- old labels;
- new labels;
- reason;
- date; and
- replacement SHA256.

The next gate is explicit authorization to reveal A/B identities for outcome
mapping. Stop before reveal.
