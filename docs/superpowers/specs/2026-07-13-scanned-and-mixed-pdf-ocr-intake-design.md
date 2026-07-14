# Scanned and Mixed PDF OCR Intake Design

Status: approved design amended for resumption planning. Phase 0 Tasks 1-4 and their review
remediation are complete; Tasks 4R, 5A, 5B, 5C, and 6 have not started.

Planning baseline: `337d9a42105a1a6769f3e0ae21bb28c59282da48`.

## Summary

MKE currently extracts page-addressed text from PDF text layers. Image-only pages and scan-dominant
pages can therefore produce no trustworthy Evidence. Mixed PDFs can also contain usable text-layer
pages alongside omitted scan-like pages.

This design adds an optional, local, cache-only-at-runtime OCR intake path for prose-heavy English
and Simplified Chinese PDFs. The goal is not OCR output by itself. The product outcome is that a
question blocked by a scanned page becomes answerable through the existing Search and Ask
contracts, with an exact portable page `mke.evidence_ref.v1`, without weakening Run, Publication,
provenance, resource, or authority boundaries.

The work starts with two bounded tracks:

1. an independently valuable owner-lifecycle and cancellation prerequisite;
2. a disposable provider, routing, dependency, and end-to-end viability spike.

No production provider or public OCR command is committed until the spike produces a valid-positive
result. A valid-negative result stops the runtime work without weakening the existing PDF path.

## Product Scope

### In scope

- image-only and scan-dominant pages in scanned and mixed PDFs;
- prose-heavy Simplified Chinese and English documents;
- deterministic page-level routing;
- one selected first-party local OCR profile behind a project-owned adapter contract;
- explicit model preparation and read-only readiness checks;
- cache-only normal ingest and proof execution;
- bounded PDF inspection, rendering, OCR, subprocess output, memory, time, and temporary storage;
- page-addressed Evidence, versioned OCR reports, and extractor fingerprints;
- CLI, Python application facade, and stdio MCP owner configuration;
- deterministic synthetic fixtures and an installed-wheel external-consumer proof;
- public documentation, error recovery, dependency, platform, model, and license evidence.

### Out of scope

- table cell structure, Markdown reconstruction, formulas, charts, seals, and layout hierarchy;
- claiming that OCR text preserves table, column, or visual reading structure;
- retrieval, chunking, dense, RRF, reranker, or answer-generation changes;
- HTTP service, multi-tenant operation, RBAC, review policy, freshness, or decision authority;
- request-time provider, model, cache, download, URL, token, or endpoint controls;
- implicit network access during ingest, doctor, proof, tests, or required CI;
- remote API fallback, AutoDL orchestration, or source upload;
- a generic OCR plugin framework;
- support claims for platforms that do not have a real runtime receipt and proof.

Every successful OCR report declares `content_fidelity="plain_text_only"`.

## Success and Kill Criteria

OCR accuracy metrics are necessary diagnostics but not sufficient product evidence.

The viability spike succeeds only when all of the following hold on the approved fixture profile:

- questions whose answer exists only on OCR-routed pages become answerable;
- Search and Ask return the exact expected PDF page EvidenceRef;
- all fixture pages receive the expected route;
- blank, decorative, ambiguous, malformed, low-quality, timed-out, or failed pages never enter an
  active Publication;
- prepared runtimes operate with a network canary proving no runtime network access;
- dependency resolution preserves supported MKE optional surfaces and required regression suites;
- model size, installation size, cold start, per-page time, peak RSS, temporary storage, and text
  volume remain inside a measured and documented local envelope;
- model code and weights have documented source, version, digest, and license status;
- an installed MKE wheel completes OCR ingest, Search, Ask, and portable EvidenceRef proof.

The production route is killed or deferred if any of the following hold:

- no local provider produces reliable answerability with exact page EvidenceRefs;
- any known ambiguous or bad page is silently activated as trustworthy Evidence;
- cache-only execution cannot be enforced after preparation;
- ordinary dependency resolution breaks an existing supported extra or required regression suite;
- the measured local resource envelope is unsuitable for the supported profile;
- documented external preprocessing is simpler and at least as useful as every local candidate.

No release is promised by the viability spike.

## Provider Selection

The initial comparison set is:

| Candidate | Role | Initial rationale |
|---|---|---|
| PP-OCRv6 medium | provisional leading candidate | The first capability is text recovery, and its text-oriented output is narrower than a document-parsing VLM contract. |
| Apple Vision text recognition | local platform baseline | It provides a Darwin-local baseline without defining the portable MKE contract. |
| PaddleOCR-VL 1.6 | layout-capable comparison | It may be useful for later document parsing, but it has a larger runtime and output surface than the first prose-only wedge. |

MinerU, DeepSeek-OCR, hosted APIs, and AutoDL are deferred. They may be reconsidered only if the
local candidates fail or a concrete consumer establishes a requirement that justifies their
runtime, license, GPU, egress, credential, or maintenance cost.

As of the planning baseline, `paddleocr==3.7.0`, `paddlepaddle==3.3.1`,
`PP-OCRv6_medium_det`, and `PP-OCRv6_medium_rec` form the PP-OCRv6 spike candidate. These values are
evaluation inputs, not a frozen production dependency.

Installing provider dependencies or acquiring model artifacts for the viability spike requires a
separate explicit operator authorization. Design approval does not grant network or download
authority.

The selected production profile receives an immutable versioned ID. If PP-OCRv6 medium wins, the
intended ID is `ppocrv6-medium-cpu-v1`. A different winner receives an equally specific ID.
`disabled` remains the default.

Changing model artifacts, render DPI, normalization, provider package, preprocessing, or quality
policy requires a new profile or fingerprint; an existing profile must never silently change.

## Architecture

```text
owner startup
  -> once-per-owner recovery
  -> optional OCR config and read-only readiness check
  -> application engine

OCR-enabled PDF ingest
  -> immutable source snapshot and digest
  -> bounded PDF inspect worker
  -> pure four-state page router
       -> text-layer accepted
       -> OCR required -> bounded render worker -> selected OCR child
       -> blank/nontext
       -> ambiguous/unsupported -> fail closed
  -> closed route/result/report validation
  -> candidate Evidence and manifest validation
  -> transactional report insert + Publication activation
  -> Search / Ask / portable EvidenceRef
```

The existing OCR-disabled text-layer path remains unchanged unless the owner explicitly selects an
OCR profile.

## Prerequisite: Owner Lifecycle and Cancellation

OCR adds long-running native and model work. The following existing lifecycle risks must be fixed
before a public OCR runtime is exposed:

- unfinished-Run recovery runs once at owner startup, not in every `SQLiteStore` construction;
- Run state transitions use compare-and-set semantics and append their Run event in the same
  transaction;
- an `INTERRUPTED`, cancelled, or stale Run cannot return to a validated or publishable state;
- individual request cancellation targets only that operation's process group;
- owner shutdown may broadcast cancellation, but request cancellation cannot kill sibling work;
- cancellation is checked after inspect, render, and OCR batches, before candidate persistence, and
  inside the final activation transaction;
- owner-wide admission allows one active OCR Run in v1 and a bounded queue or stable overload
  failure;
- reads such as Search, Ask, and Run inspection remain available within measured latency budgets
  while OCR work is active.

This prerequisite contains no OCR behavior and is independently useful reliability work. The
disposable viability spike may run in parallel because it creates no production Runs or
Publications.

## Immutable Source Boundary

The OCR-enabled application path must not hash one file instance and later extract another.

Before Run processing:

- open a regular PDF with no-follow and file-identity checks where supported;
- reject missing, empty, non-regular, symlinked, over-size, or unsupported input;
- copy the accepted bytes into a private immutable temporary snapshot;
- hash and process the same snapshot bytes;
- verify final byte count and file identity before accepting the snapshot;
- ensure cleanup on success, failure, timeout, cancellation, and owner shutdown.

The bounded PDF worker receives the snapshot. The OCR provider child receives only bounded rendered
page request files and a strict request manifest; it never receives the source PDF or an
operator-supplied path.

## PDF Inspection and Page Routing

All pages pass through one deterministic, versioned classifier. There is no early “any text” or
“any image” shortcut.

The PDF worker returns bounded facts for each page:

- normalized `get_text("text", sort=True)` output and text diagnostics;
- displayed raster image facts from `Page.get_image_info()`;
- page geometry and clipped union coverage for displayed image rectangles;
- non-trivial vector, shading, and painted-content signals;
- encryption, malformed-page, timeout, and resource-limit status.

The router produces exactly one state per page:

1. `text_layer_accepted`: the text layer passes calibrated trust checks;
2. `ocr_required`: the page is scan-dominant and contains supported raster content;
3. `blank_nontext`: the page has no meaningful text or document content;
4. `ambiguous_unsupported`: hidden, garbage, sparse, vectorized, malformed, or unsupported content
   cannot be classified safely.

Each decision includes stable reason tokens and bounded metrics for the intake report. Route sets
must be pairwise disjoint and their union must equal every page in the PDF.

The viability spike freezes routing thresholds only after testing text-layer, image-only, mixed,
decorative-image, blank, sparse-text, garbage-layer, hidden-text, vectorized-text, overlapping-image,
off-page-image, rotated, malformed, and over-limit cases. If the approved corpus cannot be routed
without silent false trust, the production route stops.

## Rendering and OCR Execution

PDF inspection/rendering and OCR are separate project-owned child boundaries.

Before allocating a pixmap, validate page dimensions, DPI, pixel count, encoded page size, total OCR
pages, total PDF pages, remaining Run time, and temporary-storage budget. After rendering, validate
the actual dimensions and encoded bytes again.

OCR pages are processed in deterministic serial batches in v1. Each batch preserves Source and page
identity and uses:

- fixed owner-selected command construction;
- private request/result files;
- strict JSON schemas and unknown-key rejection;
- hard request, result, stdout, and stderr bounds before parsing;
- an allowlisted child environment and isolated HOME/temp directories;
- a verified read-only model snapshot;
- process-group timeout, termination, grace, kill, parent wait, reader-thread, and descendant cleanup;
- cancellation checks before and after every batch.

Provider output is converted immediately into project-owned values. Provider library objects do not
enter domain, application, persistence, CLI, or MCP layers.

Geometry is intentionally omitted from v1 because no current consumer uses it. A later layout
contract must separately define coordinates, rotation, clipping, reading order, and polygon
validity.

## Project-Owned Contracts

### OCR result protocol

The child result is a closed `mke.pdf_ocr_result.v1` JSON object:

- top-level fields: `schema`, `status`, `provider`, `profile`, and `pages`;
- exact provider and immutable profile identity;
- exactly one result for each requested page;
- no missing, duplicate, extra, reordered, zero, or negative page number;
- page fields: `page_number`, ordered `lines`, `normalized_text`, and bounded aggregate diagnostics;
- line fields: bounded non-empty `text` and finite `score` in `[0, 1]`;
- valid UTF-8, finite numbers, and no unknown fields;
- no paths, URLs, tokens, tracebacks, environment values, raw provider objects, or unbounded logs.

Per-page and per-Run result byte and text bounds are frozen from Phase 0 measurements. They must fit
inside existing active Evidence and stdio Search/Ask budgets.

### OCR intake report

The existing `PdfIntakeReport` and public `intake_report` key keep their current text-layer meaning.
OCR adds `PdfOcrIntakeReport`, schema `mke.pdf_ocr_intake_report.v1`, and public key
`pdf_ocr_intake_report` across CLI JSON, MCP ingest, and Run inspection.

A successful report is closed and includes:

- provider, profile, extractor fingerprint, model fingerprint, and receipt fingerprint;
- `content_fidelity: "plain_text_only"`;
- total pages and exact page tuples for text-layer, OCR-required, OCR-completed, and blank routes;
- zero ambiguous or failed pages;
- OCR character totals and per-page character counts;
- bounded confidence diagnostics that do not independently authorize Publication;
- render profile and bounded duration, output, temporary-storage, and resource totals;
- model source `cache`.

The report validator proves:

- route sets are pairwise disjoint and cover `1..total_pages` exactly;
- every accepted text-layer or OCR page has exactly one page Evidence locator;
- blank pages have no Evidence;
- the manifest contains no duplicate page locator;
- counts and text totals equal the candidate Evidence and manifest;
- ambiguous, failed, missing, or extra pages prohibit a success report.

Failed Run inspection may expose a separate bounded failure report or sanitized diagnostic ID. It
cannot be accepted as a successful OCR intake report.

### Provenance fingerprint

The extractor fingerprint uses canonical serialization and SHA-256 over:

- text extractor identity;
- router version and frozen thresholds;
- render profile;
- OCR provider and immutable profile ID;
- relevant library versions;
- model artifact identities and tree digests;
- normalization version;
- project-owned result and report schema versions.

A readable prefix alone is never sufficient for validation.

### Phase 0 evaluation manifest identity amendment

Phase 0 must not disguise an OCR composite identity as `builtin-pdf-text-v1` or
`pymupdf-text-v1`. The evaluation runner uses a dedicated fingerprint with the exact form
`pdf-ocr-eval-v1:<64 lowercase hex SHA-256>`. This fingerprint is evaluation-only and does not
change the default PDF ingest path.

The digest input is a closed JSON object. Its exact top-level keys are `schema`, `protocol`,
`fixtures`, `router`, `render`, `provider`, `model`, `package`, and `normalization`; `schema` is
exactly `mke.pdf_ocr_extractor_identity.v1`. Nested keys and ordering are exact:

- `protocol`: `id`, `sha256`;
- `fixtures`: sorted by `document_id`, with each item containing `document_id`, `source_bytes`,
  `source_sha256`;
- `router`: `implementation_sha256`, `policy`; `policy` contains every current
  `EvaluationRoutingPolicy` field: `accepted_text_min_chars`,
  `accepted_text_max_replacement_ratio`, `ocr_text_max_chars`, `ocr_min_image_coverage`,
  `render_dpi`, `max_pages`, `max_page_pixels`, `max_total_rendered_pixels`,
  `max_rendered_file_bytes`, and `max_total_rendered_bytes`;
- `accepted_text_max_replacement_ratio` and `ocr_min_image_coverage` are exact rational objects
  with only `numerator` and `denominator`; every other policy value is a positive integer;
- `render`: `profile`, `dpi`, `pages`; pages are sorted by (`document_id`, `page_number`) and each
  contains `document_id`, `page_number`, `image_bytes`, `image_sha256`;
- `provider`: `id`, `profile`;
- `model`: `receipt_sha256`, `tree_sha256`;
- `package`: `receipt_sha256`, `installed_packages_sha256`, `mke_wheel_sha256`;
- `normalization`: `implementation_sha256`, `profile`.

All SHA-256 values are exactly 64 lowercase hexadecimal characters. Bytes, pages, DPI, integer
limits, and rational numerators and denominators are non-boolean positive integers. Lists have no
duplicate identity or sort key. Missing or extra keys, wrong types, invalid ordering, duplicates,
non-finite values, and boolean-as-integer values fail closed.

The digest bytes are exactly:

```python
json.dumps(
    payload,
    ensure_ascii=True,
    sort_keys=True,
    separators=(",", ":"),
    allow_nan=False,
).encode("utf-8")
```

No newline is appended. The fingerprint is `pdf-ocr-eval-v1:` plus the lowercase SHA-256 of those
bytes. The scorecard may use its existing stable JSON formatting; only the exact compact bytes
above authorize the fingerprint digest.

An OCR evaluation `RunManifest` uses exactly these required stages:

- `pdf_ocr_extraction`;
- `candidate_evidence`.

A text-layer-only Publication continues to use `pymupdf-text-v1` and the existing PDF stages. If
any page in a document follows the OCR route, that evaluation Publication uses the composite OCR
fingerprint and OCR stages for the whole document.

The Task 5A domain validator recognizes only the exact versioned prefix, exactly 64 lowercase
hexadecimal digest characters, the exact OCR stage set, and page locators. It rejects a prefix
without a digest, wrong-length or uppercase digests, unknown versions, duplicate required stages,
an OCR fingerprint paired with text stages, and a text fingerprint paired with OCR stages.
Existing PDF and video fingerprints remain compatible. This validator sees only the compact
manifest and does not validate the structured payload.

The scorecard persists the complete structured extractor identity. The Task 5B disposable runner
is its only current producer and authority. Before it calls `persist_validated_candidate`, the
runner validates the closed payload, recomputes its digest, and requires exact equality with the
`RunManifest` fingerprint. The `RunManifest` stores only the compact fingerprint, not the large
structured payload; SQLite and domain validation do not persist or validate that payload.

`MKEEngine.ingest_file`, CLI, and MCP have no input for selecting or submitting this evaluation
fingerprint or manifest, and Task 5A adds none. The normal PDF application path continues to use
`pymupdf-text-v1`. This contract adds no public OCR input, production OCR flag, default PDF
behavior, database migration, dependency, or production OCR authorization. Its architecture
decision is recorded in `docs/decisions/0010-pdf-ocr-evaluation-manifest-fingerprint.md`, initially
as Proposed pending implementation.

## Publication Atomicity

OCR uses the stronger report pattern already established by first-party transcription:

1. persist candidate Evidence and manifest;
2. validate route, result, report, locator, and fingerprint invariants;
3. compare-and-set the Run into the expected pre-publication state;
4. insert the successful OCR report and activate the Publication in one SQLite transaction;
5. append the matching Run event in that transaction;
6. expose the report only after commit.

The production OCR report gate described in this section belongs to future production Tasks 7-9
and is not implemented by Phase 0. Phase 0 disposable evaluation instead uses runner/scorecard
coherence before candidate persistence; it does not add an OCR report to SQLite activation.
Future production activation rejects an OCR fingerprint without a complete successful OCR report.
Any exception, malformed result, resource limit, cancellation, timeout, readiness failure, storage
failure, or unsupported page leaves the previous active Publication and its Search/Ask behavior
unchanged.

## Runtime Profile and Model Lifecycle

OCR is an optional dependency extra. Core MKE remains model-free, and OCR packages never enter core
imports when the profile is disabled.

The owner workflow is:

```text
mke ocr prepare --profile <selected-profile-v1> --check
mke ocr prepare --profile <selected-profile-v1> --allow-model-download
mke ocr doctor --profile <selected-profile-v1> --json
```

`prepare --check` is read-only and reports profile, artifact source, code/model license, expected
download bytes, required disk space, selected cache, and platform eligibility.

Only `prepare --allow-model-download` may use the network. It downloads into staging, validates an
allowlisted content-addressed manifest, rejects traversal, links, devices, excessive file count or
expanded bytes, verifies artifact and tree digests, fsyncs as required, and atomically installs an
immutable snapshot.

The shared owner-only cache resolver uses `--ocr-cache`, then `MKE_OCR_CACHE`, then a documented
platform default. Cache location is never accepted from an ingest or MCP tool request.

Snapshots are keyed by immutable profile and artifact digest and coexist side by side. A new
prepare never overwrites a working snapshot. A versioned receipt binds:

- MKE version;
- profile ID;
- manifest schema;
- provider package versions;
- exact model identities and artifact/tree digests;
- preparation time and supported runtime profile.

`doctor` is read-only, never downloads, and distinguishes dependency missing, unsupported
platform, profile mismatch, cache missing, unreadable cache, incomplete snapshot, and digest
mismatch. It fails closed unless the current OS, architecture, Python, provider packages, profile,
and model receipt have a real allowlisted proof.

A read-only inventory lists compatible and incompatible snapshots and bounded disk usage without
deleting anything. Upgrade is prepare new profile, doctor new profile, then restart the owner on the
new profile. Rollback restarts the old package/profile against its retained snapshot. Deletion is an
explicit human-authorized action.

## Public Surfaces

### CLI

The existing command shape remains `mke ingest <file>`; no `ingest file` subcommand is introduced.
After a provider wins Phase 0, the public installed-wheel quickstart uses a concrete profile and a
committed synthetic mixed-PDF fixture:

```text
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install 'multimodal-knowledge-engine[ocr]'
mke ocr prepare --profile <selected-profile-v1> --check
mke ocr prepare --profile <selected-profile-v1> --allow-model-download
mke ocr doctor --profile <selected-profile-v1> --json
mke --db ./ocr-proof.sqlite --pdf-ocr-profile <selected-profile-v1> \
  ingest ./synthetic-mixed.pdf --json
mke --db ./ocr-proof.sqlite search <fixture-query>
mke --db ./ocr-proof.sqlite ask <fixture-question>
mke proof ocr-run --profile <selected-profile-v1> --json
```

The published quickstart replaces the design metavariables with exact fixture values. `mke proof ocr-run`
validates readiness, OCR routing, ingest, Search, Ask, and the exact expected page EvidenceRef. An
ingest exit code alone is not product proof.

Human-mode preparation sends bounded stage/progress messages to stderr. JSON modes emit exactly one
final JSON object on stdout.

### Python

The existing Python application facade remains supported. A typed `PdfOcrConfig` is injected only
through `RuntimeConfig` or engine construction. `ingest_pdf(path)` keeps its current request
signature. Provider, model, cache, download, URL, endpoint, and token values are not request
parameters. Provider-library classes and adapter DTOs are not exported from the top-level package.

### stdio MCP

The server owner selects the OCR profile at startup. OCR-enabled startup runs the same read-only
doctor and exits with a stable public failure when the profile is not ready. Disabled startup does
not import or require OCR dependencies.

`ingest_file` keeps its existing request schema. Its description states that scanned-PDF support is
owner-controlled and cannot be changed by the request.

A new read-only `get_runtime_capabilities_v1` tool returns a closed
`mke.runtime_capabilities.v1` object containing:

- OCR `enabled` and `ready`;
- immutable profile ID or `null` when disabled;
- `content_fidelity: "plain_text_only"` when enabled;
- public PDF/OCR page, byte, pixel, text, and time limits;
- admission capacity and bounded `available`, `busy`, or `disabled` state;
- no paths, cache locations, provider URLs, tokens, download controls, or mutation fields.

An Agent can discover capability and bounded overload state but cannot acquire new authority.

## Stable Public Failures

OCR preserves the existing public error payload shape: stable `problem`, exact allowlisted
`cause`, machine `next_step`, optional `run_id`, and
`active_publication_impact="unchanged"`. No new error payload field is required. Each `next_step`
maps to a stable documentation anchor and a copy/paste recovery command.

| `problem` | Exact allowlisted `cause` | `next_step` |
|---|---|---|
| `pdf_ocr_runtime_unavailable` | `PDF OCR optional dependency is not installed` | `install_pdf_ocr_runtime` |
| `pdf_ocr_model_not_ready` | `PDF OCR profile is not prepared` | `run_pdf_ocr_prepare` |
| `pdf_ocr_input_limit_exceeded` | `PDF OCR input exceeds configured limits` | `reduce_pdf_ocr_input` |
| `pdf_ocr_timeout` | `PDF OCR operation timed out` | `retry_smaller_pdf` |
| `pdf_ocr_process_failed` | `PDF OCR process failed` | `inspect_pdf_ocr_run` |
| `pdf_ocr_output_limit_exceeded` | `PDF OCR output exceeds configured limits` | `reduce_pdf_ocr_input` |
| `pdf_ocr_result_invalid` | `PDF OCR result schema is invalid` | `report_pdf_ocr_runtime_issue` |
| `pdf_ocr_result_incomplete` | `PDF OCR result page inventory is incomplete` | `report_pdf_ocr_runtime_issue` |
| `pdf_ocr_result_empty` | `PDF OCR produced no accepted text` | `improve_pdf_scan` |
| `pdf_ocr_quality_rejected` | `PDF OCR output failed the configured quality gate` | `improve_or_preprocess_pdf` |
| `pdf_ocr_unsupported_page` | `PDF page is not supported by the OCR profile` | `preprocess_pdf_page` |
| `pdf_ocr_overloaded` | `PDF OCR capacity is busy` | `retry_pdf_ocr_later` |
| `pdf_ocr_cancelled` | `PDF OCR operation was cancelled` | `retry_when_owner_ready` |

The overload recovery contract documents one bounded backoff and retry. It must not recommend
unbounded polling. Process failures include a Run ID when one exists; Run inspection returns only a
bounded sanitized diagnostic ID or failure report, never raw provider logs or paths.

## Resource Bounds

All authoritative limits live in typed application configuration shared by CLI, Python, and MCP.
An MCP-only file-size check is insufficient.

Phase 0 must measure and then freeze at least:

- total PDF bytes and zero-byte rejection;
- total PDF pages and total OCR pages;
- page dimensions, render DPI, pixels, and encoded image bytes;
- per-page and per-Run OCR text bytes;
- result, stdout, and stderr bytes;
- routing, rendering, batch, and total Run time;
- temporary-storage bytes;
- owner admission capacity and queue bound;
- peak RSS on the supported real-model profile;
- active-library text budget compatibility with Search/Ask and CJK active scan.

Limits may be lowered by owner configuration but not raised beyond an approved profile maximum.
Every pre-allocation limit is checked before allocating the affected object and validated again
after the operation.

## Security, Privacy, and Supply Chain

- Source PDF bytes and rendered pages stay local.
- Runtime ingest has no implicit network access.
- The provider child receives no source PDF or operator path.
- Request-visible controls cannot select provider, model, cache, network, URL, or token.
- Private temporary roots reject traversal, symlinks, absolute paths, and unexpected files.
- Request/result/subprocess data are bounded before parsing.
- Public errors redact paths, environment values, upstream exception text, tracebacks, and logs.
- Model code and weights have separate documented source, version, digest, and license records.
- Model preparation is explicit, content-addressed, safely extracted, atomic, and resumable without
  exposing a partial snapshot as ready.
- Required CI and normal proofs do not download model weights.
- Tests include a network canary, malicious archive cases, source replacement, cancellation,
  timeout, and descendant cleanup.

## Dependency and Platform Policy

The provider dependency is accepted only after ordinary resolver evidence. `uv.lock` is not enough
because wheel consumers use standard pip resolution. Necessary compatibility constraints belong in
`pyproject.toml`.

One built MKE wheel is tested on Python 3.12 and 3.13 with:

- `[ocr]`;
- `[ocr,transcription]`;
- `[ocr,embedding]`;
- `[ocr,embedding,transcription]`.

Every environment runs `pip check`, import smoke, relevant doctor commands, and focused runtime
proof without model downloads. Existing retrieval, transcription, embedding, proof, demo, build,
lint, and type-check gates remain required.

Package-wheel availability is not a support claim. Public setup copy names only platforms that have
a real provider/model receipt and end-to-end proof. Other platforms are explicitly unverified.

## Evaluation and Verification

### Fixtures

Use public-safe deterministic generated fixtures with committed generator source and ground truth:

- English image-only PDF;
- Simplified Chinese image-only PDF;
- mixed text-layer and scanned-page PDF;
- blank and decorative-image pages;
- sparse and garbage text layers;
- hidden, vectorized, rotated, overlapping, and off-page content;
- malformed, encrypted, zero-byte, oversized, excessive-page, and excessive-pixel inputs;
- quality-rejected and unsupported-page fixtures.

An operator-local representative corpus may supplement the committed fixtures only when separately
authorized. It is never committed or required for CI.

### Provider scorecard

Each candidate is measured on the same corpus for:

- CER/WER and line/page order diagnostics;
- page-route accuracy;
- downstream Search/Ask answerability and exact EvidenceRef page;
- cold start and per-page elapsed time;
- peak RSS, temporary storage, package size, and model size;
- preparation and cache-only behavior;
- dependency compatibility;
- license and artifact provenance;
- preparation, doctor, cache, upgrade, rollback, and error-recovery UX.

Numeric acceptance thresholds are recorded only after real measurements. Vendor marketing numbers
are not used as project evidence.

### Required test matrix

- owner startup recovery, CAS transitions, stale transitions, and no Run resurrection;
- concurrent ingest/read, sibling cancellation isolation, owner shutdown, and admission overload;
- source symlink, replacement, truncation, identity, digest, and cleanup;
- bounded PDF inspect and render crash, timeout, malformed, geometry, and allocation cases;
- four-state router branch and reason-token coverage;
- cache-miss-before-import and zero-network provider behavior;
- strict OCR request/result schema, UTF-8, identity, page inventory, and quality failures;
- route/report/Evidence/manifest union, disjointness, locator, count, and text-total invariants;
- cancellation and storage failures before and inside activation with old Publication unchanged;
- safe model preparation, malicious archive, digest, idempotence, and partial-recovery cases;
- Python 3.12/3.13 ordinary-pip extra matrix from the same MKE wheel;
- installed-wheel CLI, Python, and stdio MCP proof;
- OCR-only question -> Search/Ask -> exact active page EvidenceRef;
- full existing project regression and release-presentation audit.

## Developer Experience Gate

The public OCR flag cannot merge before all of these are true:

- one immutable selected profile is used by prepare, doctor, CLI, Python, MCP, reports, and
  fingerprints;
- a committed synthetic mixed PDF makes the documented quickstart copy/pasteable;
- `mke proof ocr-run --json` proves OCR routing and exact page EvidenceRef from an installed wheel;
- public flag, README/README_CN, Getting Started, OCR how-to, CLI reference, MCP reference, error
  recovery, platform statement, license notice, and upgrade/rollback guidance land together;
- preparation preflight reports model source/license, bytes, disk, and network authority before a
  download;
- doctor and inventory are read-only and produce bounded machine-readable output;
- MCP startup and capability discovery are useful without adding request authority;
- every failure maps to an executable recovery token and stable reference entry;
- the report declares `plain_text_only` consistently across CLI, MCP, Python, and Run inspection;
- unsupported platforms and document structures are visible before first ingest.

## Delivery Sequence

1. Land and review this design specification.
2. Write a separate implementation plan that partitions the prerequisite, viability spike,
   internal contract, public exposure, and proof closure.
3. Implement the owner lifecycle/CAS/cancellation prerequisite.
4. In parallel where safe, run the disposable provider/routing/dependency vertical slice with no
   production persistence contract.
5. Stop with a valid-negative report if no candidate passes.
6. If a candidate passes, freeze provider profile, routing thresholds, resource limits, quality
   policy, dependency constraints, and license evidence.
7. Land internal OCR contracts, router, source boundary, migration, fake-provider tests, and atomic
   activation without a public flag.
8. Land the selected provider, cache lifecycle, owner configuration, public CLI/Python/MCP surfaces,
   and complete documentation together.
9. Land real-model proof, packaging matrix, dedicated CI contract checks where needed, and final
   documentation/release audit.

Each implementation PR must remain independently reviewable and preserve the existing OCR-disabled
behavior.

## Rollback and Release

Runtime rollback disables the owner OCR profile and preserves existing text-layer behavior. Code
rollback stops reading or writing the additive OCR report surface before any local schema removal.
No migration mutates existing Evidence or Publications. Model cache snapshots are never deleted
automatically.

After public runtime and proof closure merge and post-merge checks pass, the project may evaluate a
`v0.1.2` release. The exact patch sequence remains flexible. A failed viability spike does not force
a release or a replacement feature.

## References

- PaddleOCR general OCR pipeline:
  <https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html>
- PaddleOCR package metadata:
  <https://pypi.org/project/paddleocr/>
- PaddlePaddle package metadata:
  <https://pypi.org/project/paddlepaddle/>
- PP-OCRv6:
  <https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html>
- PaddleOCR and PaddleX compatibility:
  <https://www.paddleocr.ai/main/en/version3.x/paddleocr_and_paddlex.html>
- PaddleOCR-VL on Apple Silicon:
  <https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/PaddleOCR-VL-Apple-Silicon.html>
- PyMuPDF Page API:
  <https://pymupdf.readthedocs.io/en/latest/page.html>
- MinerU repository and license:
  <https://github.com/opendatalab/MinerU>
- DeepSeek-OCR repository:
  <https://github.com/deepseek-ai/DeepSeek-OCR>
- Apple Vision `RecognizeTextRequest`:
  <https://developer.apple.com/documentation/vision/recognizetextrequest>
