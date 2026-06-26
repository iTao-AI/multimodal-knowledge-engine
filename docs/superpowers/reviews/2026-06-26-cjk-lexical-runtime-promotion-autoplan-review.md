# CJK Lexical Runtime Promotion Autoplan Review

Status: completed after rerun. Approved for execution only with the required plan changes recorded
in the implementation plan.

Reviewed artifacts:

- [CJK Lexical Runtime Promotion Design](../specs/2026-06-26-cjk-lexical-runtime-promotion-design.md)
- [CJK Lexical Runtime Promotion Implementation Plan](../plans/2026-06-26-cjk-lexical-runtime-promotion-implementation.md)
- [Chinese Hybrid Retrieval Evaluation Design](../specs/2026-06-25-chinese-hybrid-retrieval-evaluation-design.md)
- [CJK Lexical Candidate Design](../specs/2026-06-26-cjk-lexical-candidate-design.md)

Review execution:

- `gstack-autoplan` skill instructions were read and followed for CEO, engineering, and DX phases.
- UI design review was skipped because the plan has no UI surface.
- DX review was run because the plan changes CLI, MCP, commands, errors, docs, and Agent-facing
  behavior.
- External Claude Code CLI and Codex CLI voices were used for independent review. No in-session
  subagent tool was used.
- Raw GStack artifacts, local restore points, private planning paths, and session transcripts are
  not recorded in this repository.

## Final Verdict

Proceed with E3-F lexical-only promotion only after applying the required review changes.

The core direction still stands: E3-B supports a bounded lexical fix for the dominant
compiled-empty Chinese failure class, and E3-F is the correct promotion stage for that smallest
verified strategy. The review found that the first plan was too optimistic about default promotion
readiness. The plan now requires:

- a tokenizer alternative spike before persistent projection work;
- strategy-aware Ask validation;
- same-transaction Publication activation for CJK projection state;
- an existing-database doctor/rebuild upgrade path;
- installed-wheel MCP tool-call proof, not only startup proof;
- an explicit Default Promotion Launch Gate;
- high-fanout CJK performance gates;
- stale-docs and public-boundary scans.

## CEO Review

### Premise Challenge

| Premise | Verdict | Resolution |
|---|---|---|
| E3-B quality lift justifies moving beyond comparison-only | Mostly valid | Keep promotion path, but require explicit launch gates and unchanged E1/E2/E3-A/E3-B semantics before default flip. |
| CJK trigram projection is the smallest viable implementation | Not yet proven | Add tokenizer alternative spike before persistent projection implementation. |
| Default promotion should happen in the same PR | Conditionally valid | Allowed only because strategy, projection, activation, proof, artifacts, and docs must land atomically; add split/abort rule. |
| Dense retrieval can wait | Valid | E3-F explicitly permits lexical-only promotion and avoids unproven dense/hybrid variables. |
| Public docs can safely call this CJK retrieval | Needs qualification | Docs and ADR must state lexical-only, small public holdout, and unvalidated Japanese/Korean behavior. |

### CEO Dual Voices

| Dimension | Claude | Codex | Consensus |
|---|---|---|---|
| Premises valid? | Partial | Partial | Confirmed with launch gates |
| Right problem? | Yes, but evidence-limited | Yes | Confirmed |
| Scope calibration? | Too much lifecycle before alternatives | Needs split/abort guard | Confirmed concern |
| Alternatives explored? | Not enough tokenizer alternatives | Not enough launch-gate alternatives | Confirmed concern |
| Market/product risks covered? | Underqualified CJK claim | Needs positioning block | Confirmed concern |
| Six-month trajectory sound? | Needs dense compatibility path | Needs strategy descriptor | Confirmed concern |

### CEO Findings

1. **High: tokenizer alternative not ruled out.** A simpler tokenizer-only or generated n-gram path
   might close the same failure class without persistent projection lifecycle.
   - Resolution: added Task 0.5 tokenizer alternative spike and ADR rejected-alternatives requirement.
2. **High: default promotion evidence needed a hard launch gate.** E3-B quality lift is bounded
   engineering evidence, not a broad Chinese RAG claim.
   - Resolution: added Default Promotion Launch Gate with Go/No-Go criteria.
3. **Medium: future dense/hybrid compatibility needed an architecture seam.**
   - Resolution: required `RetrievalStrategyDescriptor` with explicit projection and future-strategy
     fields.
4. **Medium: public positioning needed tighter claims.**
   - Resolution: docs must state lexical-only limits, small public holdout, and no arbitrary Chinese
     RAG claim.

## Engineering Review

### Existing Code Leverage Map

| Sub-problem | Existing code to reuse or protect |
|---|---|
| Query compiler rollback | `src/mke/retrieval/query_policy.py` |
| Runtime composition | `src/mke/runtime.py` |
| Search/Ask application contract | `src/mke/application/__init__.py` |
| Active Publication and FTS lifecycle | `src/mke/adapters/sqlite/__init__.py` |
| CJK evaluation term/scorer semantics | `src/mke/evaluation/cjk_lexical_candidate.py` |
| CJK artifact validation | `src/mke/evaluation/cjk_lexical_artifact.py` |
| CLI and eval command surface | `src/mke/cli.py` |
| MCP stdio interface | `src/mke/interfaces/mcp_server.py` |

### Architecture Diagram

```text
CLI / owner-started MCP
  -> RuntimeConfig(retrieval_strategy)
    -> KnowledgeEngine
      -> SQLiteStore(strategy_descriptor)
        -> active_evidence_fts
        -> cjk_lexical_fts + cjk_projection_metadata
        -> Search(query)
          -> numeric-grouping-v1 branch when compiled query is non-empty
          -> CJK trigram projection branch when compiled query is empty and eligible
        -> Ask(question)
          -> strategy-aware eligibility check
          -> Search(question)
        -> activate_publication(transaction)
          -> active FTS rows
          -> CJK projection rows
          -> CJK metadata
          -> active source pointer
          -> Run published event
```

### Eng Dual Voices

| Dimension | Claude | Codex | Consensus |
|---|---|---|---|
| Architecture sound? | Needs tighter boundaries | Needs descriptor and atomicity | Confirmed concern |
| Test coverage sufficient? | Missing Ask, punctuation, upgrade, perf | Missing Ask, upgrade, MCP tool-call, perf | Confirmed concern |
| Performance risks addressed? | Not enough | Not enough | Confirmed concern |
| Security/public boundary covered? | Needs private-path scan | Found restore path leak | Confirmed concern |
| Error paths handled? | Upgrade and projection errors underspecified | Same | Confirmed concern |
| Deployment risk manageable? | Only after launch gate | Only after launch gate | Confirmed |

### Engineering Findings

1. **Blocker: plan contained a private restore path.**
   - Resolution: removed from the plan; added public-boundary scan gate.
2. **Critical: current Ask validation rejects CJK-only questions before Search.**
   - Resolution: Task 4 now requires strategy-aware Ask validation and CJK Ask RED tests.
3. **Critical: activation atomicity was underspecified.**
   - Resolution: Task 5 now requires active FTS, CJK rows, metadata, active pointer, Run state, and
     Run event in one SQLite transaction.
4. **High: existing-database upgrade path was not executable.**
   - Resolution: Task 3 now includes doctor/rebuild upgrade commands and stable error triples.
5. **High: MCP proof covered startup but not tool calls.**
   - Resolution: Task 8 now requires installed-wheel stdio MCP tool-call proof for Search and Ask.
6. **Medium: CJK high-fanout and long-query behavior was unbounded.**
   - Resolution: Task 4 now requires query and candidate caps plus performance tests.
7. **Medium: evaluation code and runtime code boundaries were ambiguous.**
   - Resolution: Task 2 keeps runtime CJK projection code in `src/mke/retrieval/cjk_lexical.py`
     and evaluation contract code in `src/mke/evaluation/`.

## DX Review

### Developer Journey

| Step | Current friction | Required fix |
|---|---|---|
| Discover feature status | Existing docs still say runtime unchanged or E3-F unimplemented | Stale-docs scan and README updates |
| Upgrade an existing DB | No copy-paste doctor/rebuild path | Add focused existing-DB upgrade section |
| Try CJK Search/Ask | No single quick path | Add focused CJK how-to and getting-started update |
| Use MCP | Startup proof only | Add MCP tool-call proof and docs |
| Diagnose projection failure | Error triples not specified | Add stable `problem`/`cause`/`next_step` table |
| Roll back | Strategy exists but examples incomplete | Add CLI and MCP rollback snippets |
| Understand limits | Claims scattered across ADR/spec/how-to | Add positioning block and explicit lexical-only limits |

### DX Score

Initial DX score: `6.5/10` to `7/10`, depending on reviewer.

Expected score after required changes: about `8.5/10`.

### DX Findings

1. **Critical: CJK Ask behavior must be visible through the Agent-facing path.**
   - Resolution: Ask validation and MCP tool-call proof are now required.
2. **Critical: existing database upgrade path must be copy-paste actionable.**
   - Resolution: `--db <existing.sqlite>` doctor/rebuild/search examples added to plan.
3. **High: default flip must be last, not first.**
   - Resolution: Task 8.5 launch gate requires explicit selector implementation before default
     change.
4. **Medium: docs findability needs one focused entry point.**
   - Resolution: Task 9 requires `docs/how-to/enable-cjk-retrieval.md`.
5. **Medium: stale wording needs testable cleanup.**
   - Resolution: Task 9 requires grep-based stale-docs scan and public-boundary scan.

## Failure Modes Registry

| Failure mode | Severity | Required mitigation |
|---|---|---|
| CJK-only Ask rejected before retrieval strategy runs | Critical | Strategy-aware Ask validation and RED tests |
| CJK projection metadata commits separately from active pointer | Critical | Same SQLite transaction for all activation state |
| Existing DB upgrades into default strategy with missing projection | High | Doctor/rebuild upgrade path and stable error contract |
| Unsupported FTS5 trigram tokenizer breaks default startup | High | Readiness preflight and rollback guidance |
| MCP proof passes startup but tool calls fail | High | Installed-wheel MCP tool-call proof |
| High-frequency CJK trigram query scans too many rows | Medium | Query/candidate caps and performance gate |
| Stale docs imply no runtime promotion after promotion lands | Medium | Stale-docs scan and docs update requirement |
| Private GStack restore path leaks into public docs | Medium | Public-boundary scan |

## NOT In Scope

- Dense retrieval, vector search, hybrid retrieval, RRF, reranker, and query rewrite.
- HTTP API or UI behavior.
- OCR, ASR, PDF parser, chunking, or segmentation expansion.
- LangChain, LlamaIndex, LangGraph, retrieval SDK, or hosted service integration.
- Migration from the legacy RAG-OCR service layout.
- External video publication.

## Cross-Phase Themes

- **Default promotion must be gated.** CEO, engineering, and DX all flagged that the default should
  flip only after proofs, artifact validators, performance gates, docs cleanup, and rollback pass.
- **Agent-facing Ask/MCP matters more than Search-only proof.** Engineering and DX both flagged that
  CJK Search improvement is incomplete unless `ask_library` works through MCP.
- **Projection lifecycle must be operational, not just architectural.** CEO, engineering, and DX all
  flagged readiness, upgrade, rebuild, and rollback paths.
- **Claims must stay bounded.** CEO and DX both flagged that docs must say lexical-only and avoid
  arbitrary Chinese RAG claims.

## Final Approval

Approved for execution handoff after plan revision.

The execution window should start from the revised implementation plan, use TDD, and stop for
review if tokenizer alternatives change the strategy, any artifact metric/verdict changes, or the
launch gate cannot pass without expanding into dense/vector/hybrid/RRF/reranker/query rewrite work.
