from __future__ import annotations

import json
from pathlib import Path

import pytest

from mke.cli import main
from mke.embeddings.contracts import MODEL_ID, MODEL_REVISION
from mke.embeddings.readiness import (
    EmbeddingPreparationResult,
    EmbeddingReadiness,
    ReadinessCheck,
)


def test_embedding_prepare_requires_explicit_download_permission() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["embedding", "prepare"])

    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    "arguments",
    [
        ["--model", "main"],
        ["--model", "BAAI/bge-m3"],
        ["--model-revision", "main"],
    ],
)
def test_embedding_commands_reject_non_allowlisted_identity_before_runtime(
    arguments: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_prepare(**kwargs: object) -> EmbeddingPreparationResult:
        pytest.fail("invalid identity must fail before model lifecycle")

    monkeypatch.setattr("mke.cli.prepare_embedding", fail_prepare)

    with pytest.raises(SystemExit) as exc_info:
        main(["embedding", "prepare", "--allow-model-download", *arguments])

    assert exc_info.value.code == 2


def test_embedding_prepare_json_has_exact_identity_without_cache_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache = tmp_path / "cache"

    def fake_prepare(**kwargs: object) -> EmbeddingPreparationResult:
        assert kwargs == {
            "cache_dir": cache.resolve(),
            "model": MODEL_ID,
            "revision": MODEL_REVISION,
            "allow_model_download": True,
        }
        return EmbeddingPreparationResult(
            status="already_cached",
            model_id=MODEL_ID,
            model_revision=MODEL_REVISION,
            snapshot_fingerprint="sha256:" + "a" * 64,
        )

    monkeypatch.setattr("mke.cli.prepare_embedding", fake_prepare)

    assert (
        main(
            [
                "embedding",
                "prepare",
                "--allow-model-download",
                "--model-cache",
                str(cache),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "status": "already_cached",
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "snapshot_fingerprint": "sha256:" + "a" * 64,
    }
    assert str(cache) not in repr(payload)


def test_embedding_doctor_is_cache_only_and_uses_stable_exit_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache = tmp_path / "cache"

    def fake_doctor(**kwargs: object) -> EmbeddingReadiness:
        assert kwargs == {
            "cache_dir": cache.resolve(),
            "model": MODEL_ID,
            "revision": MODEL_REVISION,
        }
        return EmbeddingReadiness(
            status="not_ready",
            model_id=MODEL_ID,
            model_revision=MODEL_REVISION,
            snapshot_fingerprint=None,
            checks=(ReadinessCheck("model", "failed", "model snapshot unavailable"),),
            cause="configured embedding model is not cached",
            next_step="run_embedding_prepare",
        )

    monkeypatch.setattr("mke.cli.doctor_embedding", fake_doctor)

    assert (
        main(
            [
                "embedding",
                "doctor",
                "--model-cache",
                str(cache),
                "--json",
            ]
        )
        == 1
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "not_ready"
    assert payload["cause"] == "configured embedding model is not cached"
    assert payload["next_step"] == "run_embedding_prepare"
    assert str(cache) not in repr(payload)


def test_embedding_cache_inside_repository_is_usage_error_without_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "embedding",
                "doctor",
                "--model-cache",
                "./embedding-cache",
                "--json",
            ]
        )

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "outside the repository" in captured.err
    assert "Traceback" not in captured.err
