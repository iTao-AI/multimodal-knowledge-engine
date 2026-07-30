# Validate The Diagnostic-First Context Mechanism Comparison

MKE is a local-first Agent-callable Evidence/Context compiler. Its preferred Agent consumption
path is the compiled-Library fast path. Bounded retrieval fallback remains available when an
Agent needs selective access, and exact-read recovery remains a separate control for recovering
authoritative Evidence bytes.

This guide describes a completed, comparison-only evaluation. The deterministic comparison
rejected the candidate under the frozen development protocol. It did not change Search, Ask, MCP,
active Publication behavior, retrieval defaults, or the compiled Library.

## What O0–O5 Compare

- O0 — current Evidence baseline: observes the existing runtime retrieval and delivery path,
  including exact-read recovery.
- O1 — deterministic unit rank: ranks page-local ContextUnits without changing the product
  retrieval path.
- O2 — fixed-rank unit delivery: keeps O1 selection fixed and delivers complete authoritative unit
  text.
- O3 — source-context index: adds frozen provenance-bound source context to each O1 retrieval
  document only when its residual gate is enabled.
- O4 — source-context delivery: keeps O1 identities fixed and adds bounded source context at
  delivery only when its residual gate is enabled.
- O5 — adjacent-page assembly: keeps current-runtime or O1 identities fixed and adds bounded
  previous-page tail and next-page head for the preregistered cross-page case only when its gate is
  enabled.

These are controlled ablation contrasts, not runtime features awaiting promotion. O1 and O2
exercise deterministic, model-free candidate mechanisms. O3, O4, and O5 are conditional residual
mechanisms.

## Frozen Authority

The checked artifacts bind the following exact identities:

| Authority | SHA-256 |
|---|---|
| Protocol, `tests/fixtures/agent-context-unit-v2/protocol.json` | `8e5ef8c4a6381af84f4dc77534f95eaeaabd6a2efc9c5d47930db75e657c0710` |
| Scientific input lock | `c9f006e8d8dc32499f81a5f7d847707c3744d00ff1971437084347b8c9188fce` |
| Evaluation source seal | `5df1194213603a8682498436484f40eacc13e8c3c02f55e8fb7c08e4925bb0d7` |
| Runtime profile seal | `b3b291be8684dd2de3011c2f4b616b244c6c64d74304877663e295e8d04723a4` |
| O0 baseline artifact | `e71e46abbbee4caf11fb7aa392007fd0901680d0447c34fb479c19c8943e5bea` |
| Development artifact | `64ecc182310d01c43eeeb1b9692a70480f289538ffa0228610405c764a9a6a2a` |
| Development artifact `content_digest` | `0979b30f0634161307fa916b3e826e9aca33667a1c6dc97b3d49cbee505d23fa` |

The protocol and scientific lock bind the constructed development corpus, query policy, source
inventory, mechanism profiles, bounds, residual-gate rules, and verdict rules. The evaluation
source seal binds the exact evaluation implementation used for the observation.

The one-shot workflow accepts a caller-owned diagnostic receipt outside the repository. A started
integrity failure publishes only that bounded receipt; it excludes private paths, credentials, and
free-form exception text. A complete success leaves the diagnostic receipt absent. The retained
baseline and development artifacts are the public authority for this completed result.

## Observed Development Result

The development artifact is a complete canonical
`mke.agent_context_unit_development.v2` object with `status=passed`,
`integrity_status=passed`, and `stage_outcome=candidate_failed`. Here, `candidate_failed` is the
scientific candidate verdict under the frozen protocol, not a software-execution failure.

The exact classifications are:

- `candidate_eligibility_miss`
- `delivery_completeness_miss`
- `query_policy_miss`

The exact mechanism statuses are:

- `O1=candidate_failed`
- `O2=candidate_failed`
- `O3=not_evaluated`
- `O4=not_evaluated`
- `O5=not_evaluated`

O3, O4, and O5 were not dispatched because every residual gate closed with
`control_guardrail_failed`. Their status does not describe a positive or negative mechanism
effect. `holdout_status=not_evaluated` and `runtime_promotion_status=not_evaluated`.

The checked artifact records the frozen per-case metrics, predecessor contrasts, control
guardrails, residual gates, mechanism verdicts, two-workspace portable equality, and the exact
non-claims needed to interpret this result.

## Pure Validation

Do not rerun the one-shot observations. Validate the checked artifacts without ingesting sources or
replaying candidate mechanisms:

```bash
uv run python -m mke.evaluation.agent_context_unit_workflow validate-baseline \
  --protocol tests/fixtures/agent-context-unit-v2/protocol.json \
  --artifact benchmarks/retrieval/agent-context-unit-v2-baseline.json \
  --json

uv run python -m mke.evaluation.agent_context_unit_workflow validate-development \
  --protocol tests/fixtures/agent-context-unit-v2/protocol.json \
  --baseline benchmarks/retrieval/agent-context-unit-v2-baseline.json \
  --artifact benchmarks/retrieval/agent-context-unit-v2-development.json \
  --json
```

Pure validation does not ingest, observe, grade anew, or publish. It validates retained canonical
bytes and their closed authority links. A future strict-live source check, holdout observation, or
new comparison requires separate authority.

## Limits And Non-Claims

The artifact records these exact limitations:

- `constructed_development_corpus`
- `public_nonblind_future_holdout`

It also records:

- `development_only_until_separate_holdout_authority`
- `comparison_only`
- `no_retrieval_quality_claim`
- `no_performance_claim`
- `no_runtime_promotion`

In plain language, this is a constructed development corpus with a public-nonblind future holdout.
The result makes no retrieval-quality claim, no performance claim, no generalization claim, and no
runtime-promotion claim. It does not establish a positive mechanism effect, justify a product
retrieval change, or authorize holdout access.
