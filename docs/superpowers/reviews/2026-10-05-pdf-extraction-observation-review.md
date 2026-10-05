# PDF Extraction Observation Review

Date: 2026-10-05. Local C0/M1 candidate: accepted with the browser verification limits below.
Independent review: no open Critical or Important findings.
Scope: [design](../specs/2026-10-05-pdf-extraction-observation-design.md).
Execution: [completed plan](../plans/2026-10-05-pdf-extraction-observation-implementation.md).
Base: `d92ee72d7773504fd2fc2e2d238c724d61c8dcf0`.
Reviewed code HEAD: `8a6d28fa3197f8130a369a4d8b55bca208d3458f`.
Subsequent closeout changes only documentation and its index; runtime and test inputs are unchanged.

## Result And Authority

The public entry now leads from Source discovery through explicit Publication selection, page or
timestamp browsing, complete stored text and citation verification, with the offline Viewer linked.
Opt-in Source v2 and Export v3 disclose normalized text and displayed-raster presence from the
producing Run. Observed counts partition all PDF pages; older missing observations remain unknown
with nullable counts. Decorative rasters count as present and vector drawings remain outside scope.

Report storage and normal Publication activation share the existing transaction. Failed observation
writes roll back replacement. Reads use the active Publication's producing Run, with bounded page
materialization and explicit omitted ranges. Old Source v1, Export v1/v2, exact Evidence bytes,
locators and required stages retain their semantics. Search/Ask and retrieval defaults are unchanged.
The current fourteen-tool fixture is explicit; historical eight/ten/twelve-tool fixtures remain
unchanged. See [ADR-0015](../../decisions/0015-pdf-extraction-observations.md).

## Durable Findings Resolved

- Export v3 initially accepted missing or shifted page details. Both the domain snapshot and the
  independent consumer now require pages `1..min(total_pages,256)`. Empty, shifted and shortened
  declarations are rejected; forged exports cannot produce a Viewer. Source v2 range browsing
  retains its separate flexible window.
- Current numeric replay now derives a separate runtime schema expectation after the additive
  observation table. Archived protocols, input bytes and schema validation remain frozen;
  strict-live stale-fence rejection and wrong-observed-schema rejection remain enforced. No rank,
  retrieval-quality or historical metric is changed.
- Archive inspection found ignored execution records in the initial direct-worktree sdist.
  Explicit sdist exclusions now cover `artifacts/` and `.superpowers/`. An actual build regression
  covers ordinary roots and roots beneath `.codex`, where the backend may discard VCS patterns.
  The inspected replacements contain no local execution records. No initial archive was published.

The independent whole-change review and targeted repair review checked these authority and contract
boundaries. The original Important finding is closed; no new Critical or Important finding remains.

## Executed Local Verification

| Gate | Observed result and binding |
| --- | --- |
| Full provider-free Python 3.13 regression | `4423 passed, 14 skipped` at `7e5cce37c2ebdba98ce068e45d03dadb0903bf0d` |
| Verification after the review fixes | `320 passed` at the reviewed code HEAD; export domain/application/storage/filesystem/CLI, Source v2, consumers, Viewer, native proof, packaging, documentation and version identity |
| `.venv/bin/ruff check .` | Passed at the reviewed code HEAD |
| `UV_OFFLINE=1 uv run pyright` | Zero errors and warnings at the reviewed code HEAD |
| `UV_OFFLINE=1 uv build` plus archive inspection | Sdist and wheel built; 135 Python modules match source byte-for-byte; execution-record entries are zero; lock and historical fixtures unchanged |
| Native CLI / official MCP SDK / independent export / Viewer payload | Shared Source/Publication/revision/Run/fingerprint/locator identity and exact UTF-8 verified |
| Interactive Viewer over an HTML-only localhost preview | Mixed/decorative warnings, old-v2 unknown, omitted-page notices, hostile labels/text and visible citation details checked; no console errors |
| Focused documentation audit | Current guides, references, contract fixture and immutable-release boundaries aligned |

The full suite was not rerun at the later code HEAD. Unchanged inputs retain that full-suite
evidence, while the 320-test selection covers both repairs. Fourteen skipped tests remain skipped;
five PyMuPDF/SWIG deprecation warnings were retained without suppression. Python 3.12, a newly
installed wheel, hosted checks and a new release proof were not executed.

The [native proof](../../how-to/observe-pdf-extraction-scope.md) uses declared six-page synthetic input:
one text-only, two mixed, one raster-only and two neither pages. Its 33 exact-read chunks preserve
all known UTF-8 text; the raster-only value is absent. Maximum measured canonical and SDK result
sizes were 6,271 and 14,245 bytes. Separate 300-page coverage checks details 1–256 and the exact
257–300 omission while preserving whole-document counts. These are bounded synthetic checks,
not original-media semantic coverage or production adoption evidence.

## Remaining Verification And Delivery Boundary

The automation browser blocked direct `file://` navigation. Interactive behavior was checked over
localhost, while file-origin opening remains unverified. The Copy action showed its success status,
but the host clipboard readback was empty, so copied citation contents were not independently
verified. Neither limit is represented as a passing browser gate. The temporary preview server and
browser tab were released; the branch, worktree and ignored evidence are retained for inspection.

No push, PR, merge, tag, release or publication occurred. This is a reviewable local candidate.
No M2, OCR, image understanding, new provider, dependency/version change, Source-scoped Search/Ask,
retrieval-quality improvement or new immutable v0.1.7 claim is included. Rollback and older-contract
selection are documented in ADR-0015. No deferred feature Issue was created within this local scope.
