"""Validator for E3-E relevance gate comparison artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from mke.evaluation.relevance_gate_workflow import (
    build_relevance_gate_development_freeze,
    build_relevance_gate_holdout_report,
    run_relevance_gate_development,
)

_FORBIDDEN_FEATURE_KEYS = frozenset(
    {
        "qrel",
        "qrels",
        "qrel_grade",
        "qrel_grades",
        "grade",
        "grades",
        "category",
        "query_category",
        "split",
        "expected_locator",
        "expected_locators",
    }
)


class RelevanceGateArtifactError(ValueError):
    """Raised when the E3-E comparison artifact is invalid."""


def validate_relevance_gate_artifact(
    *,
    artifact_path: Path,
    protocol_path: Path,
    repository_root: Path,
) -> None:
    root = repository_root.resolve()
    artifact = _load_json(artifact_path, "artifact")
    _validate_state(artifact, repository_root=root)
    _scan_feature_rows(artifact)
    if artifact.get("development_status") != "passed":
        if artifact.get("holdout_status") == "observed":
            raise RelevanceGateArtifactError("holdout observed before passed development")
    development_report = run_relevance_gate_development(
        protocol_path=protocol_path,
        candidate_id="cjk-relevance-gate-reranker-v1",
        repository_root=root,
    )
    expected_freeze = build_relevance_gate_development_freeze(
        report=development_report
    )
    if artifact.get("development") != expected_freeze:
        raise RelevanceGateArtifactError("development freeze recompute mismatch")
    if artifact.get("holdout_status") == "observed":
        selected = _string(artifact.get("selected_profile"), "selected profile")
        expected_holdout = build_relevance_gate_holdout_report(
            protocol_path=protocol_path,
            selected_profile=selected,
            repository_root=root,
        )
        if artifact.get("holdout") != expected_holdout:
            if _feature_rows(artifact) != _feature_rows({"holdout": expected_holdout}):
                raise RelevanceGateArtifactError("feature row recompute mismatch")
            raise RelevanceGateArtifactError("artifact recompute mismatch")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mke.evaluation.relevance_gate_artifact")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--artifact", required=True)
    validate.add_argument("--protocol", required=True)
    validate.add_argument("--repository", required=True)
    args = parser.parse_args(argv)
    if args.command == "validate":
        try:
            validate_relevance_gate_artifact(
                artifact_path=Path(args.artifact),
                protocol_path=Path(args.protocol),
                repository_root=Path(args.repository),
            )
        except RelevanceGateArtifactError as error:
            print(
                json.dumps(
                    {
                        "problem": "relevance_gate_artifact_invalid",
                        "cause": str(error),
                        "next_step": "regenerate_or_recompute_e3e_artifact",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 1
        print("relevance gate artifact valid")
        return 0
    return 1


def _validate_state(artifact: dict[str, Any], *, repository_root: Path) -> None:
    if artifact.get("schema_version") != "mke.relevance_gate_comparison_artifact.v1":
        raise RelevanceGateArtifactError("artifact schema is invalid")
    if artifact.get("candidate_status") != "completed":
        raise RelevanceGateArtifactError("candidate status is invalid")
    if artifact.get("runtime_promotion_status") != "not_evaluated":
        raise RelevanceGateArtifactError("runtime promotion status is invalid")
    state = _object(artifact.get("state"), "state")
    freeze_path = _repository_path(
        repository_root,
        _string(state.get("development_freeze_path"), "development freeze path"),
    )
    if not freeze_path.exists():
        raise RelevanceGateArtifactError("development freeze is missing")
    if state.get("development_freeze_sha256") != _file_sha256(freeze_path):
        raise RelevanceGateArtifactError("development freeze identity mismatch")
    if artifact.get("holdout_status") == "observed":
        receipt_path = _repository_path(
            repository_root,
            _string(state.get("holdout_receipt_path"), "holdout receipt path"),
        )
        if not receipt_path.exists():
            raise RelevanceGateArtifactError("holdout receipt is missing")
        if state.get("holdout_receipt_sha256") != _file_sha256(receipt_path):
            raise RelevanceGateArtifactError("holdout receipt identity mismatch")


def _scan_feature_rows(artifact: dict[str, Any]) -> None:
    for feature in _feature_rows(artifact):
        forbidden = set(feature) & _FORBIDDEN_FEATURE_KEYS
        if forbidden:
            raise RelevanceGateArtifactError("forbidden scoring input leakage")
        for key in ("locator_start", "locator_end"):
            if type(feature.get(key)) is not int:
                raise RelevanceGateArtifactError("feature row integer is invalid")
        digest = feature.get("source_text_digest")
        if type(digest) is not str or len(digest) != 64:
            raise RelevanceGateArtifactError("feature source digest is invalid")


def _feature_rows(artifact: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for section_name in ("development", "holdout"):
        section_value = artifact.get(section_name)
        if not isinstance(section_value, dict):
            continue
        section = cast(dict[str, object], section_value)
        raw_results = section.get("results")
        if raw_results is None:
            continue
        for result in _list(raw_results, f"{section_name} results"):
            result_data = _object(result, "result")
            for feature in _list(
                result_data.get("feature_rows"),
                "feature rows",
            ):
                rows.append(_object(feature, "feature row"))
    return rows


def _load_json(path: Path, subject: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RelevanceGateArtifactError(f"{subject} is invalid") from error
    if not isinstance(payload, dict):
        raise RelevanceGateArtifactError(f"{subject} is invalid")
    return cast(dict[str, Any], payload)


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _repository_path(root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise RelevanceGateArtifactError("repository path is invalid")
    resolved = (root / relative_path).resolve()
    if not resolved.is_relative_to(root):
        raise RelevanceGateArtifactError("repository path is invalid")
    return resolved


def _object(value: object, subject: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RelevanceGateArtifactError(f"{subject} is invalid")
    return cast(dict[str, Any], value)


def _list(value: object, subject: str) -> list[object]:
    if not isinstance(value, list):
        raise RelevanceGateArtifactError(f"{subject} is invalid")
    return cast(list[object], value)


def _string(value: object, subject: str) -> str:
    if type(value) is not str or not value:
        raise RelevanceGateArtifactError(f"{subject} is invalid")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
