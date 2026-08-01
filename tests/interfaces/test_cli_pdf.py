from pathlib import Path

import pytest
from pytest import CaptureFixture, MonkeyPatch

import mke.cli
from mke.application import KnowledgeEngine
from mke.cli import main
from tests.conftest import PDF_FIXTURES

NUMERIC_FIXTURE = Path("tests/fixtures/retrieval-numeric-v1/development.pdf")


def test_cli_pdf_report_insert_failure_is_redacted_with_run_id(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: MonkeyPatch,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    engine = KnowledgeEngine(db_path)
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
    engine._store._connection.executescript(  # pyright: ignore[reportPrivateUsage]
        """
        CREATE TRIGGER fail_pdf_report
        BEFORE INSERT ON pdf_intake_reports
        BEGIN
          SELECT RAISE(ABORT, 'injected sqlite trigger SYNTHETIC_TRIGGER_PATH');
        END;
        """
    )
    engine._store._connection.commit()  # pyright: ignore[reportPrivateUsage]

    def build(_config: object) -> KnowledgeEngine:
        return engine

    monkeypatch.setattr(mke.cli, "build_engine", build)

    assert (
        main(["--db", str(db_path), "ingest", str(PDF_FIXTURES / "text-layer-revised.pdf")])
        == 1
    )

    output = capsys.readouterr().out
    assert "problem=pdf_ingest_failed" in output
    assert "cause=operation failed; details were redacted" in output
    assert "active_publication_impact=unchanged" in output
    assert "next_step=fix_input_or_retry" in output
    assert "run_id=run_" in output
    assert "injected sqlite trigger" not in output
    assert "SYNTHETIC_TRIGGER_PATH" not in output
    assert "Traceback" not in output


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
    invalid = tmp_path / "not-a-pdf.pdf"
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


def test_cli_search_uses_numeric_grouping_default_and_current_rollback(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    assert main(["--db", str(db_path), "ingest", str(NUMERIC_FIXTURE)]) == 0
    capsys.readouterr()

    assert main(["--db", str(db_path), "search", "410000 grouped daily withdrawal"]) == 0
    assert "page=1" in capsys.readouterr().out

    assert (
        main(
            [
                "--db",
                str(db_path),
                "--retrieval-query-policy",
                "current",
                "search",
                "410000 grouped daily withdrawal",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == ""


def test_cli_invalid_retrieval_policy_is_usage_error_before_engine_construction(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    def fail_build(config: object) -> object:
        raise AssertionError("engine construction must not run")

    monkeypatch.setattr(mke.cli, "build_engine", fail_build)

    with pytest.raises(SystemExit) as raised:
        main(
            [
                "--db",
                str(tmp_path / "mke.sqlite"),
                "--retrieval-query-policy",
                "unknown",
                "search",
                "query",
            ]
        )

    assert raised.value.code == 2
    error = capsys.readouterr().err
    assert "invalid choice: 'unknown'" in error
    assert "--retrieval-query-policy" in error


def test_cli_eval_rejects_retrieval_policy_override(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(
            [
                "--retrieval-query-policy",
                "current",
                "eval",
                "retrieval",
                "--manifest",
                "tests/fixtures/retrieval-eval-v1.json",
            ]
        )

    assert raised.value.code == 2
    assert (
        "eval uses protocol-owned retrieval policy; "
        "--retrieval-query-policy is not supported"
    ) in capsys.readouterr().err
