# Versioned Evidence Provenance Contract Implementation Review

Date: 2026-07-11

Status: `CLEAN / 0 findings` after targeted authoritative re-review of
`53b840b8b88082a204719ea5da98765c4d55dcc5`.

Base: `c8717dbaea9fa4ab0273a778151d64d7360e83f3`.

## Scope

This branch adds three strict read-only MCP tools and preserves the five legacy contracts. It adds
no database migration, retrieval/ranking change, HTTP/UI, OCR/crawler, orchestration framework,
runtime promotion, version, CHANGELOG, release, or deployment work.

## Verification Evidence

- Review regression suite: `54 passed` across domain, strict MCP schemas, legacy schema snapshot,
  SQLite provenance integrity, and real stdio proof.
- Full pytest: `1386 passed, 5 skipped`; only the five existing PyMuPDF/SWIG deprecation warnings.
- Ruff: passed. Pyright: `0 errors, 0 warnings, 0 informations`.
- Build: sdist and wheel created successfully.
- Product proof: 8/8. Demo: passed. Local-knowledge proof: passed.
- Evidence-provenance proof: passed over real stdio MCP and official SDK.
- Installed wheel: Python 3.12.13 and 3.13.12 passed from external cwd with hostile
  `PYTHONPATH`, installed-module identity verification, lock-derived constraints, and strict
  offline mode.
- Release presentation audit: `status=ok`, zero violations. `git diff --check`: passed.

## Authoritative Review Remediation

The 2026-07-12 authoritative review returned `CHANGES REQUESTED`. All five remediation items were
implemented and committed at `53b840b8b88082a204719ea5da98765c4d55dcc5`. Targeted authoritative
re-review then returned `CLEAN / 0 findings`.

- Domain and Pydantic response validators now close observation/result/status relationships,
  reject impossible Publication counts, and enforce the public maximum of 20 Search/Ask items.
- Strict error consumers accept only the shared public cause allowlist or the stable redacted
  cause. `problem` and `next_step` are machine tokens; path, credential, environment, stderr, and
  traceback mutations are rejected.
- SQLite proof now parameterizes ten corruption classes, covers mixed active/inactive Source
  states, proves one transaction view against a second connection write, and asserts a fixed five
  SELECT shape with one bulk enrichment and no N+1 provenance reads.
- The timeout child writes its PID. The real stdio proof performs bounded polling until that PID
  is gone and separately proves temporary store cleanup.
- Both worktree and planning-base range `git diff --check` pass after removing the three extra EOF
  blank lines.

## Artifact Closure

The repository-supported atomic refresh updated E1 through E3-B identity metadata. Downstream
E3-C, E3-D, and E3-E protocol/artifact identities were rebuilt in dependency order with existing
repository builders. E1/E2/E3-A/E3-B evaluator reports, normalized by removing volatile duration
fields,
matched Task 0 byte-for-byte. All E1 through E3-E canonical validators passed. Corpus fixture
bytes, qrels, query definitions, observations, metrics, gates, profiles, candidates, and verdicts
did not drift.

## Remaining Risks

The authoritative implementation review is closed as `CLEAN / 0 findings`. The installed-wheel
proof validates local platform/cache availability, not other operating systems or architectures.
No network/model/fixture download was used.
