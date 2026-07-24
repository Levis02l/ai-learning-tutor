# V1-B Adaptive Policy — Scenario Design Handoff

## Status

Research-design handoff only.

This document proposes the concrete methodological content for `AP_G01`–`AP_G11`.
It is **not** the formal dataset, does **not** assign production `concept_id` values,
does **not** freeze evidence chunk IDs, and does **not** authorize a runner or model generation.

Codex should map this design to the current production schema, intent detector,
concept graph, policy implementation, and frozen evidence fixtures before creating
`adaptive_policy_v1_formal_candidate.json`.

## 1. Canonical learner-state profiles

### LOW
- mastery_score: 0.25
- recent_accuracy: 0.25
- attempt_count: 8
- consecutive_errors: 1
- review_due: false

### MEDIUM
- mastery_score: 0.58
- recent_accuracy: 0.625
- attempt_count: 8
- consecutive_errors: 0
- review_due: false

### HIGH
- mastery_score: 0.88
- recent_accuracy: 0.875
- attempt_count: 8
- consecutive_errors: 0
- review_due: false

These values stay away from the 0.40 and 0.75 mastery boundaries and remain below the repeated-error trigger.
Because multiple coherent learner-state fields vary together, the counterfactual dimension should be named `learner_state_profile`, not `mastery_score_only`.

All scenarios use `misconception = null`.

---

## AP_G01 — Explicit Explain / K-means Convergence

- Methodological role: state-adaptation low/high pair
- Concept candidate: `K-means Convergence`
- Evidence candidate: page 7
- Question: **Explain why Lloyd's K-means algorithm can converge to a local rather than a global minimum.**
- Required intent: `explain`

LOW:
- Adaptive: `explain / scaffolded`
- Baseline: `explain / guided`

HIGH:
- Adaptive: `explain / concise`
- Baseline: `explain / guided`

Evidence target: alternating minimisation, non-increasing objective, finite convergence to a possibly local minimum.

---

## AP_G02 — Explicit Explain / First Principal Component

- Role: state-adaptation low/high pair
- Concept candidate: `First Principal Component`
- Evidence candidate: pages 50–51
- Question: **Explain why the first principal component is associated with the largest eigenvalue of the covariance matrix.**
- Required intent: `explain`

LOW:
- Adaptive: `explain / scaffolded`
- Baseline: `explain / guided`

HIGH:
- Adaptive: `explain / concise`
- Baseline: `explain / guided`

Evidence target: projected variance `u^T S u`; maximisation gives the largest eigenvalue and an associated eigenvector.

---

## AP_G03 — Explicit Practice / Silhouette Interpretation

- Role: state-adaptation low/high pair
- Concept candidate: `Silhouette Method`
- Evidence candidate: page 14
- Question: **Quiz me on how to interpret silhouette width, including what a(i), b(i), and s(i) mean.**
- Required intent: `practice`

LOW:
- Adaptive: `quiz / guided`
- Baseline: `quiz / guided`

HIGH:
- Adaptive: `quiz / challenging`
- Baseline: `quiz / guided`

Evidence target: definitions of `a(i)`, `b(i)`, `s(i)` and interpretation near 1, near 0, and negative.

---

## AP_G04 — Explicit Practice / Kernel Trick

- Role: state-adaptation low/high pair
- Concept candidate: `Kernel Trick`
- Evidence candidate: page 33
- Question: **Give me a practice question on how the kernel trick lets kernel K-means compute feature-space distances without explicitly constructing the feature map.**
- Required intent: `practice`

LOW:
- Adaptive: `quiz / guided`
- Baseline: `quiz / guided`

HIGH:
- Adaptive: `quiz / challenging`
- Baseline: `quiz / guided`

Evidence target: feature-space squared distances rewritten using kernel evaluations only.

---

## AP_G05 — Neutral Request / K-medians

- Role: state-adaptation low/high pair
- Concept candidate: `K-medians`
- Evidence candidate: pages 15–16
- Candidate neutral question: **Let's continue with K-medians.**
- Required intent: `unknown`

LOW:
- Adaptive: `explain / scaffolded`
- Baseline: `explain / guided`

HIGH:
- Adaptive: `quiz / challenging`
- Baseline: `explain / guided`

Evidence target: L1/Manhattan objective and coordinate-wise median representatives.

---

## AP_G06 — Neutral Request / PCA Explained Variance

- Role: state-adaptation low/high pair
- Concept candidate: `PCA Explained Variance`
- Evidence candidate: page 52
- Candidate neutral question: **Let's continue with PCA explained variance.**
- Required intent: `unknown`

LOW:
- Adaptive: `explain / scaffolded`
- Baseline: `explain / guided`

HIGH:
- Adaptive: `quiz / challenging`
- Baseline: `explain / guided`

Evidence target: explained-variance ratio from covariance eigenvalues.

---

## AP_G07 — Explicit Explain Triplet / Kernel Choice

- Role: low/medium/high ordinal triplet
- Concept candidate: `Kernel Choice`
- Evidence candidate: pages 35–36
- Question: **Explain why different kernel choices can produce different clustering outcomes in kernel K-means.**
- Required intent: `explain`

LOW:
- Adaptive: `explain / scaffolded`
- Baseline: `explain / guided`

MEDIUM:
- Adaptive: `explain / guided`
- Baseline: `explain / guided`

HIGH:
- Adaptive: `explain / concise`
- Baseline: `explain / guided`

Registered ordinal sequence: `scaffolded -> guided -> concise`.

Evidence target: multiple kernel families and the concentric-cluster example showing different outcomes across kernels/settings.

---

## AP_G08 — Neutral Triplet / PCA Before Clustering

- Role: low/medium/high ordinal triplet
- Concept candidate: `PCA before Clustering`
- Evidence candidate: pages 54–55
- Candidate neutral question: **Let's continue with using PCA before clustering.**
- Required intent: `unknown`

LOW:
- Adaptive: `explain / scaffolded`
- Baseline: `explain / guided`

MEDIUM:
- Adaptive: `hint / guided`
- Baseline: `explain / guided`

HIGH:
- Adaptive: `quiz / challenging`
- Baseline: `explain / guided`

Registered ordinal sequence: `explain/scaffolded -> hint/guided -> quiz/challenging`.

Evidence target: standardise, apply PCA, retain two PCs (~85.7%), then cluster in PC1-PC2 space with K=2.

---

## AP_G09 — Review-Due Pair / Elbow Method

- Role: review_due false/true pair
- Concept candidate: `Elbow Method`
- Evidence candidate: pages 12–13
- Candidate neutral question: **Let's continue with the Elbow method.**
- Required intent: `unknown`
- Fixed learner profile: MEDIUM

FALSE:
- review_due: false
- Adaptive: `hint / guided`
- Baseline: `explain / guided`

TRUE:
- review_due: true
- Adaptive: `review / review_drill`
- Baseline: `explain / guided`

Frozen due-review fixture candidate:
- Prompt: **What does the Elbow method look for when choosing K?**
- Reference: a K beyond which additional WSS reductions become marginal / improvement drops sharply.

Only `review_due` may vary in this group.

---

## AP_G10 — Explicit Hint Fidelity / WSS Monotonicity

- Role: explicit-intent fidelity low/high pair
- Concept candidate: `Elbow Method` or the production concept that resolves specifically to WSS monotonicity
- Evidence candidate: pages 12–13
- Question: **Give me a hint for why optimal K-means WSS cannot increase when K increases. Don't give me the full explanation.**
- Required intent: `hint`

LOW:
- Adaptive: `hint / scaffolded`
- Baseline: `hint / guided`

HIGH:
- Adaptive: `hint / concise`
- Baseline: `hint / guided`

Primary fidelity requirement: selected action must remain `hint` in both states.

---

## AP_G11 — Explicit Practice Fidelity / Metric vs Dissimilarity

- Role: explicit-intent fidelity low/high pair
- Concept candidate: `Metric Spaces`
- Evidence candidate: pages 65–66
- Question: **Quiz me on the difference between a metric and a dissimilarity, including how squared Euclidean distance is classified.**
- Required intent: `practice`

LOW:
- Adaptive: `quiz / guided`
- Baseline: `quiz / guided`

HIGH:
- Adaptive: `quiz / challenging`
- Baseline: `quiz / guided`

Primary fidelity requirement: selected action must remain `quiz` in both states.

Evidence target: metric includes triangle inequality; squared Euclidean is treated as a dissimilarity that may fail to be a metric.

---

## 3. Topology

- AP_G01–AP_G06: 6 state-adaptation low/high pairs = 12 instances
- AP_G07–AP_G08: 2 low/medium/high triplets = 6 instances
- AP_G09: 1 review_due false/true pair = 2 instances
- AP_G10–AP_G11: 2 explicit-intent fidelity low/high pairs = 4 instances

Total: **11 groups / 24 scenario instances**

Pre-registered denominators:
- state-adaptation directional pairs: 6
- mastery ordinal triplets: 2
- review_due pair: 1
- explicit-intent fidelity pairs: 2
- Adaptive/Baseline paired response comparisons: 24
- generated outputs: 48, not independent n=48

---

## 4. Deterministic annotation-context templates

Do not expose `low`, `medium`, `high`, condition labels, expected/actual policy, or strategy names.

LOW:
> Mastery estimate: 0.25. Recent accuracy: 25% across 8 recorded attempts. Current consecutive errors: 1. No review item is due. No misconception flag is present.

MEDIUM:
> Mastery estimate: 0.58. Recent accuracy: 62.5% across 8 recorded attempts. Current consecutive errors: 0. No review item is due. No misconception flag is present.

HIGH:
> Mastery estimate: 0.88. Recent accuracy: 87.5% across 8 recorded attempts. Current consecutive errors: 0. No review item is due. No misconception flag is present.

AP_G09 review_true:
Use the MEDIUM vignette except state:
> A review item for this concept is due.

The same learner context is shown for Response A and Response B within each scenario.

---

## 5. Required engineering audit before candidate dataset creation

Codex must verify without changing production code:

1. exact `LearnerState` schema fields;
2. mastery thresholds and branch semantics;
3. repeated-error trigger;
4. canonical intent labels;
5. G01/G02/G07 classify as `explain`;
6. G03/G04/G11 classify as `practice`;
7. G10 classifies as `hint`;
8. G05/G06/G08/G09 classify as `unknown`;
9. each candidate concept resolves to exactly one observed production concept;
10. expected Adaptive policy matches current production `rule_v2`;
11. expected Baseline policy matches the frozen state-blind mapping;
12. evidence for every group is sufficient;
13. all variants within a group use the same ordered evidence fixture;
14. AP_G09 uses an evaluation-only frozen due-review fixture.

Any failed intent, concept, state, or evidence audit must be resolved before candidate freeze and before model output generation.

---

## 6. Concept coverage

The proposed design spans:
- K-means convergence
- First Principal Component
- Silhouette Method
- Kernel Trick
- K-medians
- PCA Explained Variance
- Kernel Choice
- PCA before Clustering
- Elbow Method / WSS
- Metric vs Dissimilarity

This intentionally covers clustering, kernel methods, and PCA rather than concentrating V1-B on one topic.

---

## 7. Next Codex artifacts

After engineering validation, Codex should create:

- `backend/eval/datasets/adaptive_policy_v1_formal_candidate.json`
- `backend/eval/protocols/adaptive_policy_v1_candidate_dataset_audit.md`

Do not implement the runner and do not generate any Adaptive/Baseline experimental responses at this stage.
