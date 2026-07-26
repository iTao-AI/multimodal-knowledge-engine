from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts/retrieval_order_installed_proof.py"
)


def _load() -> Any:
    spec = importlib.util.spec_from_file_location(
        "retrieval_order_installed_proof",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_help_requires_explicit_same_wheel_and_all_authority_inputs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    proof = _load()

    with pytest.raises(SystemExit) as raised:
        proof.main(["--help"])

    assert raised.value.code == 0
    output = capsys.readouterr().out
    for option in (
        "--mke-wheel",
        "--candidate-receipt",
        "--protocol",
        "--development-freeze",
        "--holdout-receipt",
        "--artifact",
        "--compatibility",
    ):
        assert option in output
    assert "explicit prebuilt wheel only" in output
    assert "never rebuilds or discovers a wheel" in output


def test_installed_proof_uses_exact_same_wheel_without_build_or_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    proof = _load()
    inputs = _synthetic_inputs(tmp_path)
    commands: list[list[str]] = []

    def run(
        command: Sequence[str],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout_seconds: float,
    ) -> Any:
        del cwd, env, timeout_seconds
        argv = list(command)
        commands.append(argv)
        if argv[:2] == ["uv", "venv"]:
            environment = Path(argv[2])
            installed = environment / "bin/python"
            installed.parent.mkdir(parents=True)
            installed.write_bytes(b"synthetic installed python")
            return proof.CommandResult(0, b"", b"")
        if argv[:3] == ["uv", "pip", "install"]:
            return proof.CommandResult(0, b"", b"")
        environment = Path(argv[0]).parents[1]
        payload = {
            "distribution_version": "0.1.4",
            "module_file": str(
                environment / "lib/python/site-packages/mke/__init__.py"
            ),
            "strategy_revision": 2,
            "query_policy_revision": 1,
            "artifact_validator": True,
            "compatibility_validator": True,
        }
        return proof.CommandResult(
            0,
            json.dumps(payload).encode(),
            b"",
        )

    monkeypatch.setattr(proof, "_run", run)

    assert proof.main([*inputs["argv"], "--json"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["schema_version"] == (
        "mke.retrieval_order_installed_proof_result.v1"
    )
    assert result["status"] == "passed"
    assert result["mode"] == "installed_proof"
    assert result["authority_layer"] == "same_wheel_external_store"
    assert result["problem"] == "none"
    assert result["wheel_sha256"] == inputs["wheel_sha256"]
    assert len(
        [command for command in commands if command[:3] == ["uv", "pip", "install"]]
    ) == 2
    installs = [
        command for command in commands
        if command[:3] == ["uv", "pip", "install"]
    ]
    assert all(command[-1] == str(inputs["wheel"]) for command in installs)
    assert not any(command[:2] == ["uv", "build"] for command in commands)
    assert not any("*" in argument for command in commands for argument in command)


@pytest.mark.parametrize(
    "tamper",
    (
        "missing_wheel",
        "multiple_wheels",
        "wrong_filename",
        "wheel_digest",
        "candidate_seal",
    ),
)
def test_installed_proof_rejects_preflight_without_running_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tamper: str,
) -> None:
    proof = _load()
    inputs = _synthetic_inputs(tmp_path)
    if tamper == "missing_wheel":
        inputs["wheel"].unlink()
    elif tamper == "multiple_wheels":
        inputs["wheel"].with_name("unexpected.whl").write_bytes(b"other")
    else:
        receipt_path = inputs["receipt"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if tamper == "wrong_filename":
            receipt["wheel_filename"] = "other.whl"
        elif tamper == "wheel_digest":
            receipt["wheel_sha256"] = "0" * 64
        else:
            artifact = json.loads(
                inputs["artifact"].read_text(encoding="utf-8")
            )
            artifact["candidate_seal"]["head"] = "0" * 40
            inputs["artifact"].write_text(
                json.dumps(artifact),
                encoding="utf-8",
            )
        if tamper != "candidate_seal":
            receipt_path.write_text(
                json.dumps(receipt),
                encoding="utf-8",
            )

    def forbidden(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("preflight must not run commands")

    monkeypatch.setattr(proof, "_run", forbidden)

    assert proof.main([*inputs["argv"], "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "failed"
    assert result["problem"] in {
        "retrieval_order_proof_preflight_invalid",
        "retrieval_order_shared_wheel_mismatch",
    }
    assert result["output_state"] == "not_applicable"
    assert result["publication_outcome"] == "not_attempted"


def _synthetic_inputs(tmp_path: Path) -> dict[str, Any]:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    wheel = (
        candidate
        / "multimodal_knowledge_engine-0.1.4-py3-none-any.whl"
    )
    wheel.write_bytes(b"synthetic prebuilt wheel")
    wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
    candidate_seal = {
        "head": "a" * 40,
        "runtime_profile": {
            "python": "3.13",
            "sqlite": "3.51.1",
            "sqlite_source_id": "synthetic",
            "sqlite_compile_options": ["ENABLE_FTS5"],
            "fts5_rank_configuration": "sqlite_fts5_default_bm25",
            "strategy_revision": 2,
            "query_policy_revision": 1,
        },
    }
    receipt: dict[str, object] = {
        "schema_version": "mke.candidate_artifact_receipt.v1",
        "repository": "iTao-AI/multimodal-knowledge-engine",
        "source_commit": candidate_seal["head"],
        "package_name": "multimodal-knowledge-engine",
        "package_version": "0.1.4",
        "wheel_filename": wheel.name,
        "wheel_bytes": len(wheel.read_bytes()),
        "wheel_sha256": wheel_sha256,
        "requires_python": ">=3.12,<3.14",
        "consumer_proof_schema": "mke.consumer_source_pack_proof.v1",
        "consumer_proof_status": "passed",
        "proof_input_wheel_sha256": wheel_sha256,
    }
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    receipt_path = candidate / "candidate-artifact-receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    copied = tmp_path / "inputs"
    copied.mkdir()
    protocol = copied / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "schema_version": "mke.retrieval_order_protocol.v1",
                "protocol_id": "retrieval-order-v1",
            }
        ),
        encoding="utf-8",
    )
    protocol_sha = hashlib.sha256(protocol.read_bytes()).hexdigest()
    development = copied / "development-freeze.json"
    development_payload = {
        "schema_version": "mke.retrieval_order_development_freeze.v1",
        "protocol": {"sha256": protocol_sha},
        "candidate_seal": candidate_seal,
        "development_status": "passed",
        "holdout_status": "not_observed",
    }
    development.write_text(
        json.dumps(development_payload),
        encoding="utf-8",
    )
    holdout = copied / "holdout-receipt.json"
    holdout_payload = {
        "schema_version": "mke.retrieval_order_holdout_receipt.v1",
        "protocol": {"sha256": protocol_sha},
        "candidate_seal": candidate_seal,
        "development_freeze": {
            "sha256": hashlib.sha256(
                development.read_bytes()
            ).hexdigest()
        },
        "attempt_status": "started",
    }
    holdout.write_text(json.dumps(holdout_payload), encoding="utf-8")
    artifact = copied / "retrieval-order-artifact.json"
    artifact_payload = {
        "schema_version": "mke.retrieval_order_artifact.v1",
        "protocol": {"sha256": protocol_sha},
        "candidate_seal": candidate_seal,
        "development_freeze": {
            "sha256": hashlib.sha256(
                development.read_bytes()
            ).hexdigest()
        },
        "holdout_receipt": {
            "sha256": hashlib.sha256(holdout.read_bytes()).hexdigest()
        },
        "development_status": "passed",
        "holdout_status": "observed",
        "integrity_status": "passed",
        "runtime_promotion_status": "not_evaluated",
        "observation": {"observation_status": "passed"},
    }
    artifact.write_text(json.dumps(artifact_payload), encoding="utf-8")
    compatibility = copied / "compatibility.json"
    compatibility_payload = {
        "schema_version": "mke.retrieval_order_compatibility.v1",
        "integrity_status": "passed",
        "compatibility_status": "passed",
        "historical_bytes_frozen": "passed",
        "archived_record_self_consistent": "passed",
        "current_runtime_replay_compatible": "passed",
        "revision_2_differential_valid": "passed",
        "canonical_authority": {
            "candidate_seal": candidate_seal,
            "development_freeze": {
                "sha256": hashlib.sha256(
                    development.read_bytes()
                ).hexdigest()
            },
            "holdout_receipt": {
                "sha256": hashlib.sha256(
                    holdout.read_bytes()
                ).hexdigest()
            },
            "retrieval_artifact": {
                "sha256": hashlib.sha256(
                    artifact.read_bytes()
                ).hexdigest()
            },
        },
    }
    compatibility.write_text(
        json.dumps(compatibility_payload),
        encoding="utf-8",
    )
    interpreters = (tmp_path / "python312", tmp_path / "python313")
    for interpreter in interpreters:
        interpreter.write_bytes(b"synthetic interpreter")
        interpreter.chmod(0o755)
    argv = [
        "--python",
        str(interpreters[0]),
        "--python",
        str(interpreters[1]),
        "--mke-wheel",
        str(wheel),
        "--candidate-receipt",
        str(receipt_path),
        "--protocol",
        str(protocol),
        "--development-freeze",
        str(development),
        "--holdout-receipt",
        str(holdout),
        "--artifact",
        str(artifact),
        "--compatibility",
        str(compatibility),
    ]
    return {
        "argv": argv,
        "wheel": wheel,
        "wheel_sha256": wheel_sha256,
        "receipt": receipt_path,
        "artifact": artifact,
    }


def _canonical_sha256(value: dict[str, object]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
