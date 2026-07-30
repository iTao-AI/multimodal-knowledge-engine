# Diagnostic-First Deterministic Context Mechanism Separation v2

Status: approved design specification. Implementation, holdout observation, runtime promotion,
and publication remain separately gated.

## 1. Decision

MKE will run one bounded, diagnostic-first comparison that separates:

1. current Evidence retrieval and delivery;
2. deterministic page-internal unit segmentation;
3. fixed-rank unit delivery;
4. source-context indexing;
5. source-context delivery; and
6. bounded adjacent-page assembly.

The comparison is evaluation-only. It does not change the runtime retrieval path, public Python
API, CLI, MCP tools, schemas, dependencies, provider set, or release behavior.

The stage begins from the current reviewed `main` baseline. A discarded noncanonical prototype and its
incomplete observations are immutable historical evidence, not implementation history to merge.
Only independently reviewed pure functions, invariants, and test ideas may be selectively
reimplemented or transplanted.

## 2. Product premise

MKE is a local-first, Agent-callable Evidence and Context compiler for multimodal knowledge. Its
fast path is a compiled Library that an Agent can consume directly. Retrieval remains a bounded
fallback for exact or selective access to original Evidence.

The product question is not whether MKE should adopt a fashionable chunking or contextual
retrieval technique. The question is whether the current retrieval fallback loses Agent-consumable
context, and, if it does, which layer is responsible:

- query policy or tokenization;
- candidate eligibility or ranking;
- Evidence granularity;
- delivery truncation or output completeness;
- missing source context; or
- missing bounded cross-page assembly.

Only a frozen, label-blind observation followed by a pure grader can answer that question.

## 3. Live baseline and preserved authority

The design preserves:

- Run as execution authority;
- Publication as version and active-state authority;
- Evidence as provenance authority;
- active-only retrieval eligibility;
- deterministic retrieval-order revision 2 and its cursor contract;
- current FTS and CJK route separation;
- exact-read recovery as a separate control;
- existing Python, CLI, MCP, source-pack, installed-wheel, and compiled-Library compatibility;
- all checked-in historical retrieval artifacts and their interpretation.

The implementation may reuse existing evaluation-only primitives for:

- source identity;
- no-follow file reads;
- atomic no-replace JSON publication;
- stable public result fields; and
- pure artifact validation.

It must not broaden the authority of any historical artifact or freeze all `src/mke/**/*.py`.

## 4. Prior evaluation lesson

An earlier evaluation prototype established that the corpus and deterministic projection were
structurally viable, but it did not produce a complete candidate observation. Multiple distinct
base and extension failures could collapse into the same public
`candidate_observation_integrity_invalid` classification.

That result supports only these conclusions:

- the targeted context-loss hypothesis remains worth testing;
- the evaluator needs substage-specific diagnostics before another scientific observation;
- no segmentation or contextual retrieval mechanism has been qualified or rejected; and
- no prior incomplete observation may be retried or promoted.

It does not support a mechanism, quality, performance, or runtime claim.

## 5. Goals

1. Freeze a v2 protocol before candidate implementation.
2. Preserve the exact development and holdout corpus, queries, labels, profiles, bounds, and
   O0-O5 mechanism parameters previously selected for the comparison.
3. Build a provider-free diagnostic harness that distinguishes every observation substage.
4. Run one label-blind O0 baseline observation.
5. Stop as docs/regression-only when the targeted baseline failure is absent.
6. Implement candidate mechanisms only after the O0 failure is observed.
7. Run one development candidate observation with two fresh workspaces.
8. Separate tokenization/query-policy, ranking, granularity, delivery completeness, contextual
   indexing, contextual delivery, and adjacent-page assembly.
9. Produce a scientific negative, mixed, qualified, or evaluation-inconclusive result without
   automatic promotion.
10. Keep the public holdout sealed and unconsumed until a separate authorization.

## 6. Non-goals

- No runtime retrieval, ranking, Evidence, Publication, or active-state change.
- No GraphRAG, RAPTOR, dense retrieval, RRF, reranker runtime, or Agentic RAG loop.
- No OCR, ASR, model download, new provider, HTTP service, SaaS, or new dependency.
- No autonomous Agent loop, memory writeback, self-modification, or automatic promotion.
- No LLM-as-judge or subjective human scoring.
- No throughput, latency, database-size, cost, or performance-improvement claim.
- No statistical-generalization claim from the constructed corpus or public nonblind holdout.
- No complete trace platform, OpenTelemetry integration, or generic EvalOps framework.
- No reuse of incomplete observation artifacts as comparison evidence.
- No implementation of holdout recording in the first approved implementation stage.

## 7. Alternatives

| Alternative | Benefit | Limitation | Decision |
|---|---|---|---|
| Maintenance | Lowest risk and cost | Does not explain a reproducible context-loss failure | Always retained as control and fallback |
| Docs/regression-only | Preserves a targeted regression without new mechanism code | Cannot compare segmentation or context mechanisms | Required exit when O0 failure is absent |
| Deterministic segmentation comparison | Smallest bounded test of candidate granularity | Changes corpus statistics and cannot isolate every delivery issue | First candidate family |
| Contextual retrieval comparison | Can restore missing source context | More complex and easy to over-attribute | Conditional on a preregistered residual gate |
| Continue the discarded prototype | Reuses the most history | Confounds attempt history, diagnostics, and scientific authority | Rejected |
| New clean-main v2 with selective transplant | Preserves scientific inputs while repairing the Harness | Requires explicit source mapping and fresh review | Selected |

## 8. Protocol and frozen inputs

The canonical protocol schema is:

```text
mke.agent_context_unit_protocol.v2
```

The fixture root is:

```text
tests/fixtures/agent-context-unit-v2/
```

The protocol freezes:

- source receipts, bytes, SHA-256 values, page counts, and redistributable-source basis;
- development and holdout partitions;
- query IDs, query text, expected route, and query class;
- required spans, exact UTF-8 byte ranges, text SHA-256 values, locators, and roles;
- candidate segmentation profile;
- projection, delivery, candidate-pool, source, unit, and byte ceilings;
- O0-O5 mechanism IDs and parameters;
- runtime profile fields and rank-profile identities;
- residual-gate definitions;
- grader and verdict revision; and
- separate expected repository-relative source-path inventories for O0 and development.

The protocol preregisters source paths and roles. Record-time source seals add byte counts and
digests only after the corresponding files exist; candidate source bytes are not fabricated or
backfilled before candidate implementation.

The v2 fixture values must be byte-for-byte equivalent to the reviewed v1 scientific inputs.
Diagnostic schemas, workflow orchestration, and direct evaluator source inventory are new v2
authority and therefore receive new identities.

Any change to corpus, query, label, required span, mechanism parameter, bound, profile, residual
gate, or verdict rule requires a new protocol revision. It cannot repair an observation.

## 9. Holdout authority

The holdout is public and nonblind. Its separation is enforced by code and phase authority, not
cryptographic secrecy.

Before a separately approved holdout phase:

- development modules cannot open holdout source receipts, observer cases, labels, or source bytes;
- the development observer and diagnostic module cannot import holdout loaders;
- pure development validation cannot open holdout;
- no holdout receipt or comparison artifact exists; and
- no holdout command is implemented or invoked in the first implementation stage.

The small holdout can verify workflow separation and exact frozen-case behavior. It cannot prove
production quality or statistical generalization.

## 10. Source and artifact identity layers

Three identity modes are distinct:

### 10.1 Record-time strict source seal

Before an observation starts, the workflow records exact identities for the direct evaluator,
protocol, profile, and input files used by that observation.

The seal:

- uses sorted unique repository-relative paths;
- rejects symlinks, nonregular files, physical aliases, and mid-read mutation;
- records byte count and SHA-256 for each file;
- records the aggregate source identity; and
- does not use a whole-source glob or the Git tree as validation authority.

A Git commit may be recorded as audit metadata but is not a substitute for the direct file map.

### 10.2 Retained artifact validation

A checked-in historical artifact validates against:

- its recorded source seal;
- its recorded protocol/profile/input seals;
- its own schema and internal digests; and
- its recorded observation and verdict data.

Future additive evaluator files do not invalidate the historical artifact.

### 10.3 Strict-live replay

A separate strict-live command may require current direct source identities to match an artifact.
Failure of strict-live replay does not reinterpret or corrupt the historical artifact.

## 11. Module boundaries

The implementation uses project-specific evaluation modules with one-way dependencies:

```text
protocol and identity
        |
        v
segmentation / ranking / assembly
        |
        v
observation schemas and seals
        |
        v
pure metrics and verdict
        |
        v
workflow and publication
```

Required boundaries:

- protocol parsing does not ingest or observe;
- observer inputs contain query text and source/profile identities, never qrels, labels, required
  spans, expected locators, strata, or verdict hints;
- segmentation, ranking, and assembly do not import labels or grader code;
- grader and validators do not call ingest, projection, ranking, assembly, observers, recorders, or
  publication;
- diagnostics do not import labels or holdout loaders;
- workflow orchestrates typed components and does not implement mechanism logic;
- runtime and public product modules do not import v2 evaluation modules.

The discarded prototype's large workflow and grading modules are not transplanted wholesale.
Pure functions move only with focused tests and an explicit responsibility in this graph.

## 12. ContextUnit authority

A `ContextUnit` is a deterministic, exact, page-local slice of one active parent Evidence item.
It records:

- source fingerprint;
- Publication and Evidence provenance;
- page and locator authority;
- parent stable locator;
- UTF-8 start and end offsets;
- exact text bytes and SHA-256;
- stable projection ID; and
- rank-profile ID.

Units are ordered, gap-free, non-overlapping, and concatenate to the exact parent Evidence bytes.
Normalization can discover boundaries but never rewrites authoritative bytes.

The frozen segmentation profile is:

- target 1,024 UTF-8 bytes;
- minimum 256 bytes except a final page span;
- maximum 1,536 bytes;
- zero overlap;
- hard page boundary;
- original whitespace retained; and
- frozen heading, paragraph, sentence, hard-split, and final-merge rules.

Page-crossing context is excluded from ContextUnit construction and belongs only to O5.

## 13. Observation model

### O0 — current Evidence baseline

- Uses the exact current runtime strategy and profile.
- Records compiled query, route, eligible candidates, raw ranked Evidence identities, arm-local
  scores, match hints, excerpt, exact-read recovery, and required-role coverage.
- Establishes separate FTS and CJK parity.
- Cannot import or call candidate builders.

### O1 — deterministic unit rank

- Uses page-internal ContextUnits.
- Ranks only authoritative unit text with the same lexical scoring family.
- Records candidate expansion and bounds.
- Names only `segmentation_rank_effect`.
- Does not claim a pure granularity effect because segmentation changes corpus statistics.

### O2 — fixed-rank unit delivery

- Consumes sealed selected identities.
- Changes delivery from current excerpt to complete authoritative unit text.
- Does not select by qrel or rerank.
- Names only `segmentation_delivery_effect`.

### O3 — source-context index

- Uses the exact O1 units.
- Runs only when the preregistered residual indexing/ranking gate remains after O1/O2.
- Adds one frozen source-derived context treatment to retrieval text.
- Delivers unchanged unit text.
- Records unit-origin, context-origin, context-only, and component attribution.
- Names only `context_index_effect`.

### O4 — source-context delivery

- Freezes O1 selected identities.
- Runs only for a preregistered residual delivery failure.
- Adds provenance-bound source context at delivery time.
- Does not rebuild, select, or rerank.
- Names only `context_delivery_effect`.

### O5 — adjacent-page assembly

- Freezes current-runtime or O1 selected identities.
- Adds bounded previous-page tail and next-page head from the same active source and Publication
  order.
- Does not change segmentation, indexing, eligibility, or ranking.
- Names only `cross_page_assembly_effect`.
- Missing, inactive, ambiguous, or nonadjacent pages produce explicit no-context records.

O0-O5 are ablation contrasts, not six features awaiting promotion.

## 14. Delivery and context budgets

The existing Agent envelope remains authoritative:

- top 5 primary results;
- top 10 diagnostic ranks;
- at most 2,048 UTF-8 bytes per delivered item;
- at most 16,384 UTF-8 content bytes per response; and
- at most 32,768 UTF-8 bytes in the canonical envelope.

For O3/O4:

- authoritative unit text is never truncated;
- source-derived context, component labels, and separators total at most 512 bytes;
- unit plus context totals at most 2,048 bytes;
- allocation priority is heading, previous unit, then next unit; and
- requested, returned, omitted, and truncated bytes are recorded.

For O5:

- selected excerpt authority is fixed before assembly;
- previous-page tail and next-page head each have a 256-byte ceiling;
- separators count toward the item budget; and
- any excerpt reduction follows a frozen allocation rule, never qrels.

Source display names and filenames are excluded from verdict-bearing retrieval text. Misleading-name
controls enforce that boundary.

## 15. Diagnostic substage taxonomy

One observation advances through these stable substages:

1. `authority_preflight`
2. `runtime_baseline`
3. `source_snapshot`
4. `unit_projection`
5. `unit_rank`
6. `fixed_rank_delivery`
7. `adjacent_page_assembly`
8. `source_context_index`
9. `source_context_delivery`
10. `residual_gate`
11. `complete_observation_seal`
12. `grading`
13. `artifact_validation`
14. `publication`

Each component returns a typed success value or raises a project-specific stage error containing:

- substage;
- stable error code; and
- safe error family.

An unexpected exception is normalized at the active substage as
`unexpected_stage_failure`. It must not erase the substage or be reclassified as a scientific
outcome.

## 16. Public result and operator receipt

Two evidence layers are intentionally separate.

### 16.1 Public result

The stable public-neutral result contains:

```text
schema_version
status
phase
integrity_status
stage_outcome
mechanism_statuses
holdout_status
runtime_promotion_status
output_state
publication_outcome
problem
cause
next_step
first_failed_gate
diagnostic_receipt_status
diagnostic_receipt_sha256
```

It does not contain a local path or free-form exception text.

### 16.2 Operator diagnostic receipt

The receipt schema is:

```text
mke.agent_context_unit_diagnostic_receipt.v1
```

It contains only:

- protocol, profile, phase-appropriate evaluator-source, and observation identities;
- phase and attempt kind;
- observation-started status;
- ordered completed-substage records and their portable output digests;
- last completed substage;
- failed substage;
- stable error code and safe error family;
- output and publication states;
- bounded stderr byte count and SHA-256 when available;
- receipt schema and content digest.

It excludes:

- absolute or private paths;
- query and source text;
- labels, qrels, and holdout content;
- generated workspace IDs and opaque Evidence IDs;
- traceback and free-form exception messages;
- credentials, environment variables, and user data.

The receipt is caller-owned, repository-external diagnostic evidence. It is not a comparison
artifact and cannot support a mechanism verdict.

## 17. Receipt and observation-start semantics

Before opening a real source or starting a scientific observation, the workflow preflights:

- protocol, profile, source, and direct evaluator identities;
- canonical artifact destination;
- diagnostic receipt destination;
- no-follow lexical parents and exact basenames;
- phase-appropriate direct evaluator source seal; and
- output/receipt absence or valid retained state.

A preflight rejection does not consume the scientific observation budget because no source,
observer, grader, or publication action has started. It may be corrected only under a separately
reviewed bounded recovery.

The observation starts:

- for O0, when the first real development source is opened; or
- for development, when the first candidate workspace begins source ingestion.

After observation start:

- any integrity failure consumes the one-shot budget;
- later substages do not run;
- grading, holdout, and comparison publication remain forbidden;
- the operator receipt is atomically published, read back, and validated before normal CLI exit;
  and
- the public result exposes receipt status and digest, never its physical path.

If an in-process failure cannot produce a complete visible receipt, the result is:

```text
problem=agent_context_diagnostic_receipt_unavailable
cause=operator_receipt_not_complete_visible
next_step=repair_diagnostic_harness_before_new_protocol
```

A hard process termination can prevent both receipt and normal JSON output. The retained process
ledger then proves the absence; the stage closes as evaluation-inconclusive and is not retried.

## 18. Artifact lifecycle

Canonical paths:

```text
benchmarks/retrieval/agent-context-unit-v2-baseline.json
benchmarks/retrieval/agent-context-unit-v2-development.json
```

Future, separately authorized holdout paths:

```text
benchmarks/retrieval/agent-context-unit-v2-holdout-receipt.json
benchmarks/retrieval/agent-context-unit-v2-comparison.json
```

The first implementation stage creates at most the protocol, baseline artifact, and development
artifact. It does not implement or create holdout outputs.

Visible-state authority:

| State | Meaning | Unique action |
|---|---|---|
| Output and receipt absent before start | Eligible after full preflight | Start once |
| Preflight rejected before start | No scientific attempt | Correct only under separate authority |
| Complete baseline exists | O0 is retained | Pure-validate; never rerun |
| Complete development exists | Development is retained | Pure-validate; never rerun |
| Receipt exists and artifact absent | Started terminal failure | Retain and stop |
| Artifact visible invalid or durability uncertain | Publication terminal | Retain visible bytes and stop |
| Symlink, nonregular, alias, or invalid parent | Path authority invalid | Do not start |

## 19. Phase model

### Phase A — protocol and diagnostic harness

1. Freeze v2 scientific inputs and direct source inventory.
2. Implement source, path, and atomic-publication primitives with focused regression tests.
3. Implement diagnostic stages, typed errors, receipt schema, and pure receipt validator.
4. Run provider-free synthetic fault tests for every substage using stub stage callables rather
   than candidate mechanism code.
5. Prove labels, grader, candidates, and holdout remain inaccessible.

No real source observation is authorized until Phase A is review-clean and the full regression
matrix passes.

### Phase B — one-shot O0

1. Seal the diagnostic harness and label-blind O0 observer.
2. Run full tests, Ruff, Pyright, build, product proof, and consumer compatibility.
3. Invoke O0 exactly once.
4. Pure-validate retained bytes without rerunning observation.

O0 terminal branches:

```text
targeted failure absent
  -> status=passed
  -> stage_outcome=docs_regression_only
  -> no candidate implementation

targeted failure observed
  -> status=passed
  -> stage_outcome=baseline_red_observed
  -> authorize Phase C

observation incomplete
  -> status=failed
  -> stage_outcome=evaluation_inconclusive
  -> retain receipt or process ledger
  -> close v2
```

### Phase C — candidate implementation

The protocol parameters remain frozen. Candidate mechanisms are implemented with TDD and
label-access barriers. Any algorithm ambiguity that requires a profile, parameter, query, label,
bound, residual-gate, or verdict change stops the stage and requires a new protocol rather than an
in-place repair.

### Phase D — one-shot development observation

1. Seal direct candidate source identities.
2. Run the complete regression and compatibility matrix.
3. Invoke development exactly once.
4. Use two fresh workspaces inside the single invocation.
5. Before any development label is opened, complete O1/O2 in both fresh workspaces, form an
   intermediate portable seal for each workspace, and require the O1/O2 portable bytes to be
   byte-identical. This intermediate seal does not add a public diagnostic substage token.
6. Only after the O1/O2 intermediate seal succeeds, open the frozen development grading payload
   exactly once in the workflow and derive residual gates only from that payload plus the sealed
   O0/O1/O2 observations.
7. Pass O3/O4/O5 candidate modules only typed residual-gate decisions, the label-blind observer
   contract, and existing frozen candidate inputs. Do not pass the grading payload, required spans,
   labels, qrels, expected locators, or hypothesis and verdict hints into candidate modules.
8. Run O3/O4 only when their preregistered residual gates are true, run O5 only for
   preregistered cross-page hypotheses, and use the same gate set in both workspaces.
9. After every dispatched mechanism completes, form `complete_observation_seal` and again require
   the complete workspace A/B portable observation bytes to be byte-identical.
10. Pure-grade the complete seal, validate the artifact, and publish atomically.

The O1/O2 intermediate seal is an internal workflow authority boundary. The stable 14-stage public
substage taxonomy remains unchanged.

Development receives no retry and no attempt 2.

### Phase E — development review

The authority review validates:

- protocol and source seals;
- receipt absence on success or exact receipt authority on failure;
- observer label blindness;
- portable equality;
- per-query metrics and classifications;
- mechanism status and verdict recomputation;
- boundedness and provenance;
- checked-in artifact bytes; and
- public claims and non-claims.

Holdout remains a separate future phase and requires new user authorization.

## 20. Metrics

Per query and observation:

- query compilation status and actual route;
- candidate eligibility and bounded candidate count;
- required-span-containing candidate presence, computed only by the grader;
- raw rank at 1/3/5/10;
- unique parent Evidence at 1/3/5/10;
- parent-collapsed rank and coverage;
- candidate expansion ratio;
- arm-local score and rank-profile identity;
- selected candidate identities;
- unique required-span coverage at 5;
- delivered role coverage at 5;
- context sufficiency at 5;
- exact-read recovery coverage;
- delivered bytes and useful-span density;
- context-only match count and component attribution;
- duplicated context bytes;
- hard-negative and false-relevant-hit status;
- deterministic observation digest; and
- mechanism and target metric separation.

Exact diagnostic layers:

- `token_presence`;
- `selection_recall`;
- `delivery_recall`;
- `output_completeness`;
- `provenance_exactness`; and
- `deterministic_equality`.

Aggregate Recall@1/3/5, MRR@5, and nDCG@10 are diagnostic summaries only over comparable frozen
labels. Per-query exact span and guardrail results are verdict authority. Durations, database size,
and timing are diagnostic and excluded from deterministic verdict equality.

## 21. Pure grading and classifications

The grader receives:

- sealed label-blind observations;
- frozen grading payload;
- frozen required spans and roles; and
- frozen residual-gate definitions.

It recomputes every classification. The protocol can define a hypothesis stratum but cannot set an
observed cause.

Scientific classifications include:

- `query_policy_miss`;
- `candidate_eligibility_miss`;
- `rank_miss`;
- `rank_regression`;
- `delivery_completeness_miss`;
- `segmentation_rank_effect`;
- `segmentation_delivery_effect`;
- `context_index_effect`;
- `context_delivery_effect`;
- `cross_page_assembly_effect`;
- `context_only_match`;
- `mechanism_ambiguous`; and
- `not_observed_under_protocol`.

Integrity failures are not scientific classifications.

## 22. Development qualification

A mechanism is `candidate_qualified` only when:

1. it closes its preregistered targeted failure with exact required-span and role coverage;
2. current-success and hard-negative development cases do not regress;
3. query policy, route, active-only, provenance, and deterministic equality pass;
4. all source, unit, candidate, context, and delivery ceilings pass;
5. no qrel, label, filename, opaque ID, or workspace order influences candidate ranking,
   selection, delivery or context bytes, or portable observation serialization; development labels
   may affect only preregistered residual-gate dispatch after the O1/O2 intermediate seal and never
   flow into candidate modules;
6. mechanism attribution is unique under the frozen contrasts; and
7. the result is independently recomputed from sealed bytes.

Selection policy:

- if segmentation closes the failure, keep the simpler segmentation candidate and do not infer a
  need for contextual retrieval;
- contextual indexing or delivery can qualify only for a residual failure left by O1/O2;
- improvement plus regression is `mechanism_ambiguous`;
- no strict bounded advantage yields `candidate_failed` or `maintenance_preferred`;
- incomplete observation yields no scientific verdict.

No candidate uplift is required for the evaluation phase to succeed.

## 23. Exit semantics

Scientific outcomes use exit 0:

- `docs_regression_only`;
- `not_observed_under_protocol`;
- `candidate_failed`;
- `candidate_qualified`;
- `mechanism_ambiguous`; and
- `maintenance_preferred`.

Integrity, source, path, execution, diagnostic-receipt, artifact, or publication failures use exit
1. Argparse misuse uses exit 2.

`runtime_promotion_status` is always:

```text
not_evaluated
```

## 24. Targeted RED requirements

Before corresponding implementation, tests must demonstrate:

- base and extension faults of the same Python exception type resolve to different substages;
- each of the 14 substages has an authoritative injected-failure RED;
- an unknown exception retains the active substage and stable error family;
- diagnostic receipt absent/preexisting/symlink/nonregular/tamper/durability behavior;
- receipt failure prevents normal success and preserves artifact absence;
- protocol, profile, source, and direct evaluator identity tamper;
- exact no-follow and physical-alias rejection;
- observer inputs remain label-free;
- qrel and holdout access are blocked before grading or authorization;
- ContextUnits are gap-free, nonoverlapping, byte-exact, and stable across Unicode boundary cases;
- capacity exact-boundary passes and one-over fails before allocation;
- FTS and CJK parity remain separate;
- arm-local scores cannot be compared across mechanisms;
- O2/O4/O5 preserve sealed selected identities;
- context components have exact attribution and provenance;
- context-only matches resolve to origin Evidence;
- misleading filenames remain excluded;
- separator, cap, truncation, and duplication accounting are exact;
- no N+1 Evidence reads;
- fresh workspace identities do not change portable bytes;
- scientific negative outcomes exit 0 and keep holdout closed;
- integrity outcomes exit 1, produce no comparison artifact, and keep holdout closed;
- grader and pure validators cannot invoke builders, observers, recorders, replay, or publication;
- historical artifacts and compatibility semantics remain unchanged; and
- Python, CLI, MCP, source-pack, installed-wheel, compiled-Library, and full-suite regressions remain
  green.

## 25. Verification order

Required order:

1. targeted RED collection and exact failure markers;
2. focused GREEN;
3. adjacent evaluation tests;
4. historical artifact and compatibility tests;
5. runtime/interface/schema/consumer tests;
6. full suite;
7. Ruff;
8. Pyright;
9. ordinary build;
10. product proof and demo;
11. installed-wheel, source-pack, MCP completeness, and compiled-Library proofs when required by
    the repository;
12. candidate source and protocol seal readback;
13. canonical-path absence;
14. one-shot observation; and
15. manual byte readback followed by later pure validation.

No test, formatter, generator, validator, or proof runs between the final candidate seal and its
one-shot invocation unless the implementation plan explicitly classifies it as part of the seal.

## 26. CI

CI:

- validates protocol and fixture identities;
- runs synthetic diagnostic fault tests;
- validates checked-in baseline and development artifacts purely;
- runs model-free deterministic comparisons;
- preserves historical retrieval compatibility;
- runs supported Python versions and existing consumer proofs; and
- never records O0, development, or holdout.

CI does not require network, model cache, OCR, ASR, or new extras.

## 27. Documentation

When the terminal branch is public-reviewable, add one maintainer document covering:

- product premise and bounded evaluation purpose;
- O0-O5 contrasts;
- protocol and source identity;
- diagnostic receipt and privacy boundary;
- one-shot workflow;
- metrics and verdict rules;
- result consumption;
- holdout authorization;
- runtime compatibility;
- non-claims; and
- no-promotion boundary.

Documentation must distinguish:

- compiled-Library fast path;
- retrieval fallback;
- exact-read recovery;
- comparison-only mechanisms; and
- future runtime promotion.

## 28. Publication matrix

| Terminal result | Public branch contents | Default lifecycle |
|---|---|---|
| `docs_regression_only` | Protocol, O0 artifact, targeted regression, bounded docs | Eligible for review |
| Complete scientific negative or mixed result | Protocol, evaluator, tests, development artifact, non-claims | Eligible for review |
| Complete qualified development result | Same, still comparison-only | Eligible for review; holdout separately gated |
| `evaluation_inconclusive` | Repository-external receipt and maintainer authority review | No mechanism PR by default |
| Independent reusable diagnostic maintenance | Small diagnostic-only diff under a new maintenance decision | Separate review; never presented as comparison |

An incomplete evaluation is not made publishable by adding documentation.

## 29. Repair and cost budget

- One original implementation, review, or preobservation terminal-gate failure permits at most two
  evidence-backed bounded repair rounds.
- A third recurrence of the same terminal gate stops the stage and requires architecture review.
- Each implementation task receives one actual-diff review and at most two targeted review-fix
  rounds.
- A plan contradiction must be resolved before code is written.
- Repeated contradiction in the same authority class closes the stage instead of creating nested
  amendments.
- Corpus, query, label, span, mechanism parameter, bound, residual gate, or verdict changes cannot
  repair an observation.
- O0 has one scientific invocation.
- Development has one scientific invocation.
- Development failure creates no attempt 2.
- No repair budget applies after a scientific observation starts; a started observation failure is
  terminal for that protocol.
- Any v2 evaluation-inconclusive terminal closes this direction; no v3 is planned.

Low-impact theoretical hardening after all acceptance gates pass is recorded as a known limitation
or follow-up rather than extending the critical path.

## 30. Acceptance criteria

The first implementation stage is complete only when one of these branches is closed:

### A. Docs/regression-only

- v2 protocol and O0 artifact pure-validate;
- targeted baseline failure is absent;
- candidate modules were not implemented;
- holdout remains unopened;
- runtime remains unchanged; and
- public docs state the bounded result.

### B. Development comparison complete

- v2 protocol, O0 artifact, and development artifact pure-validate;
- observer remained label-blind;
- two fresh workspaces produced byte-identical observations;
- every evaluated mechanism has an independently recomputed status;
- all guardrails and bounds pass;
- scientific negative, mixed, or qualified result is explicit;
- holdout remains unopened;
- runtime promotion remains not evaluated; and
- public claims match the artifact.

### C. Evaluation inconclusive

- no comparison artifact exists;
- holdout remains unopened;
- complete receipt or hard-failure process ledger is retained;
- public result does not claim mechanism success or failure;
- no retry or attempt 2 occurred; and
- the implementation branch is not published as a mechanism result by default.

## 31. Future holdout and promotion boundary

After a complete development artifact and independent authority review, a separate design/plan may
authorize one public nonblind holdout observation for development-qualified mechanisms only.

Even a successful holdout remains comparison evidence. A runtime change would require:

- separate compatibility and migration analysis;
- runtime API/CLI/MCP/consumer proof;
- new regression and release plan;
- explicit promotion approval; and
- documentation that distinguishes constructed-case evidence from production claims.

This specification does not authorize that work.
