from __future__ import annotations

import hashlib
import inspect
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from scripts import direct_audio_deployment_proof as proof


def _config(tmp_path: Path) -> proof.DirectAudioProofConfig:
    paths: dict[str, Path] = {}
    for name in (
        "python312",
        "python313",
        "multimodal_knowledge_engine-0.1.3-py3-none-any.whl",
        "receipt.json",
        "constraints.txt",
    ):
        path = tmp_path / name
        path.write_bytes(name.encode("ascii"))
        paths[name] = path
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    model_root = tmp_path / "model-cache"
    model_root.mkdir()
    fixture_root = tmp_path / "fixtures"
    fixture_root.mkdir()
    for name in ("direct-audio.mp3", "direct-audio.wav", "direct-audio.m4a"):
        (fixture_root / name).write_bytes(name.encode("ascii"))
    return proof.DirectAudioProofConfig(
        interpreters=(paths["python312"], paths["python313"]),
        mke_wheel=paths["multimodal_knowledge_engine-0.1.3-py3-none-any.whl"],
        dependency_receipt=paths["receipt.json"],
        wheelhouse=wheelhouse,
        constraints=paths["constraints.txt"],
        model_root=model_root,
        fixture_root=fixture_root,
        direct_audio_footprint_bytes=4096,
        direct_audio_footprint_budget_mode="baseline_plus",
    )


def _cli_args(config: proof.DirectAudioProofConfig) -> list[str]:
    return [
        "--python",
        str(config.interpreters[0]),
        "--python",
        str(config.interpreters[1]),
        "--mke-wheel",
        str(config.mke_wheel),
        "--dependency-receipt",
        str(config.dependency_receipt),
        "--wheelhouse",
        str(config.wheelhouse),
        "--constraints",
        str(config.constraints),
        "--model-root",
        str(config.model_root),
        "--fixture-root",
        str(config.fixture_root),
        "--direct-audio-footprint-bytes",
        "4096",
        "--direct-audio-footprint-budget-mode",
        "baseline_plus",
    ]


def _manifest(config: proof.DirectAudioProofConfig) -> proof.AuthorizationManifest:
    wheel = config.mke_wheel.read_bytes()
    constraints = config.constraints.read_bytes()
    wheelhouse = proof._observed_wheel_manifest(  # pyright: ignore[reportPrivateUsage]
        config.wheelhouse
    )
    fixtures = tuple(
        (
            name,
            len((config.fixture_root / name).read_bytes()),
            proof._sha256(  # pyright: ignore[reportPrivateUsage]
                (config.fixture_root / name).read_bytes()
            ),
        )
        for name in ("direct-audio.m4a", "direct-audio.mp3", "direct-audio.wav")
    )
    consumer = Path(proof.__file__).parent / "compiled_library_export_consumer_v2.py"
    return proof.AuthorizationManifest(
        mke_wheel_sha256=proof._sha256(wheel),  # pyright: ignore[reportPrivateUsage]
        mke_wheel_bytes=len(wheel),
        dependency_receipt_sha256="b" * 64,
        dependency_receipt_payload_sha256="c" * 64,
        wheelhouse_manifest_sha256=proof._sha256(  # pyright: ignore[reportPrivateUsage]
            proof._canonical(list(wheelhouse))  # pyright: ignore[reportPrivateUsage]
        ),
        constraints_sha256=proof._sha256(  # pyright: ignore[reportPrivateUsage]
            constraints
        ),
        interpreters=(
            ("3.12", "3.12.13", "8" * 64),
            ("3.13", "3.13.13", "9" * 64),
        ),
        package_sets=(
            ("3.12", (("multimodal-knowledge-engine", "0.1.3"),)),
            ("3.13", (("multimodal-knowledge-engine", "0.1.3"),)),
        ),
        model_identifier="Systran/faster-whisper-small",
        model_revision=proof.DEFAULT_MODEL_REVISION,
        model_tree_sha256="f" * 64,
        model_files=(("README.md", 1, "1" * 64), ("LICENSE", 1, "2" * 64)),
        consumer_sha256=proof._sha256(  # pyright: ignore[reportPrivateUsage]
            consumer.read_bytes()
        ),
        fixtures=fixtures,
        retained_inputs_sha256="6" * 64,
        estimated_temporary_disk_bytes=1000,
        temporary_disk_estimate_method="test_only_fixed_inputs",
        deny_network_method="darwin-sandbox-deny-network",
        cleanup_owner="call_owned_recursive_removal",
        direct_audio_footprint_bytes=4096,
        direct_audio_footprint_budget_mode="baseline_plus",
    )


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[proof.CommandCall] = []

    def run(self, call: proof.CommandCall) -> proof.CommandResult:
        self.calls.append(call)
        step = call.step
        if step.startswith("probe-python-"):
            version = step.removeprefix("probe-python-")
            return proof.CommandResult(0, json.dumps({"python_version": version}).encode(), b"")
        if step == "network-canary":
            return proof.CommandResult(0, b'{"status":"blocked"}', b"")
        if step == "doctor":
            return proof.CommandResult(0, b'{"status":"ready"}', b"")
        if step == "installed-identity":
            return proof.CommandResult(
                0,
                json.dumps(
                    {
                        "distribution": "multimodal-knowledge-engine",
                        "mke_file": "/call-owned/venv/lib/python/site-packages/mke/__init__.py",
                        "python": "/call-owned/venv/bin/python",
                        "wheel_sha256": "a" * 64,
                        "repository_import": False,
                    }
                ).encode(),
                b"",
            )
        if step.startswith(("python-", "cli-", "mcp-")):
            return proof.CommandResult(0, json.dumps(_product_result(step)).encode(), b"")
        if step.startswith("export-"):
            return proof.CommandResult(
                0,
                json.dumps(
                    {
                        "schema_version": "mke.compiled_library_export_response.v2",
                        "ok": True,
                        "library_id": "lib_1",
                        "source_count": 6,
                        "evidence_count": 6,
                        "manifest_sha256": "7" * 64,
                    }
                ).encode(),
                b"",
            )
        if step.startswith("consumer-"):
            return proof.CommandResult(
                0,
                b'{"schema_version":"mke.compiled_library_export_consumer.v2","status":"passed"}',
                b"",
            )
        return proof.CommandResult(0, b"{}", b"")


def _product_result(step: str) -> dict[str, object]:
    lane, fixture = step.split("-", 1)
    source_sha256 = hashlib.sha256(f"direct-audio.{fixture}".encode("ascii")).hexdigest()
    run_id = "run_" + "5" * 32
    return {
        "status": "passed",
        "lane": lane,
        "fixture": fixture,
        "source_sha256": source_sha256,
        "run_id": run_id,
        "run_state": "published",
        "search_keyword_matched": True,
        "ask_status": "evidence_found",
        "evidence_ref": {
            "schema_version": "mke.evidence_ref.v1",
            "evidence_id": "ev_" + "1" * 32,
            "source_id": "src_" + "2" * 32,
            "content_fingerprint": "sha256:" + source_sha256,
            "publication_id": "pub_" + "4" * 32,
            "publication_revision": 1,
            "run_id": run_id,
            "locator": {"kind": "timestamp_ms", "start": 0, "end": 1000},
            "text": "Direct audio remains traceable after publication.",
        },
        "transcript_intake_report": {
            "provider": "faster-whisper",
            "model": "small",
            "model_revision": proof.DEFAULT_MODEL_REVISION,
            "library_version": "1.2.1",
            "device": "cpu",
            "compute_type": "int8",
            "language": "auto",
            "detected_language": "en",
            "media_duration_ms": 3000,
            "transcription_duration_ms": 10,
            "segment_count": 1,
            "model_source": "cache",
        },
    }


def test_public_controller_has_no_fake_authority_seam() -> None:
    signature = inspect.signature(proof.run_direct_audio_deployment_proof)
    assert tuple(signature.parameters) == ("config",)
    authorization_signature = inspect.signature(
        proof.build_direct_audio_authorization_manifest
    )
    assert tuple(authorization_signature.parameters) == ("config",)


@pytest.mark.parametrize("value", [False, 0, -1])
def test_config_rejects_nonpositive_or_boolean_footprint(tmp_path: Path, value: object) -> None:
    config = _config(tmp_path)
    with pytest.raises((TypeError, ValueError)):
        replace(config, direct_audio_footprint_bytes=value)  # type: ignore[arg-type]


def test_config_rejects_absolute_budget_and_wrong_interpreter_count(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with pytest.raises(ValueError, match="baseline_plus"):
        replace(
            config,
            direct_audio_footprint_budget_mode="absolute",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="exactly two"):
        replace(config, interpreters=config.interpreters[:1])


def test_private_orchestration_freezes_two_cells_and_real_product_call_plan(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    runner = FakeRunner()

    result = proof._run_direct_audio_deployment_proof(  # pyright: ignore[reportPrivateUsage]
        config,
        _manifest(config),
        runner,
    )

    assert result["schema_version"] == "mke.direct_audio_deployment_test_observation.v1"
    assert result["canonical"] is False
    assert result["status"] == "passed"
    assert result["interpreter_count"] == 2
    cells = cast(list[dict[str, object]], result["cells"])
    assert all(len(cast(list[object], cell["product_results"])) == 7 for cell in cells)
    assert all(
        cast(dict[str, object], cell["export_result"])["manifest_sha256"] == "7" * 64
        for cell in cells
    )
    assert all(
        cast(dict[str, object], cell["consumer_result"])["schema_version"]
        == "mke.compiled_library_export_consumer.v2"
        for cell in cells
    )
    steps = [call.step for call in runner.calls]
    assert steps.index("create-venv-3.12") < steps.index("ensurepip-3.12")
    assert steps.index("ensurepip-3.12") < steps.index("pip-install-3.12")
    assert steps.count("mcp-m4a") == 2
    assert all(steps.count(f"python-{suffix}") == 2 for suffix in ("mp3", "wav", "m4a"))
    assert all(steps.count(f"cli-{suffix}") == 2 for suffix in ("mp3", "wav", "m4a"))
    assert steps.count("export-first") == 2
    assert steps.count("export-second") == 2
    assert steps.count("consumer-original") == 2
    assert steps.count("consumer-copy") == 2
    assert not any("v1" in argument for call in runner.calls for argument in call.argv)
    mcp = next(call for call in runner.calls if call.step == "mcp-m4a")
    assert "-m" in mcp.argv and "mke.proof.mcp_deployment_client" in mcp.argv
    assert "--direct-audio-footprint-bytes" in mcp.argv
    assert "4096" in mcp.argv
    assert "--direct-audio-footprint-budget-mode" in mcp.argv
    assert "baseline_plus" in mcp.argv
    assert all("PYTHONPATH" not in call.env for call in runner.calls)
    pip_call = next(call for call in runner.calls if call.step == "pip-install-3.12")
    assert set(pip_call.env) == {"HOME", "PIP_CONFIG_FILE", "TMPDIR"}
    assert pip_call.env["PIP_CONFIG_FILE"] == "/dev/null"
    assert not any(
        key in call.env
        for call in runner.calls
        for key in ("PIP_INDEX_URL", "HTTP_PROXY", "HTTPS_PROXY", "PYTHONHOME", "VIRTUAL_ENV")
    )


def test_product_result_rejects_publication_or_evidence_drift() -> None:
    payload = _product_result("python-mp3")
    cast(dict[str, object], payload["evidence_ref"])["locator"] = {
        "kind": "page",
        "start": 1,
        "end": 1,
    }
    with pytest.raises(proof.DirectAudioDeploymentProofError, match="product_path_failed"):
        proof.validate_product_result(payload, fixture="mp3")


def test_product_result_rejects_source_fingerprint_or_run_drift() -> None:
    payload = _product_result("python-mp3")
    cast(dict[str, object], payload["evidence_ref"])["content_fingerprint"] = (
        "sha256:" + "f" * 64
    )
    with pytest.raises(proof.DirectAudioDeploymentProofError, match="product_path_failed"):
        proof.validate_product_result(payload, fixture="mp3")

    payload = _product_result("python-mp3")
    payload["run_id"] = "run_" + "6" * 32
    with pytest.raises(proof.DirectAudioDeploymentProofError, match="product_path_failed"):
        proof.validate_product_result(payload, fixture="mp3")


def test_product_result_requires_complete_transcript_report() -> None:
    payload = _product_result("python-mp3")
    cast(dict[str, object], payload["transcript_intake_report"]).pop("library_version")
    with pytest.raises(proof.DirectAudioDeploymentProofError, match="product_path_failed"):
        proof.validate_product_result(payload, fixture="mp3")

    payload = _product_result("python-mp3")
    cast(dict[str, object], payload["transcript_intake_report"])[
        "transcription_duration_ms"
    ] = -1
    with pytest.raises(proof.DirectAudioDeploymentProofError, match="product_path_failed"):
        proof.validate_product_result(payload, fixture="mp3")


def test_authorization_manifest_binds_owner_pair_without_default(tmp_path: Path) -> None:
    rendered = _manifest(_config(tmp_path)).as_dict()
    assert rendered["direct_audio_footprint_bytes"] == 4096
    assert rendered["direct_audio_footprint_budget_mode"] == "baseline_plus"
    assert "recommended" not in json.dumps(rendered)
    assert "absolute" not in json.dumps(rendered)


def test_missing_retained_authority_stops_before_runner(tmp_path: Path) -> None:
    config = _config(tmp_path)
    runner = FakeRunner()
    with pytest.raises(proof.DirectAudioDeploymentProofError):
        proof._validate_inputs(config)  # pyright: ignore[reportPrivateUsage]
    assert runner.calls == []


def test_cli_has_no_download_flag_and_requires_owner_pair() -> None:
    help_text = proof._parser().format_help()  # pyright: ignore[reportPrivateUsage]
    assert "download" not in help_text
    assert "--direct-audio-footprint-bytes" in help_text
    assert "--direct-audio-footprint-budget-mode" in help_text
    assert "--authorization-only" in help_text


def test_authorization_only_cli_never_starts_terminal_product_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(tmp_path)
    manifest = _manifest(config)

    def fake_validate(value: proof.DirectAudioProofConfig) -> proof.AuthorizationManifest:
        del value
        return manifest

    def forbidden_real_proof(value: proof.DirectAudioProofConfig) -> dict[str, object]:
        del value
        raise AssertionError("real proof must not run")

    monkeypatch.setattr(proof, "_validate_inputs", fake_validate)
    monkeypatch.setattr(proof, "run_direct_audio_deployment_proof", forbidden_real_proof)

    result = proof.main(
        [
            *_cli_args(config),
            "--authorization-only",
            "--json",
        ]
    )

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "mke.direct_audio_terminal_authorization.v1"
    assert payload["status"] == "ready"
    assert "supervision_observations" not in payload


def test_cli_closes_duplicate_interpreter_and_missing_receipt_parent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(tmp_path)
    args = _cli_args(config)
    args[3] = args[1]
    assert proof.main([*args, "--authorization-only", "--json"]) == 1
    failure = json.loads(capsys.readouterr().out)
    assert failure["failure"] == "cli_arguments_invalid"

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="receipt_write_failed"):
        proof._atomic_write(  # pyright: ignore[reportPrivateUsage]
            tmp_path / "missing" / "receipt.json",
            {"status": "passed"},
        )


def _wheel(
    filename: str,
    *,
    distribution: str = "demo",
    version: str = "1.0",
    python_tags: list[str] | None = None,
    platform_tags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "filename": filename,
        "distribution": distribution,
        "version": version,
        "build": None,
        "python_tags": python_tags or ["py3"],
        "abi_tags": ["none"],
        "platform_tags": platform_tags or ["any"],
        "bytes": 1,
        "sha256": "a" * 64,
    }


def _compatibility_payload() -> dict[str, object]:
    return {
        "cells": [
            {
                "cell": version,
                "interpreter": {"sysconfig_platform": "macosx-11.0-arm64"},
            }
            for version in ("3.12", "3.13")
        ]
    }


def _constraints() -> bytes:
    return (
        "# mke-cell 3.12:demo==1.0\n"
        "# mke-cell 3.13:demo==1.0\n"
        f"demo==1.0 --hash=sha256:{'a' * 64}\n"
    ).encode("ascii")


@pytest.mark.parametrize(
    "manifest",
    [
        (),
        (
            _wheel("demo-1.0-py3-none-any.whl"),
            _wheel("surplus-1.0-py3-none-any.whl", distribution="surplus"),
        ),
        (
            _wheel(
                "demo-1.0-cp311-cp311-macosx_11_0_x86_64.whl",
                python_tags=["cp311"],
                platform_tags=["macosx_11_0_x86_64"],
            ),
        ),
        (
            _wheel("demo-1.0-py3-none-any.whl"),
            _wheel("demo-1.0-1-py3-none-any.whl"),
        ),
    ],
)
def test_wheel_resolution_rejects_missing_extra_wrong_tag_and_ambiguous_pairs(
    manifest: tuple[dict[str, object], ...],
) -> None:
    with pytest.raises(proof.DirectAudioDeploymentProofError, match="dependency_authority_invalid"):
        proof._validate_wheel_compatibility(  # pyright: ignore[reportPrivateUsage]
            _constraints(),
            manifest,
            _compatibility_payload(),
        )


def test_wheelhouse_manifest_detects_same_name_different_digest(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = wheelhouse / "demo-1.0-py3-none-any.whl"
    wheel.write_bytes(b"first")
    first = proof._observed_wheel_manifest(wheelhouse)  # pyright: ignore[reportPrivateUsage]
    wheel.write_bytes(b"other")
    second = proof._observed_wheel_manifest(wheelhouse)  # pyright: ignore[reportPrivateUsage]
    assert first[0]["filename"] == second[0]["filename"]
    assert first[0]["sha256"] != second[0]["sha256"]


def test_model_tree_rejects_symlink_escape(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    snapshot = cache / "snapshot"
    snapshot.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.write_text("secret", encoding="utf-8")
    for name in ("README.md", "LICENSE", "config.json", "model.bin", "tokenizer.json"):
        (snapshot / name).write_text(name, encoding="utf-8")
    (snapshot / "vocabulary.json").symlink_to(outside)

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="model_authority_invalid"):
        proof._tree_manifest(  # pyright: ignore[reportPrivateUsage]
            snapshot,
            authority_root=cache,
        )


def test_atomic_receipt_replaces_complete_canonical_payload(tmp_path: Path) -> None:
    target = tmp_path / "proof.json"
    target.write_text("old", encoding="ascii")
    payload = {"schema_version": "mke.direct_audio_deployment_proof.v1", "status": "passed"}

    proof._atomic_write(target, payload)  # pyright: ignore[reportPrivateUsage]

    assert json.loads(target.read_text(encoding="ascii")) == payload
    assert not list(tmp_path.glob(".proof.json.tmp-*"))


def test_interpreter_snapshot_rejects_transient_target_replacement(tmp_path: Path) -> None:
    interpreter = tmp_path / "python3.12"
    interpreter.write_bytes(b"approved")
    interpreter.chmod(0o700)
    snapshot = proof.dependency_authority._snapshot_executable(  # pyright: ignore[reportPrivateUsage]
        interpreter
    )
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"different")
    replacement.chmod(0o700)
    os.replace(replacement, interpreter)

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="interpreter_identity_drift"):
        proof._require_interpreter_snapshot(  # pyright: ignore[reportPrivateUsage]
            interpreter,
            snapshot,
        )


def test_cleanup_failure_is_closed_and_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    runtime = tmp_path / "runtime"

    class FailingCleanup:
        def __init__(self, *, prefix: str) -> None:
            del prefix

        def __enter__(self) -> str:
            runtime.mkdir()
            return str(runtime)

        def __exit__(self, *args: object) -> None:
            raise OSError("private cleanup path")

    monkeypatch.setattr(proof.tempfile, "TemporaryDirectory", FailingCleanup)

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="cleanup_failed"):
        proof._run_direct_audio_deployment_proof(  # pyright: ignore[reportPrivateUsage]
            config,
            _manifest(config),
            FakeRunner(),
        )
