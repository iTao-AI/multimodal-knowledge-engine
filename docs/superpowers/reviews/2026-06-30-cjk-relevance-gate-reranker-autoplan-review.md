# CJK Relevance Gate Reranker Autoplan Review

Date: 2026-06-30

Scope: E3-E comparison-only deterministic relevance gate and reranker plan.

Reviewed documents:

- [CJK Relevance Gate Reranker Candidate Design](../specs/2026-06-30-cjk-relevance-gate-reranker-design.md)
- [CJK Relevance Gate Reranker Candidate Implementation Plan](../plans/2026-06-30-cjk-relevance-gate-reranker-implementation.md)

Planning base: `main@0ed1ee1c7763d65b1cd493d002908361df410521`.

## Autoplan Mode

This review applied the `gstack-autoplan` structure in a single scheme-window pass:

| Phase | Status | Reason |
|---|---|---|
| CEO / scope review | Run | E3-E changes evaluation direction and decides whether reranking remains worth pursuing. |
| Design review | Skipped | No UI, visual layout, or interaction surface is in scope. |
| Engineering review | Run | E3-E adds artifact protocols, validators, gate scoring, and holdout state transitions. |
| DX review | Run | E3-E adds a developer-facing evaluation command and reproduction guide. |

No subagents or non-public planning artifacts were used. Findings below are distilled into
repository-visible public-neutral requirements.

## CEO Review

### Premise Challenge

The premise is sound: E3-D showed complementarity but failed refusal. A reranker/gate comparison is
the right next question only if it isolates the safety failure without changing candidate generation
or runtime behavior.

The tempting alternative is a local cross-encoder or API reranker. That would look more like a
standard RAG stack, but it would add model/provider/resource boundaries before proving that the
existing union can be filtered safely. The plan correctly defers those options.

### Accepted Scope

- Use existing E3-C and E3-D artifacts.
- Implement a deterministic gate and rerank candidate.
- Evaluate refusal/no-hit and hard-negative behavior as first-class gates.
- Preserve comparison-only scope.

### Rejected Scope

- Runtime promotion.
- API/LLM reranker.
- Local cross-encoder model.
- Query rewrite.
- Passage/segmentation.
- Search/Ask/MCP changes.

### CEO Findings

| Finding | Severity | Resolution |
|---|---|---|
| E3-E could become a "reranker" label without actually testing refusal safety. | P1 | The design now makes unanswerable no-hit and hard-negative gates mandatory, not diagnostic-only. |
| E3-E could overfit 24 development queries by letting arbitrary profiles evolve during implementation. | P1 | The design freezes a small profile catalog and deterministic selection objective before scoring. |
| Public docs could overstate this as production reranking. | P2 | Spec and plan now call it a comparison-only deterministic relevance gate/reranker candidate. |

CEO verdict: CLEAN after amendments.

## Engineering Review

### Architecture Check

```text
canonical E3-C dense artifact
          |
          v
canonical E3-D RRF artifact + frozen Chinese protocol
          |
          v
bounded union rows with stable Evidence identity
          |
          v
public query/Evidence feature extraction
          |
          v
frozen gate profile selection on development
          |
          v
deterministic rerank + metrics + artifact validator
```

The architecture keeps SQLite/runtime behavior outside the experiment and uses repository-visible
artifacts as inputs. That matches MKE's current evaluation style.

### Evidence Integrity Findings

| Finding | Severity | Resolution |
|---|---|---|
| Candidate scoring might accidentally read qrel grades, category labels, split labels, or expected locators. | P1 | Spec and plan now explicitly forbid these as scoring inputs and require regression tests. |
| Feature derivation could become unverifiable if only final metrics are recorded. | P1 | Plan requires serialized feature rows, gate decisions, reason codes, rerank score, and independent validator recomputation. |
| Holdout could be observed before development freeze. | P1 | Plan requires exclusive-create development freeze and blocks holdout unless development status is `passed`. |
| Historical artifact identity refresh could mask semantic drift. | P1 | Plan requires normalized E1/E2/E3-A/E3-B comparisons before any identity-only refresh. |
| Rerank score ties could differ across Python versions. | P2 | Plan requires deterministic tie-break order and Python 3.12/3.13 verification. |

### Failure Modes Registry

| Failure mode | Expected behavior |
|---|---|
| No gate profile passes development | Record `development_status=valid_negative`; do not observe holdout. |
| Candidate needs qrels or expected locators to pass | Stop for planning review; do not implement scoring shortcut. |
| Feature extraction cannot bind source-text digest | Fail closed with stable public error. |
| Artifact and observed report are both tampered | Validator rejects by recomputing features, gate decisions, metrics, and state. |
| Runtime Search/Ask/MCP changes become necessary | Stop; that is outside E3-E. |

Engineering verdict: CLEAN after amendments.

## DX Review

### Developer Journey

| Stage | Required path |
|---|---|
| Discover | `docs/README.md` links the E3-E design, plan, review, and how-to. |
| Reproduce development | Run `mke eval retrieval-relevance-gate --development-only ...`. |
| Understand result | Read comparison artifact status and metrics table. |
| Validate | Run `python -m mke.evaluation.relevance_gate_artifact validate ...`. |
| Interpret scope | How-to states comparison-only and no runtime change. |
| Debug failure | CLI emits problem/cause/next_step without private paths or stack traces. |

### DX Findings

| Finding | Severity | Resolution |
|---|---|---|
| A command named "reranker" could imply runtime behavior. | P2 | Command stays under `mke eval retrieval-relevance-gate`, and docs repeat comparison-only scope. |
| Developers may rerun holdout by accident. | P1 | Plan requires development freeze, conditional holdout command, and explicit stop behavior when development is valid negative. |
| Optional dense replay could be confused with an acceptance gate. | P2 | Plan keeps E3-E model-free and uses E3-C/E3-D artifacts; optional model/cache checks are not required. |

DX verdict: CLEAN after amendments.

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Select deterministic relevance gate before model/API reranker. | Auto-decided | Isolate variables before adding providers/models. | E3-D already proved union complementarity; next unknown is safety filtering. | API reranker, local cross-encoder in E3-E. |
| 2 | CEO | Treat no-hit and hard-negative metrics as gates. | Auto-decided | Safety before quality-only wins. | E3-D failed because refusal collapsed despite better Recall@5. | Recall-only success criterion. |
| 3 | Eng | Forbid qrels/category/split labels in scoring. | Auto-decided | Evaluation integrity. | Candidate decisions must be reproducible from deployable features, not labels. | Label-aware score shortcuts. |
| 4 | Eng | Freeze a small profile catalog before development scoring. | Auto-decided | Reduce overfit. | Current corpus is small; arbitrary tuning would not be credible. | Open-ended threshold/profile tuning. |
| 5 | DX | Keep CLI under evaluation namespace. | Auto-decided | Prevent runtime confusion. | The candidate must not look like a shipped Search/Ask strategy. | Runtime selector or MCP override. |

## Review Scores

| Phase | Score | Notes |
|---|---:|---|
| CEO | 9/10 | Scope is justified by E3-D valid negative and avoids premature model/API complexity. |
| Engineering | 8/10 | Artifact and gate integrity are strong after added forbidden-input and holdout-stop requirements. |
| DX | 8/10 | Reproduction path is clear; final quality depends on implementation keeping errors public and stable. |

## Cross-Phase Themes

| Theme | Phases | Resolution |
|---|---|---|
| Do not overfit the small development set. | CEO, Engineering | Frozen profile catalog, deterministic selection objective, holdout only after freeze. |
| Do not confuse comparison evidence with runtime behavior. | CEO, DX | Repeated non-scope statements and eval-only CLI naming. |
| Refusal safety is the main E3-E value. | CEO, Engineering, DX | No-hit and hard-negative gates are mandatory pass criteria. |

## Final Verdict

CLEAN / 0 unresolved findings.

The E3-E plan is ready to hand to an implementation window after user authorization. It must remain
comparison-only and must not change Search, Ask, MCP, owner startup, Publication, ingestion, or the
runtime default.
