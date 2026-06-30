from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pytest import CaptureFixture

from mke.cli import main

PROTOCOL = Path("tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json")
CANDIDATE = "cjk-relevance-gate-reranker-v1"


def test_cli_eval_relevance_gate_development_dispatches_freeze(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def run_development(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "candidate_status": "completed",
            "development_status": "passed",
            "holdout_status": "not_observed",
            "runtime_promotion_status": "not_evaluated",
            "selected_profile": "strict-constraint",
        }

    def record_freeze(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return cast(dict[str, object], kwargs["report"])

    monkeypatch.setattr("mke.cli.run_relevance_gate_development", run_development)
    monkeypatch.setattr(
        "mke.cli.record_relevance_gate_development_freeze",
        record_freeze,
    )
    freeze = tmp_path / "freeze.json"

    assert main(
        [
            "eval",
            "retrieval-relevance-gate",
            "--protocol",
            str(PROTOCOL),
            "--candidate",
            CANDIDATE,
            "--development-only",
            "--record-development-freeze",
            str(freeze),
            "--json",
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["development_status"] == "passed"
    assert payload["runtime_promotion_status"] == "not_evaluated"
    assert captured["protocol_path"] == PROTOCOL
    assert captured["target_path"] == freeze


@pytest.mark.parametrize(
    "argv",
    (
        ["--development-only"],
        ["--record-development-freeze", "freeze.json"],
        ["--development-freeze", "freeze.json", "--record", "artifact.json"],
        [
            "--development-only",
            "--record-development-freeze",
            "freeze.json",
            "--record",
            "artifact.json",
        ],
    ),
)
def test_cli_eval_relevance_gate_rejects_incompatible_phase_flags(
    capsys: CaptureFixture[str],
    argv: list[str],
) -> None:
    base = [
        "eval",
        "retrieval-relevance-gate",
        "--protocol",
        str(PROTOCOL),
        "--candidate",
        CANDIDATE,
    ]

    with pytest.raises(SystemExit) as error:
        main([*base, *argv])

    assert error.value.code == 2
    assert "incomplete or incompatible" in capsys.readouterr().err


def test_cli_eval_relevance_gate_holdout_dispatches_all_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def run_holdout(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "candidate_status": "completed",
            "development_status": "passed",
            "holdout_status": "observed",
            "runtime_promotion_status": "not_evaluated",
            "selected_profile": "strict-constraint",
            "holdout": {"holdout_gate_status": "failed"},
        }

    monkeypatch.setattr("mke.cli.run_relevance_gate_holdout", run_holdout)
    freeze = tmp_path / "freeze.json"
    artifact = tmp_path / "artifact.json"
    receipt = tmp_path / "receipt.json"

    assert main(
        [
            "eval",
            "retrieval-relevance-gate",
            "--protocol",
            str(PROTOCOL),
            "--candidate",
            CANDIDATE,
            "--development-freeze",
            str(freeze),
            "--record",
            str(artifact),
            "--record-holdout-receipt",
            str(receipt),
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "candidate_status=completed" in output
    assert "holdout_status=observed" in output
    assert "runtime_promotion_status=not_evaluated" in output
    assert "holdout_gate_status=failed" in output
    assert captured["development_freeze_path"] == freeze
    assert captured["record_path"] == artifact
    assert captured["holdout_receipt_path"] == receipt


def test_cli_eval_relevance_gate_invalid_candidate_is_usage_error(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "eval",
                "retrieval-relevance-gate",
                "--protocol",
                str(PROTOCOL),
                "--candidate",
                "shortcut",
                "--development-only",
                "--record-development-freeze",
                "freeze.json",
            ]
        )

    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_cli_eval_relevance_gate_failure_is_stable_public_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    def fail_development(**kwargs: object) -> dict[str, object]:
        del kwargs
        raise RuntimeError(f"Traceback SECRET {tmp_path}/private.json")

    monkeypatch.setattr("mke.cli.run_relevance_gate_development", fail_development)

    assert main(
        [
            "eval",
            "retrieval-relevance-gate",
            "--protocol",
            str(PROTOCOL),
            "--candidate",
            CANDIDATE,
            "--development-only",
            "--record-development-freeze",
            str(tmp_path / "freeze.json"),
            "--json",
        ]
    ) == 1

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["failure"]["problem"] == "relevance_gate_evaluation_failed"
    assert payload["runtime_promotion_status"] == "not_evaluated"
    assert "Traceback" not in output.out
    assert "SECRET" not in output.out
    assert str(tmp_path) not in output.out


def test_cli_eval_relevance_gate_rejects_runtime_strategy_override(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--retrieval-strategy",
                "current",
                "eval",
                "retrieval-relevance-gate",
                "--protocol",
                str(PROTOCOL),
                "--candidate",
                CANDIDATE,
                "--development-only",
                "--record-development-freeze",
                "freeze.json",
            ]
        )

    assert error.value.code == 2
    assert "--retrieval-strategy is not supported" in capsys.readouterr().err
