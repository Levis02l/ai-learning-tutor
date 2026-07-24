# Adaptive Policy V1-B Analysis Execution Plan

## Status

Locked after blind-annotation freeze and before reading the reveal key for
outcome analysis.

This document operationalizes only analysis details that were required but not
numerically specified in the frozen protocol. It does not modify the primary
outcome, group-clustered sensitivity method, frozen annotation, or any
experimental treatment.

## Frozen Inputs

- valid run: `adaptive_policy_v1_formal_24case_v2`
- annotation SHA256:
  `38bdb085fe05e967c7a3bbe139815ebb2ecf14679f75ce8f841278f088f3e7e1`
- reveal-key SHA256:
  `0fbc184c65d5d24af4eb702daf36972950d1d9851393efbece45c25089b8bf32`
- raw-results SHA256:
  `657af308f091ccd08795b6de6a46f3e96f0c9524d2a30548617d19ca191d4ce6`
- formal-dataset SHA256:
  `3221a85d87ebb788a603e93d3e48343edaf02d2c1595a3574558c4be30bf36db`
- V2 validity-audit SHA256:
  `1218e379bf0139d8d4601b13c0ea99b1652191b9ea7cbc9fe796f63a9a269437`

Invalidated Formal V1 is excluded from every analysis input.

## Primary Outcome

Map each frozen blind preference through the frozen reveal key to:

- Adaptive better;
- Baseline better; or
- Tie.

Report all 24 scenarios descriptively. Apply the frozen exact two-sided sign
test to non-ties only under a 0.5 null probability.

## Group-Clustered Sensitivity

Apply Amendment 1 exactly:

- Adaptive better `= +1`;
- Tie `= 0`;
- Baseline better `= -1`;
- arithmetic mean within each of 11 groups;
- positive mean = Adaptive direction;
- zero mean = tied group;
- negative mean = Baseline direction; and
- exact two-sided sign test over nonzero group directions.

No threshold, group-size weighting, or post-hoc tie-break is permitted.

## Secondary Outcomes

For each of the four frozen `0/1/2` response ratings:

- report Adaptive mean, median, and score distribution;
- report Baseline mean, median, and score distribution;
- report the paired Adaptive-minus-Baseline mean and median difference;
- report applicable paired `N = 24`; and
- report a percentile 95% confidence interval for the paired mean difference.

The confidence interval uses 20,000 paired bootstrap resamples. Each resample
draws scenario pairs with replacement and preserves the Adaptive/Baseline
pairing.

The deterministic seed namespace is:

```text
adaptive-policy-v1-secondary-bootstrap-v1
```

A metric-specific SHA256-derived integer seed is used inside that namespace.

No secondary inferential p-values will be calculated. Therefore Holm
adjustment is not applicable. This avoids adding a post-reveal secondary test
choice not fixed in the original protocol.

## Manipulation And Implementation Checks

- action, strategy, and exact-policy conformance: 24 scenarios per condition;
- directional adaptation: G01-G06 only, denominator 6 groups;
- ordinal triplet success: G07-G08 only, denominator 2 complete triplets;
- supplementary adjacent triplet contrasts: denominator 4;
- review-due behavior: G09 only, denominator 1 group;
- explicit-intent top-level action fidelity: G10-G11 only, denominator 2
  groups;
- over-adaptation: the four G10-G11 scenario instances per condition; and
- identical-policy controls: the four registered case IDs.

Baseline non-adaptation is expected by design and is reported only as an
implementation characteristic, not as an empirical system failure.

## Claim Boundary

The analysis addresses controlled Policy sensitivity and judged pedagogical
appropriateness.

It must not claim:

- actual learning gain;
- causal improvement in student learning;
- independent double annotation;
- inter-rater agreement; or
- human-only annotation.
