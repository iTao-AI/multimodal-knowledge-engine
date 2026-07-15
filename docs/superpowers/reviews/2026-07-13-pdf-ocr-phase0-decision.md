# PDF OCR Phase 0 Viability Decision

Date: 2026-07-15

Status: ACCEPTED PHASE 0 GO / CLEARED FOR SEPARATE PRODUCTION PLANNING

## Evidence Scope

The Task 6 consumer proof starts from committed HEAD
`f29730eb4433d08a9a0d00bb5a86584a577dd469`. It built and reused exactly one
`multimodal_knowledge_engine-0.1.2-py3-none-any.whl`: `294392` bytes, SHA-256
`e17ed9ce1f374eb10a5e006f56d34c50bacc35f497d32654faf40459fa0316b1`.

The installed-wheel aggregate proof returned:

```json
{"ask_verified":true,"cleanup":true,"evidence_ref_verified":true,"network_blocked":true,"package_version":"0.1.2","profile":"phase0-200dpi-plain-text-v1","protocol":"pdf-ocr-phase0-v1","provider":"ppocrv6-medium-cpu-spike-v1","publication_verified":true,"python_version":"3.13.12","schema":"mke.pdf_ocr_phase0_consumer_proof.v1","search_verified":true,"status":"passed","wheel_reused":true,"wheel_sha256":"e17ed9ce1f374eb10a5e006f56d34c50bacc35f497d32654faf40459fa0316b1"}
```

That installed wheel validated the canonical Phase 0 scorecard and replayed disposable active
Publications through current contracts using the closed protocol expected truth. It was also used
by an isolated official MCP Python SDK client. The client discovered `search_library_v1` and
`ask_library_v1`, then verified equal, portable `mke.evidence_ref.v1` page provenance and normalized
payload truth for all three protocol queries. OS-level network denial was observed during this run.
The call-owned environment and database were removed after proof completion. Task 6 did not invoke
`run_phase0_scorecard`, rerun an OCR provider or model, or generate the scorecard.

## Closed Authority

- Protocol: `pdf-ocr-phase0-v1`, SHA-256
  `1c1f9310f3c719843e2af49ce44b0d03218c85ab84c7bd9f148afea3d6d1c2ef`; four documents, nine
  pages, and three queries.
- Scorecard: SHA-256
  `b84720bd33999ad333e3ac5105b7abd996ab910b3c9cd458f6c43e66fa709457`.
- Package receipt: SHA-256
  `d2232fcbd6775a9f03fa3d2a77b181987b5cfa43c9fdc1efcb48f08f01553d2a`; all 16 Python
  3.12/3.13 candidate and MKE-surface cells passed, with no unsupported cell. The Task 4R package,
  startup, and Task 5B scorecard extractor identities bind MKE wheel SHA-256
  `6f499710dce8f4ac3e23ac0513c0020a8367f83b38755d43f6ffc4fb49056218`.
- Model receipt: SHA-256
  `3d1e8c45b7ed0c817acaeda3f51954b463016763690e09ca1f23162042219d6e`.
- Provider startup receipt: SHA-256
  `1a159461fd73c7069905b0a085f5b900f4b1577dbf418a86adcf96b9c6354652`.
- Pinned model components are `PaddlePaddle/PP-OCRv6_medium_det`,
  `PaddlePaddle/PP-OCRv6_medium_rec`, `PaddlePaddle/PP-DocLayoutV3`, and
  `PaddlePaddle/PaddleOCR-VL-1.6`; every receipt declares `Apache-2.0`.

## Observed Candidate Results

All values below are observations on the fixed protocol, not approved production limits.

| Candidate | Result | CER | WER | Route | Query / EvidenceRef | Elapsed | Peak RSS | Temporary | Result | Package | Model |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `apple-vision-local-v1` | failed | 12/137 | 1/19 | 9/9 | 2/3 | 1609 ms | 102268928 B | 248441 B | 140 B | 125072 B | 0 B |
| `paddleocr-vl-1.6-cpu-spike-v1` | passed | 0/137 | 0/19 | 9/9 | 3/3 | 59638 ms | 10005151744 B | 248253 B | 158 B | 771367970 B | 2062479643 B |
| `ppocrv6-medium-cpu-spike-v1` | passed | 0/137 | 0/19 | 9/9 | 3/3 | 42974 ms | 5047795712 B | 248538 B | 158 B | 746367947 B | 139160864 B |

Apple Vision did not satisfy query and EvidenceRef hard gates. Both Paddle candidates satisfied the
closed Phase 0 gates. The deterministic tie-break selected
`ppocrv6-medium-cpu-spike-v1` with profile `phase0-200dpi-plain-text-v1`.

## Authority Decision

Phase 0 `GO` is accepted for separate production planning using
`ppocrv6-medium-cpu-spike-v1` and `phase0-200dpi-plain-text-v1` as the sole selected planning
baseline. The following limits are accepted only as provisional regression and planning budgets
for the closed synthetic protocol. They are not production SLAs:

- route, query, and EvidenceRef accuracy must remain 100% on the closed protocol;
- observed CER and WER must remain zero on the closed protocol;
- elapsed time at most 60000 ms and peak RSS at most 6442450944 bytes;
- temporary bytes and result bytes at most 1048576 bytes each;
- installed package bytes at most 800000000 and model bytes at most 160000000;
- cache-only startup and OS-level network denial remain mandatory.

This acceptance clears only the production-planning gate. A representative corpus and a final
installed-wheel real OCR ingest remain required before a public capability. This record does not
authorize a production OCR extra, public flag, runtime default, runtime promotion, hosted service,
release, or deployment.

## Verification

Fresh local verification recorded:

- `UV_OFFLINE=1 uv run pytest -q tests/scripts/test_pdf_ocr_phase0_consumer.py`:
  `19 passed, 5 warnings`.
- `UV_OFFLINE=1 uv run pytest -q`: `2006 passed, 5 skipped, 5 warnings`.
- `uv run ruff check .`: passed.
- Focused Pyright for the Task 6 script and tests: `0 errors, 0 warnings`.
- A subsequent strict-typing closure correctly attributed the branch-only 368-error result to the
  four Phase 0 OCR test files rather than to the main baseline. Bare `uv run pyright` now passes
  with `0 errors, 0 warnings, 0 informations` under the repository's strict configuration.
- `UV_OFFLINE=1 uv build --wheel`: passed and produced the wheel identity above.
- `UV_OFFLINE=1 uv run mke proof run`: 8/8 cases passed.
- `UV_OFFLINE=1 uv run mke demo --verify`: passed.
- `UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py`: passed.
- `UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py`: passed.
- `uv run python scripts/release_presentation_audit.py --root .`: `status=ok`.
- `git diff --check`: passed.

## Limitations

Evidence is limited to macOS, cache-only local execution and a small synthetic single-page-focused
corpus. The adapter is prose-only and does not establish table, formula, image, or layout fidelity.
There is no real-user corpus result, hosted OCR comparison, AutoDL comparison, general OCR quality
claim, approved production numeric threshold, production capability, runtime promotion, or release
authority. The provisional synthetic-protocol budgets above remain accepted only for regression
and planning.
