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
