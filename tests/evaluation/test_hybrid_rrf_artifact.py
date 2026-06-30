from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from mke.evaluation.hybrid_rrf_artifact import (
    HybridRrfArtifactError,
    build_hybrid_rrf_comparison_artifact,
    validate_hybrid_rrf_artifact,
)
from mke.evaluation.hybrid_rrf_workflow import run_hybrid_rrf_development

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json"
DENSE_ARTIFACT = (
    ROOT / "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json"
)
ArtifactMutation = Callable[[dict[str, Any]], None]


@pytest.fixture
def temporary_artifact(tmp_path: Path) -> Path:
    report = run_hybrid_rrf_development(
        protocol_path=PROTOCOL,
        dense_artifact_path=DENSE_ARTIFACT,
        repository_root=ROOT,
    )
    artifact = build_hybrid_rrf_comparison_artifact(report=report)
    path = tmp_path / "comparison.json"
    path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def test_artifact_validator_recomputes_from_inputs(temporary_artifact: Path) -> None:
    validate_hybrid_rrf_artifact(
        artifact_path=temporary_artifact,
        protocol_path=PROTOCOL,
        dense_artifact_path=DENSE_ARTIFACT,
        repository_root=ROOT,
    )


@pytest.mark.parametrize(
    "mutation",
    (
        lambda payload: _first_fused(payload).__setitem__("rank", 2),
        lambda payload: _first_fused(payload).__setitem__("portable_score", "0"),
        lambda payload: _first_fused(payload).__setitem__("arms", ["dense"]),
        lambda payload: payload["development"]["diagnostics"].__setitem__(
            "ranking_headroom_count", 99
        ),
        lambda payload: payload.__setitem__("runtime_promotion_status", "promoted"),
    ),
)
def test_artifact_validator_rejects_derived_field_tampering(
    temporary_artifact: Path,
    mutation: ArtifactMutation,
    tmp_path: Path,
) -> None:
    payload = _load(temporary_artifact)
    mutation(payload)
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(HybridRrfArtifactError):
        validate_hybrid_rrf_artifact(
            artifact_path=path,
            protocol_path=PROTOCOL,
            dense_artifact_path=DENSE_ARTIFACT,
            repository_root=ROOT,
        )


def test_artifact_validator_rejects_coordinated_report_tampering(
    temporary_artifact: Path,
    tmp_path: Path,
) -> None:
    payload = _load(temporary_artifact)
    row = _first_fused(payload)
    row["rank"] = 2
    metrics = cast(dict[str, Any], payload["development"])["metrics"]
    cast(dict[str, Any], metrics)["fused"] = cast(dict[str, Any], metrics)["lexical"]
    path = tmp_path / "coordinated.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(HybridRrfArtifactError):
        validate_hybrid_rrf_artifact(
            artifact_path=path,
            protocol_path=PROTOCOL,
            dense_artifact_path=DENSE_ARTIFACT,
            repository_root=ROOT,
        )


@pytest.mark.parametrize(
    "mutation",
    (
        lambda payload: _first_fused(payload).__setitem__("rank", True),
        lambda payload: _first_fused(payload).__setitem__("locator_start", True),
        lambda payload: _first_fused(payload).__setitem__("locator_kind", "unknown"),
    ),
)
def test_artifact_validator_rejects_bool_integer_and_malformed_locator_fields(
    temporary_artifact: Path,
    mutation: ArtifactMutation,
    tmp_path: Path,
) -> None:
    payload = _load(temporary_artifact)
    mutation(payload)
    path = tmp_path / "malformed.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(HybridRrfArtifactError):
        validate_hybrid_rrf_artifact(
            artifact_path=path,
            protocol_path=PROTOCOL,
            dense_artifact_path=DENSE_ARTIFACT,
            repository_root=ROOT,
        )


def test_missing_artifact_module_cli_exits_nonzero(tmp_path: Path) -> None:
    result = subprocess.run(
        (
            sys.executable,
            "-m",
            "mke.evaluation.hybrid_rrf_artifact",
            "validate",
            "--artifact",
            str(tmp_path / "missing.json"),
            "--protocol",
            str(PROTOCOL),
            "--dense-artifact",
            str(DENSE_ARTIFACT),
            "--repository",
            str(ROOT),
        ),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr == "hybrid RRF artifact is invalid\n"
    assert "Traceback" not in result.stderr
    assert str(ROOT) not in result.stderr


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _first_fused(payload: dict[str, Any]) -> dict[str, Any]:
    development = cast(dict[str, Any], payload["development"])
    results = cast(list[dict[str, Any]], development["results"])
    fused = cast(list[dict[str, Any]], results[0]["fused_results"])
    return fused[0]
