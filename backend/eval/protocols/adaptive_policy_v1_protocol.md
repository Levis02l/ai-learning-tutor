# Adaptive Policy V1-B Evaluation Protocol

## Status

**Frozen for the V1-B formal experiment on 24 July 2026.**

This document defines the V1-B evaluation of learner-state-aware pedagogical
policy. It does not change production tutoring behaviour.

The authoritative frozen inputs, versions, counts, and file hashes are recorded
in `adaptive_policy_v1_final_freeze.json` and
`adaptive_policy_v1_final_freeze.md`. Those records authorize only a formal run
that passes the runner's frozen-input preflight.

## 1. Scope and claim boundary

V1-B evaluates two properties under controlled scenarios:

1. whether the adaptive policy responds directionally to changes in learner
   state while preserving explicit learner intent; and
2. whether learner-state-conditioned responses are judged more pedagogically
   appropriate than responses from an intent-aware, learner-state-blind
   baseline.

V1-B does **not** measure learning gain, retention, examination performance, or
long-term educational effectiveness. It contains no pre-test/post-test design
and no real-student outcome comparison. Results must therefore be described as
policy sensitivity and judged pedagogical appropriateness, not improved student
learning.

Misconception-aware adaptation is outside V1-B. Every scenario must set
`misconception = null`. Misconception-aware teaching remains a separate V1-C
evaluation question.

## 2. Research questions

### RQ2a - Policy sensitivity

> Does the adaptive policy respond appropriately and directionally to
> controlled changes in learner state while preserving explicit learner intent?

### RQ2b - Pedagogical appropriateness

> Are learner-state-conditioned tutor responses judged more pedagogically
> appropriate than responses from an intent-aware, learner-state-blind
> baseline?

## 3. Pre-registered hypotheses

### H2a - Directional policy behaviour

The adaptive condition will follow the pre-registered action and strategy
transitions for low, medium, and high mastery profiles, review-due state, and
explicit-intent controls.

### H2b - Explicit intent preservation

For explicit-intent scenarios represented in the formal dataset, learner-state
adaptation will preserve the requested top-level action. Learner state may
change how that action is delivered, but not replace the explicitly requested
action.

### H2c - Blinded pedagogical preference

Across the 24 scenario instances, the adaptive response will be preferred more
often than the state-blind baseline response in a condition-blinded pairwise
pedagogical comparison.

Implementation conformance hypotheses H2a and H2b are manipulation checks. They
must not be presented as evidence that the adaptive response is pedagogically
better. H2c is the primary comparative hypothesis.

## 4. Experimental design

The frozen formal design contains:

- 24 frozen scenario instances;
- 11 counterfactual scenario groups;
- 2 response conditions for each instance;
- 48 condition-level response artifacts in total;
- 24 paired Adaptive/Baseline response comparisons.

The scenario structure is:

| Group family | Groups | Instances | Purpose |
| --- | ---: | ---: | --- |
| State-adaptation low/high pairs | 6 | 12 | Test pre-registered state-sensitive changes |
| Low/medium/high mastery triplets | 2 | 6 | Test ordinal strategy/action progression |
| Review-due false/true pair | 1 | 2 | Isolate review-due behaviour under neutral intent |
| Explicit-intent fidelity low/high pairs | 2 | 4 | Test action preservation while strategy may adapt |
| **Total** | **11** | **24** | |

There are eight low/high structured groups in total. Six are
state-adaptation pairs used in the directional-sensitivity denominator. Two are
explicit-intent fidelity pairs used in the action-fidelity denominator.

The 48 condition-level artifacts are not 48 independent samples. Adaptive and
Baseline outputs are paired within each scenario, and scenarios are
additionally grouped by shared counterfactual question/evidence context. Four
pre-registered identical-policy controls reuse one canonical TutorResponse
execution. Under the frozen service path, the 44 canonical executions are
expected to produce 49 provider-generation events: one deterministic review
execution produces none, while six scaffolded explanations each add one
comprehension-check generation.

## 5. Experimental conditions

### 5.1 Adaptive Policy

The Adaptive condition uses:

- detected user intent;
- the frozen learner-state snapshot;
- review-due status;
- the frozen evidence-state snapshot; and
- the production rule-based policy implementation under evaluation.

It produces:

- `selected_action`; and
- `response_strategy`.

The production policy version and Git commit must be recorded at protocol
freeze and in every run manifest.

### 5.2 Non-Adaptive Baseline

The Baseline is intent-aware and evidence-safe but learner-state-blind. It must
not read mastery, recent performance, consecutive errors, or review-due status
when selecting its action and strategy.

Its mapping is frozen as:

| Detected intent | Selected action | Response strategy |
| --- | --- | --- |
| `explain` | `explain` | `guided` |
| `hint` | `hint` | `guided` |
| `practice` | `quiz` | `guided` |
| `review` | `review` | `review_drill` |
| `unknown` | `explain` | `guided` |

The canonical production intent is `practice`; its corresponding teaching
action is `quiz`. Protocol, dataset, and evaluation artifacts must store
`practice` as the detected intent and must not introduce an evaluation-only
`quiz` intent alias.

Evidence safety remains active in both conditions:

| Evidence condition | Selected action | Response strategy |
| --- | --- | --- |
| insufficient evidence for an evidence-requiring action | `refuse` | `refusal` |

The V1-B formal scenario set is expected to use sufficient frozen course
evidence so that V1-B isolates learner-state adaptation rather than repeating
the V1-A refusal experiment. The refusal mapping is retained as a condition
invariant and implementation safeguard.

The Baseline must not be deliberately weakened. It uses valid production
strategy values and the same response-generation infrastructure as Adaptive.

### 5.3 Identical-policy generation control

Some scenarios are expected no-treatment controls: the Adaptive and Baseline
conditions produce the same `selected_action` and `response_strategy`. When the
question, ordered evidence fixture, PolicyDecision, prompt inputs, and
generation configuration are identical, the evaluation must make one canonical
model call and reuse that response for both condition-level artifacts.

The two artifacts remain distinct for provenance and paired-analysis topology,
but they are not independent model generations. Their registered pairwise
preference is a tie. This prevents model-service variation from being
misattributed to a policy treatment that did not occur.

The candidate dataset identifies these cases prospectively. If later dataset
changes alter which policies are identical, validation must recompute the set
rather than relying on a stale manual list.

## 6. Controlled variables

For an Adaptive/Baseline comparison of the same scenario, the following must be
identical:

- question text;
- course and concept;
- detected intent;
- learner-context vignette shown to the annotator;
- frozen evidence-state snapshot;
- frozen evidence chunks and their order;
- response-generation model and provider;
- temperature and other generation parameters;
- prompt builder and prompt templates;
- maximum output length;
- TutorResponseService execution path; and
- retry and failure-handling policy.

The experimental condition changes only the `PolicyDecision` supplied to the
shared response-generation path. Prompt text may consequently differ where the
selected action or response strategy differs, but both conditions must use the
same prompt infrastructure and frozen strategy templates.

Within a counterfactual group, question, concept, intent, evidence, and all
non-manipulated state fields must remain fixed. Only the pre-registered
counterfactual learner-state dimension may change.

## 7. Evaluation-only state injection

Counterfactual learner states must not be created by editing real user history
or production database records.

The later evaluation harness must:

1. load a frozen scenario;
2. construct the frozen learner-state and evidence snapshots;
3. call the pure policy decision boundary for the Adaptive condition;
4. construct the frozen state-blind decision for the Baseline condition;
5. pass each decision through the same TutorResponseService machinery; and
6. save both raw decisions, prompts or prompt hashes, evidence, and responses.

For identical-policy controls, step 5 performs one canonical generation and
step 6 writes two condition-level artifacts referencing that same generation.

The harness must bypass production lookups that would re-resolve learner state
or misconception data. It must explicitly provide `misconception = null`.

Concept scenarios must be marked `observed` unless a future protocol explicitly
adds unobserved-concept behaviour. This prevents the production diagnostic-quiz
branch from becoming an uncontrolled variable.

For the review-due scenario, any due review item required to execute the review
response must be provided as a frozen evaluation fixture. The evaluation must
not depend on mutable production review queues.

## 8. Pre-registered policy behaviour

The formal dataset must contain expected Adaptive and Baseline decisions before
any model output is generated.

Expected Adaptive behaviour must follow the production policy specification
under evaluation. Examples include:

| Intent/state | Expected Adaptive behaviour |
| --- | --- |
| explicit explain + low mastery | `explain / scaffolded` |
| explicit explain + medium mastery | `explain / guided` |
| explicit explain + high mastery | `explain / concise` |
| explicit practice + low or medium mastery | `quiz / guided` |
| explicit practice + high mastery | `quiz / challenging` |
| neutral + low mastery | `explain / scaffolded` |
| neutral + medium mastery | `hint / guided` |
| neutral + high mastery | `quiz / challenging` |
| neutral + review due | `review / review_drill` |

Explicit intent determines **what** action is performed. Learner state may
determine **how** that action is delivered. Explicit-intent fidelity therefore
requires action preservation, not strategy stability.

The formal pre-registration must be reviewed for pedagogical plausibility, not
copied mechanically after observing model responses.

## 9. Outcomes and metrics

### 9.1 Primary comparative outcome

#### Blinded Pairwise Pedagogical Preference

For every scenario, the annotator receives the same learner context and two
responses in randomized A/B order. The annotator selects exactly one:

- `A_better`;
- `B_better`; or
- `tie`.

The condition mapping is revealed only during analysis and converted to:

- `adaptive_better`;
- `baseline_better`; or
- `tie`.

Report:

- Adaptive win count and rate;
- Baseline win count and rate;
- tie count and rate;
- total paired scenarios (`n = 24`); and
- non-tie comparison count.

The pre-registered primary inferential test is an exact two-sided sign test on
non-tie preferences under a 0.5 null preference probability. Ties are excluded
from the sign-test denominator but must remain visible in all reporting.

Because instances within a counterfactual group share question and evidence,
the following group-clustered sensitivity analysis is pre-registered:

1. Encode each revealed scenario preference as `+1` for
   `adaptive_better`, `0` for `tie`, and `-1` for `baseline_better`.
2. For each of the 11 registered counterfactual groups, calculate the
   arithmetic mean of its scenario scores. Each group therefore contributes
   one direction regardless of whether it contains two or three scenarios.
3. Classify a positive group mean as `adaptive_direction`, an exactly zero
   mean as `tied_group`, and a negative mean as `baseline_direction`.
4. Apply an exact two-sided sign test to the nonzero group directions under a
   0.5 null probability of an Adaptive direction. Tied groups are excluded
   from the test denominator but retained in reporting.
5. Report Adaptive-direction group count, Baseline-direction group count,
   tied-group count, all 11 registered groups, and the non-tied group
   denominator.

No magnitude threshold, weighting by group size, or post-hoc tie-break is
permitted. This is a sensitivity analysis; the primary analysis remains the
24-scenario exact sign test. The primary scenario-level result and clustered
sensitivity result must both be retained, including any disagreement between
them.

### 9.2 Secondary response outcomes

Each response is rated independently on a `0/1/2` rubric before or alongside
the pairwise preference judgment:

| Outcome | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Pedagogical appropriateness | inappropriate for the learner context | partly appropriate, with material mismatch | clearly appropriate for the learner context |
| Learner-state tailoring | no meaningful tailoring to the provided learner context | some tailoring is visible, but it is weak, inconsistent, or only partly appropriate | clearly and appropriately tailored to the provided learner context |
| Intent fidelity | conflicts with the learner's explicit request | partly follows the request | fully follows the request |
| Response relevance | materially off-topic or unusable | partly relevant or unnecessarily indirect | directly relevant and usable |

Adaptive and Baseline ratings are paired within scenario. Analysis must report
condition estimates, paired differences, uncertainty intervals, and the number
of applicable paired scenarios. Secondary inferential tests are exploratory;
if p-values are reported for all four outcomes, a pre-specified Holm correction
must be applied.

Whether an Adaptive response realizes its hidden pre-registered strategy, such
as `scaffolded`, `guided`, `concise`, or `challenging`, may be inspected only in
a separate post-reveal qualitative or manipulation analysis. It is not a
condition-blinded human metric.

### 9.3 Manipulation and implementation checks

These checks determine whether each condition followed its pre-registered
specification. They are not evidence of superior pedagogy.

- `action_accuracy`: actual action equals pre-registered expected action;
- `strategy_accuracy`: actual strategy equals pre-registered expected strategy;
- `exact_policy_match`: action and strategy are both correct;
- `directional_sensitivity`: a registered state-adaptation low/high pair changes
  in the registered direction;
- `ordinal_triplet_success`: the complete low/medium/high sequence matches the
  registered ordinal progression;
- `explicit_intent_action_fidelity`: explicit intent retains its corresponding
  action across learner states; and
- `over_adaptation_rate`: the action violates explicit intent because of
  learner-state conditioning.

Adaptive and Baseline conformance must be reported separately. Baseline is not
expected to exhibit learner-state adaptation by design, so its lack of
adaptation cannot be presented as a discovered failure.

## 10. Units of analysis and denominators

| Analysis | Unit | Pre-registered denominator |
| --- | --- | ---: |
| Policy conformance | scenario instance | 24 |
| State-adaptation low/high directional adaptation | counterfactual pair | 6 |
| Mastery ordinal success | complete triplet | 2 |
| Adjacent triplet contrasts, supplementary | pre-defined adjacent contrast | 4 |
| Review-due behaviour | review pair | 1 |
| Explicit-intent action fidelity | fidelity pair/group | 2 |
| Adaptive/Baseline response comparison | paired scenario | 24 |
| Generated responses | output artifact, not an independent analysis unit | 48 |

The review-due result is a targeted functional check and must not support a
broad statistical claim by itself.

## 11. Blinded human evaluation

### 11.1 Information shown to the annotator

The annotator may see:

- question;
- course/concept context required to understand the task;
- user intent in neutral wording;
- frozen learner-state values or a deterministic standardized vignette;
- review-due status;
- confirmation that misconception information is absent; and
- Response A and Response B.

The learner context must be identical for both responses in a pair. A vignette
must contain only information present in the frozen scenario and must not add
LLM-inferred statements such as an unrecorded learning difficulty.

### 11.2 Information hidden until analysis

The annotation artifact must hide:

- Adaptive/Baseline condition;
- expected and actual action;
- expected and actual strategy;
- policy reason;
- policy version where it could reveal the condition;
- generation order; and
- the A/B randomization key.

Low/medium/high category names may be omitted in favour of exact values or a
standardized state vignette. Condition blinding, not concealment of relevant
learner context, is the methodological requirement.

### 11.3 Randomization and disclosure

A/B order must be assigned using a deterministic recorded seed before
annotation. The blinded annotation file must be separate from the reveal key.

Any AI assistance in preparing annotations must be disclosed. Final labels
require author review and sign-off. Unless a second independent annotator is
actually used, the dissertation must not claim independent double annotation or
inter-rater agreement.

## 12. Failure handling

The later runner must preserve every attempted output and record failures per
condition. Transient provider or network failures may use a bounded,
pre-registered retry policy. Persistent failures must remain in raw results and
must not be silently regenerated until a preferred answer appears.

An isolated recovery run is permissible only for missing infrastructure-failure
outputs under identical frozen settings. Recovery provenance must be retained.

## 13. Reproducibility requirements

Every pilot and formal run must record:

- run ID and run type;
- timestamp;
- Git commit and dirty/clean status;
- policy version;
- dataset path and SHA256;
- evidence-fixture path and SHA256;
- prompt/template version or hash;
- model/provider and generation parameters;
- A/B randomization seed and reveal-key hash;
- retry configuration;
- raw policy inputs and outputs;
- raw model responses;
- condition-specific latency and errors; and
- software/configuration manifests needed to reproduce the run.

Pilot, formal, recovery, blinded annotation, reveal-key, and analysis artifacts
must be stored separately and must not overwrite one another.

## 14. Pilot, freeze, and formal procedure

1. Review and approve this protocol and the dataset design.
2. Draft the 11 groups / 24 instances without generating outputs.
3. Audit concept resolution, evidence fixtures, counterfactual isolation,
   expected decisions, and annotation vignettes.
4. Select a separate 6-8 instance pilot covering mastery, neutral intent,
   review due, and explicit-intent fidelity.
5. Implement the evaluation harness without modifying production policy or
   TutorResponseService behaviour.
6. Run the pilot only to identify experiment-invalidating bugs, missing
   instrumentation, or ambiguous rubric definitions.
7. Freeze protocol, formal dataset, evidence fixtures, prompt/configuration,
   baseline mapping, annotation rubric, and statistical plan.
8. Run the complete formal experiment once under the frozen configuration.
9. Produce a condition-blinded randomized annotation artifact.
10. Complete author-reviewed annotation, freeze the labels, and reveal
    conditions only for analysis.
11. Run the pre-registered statistical analysis and qualitative failure review.

The pilot must not be tuned until its outputs look favourable. Formal scenarios
must not be inspected and used to modify policy rules or prompts.

## 15. Prohibited changes and extensions

V1-B must not introduce or evaluate:

- DKT;
- contextual bandits;
- reinforcement learning;
- misconception-aware adaptation;
- new production policy actions or strategy values;
- production learner-state mutation for counterfactual testing;
- a separate or deliberately weaker Baseline response generator; or
- claims of measured learning improvement.

This draft does not modify the production Policy Controller or
TutorResponseService.

## 16. Formal authorization gate

The independent Pilot completed successfully and received validity sign-off.
The 11 groups, 24 scenario instances, evidence fixtures, Baseline mapping,
Policy version, generation adapter, runner, model/configuration, blinding
procedure, annotation rubric, and statistical plan are frozen together in the
V1-B final-freeze records.

The next permitted operation is a read-only formal preflight. Model generation
is authorized only after that preflight passes against a clean Git worktree and
the exact frozen hashes. No second Pilot or outcome-driven tuning is permitted.
