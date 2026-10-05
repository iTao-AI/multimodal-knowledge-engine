# PDF Extraction Observation Review

Date: 2026-10-05. C0/M1 implementation and bounded test repair: independently accepted.
The delivery owner accepted the bounded verification scope with the browser limits below;
those limits are not represented as passing gates.
Independent review: no open Critical or Important findings.
Scope: [design](../specs/2026-10-05-pdf-extraction-observation-design.md).
Execution: [completed plan](../plans/2026-10-05-pdf-extraction-observation-implementation.md).
Base: `d92ee72d7773504fd2fc2e2d238c724d61c8dcf0`.
Reviewed runtime HEAD: `8a6d28fa3197f8130a369a4d8b55bca208d3458f`.
Reviewed test-repair HEAD: `8b01d6c445323e2a42ece90c99e4db0e0e1e2da2`.
The bounded follow-up changes one test and this documentation; product code and contracts are unchanged.

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
- A later acceptance selection reported `1 failed, 68 passed`: the cursor-isolation test selected
  the first catalog Source again after adding a one-Evidence Source. Catalog orders by content
  fingerprint and Source ID, while generated PDF trailer IDs change its serialized hash. Selecting
  the one-Evidence Source correctly returns `complete` without a cursor. Controlled second-Source
  fingerprints `0*64` and `f*64` reproduced the old test as `1 failed, 1 passed`. The repair binds
  the original three-Evidence Source before insertion and asserts both catalog orders, selected
  identity, `more_available`, v1 rejection and v2 continuation. Earlier green samples did not force
  both orders. No pagination implementation, ordering contract or frozen PDF fixture was changed.

The independent whole-change review and targeted repair reviews checked these authority, contract
and test boundaries. The original Important finding is closed; no new Critical or Important finding
remains. The reported flaky-test failure and controlled RED remain part of the acceptance evidence.

## Executed Local Verification

| Gate | Observed result and binding |
| --- | --- |
| Full provider-free Python 3.13 regression | `4423 passed, 14 skipped` at `7e5cce37c2ebdba98ce068e45d03dadb0903bf0d` |
| Verification after the export/build review fixes | `320 passed` at the reviewed runtime HEAD; export domain/application/storage/filesystem/CLI, Source v2, consumers, Viewer, native proof, packaging, documentation and version identity |
| Bounded cursor-fixture repair | `90 passed` at the test-repair HEAD; the failing acceptance selection plus Source discovery and current MCP fixture |
| Independent final acceptance selection | `70 passed` at the test-repair HEAD; PDF extractor/report, Source v2, Export v3, native consumer and Viewer; test-file SHA-256 `45e842d7496363cabcf9f02ca0bb8202ecf7aae60b1bbeece93bc23d1f342b11` |
| Ruff | Full check passed at the reviewed runtime HEAD; changed test check passed at the test-repair HEAD |
| `UV_OFFLINE=1 uv run pyright` | Zero errors and warnings at both reviewed HEADs |
| `UV_OFFLINE=1 uv build` plus archive inspection | Sdist and wheel built; 135 Python modules match source byte-for-byte; execution-record entries are zero; lock and historical fixtures unchanged |
| Native CLI / official MCP SDK / independent export / Viewer payload | Shared Source/Publication/revision/Run/fingerprint/locator identity and exact UTF-8 verified |
| Interactive Viewer over an HTML-only localhost preview | Mixed/decorative warnings, old-v2 unknown, omitted-page notices, hostile labels/text and visible citation details checked; no console errors |
| Focused documentation audit | Current guides, references, contract fixture and immutable-release boundaries aligned |

The full suite was not rerun at the later HEADs. Unchanged inputs retain that full-suite evidence;
the 320-test selection covers the export/build repairs and 90 tests cover the cursor-fixture repair.
Fourteen skipped tests remain skipped;
five PyMuPDF/SWIG deprecation warnings were retained without suppression. Python 3.12, a newly
installed wheel, hosted checks and a new release proof were not executed.

The [native proof](../../how-to/observe-pdf-extraction-scope.md) uses declared six-page synthetic input:
one text-only, two mixed, one raster-only and two neither pages. Its 33 exact-read chunks preserve
all known UTF-8 text; the raster-only value is absent. Maximum measured canonical and SDK result
sizes were 6,271 and 14,245 bytes. Separate 300-page coverage checks details 1–256 and the exact
257–300 omission while preserving whole-document counts. These are bounded synthetic checks,
not original-media semantic coverage or production adoption evidence.

## Remaining Verification And Delivery Boundary

The automation browser again blocked direct `file://` navigation before loading: its URL policy
allows only HTTP/HTTPS. No alternate browser, native action or permission change was used to bypass
that policy. Interactive behavior was checked over localhost, while file-origin opening remains
unverified. The Copy action showed its success status, but both clipboard read interfaces returned
empty results; a normal page-local Cmd+V attempt was also rejected because the tool's virtual
clipboard had no data. Copied citation contents were not independently verified. These are explicit
verification limits, not passing browser gates or demonstrated product defects.

The normal user path remains opening the generated HTML directly in a standard browser, then Copy
or the selectable-reference fallback when clipboard access is denied, as documented in the
[Viewer guide](../../how-to/view-compiled-library.md). The citation formatter, Copy handler and
fallback code are byte-for-byte unchanged from the comparison base. This follow-up changes no
product code. The delivery owner accepted these existing reading/copy paths within the declared
limited scope.
The temporary preview server and browser tab were released; the branch, worktree and ignored
evidence are retained for inspection.

This record covers local/native acceptance. PR, reviewed-HEAD checks, merge and exact-main CI are
separate delivery gates, recorded in the PR. No tag or release belongs to this scope.
No M2, OCR, image understanding, new provider, dependency/version change, Source-scoped Search/Ask,
retrieval-quality improvement or new immutable v0.1.7 claim is included. Rollback and older-contract
selection are documented in ADR-0015. No deferred feature Issue was created within this local scope.
