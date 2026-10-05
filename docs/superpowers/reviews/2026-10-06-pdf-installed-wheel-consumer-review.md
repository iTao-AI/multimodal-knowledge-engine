# PDF Installed-Wheel Consumer Review

Date: 2026-10-06. Status: controller and targeted repairs reviewed; complete C1 acceptance pending.

## Scope And Binding

This review covers the standalone installation controller, its regressions and the evidence
boundary in the [implementation plan](../plans/2026-10-06-pdf-installed-wheel-consumer-implementation.md).
The product source, dependencies and frozen historical fixtures remain byte-identical to merged
commit `2426847e53274d7bb14de12428b93107e502e79e` (PR #134). The final reviewed controller/test
HEAD is `11d78cab4b4f3abeb83fe444b834201a597a94f0`; subsequent documentation changes receive a
focused diff/link check. One read-only independent code review and targeted repair re-reviews
found no remaining Critical, Important or Minor code findings within this scope.

| Input | Verified value |
|---|---|
| Package metadata version | `0.1.7`; no new release/tag claim |
| Wheel SHA-256 | `c109f5c5c51d4c75dd7e6fb8d4616fe8e0bb773f6270f190c70ca32c70a700ef` |
| Lock SHA-256 | `aa4f1c5d612b48a5b9280675eb82dfa972523877810ad90e7ef7d122aaf5109d` |
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

| Boundary | Python 3.12.13 | Python 3.13.13 |
|---|---|---|
| Fresh offline hash-checked installation preflight | Passed | Passed |
| Environment/origin/136 package bytes/locked versions | Passed | Passed |
| Native installed CLI and official-SDK stdio MCP consumer | Passed | Not run |
| Fourteen tools, 33 exact UTF-8 chunks and descriptor/citation identity | Passed | Not run |
| Separate stdlib Export v3 consumer | Passed | Not run |
| Malformed-export and unknown-Source exit 1 | Passed in targeted repair | Not run |
| Complete controller success receipt | Failed before second case | Not produced |

The 3.12 synthetic PDF fingerprint is
`sha256:fc8a96709b7eab6553292e4cd5bb9bf4cd4883dfff4c6d10843fce649abc63e2`;
the current tool fixture SHA-256 is
`f97979b156ae82978be2240d74e41138dc55f05b023deea9bfe4ef453e582a60`.
Native Source `src_f54cd4cb4d744aa3b11ef0c32e20d4a5`, Run
`run_bd1415acb4dd465e82ac2f881aec9e13` and Publication
`pub_8856c4dac25d4f4c8b3236de3ebb2538` revision 1 match CLI/MCP/export/Viewer payload identity.
Measured maximum canonical and full SDK response sizes are 6,271 and 14,245 bytes respectively.

Controller regressions: 39 passed. Export/governance documentation checks: 26 passed. Ruff and
explicit-interpreter Pyright passed. Independent targeted re-reviews ran the provenance/version
selection (14 passed) and manifest regression (1 passed). Unchanged full-suite and earlier
installation evidence are reused under the approved scope; exact-merge CI has 4,400 passed and
47 skipped on each declared Python runtime. Raw diagnostics and all failed attempt roots are retained
outside the public source inventory.

## Remaining Acceptance

The resumed complete run exited 1 after the 3.12 positive consumers because of its negative-fixture
setup. Its original failed receipt is preserved; targeted repair success does not replace a complete
dual-runtime receipt. The next full run requires the coordinating owner's explicit route decision.
C1 remote delivery, version/tag/Release publication, M2, OCR/model quality and interactive browser
file-origin/clipboard acceptance remain outside this local controller review.

The verified operator entry and failure meanings are in the
[PDF observation guide](../../how-to/observe-pdf-extraction-scope.md#installed-wheel-follow-up).
