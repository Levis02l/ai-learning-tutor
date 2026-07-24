# V1-B Adaptive Policy Pilot Dataset Audit

## Status

**Independent development pilot; audited but not yet authorized for model
generation.**

This pilot exists only to validate the V1-B evaluation harness. It is not part
of the formal result set and must never be pooled with formal outcomes.

Locked formal candidate:

```text
commit:
7ab5be7923e1cd1a8d9b85b8432278f855c588a2

dataset SHA256:
3221a85d87ebb788a603e93d3e48343edaf02d2c1595a3574558c4be30bf36db
```

The eight pilot questions are not copies of any locked AP_G01-AP_G11 question.
No formal-candidate model output has been generated.

## 1. Pilot Topology

| Group | Structure | Topic | Primary harness check |
| --- | --- | --- | --- |
| P01 | LOW/MEDIUM | Optimal centroid update | explain strategies and same-policy reuse |
| P02 | MEDIUM/HIGH | Total Sum of Squares | neutral action adaptation and quiz path |
| P03 | review false/true | Silhouette Method | frozen review fixture and review action |
| P04 | LOW/HIGH | Data Standardization | explicit hint action fidelity |

The pilot contains:

```text
4 groups
8 scenario instances
16 condition-level artifacts
1 structural identical-policy control
15 canonical response executions
15 expected successful provider generations before retries
```

P01 LOW adds one comprehension-check generation to the production
scaffolded-explanation path. P03 review true uses the deterministic production
review response with an evaluation-only frozen review fixture and makes no
provider call. These effects cancel, so the harness expects 15 successful
provider generations while recording canonical response executions and actual
provider calls separately. This is a pilot instrumentation check, not a formal
result.

## 2. Production Intent and Concept Audit

All questions were checked using the current production `detect_intent` and
`resolve_concept_for_focus` implementations against course 2.

| Group | Detected intent | Concept ID | Production concept | Confidence |
| --- | --- | ---: | --- | ---: |
| P01 | `explain` | 23 | Optimal centroid update | 0.900 |
| P02 | `unknown` | 10 | Total Sum of Squares | 0.900 |
| P03 | `unknown` | 15 | Silhouette Method | 0.900 |
| P04 | `hint` | 13 | Data Standardization | 0.900 |

All four concepts currently have zero production attempts. The dataset records
that truth as `production_state_status = unobserved` while injecting
`evaluation_state_status = observed` at the pure policy boundary. Production
learner history is not edited.

## 3. Pre-registered Policy Audit

| Scenario | Adaptive | Baseline |
| --- | --- | --- |
| P01 LOW | `explain / scaffolded` | `explain / guided` |
| P01 MEDIUM | `explain / guided` | `explain / guided` |
| P02 MEDIUM | `hint / guided` | `explain / guided` |
| P02 HIGH | `quiz / challenging` | `explain / guided` |
| P03 review false | `hint / guided` | `explain / guided` |
| P03 review true | `review / review_drill` | `explain / guided` |
| P04 LOW | `hint / scaffolded` | `hint / guided` |
| P04 HIGH | `hint / concise` | `hint / guided` |

Every Adaptive expectation was recomputed through production `rule_v2`.
Baseline expectations use the frozen state-blind mapping.

P01 MEDIUM is the only no-treatment control. Its one canonical response must be
reused for the Adaptive and Baseline condition artifacts.

## 4. Evidence Audit

All evidence comes from document 3:

`Lecture_notes_in_Unsupervised_Learning_2026_02_19.pdf`

| Group | Ordered chunks | Evidence target |
| --- | --- | --- |
| P01 | `91, 92, 93` | mean as the unique optimal centroid for fixed assignments |
| P02 | `98, 99, 100` | TSS, WSS, BSS and their decomposition |
| P03 | `104, 105, 106` | silhouette definitions, interpretation and selection of K |
| P04 | `100, 101` | scale dominance and standardization before clustering |

Chunk IDs, indexes, document/course ownership and UTF-8 content SHA256 values
were checked against the live course database. Each fixture SHA covers the
complete canonical fixture metadata. `top_similarity` remains `null` because
these are human-audited frozen fixtures, not live retrieval outputs.

P02 is the only pilot scenario whose Adaptive condition executes the production
policy-quiz path. The production concept quiz source order was verified as
exactly `98, 99, 100`, matching the frozen fixture.

P03 review true uses the evaluation-only
`adaptive_pilot_review_p03_due` fixture. Its Adaptive decision uses
`evidence_strength = not_required`, matching the production semantics for an
existing source-traceable due item. During the shared TutorResponseService call,
an evaluation-only scoped adapter supplies only that frozen item and restores
the production dependency immediately afterwards. The mutable live review
queue is never read.

## 5. Effective Generation and Annotation Controls

The raw Adaptive PolicyDecision retains the frozen learner and concept state
used by `rule_v2`. The raw Baseline PolicyDecision retains the same scenario
snapshot for paired provenance, but its action and strategy come only from the
frozen state-blind mapping.

Before either decision reaches the shared production TutorResponseService, an
evaluation-only `policy_treatment_only_v1` adapter withholds mastery, accuracy,
attempt, error and review-due values from the effective generation prompt. The
adapter preserves:

- the question and resolved concept identity;
- the selected action and response strategy;
- the ordered frozen evidence;
- the shared production prompt builder; and
- the shared production response execution path.

The effective prompt therefore realizes the pre-registered policy treatment
without allowing raw learner-state values to create an additional response
treatment. Raw and effective generation decisions are both saved. A recording
provider test confirms identical Baseline prompt hashes across the P02 MEDIUM
and HIGH counterfactual variants.

Blinded annotation artifacts show only learner-visible initial content:

- quiz question and options, without answer, correct option or explanation;
- review question, without answer, database IDs or source metadata; and
- the answer text and suggested next step shown by the Tutor UI.

The annotation schema contains the single primary pairwise preference plus
per-response pedagogical appropriateness, learner-state tailoring, intent
fidelity and response relevance fields.

A seeded balanced shuffle assigns Adaptive to A for exactly four Pilot cases
and to B for exactly four. The reveal key is stored separately. The same
algorithm produces a 12/12 balance for the later 24-case Formal run.

The manifest records the Git commit and clean/dirty state, actual resolved model
name, dataset/config SHA256 values, and effective retry settings after any CLI
override. Pilot generation is rejected when the Git worktree is dirty.

## 6. Harness Acceptance Criteria

Before a pilot model-generation run is authorized, tests must demonstrate:

1. frozen learner and concept snapshots bypass production history lookups;
2. evidence chunks are loaded by frozen ID and hash, without live retrieval;
3. both policies use the same TutorResponseService execution boundary;
4. all evaluation writes are enclosed by an outer rollback transaction;
5. P01 MEDIUM performs one canonical execution and writes two artifacts;
6. P02 HIGH uses the verified frozen quiz evidence path;
7. P03 review true does not read the live review queue;
8. prompts or prompt hashes, raw provider outputs, retries and errors are saved;
9. Baseline prompt hashes are invariant across learner-state variants with
   identical baseline treatment inputs;
10. blinded quiz/review projections match initial learner-visible content;
11. all four frozen secondary annotation outcomes are present;
12. A/B assignment is deterministic, balanced 4/4 and separately revealed;
13. effective retry settings and Git clean/dirty state are persisted;
14. pilot and formal output directories cannot be confused; and
15. a `candidate_not_frozen` formal dataset is rejected by the runner.

Model generation remains prohibited until the pilot dataset and harness pass
review after implementation.
