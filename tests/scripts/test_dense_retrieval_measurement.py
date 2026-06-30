from __future__ import annotations

import json
from pathlib import Path

import pytest

from mke.evaluation import dense_workflow
from mke.evaluation.dense_workflow import DenseWorkflowError
from scripts.dense_retrieval_measurement import main


def test_model_free_measurement_validates_without_model_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}", encoding="utf-8")
    protocol = tmp_path / "protocol.json"
    protocol.write_text("{}", encoding="utf-8")
    calls = 0

    def validate(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(
        "scripts.dense_retrieval_measurement.validate_dense_comparison_artifact",
        validate,
    )

    assert main(
        [
            "--repository",
            str(tmp_path),
            "--protocol",
            str(protocol),
            "--artifact",
            str(artifact),
            "--model-free",
        ]
    ) == 0
    assert calls == 1
    assert json.loads(capsys.readouterr().out) == {
        "mode": "model-free",
        "status": "passed",
    }


def test_measurement_rejects_model_cache_in_model_free_mode(
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--repository",
                str(tmp_path),
                "--protocol",
                str(tmp_path / "protocol.json"),
                "--artifact",
                str(tmp_path / "artifact.json"),
                "--model-free",
                "--model-cache",
                str(tmp_path / "cache"),
            ]
        )

    assert error.value.code == 2


def test_dense_record_writer_is_exclusive_and_preserves_existing_bytes(
    tmp_path: Path,
) -> None:
    target = tmp_path / "receipt.json"
    dense_workflow._write_exclusive_json(  # pyright: ignore[reportPrivateUsage]
        target, {"status": "first"}
    )
    before = target.read_bytes()

    with pytest.raises(DenseWorkflowError, match="already exists"):
        dense_workflow._write_exclusive_json(  # pyright: ignore[reportPrivateUsage]
            target, {"status": "second"}
        )

    assert target.read_bytes() == before
