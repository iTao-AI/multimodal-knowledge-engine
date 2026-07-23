from __future__ import annotations

import hashlib
import inspect
import io
import json
import os
import stat
import subprocess
import sys
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from scripts import direct_audio_deployment_proof as proof


def test_documented_direct_script_path_runs_without_pythonpath() -> None:
    repository = Path(__file__).parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/direct_audio_deployment_proof.py",
            "--help",
        ],
        cwd=repository,
        env={"PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "usage: direct_audio_deployment_proof.py" in result.stdout


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
        mcp_diagnostic=tmp_path / "mcp-diagnostic.json",
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
        root_requirements_by_cell=(
            ("3.12", _staged_root_requirements(config)),
            ("3.13", _staged_root_requirements(config)),
        ),
    )


def _staged_root_requirements(config: proof.DirectAudioProofConfig) -> bytes:
    candidate = (
        "multimodal-knowledge-engine[transcription]==0.1.3 "
        f"--hash=sha256:{hashlib.sha256(config.mke_wheel.read_bytes()).hexdigest()}"
    )
    return (
        "\n".join(
            sorted(
                (
                    f"anyio==4.14.0 --hash=sha256:{'a' * 64}",
                    f"av==17.1.0 --hash=sha256:{'b' * 64}",
                    f"mcp==1.28.1 --hash=sha256:{'c' * 64}",
                    candidate,
                )
            )
        )
        + "\n"
    ).encode("ascii")


@pytest.mark.parametrize("version", ("3.12", "3.13"))
def test_stage_cell_writes_exact_receipt_bound_root_projection(
    tmp_path: Path,
    version: str,
) -> None:
    config = _config(tmp_path)
    root = tmp_path / "runtime"
    root.mkdir()

    _, stage, _ = proof._stage_cell_impl(  # pyright: ignore[reportPrivateUsage]
        config,
        _manifest(config),
        root,
        version,
    )

    observed = (stage / "root-requirements.txt").read_bytes()
    assert observed == _staged_root_requirements(config)
    assert len(observed.decode("ascii").splitlines()) == 4


@pytest.mark.parametrize(
    "mutation",
    (
        "missing-transitive",
        "wrong-version",
        "wrong-hash",
        "noncanonical-order",
        "duplicate",
        "surplus",
        "same-size-replacement",
    ),
)
def test_staged_input_validation_requires_exact_root_projection(
    tmp_path: Path,
    mutation: str,
) -> None:
    config = _config(tmp_path)
    authorization = _manifest(config)
    root = tmp_path / "runtime"
    root.mkdir()
    _, stage, _ = proof._stage_cell_impl(  # pyright: ignore[reportPrivateUsage]
        config,
        authorization,
        root,
        "3.12",
    )
    requirements = stage / "root-requirements.txt"
    expected = _staged_root_requirements(config)
    lines = expected.decode("ascii").splitlines()
    if mutation == "missing-transitive":
        mutated = ("\n".join(lines[1:]) + "\n").encode("ascii")
    elif mutation == "wrong-version":
        mutated = expected.replace(b"anyio==4.14.0", b"anyio==4.14.1")
    elif mutation == "wrong-hash":
        mutated = expected.replace(b"a" * 64, b"d" * 64, 1)
    elif mutation == "noncanonical-order":
        mutated = ("\n".join(reversed(lines)) + "\n").encode("ascii")
    elif mutation == "duplicate":
        mutated = expected + (lines[0] + "\n").encode("ascii")
    elif mutation == "surplus":
        mutated = expected + (
            f"surplus==1.0 --hash=sha256:{'e' * 64}\n"
        ).encode("ascii")
    else:
        mutated = expected.replace(b"anyio==4.14.0", b"anyio==4.14.1")
    if mutation == "same-size-replacement":
        replacement = stage / "replacement.txt"
        replacement.write_bytes(mutated)
        os.replace(replacement, requirements)
    else:
        requirements.write_bytes(mutated)

    with pytest.raises(
        proof.DirectAudioDeploymentProofError,
        match="^pip_input_identity_drift$",
    ):
        proof._validate_staged_inputs(  # pyright: ignore[reportPrivateUsage]
            config=config,
            authorization=authorization,
            stage=stage,
        )


def test_package_sets_reject_old_receipt_without_candidate_wheel_identity() -> None:
    payload: dict[str, object] = {
        "cells": [
            {
                "cell": cell,
                "installed_distributions": [
                    {
                        "distribution": "mcp",
                        "version": "1.28.1",
                        "source_wheel_filename": "mcp-1.28.1-py3-none-any.whl",
                        "source_wheel_sha256": "a" * 64,
                    }
                ],
            }
            for cell in ("3.12", "3.13")
        ]
    }

    with pytest.raises(
        proof.DirectAudioDeploymentProofError,
        match="dependency_authority_invalid",
    ):
        proof._package_sets(  # pyright: ignore[reportPrivateUsage]
            payload,
            "0.1.3",
            (("mcp", ">=1,<2"),),
            "multimodal_knowledge_engine-0.1.3-py3-none-any.whl",
            "b" * 64,
        )


def _candidate_wheel(metadata: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "multimodal_knowledge_engine-0.1.3.dist-info/METADATA",
            metadata,
        )
    return output.getvalue()


def _candidate_root_fixture(
    tmp_path: Path,
    *,
    extra_candidate_requirement: str | None = None,
) -> tuple[
    Path,
    proof.dependency_authority.LockProjection,
    dict[str, object],
    tuple[tuple[str, bytes], ...],
]:
    candidate = tmp_path / "multimodal_knowledge_engine-0.1.3-py3-none-any.whl"
    extra = (
        ""
        if extra_candidate_requirement is None
        else f"Requires-Dist: {extra_candidate_requirement}\n"
    )
    candidate.write_bytes(
        _candidate_wheel(
            "Metadata-Version: 2.4\n"
            "Name: multimodal-knowledge-engine\n"
            "Version: 0.1.3\n"
            "Requires-Dist: mcp<2,>=1.28.1\n"
            f"{extra}"
            "Provides-Extra: embedding\n"
            "Requires-Dist: ignored==1; extra == 'embedding'\n"
            "Provides-Extra: transcription\n"
            "Requires-Dist: av<18,>=11; extra == 'transcription'\n"
        )
    )
    authority = proof.dependency_authority
    cells = (
        authority.Cell("python3.12", "3.12", "cp312", "macosx_11_0_arm64"),
        authority.Cell("python3.13", "3.13", "cp313", "macosx_11_0_arm64"),
    )
    requirements = (
        authority.Requirement("anyio", "4.14.0"),
        authority.Requirement("av", "17.1.0"),
        authority.Requirement("mcp", "1.28.1"),
    )
    external_lines = (
        f"anyio==4.14.0 --hash=sha256:{'a' * 64}",
        f"av==17.1.0 --hash=sha256:{'b' * 64}",
        f"mcp==1.28.1 --hash=sha256:{'c' * 64}",
    )
    external = ("\n".join(external_lines) + "\n").encode("ascii")
    constraints = (
        "# mke-cell 3.12:anyio==4.14.0,av==17.1.0,mcp==1.28.1\n"
        "# mke-cell 3.13:anyio==4.14.0,av==17.1.0,mcp==1.28.1\n"
        + external.decode("ascii")
    ).encode("ascii")
    projection = authority.LockProjection(
        requirements=requirements,
        requirements_by_cell=tuple((cell.version, requirements) for cell in cells),
        constraints=constraints,
        root_requirements=external,
        root_requirements_by_cell=tuple((cell.version, external) for cell in cells),
        direct_requirements_by_cell=tuple(
            (cell.version, ("av", "mcp")) for cell in cells
        ),
        locked_wheels=(),
        cells=cells,
    )
    candidate_line = (
        "multimodal-knowledge-engine[transcription]==0.1.3 "
        f"--hash=sha256:{hashlib.sha256(candidate.read_bytes()).hexdigest()}"
    )
    canonical = (
        "\n".join(sorted((*external_lines, candidate_line))) + "\n"
    ).encode("ascii")
    roots = tuple((cell.version, canonical) for cell in cells)
    digest = hashlib.sha256(canonical).hexdigest()
    payload: dict[str, object] = {
        "cells": [
            {
                "cell": cell.version,
                "pip": {"staging": {"root_requirements_sha256": digest}},
            }
            for cell in cells
        ]
    }
    return candidate, projection, payload, roots


def test_candidate_root_projection_reuses_receipt_authority_for_both_cells(
    tmp_path: Path,
) -> None:
    candidate, projection, payload, expected = _candidate_root_fixture(tmp_path)

    observed = proof._candidate_root_authority(  # pyright: ignore[reportPrivateUsage]
        candidate=candidate,
        constraints=projection.constraints,
        payload=payload,
        projection=projection,
    )

    assert observed == expected
    assert [cell for cell, _ in observed] == ["3.12", "3.13"]
    assert all(len(value.decode("ascii").splitlines()) == 4 for _, value in observed)


def test_candidate_root_projection_rejects_candidate_metadata_dependency_drift(
    tmp_path: Path,
) -> None:
    candidate, projection, payload, _ = _candidate_root_fixture(
        tmp_path,
        extra_candidate_requirement="anyio<5,>=4",
    )

    with pytest.raises(
        proof.DirectAudioDeploymentProofError,
        match="^dependency_authority_invalid$",
    ):
        proof._candidate_root_authority(  # pyright: ignore[reportPrivateUsage]
            candidate=candidate,
            constraints=projection.constraints,
            payload=payload,
            projection=projection,
        )


def test_candidate_metadata_closes_core_and_transcription_requirements() -> None:
    value = _candidate_wheel(
        "Metadata-Version: 2.4\n"
        "Name: multimodal-knowledge-engine\n"
        "Version: 0.1.3\n"
        "Requires-Dist: mcp<2,>=1.28.1\n"
        "Provides-Extra: embedding\n"
        "Requires-Dist: ignored==1; extra == 'embedding'\n"
        "Provides-Extra: transcription\n"
        "Requires-Dist: av<18,>=11; extra == 'transcription'\n"
    )

    assert proof._wheel_metadata(value) == (  # pyright: ignore[reportPrivateUsage]
        "multimodal-knowledge-engine",
        "0.1.3",
        (("av", "<18,>=11"), ("mcp", "<2,>=1.28.1")),
    )


@pytest.mark.parametrize(
    "requires_dist",
    (
        "mcp>=1; python_version >= '3.12'",
        "mcp[cli]>=1",
        "mcp>=candidate",
    ),
)
def test_candidate_metadata_rejects_unclosed_requirement_authority(
    requires_dist: str,
) -> None:
    value = _candidate_wheel(
        "Metadata-Version: 2.4\n"
        "Name: multimodal-knowledge-engine\n"
        "Version: 0.1.3\n"
        f"Requires-Dist: {requires_dist}\n"
        "Provides-Extra: embedding\n"
        "Provides-Extra: transcription\n"
    )

    with pytest.raises(
        proof.DirectAudioDeploymentProofError,
        match="^candidate_artifact_invalid$",
    ):
        proof._wheel_metadata(value)  # pyright: ignore[reportPrivateUsage]


def test_package_sets_reject_candidate_direct_version_drift() -> None:
    payload = {
        "cells": [
            {
                "cell": cell,
                "installed_distributions": [
                    {
                        "distribution": "mcp",
                        "version": "1.27.0",
                        "source_wheel_filename": "mcp-1.27.0-py3-none-any.whl",
                        "source_wheel_sha256": "a" * 64,
                    }
                ],
            }
            for cell in ("3.12", "3.13")
        ]
    }

    with pytest.raises(
        proof.DirectAudioDeploymentProofError,
        match="^dependency_authority_invalid$",
    ):
        proof._package_sets(  # pyright: ignore[reportPrivateUsage]
            payload,
            "0.1.3",
            (("mcp", ">=1.28.1,<2"),),
            "multimodal_knowledge_engine-0.1.3-py3-none-any.whl",
            "b" * 64,
        )


def test_package_sets_bind_exact_candidate_wheel_row() -> None:
    filename = "multimodal_knowledge_engine-0.1.3-py3-none-any.whl"
    payload = {
        "cells": [
            {
                "cell": cell,
                "installed_distributions": [
                    {
                        "distribution": "mcp",
                        "version": "1.28.1",
                        "source_wheel_filename": "mcp-1.28.1-py3-none-any.whl",
                        "source_wheel_sha256": "a" * 64,
                    },
                    {
                        "distribution": "multimodal-knowledge-engine",
                        "version": "0.1.3",
                        "source_wheel_filename": filename,
                        "source_wheel_sha256": "b" * 64,
                    },
                ],
            }
            for cell in ("3.12", "3.13")
        ]
    }

    assert proof._package_sets(  # pyright: ignore[reportPrivateUsage]
        payload,
        "0.1.3",
        (("mcp", ">=1.28.1,<2"),),
        filename,
        "b" * 64,
    ) == (
        (
            "3.12",
            (("mcp", "1.28.1"), ("multimodal-knowledge-engine", "0.1.3")),
        ),
        (
            "3.13",
            (("mcp", "1.28.1"), ("multimodal-knowledge-engine", "0.1.3")),
        ),
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


class InstallGateRunner:
    def __init__(self, result: proof.CommandResult) -> None:
        self.result = result
        self.calls: list[proof.CommandCall] = []

    def run(self, call: proof.CommandCall) -> proof.CommandResult:
        self.calls.append(call)
        return self.result


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
    assert "--child-cwd" in mcp.argv
    assert str(mcp.cwd) in mcp.argv
    assert "--diagnostic" in mcp.argv
    assert str(mcp.cwd / proof._MCP_CHILD_DIAGNOSTIC_NAME) in mcp.argv  # pyright: ignore[reportPrivateUsage]
    assert str(config.mcp_diagnostic) not in mcp.argv
    assert mcp.env["UV_OFFLINE"] == "1"
    assert mcp.env["PATH"] == "/usr/bin:/bin:/usr/sbin:/sbin"
    assert all("PYTHONPATH" not in call.env for call in runner.calls)
    pip_call = next(call for call in runner.calls if call.step == "pip-install-3.12")
    assert set(pip_call.env) == {"HOME", "PIP_CONFIG_FILE", "TMPDIR"}
    assert pip_call.env["PIP_CONFIG_FILE"] == "/dev/null"
    assert "--require-hashes" in pip_call.argv
    assert "--no-index" in pip_call.argv
    assert "--only-binary=:all:" in pip_call.argv
    assert "--constraint" in pip_call.argv
    assert "--requirement" in pip_call.argv
    assert "--no-deps" not in pip_call.argv
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
    assert "root_requirements_by_cell" not in rendered


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


@pytest.mark.parametrize(
    "step",
    (
        "pip-install-3.12",
        "pip-check-3.12",
        "pip-install-3.13",
        "pip-check-3.13",
    ),
)
def test_failed_install_gate_writes_bounded_operator_diagnostic(
    tmp_path: Path,
    step: str,
) -> None:
    stdout = ("ok-\N{SNOWMAN}".encode() + b"\xff") * 20_000
    stderr = ("bad-\N{SNOWMAN}".encode() + b"\xfe") * 20_000
    diagnostic = tmp_path / "install-diagnostic.json"
    runner = InstallGateRunner(proof.CommandResult(23, stdout, stderr))
    call = proof.CommandCall(step, ("not-executed",), {}, tmp_path)

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^install_failed$"):
        proof._run_install_gate(  # pyright: ignore[reportPrivateUsage]
            runner,
            call,
            diagnostic,
        )

    payload = json.loads(diagnostic.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": "mke.direct_audio_install_diagnostic.v1",
        "status": "failed",
        "failure": "install_failed",
        "step": step,
        "returncode": 23,
        "stdout": {
            "bytes": len(stdout),
            "sha256": hashlib.sha256(stdout).hexdigest(),
            "text": payload["stdout"]["text"],
            "truncated": True,
        },
        "stderr": {
            "bytes": len(stderr),
            "sha256": hashlib.sha256(stderr).hexdigest(),
            "text": payload["stderr"]["text"],
            "truncated": True,
        },
    }
    assert len(payload["stdout"]["text"].encode("utf-8")) <= 64 * 1024
    assert len(payload["stderr"]["text"].encode("utf-8")) <= 64 * 1024
    assert set(payload) == {
        "schema_version",
        "status",
        "failure",
        "step",
        "returncode",
        "stdout",
        "stderr",
    }
    assert diagnostic.stat().st_mode & 0o777 == 0o600


def test_successful_install_gate_does_not_create_diagnostic(tmp_path: Path) -> None:
    diagnostic = tmp_path / "install-diagnostic.json"
    runner = InstallGateRunner(proof.CommandResult(0, b"success", b""))

    proof._run_install_gate(  # pyright: ignore[reportPrivateUsage]
        runner,
        proof.CommandCall("pip-check-3.12", ("not-executed",), {}, tmp_path),
        diagnostic,
    )

    assert not diagnostic.exists()


@pytest.mark.parametrize("destination_kind", ("file", "symlink"))
def test_install_diagnostic_rejects_existing_destination_without_clobber(
    tmp_path: Path,
    destination_kind: str,
) -> None:
    operator_state = tmp_path / "operator-state"
    operator_state.write_bytes(b"preserve-operator-state")
    diagnostic = tmp_path / "install-diagnostic.json"
    if destination_kind == "file":
        diagnostic.write_bytes(b"preserve-existing-diagnostic")
    else:
        diagnostic.symlink_to(operator_state)
    runner = InstallGateRunner(proof.CommandResult(9, b"out", b"err"))

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^install_failed$"):
        proof._run_install_gate(  # pyright: ignore[reportPrivateUsage]
            runner,
            proof.CommandCall("pip-install-3.13", ("not-executed",), {}, tmp_path),
            diagnostic,
        )

    assert operator_state.read_bytes() == b"preserve-operator-state"
    if destination_kind == "file":
        assert diagnostic.read_bytes() == b"preserve-existing-diagnostic"
    else:
        assert diagnostic.is_symlink()


@pytest.mark.parametrize("nested", (False, True))
def test_install_diagnostic_rejects_symlink_parent_without_touching_operator_state(
    tmp_path: Path,
    nested: bool,
) -> None:
    operator_root = tmp_path / "operator-root"
    operator_root.mkdir()
    operator_state = operator_root / "state"
    operator_state.write_bytes(b"preserve-operator-state")
    target_before = operator_root.stat()
    alias_root = tmp_path / "call-owned"
    if nested:
        alias_root.mkdir()
        diagnostic_parent = alias_root / "nested"
    else:
        diagnostic_parent = alias_root
    diagnostic_parent.symlink_to(operator_root, target_is_directory=True)
    diagnostic = diagnostic_parent / "install-diagnostic.json"
    runner = InstallGateRunner(proof.CommandResult(9, b"out", b"err"))

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^install_failed$"):
        proof._run_install_gate(  # pyright: ignore[reportPrivateUsage]
            runner,
            proof.CommandCall("pip-install-3.12", ("not-executed",), {}, tmp_path),
            diagnostic,
        )

    target_after = operator_root.stat()
    assert operator_state.read_bytes() == b"preserve-operator-state"
    assert not (operator_root / diagnostic.name).exists()
    assert (
        target_after.st_dev,
        target_after.st_ino,
        target_after.st_mode,
        target_after.st_mtime_ns,
        target_after.st_ctime_ns,
    ) == (
        target_before.st_dev,
        target_before.st_ino,
        target_before.st_mode,
        target_before.st_mtime_ns,
        target_before.st_ctime_ns,
    )


def test_install_diagnostic_rejects_parent_traversal_before_creation(
    tmp_path: Path,
) -> None:
    traversal_parent = tmp_path / "traversal"
    traversal_parent.mkdir()
    diagnostic = traversal_parent / ".." / "install-diagnostic.json"
    runner = InstallGateRunner(proof.CommandResult(9, b"out", b"err"))

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^install_failed$"):
        proof._run_install_gate(  # pyright: ignore[reportPrivateUsage]
            runner,
            proof.CommandCall("pip-check-3.12", ("not-executed",), {}, tmp_path),
            diagnostic,
        )

    assert not (tmp_path / diagnostic.name).exists()


@pytest.mark.parametrize("failing_close", ("file", "parent"))
def test_install_diagnostic_maps_descriptor_close_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failing_close: str,
) -> None:
    diagnostic = tmp_path / "install-diagnostic.json"
    real_close = os.close
    closed: list[int] = []

    def close_with_failure(descriptor: int) -> None:
        closed.append(descriptor)
        real_close(descriptor)
        failure_index = 1 if failing_close == "file" else 2
        if len(closed) == failure_index:
            raise OSError("synthetic close failure")

    monkeypatch.setattr(proof.os, "close", close_with_failure)

    with pytest.raises(
        proof.DirectAudioDeploymentProofError,
        match="^install_diagnostic_write_failed$",
    ):
        proof._write_install_diagnostic(  # pyright: ignore[reportPrivateUsage]
            diagnostic,
            step="pip-check-3.13",
            result=proof.CommandResult(17, b"out", b"err"),
        )

    assert len(closed) == 2
    assert len(set(closed)) == 2


def test_install_gate_keeps_public_code_when_descriptor_close_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostic = tmp_path / "install-diagnostic.json"
    real_close = os.close
    close_count = 0

    def fail_first_close(descriptor: int) -> None:
        nonlocal close_count
        close_count += 1
        real_close(descriptor)
        if close_count == 1:
            raise OSError("synthetic close failure")

    monkeypatch.setattr(proof.os, "close", fail_first_close)

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^install_failed$"):
        proof._run_install_gate(  # pyright: ignore[reportPrivateUsage]
            InstallGateRunner(proof.CommandResult(17, b"out", b"err")),
            proof.CommandCall("pip-install-3.13", ("not-executed",), {}, tmp_path),
            diagnostic,
        )

    assert close_count == 2


def test_close_failure_cleanup_preserves_operator_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostic = tmp_path / "install-diagnostic.json"
    real_close = os.close
    closed: list[int] = []

    def replace_then_fail_close(descriptor: int) -> None:
        closed.append(descriptor)
        if len(closed) == 1:
            diagnostic.unlink()
            diagnostic.write_bytes(b"operator-replacement")
        real_close(descriptor)
        if len(closed) == 1:
            raise OSError("synthetic close failure")

    monkeypatch.setattr(proof.os, "close", replace_then_fail_close)

    with pytest.raises(
        proof.DirectAudioDeploymentProofError,
        match="^install_diagnostic_write_failed$",
    ):
        proof._write_install_diagnostic(  # pyright: ignore[reportPrivateUsage]
            diagnostic,
            step="pip-install-3.12",
            result=proof.CommandResult(17, b"out", b"err"),
        )

    assert diagnostic.read_bytes() == b"operator-replacement"
    assert len(closed) == 2
    assert len(set(closed)) == 2


def test_install_diagnostic_write_failure_preserves_public_classification(
    tmp_path: Path,
) -> None:
    runner = InstallGateRunner(proof.CommandResult(7, b"out", b"err"))
    diagnostic = tmp_path / "missing" / "install-diagnostic.json"

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^install_failed$"):
        proof._run_install_gate(  # pyright: ignore[reportPrivateUsage]
            runner,
            proof.CommandCall("pip-check-3.13", ("not-executed",), {}, tmp_path),
            diagnostic,
        )

    assert not diagnostic.exists()


def test_unrelated_failure_does_not_create_install_diagnostic(tmp_path: Path) -> None:
    diagnostic = tmp_path / "install-diagnostic.json"
    config = replace(_config(tmp_path), install_diagnostic=diagnostic)

    class EnsurePipFailure(FakeRunner):
        def run(self, call: proof.CommandCall) -> proof.CommandResult:
            if call.step == "ensurepip-3.12":
                return proof.CommandResult(4, b"out", b"err")
            return super().run(call)

    with pytest.raises(
        proof.DirectAudioDeploymentProofError,
        match="^environment_create_failed$",
    ):
        proof._run_direct_audio_deployment_proof(  # pyright: ignore[reportPrivateUsage]
            config,
            _manifest(config),
            EnsurePipFailure(),
        )

    assert not diagnostic.exists()


def test_cli_install_diagnostic_keeps_public_failure_aggregate_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(tmp_path)
    diagnostic = tmp_path / "install-diagnostic.json"

    def fail(value: proof.DirectAudioProofConfig) -> dict[str, object]:
        assert value.install_diagnostic == diagnostic
        raise proof.DirectAudioDeploymentProofError("install_failed")

    monkeypatch.setattr(proof, "run_direct_audio_deployment_proof", fail)

    assert proof.main(
        [
            *_cli_args(config),
            "--install-diagnostic",
            str(diagnostic),
            "--json",
        ]
    ) == 1
    output = capsys.readouterr().out
    assert output == (
        '{"canonical": false, "failure": "install_failed", '
        '"schema_version": "mke.direct_audio_deployment_proof.v1", '
        '"status": "failed"}\n'
    )
    assert json.loads(output) == {
        "schema_version": "mke.direct_audio_deployment_proof.v1",
        "status": "failed",
        "canonical": False,
        "failure": "install_failed",
    }


def _mcp_diagnostic_payload(
    *,
    stage: str = "search",
    stderr_bytes: int | None = None,
    overflow: bool = False,
    capture_failed: bool = False,
) -> dict[str, object]:
    stderr = b"bounded server warning"
    observed_bytes = len(stderr) if stderr_bytes is None else stderr_bytes
    return {
        "schema_version": "mke.mcp_deployment_diagnostic.v1",
        "status": "failed",
        "failure": "mcp_deployment_failed",
        "stage": stage,
        "stderr": {
            "bytes": observed_bytes,
            "sha256": hashlib.sha256(stderr).hexdigest(),
            "overflow": overflow,
            "capture_failed": capture_failed,
        },
    }


def _mcp_child_diagnostic(tmp_path: Path) -> Path:
    return tmp_path / "mcp-child-diagnostic.json"


def _run_mcp_gate_for_m4a(
    runner: proof.CommandRunner,
    tmp_path: Path,
    diagnostic: Path,
) -> dict[str, object]:
    return proof._run_mcp_gate(  # pyright: ignore[reportPrivateUsage]
        runner,
        proof.CommandCall("mcp-m4a", ("not-executed",), {}, tmp_path),
        diagnostic,
        fixture="m4a",
        expected_source_sha256=hashlib.sha256(b"direct-audio.m4a").hexdigest(),
    )


def test_mcp_gate_preserves_valid_bounded_operator_diagnostic(tmp_path: Path) -> None:
    diagnostic = tmp_path / "mcp-diagnostic.json"
    child_diagnostic = _mcp_child_diagnostic(tmp_path)

    class FailedMcpRunner:
        def run(self, call: proof.CommandCall) -> proof.CommandResult:
            del call
            child_diagnostic.write_text(
                json.dumps(_mcp_diagnostic_payload(), sort_keys=True) + "\n",
                encoding="ascii",
            )
            child_diagnostic.chmod(0o600)
            return proof.CommandResult(
                1,
                b'{"status":"failed","reason":"mcp_deployment_failed"}\n',
                b"",
            )

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^mcp_failed$"):
        _run_mcp_gate_for_m4a(
            FailedMcpRunner(),
            tmp_path,
            diagnostic,
        )

    assert json.loads(diagnostic.read_text(encoding="ascii")) == (
        _mcp_diagnostic_payload()
    )


def test_mcp_gate_writes_parent_result_validation_diagnostic(tmp_path: Path) -> None:
    diagnostic = tmp_path / "mcp-diagnostic.json"
    payload = _product_result("mcp-m4a")
    payload["status"] = "failed"

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^mcp_failed$"):
        _run_mcp_gate_for_m4a(
            InstallGateRunner(proof.CommandResult(0, json.dumps(payload).encode(), b"")),
            tmp_path,
            diagnostic,
        )

    observed = proof._validate_mcp_diagnostic(  # pyright: ignore[reportPrivateUsage]
        diagnostic
    )
    assert observed["stage"] == "parent_result_validation"
    assert "/private" not in diagnostic.read_text(encoding="ascii")


def test_mcp_gate_writes_exact_source_identity_diagnostic(tmp_path: Path) -> None:
    diagnostic = tmp_path / "mcp-diagnostic.json"
    payload = _product_result("mcp-m4a")
    payload["source_sha256"] = "0" * 64
    evidence = cast(dict[str, object], payload["evidence_ref"])
    evidence["content_fingerprint"] = "sha256:" + "0" * 64

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^mcp_failed$"):
        _run_mcp_gate_for_m4a(
            InstallGateRunner(proof.CommandResult(0, json.dumps(payload).encode(), b"")),
            tmp_path,
            diagnostic,
        )

    observed = proof._validate_mcp_diagnostic(  # pyright: ignore[reportPrivateUsage]
        diagnostic
    )
    assert observed["stage"] == "source_identity"
    assert "0" * 64 not in diagnostic.read_text(encoding="ascii")


def test_mcp_diagnostic_binds_policy_and_bytes_to_same_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostic = tmp_path / "mcp-diagnostic.json"
    diagnostic.write_text(
        json.dumps(
            _mcp_diagnostic_payload(stage="parent_result_validation"),
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )
    diagnostic.chmod(0o600)
    replacement = tmp_path / "replacement.json"
    replacement.write_text(
        json.dumps(
            _mcp_diagnostic_payload(stage="parent_result_validation"),
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )
    replacement.chmod(0o644)
    original_lstat = Path.lstat
    replaced = False

    def replace_after_policy_check(path: Path) -> os.stat_result:
        nonlocal replaced
        observed = original_lstat(path)
        if path == diagnostic and not replaced:
            os.replace(replacement, diagnostic)
            replaced = True
        return observed

    monkeypatch.setattr(Path, "lstat", replace_after_policy_check)

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^mcp_failed$"):
        proof._validate_mcp_diagnostic(  # pyright: ignore[reportPrivateUsage]
            diagnostic
        )

    assert replaced is True
    assert stat.S_IMODE(original_lstat(diagnostic).st_mode) == 0o644


@pytest.mark.parametrize(
    ("stage", "stderr_bytes", "overflow", "capture_failed"),
    (
        ("search", proof._MAX_MCP_SERVER_STDERR_BYTES + 1, True, False),  # pyright: ignore[reportPrivateUsage]
        ("search", 0, False, True),
        ("stderr", 0, False, False),
        ("stderr", proof._MAX_MCP_SERVER_STDERR_BYTES, True, False),  # pyright: ignore[reportPrivateUsage]
    ),
)
def test_mcp_diagnostic_rejects_generator_impossible_stderr_semantics(
    tmp_path: Path,
    stage: str,
    stderr_bytes: int,
    overflow: bool,
    capture_failed: bool,
) -> None:
    diagnostic = tmp_path / "mcp-diagnostic.json"
    diagnostic.write_text(
        json.dumps(
            _mcp_diagnostic_payload(
                stage=stage,
                stderr_bytes=stderr_bytes,
                overflow=overflow,
                capture_failed=capture_failed,
            ),
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )
    diagnostic.chmod(0o600)

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^mcp_failed$"):
        proof._validate_mcp_diagnostic(  # pyright: ignore[reportPrivateUsage]
            diagnostic
        )


@pytest.mark.parametrize(
    ("stage", "stderr_bytes", "overflow", "capture_failed"),
    (
        ("search", len(b"bounded server warning"), False, False),
        ("search", proof._MAX_MCP_SERVER_STDERR_BYTES, False, False),  # pyright: ignore[reportPrivateUsage]
        ("stderr", proof._MAX_MCP_SERVER_STDERR_BYTES + 1, True, False),  # pyright: ignore[reportPrivateUsage]
        ("stderr", 0, False, True),
    ),
)
def test_mcp_diagnostic_accepts_exact_producer_stderr_semantics(
    tmp_path: Path,
    stage: str,
    stderr_bytes: int,
    overflow: bool,
    capture_failed: bool,
) -> None:
    diagnostic = tmp_path / "mcp-diagnostic.json"
    payload = _mcp_diagnostic_payload(
        stage=stage,
        stderr_bytes=stderr_bytes,
        overflow=overflow,
        capture_failed=capture_failed,
    )
    diagnostic.write_text(
        json.dumps(payload, sort_keys=True) + "\n",
        encoding="ascii",
    )
    diagnostic.chmod(0o600)

    assert proof._validate_mcp_diagnostic(  # pyright: ignore[reportPrivateUsage]
        diagnostic
    ) == payload


def test_mcp_diagnostic_rejects_same_inode_content_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostic = tmp_path / "mcp-diagnostic.json"
    value = (
        json.dumps(
            _mcp_diagnostic_payload(stage="parent_result_validation"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    mutated = value.replace(b'"sha256": "', b'"sha256": "f', 1)[:-1]
    assert len(mutated) == len(value)
    diagnostic.write_bytes(value)
    diagnostic.chmod(0o600)
    original_read = os.read
    changed = False

    def mutate_after_read(descriptor: int, size: int) -> bytes:
        nonlocal changed
        chunk = original_read(descriptor, size)
        if chunk and not changed:
            with diagnostic.open("r+b", buffering=0) as stream:
                stream.write(mutated)
            changed = True
        return chunk

    monkeypatch.setattr(os, "read", mutate_after_read)

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^mcp_failed$"):
        proof._validate_mcp_diagnostic(  # pyright: ignore[reportPrivateUsage]
            diagnostic
        )

    assert changed is True


@pytest.mark.parametrize("diagnostic_state", ("missing", "malformed", "ambiguous"))
def test_mcp_gate_writes_unavailable_reason_when_child_diagnostic_is_not_valid(
    tmp_path: Path,
    diagnostic_state: str,
) -> None:
    diagnostic = tmp_path / "mcp-diagnostic.json"
    child_diagnostic = _mcp_child_diagnostic(tmp_path)

    class FailedMcpRunner:
        def run(self, call: proof.CommandCall) -> proof.CommandResult:
            del call
            if diagnostic_state == "malformed":
                child_diagnostic.write_bytes(b'{"stage":"/private/raw-secret"}\n')
                child_diagnostic.chmod(0o600)
            elif diagnostic_state == "ambiguous":
                payload = _mcp_diagnostic_payload(stage="unknown")
                child_diagnostic.write_text(
                    json.dumps(payload) + "\n", encoding="ascii"
                )
                child_diagnostic.chmod(0o600)
            return proof.CommandResult(2, b"{}", b"client stderr must stay private")

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^mcp_failed$"):
        _run_mcp_gate_for_m4a(
            FailedMcpRunner(),
            tmp_path,
            diagnostic,
        )

    observed = proof._validate_mcp_diagnostic(  # pyright: ignore[reportPrivateUsage]
        diagnostic
    )
    assert observed["stage"] == "child_diagnostic_unavailable"
    rendered = diagnostic.read_text(encoding="ascii")
    assert "client stderr" not in rendered
    assert "/private" not in rendered


def test_successful_mcp_gate_rejects_spurious_diagnostic(tmp_path: Path) -> None:
    diagnostic = tmp_path / "mcp-diagnostic.json"
    child_diagnostic = _mcp_child_diagnostic(tmp_path)

    class SpuriousDiagnosticRunner:
        def run(self, call: proof.CommandCall) -> proof.CommandResult:
            del call
            child_diagnostic.write_text(
                json.dumps(_mcp_diagnostic_payload()) + "\n",
                encoding="ascii",
            )
            child_diagnostic.chmod(0o600)
            return proof.CommandResult(0, b'{"status":"passed"}', b"")

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^mcp_failed$"):
        _run_mcp_gate_for_m4a(
            SpuriousDiagnosticRunner(),
            tmp_path,
            diagnostic,
        )

    observed = proof._validate_mcp_diagnostic(  # pyright: ignore[reportPrivateUsage]
        diagnostic
    )
    assert observed["stage"] == "child_diagnostic_unavailable"


@pytest.mark.parametrize("state", ("missing", "malformed", "mode", "directory"))
def test_extended_operator_diagnostic_rejects_invalid_authority(
    tmp_path: Path,
    state: str,
) -> None:
    diagnostic = tmp_path / "mcp-diagnostic.json"
    if state == "malformed":
        diagnostic.write_bytes(b'{"stage":"parent_result_validation"}\n')
        diagnostic.chmod(0o600)
    elif state == "mode":
        diagnostic.write_text(
            json.dumps(
                _mcp_diagnostic_payload(stage="parent_result_validation")
            )
            + "\n",
            encoding="ascii",
        )
        diagnostic.chmod(0o644)
    elif state == "directory":
        diagnostic.mkdir()

    with pytest.raises(proof.DirectAudioDeploymentProofError, match="^mcp_failed$"):
        proof._validate_mcp_diagnostic(  # pyright: ignore[reportPrivateUsage]
            diagnostic
        )


def test_cli_mcp_diagnostic_keeps_public_failure_aggregate_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(tmp_path)

    def fail(value: proof.DirectAudioProofConfig) -> dict[str, object]:
        assert value.mcp_diagnostic == config.mcp_diagnostic
        raise proof.DirectAudioDeploymentProofError("mcp_failed")

    monkeypatch.setattr(proof, "run_direct_audio_deployment_proof", fail)

    assert proof.main(
        [
            *_cli_args(config),
            "--mcp-diagnostic",
            str(config.mcp_diagnostic),
            "--json",
        ]
    ) == 1
    output = capsys.readouterr().out
    assert output == (
        '{"canonical": false, "failure": "mcp_failed", '
        '"schema_version": "mke.direct_audio_deployment_proof.v1", '
        '"status": "failed"}\n'
    )
    assert json.loads(output) == {
        "schema_version": "mke.direct_audio_deployment_proof.v1",
        "status": "failed",
        "canonical": False,
        "failure": "mcp_failed",
    }


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
