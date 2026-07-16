from __future__ import annotations

from pathlib import Path
from sqlite3 import OperationalError

import pytest
from pytest import CaptureFixture

from mke.adapters.sqlite import SQLiteStore
from mke.application import KnowledgeEngine, VideoIngestError
from mke.cli import main
from mke.interfaces.public_errors import (
    _ALLOWLISTED_CAUSES,  # pyright: ignore[reportPrivateUsage]
    PublicError,
    public_error_from_cause,
    render_public_error_line,
)


def test_shared_public_error_payload_and_allowlist_remain_unextended() -> None:
    payload = PublicError("problem", "cause", "next_step").payload()
    assert set(payload) == {
        "ok", "problem", "cause", "active_publication_impact", "next_step"
    }
    assert "schema_version" not in payload
    assert {
        "local Library has no active Publications",
        "active Publication provenance graph is invalid",
        "local Library database is unavailable or incompatible",
        "output directory must not already exist",
        "output parent is invalid",
        "active Library exceeds v1 export limits",
    }.isdisjoint(_ALLOWLISTED_CAUSES)


def test_library_export_error_model_rejects_unrelated_shared_cause() -> None:
    from pydantic import ValidationError

    from mke.interfaces.library_export import LibraryExportErrorV1

    with pytest.raises(ValidationError):
        LibraryExportErrorV1(
            ok=False,
            problem="library_export_failed",
            cause="question must not be empty",
            next_step="retry_library_export",
        )


@pytest.mark.parametrize(
    "cause",
    [
        "transcription optional dependency is not installed",
        "configured transcription model is not cached",
        "transcription model resolution failed",
        "transcript schema validation failed",
    ],
)
def test_transcription_setup_causes_are_public_allowlisted(cause: str) -> None:
    error = public_error_from_cause(
        cause,
        problem="video_ingest_failed",
        next_step="fix_input_or_retry",
    )

    assert error.cause == cause


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


def test_cli_preserves_typed_video_recovery_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    video = tmp_path / "input.mp4"
    video.write_bytes(b"fake mp4 bytes")

    def fail_with_typed_error(self: KnowledgeEngine, path: Path) -> object:
        raise VideoIngestError(
            "configured transcription model is not cached",
            problem="video_ingest_failed",
            next_step="run_transcription_prepare",
        )

    monkeypatch.setattr(KnowledgeEngine, "ingest_video", fail_with_typed_error)

    assert main(["--db", str(tmp_path / "mke.sqlite"), "ingest", str(video)]) == 1

    output = capsys.readouterr().out
    assert "cause=configured transcription model is not cached" in output
    assert "next_step=run_transcription_prepare" in output


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


@pytest.mark.parametrize("failure_method", ["ensure_source", "create_run"])
def test_cli_redacts_pre_run_storage_failure_without_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
    failure_method: str,
) -> None:
    video = tmp_path / "input.mp4"
    video.write_bytes(b"fake mp4 bytes")
    recovery_calls: list[str] = []

    def fail_with_sensitive_storage_error(*args: object, **kwargs: object) -> object:
        raise OperationalError(f"ESCAPED OperationalError {tmp_path}/mke.sqlite is unreadable")

    def record_recovery(self: SQLiteStore, run_id: str) -> None:
        recovery_calls.append(run_id)

    monkeypatch.setattr(
        KnowledgeEngine,
        failure_method,
        fail_with_sensitive_storage_error,
    )
    monkeypatch.setattr(SQLiteStore, "mark_run_failed", record_recovery)

    assert main(["--db", str(tmp_path / "mke.sqlite"), "ingest", str(video)]) == 1

    output = capsys.readouterr().out
    assert "problem=video_ingest_failed" in output
    assert "cause=video ingest initialization failed" in output
    assert "run_id=" not in output
    assert str(tmp_path) not in output
    assert "OperationalError" not in output
    assert "Traceback" not in output
    assert recovery_calls == []
