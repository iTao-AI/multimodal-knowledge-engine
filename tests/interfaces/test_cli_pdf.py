from pathlib import Path

from pytest import CaptureFixture

from mke.cli import main
from tests.conftest import PDF_FIXTURES


def test_cli_ingest_and_search_pdf(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    db_path = tmp_path / "mke.sqlite"

    assert main(["--db", str(db_path), "ingest", str(PDF_FIXTURES / "text-layer.pdf")]) == 0
    ingest_output = capsys.readouterr().out
    assert "run_state=published" in ingest_output
    assert "evidence_count=2" in ingest_output

    assert main(["--db", str(db_path), "search", "publication active"]) == 0
    search_output = capsys.readouterr().out
    assert "page=2" in search_output
    assert "Publication search returns only active page two." in search_output


def test_cli_ingest_invalid_pdf_returns_error(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    db_path = tmp_path / "mke.sqlite"
    invalid = tmp_path / "not-a-pdf.txt"
    invalid.write_text("not a pdf")

    assert main(["--db", str(db_path), "ingest", str(invalid)]) == 1
    assert "problem=pdf_ingest_failed" in capsys.readouterr().out


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
