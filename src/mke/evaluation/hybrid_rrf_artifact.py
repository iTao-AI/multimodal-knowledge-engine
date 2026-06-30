"""Canonical model-free E3-D hybrid RRF comparison artifact."""

from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from mke.evaluation.hybrid_rrf_workflow import (
    build_hybrid_rrf_development_freeze,
    run_hybrid_rrf_development,
)

ARTIFACT_SCHEMA = "mke.hybrid_rrf_comparison_artifact.v1"


class HybridRrfArtifactError(ValueError):
    """The hybrid RRF artifact failed a frozen integrity rule."""

    def __init__(self) -> None:
        super().__init__("hybrid RRF artifact is invalid")


def build_hybrid_rrf_comparison_artifact(
    *,
    report: dict[str, object],
) -> dict[str, Any]:
    """Build the canonical development-only artifact for a valid negative."""
    try:
        if (
            report.get("schema_version") != "mke.hybrid_rrf_development.v1"
            or report.get("development_status") != "valid_negative"
            or report.get("holdout_status") != "not_observed"
            or report.get("runtime_promotion_status") != "not_evaluated"
        ):
            raise HybridRrfArtifactError
        diagnostics = _object(report.get("diagnostics"))
        freeze = build_hybrid_rrf_development_freeze(report=report)
        artifact = {
            "schema_version": ARTIFACT_SCHEMA,
            "candidate": _object(report.get("candidate")),
            "candidate_status": "completed",
            "development_status": "valid_negative",
            "holdout_status": "not_observed",
            "runtime_promotion_status": "not_evaluated",
            "e3e_status": _followup_status(diagnostics),
            "segmentation_status": _segmentation_status(diagnostics),
            "development": report,
            "holdout": None,
            "state": {
                "development_freeze_sha256": _payload_sha256(freeze),
                "holdout_receipt_sha256": None,
            },
        }
        return _json_normalized(artifact)
    except HybridRrfArtifactError:
        raise
    except Exception as error:
        raise HybridRrfArtifactError from error


def validate_hybrid_rrf_artifact(
    *,
    artifact_path: Path,
    protocol_path: Path,
    dense_artifact_path: Path,
    repository_root: Path,
) -> None:
    """Recompute and validate the canonical E3-D artifact without model loading."""
    try:
        artifact = _load_artifact(artifact_path)
        report = run_hybrid_rrf_development(
            protocol_path=protocol_path,
            dense_artifact_path=dense_artifact_path,
            repository_root=repository_root,
        )
        expected = build_hybrid_rrf_comparison_artifact(report=report)
        if _canonical_json(artifact) != _canonical_json(expected):
            raise HybridRrfArtifactError
    except HybridRrfArtifactError:
        raise
    except Exception as error:
        raise HybridRrfArtifactError from error


def render_hybrid_rrf_artifact_json(artifact: dict[str, Any]) -> str:
    return json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m mke.evaluation.hybrid_rrf_artifact"
    )
    parser.add_argument("command", choices=("validate",))
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--dense-artifact", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        validate_hybrid_rrf_artifact(
            artifact_path=args.artifact,
            protocol_path=args.protocol,
            dense_artifact_path=args.dense_artifact,
            repository_root=args.repository,
        )
    except Exception:
        print("hybrid RRF artifact is invalid", file=sys.stderr)
        return 1
    print("hybrid RRF artifact valid")
    return 0


def _load_artifact(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HybridRrfArtifactError from error
    if not isinstance(payload, dict):
        raise HybridRrfArtifactError
    return cast(dict[str, Any], payload)


def _payload_sha256(payload: dict[str, object]) -> str:
    return sha256(_canonical_json(payload).encode()).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _followup_status(diagnostics: dict[str, Any]) -> str:
    value = diagnostics.get("ranking_headroom_count")
    if type(value) is not int or value < 0:
        raise HybridRrfArtifactError
    return "eligible" if value > 0 else "not_evaluated"


def _segmentation_status(diagnostics: dict[str, Any]) -> str:
    value = diagnostics.get("neither_arm_miss_count")
    if type(value) is not int or value < 0:
        raise HybridRrfArtifactError
    return "eligible" if value > 0 else "not_evaluated"


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HybridRrfArtifactError
    return cast(dict[str, Any], value)


def _json_normalized(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(value, ensure_ascii=False)))


if __name__ == "__main__":
    raise SystemExit(main())
