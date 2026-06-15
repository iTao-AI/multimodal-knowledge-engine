from pathlib import Path

from pytest import CaptureFixture

from mke.cli import main
from tests.conftest import PDF_FIXTURES, VIDEO_FIXTURES


def test_cli_ingest_video_and_search_timestamp_evidence(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"

    assert main(["--db", str(db_path), "ingest", str(VIDEO_FIXTURES / "short-audio.mp4")]) == 0
    ingest_output = capsys.readouterr().out
    assert "run_state=published" in ingest_output
    assert "evidence_count=2" in ingest_output

    assert main(["--db", str(db_path), "search", "timestamp proof"]) == 0
    search_output = capsys.readouterr().out
    assert "timestamp_ms=1200..2200" in search_output
    assert "Active publication search finds spoken timestamp proof." in search_output


def test_cli_error_contract_for_invalid_video(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    db_path = tmp_path / "mke.sqlite"
    video = tmp_path / "bad.mp4"
    video.write_bytes(b"fake mp4 bytes")
    video.with_suffix(video.suffix + ".mke-transcript.json").write_text("{}")

    assert main(["--db", str(db_path), "ingest", str(video)]) == 1

    output = capsys.readouterr().out
    assert "problem=video_ingest_failed" in output
    assert "active_publication_impact=unchanged" in output
    assert "next_step=fix_input_or_retry" in output


def test_demo_verify_proves_pdf_and_video(capsys: CaptureFixture[str]) -> None:
    assert main(
        [
            "demo",
            "--verify",
            "--fixture",
            str(PDF_FIXTURES / "text-layer.pdf"),
            "--video-fixture",
            str(VIDEO_FIXTURES / "short-audio.mp4"),
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "phase=ingest_initial status=ok" in output
    assert "phase=ingest_video status=ok" in output
    assert "video_evidence_count=2" in output
    assert "result=passed" in output


def test_demo_verify_missing_video_fixture_returns_video_error_contract(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.mp4"

    assert main(["demo", "--verify", "--video-fixture", str(missing)]) == 1

    output = capsys.readouterr().out
    assert "problem=video_ingest_failed" in output
    assert "cause=demo video fixture is missing" in output
    assert "active_publication_impact=unchanged" in output
    assert "next_step=fix_input_or_retry" in output
