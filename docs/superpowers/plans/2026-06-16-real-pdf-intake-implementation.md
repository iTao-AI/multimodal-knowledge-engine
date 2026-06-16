# Real PDF Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixture-only PDF parser with a PyMuPDF-backed text-layer intake adapter that publishes page Evidence through the existing Publication lifecycle and exposes `PdfIntakeReport` diagnostics.

**Architecture:** Keep MKE's clean core: domain DTOs and `KnowledgeEngine` own the contract, PyMuPDF stays behind `src/mke/adapters/pdf/`, and SQLite stores Run-attached intake diagnostics. CLI and MCP read the same `IngestResult.intake_report` / Run diagnostics while Search and Ask remain active-Publication-only.

**Tech Stack:** Python 3.12/3.13, PyMuPDF `pymupdf>=1.24.0,<2`, SQLite, pytest, Ruff, Pyright strict mode, MCP Python SDK.

---

## Review Findings Covered

This plan incorporates:

- `docs/superpowers/specs/2026-06-16-real-pdf-intake-design.md`
- `docs/superpowers/reviews/2026-06-16-real-pdf-intake-autoplan-review.md`
- `docs/superpowers/reviews/2026-06-16-real-pdf-intake-eng-review.md`

| Finding | Handling |
|---|---|
| `IngestResult` lacks report slot | Task 1 adds `intake_report: PdfIntakeReport | None = None`. |
| Extractor return type underspecified | Task 1 adds `PdfExtractionResult(report, pages)`. |
| `get_text()` ordering unspecified | Task 2 uses `page.get_text("text", sort=True)`. |
| Adapter replaceability claim unsupported | Task 2 adds a small extractor object boundary used by the application layer. |
| PyMuPDF version unpinned | Task 0 pins `pymupdf>=1.24.0,<2`. |
| MCP file size unbounded | Task 5 adds a 100 MB PDF guard before opening the engine. |
| Normalization goals conflict | Task 2 implements explicit line-ending/control-character normalization and CLI-only one-line formatting. |
| Old PDF fingerprint compatibility | Task 1 recognizes both `builtin-pdf-text-v1` and `pymupdf-text-v1`. |
| Non-ASCII Search limitation | Task 6 documents that D1 extracts Unicode but does not change ASCII query tokenization. |

## File Structure

- Create `docs/decisions/0004-pymupdf-pdf-intake-adapter.md`: dependency and licensing ADR.
- Modify `pyproject.toml`: add `pymupdf>=1.24.0,<2`.
- Modify `src/mke/domain/__init__.py`: add `PdfIntakeReport`, `PdfExtractionResult`, extend `IngestResult`, add `PYMUPDF_TEXT_FINGERPRINT`, and preserve legacy PDF fingerprint validation.
- Modify `src/mke/adapters/pdf/extractor.py`: replace regex-only extraction with `PyMuPDFPdfExtractor` and compatibility `extract_text_pages()`.
- Modify `src/mke/adapters/pdf/__init__.py`: export new DTO-facing extractor symbols.
- Modify `src/mke/adapters/sqlite/__init__.py`: add `pdf_intake_reports` migration and Run-attached report persistence/read methods.
- Modify `src/mke/application/__init__.py`: wire the extractor boundary, persist reports, return `intake_report`, and expose Run intake lookup.
- Modify `src/mke/cli.py`: print intake summary on `ingest` and `run get`.
- Modify `src/mke/interfaces/mcp_contract.py`: add 100 MB PDF guard and intake summary payloads for `ingest_file` and `get_run`.
- Modify tests under `tests/domain/`, `tests/adapters/`, `tests/application/`, and `tests/interfaces/`.
- Create `scripts/pdf_intake_smoke.py`: optional local smoke harness for 10-20 diverse PDFs without committing source documents.
- Modify docs: `docs/reference/cli.md`, `docs/reference/contracts.md`, `docs/how-to/run-local-product-proof.md`, `README.md`, `README_CN.md`, and `docs/README.md`.

## Task 0: Dependency ADR And Pin

**Files:**
- Create: `docs/decisions/0004-pymupdf-pdf-intake-adapter.md`
- Modify: `pyproject.toml`
- Test: `uv lock --check` or `uv sync --locked`

- [x] **Step 1: Add the dependency ADR**

Create `docs/decisions/0004-pymupdf-pdf-intake-adapter.md`:

```markdown
# ADR-0004: PyMuPDF PDF Intake Adapter

- Status: Accepted
- Date: 2026-06-16

## Context

D1 must move beyond the fixture-only PDF parser and support ordinary text-layer PDFs while keeping
the MKE domain and application contracts independent from extraction libraries.

PyMuPDF is dual-licensed under AGPL or commercial license terms. Using it in-process is acceptable
for this open-source proof, but downstream closed-source redistribution requires license review,
a commercial PyMuPDF license, or a replacement adapter.

## Decision

- Use `pymupdf>=1.24.0,<2` for the D1 in-process PDF text-layer adapter.
- Keep PyMuPDF behind `src/mke/adapters/pdf/`.
- Expose only project-owned DTOs: `PdfIntakeReport`, `PdfExtractionResult`, and `PdfPageText`.
- Use `page.get_text("text", sort=True)` for page text extraction.
- Treat a future PDF sidecar adapter as the escape route for closed-source or stricter license
  isolation needs.

## Consequences

- D1 reaches real text-layer PDF intake faster than building a sidecar or custom parser.
- The core lifecycle stays independent of PyMuPDF.
- Major PyMuPDF upgrades require re-running the PDF smoke harness.
- OCR, table extraction, PyMuPDF4LLM, and layout-aware chunking remain outside D1.
```

- [x] **Step 2: Pin PyMuPDF**

Modify `pyproject.toml` dependencies:

```toml
dependencies = [
  "mcp>=1.12.4,<2",
  "pymupdf>=1.24.0,<2",
]
```

- [x] **Step 3: Refresh lockfile**

Run:

```bash
uv sync
```

Expected: `uv.lock` updates with a PyMuPDF package entry and the environment syncs successfully.

- [x] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock docs/decisions/0004-pymupdf-pdf-intake-adapter.md
git commit -m "docs(decision): accept pymupdf pdf intake adapter"
```

## Task 1: Domain DTOs And Fingerprint Compatibility

**Files:**
- Modify: `src/mke/domain/__init__.py`
- Create: `tests/domain/test_pdf_intake_report.py`

- [x] **Step 1: Add failing domain tests**

Create `tests/domain/test_pdf_intake_report.py`:

```python
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    PYMUPDF_TEXT_FINGERPRINT,
    CandidateEvidence,
    PdfIntakeReport,
    RunManifest,
    validate_manifest,
)


def test_pdf_intake_report_summary_fields_are_immutable() -> None:
    report = PdfIntakeReport(
        total_pages=3,
        extracted_pages=2,
        empty_pages=1,
        total_extracted_chars=120,
        page_char_counts=(80, 40, 0),
        suspected_scanned_pages=1,
        extraction_mode="pymupdf-text",
        failure_reason=None,
    )

    assert report.total_pages == 3
    assert report.extracted_pages == 2
    assert report.page_char_counts == (80, 40, 0)
    assert report.failure_reason is None


def test_validate_manifest_accepts_legacy_and_pymupdf_pdf_fingerprints() -> None:
    evidence = [
        CandidateEvidence(
            evidence_id="ev_page",
            locator_kind="page",
            locator_start=1,
            locator_end=1,
            text="Page text",
        )
    ]

    for fingerprint in (PDF_EXTRACTOR_FINGERPRINT, PYMUPDF_TEXT_FINGERPRINT):
        validate_manifest(
            RunManifest(
                run_id="run_pdf",
                evidence_count=1,
                required_stages=("candidate_evidence", "pdf_text_extraction"),
                extractor_fingerprint=fingerprint,
                asset_sha256="a" * 64,
            ),
            evidence,
        )
```

- [x] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/domain/test_pdf_intake_report.py -q
```

Expected: FAIL because `PdfIntakeReport` and `PYMUPDF_TEXT_FINGERPRINT` do not exist.

- [x] **Step 3: Add DTOs and fingerprint**

Modify `src/mke/domain/__init__.py` after `ActivationResult`:

```python
@dataclass(frozen=True)
class PdfIntakeReport:
    total_pages: int
    extracted_pages: int
    empty_pages: int
    total_extracted_chars: int
    page_char_counts: tuple[int, ...]
    suspected_scanned_pages: int
    extraction_mode: str
    failure_reason: str | None = None


@dataclass(frozen=True)
class PdfExtractionResult:
    report: PdfIntakeReport
    pages: tuple["PdfPageText", ...]
```

Add `intake_report` to `IngestResult`:

```python
@dataclass(frozen=True)
class IngestResult:
    run_id: str
    run_state: RunState
    evidence_count: int
    retry_of_run_id: str | None = None
    intake_report: PdfIntakeReport | None = None
```

Move or define `PdfPageText` in domain if keeping adapter DTOs centralized:

```python
@dataclass(frozen=True)
class PdfPageText:
    page_number: int
    text: str
```

Add fingerprint:

```python
PDF_EXTRACTOR_FINGERPRINT = "builtin-pdf-text-v1"
PYMUPDF_TEXT_FINGERPRINT = "pymupdf-text-v1"
```

Update `validate_manifest()` PDF branch:

```python
    if manifest.extractor_fingerprint in {
        PDF_EXTRACTOR_FINGERPRINT,
        PYMUPDF_TEXT_FINGERPRINT,
    }:
        expected_stages = REQUIRED_PDF_STAGES
        expected_locator_kind = "page"
```

- [x] **Step 4: Run tests**

Run:

```bash
uv run pytest tests/domain/test_pdf_intake_report.py tests/domain/test_manifest.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/mke/domain/__init__.py tests/domain/test_pdf_intake_report.py
git commit -m "feat(domain): add pdf intake report contract"
```

## Task 2: PyMuPDF Extractor

**Files:**
- Modify: `src/mke/adapters/pdf/extractor.py`
- Modify: `src/mke/adapters/pdf/__init__.py`
- Create: `tests/adapters/test_pdf_extractor.py`
- Create or update fixtures under `tests/fixtures/pdf/`

- [x] **Step 1: Add failing extractor tests**

Create `tests/adapters/test_pdf_extractor.py`:

```python
from pathlib import Path

import pytest

from mke.adapters.pdf import PdfExtractionError, PyMuPDFPdfExtractor
from tests.conftest import PDF_FIXTURES


def test_pymupdf_extractor_returns_pages_and_report() -> None:
    result = PyMuPDFPdfExtractor().extract(PDF_FIXTURES / "text-layer.pdf")

    assert result.report.total_pages == 2
    assert result.report.extracted_pages == 2
    assert result.report.empty_pages == 0
    assert result.report.total_extracted_chars > 0
    assert result.report.extraction_mode == "pymupdf-text"
    assert result.pages[0].page_number == 1
    assert "Trustworthy evidence starts on page one." in result.pages[0].text


def test_pymupdf_extractor_counts_empty_pages(tmp_path: Path) -> None:
    path = tmp_path / "blank-and-text.pdf"
    _write_blank_and_text_pdf(path)

    result = PyMuPDFPdfExtractor().extract(path)

    assert result.report.total_pages == 2
    assert result.report.extracted_pages == 1
    assert result.report.empty_pages == 1
    assert result.report.page_char_counts[-1] == 0
    assert [page.page_number for page in result.pages] == [1]


def test_pymupdf_extractor_rejects_invalid_pdf(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.7\\ntruncated")

    with pytest.raises(PdfExtractionError, match="PDF cannot be opened"):
        PyMuPDFPdfExtractor().extract(path)


def test_pymupdf_extractor_rejects_encrypted_pdf(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.pdf"
    _write_encrypted_pdf(path)

    with pytest.raises(PdfExtractionError, match="encrypted PDF is not supported"):
        PyMuPDFPdfExtractor().extract(path)


def test_pymupdf_extractor_rejects_no_text_pdf() -> None:
    with pytest.raises(PdfExtractionError, match="no extractable text"):
        PyMuPDFPdfExtractor().extract(PDF_FIXTURES / "no-text.pdf")


def test_pymupdf_extractor_uses_sorted_text_order(tmp_path: Path) -> None:
    path = tmp_path / "two-column.pdf"
    _write_two_column_pdf(path)

    result = PyMuPDFPdfExtractor().extract(path)

    assert "left column first" in result.pages[0].text
    assert "right column second" in result.pages[0].text


def test_pymupdf_extractor_preserves_50_page_numbers(tmp_path: Path) -> None:
    path = tmp_path / "many-pages.pdf"
    _write_many_pages_pdf(path, pages=50)

    result = PyMuPDFPdfExtractor().extract(path)

    assert result.report.total_pages == 50
    assert result.report.extracted_pages == 50
    assert result.pages[0].page_number == 1
    assert result.pages[-1].page_number == 50


def _write_blank_and_text_pdf(path: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "visible text page")
    doc.new_page()
    doc.save(path)


def _write_two_column_pdf(path: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "left column first")
    page.insert_text((320, 72), "right column second")
    doc.save(path)


def _write_many_pages_pdf(path: Path, pages: int) -> None:
    import pymupdf

    doc = pymupdf.open()
    for index in range(1, pages + 1):
        page = doc.new_page()
        page.insert_text((72, 72), f"page {index} evidence text")
    doc.save(path)


def _write_encrypted_pdf(path: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "encrypted evidence text")
    doc.save(
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
        permissions=int(pymupdf.PDF_PERM_ACCESSIBILITY),
    )
```

- [x] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/adapters/test_pdf_extractor.py -q
```

Expected: FAIL because `PyMuPDFPdfExtractor` does not exist.

- [x] **Step 3: Implement extractor**

Replace `src/mke/adapters/pdf/extractor.py` with:

```python
"""PyMuPDF-backed text-layer PDF extractor."""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf

from mke.domain import PdfExtractionResult, PdfIntakeReport, PdfPageText


class PdfExtractionError(ValueError):
    """Raised when a PDF cannot produce trustworthy text-layer Evidence."""

    def __init__(self, message: str, report: PdfIntakeReport | None = None) -> None:
        super().__init__(message)
        self.report = report


class PyMuPDFPdfExtractor:
    """Extract text-layer page Evidence and intake diagnostics from local PDFs."""

    extraction_mode = "pymupdf-text"

    def extract(self, path: Path) -> PdfExtractionResult:
        try:
            with pymupdf.open(path) as document:
                if document.is_encrypted:
                    report = _failure_report("encrypted PDF is not supported")
                    raise PdfExtractionError("encrypted PDF is not supported", report)
                pages: list[PdfPageText] = []
                page_char_counts: list[int] = []
                suspected_scanned_pages = 0
                for page_index, page in enumerate(document, start=1):
                    text = _normalize_page_text(page.get_text("text", sort=True))
                    char_count = len(text)
                    page_char_counts.append(char_count)
                    if text:
                        pages.append(PdfPageText(page_number=page_index, text=text))
                    elif page.get_images(full=True):
                        suspected_scanned_pages += 1
                report = PdfIntakeReport(
                    total_pages=len(document),
                    extracted_pages=len(pages),
                    empty_pages=len(document) - len(pages),
                    total_extracted_chars=sum(page_char_counts),
                    page_char_counts=tuple(page_char_counts),
                    suspected_scanned_pages=suspected_scanned_pages,
                    extraction_mode=self.extraction_mode,
                    failure_reason=None,
                )
        except PdfExtractionError:
            raise
        except Exception as error:
            report = _failure_report("PDF cannot be opened")
            raise PdfExtractionError("PDF cannot be opened", report) from error
        if not pages:
            failed = PdfIntakeReport(
                total_pages=report.total_pages,
                extracted_pages=0,
                empty_pages=report.empty_pages,
                total_extracted_chars=0,
                page_char_counts=report.page_char_counts,
                suspected_scanned_pages=report.suspected_scanned_pages,
                extraction_mode=report.extraction_mode,
                failure_reason="PDF has no extractable text",
            )
            raise PdfExtractionError("PDF has no extractable text", failed)
        return PdfExtractionResult(report=report, pages=tuple(pages))


def extract_text_pages(path: Path) -> list[PdfPageText]:
    """Compatibility helper for callers not yet using PdfExtractionResult."""
    return list(PyMuPDFPdfExtractor().extract(path).pages)


def _normalize_page_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", " ")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    return text.strip()


def _failure_report(reason: str) -> PdfIntakeReport:
    return PdfIntakeReport(
        total_pages=0,
        extracted_pages=0,
        empty_pages=0,
        total_extracted_chars=0,
        page_char_counts=(),
        suspected_scanned_pages=0,
        extraction_mode=PyMuPDFPdfExtractor.extraction_mode,
        failure_reason=reason,
    )
```

Text normalization priority for this implementation:

1. Preserve page boundaries and semantic text content in stored Evidence.
2. Normalize line endings to `\n` and strip page-leading/page-trailing whitespace.
3. Replace NUL and unsafe control characters before indexing.
4. Keep one-line output formatting in CLI rendering, not in the extractor.

Update `src/mke/adapters/pdf/__init__.py`:

```python
from mke.adapters.pdf.extractor import (
    PdfExtractionError,
    PyMuPDFPdfExtractor,
    extract_text_pages,
)

__all__ = ["PdfExtractionError", "PyMuPDFPdfExtractor", "extract_text_pages"]
```

- [x] **Step 4: Run extractor tests**

Run:

```bash
uv run pytest tests/adapters/test_pdf_extractor.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/mke/adapters/pdf/extractor.py src/mke/adapters/pdf/__init__.py tests/adapters/test_pdf_extractor.py
git commit -m "feat(pdf): add pymupdf text intake adapter"
```

## Task 3: Persist Run-Attached Intake Reports

**Files:**
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Create: `tests/adapters/test_sqlite_pdf_intake_report.py`

- [x] **Step 1: Add failing storage tests**

Create `tests/adapters/test_sqlite_pdf_intake_report.py`:

```python
from pathlib import Path

from mke.adapters.sqlite import SQLiteStore
from mke.domain import PdfIntakeReport


def test_sqlite_persists_pdf_intake_report_for_run(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    source = store.ensure_source("doc.pdf", "a" * 64)
    run = store.create_run(source.source_id)
    report = PdfIntakeReport(
        total_pages=2,
        extracted_pages=1,
        empty_pages=1,
        total_extracted_chars=20,
        page_char_counts=(20, 0),
        suspected_scanned_pages=1,
        extraction_mode="pymupdf-text",
        failure_reason=None,
    )

    store.persist_pdf_intake_report(run.run_id, report)

    loaded = store.get_pdf_intake_report(run.run_id)
    assert loaded == report


def test_sqlite_returns_none_for_missing_pdf_intake_report(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    source = store.ensure_source("doc.pdf", "a" * 64)
    run = store.create_run(source.source_id)

    assert store.get_pdf_intake_report(run.run_id) is None
```

- [x] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/adapters/test_sqlite_pdf_intake_report.py -q
```

Expected: FAIL because persistence methods do not exist.

- [x] **Step 3: Add schema and storage methods**

In `SQLiteStore.migrate()`, add:

```sql
CREATE TABLE IF NOT EXISTS pdf_intake_reports (
  run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
  total_pages INTEGER NOT NULL,
  extracted_pages INTEGER NOT NULL,
  empty_pages INTEGER NOT NULL,
  total_extracted_chars INTEGER NOT NULL,
  page_char_counts TEXT NOT NULL,
  suspected_scanned_pages INTEGER NOT NULL,
  extraction_mode TEXT NOT NULL,
  failure_reason TEXT
);
```

Import `json` and `PdfIntakeReport`, then add methods:

```python
    def persist_pdf_intake_report(self, run_id: str, report: PdfIntakeReport) -> None:
        self._connection.execute(
            """
            INSERT OR REPLACE INTO pdf_intake_reports(
              run_id, total_pages, extracted_pages, empty_pages,
              total_extracted_chars, page_char_counts, suspected_scanned_pages,
              extraction_mode, failure_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                report.total_pages,
                report.extracted_pages,
                report.empty_pages,
                report.total_extracted_chars,
                json.dumps(list(report.page_char_counts), separators=(",", ":")),
                report.suspected_scanned_pages,
                report.extraction_mode,
                report.failure_reason,
            ),
        )
        self._connection.commit()

    def get_pdf_intake_report(self, run_id: str) -> PdfIntakeReport | None:
        row = self._connection.execute(
            """
            SELECT total_pages, extracted_pages, empty_pages, total_extracted_chars,
                   page_char_counts, suspected_scanned_pages, extraction_mode, failure_reason
            FROM pdf_intake_reports WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return PdfIntakeReport(
            total_pages=int(row["total_pages"]),
            extracted_pages=int(row["extracted_pages"]),
            empty_pages=int(row["empty_pages"]),
            total_extracted_chars=int(row["total_extracted_chars"]),
            page_char_counts=tuple(int(value) for value in json.loads(str(row["page_char_counts"]))),
            suspected_scanned_pages=int(row["suspected_scanned_pages"]),
            extraction_mode=str(row["extraction_mode"]),
            failure_reason=(
                str(row["failure_reason"]) if row["failure_reason"] is not None else None
            ),
        )
```

- [x] **Step 4: Run storage tests**

Run:

```bash
uv run pytest tests/adapters/test_sqlite_pdf_intake_report.py tests/adapters/test_sqlite_migration.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/mke/adapters/sqlite/__init__.py tests/adapters/test_sqlite_pdf_intake_report.py
git commit -m "feat(storage): persist pdf intake report"
```

## Task 4: Application Wiring

**Files:**
- Modify: `src/mke/application/__init__.py`
- Modify: `tests/application/test_pdf_publication.py`

- [x] **Step 1: Add failing application tests**

Append to `tests/application/test_pdf_publication.py`:

```python
def test_pdf_ingest_result_carries_intake_report(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    result = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

    assert result.intake_report is not None
    assert result.intake_report.total_pages == 2
    assert result.intake_report.extracted_pages == 2
    assert engine.get_pdf_intake_report(result.run_id) == result.intake_report


def test_failed_pdf_ingest_persists_failure_report(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(PdfIngestError) as error:
        engine.ingest_pdf(PDF_FIXTURES / "no-text.pdf")

    report = engine.get_pdf_intake_report(error.value.run_id or "")
    assert report is not None
    assert report.failure_reason == "PDF has no extractable text"
    assert engine.search("anything") == []
```

- [x] **Step 2: Run failing application tests**

Run:

```bash
uv run pytest tests/application/test_pdf_publication.py -q
```

Expected: FAIL because `get_pdf_intake_report()` and `intake_report` wiring do not exist.

- [x] **Step 3: Wire extractor and report persistence**

Update imports in `src/mke/application/__init__.py`:

```python
from typing import Protocol

from mke.adapters.pdf import PdfExtractionError, PyMuPDFPdfExtractor
from mke.domain import PYMUPDF_TEXT_FINGERPRINT, PdfExtractionResult, PdfIntakeReport
```

Add protocol:

```python
class PdfExtractor(Protocol):
    def extract(self, path: Path) -> PdfExtractionResult:
        raise NotImplementedError
```

Change constructor:

```python
    def __init__(self, db_path: Path, pdf_extractor: PdfExtractor | None = None) -> None:
        self._store = SQLiteStore(db_path)
        self._pdf_extractor = pdf_extractor or PyMuPDFPdfExtractor()
```

Add method:

```python
    def get_pdf_intake_report(self, run_id: str) -> PdfIntakeReport | None:
        return self._store.get_pdf_intake_report(run_id)
```

In `_process_pdf()`, replace `pages = extract_text_pages(path)` with:

```python
            extraction = self._pdf_extractor.extract(path)
            self._store.persist_pdf_intake_report(run.run_id, extraction.report)
            pages = extraction.pages
```

Set manifest fingerprint:

```python
                extractor_fingerprint=PYMUPDF_TEXT_FINGERPRINT,
```

Return report on non-activated and activated paths:

```python
                return IngestResult(
                    run.run_id,
                    RunState.VALIDATED,
                    len(evidence),
                    retry_of_run_id,
                    extraction.report,
                )
```

and:

```python
            return IngestResult(
                run_id=run.run_id,
                run_state=activation.run_state,
                evidence_count=len(evidence) if activation.published else 0,
                retry_of_run_id=retry_of_run_id,
                intake_report=extraction.report,
            )
```

In the `except PdfExtractionError` branch, persist the error report when available:

```python
            if error.report is not None:
                self._store.persist_pdf_intake_report(run.run_id, error.report)
```

- [x] **Step 4: Run application tests**

Run:

```bash
uv run pytest tests/application/test_pdf_publication.py tests/application/test_reliability_demo.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/mke/application/__init__.py tests/application/test_pdf_publication.py
git commit -m "feat(pdf): attach intake reports to runs"
```

## Task 5: CLI And MCP Contracts

**Files:**
- Modify: `src/mke/cli.py`
- Modify: `src/mke/interfaces/mcp_contract.py`
- Modify: `tests/interfaces/test_cli_pdf.py`
- Modify: `tests/interfaces/test_mcp_contract.py`

- [x] **Step 1: Add failing CLI tests**

Append to `tests/interfaces/test_cli_pdf.py`:

```python
def test_cli_ingest_prints_pdf_intake_summary(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"

    assert main(["--db", str(db_path), "ingest", str(PDF_FIXTURES / "text-layer.pdf")]) == 0

    output = capsys.readouterr().out
    assert "pdf_pages=2" in output
    assert "extracted_pages=2" in output
    assert "empty_pages=0" in output
    assert "suspected_scanned_pages=0" in output


def test_cli_run_get_prints_pdf_intake_summary(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    assert main(["--db", str(db_path), "ingest", str(PDF_FIXTURES / "text-layer.pdf")]) == 0
    ingest_output = capsys.readouterr().out
    run_id = ingest_output.split()[0].split("=", 1)[1]

    assert main(["--db", str(db_path), "run", "get", run_id]) == 0

    output = capsys.readouterr().out
    assert "pdf_pages=2" in output
    assert "extracted_pages=2" in output
```

- [x] **Step 2: Add failing MCP tests**

Append to `tests/interfaces/test_mcp_contract.py`:

```python
def test_mcp_ingest_file_returns_pdf_intake_summary(tmp_path: Path) -> None:
    config = McpRuntimeConfig(db_path=tmp_path / "mke.sqlite", allowed_root=PDF_FIXTURES)

    result = ingest_file(config, "text-layer.pdf")

    assert result["ok"] is True
    assert result["intake_report"]["total_pages"] == 2
    assert result["intake_report"]["extracted_pages"] == 2


def test_mcp_get_run_returns_pdf_intake_summary(tmp_path: Path) -> None:
    config = McpRuntimeConfig(db_path=tmp_path / "mke.sqlite", allowed_root=PDF_FIXTURES)
    ingest = ingest_file(config, "text-layer.pdf")

    result = get_run(config, ingest["run_id"])

    assert result["ok"] is True
    assert result["intake_report"]["total_pages"] == 2


def test_mcp_rejects_oversized_pdf_before_ingest(tmp_path: Path) -> None:
    large_pdf = tmp_path / "large.pdf"
    large_pdf.write_bytes(b"%PDF-1.7\n" + b"0" * (100 * 1024 * 1024 + 1))
    config = McpRuntimeConfig(db_path=tmp_path / "mke.sqlite", allowed_root=tmp_path)

    result = ingest_file(config, "large.pdf")

    assert result == {
        "ok": False,
        "problem": "input_file_too_large",
        "cause": "PDF input exceeds 100 MB limit",
        "active_publication_impact": "unchanged",
        "next_step": "choose_smaller_file",
    }
```

- [x] **Step 3: Run failing interface tests**

Run:

```bash
uv run pytest tests/interfaces/test_cli_pdf.py tests/interfaces/test_mcp_contract.py -q
```

Expected: FAIL because intake payloads and size guard are missing.

- [x] **Step 4: Implement CLI helpers**

In `src/mke/cli.py`, import `PdfIntakeReport` and add:

```python
def _format_pdf_intake_report(report: PdfIntakeReport) -> str:
    return (
        f"pdf_pages={report.total_pages} "
        f"extracted_pages={report.extracted_pages} "
        f"empty_pages={report.empty_pages} "
        f"extracted_chars={report.total_extracted_chars} "
        f"suspected_scanned_pages={report.suspected_scanned_pages}"
    )
```

In `_ingest()`, append report fields:

```python
    report = (
        f" {_format_pdf_intake_report(result.intake_report)}"
        if result.intake_report is not None
        else ""
    )
    print(
        f"run_id={result.run_id} run_state={result.run_state.value} "
        f"evidence_count={result.evidence_count}{report}"
    )
```

In `_run_get()`, after the Run line:

```python
    report = engine.get_pdf_intake_report(run_id)
    if report is not None:
        print(_format_pdf_intake_report(report))
```

- [x] **Step 5: Implement MCP report mapper and size guard**

In `src/mke/interfaces/mcp_contract.py`, add:

```python
_MAX_PDF_INPUT_BYTES = 100 * 1024 * 1024
```

After suffix detection:

```python
    if suffix == ".pdf" and input_path.stat().st_size > _MAX_PDF_INPUT_BYTES:
        return _failure(
            "input_file_too_large",
            "PDF input exceeds 100 MB limit",
            "choose_smaller_file",
        )
```

Add mapper:

```python
def _pdf_intake_report_payload(report: PdfIntakeReport) -> dict[str, Any]:
    return {
        "total_pages": report.total_pages,
        "extracted_pages": report.extracted_pages,
        "empty_pages": report.empty_pages,
        "total_extracted_chars": report.total_extracted_chars,
        "page_char_counts": list(report.page_char_counts),
        "suspected_scanned_pages": report.suspected_scanned_pages,
        "extraction_mode": report.extraction_mode,
        "failure_reason": report.failure_reason,
    }
```

In successful `ingest_file()` payload:

```python
        payload = {
            "ok": True,
            "run_id": result.run_id,
            "run_state": result.run_state.value,
            "evidence_count": result.evidence_count,
            "media_type": media_type,
            "active_publication_impact": (
                "changed" if result.run_state.value == "published" else "unchanged"
            ),
        }
        if result.intake_report is not None:
            payload["intake_report"] = _pdf_intake_report_payload(result.intake_report)
        return payload
```

In `get_run()`:

```python
        report = engine.get_pdf_intake_report(run_id)
        payload = {
            "ok": True,
            "run": {
                "run_id": run.run_id,
                "state": run.state.value,
                "source_generation": run.source_generation,
                "retry_of_run_id": run.retry_of_run_id,
            },
            "events": events,
        }
        if report is not None:
            payload["intake_report"] = _pdf_intake_report_payload(report)
        return payload
```

- [x] **Step 6: Run interface tests**

Run:

```bash
uv run pytest tests/interfaces/test_cli_pdf.py tests/interfaces/test_mcp_contract.py -q
```

Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add src/mke/cli.py src/mke/interfaces/mcp_contract.py tests/interfaces/test_cli_pdf.py tests/interfaces/test_mcp_contract.py
git commit -m "feat(interfaces): expose pdf intake summaries"
```

## Task 6: Smoke Harness And Documentation

**Files:**
- Create: `scripts/pdf_intake_smoke.py`
- Modify: `docs/reference/cli.md`
- Modify: `docs/reference/contracts.md`
- Modify: `docs/how-to/run-local-product-proof.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`

- [x] **Step 1: Add smoke harness**

Create `scripts/pdf_intake_smoke.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mke.adapters.pdf import PdfExtractionError, PyMuPDFPdfExtractor


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_dir", type=Path)
    args = parser.parse_args()
    extractor = PyMuPDFPdfExtractor()
    results = []
    for path in sorted(args.pdf_dir.glob("*.pdf")):
        try:
            result = extractor.extract(path)
            results.append(
                {
                    "file": path.name,
                    "status": "ok",
                    "total_pages": result.report.total_pages,
                    "extracted_pages": result.report.extracted_pages,
                    "suspected_scanned_pages": result.report.suspected_scanned_pages,
                    "total_extracted_chars": result.report.total_extracted_chars,
                }
            )
        except PdfExtractionError as error:
            report = error.report
            results.append(
                {
                    "file": path.name,
                    "status": "failed",
                    "failure_reason": str(error),
                    "total_pages": report.total_pages if report else 0,
                    "extracted_pages": report.extracted_pages if report else 0,
                    "suspected_scanned_pages": report.suspected_scanned_pages if report else 0,
                    "total_extracted_chars": report.total_extracted_chars if report else 0,
                }
            )
    print(json.dumps({"pdf_count": len(results), "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 2: Update docs**

Update docs to say:

- PDF ingest now uses PyMuPDF text-layer extraction.
- `mke ingest` and `mke run get` expose PDF intake summary fields.
- MCP `ingest_file` rejects PDFs above 100 MB.
- OCR, table extraction, layout-aware chunking, and Unicode retrieval remain outside D1.
- PyMuPDF dependency and license boundary are documented in ADR-0004.

- [x] **Step 3: Run doc checks**

Run:

```bash
rg -n "fixture-only PDF|uncompressed text showing operators|builtin-pdf-text-v1" README.md README_CN.md docs
```

Expected: no stale user-facing claim that the only PDF path is fixture-only. Internal historical plans may still mention old fingerprints if they are explicitly historical.

- [x] **Step 4: Commit**

```bash
git add scripts/pdf_intake_smoke.py README.md README_CN.md docs/README.md docs/reference/cli.md docs/reference/contracts.md docs/how-to/run-local-product-proof.md
git commit -m "docs(pdf): document real pdf intake workflow"
```

## Task 7: Final Verification And Review Preparation

**Files:**
- Modify: `docs/superpowers/plans/2026-06-16-real-pdf-intake-implementation.md`
- Optional create after review: `docs/superpowers/reviews/2026-06-16-real-pdf-intake-review.md`

- [x] **Step 1: Run full verification**

Run:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke demo --verify
```

Expected:

- tests pass,
- Ruff passes,
- Pyright reports 0 errors,
- build creates sdist/wheel,
- demo prints `result=passed`.

- [x] **Step 2: Run optional smoke harness**

If a local smoke PDF directory is available, run:

```bash
uv run python scripts/pdf_intake_smoke.py /path/to/local/pdf-directory
```

Commit only redacted aggregate results in the PR body. Do not commit source PDFs or local paths.

- [x] **Step 3: Update checklist**

Mark completed tasks in this plan from `- [ ]` to `- [x]` as they are finished. Do not mark future
items complete early.

- [x] **Step 4: Run pre-landing review**

Run the approved project review workflow against the full branch diff. Persist durable
public-neutral findings to:

```text
docs/superpowers/reviews/2026-06-16-real-pdf-intake-review.md
```

Only include review conclusions, actionable findings, and verification results. Do not include raw
GStack restore paths or private local paths.

- [x] **Step 5: Prepare Chinese PR body**

Use the project PR format:

```markdown
## Summary

D1 将 PDF intake 从 fixture-only 解析扩展为 PyMuPDF-backed text-layer extraction，并保持现有 Publication/Search/Ask 可信边界。

- 新增 PyMuPDF 依赖 ADR 和 adapter 边界。
- 新增 PdfIntakeReport，并在 CLI/MCP/Run inspection 暴露摘要。
- 保留旧 PDF fingerprint 兼容，新增 `pymupdf-text-v1`。
- MCP PDF ingest 增加 100 MB size guard。

## Completion

- [x] Text-layer PDF intake uses PyMuPDF.
- [x] `PdfIntakeReport` is returned for ingest and Run inspection.
- [x] Failed PDF extraction leaves active Publication unchanged.
- [x] OCR, table extraction, hybrid retrieval, and legacy code import remain out of scope.

## Verification

| Check | Result |
|---|---|
| `uv run pytest -q` | Replace this sentence with the exact passing test count before PR creation. |
| `uv run ruff check .` | Replace this sentence with the exact Ruff result before PR creation. |
| `uv run pyright` | Replace this sentence with the exact Pyright result before PR creation. |
| `uv build` | Replace this sentence with the exact build result before PR creation. |
| `uv run mke demo --verify` | Replace this sentence with the exact demo result before PR creation. |

## Scope

本 PR 不实现 OCR、layout-aware chunking、hybrid retrieval、rerank、HTTP、workspace UI 或 generative Ask。

## Risks / Migration

- User impact: PDF ingest can handle broader text-layer PDFs and reports extraction diagnostics.
- System impact: Adds PyMuPDF as an in-process adapter dependency.
- Compatibility impact: Existing PDF manifest fingerprint remains recognized.
- Rollback plan: Revert the adapter and dependency commit; existing Publication data remains protected by active Publication semantics.

## Documentation impact

- Updated ADR, CLI/MCP references, product proof docs, README files, and implementation history.
```

- [x] **Step 6: Stop for authorization**

Do not push, create PR, or merge without explicit user authorization.

## Implementation Handoff

Recommended execution mode: Subagent-Driven implementation in the project window.

Prompt for the execution window:

```text
Read AGENTS.md, docs/superpowers/specs/2026-06-16-real-pdf-intake-design.md,
docs/superpowers/reviews/2026-06-16-real-pdf-intake-autoplan-review.md,
docs/superpowers/reviews/2026-06-16-real-pdf-intake-eng-review.md, and
docs/superpowers/plans/2026-06-16-real-pdf-intake-implementation.md.

Execute the plan task-by-task using TDD. Keep PyMuPDF behind adapters/pdf, preserve
active-Publication-only Search and Ask, do not import legacy RAG-OCR runtime code, and do not add
OCR, hybrid retrieval, rerank, HTTP, workspace UI, or generative Ask.

After implementation, run:
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke demo --verify

Prepare a Chinese PR body using the project result-first format. Stop before push or PR unless
authorized.
```
