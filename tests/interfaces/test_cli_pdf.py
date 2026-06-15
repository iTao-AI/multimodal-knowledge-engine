from pathlib import Path

from pytest import CaptureFixture

from mke.cli import main

FIXTURES = Path(__file__).parents[1] / "fixtures" / "pdf"


def test_cli_ingest_and_search_pdf(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    db_path = tmp_path / "mke.sqlite"

    assert main(["--db", str(db_path), "ingest", str(FIXTURES / "text-layer.pdf")]) == 0
    ingest_output = capsys.readouterr().out
    assert "run_state=published" in ingest_output
    assert "evidence_count=2" in ingest_output

    assert main(["--db", str(db_path), "search", "publication active"]) == 0
    search_output = capsys.readouterr().out
    assert "page=2" in search_output
    assert "Publication search returns only active page two." in search_output
