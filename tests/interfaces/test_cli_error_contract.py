from __future__ import annotations

from pathlib import Path

import pytest
from pytest import CaptureFixture

from mke.application import KnowledgeEngine, VideoIngestError
from mke.cli import main
from mke.interfaces.public_errors import PublicError, render_public_error_line


def test_cli_error_renderer_uses_public_error_contract() -> None:
    error = PublicError(
        problem="invalid_question",
        cause="question must not be empty",
        next_step="provide_non_empty_question",
    )

    assert render_public_error_line(error) == (
        "problem=invalid_question cause=question must not be empty "
        "active_publication_impact=unchanged next_step=provide_non_empty_question"
    )


def test_error_contract_redacts_unrecognized_sensitive_cause(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    video = tmp_path / "input.mp4"
    video.write_bytes(b"fake mp4 bytes")

    def fail_with_sensitive_cause(self: KnowledgeEngine, path: Path) -> object:
        raise VideoIngestError("SECRET_TOKEN Traceback /Users/mac/private/file.py")

    monkeypatch.setattr(KnowledgeEngine, "ingest_video", fail_with_sensitive_cause)

    assert main(["--db", str(tmp_path / "mke.sqlite"), "ingest", str(video)]) == 1

    output = capsys.readouterr().out
    assert "cause=operation failed; details were redacted" in output
    assert "SECRET_TOKEN" not in output
    assert "Traceback" not in output
    assert "/Users/mac" not in output


def test_cli_redacts_video_hash_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    video = tmp_path / "disappeared-after-preflight.mp4"
    video.write_bytes(b"fake mp4 bytes")

    def fail_hash(path: Path) -> str:
        raise FileNotFoundError(f"Traceback: could not read {path}")

    monkeypatch.setattr("mke.application._sha256_file", fail_hash)

    assert main(["--db", str(tmp_path / "mke.sqlite"), "ingest", str(video)]) == 1

    output = capsys.readouterr().out
    assert "problem=video_ingest_failed" in output
    assert "cause=input video could not be read" in output
    assert str(video) not in output
    assert "Traceback" not in output
