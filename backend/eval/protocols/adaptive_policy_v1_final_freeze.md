# Adaptive Policy V1-B Final Freeze

## Status

**Frozen on 24 July 2026.**

The independent eight-scenario Pilot completed successfully and received
validity sign-off. No second Pilot is authorized. The next permitted operation
is a read-only formal preflight followed, if it passes, by one frozen 24-case
formal run.

The machine-readable authority for this freeze is
`adaptive_policy_v1_final_freeze.json`.

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
- all frozen chunks present with unchanged hashes;
- unchanged production concept resolution; and
- a clean Git worktree.

Only after a passing preflight may the formal generation guard be used. Formal
outputs must be retained even if a condition fails. No prompt, dataset,
evidence, Policy, model, or threshold changes may be made after inspecting
formal outputs.
