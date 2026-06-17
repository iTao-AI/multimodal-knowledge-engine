from __future__ import annotations

from pathlib import Path

import pytest
from pytest import CaptureFixture

from mke.application import KnowledgeEngine, VideoIngestError
from mke.cli import main


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
