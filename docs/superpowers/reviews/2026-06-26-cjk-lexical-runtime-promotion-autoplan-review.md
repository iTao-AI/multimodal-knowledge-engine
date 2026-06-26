# CJK Lexical Runtime Promotion Autoplan Review

Status: approved with required constraints incorporated into the design and implementation plan.

Reviewed artifacts:

- [CJK Lexical Runtime Promotion Design](../specs/2026-06-26-cjk-lexical-runtime-promotion-design.md)
- [CJK Lexical Runtime Promotion Implementation Plan](../plans/2026-06-26-cjk-lexical-runtime-promotion-implementation.md)
- [Chinese Hybrid Retrieval Evaluation Design](../specs/2026-06-25-chinese-hybrid-retrieval-evaluation-design.md)
- [CJK Lexical Candidate Design](../specs/2026-06-26-cjk-lexical-candidate-design.md)

Review mode:

- Applied the `gstack-autoplan` review sequence in single-agent form due the active session's
  no-subagent execution constraint.
- CEO/product review: completed.
- Visual design review: skipped because this plan has no UI surface.
- Engineering review: completed.
- Developer-experience review: completed for CLI, MCP, proof, and docs.
- No raw planning artifacts or private workspace context are recorded here.

## Final Verdict

Proceed with E3-F lexical-only runtime promotion.

The promotion is justified because E3-B already proved a bounded candidate with material improvement
on the frozen Chinese protocol and no E1/E2 regression. Waiting for dense retrieval, RRF, or reranker
would add unproven variables and delay the smallest product-visible fix for the dominant E3-A
failure class.

This approval is conditional on preserving the plan's explicit boundaries:

- `cjk-trigram-overlap-v1` may become the default runtime retrieval strategy.
- `numeric-grouping-v1` and `current` must remain direct rollback paths.
- Dense/vector/hybrid/RRF/reranker/query rewrite remain separate future stages.
- Runtime projection lifecycle, readiness, rebuild, and failure isolation are required before
  default promotion.

## CEO Review

### Decision: promote lexical before dense

The strongest product move is not to implement the most market-recognizable RAG stack immediately.
The strongest move is to ship the smallest verified improvement that changes normal Agent-facing
behavior while preserving the Evidence engine's reliability story.

E3-A shows the current failure is largely lexical coverage. E3-B shows a lexical-only CJK candidate
substantially improves Recall@5 and nDCG@10 on the frozen protocol. Dense retrieval may still be
valuable later, but it is not required to close the known compiled-empty failure class.

Resolution: the plan correctly chooses E3-F lexical-only promotion and leaves E3-C/E3-D/E3-E as
future comparison stages.

### Decision: default strategy should change

Keeping the candidate optional would make the feature harder to demonstrate and would leave normal
CLI/MCP users on the known weaker path. E3-F is a promotion stage, not another comparison stage.

Resolution: `cjk-trigram-overlap-v1` should become the runtime default, provided readiness,
rollback, and projection failure isolation are implemented.

### Rejected product alternatives

| Alternative | Verdict | Reason |
|---|---|---|
| Wait for dense retrieval first | Rejected | E3-B already supports the smaller lexical fix; dense would add an independent unproven variable. |
| Ship optional-only CJK strategy | Rejected | It would not improve the default Agent-facing product path. |
| Add LangChain/LlamaIndex retrievers | Rejected | It would pollute project-owned Evidence, Publication, CLI, and MCP contracts without solving the known failure class. |
| Add a web UI now | Rejected | The current gap is retrieval behavior and proof, not presentation surface. |

## Engineering Review

### Finding E3F-ENG-1: query policy is too narrow for runtime promotion

Severity: required plan change.

`RetrievalQueryPolicy` currently represents query compilation. The CJK candidate is a strategy that
can choose between the existing active FTS path and a separate CJK projection. Extending the old name
without clarification would blur compiler policy, projection lifecycle, and owner runtime strategy.

Resolution: the plan now requires a `RetrievalStrategy` concept while preserving
`RetrievalQueryPolicy` compatibility for existing evaluation code and legacy CLI use.

### Finding E3F-ENG-2: runtime projection lifecycle is mandatory

Severity: required plan change.

E3-B used an evaluation-only projection. A runtime default cannot depend on temporary evaluation
tables or rebuild-on-search behavior. It needs persistent projection metadata, readiness checking,
and rebuild tooling.

Resolution: the plan requires a separate active CJK FTS5 projection, metadata identity, cache-only
`doctor`, idempotent `rebuild`, and source-of-truth rebuild from domain rows.

### Finding E3F-ENG-3: default promotion must fail closed

Severity: required plan change.

Silent fallback from selected `cjk-trigram-overlap-v1` to `numeric-grouping-v1` would hide stale or
missing projections and make production behavior unverifiable.

Resolution: the plan distinguishes intended numeric-branch behavior for non-empty compiled queries
from error fallback. Missing or stale CJK projection must fail closed for the selected CJK strategy.

### Finding E3F-ENG-4: Publication activation must isolate projection failure

Severity: required plan change.

The project architecture says required indexing failures must fail the Run and prevent Publication
switching. Promoting CJK lexical makes the projection a required indexing step for that selected
strategy.

Resolution: the plan adds activation tests proving injected CJK projection failure preserves the
previous active Publication and never exposes partial searchable state.

### Finding E3F-ENG-5: canonical artifacts will need source identity refresh

Severity: required plan change.

Runtime source changes can alter source-content identities in E1/E2/E3-A/E3-B artifacts. A refresh
is acceptable only if semantics, observations, metrics, gates, qrels, and fixture bytes remain
unchanged.

Resolution: the plan requires artifact refresh plus semantic equality checks and stops execution on
unexpected metric or verdict changes.

## Developer Experience Review

### Finding E3F-DX-1: introduce a clear owner selector

Severity: required plan change.

Users should not need to understand the old query-policy implementation detail to choose a runtime
retrieval path.

Resolution: the preferred selector is `--retrieval-strategy`. The existing
`--retrieval-query-policy` remains a compatibility alias, with conflict detection.

### Finding E3F-DX-2: doctor/rebuild must be direct and offline

Severity: required plan change.

When a local database has active Publications created before the new projection, the user needs a
clear local command to diagnose and rebuild projection state.

Resolution: the plan requires `mke retrieval doctor` and `mke retrieval rebuild` command surfaces,
documented consistently across CLI, MCP, and ADR.

### Finding E3F-DX-3: installed-wheel proof must include MCP

Severity: required plan change.

The project positioning is an Agent-callable local tool. CLI-only proof would not cover the primary
Agent integration path.

Resolution: the plan requires installed-wheel CLI and stdio MCP proof for Python 3.12 and 3.13,
including default strategy, rollback startup, hostile environment, external cwd, and source-tree
import rejection.

## Risk Register

| Risk | Mitigation |
|---|---|
| SQLite build lacks FTS5 trigram tokenizer | Fail closed only when selected strategy needs CJK projection; expose stable doctor error. |
| Existing databases lack CJK projection metadata | Provide idempotent rebuild from active domain rows. |
| Default promotion changes E1/E2 behavior unexpectedly | Require artifact validators and semantic equality checks before PR. |
| CJK lexical matching appears broader than proven | Docs and ADR must state bounded public-holdout evidence and lexical-only limits. |
| CLI flag rename breaks users | Keep `--retrieval-query-policy` compatibility alias and document `--retrieval-strategy` as preferred. |

## Required Implementation Checkpoints

1. Add ADR-0008 and strategy vocabulary before default behavior changes.
2. Build persistent CJK projection and readiness metadata.
3. Add `doctor` and `rebuild` commands.
4. Wire Search/Ask strategy with fail-closed projection checks.
5. Bind projection build to Publication activation and rollback proof.
6. Update CLI/MCP owner startup contracts.
7. Refresh artifacts with unchanged metrics and verdicts.
8. Add installed-wheel CLI/MCP proof.
9. Run full verification and independent pre-PR review.

## Approval

Approved for execution handoff.

The execution window should implement the plan with TDD, stop on unexpected artifact or metric
changes, and return a clean local branch for the established pre-PR review sequence.
