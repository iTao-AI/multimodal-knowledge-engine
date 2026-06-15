from pathlib import Path

from pytest import CaptureFixture

from mke.cli import main
from tests.conftest import PDF_FIXTURES


def test_cli_run_get_prints_state_and_events(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    db_path = tmp_path / "mke.sqlite"
    assert main(["--db", str(db_path), "ingest", str(PDF_FIXTURES / "text-layer.pdf")]) == 0
    ingest_output = capsys.readouterr().out
    run_id = ingest_output.split()[0].split("=", 1)[1]

    assert main(["--db", str(db_path), "run", "get", run_id]) == 0

    output = capsys.readouterr().out
    assert f"run_id={run_id}" in output
    assert "state=published" in output
    assert "event=run_created" in output
    assert "event=publication_activated" in output


def test_cli_error_contract_for_invalid_pdf(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    db_path = tmp_path / "mke.sqlite"
    invalid = tmp_path / "invalid.pdf"
    invalid.write_text("not a pdf")

    assert main(["--db", str(db_path), "ingest", str(invalid)]) == 1

    output = capsys.readouterr().out
    assert "problem=pdf_ingest_failed" in output
    assert "cause=input is not a valid PDF" in output
    assert "active_publication_impact=unchanged" in output
    assert "next_step=fix_input_or_retry" in output


def test_demo_verify_outputs_phases_and_cleans_up(capsys: CaptureFixture[str]) -> None:
    assert main(["demo", "--verify"]) == 0

    output = capsys.readouterr().out
    assert "mke demo --verify" in output
    assert "phase=ingest_initial status=ok" in output
    assert "phase=failed_reprocess status=ok active_publication_impact=unchanged" in output
    assert "phase=retry_publish status=ok" in output
    assert "phase=cleanup status=ok" in output
    assert "result=passed" in output


def test_demo_verify_failure_exit_code_for_missing_fixture(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.pdf"

    assert main(["demo", "--verify", "--fixture", str(missing)]) == 1

    output = capsys.readouterr().out
    assert "problem=pdf_ingest_failed" in output
    assert "cause=demo fixture is missing" in output
    assert "active_publication_impact=unchanged" in output
    assert "next_step=fix_input_or_retry" in output


def test_cli_run_get_nonexistent_id_returns_error_contract(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    # create a minimal database file so KnowledgeEngine can open it
    import sqlite3

    sqlite3.connect(db_path).close()

    assert main(["--db", str(db_path), "run", "get", "run_nonexistent"]) == 1

    output = capsys.readouterr().out
    assert "problem=pdf_ingest_failed" in output
    assert "cause=unknown run: run_nonexistent" in output
    assert "active_publication_impact=unchanged" in output
    assert "next_step=fix_input_or_retry" in output
