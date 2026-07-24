# Adaptive Policy V1-B Results Fact Sheet

## Status

`FINAL_RESULTS_FROZEN`

V1-B experimental work and statistical analysis are complete. No rerun,
re-annotation, policy change, dataset change, or statistical-plan change is
authorized from these results.

## Claim Boundary

V1-B evaluates:

- controlled learner-state sensitivity of a deterministic pedagogical policy;
- preservation of explicit learner intent; and
- blinded judgments of pedagogical fit relative to an intent-aware,
  learner-state-blind baseline.

V1-B does not evaluate or establish:

- actual learning gain;
- causal improvement in student performance;
- effectiveness with real learners;
- independent expert consensus; or
- inter-rater reliability.

## Provenance

- valid formal run: `adaptive_policy_v1_formal_24case_v2`
- invalidated Formal V1 included in analysis: no
- formal scenarios: 24
- counterfactual groups: 11
- conditions: Adaptive and Baseline
- frozen annotation procedure: AI-assisted blinded annotation followed by
  final author review and sign-off
- annotation rows: 24
- analysis version: `adaptive-policy-v1-b-final-1`
- analysis results commit: `5ee6a29aa6bb7ff8ab7d017cd1c246b983bd1288`

## Denominators

| Result | Unit | Denominator |
| --- | --- | ---: |
| Primary preference description | paired scenario | 24 |
| Primary exact sign test | non-tied paired scenario | 13 |
| Clustered sensitivity description | registered group | 11 |
| Clustered exact sign test | non-tied group direction | 7 |
| Secondary response ratings | paired scenario | 24 |
| Policy conformance | scenario per condition | 24 |
| Directional low/high behavior | registered group per condition | 6 |
| Ordinal mastery behavior | complete triplet per condition | 2 |
| Adjacent triplet contrasts | registered contrast per condition | 4 |
| Review-due behavior | registered group per condition | 1 |
| Explicit-intent fidelity | registered group per condition | 2 |
| Over-adaptation | scenario per condition | 4 |
| Identical-policy controls | registered control | 4 |

## Primary Outcome

Across all 24 paired scenarios:

| Outcome | Count | Rate |
| --- | ---: | ---: |
| Adaptive better | 11 | 45.8% |
| Baseline better | 2 | 8.3% |
| Tie | 11 | 45.8% |

Among the 13 non-tied scenarios:

- Adaptive better: `11/13` (`84.6%`)
- Baseline better: `2/13` (`15.4%`)
- exact two-sided sign test under `H0 = 0.5`: `p = 0.0224609375`
- effect direction: Adaptive

Ties remain part of the 24-scenario descriptive result and are excluded only
from the pre-registered sign-test denominator.

## Group-Clustered Sensitivity

Using the frozen equal-weight group algorithm:

| Direction | Groups |
| --- | ---: |
| Adaptive direction | 7 |
| Baseline direction | 0 |
| Tied group | 4 |

- non-tied group directions: `7`
- exact two-sided sign test under `H0 = 0.5`: `p = 0.015625`
- no group-size weighting, threshold, or post-hoc tie-break was used

The primary direction therefore remained unchanged after accounting for the
registered counterfactual grouping.

## Secondary Outcomes

All ratings use the frozen `0/1/2` scale and `N = 24` paired scenarios.
Differences are Adaptive minus Baseline. Confidence intervals are paired
percentile bootstrap intervals with 20,000 resamples.

| Metric | Adaptive mean | Baseline mean | Mean difference | 95% CI |
| --- | ---: | ---: | ---: | ---: |
| Pedagogical appropriateness | 1.917 | 1.792 | +0.125 | [-0.083, 0.333] |
| Learner-state tailoring | 1.875 | 1.125 | +0.750 | [0.417, 1.083] |
| Intent fidelity | 2.000 | 2.000 | 0.000 | [0.000, 0.000] |
| Response relevance | 2.000 | 2.000 | 0.000 | [0.000, 0.000] |

No secondary p-values were calculated, so Holm adjustment is not applicable.

Interpretation constraints:

- the absolute pedagogical-appropriateness difference was small and its
  confidence interval included zero;
- the clearest secondary difference was learner-state tailoring; and
- adaptation did not show an observed trade-off in intent fidelity or response
  relevance in these scenarios.

## Manipulation And Implementation Checks

| Check | Adaptive | Baseline |
| --- | ---: | ---: |
| Exact policy match | 24/24 | 24/24 |
| Registered low/high behavior | 6/6 adapted | 6/6 remained non-adaptive |
| Registered ordinal behavior | 2/2 adapted | 2/2 remained non-adaptive |
| Adjacent triplet behavior | 4/4 adapted | 4/4 remained non-adaptive |
| Review-due behavior | 1/1 adapted | 1/1 remained non-adaptive |
| Explicit-intent action fidelity | 2/2 | 2/2 |
| Over-adaptation violations | 0/4 | 0/4 |

Baseline non-adaptation is an intended implementation property, not an
empirical Baseline failure.

## Identical-Policy Controls

All four pre-registered identical-policy controls:

- reused one canonical execution correctly;
- produced identical learner-visible responses; and
- received a structural Tie after reveal.

They remain in the 24-scenario primary descriptive counts. As a supplementary
description only, the 20 treatment-different scenarios contained:

- Adaptive better: 11
- Baseline better: 2
- Tie: 7

No post-hoc test is authorized for this 20-scenario subset.

## RQ2 Answers

### RQ2a

Within the controlled scenarios, the rule-based adaptive policy changed its
pedagogical behavior in the pre-registered direction as learner state changed,
while preserving explicit learner intent in the tested cases.

### RQ2b

The results support the hypothesis that learner-state-conditioned responses
were more often judged the better pedagogical fit than responses from the
intent-aware, learner-state-blind baseline. The clearest secondary advantage
was learner-state tailoring, not a conclusive difference in absolute
pedagogical-appropriateness ratings.

## Frozen Conclusion

Within the controlled evaluation scenarios, the learner-state-conditioned
adaptive policy showed consistent state-sensitive pedagogical behavior and was
more frequently preferred than an intent-aware learner-state-blind baseline,
with the clearest advantage appearing in learner-state tailoring while intent
fidelity and response relevance were preserved.

## Methodological Limitation

The response pairs were evaluated using an AI-assisted blinded annotation
procedure, with all final labels reviewed and signed off by the author before
condition identities were revealed. This was not an independent multi-annotator
or human-only evaluation. A single author-reviewed process may introduce
evaluator subjectivity; replication with multiple independent educators or
learners would strengthen external validity.

## Frozen Artifacts

- `backend/eval/analysis/adaptive_policy_v1_final/revealed_annotations.csv`
- `backend/eval/analysis/adaptive_policy_v1_final/primary_and_clustered_results.json`
- `backend/eval/analysis/adaptive_policy_v1_final/secondary_results.json`
- `backend/eval/analysis/adaptive_policy_v1_final/manipulation_results.json`
- `backend/eval/analysis/adaptive_policy_v1_final/integrity_audit.json`
- `backend/eval/analysis/adaptive_policy_v1_final/summary.json`
- `backend/eval/analysis/adaptive_policy_v1_final/analysis_manifest.json`

The integrity audit status is `PASS`.
