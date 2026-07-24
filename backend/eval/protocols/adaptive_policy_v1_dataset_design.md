# Adaptive Policy V1-B Dataset Design Draft

## Status

**Design draft for review. No formal dataset has been created.**

This document specifies the required structure, composition, invariants, and
audit checks for the proposed V1-B counterfactual dataset. It must be read with
`adaptive_policy_v1_protocol.md`.

## 1. Dataset objective

The dataset must support controlled comparison of:

- the learner-state-aware Adaptive policy; and
- an intent-aware, evidence-safe, learner-state-blind Baseline.

It must isolate learner-state effects while holding question, concept, intent,
course evidence, generation model, and response machinery constant.

The dataset is a controlled scenario dataset, not an observational sample of
real learners and not evidence of learning gain.

## 2. Required size and topology

The formal candidate must contain exactly:

- 24 scenario instances;
- 11 scenario groups;
- 6 state-adaptation low/high pairs (12 instances);
- 2 low/medium/high triplets (6 instances);
- 1 review-due false/true pair (2 instances); and
- 2 explicit-intent fidelity low/high pairs (4 instances).

There are eight low/high structured groups in total:

- 6 state-adaptation pairs, which define the directional-adaptation
  denominator; and
- 2 explicit-intent fidelity pairs, which define the action-fidelity
  denominator.

Group sizes are therefore:

- 9 groups of size 2; and
- 2 groups of size 3.

The design must never be described as 12 independent pairs.

## 3. Proposed group allocation

The following table defines group roles, not final questions. Concrete concepts,
wording, evidence, and expected decisions require a later authoring and audit
step.

| Group ID | Structure | Intended request family | Counterfactual dimension | Instances | Main check |
| --- | --- | --- | --- | ---: | --- |
| `AP_G01` | state-adaptation low/high pair | explicit explanation | mastery profile | 2 | strategy changes; action remains explain |
| `AP_G02` | state-adaptation low/high pair | explicit explanation | mastery profile | 2 | replicate explain adaptation on another concept |
| `AP_G03` | state-adaptation low/high pair | explicit practice | mastery profile | 2 | guided vs challenging quiz strategy |
| `AP_G04` | state-adaptation low/high pair | explicit practice | mastery profile | 2 | replicate quiz adaptation on another concept |
| `AP_G05` | state-adaptation low/high pair | neutral learning request | mastery profile | 2 | action and strategy adapt to state |
| `AP_G06` | state-adaptation low/high pair | neutral learning request | mastery profile | 2 | replicate neutral adaptation on another concept |
| `AP_G07` | low/medium/high triplet | explicit explanation | mastery profile | 3 | scaffolded -> guided -> concise |
| `AP_G08` | low/medium/high triplet | neutral learning request | mastery profile | 3 | explain -> hint -> quiz progression |
| `AP_G09` | false/true pair | neutral learning request | review_due only | 2 | review prioritization when due |
| `AP_G10` | explicit-intent fidelity low/high pair | explicit hint | mastery profile | 2 | hint action fidelity; strategy may change |
| `AP_G11` | explicit-intent fidelity low/high pair | explicit practice | mastery profile | 2 | quiz action fidelity; strategy may change |

The later concrete dataset may revise which course concept is assigned to a
group, but it must not change the group counts or methodological role without a
protocol revision before any output is generated.

## 4. Counterfactual invariants

Within each group, all instances must share:

- identical question text;
- identical normalized detected intent;
- identical course ID;
- identical concept ID and concept name;
- identical observed concept-state status;
- identical evidence fixture ID;
- identical evidence-state snapshot;
- identical ordered source-chunk IDs and source text;
- identical misconception value (`null`);
- identical generation configuration; and
- identical fields not named as the counterfactual dimension.

For mastery groups, review_due must remain `false` unless the protocol is
explicitly revised. For the review group, the complete mastery profile must
remain identical and only `review_due` may change.

## 5. Learner-state profiles

The final dataset must use canonical, coherent learner-state snapshots. Exact
values require review before freeze, but they must unambiguously exercise the
production thresholds:

| Profile | Required mastery relation | Consecutive errors | Review due | Purpose |
| --- | --- | ---: | --- | --- |
| low | `< 0.40` | below repeated-error trigger unless explicitly tested | false | exercise low-mastery branch |
| medium | `>= 0.40` and `< 0.75` | below repeated-error trigger | false | exercise medium-mastery branch |
| high | `>= 0.75` | below repeated-error trigger | false | exercise high-mastery branch |

Avoid exact boundary values `0.40` and `0.75` in the main formal scenarios.
Boundary correctness belongs in unit tests, not in the primary human-response
comparison.

To isolate mastery-band behaviour, the primary profiles should not also trigger
the repeated-error rule. `consecutive_errors` must therefore remain below 2.

Other learner fields, such as recent accuracy and attempt count, must form a
coherent frozen vignette. If those values differ across mastery profiles, the
counterfactual dimension must be named `learner_state_profile`, not falsely
described as mastery score alone. The production policy input and annotator
vignette must both retain the exact frozen values.

## 6. Review-due pair

`AP_G09` must use:

- neutral/unknown intent;
- an observed concept;
- sufficient evidence;
- one fixed mastery profile;
- identical question and evidence; and
- `review_due = false` versus `review_due = true` as the only changed learner
  field.

The expected Adaptive transition must be registered before generation. The
`review_due = true` instance expects `review / review_drill`. The false instance
uses the action implied by its unchanged mastery profile.

The Baseline ignores review_due and therefore expects `explain / guided` for
both neutral-intent instances.

A frozen due-review fixture must exist for response execution in the true
instance. It must be an evaluation artifact, not a mutable production queue.

## 7. Explicit-intent action-fidelity groups

`AP_G10` and `AP_G11` test whether learner-state adaptation preserves what the
learner explicitly requested.

The required invariant is action fidelity:

- explicit hint remains `hint`;
- explicit practice remains `quiz`.

Response strategy is allowed and expected to change by mastery profile. These
groups must not be scored as strategy-stability tests.

An over-adaptation failure occurs when learner state changes the action away
from the explicit request, for example explicit hint becoming quiz.

## 8. Triplet definition

`AP_G07` and `AP_G08` contain low, medium, and high instances with all
non-state inputs fixed.

The complete ordinal sequences are pre-registered as:

### `AP_G07` explicit explanation

```text
low    -> explain / scaffolded
medium -> explain / guided
high   -> explain / concise
```

### `AP_G08` neutral learning request

```text
low    -> explain / scaffolded
medium -> hint / guided
high   -> quiz / challenging
```

Each triplet receives one `ordinal_triplet_success` result. It succeeds only if
all three states match the registered sequence.

The following four adjacent contrasts may be reported as supplementary checks:

- `AP_G07`: low -> medium;
- `AP_G07`: medium -> high;
- `AP_G08`: low -> medium; and
- `AP_G08`: medium -> high.

They must not replace the two-triplet primary denominator.

## 9. Expected Baseline decisions

Every scenario must store an expected Baseline decision derived from the frozen
state-blind mapping:

| Intent | Expected Baseline action | Expected Baseline strategy |
| --- | --- | --- |
| explain | explain | guided |
| hint | hint | guided |
| practice | quiz | guided |
| review | review | review_drill |
| unknown | explain | guided |

Expected Baseline decisions must be identical across learner-state variants in
the same group.

The canonical production detected-intent value for quiz/practice requests is
`practice`; the corresponding teaching action is `quiz`. The dataset must store
`practice` directly and must not introduce an evaluation-only `quiz` intent
alias.

## 10. Proposed scenario schema

The later formal dataset should use a structured schema equivalent to:

```json
{
  "case_id": "adaptive_formal_001_low",
  "group_id": "AP_G01",
  "group_type": "mastery_pair",
  "scenario_position": "low",
  "course_id": 2,
  "question": "Approved question text",
  "concept": {
    "concept_id": 1,
    "name": "Approved concept name",
    "state_status": "observed"
  },
  "detected_intent": "explain",
  "counterfactual_dimension": "learner_state_profile",
  "learner_state": {
    "mastery_score": 0.25,
    "recent_accuracy": 0.25,
    "attempt_count": 8,
    "consecutive_errors": 0,
    "review_due": false
  },
  "misconception": null,
  "evidence_fixture_id": "adaptive_evidence_g01",
  "evidence_state": {
    "evidence_strength": "high",
    "requires_evidence": true
  },
  "expected_adaptive_policy": {
    "selected_action": "explain",
    "response_strategy": "scaffolded"
  },
  "expected_baseline_policy": {
    "selected_action": "explain",
    "response_strategy": "guided"
  },
  "annotation_context": {
    "intent_text": "The learner explicitly requests an explanation.",
    "learner_vignette": "Deterministic text generated only from frozen state values."
  },
  "notes": ""
}
```

The example is illustrative and is not a formal case. Exact field names will be
validated against the future evaluation harness before dataset freeze.

## 11. Question and concept selection

Concrete questions must:

- be answerable from the frozen course corpus;
- resolve confidently to one observed concept;
- have sufficient evidence for both conditions;
- avoid requiring misconception-specific remediation;
- be suitable for the intended action family;
- avoid duplicating pilot questions verbatim in the formal primary set; and
- cover more than one course concept so results are not dominated by one topic.

Question wording must make the intended intent class clear for explicit groups
and genuinely neutral for unknown-intent groups. Neutral prompts must be checked
against the production intent detector before freeze.

## 12. Evidence fixtures

Evidence must be retrieved and audited before response generation, then frozen
as a fixture.

Each fixture must record:

- course ID;
- concept ID;
- ordered chunk IDs;
- source filenames and metadata;
- exact chunk text or immutable content hashes;
- retrieval/evidence-state fields;
- retrieval configuration; and
- fixture SHA256.

Adaptive and Baseline use the exact same fixture for a scenario. All variants
within a counterfactual group should also use the same fixture unless the group
design explicitly and prospectively states otherwise. The current design does
not authorize such an exception.

## 13. Annotation-context design

The annotation context must tell the evaluator enough to judge pedagogical fit
without revealing the condition or expected policy.

Allowed context includes:

- the learner's request;
- exact frozen mastery estimate or a deterministic vignette;
- attempt/error context actually present in the state;
- review-due status;
- concept; and
- absence of a misconception flag.

The context must not include:

- Adaptive/Baseline labels;
- expected or actual actions;
- expected or actual strategies;
- policy reasons;
- words inserted to imply that one response style is preferred; or
- inferred learner difficulties not represented in the frozen state.

The same context is displayed for Response A and Response B.

## 14. A/B randomization artifacts

The later pipeline must produce:

1. a blinded annotation file containing scenario context, Response A, Response
   B, rubric fields, and no condition labels;
2. a separate reveal key mapping A/B to Adaptive/Baseline; and
3. a manifest recording the deterministic randomization seed and hashes of both
   artifacts.

The reveal key must not be used until annotation is complete and signed off.

## 15. Dataset audit checklist

Before a candidate dataset may be frozen, validation must confirm:

- [ ] exactly 24 unique `case_id` values;
- [ ] exactly 11 unique `group_id` values;
- [ ] exactly 9 groups of size 2 and 2 groups of size 3;
- [ ] exactly 6 registered state-adaptation low/high pairs;
- [ ] exactly 2 registered explicit-intent fidelity low/high pairs;
- [ ] exactly 8 low/high structured groups in total;
- [ ] exactly 2 registered mastery triplets;
- [ ] exactly 1 review-due pair;
- [ ] exactly 2 explicit-intent action-fidelity groups;
- [ ] group-invariant question, concept, intent, and evidence;
- [ ] only the registered counterfactual fields vary within each group;
- [ ] all concepts are observed;
- [ ] all misconception values are null;
- [ ] all formal evidence fixtures are sufficient and manually auditable;
- [ ] Adaptive and Baseline expected decisions are present for every instance;
- [ ] expected decisions match the pre-registered policy specifications;
- [ ] neutral prompts are classified as `unknown` by the frozen intent detector;
- [ ] explicit prompts resolve to their registered intent;
- [ ] mastery profiles avoid threshold-boundary ambiguity;
- [ ] review-due is false outside the registered review group;
- [ ] Baseline decisions do not vary with learner state;
- [ ] annotation vignettes contain only frozen state information;
- [ ] concept and question coverage is not concentrated in a single topic;
- [ ] pilot and formal primary questions are separated;
- [ ] no model outputs were inspected while authoring expected labels; and
- [ ] dataset and evidence-fixture SHA256 values are recorded.

## 16. Pilot sampling guidance

The pilot should contain 6-8 development instances separate from the formal
primary set and should cover at least:

- one explicit explain adaptation;
- one explicit practice or hint adaptation;
- low, medium, and high mastery somewhere in the pilot;
- one neutral-intent action change;
- the review-due path; and
- explicit-intent action fidelity.

Pilot outputs may be used only to repair experiment-invalidating bugs,
instrumentation gaps, or ambiguous annotation instructions. They must not be
used to tune production policy or response prompts until preferred outcomes are
obtained.

## 17. Freeze deliverables

The later V1-B freeze should include at minimum:

- approved protocol;
- approved 24-instance dataset;
- approved evidence fixtures;
- dataset and fixture audit report;
- frozen Baseline mapping;
- frozen policy version and implementation commit;
- frozen model/prompt/generation config;
- blinded annotation rubric and schema;
- A/B randomization procedure;
- statistical analysis plan; and
- SHA256 values for every frozen input.

## 18. Next approval gate

Do not create concrete formal scenarios or implement a runner until this design
and the accompanying protocol have been reviewed. The next approved task is to
author and audit the 11 concrete groups / 24 concrete instances without running
either condition.
