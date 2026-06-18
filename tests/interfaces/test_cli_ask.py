from pathlib import Path

from pytest import CaptureFixture

from mke.cli import main
from tests.conftest import PDF_FIXTURES, VIDEO_FIXTURES


def test_cli_ask_returns_evidence_packet(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    db_path = tmp_path / "mke.sqlite"

    assert main(["--db", str(db_path), "ingest", str(PDF_FIXTURES / "text-layer.pdf")]) == 0
    capsys.readouterr()

    assert main(["--db", str(db_path), "ask", "publication active"]) == 0

    output = capsys.readouterr().out
    assert "answer_status=evidence_found" in output
    assert "evidence_count=1" in output
    assert 'summary="1 active Evidence item matched the search terms."' in output
    assert "page=2" in output
    assert "Publication search returns only active page two." in output


def test_cli_ask_returns_video_timestamp_evidence(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"

    assert main(["--db", str(db_path), "ingest", str(VIDEO_FIXTURES / "short-audio.mp4")]) == 0
    capsys.readouterr()

    assert main(["--db", str(db_path), "ask", "timestamp"]) == 0

    output = capsys.readouterr().out
    assert "answer_status=evidence_found" in output
    assert "evidence_count=2" in output
    assert "timestamp_ms=0..1200" in output
    assert "timestamp_ms=1200..2200" in output
    assert "Active publication search finds spoken timestamp proof." in output


def test_cli_ask_returns_insufficient_evidence(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"

    assert main(["--db", str(db_path), "ingest", str(PDF_FIXTURES / "text-layer.pdf")]) == 0
    capsys.readouterr()

    assert main(["--db", str(db_path), "ask", "audio diarization"]) == 0

    output = capsys.readouterr().out
    assert "answer_status=insufficient_evidence" in output
    assert "evidence_count=0" in output
    assert 'summary="No active Evidence matched the search terms."' in output


def test_cli_ask_invalid_question_returns_error_contract(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"

    assert main(["--db", str(db_path), "ask", "发布时间？"]) == 1

    output = capsys.readouterr().out
    assert "problem=invalid_question" in output
    assert "cause=question must contain at least one searchable ASCII token" in output
    assert "active_publication_impact=unchanged" in output
    assert "next_step=provide_searchable_question" in output


def test_cli_ask_overlong_question_preserves_stable_cause(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"

    assert main(["--db", str(db_path), "ask", "a" * 1001]) == 1

    output = capsys.readouterr().out
    assert "problem=invalid_question" in output
    assert "cause=question must be 1000 characters or fewer" in output
    assert "details were redacted" not in output
    assert "next_step=shorten_question" in output
