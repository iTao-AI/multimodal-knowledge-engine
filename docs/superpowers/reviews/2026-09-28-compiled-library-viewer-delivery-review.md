# Compiled Library Viewer delivery review

- Date: 2026-09-28
- Base: `27fd47e3693fe89e6a40820914395e8499fdb23b` (`main` at integration)
- Reviewed implementation and documentation: through `21b6271b09a7983f72c8a0c1544665fae234989a`

## Decision

The Export v2 consumer and offline, single-file Viewer form a bounded read-only path from active Publications to exact Evidence text and traceable citations. The change preserves the current CLI, MCP, retrieval, provider, and storage contracts. The repository walkthrough uses the existing text-layer PDF and video transcript-sidecar fixtures; the README shows a page generated from those test fixtures, while the older Evidence workspace frames remain labeled as synthetic projections.

The delivery review found no remaining code or documentation blocker for a PR. The newly integrated branch was not browser-retested; the earlier real-browser check used the identical Viewer script blob. PR checks and merge verification remain separate hosted gates.

## Evidence checked

- The Viewer script's Git blob is `29989f4120fa7b5115142ad87fcc73e864ce0562`, byte-identical to the previously browser-checked `dff7d9b` script. That earlier check covered the two-Source, four-Evidence fixture in desktop and narrow layouts, filtering, keyboard focus, Source and fragment changes, citation copy, and untrusted text display.
- The README image at `docs/how-to/assets/compiled-library-viewer-repository-samples.png` is a page-only screenshot from actual CLI ingestion of the repository PDF and video sidecar, Export v2, consumer validation, and Viewer generation. It shows two Sources and four Evidence records. SHA-256: `d217be20245e75ff2292e461f27f381635f6662ead0550515977a43291aa4820`. It contains no browser address bar or private paths.
- The source-checkout walkthrough ran through ingest, explicit v2 export, consumer validation, and HTML generation with two Sources and four Evidence records. Its relative paths were checked from the repository root. The final `open` line is identified as macOS-specific; it was not executed in the integrated-branch check.
- The public `v0.1.7` GitHub Release is published, and the tagged tree does not contain `scripts/build_compiled_library_viewer.py`. The READMEs identify the Viewer as available from the current source checkout and absent from that release. The five changed documentation files' relative links resolved locally; a scan of changed text found no private local paths.

## Verification by revision

- With Viewer code at `f05ad64`, the execution report recorded `uv run pytest -q`: 4,294 passed, 14 skipped; affected focused tests: 53 passed; Ruff, Pyright, `uv build`, `mke proof run` (8/8), and `mke demo --verify` passed. The dependency lockfile did not change.
- After README, image, and documentation assertion changes, focused tests at `dad9aae3` passed: 40 passed. A final macOS note and removal of brittle README word-ban assertions at `21b6271` passed the affected focused tests: 19 passed. `git diff --check` passed at both steps.
- This review checked the complete change against `main`, the screenshot and Viewer blob hashes, relative links, release wording, and the final diff. No new runtime or dependency change followed the full test run.

## Browser boundary

The available Chrome control refused navigation to the integrated branch's local `file://` HTML, so this branch has no new GUI result. The execution report described an http/https-only navigation policy and a prohibition on switching interfaces to bypass it; the original tool output was not retained, so this review does not quote it or assign a more specific approval type. The prior screenshot and interactions are evidence for the identical Viewer script, not a new browser run on the integrated branch.
