# V1-B Adaptive Policy Candidate Dataset Audit

## Status

**Engineering-audited candidate; not frozen and not authorized for model
generation.**

This audit maps the approved `AP_G01`-`AP_G11` research-design handoff to the
current backend code, course-2 concept graph, and course-2 document chunks. It
does not add a runner, call an LLM, generate experiment responses, mutate
production learner history, or change production behavior.

Candidate dataset:

`backend/eval/datasets/adaptive_policy_v1_formal_candidate.json`

## 1. Production Rule Audit

The implementation inspected was `backend/app/services/policy.py`.

| Item | Verified value |
| --- | --- |
| Policy version | `rule_v2` |
| Canonical intents | `explain`, `hint`, `practice`, `review`, `unknown` |
| Teaching actions | `explain`, `hint`, `quiz`, `review`, `refuse` |
| Low mastery branch | mastery `< 0.40` or consecutive errors `>= 2` |
| Medium mastery branch | mastery `< 0.75` |
| High mastery branch | mastery `>= 0.75` |
| Evidence safety | insufficient evidence has highest priority |
| Unobserved concept branch | `quiz / guided` before mastery or review rules |
| Review-due implicit branch | `review / review_drill` |

The frozen LOW, MEDIUM, and HIGH profiles are valid `LearnerState` values and
remain away from both mastery thresholds. LOW uses one consecutive error, so it
does not accidentally trigger the repeated-error branch.

All 24 scenarios were passed through the pure `decide_teaching_action` boundary
with sufficient evidence, an evaluation-only observed concept snapshot, and
`misconception = null`. Every actual Adaptive action and strategy matched the
pre-registered expectation.

The Baseline expectations match the frozen state-blind mapping in
`adaptive_policy_v1_protocol.md`:

| Intent | Action | Strategy |
| --- | --- | --- |
| `explain` | `explain` | `guided` |
| `hint` | `hint` | `guided` |
| `practice` | `quiz` | `guided` |
| `review` | `review` | `review_drill` |
| `unknown` | `explain` | `guided` |

## 2. Intent and Concept Resolution Audit

The current resolver is lexical and requires a confidence of at least `0.72`.
The candidate wording below was checked against the real production
`detect_intent` and `resolve_concept_for_focus` implementations.

| Group | Intent | Concept ID | Production concept | Confidence |
| --- | --- | ---: | --- | ---: |
| AP_G01 | `explain` | 3 | K-means Clustering | 0.900 |
| AP_G02 | `explain` | 20 | Principal Component Analysis | 0.900 |
| AP_G03 | `practice` | 16 | Silhouette Width | 0.900 |
| AP_G04 | `practice` | 19 | Kernel K-means Clustering | 0.833 |
| AP_G05 | `unknown` | 17 | K-medians Clustering | 0.900 |
| AP_G06 | `unknown` | 20 | Principal Component Analysis | 0.900 |
| AP_G07 | `explain` | 19 | Kernel K-means Clustering | 0.900 |
| AP_G08 | `unknown` | 20 | Principal Component Analysis | 0.900 |
| AP_G09 | `unknown` | 14 | Elbow Method | 0.900 |
| AP_G10 | `hint` | 6 | Within-Cluster Sum of Squares | 0.900 |
| AP_G11 | `practice` | 7 | Euclidean Norm | 0.900 |

Several minimal wording adjustments were needed:

1. AP_G01 uses the natural wording `Lloyd's algorithm for K-means Clustering`,
   allowing it to use the existing observed K-means concept while preserving
   the Lloyd convergence question.
2. AP_G02, AP_G06, and AP_G08 use the full production name
   `Principal Component Analysis` instead of relying on the unsupported `PCA`
   alias.
3. AP_G07 contains the full phrase `Kernel K-means Clustering`; otherwise the
   shorter `Clustering` concept won the lexical resolver tie.
4. AP_G10 uses the exact phrase `Give me a hint for` and the production concept
   name `Within-Cluster Sum of Squares`. The handoff wording contained
   punctuation after `hint`, so the current phrase matcher classified it as
   `explain`.

AP_G05 adds `clustering` to `K-medians`. The proposed AP_G11
metric-versus-dissimilarity question was replaced because `Euclidean Norm` was
only a related, not equivalent, learner-state concept. AP_G11 now asks how the
Euclidean Norm is used to determine nearest-centroid assignment in the K-means
algorithm. It resolves cleanly to concept 7 and preserves the explicit-practice
fidelity role.

## 3. Observed-State Boundary

The live course-2 database currently contains objective attempts only for:

| Concept ID | Concept | Production attempts | Production status |
| ---: | --- | ---: | --- |
| 3 | K-means Clustering | 2 | observed |

The remaining candidate concepts exist in the production concept graph but
currently have zero linked attempts and therefore return `unobserved` from the
production learner-state service.

This is not repaired by creating fake quiz attempts or editing production
history. Section 7 of the frozen V1-B protocol explicitly requires
evaluation-only counterfactual state injection and says concept scenarios must
be marked `observed`. The candidate therefore records both:

- `production_state_status`, which remains truthful to the current database;
  and
- `evaluation_state_status = observed`, which is the controlled experimental
  snapshot supplied directly to the pure policy boundary.

The future runner must bypass mutable production learner-state lookups. If the
formal methodology later requires all states to arise from real interaction
history rather than controlled counterfactual snapshots, the current candidate
cannot be frozen without collecting genuine attempts for those concepts. No
such requirement exists in the current frozen protocol.

## 4. Evidence Audit

All evidence comes from:

`Lecture_notes_in_Unsupervised_Learning_2026_02_19.pdf`

Database provenance:

- course ID: `2`
- document ID: `3`
- processed chunks: `119`

| Group | Ordered chunk IDs | Evidence target | Audit |
| --- | --- | --- | --- |
| AP_G01 | `94` | alternating minimization and possibly local convergence | sufficient |
| AP_G02 | `154, 155, 156` | projected variance and largest eigenvalue | sufficient |
| AP_G03 | `104, 105` | `a(i)`, `b(i)`, `s(i)`, and interpretation | sufficient |
| AP_G04 | `132` | kernel-only feature-space distance formula | sufficient |
| AP_G05 | `107, 108` | L1 objective and coordinate-wise medians | sufficient |
| AP_G06 | `158, 159` | PCA explained-variance ratio | sufficient |
| AP_G07 | `136, 137, 138, 139` | kernel families and differing outcomes | sufficient |
| AP_G08 | `162, 163, 164` | standardize, PCA, retain two PCs, then cluster | sufficient |
| AP_G09 | `101, 103` | Elbow criterion and marginal WSS improvement | sufficient |
| AP_G10 | `101, 102, 103` | proof that optimal WSS is non-increasing in K | sufficient |
| AP_G11 | `94` | Euclidean nearest-centroid assignment | sufficient |

Each chunk has an exact UTF-8 content SHA256 in the candidate JSON. Each
fixture also has a SHA256 calculated from the complete canonical fixture
payload except the hash field itself. This covers the fixture identity, course
and concept, page targets, ordered chunk IDs/indexes/content hashes, and the
full frozen evidence-state metadata.

The fixtures are human-audited, frozen course evidence rather than live vector
retrieval outputs. Therefore `top_similarity` is deliberately `null`; the
candidate does not fabricate an embedding similarity score. The policy-relevant
state is pre-registered as `high` and sufficient. A future runner schema must
preserve this distinction rather than present a synthetic score as a measured
retrieval result.

AP_G09 includes an evaluation-only due-review fixture linked to chunks `101`
and `103`. The live review queue is not used.

## 5. Counterfactual Invariants

The candidate contains exactly:

- 11 groups;
- 24 scenario instances;
- 6 low/high state-adaptation pairs;
- 2 low/medium/high ordinal triplets;
- 1 review-due false/true pair; and
- 2 explicit-intent fidelity pairs.

Within every group:

- question text is identical across state variants;
- concept ID is identical;
- detected intent is identical;
- misconception is always `null`;
- the same ordered evidence fixture is used;
- Baseline decisions are state-blind and identical;
- only the registered learner-state profile changes; and
- AP_G09 changes only `review_due`.

The 24 scenarios produce 24 paired Adaptive/Baseline comparisons and, later,
48 condition-level response artifacts. They are not 48 independent
observations.

## 6. Identical-Policy Generation Control

Four candidate scenarios have identical expected Adaptive and Baseline
PolicyDecision:

- `adaptive_formal_g03_low`;
- `adaptive_formal_g04_low`;
- `adaptive_formal_g07_medium`; and
- `adaptive_formal_g11_low`.

For these expected no-treatment controls, the future harness must generate one
canonical response and reuse it for both condition artifacts. The registered
pairwise result is a tie. The other 20 scenarios generate the two conditions
independently.

The candidate therefore contains:

- 48 condition-level artifacts; and
- 44 planned model generation calls.

This control prevents provider variation from being interpreted as an
Adaptive-versus-Baseline effect when the policy treatment is identical.
Future reporting must distinguish these four structural no-treatment ties from
observed evaluative ties among the 20 treatment-different comparisons. They
must not be collapsed into one unexplained tie count.

## 7. Executable Schema Validation

The candidate is covered by an executable Pydantic schema and invariant
validator:

```text
backend/eval/datasets/adaptive_policy_v1.schema.json
backend/eval/validate_adaptive_policy_dataset.py
backend/tests/test_adaptive_policy_dataset.py
```

The validator checks:

- strict dataset shape and field types;
- exactly 11 groups and 24 unique scenario instances;
- counterfactual group invariants and the registered group topology;
- production intent detection and `rule_v2` policy decisions;
- production versus evaluation learner-state provenance;
- human-audited evidence with `top_similarity = null`;
- review-due fixture references;
- complete fixture metadata hashes;
- the recomputed identical-policy set; and
- 48 condition artifacts and 44 planned model-generation calls.

The optional freeze-level `--verify-production-resolution` check additionally
re-runs each group question through the live production concept resolver and
verifies the concept ID, name, confidence, and reason recorded in the candidate.

The candidate passes the executable validator and its regression tests.

## 8. Candidate Design Lock

This artifact set is locked as an engineering-audited formal candidate, not as
the final formal experiment freeze. Its purpose is to prevent the 24 candidate
scenarios from being used to develop or tune the future runner.

Candidate dataset SHA256:

```text
3221a85d87ebb788a603e93d3e48343edaf02d2c1595a3574558c4be30bf36db
```

The dataset intentionally retains:

```text
status = candidate_not_frozen
```

No model output is authorized for these 24 candidate scenarios before an
independent pilot has validated the evaluation harness.

## 9. Remaining Formal Freeze Checks

Before this candidate becomes the formal frozen dataset:

1. create a separate pilot dataset with questions not present in this formal
   candidate;
2. verify the future runner materializes sufficient human-audited evidence
   without inventing a retrieval similarity;
3. verify the future runner injects observed concept snapshots directly and
   never reads or mutates production learner history;
4. verify AP_G09 uses only the frozen due-review fixture;
5. run only the independent pilot and repair only experiment-invalidating
   infrastructure defects; and
6. freeze the protocol, formal dataset, evidence, runner/configuration,
   annotation schema, and statistics plan together.

No formal-candidate model outputs should be generated until those checks are
complete.
