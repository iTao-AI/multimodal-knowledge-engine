# PDF OCR Phase 0 Viability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Status: in progress. Tasks 1-3 and their review remediation are complete. Task 4 Steps 1-6 are
complete as a bounded compatibility checkpoint. The pinned model roots were prepared and real
startup evidence was recorded. A bounded Task 4 amendment now accepts only the observed pinned
PaddleOCR-VL direct-top-level prose envelope and binds startup evidence to the package, model,
protocol, and vendor-artifact identities. Targeted authority re-review accepted the amendment at
`040cb6cea2439f5f9d46b09862b17fa1fee59e39`. The branch then reconciled MKE 0.1.2 through merge
commit `804b9205c35b657ab3aba51faf4cdc40ab0e4057`, preserving the reviewed Task 4 commits rather than
rewriting their provenance. Resumption now requires Task 4R, Task 5A, Task 5B, and Task 5C in that
order. Targeted authority re-review accepted the resumption plan at
`3673c8373da6973b0961f789204be14adce3d4dd`. Task 4R-A is complete and its targeted authority
re-review accepted implementation commit `3b029a47c69f32d63e9cae688196e205d96f8af7`. Task 4R-B has
satisfied its prerequisite review gate and is cleared for a separate dispatch, but has not started.
Task 4R as a whole remains incomplete; Task 5A, Task 5B, Task 5C, and Task 6 have not started.

**Goal:** Produce reproducible valid-positive or valid-negative evidence for local scanned/mixed-PDF OCR before adding a production runtime contract.

**Architecture:** Evaluation-only modules generate and validate a public-safe corpus, classify every page with a pure four-state router, invoke isolated provider candidates through one strict child protocol, and persist disposable Evidence through current SQLite/Publication contracts. A wheel-installed external consumer then verifies Search, Ask, and exact page `mke.evidence_ref.v1`; the final scorecard selects no production provider unless all hard gates pass.

**Tech Stack:** Python 3.12/3.13, PyMuPDF, SQLite, stdio MCP, Swift Vision baseline on Darwin, isolated PaddleOCR/PaddleOCR-VL candidate environments, pytest, Ruff, Pyright.

## Global Constraints

- Do not modify production PDF ingest, domain DTOs, SQLite schema, public CLI/MCP schemas, retrieval, chunking, ranking, or active runtime defaults.
- Do not add an `[ocr]` production extra, provider import, public OCR flag, or model cache contract in this phase.
- Provider packages run only in isolated candidate environments and never become core imports.
- Installing packages or downloading models requires separate explicit operator authorization; absent authorization, complete Tasks 1-3 and stop before Task 4 external actions.
- Required CI is model-free, network-free, and uses fake child results. Real-provider proof is opt-in and records the exact environment.
- Compare PP-OCRv6 medium, Apple Vision, and PaddleOCR-VL 1.6 on the same approved pages. No candidate is preselected.
- Use committed public-safe synthetic fixtures and ground truth. Operator-local documents are optional, separately authorized, never committed, and never required for a decision.
- Treat vendor metrics as background only. Repository artifacts record only observed measurements.
- A provider that fails dependency, routing, quality, cache-only, license, or exact EvidenceRef gates cannot win on speed or popularity.
- The output may be `no_go`; a valid-negative result completes this plan without creating production contracts.

---

## File Map

| File | Responsibility |
|---|---|
| `src/mke/evaluation/pdf_ocr_protocol.py` | Closed corpus, provider-result, measurement, and scorecard DTOs/validators. |
| `src/mke/evaluation/pdf_ocr_router.py` | Bounded PyMuPDF inspection, rectangle union, four-state routing, and rendering. |
| `src/mke/evaluation/pdf_ocr_provider.py` | Fixed child request/result protocol and bounded command execution. |
| `src/mke/evaluation/pdf_ocr_runner.py` | Candidate evaluation, disposable Publication, Search/Ask/EvidenceRef proof, and scorecard. |
| `src/mke/evaluation/pdf_ocr_ppocrv6.py` | Lazy PP-OCRv6 candidate child. |
| `src/mke/evaluation/pdf_ocr_paddle_vl.py` | Lazy PaddleOCR-VL candidate child. |
| `scripts/pdf_ocr_apple_vision.swift` | Darwin Vision candidate child. |
| `scripts/generate_pdf_ocr_phase0_fixtures.py` | Deterministic public-safe fixture generator. |
| `scripts/pdf_ocr_candidate_compatibility.py` | Wheel + ordinary-pip candidate resolver/install matrix. |
| `scripts/pdf_ocr_phase0_consumer.py` | External stdio MCP consumer proof. |
| `tests/fixtures/pdf-ocr-phase0-v1/` | Generated PDFs, `protocol.json`, and ground truth. |
| `tests/evaluation/test_pdf_ocr_protocol.py` | Closed schema, identity, and fixture integrity. |
| `tests/evaluation/test_pdf_ocr_router.py` | All route branches, geometry, rendering, and limits. |
| `tests/evaluation/test_pdf_ocr_provider.py` | Child schema, bounds, redaction, and fake providers. |
| `tests/evaluation/test_pdf_ocr_runner.py` | Hard gates, valid-negative behavior, and product proof. |
| `tests/scripts/test_pdf_ocr_candidate_compatibility.py` | Command construction, isolation, and exact aggregate receipt. |
| `tests/scripts/test_pdf_ocr_phase0_consumer.py` | External consumer contract and failure cases. |
| `benchmarks/ocr/model-artifacts.json` | Immutable pinned model inventory, per-file identity, bytes, and tree receipt. |
| `benchmarks/ocr/provider-startup.json` | Cache-only startup, network canary, and real PaddleOCR-VL artifact-schema evidence. |
| `benchmarks/ocr/phase0-scorecard.json` | Public measurement/decision artifact generated only from a real authorized run. |
| `docs/decisions/0010-pdf-ocr-evaluation-manifest-fingerprint.md` | Proposed evaluation-only OCR fingerprint contract pending Task 5A implementation. |
| `docs/superpowers/reviews/2026-07-14-pdf-ocr-phase0-resumption-plan-review.md` | Main reconciliation and resumption-plan review checkpoint. |
| `docs/superpowers/reviews/2026-07-13-pdf-ocr-phase0-decision.md` | Public-neutral GO/NO-GO rationale and limits of the evidence. |

## Interfaces Frozen by This Plan

```python
PageRoute = Literal[
    "text_layer_accepted",
    "ocr_required",
    "blank_nontext",
    "ambiguous_unsupported",
]

@dataclass(frozen=True)
class PageInspection:
    page_number: int
    normalized_text: str
    text_chars: int
    replacement_ratio: float
    hidden_text_present: bool
    displayed_image_coverage: float
    drawing_count: int
    width_points: float
    height_points: float

@dataclass(frozen=True)
class PageDecision:
    page_number: int
    route: PageRoute
    reasons: tuple[str, ...]
    inspection: PageInspection

@dataclass(frozen=True)
class OcrEvalLine:
    text: str
    confidence: float | None
    box: tuple[float, float, float, float]

@dataclass(frozen=True)
class OcrEvalPageResult:
    schema: Literal["mke.pdf_ocr_eval_result.v1"]
    provider: str
    profile: str
    page_number: int
    lines: tuple[OcrEvalLine, ...]
    normalized_text: str
    duration_ms: int

class OcrEvaluationCandidate(Protocol):
    provider: str
    profile: str
    def recognize(self, image_path: Path, page_number: int) -> OcrEvalPageResult: ...
```

The provider child accepts fixed `--input`, `--output`, `--page-number`, and provider-specific local model-directory arguments. It writes one result file and emits no result JSON on stdout.

## Plan Dependencies and Parallel Boundary

- Complete the owner-lifecycle plan before accepting this plan as a whole.
- Tasks 1-2 here may run in parallel with owner-lifecycle Tasks 1-2 because they are pure
  evaluation code and fixtures.
- Task 3 here depends on owner-lifecycle Task 3's operation-scoped `ActiveProcessController`.
- Task 4 is historical compatibility evidence. After the MKE 0.1.2 reconciliation, Tasks 4R,
  5A, 5B, 5C, and 6 are sequential and require their explicit authority checkpoints.
- A valid-positive Phase 0 result returns to planning. It does not unlock production Tasks 7-9 from
  the design spec automatically; those require a new reviewed production plan.

Every behavior change follows RED then minimal GREEN. Tasks 4R, 5A, 5B, and 5C each produce an
independent local commit and stop for a review checkpoint. Task 5A and Task 5B must both complete
before any scorecard or OCR viability conclusion is claimed. Push, PR creation, merge to `main`,
tag, release, and deployment remain separately authorized actions and are not granted by this plan.

---

### Task 1: Freeze the corpus protocol and deterministic fixtures

**Files:**
- Create: `src/mke/evaluation/pdf_ocr_protocol.py`
- Create: `scripts/generate_pdf_ocr_phase0_fixtures.py`
- Create: `tests/fixtures/pdf-ocr-phase0-v1/protocol.json`
- Create: generated PDFs under `tests/fixtures/pdf-ocr-phase0-v1/documents/`
- Create: `tests/evaluation/test_pdf_ocr_protocol.py`

**Interfaces:**
- Consumes: current PyMuPDF dependency and existing fixture identity patterns.
- Produces: `PdfOcrEvaluationProtocol`, page route truth, OCR text truth, and exact Search/Ask expectations for Tasks 2-6.

- [x] **Step 1: Write failing closed-protocol tests**

Create tests that require:

```python
PROTOCOL = Path("tests/fixtures/pdf-ocr-phase0-v1/protocol.json")

def test_protocol_has_exact_public_corpus_inventory() -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL)
    assert protocol.protocol_id == "pdf-ocr-phase0-v1"
    assert [item.document_id for item in protocol.documents] == [
        "english-scan",
        "chinese-scan",
        "mixed-prose",
        "routing-adversarial",
    ]
    assert protocol.providers == (
        "apple-vision-local-v1",
        "paddleocr-vl-1.6-cpu-spike-v1",
        "ppocrv6-medium-cpu-spike-v1",
    )

def test_generator_is_byte_deterministic(tmp_path: Path) -> None:
    first = generate_fixture_tree(tmp_path / "first")
    second = generate_fixture_tree(tmp_path / "second")
    assert snapshot_tree(first) == snapshot_tree(second)

def test_protocol_rejects_unknown_fields_and_checksum_drift(tmp_path: Path) -> None:
    # Copy the fixture tree, mutate one PDF byte and one JSON field, and assert stable failures.
```

- [x] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_pdf_ocr_protocol.py
```

Expected: protocol, generator, and loader are absent.

- [x] **Step 3: Implement the closed protocol loader**

Use dataclasses for `FixtureIdentity`, `ExpectedPage`, `ExpectedQuery`, `EvaluationDocument`, and `PdfOcrEvaluationProtocol`. Require exact object keys, `mke.pdf_ocr_eval_protocol.v1`, normalized relative POSIX paths, lowercase SHA-256, exact byte counts, contiguous page numbers, unique document/query IDs, one expected route per page, and query locators that reference an existing page.

Reject absolute paths, traversal, links, directories in place of files, invalid UTF-8/JSON, unknown providers, missing fields, and private-path markers. Return stable `PdfOcrProtocolError(problem, cause, next_step, subject_id)` values without embedding the failing path.

- [x] **Step 4: Implement and run the fixture generator**

Use PyMuPDF only. Create source text pages with fixed dimensions and metadata, render scan pages at 200 DPI, then embed those raster bytes into new image-only PDF pages. Use built-in Helvetica for English and the PyMuPDF reserved Simplified Chinese font name `china-s` for Chinese. Save with fixed metadata, `garbage=4`, `deflate=True`, and `no_new_id=True`.

The committed corpus contains these truths:

- English scan page 1: `Aurora station uses amber seals for verified cargo.`
- Chinese scan page 1: `巡检编号为海燕四十二号。`
- Mixed page 1 text layer: `Text-layer evidence remains authoritative.`
- Mixed page 2 scan: `Scanned appendix code is ORBIT-731.`
- Routing adversarial pages: blank, decorative raster under 10% coverage, hidden/garbage text, vectorized text, and full-page scan.

Queries must include exact expected page EvidenceRefs for `amber seals`, `海燕四十二号`, and `ORBIT-731`.

Run the generator twice, compare SHA-256 inventories, then write the committed `protocol.json` using the observed stable identities.

- [x] **Step 5: Run GREEN and commit Task 1**

```bash
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_pdf_ocr_protocol.py
git add \
  src/mke/evaluation/pdf_ocr_protocol.py \
  scripts/generate_pdf_ocr_phase0_fixtures.py \
  tests/fixtures/pdf-ocr-phase0-v1 \
  tests/evaluation/test_pdf_ocr_protocol.py
git diff --cached --check
git commit -m "test(ocr): add deterministic phase zero corpus"
```

---

### Task 2: Implement the pure four-state router and bounded page rendering

**Files:**
- Create: `src/mke/evaluation/pdf_ocr_router.py`
- Create: `tests/evaluation/test_pdf_ocr_router.py`

**Interfaces:**
- Consumes: `PdfOcrEvaluationProtocol` and immutable source PDFs.
- Produces: one `PageDecision` for every page and PNG files only for `ocr_required` pages.
- Does not consume or emit provider results.

The following values are an evaluation policy, not production defaults:

```python
@dataclass(frozen=True)
class EvaluationRoutingPolicy:
    accepted_text_min_chars: int = 32
    accepted_text_max_replacement_ratio: float = 0.01
    ocr_text_max_chars: int = 8
    ocr_min_image_coverage: float = 0.80
    render_dpi: int = 200
    max_pages: int = 32
    max_page_pixels: int = 25_000_000
    max_total_rendered_pixels: int = 100_000_000
    max_rendered_file_bytes: int = 32 * 1024 * 1024
    max_total_rendered_bytes: int = 96 * 1024 * 1024
```

- [x] **Step 1: Write failing route and geometry tests**

Require exact route/reason behavior for every protocol page:

```python
@pytest.mark.parametrize(
    ("fixture_id", "page_number", "expected"),
    protocol_route_cases(),
)
def test_router_matches_closed_protocol(
    fixture_id: str,
    page_number: int,
    expected: PageRoute,
) -> None:
    decisions = inspect_pdf(fixture_path(fixture_id), EVALUATION_POLICY)
    assert decisions[page_number - 1].route == expected

def test_hidden_text_never_suppresses_ocr() -> None:
    decision = route_page(hidden_text_page(), EVALUATION_POLICY)
    assert decision.route == "ambiguous_unsupported"
    assert "hidden_text_present" in decision.reasons

def test_image_coverage_is_union_clipped_to_page() -> None:
    inspection = inspect_geometry(overlapping_and_off_page_images())
    assert 0.0 <= inspection.displayed_image_coverage <= 1.0
    assert inspection.displayed_image_coverage == pytest.approx(expected_union_ratio())
```

Also cover empty text, replacement characters, whitespace normalization, sparse text, decorative
images, vector drawings, non-finite rectangles, degenerate pages, encrypted files, malformed files,
zero bytes, excessive pages, and source replacement between identity check and open.

- [x] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_pdf_ocr_router.py
```

Expected: router and bounded renderer are absent.

- [x] **Step 3: Implement bounded inspection and rectangle union**

Open only a previously identified regular-file snapshot. Use `Page.get_text("text", sort=True)`,
`Page.get_image_info()`, `Page.get_drawings()`, and `Page.get_texttrace()` to collect bounded facts.
Normalize text with Unicode NFC, collapse horizontal whitespace, preserve line order, and count
Unicode scalar values. Treat any span whose render mode or opacity makes it non-visible as hidden.

Compute displayed raster coverage from image bounding rectangles clipped to `page.rect`. Use an
exact sweep-line union implementation; summing areas is forbidden because overlap can falsely turn
decorative images into full-page scans. Reject non-finite geometry before arithmetic. The
inspection object contains counts and ratios only, never source bytes or provider data.

- [x] **Step 4: Implement the closed route decision table**

Apply these rules in order:

1. `blank_nontext` when normalized text is empty, image coverage is zero, and drawing count is zero.
2. `ambiguous_unsupported` when hidden text, replacement-ratio failure, vector drawings without an
   accepted text layer, invalid geometry, or conflicting signals are present.
3. `text_layer_accepted` when visible normalized text meets the minimum character count and maximum
   replacement ratio.
4. `ocr_required` when text is at or below the OCR maximum, image coverage meets the minimum,
   drawing count is zero, and no ambiguity signal exists.
5. `ambiguous_unsupported` for everything else.

Emit sorted, allowlisted reason tokens. There is no heuristic fallback from ambiguity to OCR.

- [x] **Step 5: Implement bounded rendering and run GREEN**

Render only `ocr_required` pages from the already-open immutable snapshot at the policy DPI. Check
page pixels before allocating the pixmap, then check encoded PNG and aggregate byte limits. Write
private `0600` files beneath a caller-owned temporary directory using deterministic names such as
`page-0002.png`. Return normalized relative names and identities; do not return operator paths.

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_pdf_ocr_protocol.py \
  tests/evaluation/test_pdf_ocr_router.py
uv run ruff check src/mke/evaluation/pdf_ocr_protocol.py src/mke/evaluation/pdf_ocr_router.py \
  scripts/generate_pdf_ocr_phase0_fixtures.py \
  tests/evaluation/test_pdf_ocr_protocol.py tests/evaluation/test_pdf_ocr_router.py
uv run pyright src/mke/evaluation/pdf_ocr_protocol.py src/mke/evaluation/pdf_ocr_router.py
```

- [x] **Step 6: Commit Task 2**

```bash
git add src/mke/evaluation/pdf_ocr_router.py tests/evaluation/test_pdf_ocr_router.py
git diff --cached --check
git commit -m "feat(ocr): add evaluation page router"
```

---

### Task 3: Add strict isolated provider children and model-free contract tests

**Files:**
- Create: `src/mke/evaluation/pdf_ocr_provider.py`
- Create: `src/mke/evaluation/pdf_ocr_ppocrv6.py`
- Create: `src/mke/evaluation/pdf_ocr_paddle_vl.py`
- Create: `scripts/pdf_ocr_apple_vision.swift`
- Create: `tests/evaluation/test_pdf_ocr_provider.py`

**Interfaces:**
- Consumes: one bounded rendered PNG plus exact provider/profile/model-directory arguments.
- Produces: one closed `mke.pdf_ocr_eval_result.v1` result file.
- The required test suite uses a fake child only. Importing evaluation modules must not import
  PaddleOCR, PaddlePaddle, or platform frameworks.

```python
@dataclass(frozen=True)
class ProviderCommand:
    argv: tuple[str, ...]
    provider: str
    profile: str
    max_stdout_bytes: int = 64 * 1024
    max_stderr_bytes: int = 256 * 1024
    max_result_bytes: int = 8 * 1024 * 1024
    timeout_seconds: float = 180.0

class PdfOcrProviderError(RuntimeError):
    def __init__(
        self,
        *,
        problem: str,
        cause: str,
        next_step: str,
        provider: str,
    ) -> None: ...
```

- [x] **Step 1: Write failing child-boundary tests**

Cover:

- exact result keys and complete page inventory;
- UTF-8, NFC text, finite confidence in `[0, 1]`, bounded boxes, and stable line order;
- malformed/trailing JSON, unknown/extra/missing fields, wrong provider/profile/page, empty output,
  symlink output, oversized result/stdout/stderr, timeout, negative exit, and descendant cleanup;
- missing provider package and missing local model directories fail before provider construction;
- command and public failures contain no input/output/model path, traceback, environment value,
  token, URL, or upstream exception text;
- fake child success and failure run on every required CI platform without provider packages.

```python
def test_provider_modules_are_lazy() -> None:
    import mke.evaluation.pdf_ocr_paddle_vl
    import mke.evaluation.pdf_ocr_ppocrv6

    assert "paddleocr" not in sys.modules
    assert "paddle" not in sys.modules

def test_result_rejects_identity_mismatch(tmp_path: Path) -> None:
    command = fake_result_command(tmp_path, page_number=2, result_page_number=3)
    with pytest.raises(PdfOcrProviderError, match="pdf_ocr_result_invalid"):
        run_provider(command)
```

- [x] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_pdf_ocr_provider.py
```

Expected: child protocol, adapters, and bounded runner are absent.

- [x] **Step 3: Implement the project-owned child protocol**

Use the current `ActiveProcessController` after the owner-lifecycle plan lands. Assign one operation
ID per provider call. Start a new process group, bound parent-side stdout/stderr while reading, use
an output file created by the controller, terminate the process group on timeout/cancellation, wait
for the parent and reader threads, and validate the result only after exit zero. Result validation
must not depend on provider object types.

The exact result object is:

```json
{
  "schema": "mke.pdf_ocr_eval_result.v1",
  "provider": "ppocrv6-medium-cpu-spike-v1",
  "profile": "phase0-200dpi-plain-text-v1",
  "page_number": 1,
  "lines": [
    {"text": "example", "confidence": 0.99, "box": [0.1, 0.2, 0.4, 0.3]}
  ],
  "normalized_text": "example",
  "duration_ms": 42
}
```

Require exact keys and normalized `[x0, y0, x1, y1]` boxes within `[0, 1]`. `normalized_text` must
equal the normalized line join. Apple Vision may emit `confidence=null`; Paddle candidates must emit
finite confidence. No raw provider object crosses the child boundary.

- [x] **Step 4: Implement provider-specific children without executing them**

The PP-OCRv6 child lazily imports `PaddleOCR`, verifies the two model roots are regular directories,
and constructs exactly:

```python
pipeline = PaddleOCR(
    text_detection_model_name="PP-OCRv6_medium_det",
    text_detection_model_dir=str(detection_model_dir),
    text_recognition_model_name="PP-OCRv6_medium_rec",
    text_recognition_model_dir=str(recognition_model_dir),
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    device="cpu",
)
results = list(pipeline.predict(str(input_image)))
```

Accept exactly one page result. Extract `rec_texts`, `rec_scores`, and `rec_boxes` from the documented
JSON result surface, validate them before normalization, and reject length or order mismatch.

The PaddleOCR-VL child lazily imports `PaddleOCRVL`, verifies local layout/VL model roots, and uses
the current official Apple Silicon direct-inference form:

```python
pipeline = PaddleOCRVL(
    pipeline_version="v1.6",
    layout_detection_model_dir=str(layout_model_dir),
    vl_rec_model_dir=str(vl_model_dir),
    device="cpu",
)
results = list(pipeline.predict(str(input_image)))
```

It writes provider output to a fresh private directory, requires one JSON result and one Markdown
result, and derives plain text only from the validated Markdown result. Tables, formulas, images,
and layout hierarchy are diagnostics and are not mapped into MKE Evidence in Phase 0.

The Swift child uses `VNRecognizeTextRequest`, `.accurate`, explicit English and Simplified Chinese
recognition languages, language correction disabled, and `usesCPUOnly=true` where supported. It
accepts only the same fixed CLI fields and writes the same project-owned JSON. Darwin availability
is a measured candidate constraint, not a portable product claim.

- [x] **Step 5: Run model-free GREEN and static validation**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_pdf_ocr_protocol.py \
  tests/evaluation/test_pdf_ocr_router.py \
  tests/evaluation/test_pdf_ocr_provider.py
uv run ruff check src/mke/evaluation/pdf_ocr_*.py tests/evaluation/test_pdf_ocr_*.py
uv run pyright src/mke/evaluation/pdf_ocr_*.py
```

On Darwin with the existing toolchain, also run:

```bash
xcrun swiftc -typecheck scripts/pdf_ocr_apple_vision.swift
```

If `xcrun` or the required Vision API is absent, record the Apple candidate as unavailable; do not
install an SDK or weaken required tests.

- [x] **Step 6: Commit Task 3**

```bash
git add \
  src/mke/evaluation/pdf_ocr_provider.py \
  src/mke/evaluation/pdf_ocr_ppocrv6.py \
  src/mke/evaluation/pdf_ocr_paddle_vl.py \
  scripts/pdf_ocr_apple_vision.swift \
  tests/evaluation/test_pdf_ocr_provider.py
git diff --cached --check
git commit -m "feat(ocr): isolate phase zero providers"
```

**Hard stop:** If package/model acquisition has not been explicitly authorized, stop here with Tasks
1-3 committed and provide the exact proposed downloads, licenses, disk estimate, and commands. Do
not begin Task 4 by assuming design approval grants network authority.

---

### Task 4: Prove ordinary-pip compatibility and prepare immutable candidate receipts

Before cache-only real-provider startup, compatibility must capture the authorized PaddleOCR-VL
1.6 `save_to_json` and `save_to_markdown` regular-file inventory and schema, then compare it with
the strict provisional prose-only adapter envelope from Task 3. Do not relax that envelope without
fixture-backed compatibility evidence. The package-only checkpoint below did not construct a real
provider or observe vendor output; this compatibility check remains blocked on separate model
acquisition authority.

**Files:**
- Create: `scripts/pdf_ocr_candidate_compatibility.py`
- Create: `tests/scripts/test_pdf_ocr_candidate_compatibility.py`
- Create after an authorized run: `benchmarks/ocr/candidate-environments.json`

**Interfaces:**
- Consumes: one built MKE wheel, explicitly supplied Python 3.12/3.13 interpreters, candidate
  package pins, and operator-selected staging/cache roots.
- Produces: redacted `mke.pdf_ocr_candidate_environments.v1` compatibility and artifact receipts.

Start with these exact candidate pins, which match the approved protocol date:

- `paddleocr==3.7.0` and `paddlepaddle==3.3.1` for PP-OCRv6 medium;
- `paddleocr[doc-parser]==3.7.0` and `paddlepaddle==3.3.1` for PaddleOCR-VL 1.6.

If an exact distribution is unavailable for a required interpreter/platform, record that candidate
cell as `resolver_failed`. Do not substitute a newer release, edit the project dependency graph, or
drop Python 3.13 without a new authority decision.

- [x] **Step 1: Write failing command/receipt tests**

Tests must require one wheel identity across all cells and exact cells for Python 3.12/3.13 with:

1. base MKE wheel plus PP-OCR candidate;
2. MKE `[embedding]` plus PP-OCR candidate;
3. MKE `[transcription]` plus PP-OCR candidate;
4. MKE `[embedding,transcription]` plus PP-OCR candidate;
5. the same four cells for PaddleOCR-VL.

Each successful cell runs `python -m pip check`, an import doctor, project wheel metadata checks,
and a fake-child provider proof. The script must reject interpreter aliasing, wheel identity drift,
unbounded subprocess output, missing receipt fields, private paths, and non-exact package pins.

```python
def test_matrix_uses_one_wheel_and_both_interpreters() -> None:
    command_plan = build_matrix_plan(INPUTS)
    assert {cell.mke_wheel_sha256 for cell in command_plan.cells} == {EXPECTED_SHA256}
    assert {cell.python_minor for cell in command_plan.cells} == {"3.12", "3.13"}
    assert len(command_plan.cells) == 16
```

- [x] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_pdf_ocr_candidate_compatibility.py
```

Expected: matrix builder and receipt schema are absent.

- [x] **Step 3: Implement the isolated ordinary-pip matrix**

Build the MKE wheel once. Create every environment outside the repository. Download candidate
wheels into per-candidate staging only during the explicitly authorized prepare step, then install
with ordinary `python -m pip`; do not use the project `uv.lock` as resolver evidence. Save exact
distribution filenames and SHA-256 values. Recreate each successful environment offline from the
same wheel set and rerun `pip check`, imports, and the fake-child proof.

The public receipt contains only schema, candidate/profile, OS, architecture, Python, package
versions, distribution digests, MKE wheel digest, cell result, stable failure code, and aggregate
download/install bytes. It contains no absolute paths, usernames, cache values, URLs, commands, or
upstream logs.

Package-only checkpoint: one MKE wheel was built and frozen at SHA-256
`c4faf00f39d95978b70787f3eb2b2c0253749f6f704106175af377c64ea4ddbe`. Exact Python
`3.12.13` and `3.13.12` interpreters resolved both candidate wheel sets, and all 16 cells passed an
independent offline rebuild, `pip check`, import doctor, installed-wheel identity check, and
model-free fake-child proof. The committed receipt records 1,517,730,869 aggregate distribution
bytes and 25,101,925,887 aggregate per-cell installed bytes. These are package compatibility facts,
not provider quality, startup, artifact-schema, or model compatibility evidence.

Targeted package-checkpoint review resolution: bounded commands now clean their captured process
group after every parent exit, including successful exits, and required tests bind the committed
receipt to its canonical frozen bytes plus its internal distribution totals and MKE wheel identity.
Candidate wheelhouses are seeded with that same MKE wheel before online resolution, so an
all-resolver-failed candidate can emit valid-negative evidence without inventing provider packages;
prepared wheelhouses remain read-only and fail closed when the MKE identity is absent or drifted.
Targeted re-review completed and accepted the package-only checkpoint at implementation HEAD
`ba86e74f3f67fe0c153caf60133aebe74c27568b`; see the durable
[Package Compatibility Checkpoint Review](../reviews/2026-07-14-pdf-ocr-phase0-package-checkpoint-review.md).
The 25,101,925,887-byte figure is the sum of 16 temporary installed trees measured before per-cell
cleanup, not retained disk usage. The retained operator-local package evidence is approximately
2.2 GB; its location is intentionally not part of the public receipt or repository contract. Task 4
Steps 4-6 subsequently completed under separate model-download authority. Their bounded amendment
is recorded in the
[Task 4 Amendment Review](../reviews/2026-07-14-pdf-ocr-phase0-task4-amendment-review.md) and was
accepted at implementation HEAD `040cb6cea2439f5f9d46b09862b17fa1fee59e39`, clearing Task 5.

- [x] **Step 4: Prepare model artifacts under explicit authority**

Before downloading, print a bounded preflight naming every model, source host, declared license,
expected or unknown bytes, staging root, and final candidate profile. Require
`--allow-model-download`; absence is a stable no-op failure.

Prepare separate immutable model roots:

- PP-OCRv6 medium detection and recognition;
- PaddleOCR-VL 1.6 layout and VL recognition.

After acquisition, reject links and unexpected file types, compute a normalized tree digest and
total bytes, record upstream model identifiers and license evidence, then atomically rename staging
to the content-addressed final root. A partial root is never ready. Do not commit models or expose
local locations in the receipt.

The authorized preparation pinned four official revisions and produced 34 regular files totaling
2,201,640,507 bytes. The canonical model receipt SHA-256 is
`3d1e8c45b7ed0c817acaeda3f51954b463016763690e09ca1f23162042219d6e`; its aggregate normalized tree
SHA-256 is `9877eb33601bc06640608021b4b33f9950ccd6ef990cc0877501ba1d451cc998`. Every
component is stored in a read-only content-addressed directory outside the repository. Acquisition
used only the four pinned `PaddlePaddle` revisions, and the call-owned partial staging root was
removed after atomic publication.

The targeted amendment seals the content-addressed snapshot in private staging, reopens every
regular file through the descriptor-bound validator, and recomputes every file, component, and
aggregate identity before atomic publication. The public final tree is revalidated before the
canonical receipt is published, so a same-size replacement after the initial validation fails
closed without exposing a writable accepted snapshot.

- [x] **Step 5: Prove cache-only real-provider startup**

Run each available real provider once with all local model-directory arguments and external egress
blocked. Any attempted download, URL fetch, cache miss, missing artifact, package incompatibility,
or unsupported architecture yields a stable candidate failure. The direct Apple Vision baseline
does not need model preparation but still records platform/API availability.

PaddleOCR-VL direct CPU inference is the approved Phase 0 comparison path. Hosted APIs, AutoDL, and
local VLM service backends remain out of scope even if official documentation recommends them for
speed.

Fresh targeted-repair evidence rebuilt the current MKE wheel at SHA-256
`529a49b33ffce5af8243f9b50f5050d5b0e3a28ada9c13dabb8cd723549e6f47`, replaced only the MKE wheel
inside call-owned copies of the retained third-party wheelhouses, and reran the complete offline
matrix. All 16 cells passed with exact Python 3.12.13 and 3.13.12; the updated canonical package
receipt SHA-256 is `91c782fb147fbb1f59f2c2f447f79d8c8c82188860b2b6afeb4455c92630fcbb`.
The original prepared evidence remained unchanged.

The real-provider controller then created a fresh offline Python 3.13.12 environment from that
exact wheel and verified that `mke` resolved from its `site-packages`, isolated mode was active,
`PYTHONPATH` was absent, the supplied wheelhouse exactly matched the candidate distribution
inventory, and the installed package map exactly matched the passed Python 3.13/base cell after
the same Paddle provider import boundary.
With operating-system network denial and a blocked canary, Apple Vision, PaddleOCR-VL, and
PP-OCRv6 medium returned the exact public fixture text through the installed-wheel result validator
in 328 ms, 15,118 ms, and 9,536 ms respectively. The canonical provider-startup receipt SHA-256 is
`b51dccfc532d8866e49f8325ccb5684b755a63c0356198d793c63b7cad4a7d5f`. These are single-page
startup observations, not OCR quality or production claims.

PaddleOCR-VL loaded both local model roots and completed direct CPU inference, then wrote exactly
`english-scan-page-1.md` (51 bytes) and `english-scan-page-1_res.json` (2,458 bytes). The Markdown
was prose-only and matched the fixture text. The amended adapter rejects the unobserved nested
envelope and accepts only the exact observed direct-top-level keys, strict page/layout/block types
and bounds, supported prose labels, and Markdown/block equality. The exact inventory, digests,
top-level keys, and block keys are bound through the repository authority validator to
`benchmarks/ocr/provider-startup.json` and a public-safe sanitized observed fixture. The receipt
records this retained two-file inventory separately as `observed_vendor_fixture`; fresh provider
entries claim only current-run startup facts and do not reuse historical artifact digests as if
they were captured again. Unknown or unsupported vendor content still fails closed.

- [x] **Step 6: Run GREEN and commit Task 4**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_pdf_ocr_candidate_compatibility.py
uv run ruff check scripts/pdf_ocr_candidate_compatibility.py \
  tests/scripts/test_pdf_ocr_candidate_compatibility.py
uv run pyright scripts/pdf_ocr_candidate_compatibility.py
git add \
  scripts/pdf_ocr_candidate_compatibility.py \
  tests/scripts/test_pdf_ocr_candidate_compatibility.py \
  benchmarks/ocr/candidate-environments.json
git diff --cached --check
git commit -m "test(ocr): record candidate compatibility"
```

If no candidate environment can be recreated offline, continue to Task 5 only far enough to emit a
tested `no_go` scorecard. Do not run or design a production provider.

Task 4 closes as compatibility evidence, not a provider decision. The package matrix is rebound to
the amended exact MKE wheel and remains canonical; model and startup receipts are independently
canonical, and required model-free suites remain network-free. Targeted authority re-review
accepted the bounded Task 4 amendment at `040cb6cea2439f5f9d46b09862b17fa1fee59e39`, with
`158 passed, 5 warnings`, Ruff, Pyright, diff check, and all three canonical receipt identities
passing. That acceptance predates the MKE 0.1.2 reconciliation. The existing package and startup
receipts are therefore historical until Task 4R rebinds them; Task 5B cannot start from those
receipts. This does not select a provider or authorize production OCR.

---

### Task 4R: Reconcile v0.1.2 and refresh retained provider authority

The branch was reconciled with `main` through merge commit
`804b9205c35b657ab3aba51faf4cdc40ab0e4057`. Merge, rather than rebase or squash, preserves the
accepted Task 4 commit identities referenced by the review record. Task 4R execution begins only
after targeted review accepts this resumption plan. The review of
`dccf5bb7eb4d1ff7527e1ee5801554576c4dfcd1..3673c8373da6973b0961f789204be14adce3d4dd`
accepted the plan and cleared Task 4R-A. Task 4R-A implementation commit
`3b029a47c69f32d63e9cae688196e205d96f8af7` was subsequently accepted with no findings. Task 4R-B
is cleared only for a separate dispatch and has not started; later work remains gated.

The existing package and startup receipts bind an MKE 0.1.1 wheel. They remain historical,
self-consistent evidence after the MKE 0.1.2 merge and cannot authorize Task 5B. Task 4R-A removed
the compatibility controller's former fixed 0.1.1 wheel filename and installed-version authority
and added the call-owned rebind harness required before evidence refresh. Task 4R-A and Task 4R-B
remain separate TDD commits and reviewable checkpoints; both must complete before Task 4R review.

#### Task 4R-A: Generalize candidate wheel authority and prepare rebound wheelhouses

**Files:**

- Modify: `scripts/pdf_ocr_candidate_compatibility.py`
- Modify: `tests/scripts/test_pdf_ocr_candidate_compatibility.py`

No dependency or production `src/mke` file may change.

Task 4R-A preserved the existing committed-receipt freeze exactly. The assertion for
`benchmarks/ocr/candidate-environments.json` remains bound to
`91c782fb147fbb1f59f2c2f447f79d8c8c82188860b2b6afeb4455c92630fcbb` after Task 4R-A.
Synthetic historical 0.1.1 cases supplement that gate; they must not delete, weaken, dynamically
derive, or turn the exact committed SHA assertion into a tautology.

- [x] **Step 1: Freeze the plan start and write RED version-authority tests**

Freeze `task4r_plan_start="$(git rev-parse HEAD)"`. Require it to be the review-cleared resumption
plan commit, contain merge `804b9205c35b657ab3aba51faf4cdc40ab0e4057`, and preserve accepted
Task 4 commits. Add failing tests for:

- a historical 0.1.1 receipt remaining valid through self-consistency rather than current-checkout
  version binding;
- current 0.1.2 generation from an exact
  `multimodal_knowledge_engine-0.1.2-py3-none-any.whl`;
- filename/version/repository `pyproject.toml` drift;
- duplicate or missing MKE distributions and cross-candidate MKE filename/digest drift;
- successful-cell installed package version drift and provider runtime version drift.

- [x] **Step 2: Implement self-consistent wheel authority**

Remove fixed `0.1.1` filename and version authority from generation and validation paths. Use a
strict parser for exactly `multimodal_knowledge_engine-<version>-py3-none-any.whl`, where `version`
matches a closed safe-version regular expression. New generation requires the filename version to
equal `project.version` from repository `pyproject.toml`; for this branch it is `0.1.2`.

Receipt validation remains checkout-independent and self-consistent: each candidate has exactly one
MKE distribution; both candidates use the same filename, bytes, and digest; every passed cell has
`package_versions["multimodal-knowledge-engine"]` equal to the parsed filename version; and the
provider runtime version, digest, filename, candidate, surface, Python cell, and installed package
set exactly match the referenced package receipt cell. Wheel filename, wheel METADATA, install
doctor, repository version, or runtime disagreement fails closed. Historical 0.1.1 receipts remain
readable evidence but cannot authorize Task 5B after reconciliation.

- [x] **Step 3: Implement and test call-owned prepared-wheelhouse copy/rebind**

Add an internal helper that consumes the retained prepared root, a nonexistent call-owned
destination, and the new exact MKE wheel. The source must contain exactly the two candidate
directories and only regular `.whl` files: no symlinks, nested paths, or unexpected entries. Each
candidate must contain exactly one old MKE wheel.

Copy every third-party wheel through descriptor-bound reads into the destination. Omit the old MKE
wheel and write the same new MKE wheel bytes once per candidate. Verify source entry inventory,
bytes, and digests before and after; it must remain byte-identical. Verify destination third-party
inventory exactly equals source and differs only in MKE filename/version/bytes/digest. Destination
collision, missing or multiple MKE wheels, source drift, symlink, non-regular file, nested or
unexpected entry fails closed. Only this rebound call-owned root may be passed to
`--prepared-wheelhouses` and `ProviderStartupConfig.wheelhouse`; the retained source is never
modified.

- [x] **Step 4: Run GREEN and commit Task 4R-A**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_pdf_ocr_candidate_compatibility.py
UV_OFFLINE=1 uv run ruff check scripts/pdf_ocr_candidate_compatibility.py \
  tests/scripts/test_pdf_ocr_candidate_compatibility.py
UV_OFFLINE=1 uv run pyright scripts/pdf_ocr_candidate_compatibility.py
git diff --check
git diff --name-only
git status --short
git add scripts/pdf_ocr_candidate_compatibility.py \
  tests/scripts/test_pdf_ocr_candidate_compatibility.py
git diff --cached --check
git commit -m "fix(ocr): generalize candidate wheel authority"
```

Task 4R-A stages only the script and its tests. Stop on any other tracked change.
Targeted authority re-review accepted Task 4R-A at
`3b029a47c69f32d63e9cae688196e205d96f8af7`. This acceptance covers the model-free harness and
controller authority only. Task 4R-B remains a separate, unstarted evidence operation.

#### Task 4R-B: Refresh v0.1.2 package and provider evidence

**Files:**

- Modify: `benchmarks/ocr/candidate-environments.json`
- Modify: `benchmarks/ocr/provider-startup.json`
- Modify mechanically after generation: `tests/scripts/test_pdf_ocr_candidate_compatibility.py`
- Verify byte-identical: `benchmarks/ocr/model-artifacts.json`

Task 4R-B permits no controller or production behavior change. The test file may change only to
replace the committed package receipt's exact frozen SHA with the SHA-256 of the newly generated
canonical 0.1.2 receipt.

- [ ] **Step 5: Freeze the evidence source and call-owned cleanup contract**

After Task 4R-A is committed and the worktree is clean, freeze
`task4r_evidence_start="$(git rev-parse HEAD)"`. Build only from that exact committed HEAD. The
handoff records `task4r_plan_start`, the Task 4R-A commit, and `task4r_evidence_start`; current
receipt schemas have no `source_commit`, so do not claim they bind those commits.

```bash
python312="$(command -v python3.12)"
python313="$(command -v python3.13)"
retained_wheelhouses="${MKE_OCR_RETAINED_WHEELHOUSES:?operator input required}"
model_root="${MKE_OCR_RETAINED_MODEL_ROOT:?operator input required}"
staging_root="$(mktemp -d)"
cache_root="$(mktemp -d)"
cleanup_task4r() {
  rm -rf -- "${staging_root}" "${cache_root}"
}
trap cleanup_task4r EXIT INT TERM
wheel_dir="${staging_root}/wheel"
rebound_wheelhouses="${staging_root}/rebound-wheelhouses"
apple_executable="${staging_root}/apple-vision-child"
mkdir -p "${wheel_dir}"
UV_OFFLINE=1 uv build --wheel --out-dir "${wheel_dir}"
wheel="${wheel_dir}/multimodal_knowledge_engine-0.1.2-py3-none-any.whl"
test -f "${wheel}"
```

The trap owns only the two `mktemp` roots and never deletes operator-retained evidence. Record the
wheel filename, bytes, SHA-256, version, and METADATA before cleanup. After all evidence and checks
complete, invoke the trap cleanup, disable it, and require both roots not to exist.

- [ ] **Step 6: Create the rebound wheelhouses and run the offline matrix**

Use the Task 4R-A helper to create `rebound_wheelhouses` from `retained_wheelhouses` and the exact
new wheel. Prove the retained source unchanged and the destination identity constraints, then run:

```bash
UV_OFFLINE=1 uv run python scripts/pdf_ocr_candidate_compatibility.py \
  --repository . \
  --wheel "${wheel}" \
  --python "${python312}" \
  --python "${python313}" \
  --prepared-wheelhouses "${rebound_wheelhouses}" \
  --staging-root "${staging_root}/matrix" \
  --cache-root "${cache_root}/matrix" \
  --output benchmarks/ocr/candidate-environments.json \
  --json
```

Require `UV_OFFLINE=1` and do not pass `--allow-package-download` or
`--allow-model-download`. Require exact 0.1.2 filename/METADATA/cell versions, two candidates,
Python 3.12/3.13, four surfaces, and 16 validated cells.

- [ ] **Step 7: Compile the Apple Vision child and refresh provider startup**

The Swift driver is not a provider child. Typecheck and compile the tracked source into the
call-owned executable, then pass only that compiled child to `ProviderStartupConfig`:

```bash
xcrun swiftc -typecheck scripts/pdf_ocr_apple_vision.swift
xcrun swiftc scripts/pdf_ocr_apple_vision.swift -o "${apple_executable}"
test -x "${apple_executable}"
```

Use a call-owned Python invocation of existing `ProviderStartupConfig` and
`run_provider_startup`, with `task4r_evidence_start`, the exact wheel, `python313`,
`rebound_wheelhouses/paddleocr-vl-1.6-cpu-spike-v1`, retained `model_root`, compiled
`apple_executable`, and call-owned provider staging. Do not add a tracked runner or pass `swift` or
`swiftc` as the provider executable. Write exactly `benchmarks/ocr/provider-startup.json`. Require
installed-wheel origin, package receipt/cell identity, network denial, canary, and all three
provider startup results. Descriptor-bound rehash `model_root`; any difference from
`benchmarks/ocr/model-artifacts.json` is a hard stop and that receipt remains byte-identical.

- [ ] **Step 8: Freeze the new canonical package receipt**

Only after the offline matrix and provider startup have completed, require
`benchmarks/ocr/candidate-environments.json` to equal its canonical bytes and compute its exact
SHA-256. Mechanically replace only the old literal passed as `frozen_sha256` by
`test_committed_receipt_is_canonical_closed_and_frozen` with that new digest. Do not derive the
expected value from the file at test time, weaken or remove the assertion, or change any other test.

Inspect the test diff before verification:

```bash
candidate_receipt_sha256="$(sha256sum benchmarks/ocr/candidate-environments.json | awk '{print $1}')"
test "${#candidate_receipt_sha256}" -eq 64
git diff -- tests/scripts/test_pdf_ocr_candidate_compatibility.py
```

The receipt and startup evidence bind exact wheel, package, model, and runtime bytes and identities;
they do not bind `source_commit`. This post-run test-only freeze update is repository regression
authority for the generated receipt bytes, not a source-commit binding.

- [ ] **Step 9: Run complete verification after the freeze update**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_pdf_ocr_candidate_compatibility.py
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_pdf_ocr_protocol.py \
  tests/evaluation/test_pdf_ocr_router.py \
  tests/evaluation/test_pdf_ocr_provider.py
UV_OFFLINE=1 uv run ruff check scripts/pdf_ocr_candidate_compatibility.py \
  tests/scripts/test_pdf_ocr_candidate_compatibility.py
UV_OFFLINE=1 uv run pyright scripts/pdf_ocr_candidate_compatibility.py
git diff --check
git diff --name-only
git status --short
```

Validate both canonical receipts, exact wheel version/digest, the 16-cell JSON, full package-set
authority, provider runtime authority, network canary, model rehash, and the exact new frozen SHA.
The complete compatibility suite runs only after the freeze assertion is updated. Remove the two
call-owned roots through `cleanup_task4r`, run `trap - EXIT INT TERM`, and require
`test ! -e "${staging_root}"` plus `test ! -e "${cache_root}"`.

- [ ] **Step 10: Audit three exact files and commit Task 4R-B**

Require the test diff to contain only the single mechanical committed-receipt frozen-SHA update;
any other test or code change is a hard stop. Verify `benchmarks/ocr/model-artifacts.json` remains
byte-identical. Stage exactly the two receipts and the test file:

```bash
git diff -- tests/scripts/test_pdf_ocr_candidate_compatibility.py
git add benchmarks/ocr/candidate-environments.json \
  benchmarks/ocr/provider-startup.json \
  tests/scripts/test_pdf_ocr_candidate_compatibility.py
git diff --cached --check
git diff --cached --name-only
git commit -m "test(ocr): refresh v0.1.2 provider evidence"
```

Any other tracked change, missing retained evidence, identity drift, or attempted network fallback
is an authority hard stop. Task 4R-A and Task 4R-B must both complete before the Task 4R authority
review checkpoint.

---

### Task 5A: Add the evaluation-only OCR manifest fingerprint contract

**Files:**
- Modify: `src/mke/domain/__init__.py`
- Modify: `tests/domain/test_manifest.py`
- Modify: `tests/application/test_pdf_publication.py`
- Modify: `tests/application/test_video_publication.py`
- Modify: `tests/interfaces/test_cli_retrieval.py`
- Modify: `tests/interfaces/test_mcp_contract.py`
- Add and then update: `docs/decisions/0010-pdf-ocr-evaluation-manifest-fingerprint.md`

- [ ] **Step 1: Write RED fingerprint and stage-mismatch tests**

Require exact `pdf-ocr-eval-v1:<64 lowercase hex SHA-256>` recognition and exact OCR stages
`pdf_ocr_extraction` plus `candidate_evidence`. Reject prefix-only, wrong-length, uppercase, unknown
version, OCR fingerprint with text stages, text fingerprint with OCR stages, and non-page locators.
Reject duplicate required stages. Keep all existing PDF and video compatibility cases green, prove
the normal PDF application path still emits `pymupdf-text-v1`, and prove public CLI/MCP contracts
do not add an `extractor_fingerprint` or `RunManifest` input.

- [ ] **Step 2: Run RED**

Run the exact focused set:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/domain/test_manifest.py \
  tests/application/test_pdf_publication.py \
  tests/application/test_video_publication.py \
  tests/interfaces/test_cli_retrieval.py \
  tests/interfaces/test_mcp_contract.py
```

Only the new OCR domain cases may be RED because the evaluation fingerprint is not recognized.
Existing PDF/video behavior and application/interface no-new-input assertions must remain GREEN.

- [ ] **Step 3: Implement the minimal domain validator contract**

Add only the evaluation fingerprint regex and required-stage mapping. The domain validator checks
compact syntax, exact stages, and page locators; it does not validate the structured payload.
Production code changes are limited to the minimal domain validator. Do not change application or
interface code, CLI, MCP, SQLite schema, runtime defaults, dependencies, or default PDF ingest. If
implementation requires an application or interface production-code change, hard stop for a new
authority finding.

- [ ] **Step 4: Run GREEN and update ADR status**

After the exact compatibility and mismatch tests pass, change ADR-0010 from Proposed to Accepted
with the actual implementation evidence. Do not mark it Accepted before implementation.

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/domain/test_manifest.py \
  tests/application/test_pdf_publication.py \
  tests/application/test_video_publication.py \
  tests/interfaces/test_cli_retrieval.py \
  tests/interfaces/test_mcp_contract.py
UV_OFFLINE=1 uv run ruff check src/mke/domain/__init__.py \
  tests/domain/test_manifest.py \
  tests/application/test_pdf_publication.py \
  tests/application/test_video_publication.py \
  tests/interfaces/test_cli_retrieval.py \
  tests/interfaces/test_mcp_contract.py
UV_OFFLINE=1 uv run pyright src/mke/domain/__init__.py
```

- [ ] **Step 5: Commit Task 5A and stop for review**

Stage only the domain validator, its tests, and ADR. Create an independent local commit and review
checkpoint.

---

### Task 5B: Generate the real scorecard through Publication, Search, Ask, and EvidenceRef

**Files:**
- Create: `src/mke/evaluation/pdf_ocr_runner.py`
- Create: `tests/evaluation/test_pdf_ocr_runner.py`
- Create after an authorized real run: `benchmarks/ocr/phase0-scorecard.json`

**Interfaces:**
- Consumes: closed protocol, deterministic router, available candidate commands, and compatibility
  receipts.
- Produces: `mke.pdf_ocr_phase0_scorecard.v1` with one valid-positive selection or `no_go`.

```python
@dataclass(frozen=True)
class CandidateOutcome:
    provider: str
    profile: str
    status: Literal["passed", "failed", "unavailable"]
    route_accuracy: Fraction
    query_accuracy: Fraction
    evidence_ref_accuracy: Fraction
    character_error_rate: float | None
    word_error_rate: float | None
    elapsed_ms: int | None
    peak_rss_bytes: int | None
    failure_codes: tuple[str, ...]

@dataclass(frozen=True)
class Phase0Decision:
    status: Literal["go", "no_go"]
    selected_provider: str | None
    selected_profile: str | None
    outcomes: tuple[CandidateOutcome, ...]
```

- [ ] **Step 1: Write failing metric, publication, and hard-gate tests**

Use fake provider outputs to require:

- deterministic Unicode code-point CER and whitespace-token WER;
- exact page order and line order;
- 100% protocol route accuracy before any provider can pass;
- exact query answerability and exact `mke.evidence_ref.v1` source/page locators;
- no Evidence from blank or ambiguous pages;
- accepted text-layer pages bypass OCR and retain extractor authority;
- provider/package/model receipt fingerprints in the Run manifest;
- a candidate with lower CER but a dependency, cache-only, query, locator, or license failure loses;
- `no_go` is emitted deterministically when no candidate passes every hard gate;
- JSON contains no non-finite numbers, paths, timestamps, hostnames, or unbounded diagnostics.
- the extractor identity schema has exactly the frozen top-level and nested keys and types;
- mutating every nested authority leaf either changes the digest or is rejected;
- every missing/extra key, fixture or page reordering/duplicate, non-finite value, and
  boolean-as-integer value fails closed.

```python
def test_fast_candidate_cannot_win_without_exact_evidence_refs() -> None:
    decision = decide(scorecard_with_fast_locator_failure())
    assert decision.status == "no_go"
    assert "evidence_ref_mismatch" in decision.outcomes[0].failure_codes

def test_ambiguous_page_never_reaches_disposable_publication() -> None:
    result = evaluate_with_fake_provider(protocol_with_ambiguous_page())
    assert result.publication_evidence_pages.isdisjoint(result.ambiguous_pages)
```

- [ ] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_pdf_ocr_runner.py
```

Expected: metrics, publication builder, and decision logic are absent.

- [ ] **Step 3: Implement deterministic metrics and hard gates**

Implement edit distance locally; do not add an evaluation dependency. Normalize both truth and
candidate text using the protocol normalization. Store exact numerators/denominators in JSON and
derive display decimals from them. Metrics are descriptive until authority review freezes numeric
quality/resource thresholds. The following gates are already non-negotiable:

- exact route truth for every page;
- every required provider page has valid non-empty output;
- every protocol query is answerable by both Search and Ask;
- every returned EvidenceRef has the exact source and page locator;
- no ambiguous or blank page is published;
- successful ordinary-pip and offline/cache-only receipts;
- declared compatible license/provenance evidence;
- no external runtime egress;
- bounded completion with complete measurements.

- [ ] **Step 4: Build a disposable Publication using current contracts**

Use a temporary SQLite database and current domain/store APIs; do not add a production repository
method. For each document:

1. create/ensure Source from the immutable fixture identity;
2. create a Run and transition it through current legal states;
3. convert accepted text-layer pages and accepted OCR pages into distinct Evidence rows with exact
   page locators;
4. create and validate the closed structured `mke.pdf_ocr_extractor_identity.v1` payload with the
   exact ADR-0010 keys, types, rational encoding, ordering, and compact serialization; verify its
   digest exactly matches the compact `RunManifest` `pdf-ocr-eval-v1:<sha256>` fingerprint before
   calling `persist_validated_candidate`;
5. validate and activate one disposable Publication;
6. call current `search_library_v1` and `ask_library_v1` application contracts;
7. compare normalized payloads and portable EvidenceRefs to protocol truth.

The evaluation runner may compose current public/application contracts, but it must not bypass
Publication authority by writing ad hoc retrieval rows or querying private database tables for the
product assertion.

- [ ] **Step 5: Run real candidates and write the scorecard**

Execute every available candidate on the same rendered page identities. Run candidates serially to
make resource measurements comparable. Measure wall time, peak child RSS, temporary bytes, result
bytes, model bytes, package bytes, and cold-start behavior. Record `unavailable` rather than
inventing measurements for an unsupported platform or failed resolver.

Write the scorecard with stable sorted JSON and no timestamps. Its `decision` is:

- `go` with exactly one provider/profile only when one or more candidates pass every hard gate; use
  lower observed CER, then lower peak RSS, then provider ID as deterministic tie-breakers;
- `no_go` with no selected provider otherwise.

Numeric quality and resource limits remain `observed`, not `approved`, until the planning/review
window accepts the scorecard. A green runner alone does not authorize production implementation.

- [ ] **Step 6: Run GREEN and commit Task 5B**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_pdf_ocr_protocol.py \
  tests/evaluation/test_pdf_ocr_router.py \
  tests/evaluation/test_pdf_ocr_provider.py \
  tests/evaluation/test_pdf_ocr_runner.py
uv run ruff check src/mke/evaluation/pdf_ocr_*.py tests/evaluation/test_pdf_ocr_*.py
uv run pyright src/mke/evaluation/pdf_ocr_*.py
git add \
  src/mke/evaluation/pdf_ocr_runner.py \
  tests/evaluation/test_pdf_ocr_runner.py \
  benchmarks/ocr/phase0-scorecard.json
git diff --cached --check
git commit -m "test(ocr): add phase zero product scorecard"
```

Commit Task 5B independently and stop for its review checkpoint before Task 5C begins.

---

### Task 5C: Refresh retrieval evaluation provenance once after code stabilizes

The E1 source identity hashes the complete `src/mke/**/*.py` inventory. On the reconciled OCR
branch, the checked-in canonical baseline validator already reports `evaluation_content` identity
drift. Perform one refresh only after Task 5A and Task 5B production/evaluation code is stable so
the repository does not churn provenance repeatedly. Reuse the proven current-main closure from
`docs/superpowers/plans/2026-07-14-v0-1-2-release-closeout-implementation.md` Task 4 exactly.

The maximum conditional allowlist is exactly these 21 paths; a smaller validator-proven subset is
allowed, while any different or larger changed set is an authority hard stop:

- `benchmarks/retrieval/retrieval-eval-v1-baseline.json`
- `tests/fixtures/retrieval-numeric-v1/protocol-lock.json`
- `benchmarks/retrieval/numeric-grouping-v1-comparison.json`
- `benchmarks/retrieval/retrieval-chinese-v1-baseline.json`
- `benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json`
- `tests/fixtures/retrieval-dense-v1/protocol-lock.json`
- `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-development-freeze.json`
- `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-holdout-receipt.json`
- `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json`
- `tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json`
- `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json`
- `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json`
- `tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json`
- `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json`
- `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-holdout-receipt.json`
- `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json`
- `docs/how-to/evaluate-dense-retrieval.md`
- `docs/how-to/evaluate-hybrid-rrf-retrieval.md`
- `docs/how-to/evaluate-relevance-gate-reranker.md`
- `tests/evaluation/test_relevance_gate_protocol.py`
- `tests/evaluation/test_relevance_gate_workflow.py`

- [ ] **Step 1: Freeze the reference and generate fresh observations in the proven order**

Before any write, set `task5c_start="$(git rev-parse HEAD)"` and create a call-owned
`evidence_dir`. Generate E2 first from an exclusive call-owned hidden protocol copy inside
`tests/fixtures/retrieval-numeric-v1`, because `load_numeric_protocol` derives its root from that
path. Never overwrite an existing hidden protocol:

```bash
evidence_dir="$(mktemp -d)"
task5c_start="$(git rev-parse HEAD)"
e2_protocol="tests/fixtures/retrieval-numeric-v1/.protocol-lock.ocr-observation.json"
test ! -e "${e2_protocol}"
cleanup_e2_protocol() { rm -f -- "${e2_protocol}"; }
trap cleanup_e2_protocol EXIT INT TERM
cp tests/fixtures/retrieval-numeric-v1/protocol-lock.json "${e2_protocol}"
uv run python -m mke.evaluation.numeric_comparison refresh-scope \
  --protocol "${e2_protocol}" --repository .
uv run mke eval retrieval-numeric --protocol "${e2_protocol}" --json \
  > "${evidence_dir}/e2.json"
jq -e '
  .schema_version == "mke.retrieval_numeric_comparison.v1" and
  .protocol_id == "retrieval-numeric-v1" and
  .integrity_status == "passed" and
  .candidate_status == "passed" and
  .integrity_failures == []
' "${evidence_dir}/e2.json"
rm -f -- "${e2_protocol}"
trap - EXIT INT TERM
test ! -e "${e2_protocol}"

uv run mke eval retrieval --manifest tests/fixtures/retrieval-eval-v1.json \
  --json > "${evidence_dir}/e1.json"
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json > "${evidence_dir}/e3a.json"
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > "${evidence_dir}/e3b.json"
```

An E2 observation generated directly from the checked-in protocol is diagnostic only and must
never be passed to `artifact_refresh`. Run `tests/evaluation/test_artifact_refresh.py` before any
artifact write.

- [ ] **Step 2: Run all seven exact canonical validators before writing**

Run the seven canonical validator commands from the release-closeout plan Task 4 Step 2, in order:
`mke.evaluation.baseline`, `numeric_artifact validate`, `chinese_artifact validate`,
`cjk_lexical_artifact validate`, `dense_artifact validate`, `hybrid_rrf_artifact validate`, and
`relevance_gate_artifact validate`, with their exact checked-in artifact/protocol paths,
`${evidence_dir}` observations for E2/E3-A/E3-B, and `--repository .`. Generate all four
observations before this validator chain. Continue only if every failure is an identity-only
source/scope/dependency mismatch; never call it an unchanged baseline.

```bash
uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository .
uv run python -m mke.evaluation.numeric_artifact validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed "${evidence_dir}/e2.json" \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
uv run python -m mke.evaluation.chinese_artifact validate \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --observed "${evidence_dir}/e3a.json" \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed "${evidence_dir}/e3b.json" \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run python -m mke.evaluation.dense_artifact validate \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --repository .
uv run python -m mke.evaluation.hybrid_rrf_artifact validate \
  --artifact benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --repository .
uv run python -m mke.evaluation.relevance_gate_artifact validate \
  --artifact benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json \
  --protocol tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json \
  --repository .
```

- [ ] **Step 3: Refresh E1 through E3-B only through the recoverable five-target transaction**

```bash
uv run python -m mke.evaluation.artifact_refresh \
  --repository . \
  --e1-observed "${evidence_dir}/e1.json" \
  --e2-observed "${evidence_dir}/e2.json" \
  --e3-observed "${evidence_dir}/e3a.json" \
  --e3b-observed "${evidence_dir}/e3b.json"
```

On failure, run only
`uv run python -m mke.evaluation.artifact_refresh recover --repository .`, then stop. Do not modify
`src/mke/evaluation/artifact_refresh.py`. If the existing helper cannot express this identity-only
change, stop with a new authority finding; do not extend it.

- [ ] **Step 4: Rebind E3-C, E3-D, and E3-E in a detached validation mirror**

Create a call-owned rebinder under `${evidence_dir}` and record its SHA-256. Generate all downstream
candidate bytes before applying any. Create a detached mirror at `task5c_start`, then overlay the
successful E1-E3-B bytes and every staged E3-C/D/E byte at canonical repository-relative paths.
The mirror must contain the complete proposed dependency graph.

Before feature-worktree apply, require the mirror changed set to equal the complete proposed set
and remain within the 21-path allowlist; exact candidate/mirror byte equality; normalized semantic
equality at every E1 through E3-E layer; and all seven validators green with `--repository` and all
paths rooted in the mirror. Permit only source, scope, dependency, path, byte, SHA-256, and
state-receipt identity changes. Corpus, fixtures, queries, qrels, observations, ordered results,
metrics, thresholds, gates, diagnostics, selected candidate/profile, status, and verdict must not
change.

- [ ] **Step 5: Apply with exact backup and recovery**

Before apply, save exact bytes, digests, and path descriptors for every conditional downstream path
in a call-owned backup. Apply only mirror-validated E3-C/D/E bytes using per-file atomic replacement
in dependency order. If any apply or post-apply check fails, restore every touched path and verify
exact bytes and descriptors. Inexact restoration is an authority hard stop. Do not publish a
partial downstream set.

- [ ] **Step 6: Run the proven regression and validator closure**

Run the complete artifact regression suite from release-closeout Task 4 Step 6:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_artifact_refresh.py \
  tests/evaluation/test_baseline.py \
  tests/evaluation/test_numeric_artifact.py \
  tests/evaluation/test_numeric_comparison.py \
  tests/evaluation/test_chinese_artifact.py \
  tests/evaluation/test_cjk_lexical_artifact.py \
  tests/evaluation/test_dense_protocol.py \
  tests/evaluation/test_dense_artifact.py \
  tests/evaluation/test_hybrid_rrf_protocol.py \
  tests/evaluation/test_hybrid_rrf_workflow.py \
  tests/evaluation/test_hybrid_rrf_artifact.py \
  tests/evaluation/test_relevance_gate_artifact.py \
  tests/evaluation/test_relevance_gate_protocol.py \
  tests/evaluation/test_relevance_gate_workflow.py
```

Then rerun all seven exact canonical validator commands against the real worktree. Every command
must pass before staging. Run full pytest from the same candidate.

- [ ] **Step 7: Commit only validator-proven identities and stop for review**

Stage only the exact validator-proven subset of the 21-path allowlist and commit:

```bash
git diff --check
git diff --name-only -- benchmarks/retrieval tests/fixtures tests/evaluation docs/how-to
git add -- <space-separated exact validator-proven paths>
git diff --cached --check
git commit -m "test(eval): refresh OCR evaluation identities"
```

The review handoff must include the rebinder SHA-256, exact changed paths, and before/after
normalized semantic equality for every E1 through E3-E layer.

Task 5A and Task 5B completion is required before any scorecard or OCR viability conclusion may be
claimed. Task 5C must finish before Task 6 begins.

---

### Task 6: Prove the installed-wheel external consumer and record the authority decision

**Files:**
- Create: `scripts/pdf_ocr_phase0_consumer.py`
- Create: `tests/scripts/test_pdf_ocr_phase0_consumer.py`
- Create: `docs/superpowers/reviews/2026-07-13-pdf-ocr-phase0-decision.md`
- Modify: `docs/superpowers/plans/2026-07-13-pdf-ocr-phase0-viability-implementation.md`

**Interfaces:**
- Consumes: one built MKE wheel, the final scorecard, local prepared candidate artifacts, and the
  official MCP Python SDK already locked by the project.
- Produces: one exact aggregate JSON proof plus a public-neutral GO/NO-GO review record.

- [ ] **Step 1: Write failing installed-wheel controller tests**

Require a controller that:

- builds the MKE wheel once and installs that exact wheel into a temporary consumer environment;
- refuses repository imports and records the installed distribution location as external without
  serializing the path;
- invokes the Phase 0 runner from installed package code with local candidate artifacts;
- starts `mke mcp`, uses official SDK stdio discovery, calls `search_library_v1` and
  `ask_library_v1`, and validates the exact page EvidenceRef;
- bounds stdout/stderr/time/process groups and redacts all paths;
- emits one exact object on stdout and stage messages on stderr;
- maps build, venv, install, candidate, ingest, server, discovery, search, ask, locator, cleanup,
  and schema failures to distinct stable codes.

```python
EXPECTED = {
    "schema": "mke.pdf_ocr_phase0_consumer_proof.v1",
    "status": "passed",
    "protocol": "pdf-ocr-phase0-v1",
    "wheel_reused": True,
    "publication_verified": True,
    "search_verified": True,
    "ask_verified": True,
    "evidence_ref_verified": True,
    "cleanup": True,
}
```

- [ ] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_pdf_ocr_phase0_consumer.py
```

Expected: controller and stable failure mapping are absent.

- [ ] **Step 3: Implement and run the installed-wheel proof**

The outer controller owns temporary roots and final cleanup. The installed consumer owns only MCP
tool discovery/calls and exact payload validation. Model preparation is never performed by the
consumer. For a real candidate, run with external egress blocked and explicit immutable local
artifact arguments supplied only to the evaluation runner; the MCP request schema remains current
and contains no OCR authority.

```bash
UV_OFFLINE=1 uv run python scripts/pdf_ocr_phase0_consumer.py \
  --wheel dist/multimodal_knowledge_engine-*.whl \
  --scorecard benchmarks/ocr/phase0-scorecard.json \
  --json
```

Expected stdout is byte-equivalent to stable sorted JSON for `EXPECTED` plus exact provider/profile
and Python-version proof fields defined by the tests. If the scorecard is `no_go`, run the tested
negative proof instead and require `status="no_go"` with no selected provider or product claim.

- [ ] **Step 4: Run the complete repository verification**

```bash
UV_OFFLINE=1 uv run pytest -q
uv run ruff check .
uv run pyright
UV_OFFLINE=1 uv build
UV_OFFLINE=1 uv run mke proof run
UV_OFFLINE=1 uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
uv run python scripts/release_presentation_audit.py --root .
git diff --check
```

Do not classify an unrelated failure from a named worktree as baseline without reproducing it from
the same committed candidate in a neutral detached worktree. Any forbidden production-surface diff
or unclassified failure blocks completion.

- [ ] **Step 5: Write the public-neutral decision record**

The review must include:

- commit and wheel identity;
- exact corpus/protocol identity;
- candidate package/model/license receipts;
- compatibility matrix and unsupported cells;
- measured CER/WER, route/query/EvidenceRef accuracy, time, RSS, storage, package, and model bytes;
- external-egress proof and cache-only behavior;
- exact verification commands/results;
- limitations: synthetic corpus, prose-only, no table/formula/layout fidelity, no production user
  claim, no hosted/AutoDL comparison;
- `GO` only with one selected immutable provider/profile and proposed numeric limits;
- otherwise `NO-GO` and the smallest evidence-backed next choice.

The planning/review window, not the implementation worker, accepts or rejects proposed provider,
thresholds, resource limits, dependency constraints, and production-plan authorization.

- [ ] **Step 6: Mark this plan implemented, commit, and stop**

After all accepted checks, mark completed checkboxes and set an `Implemented/verified` status with
the final commit and exact test counts. For `no_go`, mark the plan complete when the negative proof
and decision record are valid; do not leave it falsely active.

```bash
git add \
  scripts/pdf_ocr_phase0_consumer.py \
  tests/scripts/test_pdf_ocr_phase0_consumer.py \
  benchmarks/ocr/phase0-scorecard.json \
  docs/superpowers/plans/2026-07-13-pdf-ocr-phase0-viability-implementation.md \
  docs/superpowers/reviews/2026-07-13-pdf-ocr-phase0-decision.md
git diff --cached --check
git commit -m "docs(ocr): close phase zero viability proof"
```

Stop with a clean local branch. Do not add a production OCR extra, public flag, runtime contract,
release change, push, PR, merge, tag, model artifact, or deployment. A valid-positive result returns
to the authority window for provider/limit freeze and a separate production implementation plan.
