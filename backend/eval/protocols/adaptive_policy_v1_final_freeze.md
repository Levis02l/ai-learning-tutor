# Adaptive Policy V1-B Final Freeze

## Status

**Frozen on 24 July 2026; Statistical Clarification Amendment 1 and Frozen
Evidence Execution Correction Amendment 2 applied.**

The independent eight-scenario Pilot completed successfully and received
validity sign-off. No second Pilot is authorized. The first formal execution
was invalidated before annotation or outcome analysis because of the
deterministic evidence-execution bug documented below. The next permitted
operation is a strengthened read-only formal preflight. Replacement formal
generation requires separate explicit authorization after that preflight.

The machine-readable authority for this freeze is
`adaptive_policy_v1_final_freeze.json`.

## Amendment 1 - Group-Clustered Sensitivity Analysis

Before any formal output was generated, the group-clustered sensitivity method
was specified exactly:

1. Encode each scenario preference as Adaptive better `= +1`, tie `= 0`, and
   Baseline better `= -1`.
2. Compute the arithmetic mean within each of the 11 registered
   counterfactual groups.
3. Classify a positive mean as Adaptive-direction, zero as a tied group, and a
   negative mean as Baseline-direction.
4. Run an exact two-sided sign test over nonzero group directions under a 0.5
   null probability.
5. Report all direction counts, all 11 groups, tied groups, and the non-tied
   denominator.

Each group receives one vote regardless of whether it contains two or three
scenarios. No threshold, group-size weighting, or post-hoc tie-break is
allowed. The primary analysis remains the exact sign test over the 24
scenario-level blinded preferences. This amendment changes no scenario,
evidence, Policy, Baseline, prompt, model, runner behaviour, or A/B assignment.

## Amendment 2 - Frozen Evidence Execution Correction

The first formal execution,
`adaptive_policy_v1_formal_24case_v1`, was invalidated before annotation and
before outcome analysis. Its integrity audit found that policy-generated quiz
items re-ran live concept retrieval instead of consuming the evidence chunks
already supplied by the frozen `PolicyDecision`. This deterministic execution
bug affected 7 of 24 scenarios and 11 condition artifacts.

The run remains permanently preserved at:

```text
backend/eval/results/adaptive_policy/formal/adaptive_policy_v1_formal_24case_v1/
```

It is excluded in full from primary and secondary efficacy analysis. It must
not be annotated, partially salvaged, overwritten, deleted, or combined with a
later result set. The reveal key was used only to verify the registered 12/12
A/B balance; it was not used for annotation or outcome analysis. Exact
provenance and artifact hashes are recorded in
`adaptive_policy_v1_invalidated_formal_run_v1.json`.

Amendment 2 authorizes one narrow execution correction:

```text
PolicyDecision.evidence_chunks
        -> policy quiz generation
        -> generate from those supplied chunks
```

The product-level fallback to ordinary quiz retrieval remains available only
when no decision evidence was supplied. This correction changes evidence
plumbing only. It does not change any formal scenario, learner profile,
expected decision, Policy rule, Baseline mapping, evidence fixture, prompt,
model, generation setting, retry policy, blinding rule, annotation rubric, or
statistical analysis.

The formal preflight now executes every canonical policy-quiz path with a
non-network provider. It verifies the exact frozen chunk order supplied to the
quiz prompt, rejects any live concept-retrieval call, and requires every
generated quiz source ID to be a subset of the corresponding frozen fixture.
The registered canonical policy-quiz execution count is 12.

A complete 24-scenario replacement run is required. Its run ID is
`adaptive_policy_v1_formal_24case_v2`. Replacement generation was explicitly
authorized after the strengthened post-commit preflight passed. The
machine-readable authorization is
`adaptive_policy_v1_formal_v2_authorization.json`. This authorization changes
only the run safety guard and does not alter any experimental input.

## Frozen Experiment

The formal experiment contains:

- 11 counterfactual groups;
- 24 scenario instances;
- 48 Adaptive/Baseline condition artifacts;
- 4 pre-registered identical-policy controls;
- 44 canonical TutorResponse executions; and
- 49 expected successful provider-generation events.

The legacy candidate fields named `planned_model_generation_call_count` contain
the value 44. After Pilot instrumentation separated canonical service
executions from provider events, that value is interpreted as the canonical
TutorResponse execution count. It is not the expected provider-event count.
The provider-event count is 49 because:

- the frozen review execution is deterministic and makes no provider call; and
- six scaffolded explanations each add one comprehension-check generation.

This terminology correction does not modify any formal scenario, policy,
evidence fixture, prompt, or expected decision.

## Frozen Dataset

The exact engineering-audited candidate is promoted by hash without modifying
its contents:

```text
backend/eval/datasets/adaptive_policy_v1_formal_candidate.json
SHA256 3221a85d87ebb788a603e93d3e48343edaf02d2c1595a3574558c4be30bf36db
```

The retained internal value `status = candidate_not_frozen` records the file's
history. Formal authorization now comes from the external freeze manifest and
the runner's exact SHA check. This avoids rewriting or reserializing the
approved 24 scenarios.

## Frozen Conditions

Adaptive:

```text
rule_v2
```

Baseline:

```text
intent_state_blind_v1
```

Both conditions use the same frozen evidence, generation infrastructure,
production prompt path, model, and retry policy. The evaluation adapter exposes
only the registered policy treatment to generation and withholds raw
learner-performance values.

Runtime:

```text
OpenAI chat model       gpt-5.4-mini
Embedding model         text-embedding-3-small
Tutor temperature       0.2
Tutor max tokens        1000
Quiz temperature        0.3
Quiz max tokens         2200
Provider retries        2
Initial retry delay     2.0 seconds
Live retrieval          disabled
Database writes         rollback only
```

## Blinding And Annotation

The A/B assignment uses deterministic balanced randomization:

```text
algorithm  seeded_balanced_shuffle_v1
seed       adaptive-policy-v1-formal-blinding-v1
balance    12 Adaptive-as-A / 12 Adaptive-as-B
```

The blinded artifact contains learner-visible response content only. Quiz
answers, correct option IDs, explanations, review answers, internal IDs,
condition labels, Policy decisions, and reveal mappings remain hidden.

The frozen response rubric and statistical analysis plan are sections 9-11 of
`adaptive_policy_v1_protocol.md`. The primary outcome is blinded pairwise
pedagogical preference. Final annotation requires author review and sign-off.

## Pilot Provenance

The signed-off Pilot remains unchanged at:

```text
backend/eval/results/adaptive_policy/pilot/adaptive_policy_v1_pilot_v1/
```

It contains 8/8 successful scenarios, 16 condition artifacts, 15 canonical
executions, 15 provider events, 15 attempts, no retries, no provider errors,
and a balanced 4/4 A/B assignment. Its exact artifact hashes are recorded in
the machine-readable freeze manifest.

The structural identical-policy control reused one canonical execution.
Internal reason metadata retained from that execution are diagnostic
provenance, not experimental outcomes.

## Formal Gate

Before generation, run the formal preflight from `backend`:

```bash
.venv/bin/python -m eval.run_adaptive_policy_evaluation \
  --run-type formal \
  --dataset eval/datasets/adaptive_policy_v1_formal_candidate.json \
  --config eval/configs/adaptive_policy_v1_formal.config.json \
  --preflight-only
```

The preflight must pass with:

- the exact dataset SHA;
- the frozen model and embedding model;
- matching Policy, Baseline, runner, and adapter versions;
- 44 canonical executions and 49 expected provider events;
- 12 canonical policy-quiz execution probes using the exact frozen chunks;
- zero live concept-retrieval calls during those quiz probes;
- all frozen chunks present with unchanged hashes;
- unchanged production concept resolution; and
- a clean Git worktree.

The replacement formal generation guard is authorized only for the complete
24-scenario run named `adaptive_policy_v1_formal_24case_v2`. A fresh
strengthened preflight and clean Git worktree are still required immediately
before generation. Formal outputs must be retained even if a condition fails.
No prompt, dataset, evidence, Policy, model, or threshold changes may be made
after inspecting formal outputs.
