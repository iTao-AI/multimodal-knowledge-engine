# v0.1.3 Post-Release Closeout

Status: `PUBLISHED / ARCHIVE VERIFIED / DOCS CLOSURE PENDING REVIEW`

Date: 2026-07-17

## Merge Authority

- Release-candidate PR: <https://github.com/iTao-AI/multimodal-knowledge-engine/pull/73>
- Reviewed head: `57133fcdb7e3c49582028aa02b51e2b1e32c5378`
- Squash merge commit: `86b8a2d85631f5e94afa49186909ac62ffd54a15`
- Merge parent: `5d707cfcc98da8ce76d31238c14158cd78b03803`
- Reviewed feature tree and merge tree: `88862bf57464e4eb630eb938a573d5188e3feed6`
- Merged at: `2026-07-17T01:58:19Z` by `iTao-AI`

The exact-head PR gates passed before merge. The post-merge CI, Python 3.12/3.13, embedding-extra,
consumer source-pack, compiled Library export, and configured CodeQL workflows also passed on the
exact merge SHA.

## Exact-Main Verification

The primary worktree was fast-forwarded until `HEAD == main == origin/main` at the merge commit and
remained clean. Fresh verification from that commit produced:

- full pytest: `2345 passed, 5 skipped, 5 warnings` in `137.08s`;
- Ruff: passed; Pyright: 0 errors; build: passed;
- product proof: 8/8; demo: passed;
- local-knowledge proof and Evidence-provenance proof: passed;
- release presentation audit: `status=ok` with zero violations;
- artifact regression: `191 passed, 5 warnings`; and
- E1, E2, E3-A, E3-B, E3-C, E3-D, and E3-E canonical validators: passed.

The four frozen OCR evidence files retained their approved SHA-256 values:

- `candidate-environments.json`: `d2232fcbd6775a9f03fa3d2a77b181987b5cfa43c9fdc1efcb48f08f01553d2a`
- `model-artifacts.json`: `3d1e8c45b7ed0c817acaeda3f51954b463016763690e09ca1f23162042219d6e`
- `provider-startup.json`: `1a159461fd73c7069905b0a085f5b900f4b1577dbf418a86adcf96b9c6354652`
- `phase0-scorecard.json`: `b84720bd33999ad333e3ac5105b7abd996ab910b3c9cd458f6c43e66fa709457`

## Final Candidate Identity

- Wheel: `multimodal_knowledge_engine-0.1.3-py3-none-any.whl`
- Wheel bytes: `309326`
- Wheel SHA-256: `50bccd685957c1b21e9b45d066060f0a89dd7f4e71e6f86b3546ce3ea4a2b036`
- Receipt canonical digest: `b6527b462c1f76907c46477c30fff1202dfc44ba3c8cea17cb633072c9a1accc`
- Receipt file SHA-256: `fac2dc1b1166712944268e389beef1cd27e740ce32b4f4fa6ffad1808434e4f6`
- Receipt source commit: `86b8a2d85631f5e94afa49186909ac62ffd54a15`

The independent descriptor-read validator co-bound version `0.1.3`, source commit, canonical
receipt, wheel filename, size, and digest. The receipt-bound installed smoke passed install,
identity, proof, demo, CLI, and MCP steps. The compiled-export proof passed with two interpreters;
its `proof_input_wheel_sha256` exactly equaled the independently validated wheel digest.

## Publication

- Tag: `v0.1.3`
- Annotated tag object: `447ebdf7416b6c6e25c8f6d2017d1ef48b465c0f`
- Peeled target: `86b8a2d85631f5e94afa49186909ac62ffd54a15`
- GitHub Release: <https://github.com/iTao-AI/multimodal-knowledge-engine/releases/tag/v0.1.3>
- Published at: `2026-07-17T02:10:45Z` by `iTao-AI`
- State: latest at publication, non-draft, non-prerelease
- Additional assets: 0

No candidate wheel or receipt was uploaded.

## Public Archive Smoke

- Archive: `multimodal-knowledge-engine-0.1.3.tar.gz`
- Bytes: `3691525`
- SHA-256: `a8f0a595f6f039628feb2a9d3e13237b37b000aa311e1b7b7b013e0e8303496e`

The GitHub-generated source archive reported package and module version `0.1.3`. Locked dependency
sync, product proof 8/8, demo, local-knowledge proof, Evidence-provenance proof, and presentation
audit passed. A real archive ingest and Compiled Library Export produced two sources and three
Evidence records. The standalone standard-library consumer accepted
`mke.compiled_library_export.v1`, `mke.compiled_markdown.v1`, and `mke.evidence_ref.v1` with
`status=passed`.

The archive contained no candidate artifact files, actual private identity paths, credentials, or
secret material. Call-owned archive and runtime directories were removed after identities and
results were recorded.

## Boundaries And Remaining Gate

This release does not publish to PyPI or another registry, deploy a service, add production OCR,
promote a retrieval or OCR runtime, verify LLM Wiki compatibility, or claim adoption or business
impact. PDF OCR remains Phase 0 planning evidence: PP-OCRv6 medium is the production-planning
baseline and PaddleOCR-VL 1.6 remains a comparison candidate.

This docs-only closeout commit is pending an actual-diff review. Its branch is intentionally not
pushed, and task-owned worktrees and branches remain intact until a separately authorized cleanup
gate.
