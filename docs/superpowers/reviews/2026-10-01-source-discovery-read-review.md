# Source Discovery And Exact Evidence Read Review

Date: 2026-10-02. Local delivery: **READY**. Final independent verdict: **Approved**;
spec compliance: **Compliant**; code and documentation quality: **Approved**.
Approved scope: [spec](../specs/2026-10-01-source-discovery-read.md).
Implementation: [completed plan](../plans/2026-10-01-source-discovery-read-implementation.md).
Reviewed range: `102b114d150f005ed66f680b995b7b9733d985cb..0af8cfb43a79a0e02d45ba42dfd9416fe42b978a`.
The reviewed and full-suite-tested feature HEAD is `0af8cfb43a79a0e02d45ba42dfd9416fe42b978a`.

## Result

The local CLI and stdio MCP can discover active Sources, select an explicit Publication, browse
ordered page or overlapping timestamp Evidence, and reuse unchanged `read_evidence_v1` to verify
complete stored UTF-8 text and citation provenance. The current exact inventory has twelve tools;
all ten prior schemas, descriptions, annotations and historical fixtures remain unchanged.

Coverage is a bounded projection of the producing Run. Catalog summaries explicitly omit PDF
per-page character counts; selected Sources return at most 256 counts with omission metadata. Missing
reports are `not_observed`. Stored text, preview completeness and original-media coverage remain
distinct. Search ranking, default CJK strategy, opt-in mixed strategy, extraction, atomic
Publication behavior and export formats remain unchanged.

## Durable Review Findings Resolved

- Reject missing Library ownership when Sources remain; a genuinely empty database still works.
- Register the new nested locator schemas through the active Pydantic handler while preserving
  all old native tool schemas.
- Preserve actual newline/backslash/quote/Unicode regression coverage in the native budget test.
- Evaluate valid oversized range endpoints in SQLite's finite stored integer domain, retaining
  page inclusivity and timestamp overlap/exclusive-end semantics. The original filter remains
  authenticated in the cursor; no public cap or filter rewrite is introduced.
- Keep current CLI command-inventory assertions aligned with the three additive commands,
  preserving the existing relative order and destination/default assertions.

The final independent whole-branch review found no Critical, Important or Minor findings. It
covered authority validation before selected text access, coherent snapshots, cursor ownership
and original-filter authentication, bounded serialization and positive pagination progress,
strict native contracts, CLI error exits, independent exact-read provenance and honest coverage.
All earlier task and targeted repair findings are closed.

## Executed Local Acceptance

| Gate | Observed result |
| --- | --- |
| Full regression, existing Python 3.13 environment | `4388 passed, 14 skipped` in 311.96 seconds |
| `ruff check .` | Passed |
| Configured `pyright`, plus explicit new consumer-script checks | Zero errors and warnings |
| `mke proof run --json` | Product proof `8/8` |
| `mke demo --verify` | Passed |
| Actual independent CLI-ingest / official-SDK consumer | Twelve tools; catalog/page/timestamp/exact-read/citation checks passed |
| Cached-backend wheel/sdist from committed Git export | Built; new modules/example/docs/fixture present; local state excluded |
| Important-feature `gstack-workflows:document-release` audit | Current contracts, real commands and historical boundaries aligned; 205 local links in 13 changed documents valid |
| Task, targeted repair and final whole-branch reviews | Approved; no open findings |
| Closeout documentation checks | 28 passed; all 12 relative file links in the three closeout documents valid |

The full regression retains five pre-existing PyMuPDF/SWIG deprecation warnings. The fourteen
skipped tests are reported as skipped, not passing. No dependency change or warning suppression
is part of this delivery.

The independent example uses a declared four-page mixed PDF and synthetic transcript sidecar.
Its PDF report observes total/extracted/empty/suspected-scan counts of `4/3/1/1`, with character
counts `[30,2279,0,35]`. Page 2 has an incomplete prefix preview; 26 exact-read chunks reconstruct
2,459 UTF-8 bytes with independently checked SHA-256 and full descriptor equality. Timestamp
`[500,1500)` selects `[0,1000)` and `[1000,2000)` in order. The sidecar report is `not_observed`;
no ASR provenance or quality is invented. Maximum measured canonical and actual SDK tool-call
result sizes are 5,516 and 12,136 bytes. The persistent near-budget case includes actual escaping
and pagination, with maxima 30,646 and 70,469 bytes over four pages. An independent native probe
with a 7,800-emoji Source name measured 32,420 canonical and 65,430 SDK bytes within the declared
32 KiB canonical and 96 KiB SDK tool-call result bounds.

These result measurements concern tool calls, not the `tools/list` inventory message. See
[Discover And Read Sources](../../how-to/discover-and-read-sources.md) for the executable example.

## Build Boundary And Remaining Scope

A direct worktree backend invocation included ignored local coordination and validation material
in its initial sdist. Archive inspection caught this before any external operation. Building a
committed Git export and inspecting both outputs excludes `.superpowers`, `artifacts`, `.venv`,
`.git` and caches while preserving public source, documentation and fixtures. Do not use an
uninspected worktree archive as a source-only delivery artifact.

Closeout adds only this accepted review, completed-plan metadata and its index link after the
reviewed feature HEAD. Those documentation changes receive focused checks; the final wheel and
sdist are rebuilt and inspected from the final committed tree.

This is local source/native acceptance plus package construction. A newly installed wheel,
dual-Python installation proof, push, PR, merge, release and hosted delivery were not executed.
No OCR, model download, real ASR, scene understanding, retrieval-quality improvement or
original-media semantic completeness is claimed. There is no database migration; rollback of
the additive registrations/routes requires exact-inventory consumers to choose matching fixtures.
No work remains within the approved local gate. The task branch, isolated worktree and local
validation evidence are retained.
