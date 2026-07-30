# Diagnostic-First Context Mechanism Separation v2 Plan Review

Status: **CLEAN / RECOMMENDED FOR APPROVAL — TARGETED AUTHORITY RECONCILIATIONS APPLIED**

This public-neutral record captures the plan review for:

```text
docs/superpowers/plans/2026-07-30-diagnostic-first-context-mechanism-separation-implementation.md
```

The review uses the approved design, live repository, current tests and CI, existing retrieval and
evaluation ports, and retained scientific lessons from the discarded prototype. Historical
incomplete observations are diagnostic evidence only.

## CEO / Product Review

The plan keeps the product question narrow: whether the retrieval fallback loses context that an
Agent needs, and which mechanism layer owns the loss. It does not turn the comparison into a
general RAG rewrite or use a chunking trend as a promotion premise.

The selected staged design is preferable to maintenance-only, immediate candidate coding, and
continuing the discarded prototype because it:

- makes the current runtime O0 the falsification gate;
- exits docs/regression-only when no targeted failure exists;
- creates candidate code only after a retained RED;
- makes source-context indexing/delivery conditional on residual gates;
- treats scientific negative and inconclusive results as acceptable outcomes; and
- keeps holdout, runtime promotion, publication, and release separately gated.

Product review found no unresolved scope or value decision.

## Design Review

Skipped as not applicable. The stage adds no user interface or visual interaction.

## Engineering Review

Engineering review identified and closed the following plan-level findings before implementation:

1. **Clean-clone scientific-input authority:** the initial draft relied on comparing against v1
   files that are not part of current `main`. Task 0 now creates an immutable normalized
   `scientific-input-lock.json`; a one-time import receipt proves the retained source bundle, while
   permanent tests run from a clean clone without the discarded branch.
2. **Private runtime access:** the plan rejects the prototype's `KnowledgeEngine._store` and
   private CJK selector usage. O0 uses public Search/Read, a separate read-only `SQLiteStore` for
   existing diagnostics, the public CJK pure scorer, and a public compiled-Library snapshot for
   stable source-fingerprint mapping.
3. **Direct source authority:** explicit O0 and development evaluator inventories replace
   whole-`src/mke` identity. Historical artifacts validate recorded source seals; strict-live
   replay remains separate.
4. **Candidate import boundary:** candidate files and commands cannot exist before retained O0 RED.
   The workflow uses lazy development imports only after baseline authorization.
5. **O0 branch ordering:** both successful O0 branches now commit and pure-validate the baseline
   artifact before diverging.
6. **Shared verification completeness:** the source-inventory regression is now part of the common
   focused gate.
7. **O3 dependency direction:** assembly produces immutable source-context components; ranking
   consumes them; neither imports grading. Workflow remains the orchestrator.
8. **Capacity authority:** exact-boundary/one-over checks occur before row parsing, encoding, or
   allocation. Timing is excluded from correctness.
9. **One-shot diagnostics:** every substage has a typed fault test and external receipt contract;
   started failures cannot be retried or reclassified as scientific outcomes.
10. **Physical protocol authority:** common metadata, label-blind observer inputs, and grading
    payloads now live in separate modules. Observation, baseline, diagnostics, segmentation,
    ranking, and assembly cannot import grading loaders; workflow may reach them only after the
    O0 complete observation seal or, for development residual-gate derivation, after both
    workspaces have formed byte-identical O1/O2 intermediate portable seals. Candidate modules
    receive only typed gate decisions and remain unable to reach grading or label authority.
11. **Historical whole-source recurrence:** current `main` still has a whole-`src/mke` refresh
    helper for the legacy baseline, but retained validation is recorded-authority-only and has an
    explicit unrelated-source-addition regression. The shared historical gate now includes that
    regression and canonical retrieval-evidence validation so additive v2 modules cannot silently
    recreate the previous identity failure.
12. **Residual-gate diagnostic order:** the stable 14-token vocabulary now places
    `residual_gate` after the O1/O2 intermediate stages and before every residual candidate stage.
    Label-load, gate-derivation, and typed-dispatch failures therefore stop before candidate entry
    and cannot be rewritten as `adjacent_page_assembly`.
13. **O3 per-document context authority:** every exact O1 unit owns an independent retrieval
    document. Provenance-bound context can be reused across unit documents, while duplicates
    remain forbidden within one O3 document and O4/O5 retain cross-output delivery deduplication.

The plan preserves strict Pyright and prohibits the prototype's file-level type-check weakening.
No unresolved engineering decision remains.

## Developer Experience Review

The operator workflow has four stable common commands (`diagnose`, `baseline`,
`validate-baseline`, `validate-receipt`) and adds `development` /
`validate-development` only on the authorized candidate branch. There is no holdout command.

The plan reduces operator ambiguity through:

- exact exit semantics: scientific outcomes 0, integrity 1, argparse 2;
- stable machine tokens and bounded JSON;
- no local path or free-form exception in public results;
- one external receipt path per scientific invocation;
- pure validation that never reruns observation;
- explicit result branches and a unique next task;
- shared verification gates instead of copied command variants; and
- no repeated approval round when the approved plan and exact candidate seal remain unchanged.

The plan is intentionally detailed because it governs two irreversible scientific invocations.
Conditional tasks keep the common critical path limited to protocol, diagnostics, O0, and one
terminal branch. No unresolved DX decision remains.

## Evaluation And Context Review

The plan treats Context as the information actually delivered to the Agent, not as a synonym for
prompt text, Memory, or retrieval score. It separately observes tokenization/query policy,
eligibility, rank, Evidence granularity, delivery completeness, source context, and adjacent-page
assembly.

Evaluation review confirms:

- frozen development and sealed future holdout roles;
- label-blind observation before pure grading;
- per-query exact spans and guardrails as verdict authority;
- aggregate metrics as diagnostics only;
- O0-O5 as ablation contrasts, not features awaiting adoption;
- ContextUnit byte/provenance authority;
- source/context component attribution;
- negative, mixed, qualified, and inconclusive terminal outcomes;
- no LLM-as-judge, timing, performance, production, or generalization claim; and
- no automatic Memory writeback, Agent loop, or runtime promotion.

This matches the required falsification-first Context/Evidence/Evaluation framing while leaving
project facts to code, protocol, tests, artifacts, and one-shot process evidence.

## Targeted Task 10 Stage-Order Reconciliation

Task 10 review exposed a conflict between residual-gate derivation and the earlier label-open
ordering: residual dispatch requires the frozen development grading payload, while candidate
observation must remain label-blind. The reconciled authority uses two distinct seal boundaries.
Both fresh workspaces first complete O1/O2 and produce byte-identical intermediate portable seals
before any development label access. The workflow then opens the frozen grading payload exactly
once, derives one residual-gate set from that payload and sealed O0/O1/O2 observations, and passes
candidate modules only typed gate decisions plus label-blind frozen inputs. After all dispatched
residual observations complete, the workflow forms the existing `complete_observation_seal`,
requires complete workspace equality, and only then pure-grades, validates, and publishes.

This reconciliation does not add a public diagnostic substage token and does not change the
corpus, queries, labels, required spans, mechanism profiles, bounds, residual-gate rules, or verdict
rules. O0 was not rerun and development had not started when the authority conflict was found.
Candidate modules remain label-blind, and pure grading remains after the complete observation
seal. This record does not claim that Task 10 implementation or verification is complete.

## Targeted Task 10 Amendment E Reconciliation

Actual-diff review found that the public `residual_gate` stage still followed O3/O4/O5 even though
the grading payload and gate set are required before dispatch. Amendment E preserves the same 14
public tokens but orders `residual_gate` immediately after `fixed_rank_delivery`. The workflow
must complete O1/O2 equality, load the development grading payload exactly once, derive and
validate the typed gate set, and complete `residual_gate` before any residual mechanism entry.
Candidate-stage failures continue to retain their own distinct stages.

The same review found that one shared deduplication inventory made O3 context consumption depend
on unit enumeration order. Amendment E separates index-time and delivery-time authority. O3 may
reuse the same provenance-bound heading or neighboring unit across independent O1 retrieval
documents, while each document rejects duplicate kinds, ranges, and payloads. O4/O5 keep their
existing cross-selected-output delivery deduplication.

No corpus, query, label, required span, profile, bound, mechanism parameter, context order,
residual rule, verdict rule, artifact schema, product runtime, dependency, holdout boundary, or
scientific observation changes. O0 remains the single retained invocation, and development has
not started. This record does not claim that the corresponding code or tests are complete.

## Final Decision

**Recommended:** approve the complete implementation plan and mechanically land this plan plus this
review record on the existing v2 spec branch.

The actual landed diff must receive independent authority review before implementation dispatch.
A later failure is attributed first to spec/plan/handoff, acceptance/gate, environment, or
implementation; repair count alone does not replace root-cause attribution.

No unresolved substantive decision remains. Holdout, push/PR, merge, release, cleanup, and runtime
promotion are not authorized by this review.
