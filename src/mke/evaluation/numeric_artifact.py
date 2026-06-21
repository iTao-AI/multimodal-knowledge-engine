from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import fitz  # pyright: ignore[reportMissingTypeStubs]

from mke.evaluation.baseline import (  # pyright: ignore[reportPrivateUsage]
    _source_content_identity,  # pyright: ignore[reportPrivateUsage]
)
from mke.evaluation.numeric_comparison import (
    CANDIDATE_ID,
    CANDIDATE_REVISION,
    GATE_ORDER,
    LIMITATIONS,
    load_numeric_protocol,
)

ARTIFACT_SCHEMA = "mke.retrieval_numeric_comparison_artifact.v1"
COMPARISON_SCHEMA = "mke.retrieval_numeric_comparison.v1"
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "protocol",
    "manifests",
    "fixtures",
    "candidate",
    "source",
    "environment",
    "comparison",
}
_VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9]+){1,3}\Z")


class NumericArtifactValidationError(ValueError):
    """The numeric comparison artifact or its bound inputs are invalid."""

    def __init__(self) -> None:
        super().__init__("numeric comparison artifact is invalid")


def record_numeric_artifact(
    *,
    observed_path: Path,
    artifact_path: Path,
    protocol_path: Path,
    repository_root: Path,
) -> None:
    observed = _load_object(observed_path)
    protocol = load_numeric_protocol(protocol_path)
    comparison = _canonical_comparison(observed)
    _validate_comparison_state(comparison)
    artifact = {
        "schema_version": ARTIFACT_SCHEMA,
        "protocol": {
            "id": protocol.protocol_id,
            "path": protocol.path.relative_to(repository_root.resolve()).as_posix(),
            "sha256": _sha256(protocol.path),
        },
        "manifests": {
            partition: {
                "id": protocol.loaded_manifests[partition].manifest_id,
                "path": path.relative_to(repository_root.resolve()).as_posix(),
                "sha256": _sha256(path),
            }
            for partition, path in protocol.manifests.items()
        },
        "fixtures": [
            {
                "partition": partition,
                "path": manifest.documents[0]
                .primary_file.path.as_posix(),
                "bytes": manifest.documents[0].primary_file.bytes,
                "sha256": manifest.documents[0].primary_file.sha256,
            }
            for partition, manifest in (
                ("development", protocol.loaded_manifests["development"]),
                ("holdout", protocol.loaded_manifests["holdout"]),
            )
        ],
        "candidate": {
            "id": protocol.candidate_id,
            "revision": protocol.candidate_revision,
        },
        "source": _source_content_identity(repository_root),
        "environment": {
            "python": ".".join(str(item) for item in sys.version_info[:3]),
            "sqlite": sqlite3.sqlite_version,
            "pymupdf": fitz.VersionBind,
        },
        "comparison": comparison,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def validate_numeric_artifact(
    *,
    artifact_path: Path,
    observed_path: Path,
    protocol_path: Path,
    repository_root: Path,
) -> None:
    try:
        artifact = _load_object(artifact_path)
        if set(artifact) != _TOP_LEVEL_FIELDS:
            raise NumericArtifactValidationError
        if artifact["schema_version"] != ARTIFACT_SCHEMA:
            raise NumericArtifactValidationError
        observed = _load_object(observed_path)
        expected_path = artifact_path.parent / ".expected-numeric-artifact.json"
        try:
            record_numeric_artifact(
                observed_path=observed_path,
                artifact_path=expected_path,
                protocol_path=protocol_path,
                repository_root=repository_root,
            )
            expected = _load_object(expected_path)
        finally:
            expected_path.unlink(missing_ok=True)
        _validate_environment(artifact["environment"])
        expected["environment"] = artifact["environment"]
        if artifact != expected:
            raise NumericArtifactValidationError
        _validate_comparison_state(
            cast(dict[str, object], artifact["comparison"])
        )
        if artifact["comparison"] != _canonical_comparison(observed):
            raise NumericArtifactValidationError
    except NumericArtifactValidationError:
        raise
    except Exception as error:
        raise NumericArtifactValidationError from error


def _validate_environment(value: object) -> None:
    if not isinstance(value, dict):
        raise NumericArtifactValidationError
    environment = cast(dict[str, object], value)
    if set(environment) != {"python", "sqlite", "pymupdf"}:
        raise NumericArtifactValidationError
    if any(
        not isinstance(environment[name], str)
        or _VERSION_RE.fullmatch(cast(str, environment[name])) is None
        for name in ("python", "sqlite", "pymupdf")
    ):
        raise NumericArtifactValidationError


def _canonical_comparison(observed: dict[str, object]) -> dict[str, object]:
    expected_fields = {
        "schema_version",
        "protocol_id",
        "candidate_id",
        "candidate_revision",
        "integrity_status",
        "candidate_status",
        "development",
        "holdout",
        "e1",
        "compiled_queries",
        "gates",
        "integrity_failures",
        "duration_ms",
        "limitations",
    }
    if set(observed) != expected_fields:
        raise NumericArtifactValidationError
    if observed["schema_version"] != COMPARISON_SCHEMA:
        raise NumericArtifactValidationError
    return {
        key: value
        for key, value in observed.items()
        if key != "duration_ms"
    }


def _validate_comparison_state(comparison: dict[str, object]) -> None:
    if comparison.get("protocol_id") != "retrieval-numeric-v1":
        raise NumericArtifactValidationError
    if comparison.get("candidate_id") != CANDIDATE_ID:
        raise NumericArtifactValidationError
    if comparison.get("candidate_revision") != CANDIDATE_REVISION:
        raise NumericArtifactValidationError
    if comparison.get("integrity_status") != "passed":
        raise NumericArtifactValidationError
    if comparison.get("integrity_failures") != []:
        raise NumericArtifactValidationError
    if comparison.get("limitations") != list(LIMITATIONS):
        raise NumericArtifactValidationError
    raw_gates = comparison.get("gates")
    if not isinstance(raw_gates, list):
        raise NumericArtifactValidationError
    gates = cast(list[dict[str, object]], raw_gates)
    if [gate.get("gate_id") for gate in gates] != list(GATE_ORDER):
        raise NumericArtifactValidationError
    all_passed = all(gate.get("status") == "passed" for gate in gates)
    candidate_status = comparison.get("candidate_status")
    if candidate_status == "passed" and not all_passed:
        raise NumericArtifactValidationError
    if candidate_status == "rejected" and all_passed:
        raise NumericArtifactValidationError
    if candidate_status not in {"passed", "rejected"}:
        raise NumericArtifactValidationError


def _load_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise NumericArtifactValidationError from error
    if not isinstance(payload, dict):
        raise NumericArtifactValidationError
    return cast(dict[str, object], payload)


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record or validate the numeric retrieval comparison artifact."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("record", "validate"):
        command = commands.add_parser(name)
        command.add_argument("--artifact", type=Path, required=True)
        command.add_argument("--observed", type=Path, required=True)
        command.add_argument("--protocol", type=Path, required=True)
        command.add_argument("--repository", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            record_numeric_artifact(
                observed_path=args.observed,
                artifact_path=args.artifact,
                protocol_path=args.protocol,
                repository_root=args.repository,
            )
            print("numeric comparison artifact recorded")
            return 0
        validate_numeric_artifact(
            artifact_path=args.artifact,
            observed_path=args.observed,
            protocol_path=args.protocol,
            repository_root=args.repository,
        )
    except NumericArtifactValidationError:
        print("numeric comparison artifact invalid")
        return 1
    print("numeric comparison artifact valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
