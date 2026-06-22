from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from mke.evaluation.manifest import (
    EvaluationQuery,
    LocatorKind,
    RetrievalEvaluationManifest,
    StableLocator,
    load_retrieval_manifest,
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
_VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9]+){1,3}\Z")
_HISTORICAL_CODE_IDENTITY = {
    "main_merge_base": "721784eabcb9fbb737166578010c9e1a46a25fef",
    "implementation_start": "3992b0e9371d1a8c9e019d3bbe2b32aac9665914",
    "evaluation_commit": "79bafb07ac592b684e6ceab15dc389dc33702978",
}
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "manifest_id",
    "manifest_sha256",
    "fixtures",
    "code",
    "environment",
    "report_schema_version",
    "benchmark_scope",
    "quality_gate",
    "documents",
    "queries",
    "answerable",
    "unanswerable",
    "category_counts",
    "metrics",
    "results",
    "answerable_misses_at_5",
    "unanswerable_false_positives",
}
_METRIC_NAMES = (
    "locator_recall_at_1",
    "locator_recall_at_3",
    "locator_recall_at_5",
    "mrr_at_5",
    "answerable_zero_hit_rate",
    "unanswerable_no_hit_rate",
    "ask_refusal_rate",
)
_RESULT_FIELDS = {
    "query_id",
    "category",
    "relevant_locator_count",
    "retrieved_locator_count",
    "relevant_retrieved_at_1",
    "relevant_retrieved_at_3",
    "relevant_retrieved_at_5",
    "first_relevant_rank",
    "ask_status",
    "retrieved_locators",
}


class BaselineValidationError(ValueError):
    """The canonical baseline artifact is malformed or has invalid provenance."""


def validate_retrieval_baseline(
    *,
    artifact_path: Path,
    manifest_path: Path,
    repository_root: Path,
    main_ref: str = "main",
) -> None:
    artifact = _load_json_object(artifact_path, "baseline artifact")
    _require_exact_fields(artifact, _TOP_LEVEL_FIELDS, "baseline artifact")
    manifest = load_retrieval_manifest(manifest_path)
    _validate_identity_and_provenance(
        artifact,
        artifact_path=artifact_path,
        manifest_path=manifest_path,
        manifest=manifest,
        repository_root=repository_root.resolve(),
        main_ref=main_ref,
    )
    results = _validate_shape_and_results(artifact, manifest)
    _validate_metrics(artifact, results)


def _validate_identity_and_provenance(
    artifact: dict[str, object],
    *,
    artifact_path: Path,
    manifest_path: Path,
    manifest: RetrievalEvaluationManifest,
    repository_root: Path,
    main_ref: str,
) -> None:
    del main_ref
    if artifact["schema_version"] != "mke.retrieval_eval_baseline.v1":
        raise BaselineValidationError("baseline schema version is unsupported")
    if artifact["manifest_id"] != manifest.manifest_id:
        raise BaselineValidationError("baseline manifest identifier does not match")
    actual_manifest_sha256 = _sha256(manifest_path)
    if artifact["manifest_sha256"] != actual_manifest_sha256:
        raise BaselineValidationError("manifest checksum does not match")
    if artifact_path.resolve().is_relative_to(manifest.root):
        raise BaselineValidationError("baseline artifact must be separate from fixture root")

    expected_fixtures: list[dict[str, object]] = []
    for document in manifest.documents:
        expected_fixtures.append(
            {
                "document_id": document.document_id,
                "role": "primary",
                "bytes": document.primary_file.bytes,
                "sha256": _sha256(manifest.resolve(document.primary_file)),
            }
        )
        expected_fixtures.extend(
            {
                "document_id": document.document_id,
                "role": supporting.role,
                "bytes": supporting.bytes,
                "sha256": _sha256(manifest.resolve(supporting)),
            }
            for supporting in document.supporting_files
        )
    if artifact["fixtures"] != expected_fixtures:
        raise BaselineValidationError(
            "fixture provenance does not match manifest and files"
        )

    code = _object(artifact["code"], "baseline code identity")
    _require_exact_fields(
        code,
        {
            "main_merge_base",
            "implementation_start",
            "evaluation_commit",
            "evaluation_content_sha256",
            "evaluation_content_files",
        },
        "baseline code identity",
    )
    historical_identity = {
        name: _commit_sha(code[name], name)
        for name in ("main_merge_base", "implementation_start", "evaluation_commit")
    }
    if historical_identity != _HISTORICAL_CODE_IDENTITY:
        raise BaselineValidationError(
            "baseline code historical metadata is invalid"
        )
    _validate_evaluation_content_identity(code, repository_root)

    environment = _object(artifact["environment"], "baseline environment")
    _require_exact_fields(
        environment, {"python", "sqlite", "pymupdf"}, "baseline environment"
    )
    if any(
        not isinstance(environment[name], str)
        or _VERSION_RE.fullmatch(cast(str, environment[name])) is None
        for name in ("python", "sqlite", "pymupdf")
    ):
        raise BaselineValidationError("baseline environment is invalid")


def _validate_shape_and_results(
    artifact: dict[str, object],
    manifest: RetrievalEvaluationManifest,
) -> list[dict[str, object]]:
    answerable = sum(query.category == "answerable" for query in manifest.queries)
    unanswerable = len(manifest.queries) - answerable
    expected_counts = {
        "documents": len(manifest.documents),
        "queries": len(manifest.queries),
        "answerable": answerable,
        "unanswerable": unanswerable,
    }
    if any(artifact[name] != value for name, value in expected_counts.items()):
        raise BaselineValidationError("baseline corpus counts do not match manifest")
    if artifact["report_schema_version"] != "mke.retrieval_eval_report.v1":
        raise BaselineValidationError("baseline report schema version is unsupported")
    if artifact["benchmark_scope"] != "small_english_page_timestamp_corpus":
        raise BaselineValidationError("baseline benchmark scope is invalid")
    if artifact["quality_gate"] != "none":
        raise BaselineValidationError("baseline quality gate must be none")
    expected_category_counts = {
        category: sum(query.category == category for query in manifest.queries)
        for category in ("answerable", "lexical_confuser", "out_of_corpus")
    }
    if artifact["category_counts"] != expected_category_counts:
        raise BaselineValidationError("baseline category counts do not match manifest")

    raw_results = artifact["results"]
    if not isinstance(raw_results, list):
        raise BaselineValidationError(
            "baseline results do not match manifest query identity"
        )
    result_items = cast(list[object], raw_results)
    if len(result_items) != len(manifest.queries):
        raise BaselineValidationError(
            "baseline results do not match manifest query identity"
        )
    results = [
        _object(item, "baseline result") for item in result_items
    ]
    for query, result in zip(manifest.queries, results, strict=True):
        _validate_result(query, result, manifest)

    misses = [
        cast(str, result["query_id"])
        for result in results
        if result["category"] == "answerable"
        and result["relevant_retrieved_at_5"] == 0
    ]
    false_positives = [
        cast(str, result["query_id"])
        for result in results
        if result["category"] != "answerable"
        and cast(int, result["retrieved_locator_count"]) > 0
    ]
    if artifact["answerable_misses_at_5"] != misses:
        raise BaselineValidationError("baseline answerable misses are inconsistent")
    if artifact["unanswerable_false_positives"] != false_positives:
        raise BaselineValidationError(
            "baseline unanswerable false positives are inconsistent"
        )
    return results


def _validate_result(
    query: EvaluationQuery,
    result: dict[str, object],
    manifest: RetrievalEvaluationManifest,
) -> None:
    try:
        _require_exact_fields(result, _RESULT_FIELDS, "baseline result")
        if result["query_id"] != query.query_id or result["category"] != query.category:
            raise BaselineValidationError
        relevant_count = _integer(result["relevant_locator_count"])
        retrieved_count = _integer(result["retrieved_locator_count"])
        at_1 = _integer(result["relevant_retrieved_at_1"])
        at_3 = _integer(result["relevant_retrieved_at_3"])
        at_5 = _integer(result["relevant_retrieved_at_5"])
        if relevant_count != len(query.relevant_locators):
            raise BaselineValidationError
        if not 0 <= retrieved_count <= 5:
            raise BaselineValidationError
        if not 0 <= at_1 <= at_3 <= at_5 <= relevant_count:
            raise BaselineValidationError
        raw_locators = result["retrieved_locators"]
        if not isinstance(raw_locators, list):
            raise BaselineValidationError
        locators = cast(list[object], raw_locators)
        if len(locators) != retrieved_count:
            raise BaselineValidationError
        parsed_locators = tuple(
            _parse_locator_summary(locator, manifest) for locator in locators
        )
        if len(set(parsed_locators)) != len(parsed_locators):
            raise BaselineValidationError
        relevant = set(query.relevant_locators)
        expected_at_1 = len(relevant.intersection(parsed_locators[:1]))
        expected_at_3 = len(relevant.intersection(parsed_locators[:3]))
        expected_at_5 = len(relevant.intersection(parsed_locators[:5]))
        if (at_1, at_3, at_5) != (expected_at_1, expected_at_3, expected_at_5):
            raise BaselineValidationError
        expected_first_rank = next(
            (
                rank
                for rank, locator in enumerate(parsed_locators[:5], start=1)
                if locator in relevant
            ),
            None,
        )
        first_rank = result["first_relevant_rank"]
        if first_rank is not None and (
            isinstance(first_rank, bool)
            or not isinstance(first_rank, int)
            or not 1 <= first_rank <= 5
        ):
            raise BaselineValidationError
        if first_rank != expected_first_rank:
            raise BaselineValidationError
        ask_status = result["ask_status"]
        if ask_status not in {"evidence_found", "insufficient_evidence"}:
            raise BaselineValidationError
        if bool(retrieved_count) != (ask_status == "evidence_found"):
            raise BaselineValidationError
    except (KeyError, TypeError, ValueError, BaselineValidationError) as error:
        raise BaselineValidationError(
            "baseline results do not match manifest query identity"
        ) from error


def _validate_metrics(
    artifact: dict[str, object],
    results: list[dict[str, object]],
) -> None:
    metrics = _object(artifact["metrics"], "baseline metrics")
    try:
        _require_exact_fields(metrics, set(_METRIC_NAMES), "baseline metrics")
        answerable = [
            result for result in results if result["category"] == "answerable"
        ]
        unanswerable = [
            result for result in results if result["category"] != "answerable"
        ]
        expected_sums = {
            "locator_recall_at_1": sum(
                cast(int, result["relevant_retrieved_at_1"])
                / cast(int, result["relevant_locator_count"])
                for result in answerable
            ),
            "locator_recall_at_3": sum(
                cast(int, result["relevant_retrieved_at_3"])
                / cast(int, result["relevant_locator_count"])
                for result in answerable
            ),
            "locator_recall_at_5": sum(
                cast(int, result["relevant_retrieved_at_5"])
                / cast(int, result["relevant_locator_count"])
                for result in answerable
            ),
            "mrr_at_5": sum(
                0.0
                if result["first_relevant_rank"] is None
                else 1.0 / cast(int, result["first_relevant_rank"])
                for result in answerable
            ),
            "answerable_zero_hit_rate": sum(
                cast(int, result["retrieved_locator_count"]) == 0
                for result in answerable
            ),
            "unanswerable_no_hit_rate": sum(
                cast(int, result["retrieved_locator_count"]) == 0
                for result in unanswerable
            ),
            "ask_refusal_rate": sum(
                result["ask_status"] == "insufficient_evidence"
                for result in unanswerable
            ),
        }
        expected_counts = {
            name: len(answerable)
            if name
            in {
                "locator_recall_at_1",
                "locator_recall_at_3",
                "locator_recall_at_5",
                "mrr_at_5",
                "answerable_zero_hit_rate",
            }
            else len(unanswerable)
            for name in _METRIC_NAMES
        }
        for name in _METRIC_NAMES:
            metric = _object(metrics[name], "baseline metric")
            _require_exact_fields(metric, {"value", "sum", "count"}, "baseline metric")
            count = _integer(metric["count"])
            total = _number(metric["sum"])
            value = _number(metric["value"])
            expected_count = expected_counts[name]
            expected_sum = expected_sums[name]
            if (
                count != expected_count
                or not math.isclose(total, expected_sum, rel_tol=0.0, abs_tol=1e-12)
                or not math.isclose(
                    value,
                    round(expected_sum / expected_count, 6),
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
            ):
                raise BaselineValidationError
    except (KeyError, TypeError, ZeroDivisionError, BaselineValidationError) as error:
        raise BaselineValidationError("baseline metrics are inconsistent") from error


def _parse_locator_summary(
    value: object,
    manifest: RetrievalEvaluationManifest,
) -> StableLocator:
    if not isinstance(value, str):
        raise BaselineValidationError
    parts = value.split(":")
    if len(parts) != 3:
        raise BaselineValidationError
    document_id, kind, raw_range = parts
    if document_id not in {document.document_id for document in manifest.documents}:
        raise BaselineValidationError
    if kind not in {"page", "timestamp_ms"}:
        raise BaselineValidationError
    range_parts = raw_range.split("..")
    if len(range_parts) != 2:
        raise BaselineValidationError
    start, end = (int(item) for item in range_parts)
    if kind == "page" and (start <= 0 or end != start):
        raise BaselineValidationError
    if kind == "timestamp_ms" and (start < 0 or end <= start):
        raise BaselineValidationError
    return StableLocator(
        document_id=document_id,
        locator_kind=cast(LocatorKind, kind),
        locator_start=start,
        locator_end=end,
    )


def _load_json_object(path: Path, subject: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BaselineValidationError(f"{subject} is not readable JSON") from error
    if not isinstance(payload, dict):
        raise BaselineValidationError(f"{subject} must be an object")
    return cast(dict[str, object], payload)


def _object(value: object, subject: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise BaselineValidationError(f"{subject} must be an object")
    return cast(dict[str, object], value)


def _require_exact_fields(
    payload: dict[str, object], expected: set[str], subject: str
) -> None:
    if set(payload) != expected:
        raise BaselineValidationError(f"{subject} fields are invalid")


def _commit_sha(value: object, name: str) -> str:
    if not isinstance(value, str) or _COMMIT_RE.fullmatch(value) is None:
        raise BaselineValidationError(f"baseline code {name} is invalid")
    return value


def _validate_evaluation_content_identity(
    code: dict[str, object], repository_root: Path
) -> None:
    raw_files = code["evaluation_content_files"]
    if not isinstance(raw_files, list):
        raise BaselineValidationError("baseline evaluation content identity is invalid")
    file_items = cast(list[object], raw_files)
    files = [_object(item, "baseline evaluation content file") for item in file_items]
    try:
        expected_identity = _source_content_identity(repository_root)
    except (OSError, BaselineValidationError) as error:
        raise BaselineValidationError(
            "baseline evaluation content identity could not be verified"
        ) from error
    expected_files = cast(list[dict[str, object]], expected_identity["files"])
    if files != expected_files:
        raise BaselineValidationError("baseline evaluation content identity is invalid")
    if (
        not isinstance(code["evaluation_content_sha256"], str)
        or _SHA256_RE.fullmatch(code["evaluation_content_sha256"]) is None
        or code["evaluation_content_sha256"] != expected_identity["sha256"]
    ):
        raise BaselineValidationError("baseline evaluation content identity is invalid")


def _source_content_identity(repository_root: Path) -> dict[str, object]:
    repository_root = repository_root.resolve()
    source_paths = sorted(repository_root.glob("src/mke/**/*.py"))
    if not source_paths:
        raise BaselineValidationError
    files: list[dict[str, object]] = []
    for source_path in source_paths:
        path = source_path.resolve()
        if not path.is_relative_to(repository_root) or not path.is_file():
            raise BaselineValidationError
        files.append(
            {
                "path": path.relative_to(repository_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    encoded_files = json.dumps(
        files, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return {
        "sha256": hashlib.sha256(encoded_files).hexdigest(),
        "files": files,
    }


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BaselineValidationError
    return value


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BaselineValidationError
    result = float(value)
    if not math.isfinite(result):
        raise BaselineValidationError
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the canonical retrieval baseline artifact."
    )
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path("."))
    parser.add_argument("--main-ref", default="main")
    args = parser.parse_args(argv)
    try:
        validate_retrieval_baseline(
            artifact_path=args.artifact,
            manifest_path=args.manifest,
            repository_root=args.repository,
            main_ref=args.main_ref,
        )
    except BaselineValidationError as error:
        print(f"retrieval baseline artifact invalid: {error}")
        return 1
    print("retrieval baseline artifact valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
