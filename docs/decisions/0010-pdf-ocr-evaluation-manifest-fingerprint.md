# ADR-0010: PDF OCR Evaluation Manifest Fingerprint

- Status: Accepted
- Date: 2026-07-14

## Context

The Phase 0 OCR runner must publish disposable Evidence through the current Run and Publication
contracts while preserving the complete evaluation identity. Existing PDF fingerprints identify
the built-in and PyMuPDF text-layer extractors; using either value for OCR-routed output would hide
the router, render, provider, model, package, wheel, and normalization authority that produced the
candidate Evidence.

## Decision

Introduce an evaluation-only fingerprint with the exact form
`pdf-ocr-eval-v1:<64 lowercase hex SHA-256>`. Its digest payload is a closed object whose exact
top-level keys are `schema`, `protocol`, `fixtures`, `router`, `render`, `provider`, `model`,
`package`, and `normalization`. `schema` is exactly `mke.pdf_ocr_extractor_identity.v1`.

The nested contract is exact:

- `protocol` has `id` and `sha256`;
- `fixtures` is sorted by `document_id`; each item has `document_id`, `source_bytes`, and
  `source_sha256`;
- `router` has `implementation_sha256` and `policy`; `policy` has every current
  `EvaluationRoutingPolicy` field: `accepted_text_min_chars`,
  `accepted_text_max_replacement_ratio`, `ocr_text_max_chars`, `ocr_min_image_coverage`,
  `render_dpi`, `max_pages`, `max_page_pixels`, `max_total_rendered_pixels`,
  `max_rendered_file_bytes`, and `max_total_rendered_bytes`;
- the two ratio fields are exact rational objects with only `numerator` and `denominator`; all
  other policy values are positive integers;
- `render` has `profile`, `dpi`, and `pages`; pages are sorted by
  (`document_id`, `page_number`) and each has `document_id`, `page_number`, `image_bytes`, and
  `image_sha256`;
- `provider` has `id` and `profile`;
- `model` has `receipt_sha256` and `tree_sha256`;
- `package` has `receipt_sha256`, `installed_packages_sha256`, and `mke_wheel_sha256`;
- `normalization` has `implementation_sha256` and `profile`.

Every SHA-256 field is exactly 64 lowercase hexadecimal characters. Byte counts, page numbers,
DPI, integer limits, and rational numerators and denominators are non-boolean positive integers.
Lists contain no duplicate identity or sort key. Missing keys, extra keys, invalid types, invalid
ordering, duplicates, non-finite values, and boolean-as-integer values fail closed.

Fingerprint bytes are exactly:

```python
json.dumps(
    payload,
    ensure_ascii=True,
    sort_keys=True,
    separators=(",", ":"),
    allow_nan=False,
).encode("utf-8")
```

No newline is appended. The fingerprint is `pdf-ocr-eval-v1:` followed by the lowercase SHA-256
of those bytes. The scorecard file may retain its existing stable JSON formatting, but fingerprint
hashing uses only these compact bytes.

OCR evaluation Publications use exactly `pdf_ocr_extraction` and `candidate_evidence` stages. A
text-layer-only Publication continues to use `pymupdf-text-v1` and the existing PDF stages; any
OCR-routed page makes the evaluation Publication use the OCR fingerprint and OCR stages.

The Task 5A domain validator accepts only the exact version, lowercase 64-hex digest, exact OCR
stage set, and page locators. Prefix-only, wrong-length, uppercase, unknown-version,
fingerprint/stage mismatch, and duplicate required stages fail closed. The domain validator does
not receive or validate the structured payload. The Task 5B disposable evaluation runner is the
only current producer and authority for that payload: it validates the closed schema and verifies
the digest against the compact `RunManifest` fingerprint before calling
`persist_validated_candidate`.

## Scope And Consequences

This decision is limited to the Phase 0 evaluation runner. `MKEEngine.ingest_file`, CLI, and MCP
have no input for selecting or submitting an OCR evaluation fingerprint or `RunManifest`, and
Task 5A adds none. It adds no production OCR flag, runtime default, SQLite migration, dependency,
or production OCR authority. Existing PDF and video fingerprints and behavior remain compatible;
the normal PDF application path continues to produce `pymupdf-text-v1`. Task 5A implemented only
the compact domain fingerprint, exact-stage, duplicate-stage, and page-locator checks. Its focused
domain, application, CLI, and MCP suite passed with `121 passed, 5 warnings`. Structured extractor
identity validation and producer authority remain assigned to Task 5B.

SQLite and the domain validate only the compact manifest contract. They do not persist or validate
the structured extractor identity. The future production OCR report-and-activation gate belongs to
production Tasks 7-9. Phase 0 instead relies on disposable runner and scorecard coherence, which
must not be described as a production OCR capability or successful production OCR report gate.

The package identity leaf is supplied only by the refreshed Task 4R authority chain. Compatibility
receipts are self-consistent across their own MKE wheel filename, parsed safe version, digest,
candidate inventories, successful-cell installed versions, and provider runtime. They are not
implicitly bound to the version of the checkout that validates them. This keeps the retained 0.1.1
receipt readable as historical evidence while requiring Task 5B to consume the separately reviewed
0.1.2 receipt and installed-wheel startup evidence. Task 4R copies retained wheelhouses into a
call-owned root and replaces only the MKE wheel in that copy; it never mutates retained evidence.
The existing exact committed-receipt SHA gate remains unchanged while Task 4R-A generalizes the
harness. After Task 4R-B generates canonical 0.1.2 package and startup receipts, it computes the
package receipt SHA from those canonical bytes and mechanically updates that one frozen test
literal before running the complete suite. This regression freeze binds receipt bytes, not the
source commit; the receipt schemas continue to bind wheel, package, model, and runtime identities
without a `source_commit` field.
