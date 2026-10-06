# PDF Installed-Wheel Consumer Review

Date: 2026-10-06. Status: controller reviewed and complete local installed-wheel proof passed;
remote delivery requires separate authorization.

## Scope And Binding

This review covers the standalone installation controller, its regressions and the evidence
boundary in the [implementation plan](../plans/2026-10-06-pdf-installed-wheel-consumer-implementation.md).
The product source, dependencies and frozen historical fixtures remain byte-identical to merged
commit `2426847e53274d7bb14de12428b93107e502e79e` (PR #134). The final reviewed controller/test
HEAD is `11d78cab4b4f3abeb83fe444b834201a597a94f0`; subsequent documentation changes receive a
focused diff/link check. One read-only independent code review and targeted repair re-reviews
found no remaining Critical, Important or Minor code findings within this scope.
The unchanged controller ran at `5f5fd12c6b2d3e87892fdf2a18155cf9b68fd93c`; after explicit resume,
the delivery controller verified one complete successful dual-runtime receipt. The earlier partial
table has been replaced by that single run's evidence; the historical failed receipts remain retained.

| Input | Verified value |
|---|---|
| Package metadata version | `0.1.7`; no new release/tag claim |
| Wheel SHA-256 | `c109f5c5c51d4c75dd7e6fb8d4616fe8e0bb773f6270f190c70ca32c70a700ef` |
| Lock SHA-256 | `aa4f1c5d612b48a5b9280675eb82dfa972523877810ad90e7ef7d122aaf5109d` |
| Exported core constraints SHA-256 | `9b5c5e75cda34cb3679a391bf6b907082d95a5eb33dc58df0b4a329aba373ea9` |
| Package provenance | All 136 package files match committed source bytes |
| Wheel inventory | 141 members; only committed package files and canonical metadata accepted |
| Console entry points | Both entries equal committed `project.scripts` |
| Available runtimes | Existing Python 3.12.13 and 3.13.13; no runtime downloaded |
| Core versions | MCP 1.29.1, Pydantic 2.13.5, pydantic-core 2.46.5, PyMuPDF 1.27.2.3 |

## Closed Findings

- **Wheel provenance:** Package-byte equality alone accepted unbound top-level modules, startup
  `.pth` files, `.data` script payloads and rewritten console entry points. Nine controlled wheel
  cases reproduced that gap. The controller now restricts the member inventory and compares
  case-preserving entry point groups against the committed project before installation. Additional
  regressions cover duplicate INI entries and `DEFAULT` inheritance.
- **Dependency regression:** The earlier mismatch fixture omitted the project distribution and
  failed before checking the changed dependency version. The fixture now supplies all required
  distributions and separately proves the valid and mismatched MCP versions.
- **Installer metadata:** uv records an empty `archive_info` for this local wheel. The
  [PyPA direct URL specification](https://packaging.python.org/en/latest/specifications/direct-url-data-structure/#archive-urls)
  permits absent archive hashes. Missing hashes remain null; selected origin, interpreter,
  complete package bytes, locked versions and supplied/final wheel digests remain mandatory.
- **Negative fixture setup:** The resumed proof exposed a wrong `manifest.json` filename after
  its native/independent positive consumers succeeded. A regression reproduced the actual
  `FileNotFoundError`; the setup now modifies `export-manifest.json` only in a new copy and
  preserves the original manifest and Evidence bytes.

## Actual Acceptance Evidence

All boundaries below passed in one complete controller invocation with exit 0 and
`status="passed"`, using new isolated environments and data for both runtimes. The receipt schema
is `mke.pdf_extraction_observation_wheel_proof.v1`; its SHA-256 is
`92485d3bc8541254e5f0aebe5e2f436e00a081fbf16d6b8dd9f181818408cbf1`.
Its `network_access="not_used"` applies to this complete run; the earlier original-lock missing
artifact preparation used network separately. Each runtime has 31 installed distributions with
versions checked against the same lock; absent optional installer archive hashes remain null.

| Boundary | Python 3.12.13 | Python 3.13.13 |
|---|---|---|
| Fresh offline hash-checked installation | Passed | Passed |
| Environment/origin/136 package bytes/locked versions | Passed | Passed |
| Native installed CLI and official-SDK stdio MCP consumer | Passed | Passed |
| Fourteen tools, 33 exact UTF-8 chunks and descriptor/citation identity | Passed | Passed |
| Separate stdlib Export v3 consumer | Passed | Passed |
| Malformed-export and unknown-Source exit 1 | Passed | Passed |
| Complete controller success receipt | Passed in the same invocation | Passed in the same invocation |

The current tool fixture SHA-256 is
`f97979b156ae82978be2240d74e41138dc55f05b023deea9bfe4ef453e582a60`.
Both generated six-page fixtures have the declared text/raster partition and exact text. Their
actual PDF hashes and native identities are recorded separately:

| Identity | Python 3.12.13 | Python 3.13.13 |
|---|---|---|
| PDF SHA-256 | `50d5697c355d69cb6853f7cf7585cd3b3f1bdd433d5b857d5a44f0eba5392a5a` | `04249b6c6207c9f02e3beff97abeb493053e88b81ec4b3a19ecca9d1bc8a5db9` |
| Source | `src_05670cc6592341fab25a6a7db8d83a53` | `src_1688769013454c8d88d1593485b591e0` |
| Run | `run_937cff4cd2d146978a512810cdd708cf` | `run_0b4d544c33964046bf33ac019d8dea28` |
| Publication | `pub_794dc352431e49ca9fc2d0ff47c90590` | `pub_c9dc7b2e62d147a7bbb7592230ee39e6` |
| Revision | 1 | 1 |

Each case's fingerprint equals `sha256:` plus its actual PDF hash, and all descriptors/citations
match CLI/MCP/export/Viewer payload identity. Measured maximum canonical and full SDK response
sizes are 6,271 and 14,245 bytes respectively in both cases.

Controller regressions: 39 passed. Export/governance documentation checks: 26 passed. Ruff and
explicit-interpreter Pyright passed. Independent targeted re-reviews ran the provenance/version
selection (14 passed) and manifest regression (1 passed). Unchanged full-suite and earlier
installation evidence are reused under the approved scope; exact-merge CI has 4,400 passed and
47 skipped on each declared Python runtime. Raw diagnostics and all failed attempt roots are retained
outside the public source inventory.

## Retained History And Limits

Three earlier controller attempts failed: cold locked cache, an invalid optional installer-hash
assumption, and the negative-fixture manifest filename. The coordinating owner explicitly resumed
after reviewable repairs. Their failed receipts and roots remain retained; the successful evidence
above comes entirely from the final fresh invocation and does not reuse their partial successes.
C1 remote delivery, version/tag/Release publication, M2, OCR/model quality and interactive browser
file-origin/clipboard acceptance remain outside this local controller review.

The verified operator entry and failure meanings are in the
[PDF observation guide](../../how-to/observe-pdf-extraction-scope.md#installed-wheel-follow-up).
