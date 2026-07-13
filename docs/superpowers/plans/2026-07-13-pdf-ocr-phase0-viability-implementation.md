# PDF OCR Phase 0 Viability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

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
| `benchmarks/ocr/phase0-scorecard.json` | Public measurement/decision artifact generated only from a real authorized run. |
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
- Tasks 4-6 are sequential and require both preceding plans plus the explicit package/model
  authorization stated below.
- A valid-positive Phase 0 result returns to planning. It does not unlock production Tasks 7-9 from
  the design spec automatically; those require a new reviewed production plan.

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

- [ ] **Step 1: Write failing closed-protocol tests**

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

- [ ] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_pdf_ocr_protocol.py
```

Expected: protocol, generator, and loader are absent.

- [ ] **Step 3: Implement the closed protocol loader**

Use dataclasses for `FixtureIdentity`, `ExpectedPage`, `ExpectedQuery`, `EvaluationDocument`, and `PdfOcrEvaluationProtocol`. Require exact object keys, `mke.pdf_ocr_eval_protocol.v1`, normalized relative POSIX paths, lowercase SHA-256, exact byte counts, contiguous page numbers, unique document/query IDs, one expected route per page, and query locators that reference an existing page.

Reject absolute paths, traversal, links, directories in place of files, invalid UTF-8/JSON, unknown providers, missing fields, and private-path markers. Return stable `PdfOcrProtocolError(problem, cause, next_step, subject_id)` values without embedding the failing path.

- [ ] **Step 4: Implement and run the fixture generator**

Use PyMuPDF only. Create source text pages with fixed dimensions and metadata, render scan pages at 200 DPI, then embed those raster bytes into new image-only PDF pages. Use built-in Helvetica for English and the PyMuPDF reserved Simplified Chinese font name `china-s` for Chinese. Save with fixed metadata, `garbage=4`, `deflate=True`, and `no_new_id=True`.

The committed corpus contains these truths:

- English scan page 1: `Aurora station uses amber seals for verified cargo.`
- Chinese scan page 1: `巡检编号为海燕四十二号。`
- Mixed page 1 text layer: `Text-layer evidence remains authoritative.`
- Mixed page 2 scan: `Scanned appendix code is ORBIT-731.`
- Routing adversarial pages: blank, decorative raster under 10% coverage, hidden/garbage text, vectorized text, and full-page scan.

Queries must include exact expected page EvidenceRefs for `amber seals`, `海燕四十二号`, and `ORBIT-731`.

Run the generator twice, compare SHA-256 inventories, then write the committed `protocol.json` using the observed stable identities.

- [ ] **Step 5: Run GREEN and commit Task 1**

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

- [ ] **Step 1: Write failing route and geometry tests**

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

- [ ] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_pdf_ocr_router.py
```

Expected: router and bounded renderer are absent.

- [ ] **Step 3: Implement bounded inspection and rectangle union**

Open only a previously identified regular-file snapshot. Use `Page.get_text("text", sort=True)`,
`Page.get_image_info()`, `Page.get_drawings()`, and `Page.get_texttrace()` to collect bounded facts.
Normalize text with Unicode NFC, collapse horizontal whitespace, preserve line order, and count
Unicode scalar values. Treat any span whose render mode or opacity makes it non-visible as hidden.

Compute displayed raster coverage from image bounding rectangles clipped to `page.rect`. Use an
exact sweep-line union implementation; summing areas is forbidden because overlap can falsely turn
decorative images into full-page scans. Reject non-finite geometry before arithmetic. The
inspection object contains counts and ratios only, never source bytes or provider data.

- [ ] **Step 4: Implement the closed route decision table**

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

- [ ] **Step 5: Implement bounded rendering and run GREEN**

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

- [ ] **Step 6: Commit Task 2**

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

- [ ] **Step 1: Write failing child-boundary tests**

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

- [ ] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_pdf_ocr_provider.py
```

Expected: child protocol, adapters, and bounded runner are absent.

- [ ] **Step 3: Implement the project-owned child protocol**

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

- [ ] **Step 4: Implement provider-specific children without executing them**

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

- [ ] **Step 5: Run model-free GREEN and static validation**

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

- [ ] **Step 6: Commit Task 3**

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

- [ ] **Step 1: Write failing command/receipt tests**

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

- [ ] **Step 2: Run RED**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_pdf_ocr_candidate_compatibility.py
```

Expected: matrix builder and receipt schema are absent.

- [ ] **Step 3: Implement the isolated ordinary-pip matrix**

Build the MKE wheel once. Create every environment outside the repository. Download candidate
wheels into per-candidate staging only during the explicitly authorized prepare step, then install
with ordinary `python -m pip`; do not use the project `uv.lock` as resolver evidence. Save exact
distribution filenames and SHA-256 values. Recreate each successful environment offline from the
same wheel set and rerun `pip check`, imports, and the fake-child proof.

The public receipt contains only schema, candidate/profile, OS, architecture, Python, package
versions, distribution digests, MKE wheel digest, cell result, stable failure code, and aggregate
download/install bytes. It contains no absolute paths, usernames, cache values, URLs, commands, or
upstream logs.

- [ ] **Step 4: Prepare model artifacts under explicit authority**

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

- [ ] **Step 5: Prove cache-only real-provider startup**

Run each available real provider once with all local model-directory arguments and external egress
blocked. Any attempted download, URL fetch, cache miss, missing artifact, package incompatibility,
or unsupported architecture yields a stable candidate failure. The direct Apple Vision baseline
does not need model preparation but still records platform/API availability.

PaddleOCR-VL direct CPU inference is the approved Phase 0 comparison path. Hosted APIs, AutoDL, and
local VLM service backends remain out of scope even if official documentation recommends them for
speed.

- [ ] **Step 6: Run GREEN and commit Task 4**

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

---

### Task 5: Generate the real scorecard through Publication, Search, Ask, and EvidenceRef

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
4. create a deterministic `RunManifest` whose extractor fingerprint includes router, render,
   provider, model-tree, package-receipt, and normalization fingerprints;
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

- [ ] **Step 6: Run GREEN and commit Task 5**

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
