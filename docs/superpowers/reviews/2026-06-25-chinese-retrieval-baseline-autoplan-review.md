# Chinese Retrieval Baseline Autoplan Review

## Status

- Stage: Approved for E3-A implementation after review corrections.
- Review date: 2026-06-25.
- Mode: HOLD SCOPE with engineering and developer-experience polish.
- Baseline: `main@b04df63a1c07b8df3dcd1284cdbea42dd4e31e1c`.
- Reviewed:
  - `docs/superpowers/specs/2026-06-25-chinese-hybrid-retrieval-evaluation-design.md`
  - `docs/superpowers/plans/2026-06-25-chinese-retrieval-baseline-implementation.md`
- Runtime implementation, implementation worktree creation, push, and PR creation were outside
  this review.

## Verdict

E3-A remains the correct next slice. It records the current Chinese lexical behavior and creates
the evidence boundary required before selecting CJK lexical, dense, fusion, or reranking
candidates.

The plan is clear for implementation after incorporating the findings below. There are no
unresolved architecture or product decisions.

## Scope Review

The review retained:

- five frozen redistribution-safe text-layer PDF fixtures;
- 48 protocol-owned development/holdout queries;
- graded page qrels, query strata, and mechanical miss symptoms;
- current `numeric-grouping-v1` Search and evidence-only Ask behavior;
- deterministic local evaluation, canonical artifact validation, and installed-wheel proof;
- evidence-gated E3-B eligibility.

The review rejected scope expansion into:

- CJK tokenizer implementation;
- embeddings, vector storage, RRF, reranking, or query rewriting;
- Passage/chunk changes or OCR;
- Web UI, hosted services, telemetry, or a general benchmark framework;
- runtime Search/Ask strategy or Publication lifecycle changes.

## Engineering Findings And Resolutions

| Finding | Resolution |
|---|---|
| Development queries could observe holdout documents in a shared corpus. | Development and holdout now execute against separate 34-page and 36-page corpora, each duplicated only for determinism. |
| Active Evidence snapshot depended on the FTS projection. | Domain Evidence is read from `sources -> publications -> evidence`; FTS rows are enumerated and verified separately. |
| Qrel completeness was represented by summary counts. | Every query stores an ordered judgment for every page in its partition, producing 1,680 derived judgments. |
| A zero-disagreement field implied unsupported inter-rater evidence. | The protocol records one completed review and makes no inter-rater agreement claim. |
| Rank observation did not prove production ordering. | Rank and `bm25()` probes use production-equivalent joins, active-Publication filtering, tie-breakers, and complete result sets. |
| Miss classification counted terms rather than actual FTS clauses. | Diagnostics model top-level `AND` clauses and parenthesized `OR` alternatives. |
| The canonical artifact stored only a global scorer label. | It binds per-query result counts, ordered Evidence-ID digests, score-pair digests, and override state. |
| E1/E2/E3-A artifact updates could be partially applied. | One journaled orchestration command stages and validates all four files, records checksummed backups, and recovers interrupted replacement on restart. |
| Search, Ask, and rank SQL observations were conflated. | Operation traces are separated and Search/Ask ordered Evidence identity must agree. |
| Installed-wheel proof did not fully lock offline/source-tree isolation. | The plan reuses hostile-environment, offline, bounded-subprocess proof on Python 3.12 and 3.13. |
| CI cost was unbounded. | The final gate records and enforces TTHW, evaluation time, proof time, peak RSS, SQLite size, and the existing job timeout. |
| A private restore path was present in the plan. | It was removed and the final public-boundary scan covers planning documents. |

## Developer Experience Findings And Resolutions

| Finding | Resolution |
|---|---|
| E3-A was not discoverable from the first-run documentation. | README and the getting-started tutorial receive one copy-paste command block and expected first output lines. |
| Human output did not prioritize the decision. | The first four stdout lines separate integrity, observed quality, E3-B eligibility, and corpus size. |
| Evaluation success could be confused with artifact validation. | Evaluation and artifact commands have separate exact exit semantics. |
| JSON fields were inconsistent between DTO and final assertions. | The complete top-level schema is fixed and includes stable `e3b_reason`. |
| A multi-minute command had no progress contract. | Human mode emits four redacted stderr phases; JSON mode remains silent. |
| Recovery actions were generic. | Each failure has an exact `problem`, bounded `cause`, and documented `next_step` token. |
| One how-to carried tutorial, explanation, reference, and validation concerns. | Documentation responsibilities follow the existing Diataxis structure. |
| Installed-wheel proof lacked timeout/output contracts. | Every subprocess is timed out, output-capped, offline, and represented by stable public-safe JSON. |
| Resource budgets lacked a reproducible measurement path. | A repository-owned helper records warm-cache TTHW and resource evidence without telemetry. |

## Integrity Boundary

The canonical artifact can verify:

- exact protocol, fixture, judgment-record, source, environment, result, metric, and limitation
  identity;
- complete partition page-judgment coverage and qrel derivation;
- deterministic Search/Ask results and per-query FTS rank evidence;
- the predeclared E3-B decision rule.

It cannot independently prove that a human relevance grade is semantically correct, that the
public holdout is blind, or that the small corpus represents general Chinese retrieval quality.
Those limitations remain explicit.

## Required Implementation Evidence

The implementation window must return:

- a clean isolated branch and worktree;
- TDD evidence for each task;
- complete targeted and full verification;
- E1/E2 semantic equality after restricted identity refresh;
- the E3-A report, canonical artifact, checksum, and validator result;
- Python 3.12/3.13 offline installed-wheel proof;
- measured TTHW/runtime/RSS/SQLite evidence;
- documentation audit and public-boundary scan;
- no candidate implementation or runtime default change.

The separate planning/review window will run the authoritative pre-PR implementation review.

## Final Review State

- CEO/scope review: clear.
- Engineering review: clear after 12 corrections.
- Developer-experience review: clear after 9 corrections.
- Targeted post-fix review: four residual consistency defects corrected:
  - FTS locator/text identity is bound;
  - `e3b_evidence` is part of the report schema;
  - multi-file refresh uses durable crash recovery rather than an atomicity claim;
  - TTHW is defined as locked sync plus evaluator wall time.
- Design/UI review: not applicable; no UI scope.
- Unresolved decisions: 0.
