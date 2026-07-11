# Versioned Evidence Provenance Contract Plan Review

Date: 2026-07-11

Status: CLEAN / 0 unresolved findings.

Planning base: `main@793788f2d74a1ec072fe205e89acd13ab595bad7`.

Reviewed documents:

- [Versioned Evidence Provenance Contract Design](../specs/2026-07-11-versioned-evidence-provenance-contract-design.md)
- [Versioned Evidence Provenance Contract Implementation Plan](../plans/2026-07-11-versioned-evidence-provenance-contract-implementation.md)

## Scope Review

The scope is accepted after architecture amendments. MKE already owns every required provenance
fact, so the change remains a read-only contract over existing SQLite authority. It does not add a
catalog, database migration, retrieval projection, orchestration layer, business metadata, or
runtime retrieval strategy.

The plan remains intentionally larger than a small serializer change because the contract must be
proved across domain integrity, SQLite snapshot consistency, FastMCP schema generation, real stdio
consumer behavior, installed-wheel identity, and the repository's existing canonical artifact
chain.

## Architecture Review

Initial review found these load-bearing issues:

| Finding | Resolution |
|---|---|
| Extending `SearchResult` would change normal CLI/evaluation construction and query behavior. | Keep `SearchResult` and existing retrieval SQL unchanged; v1 snapshot paths bulk-enrich returned IDs into `SearchResultProvenance`. |
| Replacing current read-tool outputs would be a breaking change without negotiation. | Add parallel `list_libraries_v1`, `search_library_v1`, and `ask_library_v1`; preserve all five legacy tool contracts. |
| Issuing `BEGIN` would conflict with the adapter's PEP 249 `autocommit=False` transaction model. | Reuse the existing transaction, perform observation/retrieval/bulk enrichment before closing it, and never issue nested `BEGIN`. |
| A valid-looking but mismatched Source/Publication/Run/Evidence graph could be trusted. | Validate local Library ownership, active pointer, revision, published Run state, Run/Source/Evidence linkage, manifest count, and manifest/asset fingerprint equality. |
| One planning/implementation review file could be overwritten from CLEAN back to pending. | Keep this immutable plan review separate from the later implementation review. |

Architecture verdict: CLEAN after amendments.

## Code Quality Review

| Finding | Resolution |
|---|---|
| The legacy `_safe_tool` returns open dictionaries and cannot satisfy typed v1 error unions. | Add a response-specific typed v1 safe-tool adapter; legacy wrappers remain unchanged. |
| Direct Pydantic imports would rely on an undeclared transitive dependency. | Declare `pydantic>=2.13.4,<3`, matching the current MCP lock, without introducing another package family. |
| Input and output disclosure policies could incorrectly reject legitimate `publication_revision`. | Keep legacy input owner-control terms separate from v1 output disclosure terms. |

Code-quality verdict: CLEAN after amendments.

## Test Review

The plan traces domain validation, SQLite integrity/snapshot paths, application Search/Ask
projection equality, strict success/error schemas, malformed consumer payloads, real PDF/video MCP
flows, same-store/fresh-store identity behavior, installed-wheel execution, redaction, and canonical
artifact closure.

The review added:

- a committed normalized legacy schema fixture, created before MCP changes;
- complete corrupt-provenance graph regressions rather than only zero-Evidence corruption;
- second-connection snapshot consistency testing;
- strict old/new tool coexistence checks;
- timeout, cancellation, child termination, and temporary-store cleanup tests;
- explicit allowance for validator-proven identity-only changes in canonical artifacts and
  protocol locks while forbidding corpus/qrel/query/observation/metric/gate/verdict drift.

Test verdict: coverage map complete; 0 open gaps.

## Performance Review

The v1 snapshot path adds a fixed observation/integrity query set and one bulk provenance lookup
after the unchanged bounded retrieval path. It does not perform per-result queries, rebuild a
projection, change ranking, or scan additional text. SQL trace regressions enforce the fixed query
shape.

Performance verdict: CLEAN.

## Outside Voice

The standard read-only Codex outside voice ran iteratively at `reasoning=high`. It surfaced 15
P1/P2 findings across the initial review and targeted follow-ups. Thirteen actionable findings were
folded into the design/plan. Two suggestions were rejected deliberately:

- redesigning the broad E1-E3 source-identity policy is a separate evaluation-governance change;
- removing the independent stdio consumer proof conflicts with the approved evidence-closure goal.

The final targeted re-review returned exactly `CLEAN`.

No cross-model tension remains.

## Failure Modes

The implementation plan records a test and handling rule for every identified production failure.
No path remains simultaneously silent, unhandled, and untested. Critical gaps: 0.

## Parallelization

Sequential implementation, no parallelization opportunity. Domain, SQLite, application, MCP,
consumer proof, documentation, and artifact identities share contracts and form one dependency
chain.

## Implementation Tasks

All plan-review findings are already folded into the implementation plan. No separate unresolved
task is emitted by this review.

## Review Completion Summary

- Step 0: Scope Challenge — scope accepted after compatibility-preserving amendments.
- Architecture Review: 5 issues found, 5 resolved.
- Code Quality Review: 3 issues found, 3 resolved.
- Test Review: coverage diagram produced, 5 gaps found, 5 resolved.
- Performance Review: 2 issues evaluated, 0 unresolved.
- NOT in scope: written in the implementation plan.
- What already exists: written in the implementation plan.
- TODOS.md updates: 0 proposed.
- Failure modes: 0 critical gaps.
- Outside voice: Codex ran; final targeted result CLEAN.
- Parallelization: 1 sequential lane.
- Lake Score: 13/13 actionable recommendations chose the complete option; 2 scope-expansion
  suggestions were explicitly rejected.

## Final Verdict

CLEAN / 0 unresolved findings. The planning branch is ready to commit and hand to an isolated
implementation window. This verdict does not review the future implementation diff; that requires a
separate authoritative pre-PR review after local execution completes.
