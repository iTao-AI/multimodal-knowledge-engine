from __future__ import annotations

import argparse
import hashlib
import json
import math
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
from mke.evaluation.manifest import LocatorKind, StableLocator
from mke.evaluation.metrics import AskStatus, QueryMetricInput, calculate_metrics
from mke.evaluation.numeric_comparison import (
    CANDIDATE_ID,
    CANDIDATE_REVISION,
    GATE_ORDER,
    LIMITATIONS,
    NumericProtocol,
    load_numeric_protocol,
)
from mke.retrieval import compile_fts5_query
from mke.retrieval.query_policy import numeric_grouping_eligible_tokens

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
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
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
_OBSERVATION_FIELDS = {
    "status",
    "quality_status",
    "documents",
    "queries",
    "answerable",
    "unanswerable",
    "metrics",
    "category_counts",
    "results",
    "integrity_failures",
}
_GATE_REQUIREMENTS = (
    "locked_inputs_valid",
    "six_deterministic_observations",
    "current_miss_candidate_rank_1",
    "controls_identical",
    "no_hit",
    "current_miss_candidate_rank_1",
    "controls_identical",
    "no_hit",
    "byte_identical",
    "ordered_results_identical",
    "current_miss_candidate_rank_1",
    "metrics_non_decreasing",
    "one_match_statement",
    "no_scope_expansion",
)


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
    comparison = _canonical_comparison(observed, protocol)
    _validate_comparison_state(comparison, protocol)
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
        _validate_artifact_schema(artifact)
        observed = _load_object(observed_path)
        protocol = load_numeric_protocol(protocol_path)
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
            cast(dict[str, object], artifact["comparison"]),
            protocol,
        )
        if artifact["comparison"] != _canonical_comparison(observed, protocol):
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


def _canonical_comparison(
    observed: dict[str, object],
    protocol: NumericProtocol,
) -> dict[str, object]:
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
    duration_ms = observed["duration_ms"]
    if not _is_int(duration_ms) or cast(int, duration_ms) < 0:
        raise NumericArtifactValidationError
    comparison = {
        key: value
        for key, value in observed.items()
        if key != "duration_ms"
    }
    _validate_comparison_state(comparison, protocol)
    return comparison


def _validate_artifact_schema(artifact: dict[str, object]) -> None:
    if set(artifact) != _TOP_LEVEL_FIELDS:
        raise NumericArtifactValidationError
    if artifact["schema_version"] != ARTIFACT_SCHEMA:
        raise NumericArtifactValidationError
    protocol = _require_object_fields(
        artifact["protocol"],
        {"id", "path", "sha256"},
    )
    if protocol["id"] != "retrieval-numeric-v1":
        raise NumericArtifactValidationError
    if not _is_nonempty_string(protocol["path"]):
        raise NumericArtifactValidationError
    _require_sha256(protocol["sha256"])
    manifests = _require_object_fields(
        artifact["manifests"],
        {"development", "holdout", "e1"},
    )
    for partition in ("development", "holdout", "e1"):
        _require_identity_record(manifests[partition], include_id=True)
    fixtures = _require_list(artifact["fixtures"])
    if len(fixtures) != 2:
        raise NumericArtifactValidationError
    for raw, partition in zip(
        fixtures,
        ("development", "holdout"),
        strict=True,
    ):
        fixture = _require_object_fields(
            raw,
            {"partition", "path", "bytes", "sha256"},
        )
        if fixture["partition"] != partition:
            raise NumericArtifactValidationError
        if not _is_nonempty_string(fixture["path"]):
            raise NumericArtifactValidationError
        if not _is_int(fixture["bytes"]) or cast(int, fixture["bytes"]) <= 0:
            raise NumericArtifactValidationError
        _require_sha256(fixture["sha256"])
    candidate = _require_object_fields(artifact["candidate"], {"id", "revision"})
    if candidate["id"] != CANDIDATE_ID or (
        _require_integer(candidate["revision"], minimum=1)
        != CANDIDATE_REVISION
    ):
        raise NumericArtifactValidationError
    source = _require_object_fields(artifact["source"], {"sha256", "files"})
    _require_sha256(source["sha256"])
    files = _require_list(source["files"])
    if not files:
        raise NumericArtifactValidationError
    paths: list[str] = []
    for raw in files:
        record = _require_object_fields(raw, {"path", "bytes", "sha256"})
        if not _is_nonempty_string(record["path"]):
            raise NumericArtifactValidationError
        path = cast(str, record["path"])
        paths.append(path)
        if not _is_int(record["bytes"]) or cast(int, record["bytes"]) < 0:
            raise NumericArtifactValidationError
        _require_sha256(record["sha256"])
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise NumericArtifactValidationError
    encoded_files = json.dumps(
        files,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    if source["sha256"] != hashlib.sha256(encoded_files).hexdigest():
        raise NumericArtifactValidationError
    _validate_environment(artifact["environment"])
    if not isinstance(artifact["comparison"], dict):
        raise NumericArtifactValidationError


def _require_identity_record(value: object, *, include_id: bool) -> None:
    fields = {"path", "sha256"}
    if include_id:
        fields.add("id")
    record = _require_object_fields(value, fields)
    if include_id and not _is_nonempty_string(record["id"]):
        raise NumericArtifactValidationError
    if not _is_nonempty_string(record["path"]):
        raise NumericArtifactValidationError
    _require_sha256(record["sha256"])


def _validate_comparison_state(
    comparison: dict[str, object],
    protocol: NumericProtocol,
) -> None:
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
        "limitations",
    }
    if set(comparison) != expected_fields:
        raise NumericArtifactValidationError
    if comparison.get("schema_version") != COMPARISON_SCHEMA:
        raise NumericArtifactValidationError
    if comparison.get("protocol_id") != protocol.protocol_id:
        raise NumericArtifactValidationError
    if comparison.get("candidate_id") != CANDIDATE_ID:
        raise NumericArtifactValidationError
    if (
        _require_integer(comparison.get("candidate_revision"), minimum=1)
        != CANDIDATE_REVISION
    ):
        raise NumericArtifactValidationError
    if comparison.get("integrity_status") != "passed":
        raise NumericArtifactValidationError
    if comparison.get("integrity_failures") != []:
        raise NumericArtifactValidationError
    if comparison.get("limitations") != list(LIMITATIONS):
        raise NumericArtifactValidationError
    for partition in ("development", "holdout", "e1"):
        _validate_partition(
            comparison[partition],
            protocol,
            partition,
        )
    _validate_compiled_queries(comparison["compiled_queries"], protocol)
    gates = _validate_gates(comparison["gates"])
    _validate_derivable_gates(comparison, gates)
    all_passed = all(gate["status"] == "passed" for gate in gates)
    candidate_status = comparison.get("candidate_status")
    if candidate_status == "passed" and not all_passed:
        raise NumericArtifactValidationError
    if candidate_status == "rejected" and all_passed:
        raise NumericArtifactValidationError
    if candidate_status not in {"passed", "rejected"}:
        raise NumericArtifactValidationError


def _validate_partition(
    value: object,
    protocol: NumericProtocol,
    partition: str,
) -> None:
    payload = _require_object_fields(
        value,
        {"manifest_id", "current", "candidate"},
    )
    manifest = protocol.loaded_manifests[partition]
    if payload["manifest_id"] != manifest.manifest_id:
        raise NumericArtifactValidationError
    _validate_observation(payload["current"], manifest)
    _validate_observation(payload["candidate"], manifest)


def _validate_observation(
    value: object,
    manifest: object,
) -> None:
    from mke.evaluation.manifest import RetrievalEvaluationManifest

    if not isinstance(manifest, RetrievalEvaluationManifest):
        raise NumericArtifactValidationError
    payload = _require_object_fields(value, _OBSERVATION_FIELDS)
    if (
        payload["status"] != "passed"
        or payload["quality_status"] != "baseline_recorded"
    ):
        raise NumericArtifactValidationError
    results = _require_list(payload["results"])
    if payload["integrity_failures"] != []:
        raise NumericArtifactValidationError
    if (
        _require_integer(payload["documents"], minimum=0)
        != len(manifest.documents)
    ):
        raise NumericArtifactValidationError
    if _require_integer(payload["queries"], minimum=0) != len(manifest.queries):
        raise NumericArtifactValidationError
    if len(results) != len(manifest.queries):
        raise NumericArtifactValidationError
    document_ids = frozenset(
        document.document_id
        for document in manifest.documents
    )
    parsed_results = tuple(
        _validate_result(raw, query, document_ids)
        for raw, query in zip(
            results,
            manifest.queries,
            strict=True,
        )
    )
    answerable = sum(query.category == "answerable" for query in manifest.queries)
    if _require_integer(payload["answerable"], minimum=0) != answerable:
        raise NumericArtifactValidationError
    if (
        _require_integer(payload["unanswerable"], minimum=0)
        != len(manifest.queries) - answerable
    ):
        raise NumericArtifactValidationError
    category_counts = _require_object_fields(
        payload["category_counts"],
        {"answerable", "lexical_confuser", "out_of_corpus"},
    )
    expected_category_counts = {
        category: sum(query.category == category for query in manifest.queries)
        for category in ("answerable", "lexical_confuser", "out_of_corpus")
    }
    parsed_category_counts = {
        category: _require_integer(category_counts[category], minimum=0)
        for category in ("answerable", "lexical_confuser", "out_of_corpus")
    }
    if parsed_category_counts != expected_category_counts:
        raise NumericArtifactValidationError
    expected_metrics = calculate_metrics(
        tuple(
            QueryMetricInput(
                category=query.category,
                relevant=query.relevant_locators,
                retrieved=retrieved,
                ask_status=ask_status,
            )
            for query, (retrieved, ask_status) in zip(
                manifest.queries,
                parsed_results,
                strict=True,
            )
        )
    )
    _validate_metrics(payload["metrics"], expected_metrics)


def _validate_result(
    value: object,
    query: object,
    document_ids: frozenset[str],
) -> tuple[tuple[StableLocator, ...], AskStatus]:
    from mke.evaluation.manifest import EvaluationQuery

    if not isinstance(query, EvaluationQuery):
        raise NumericArtifactValidationError
    payload = _require_object_fields(value, _RESULT_FIELDS)
    if (
        payload["query_id"] != query.query_id
        or payload["category"] != query.category
    ):
        raise NumericArtifactValidationError
    relevant = set(query.relevant_locators)
    relevant_count = _require_integer(
        payload["relevant_locator_count"],
        minimum=0,
    )
    if relevant_count != len(relevant):
        raise NumericArtifactValidationError
    locators = tuple(
        _validate_locator(item, document_ids)
        for item in _require_list(payload["retrieved_locators"])
    )
    if len(locators) != len(set(locators)):
        raise NumericArtifactValidationError
    retrieved_count = _require_integer(
        payload["retrieved_locator_count"],
        minimum=0,
        maximum=5,
    )
    if retrieved_count != len(locators):
        raise NumericArtifactValidationError
    expected_counts = (
        len(relevant.intersection(locators[:1])),
        len(relevant.intersection(locators[:3])),
        len(relevant.intersection(locators[:5])),
    )
    actual_counts = tuple(
        _require_integer(value, minimum=0, maximum=relevant_count)
        for value in (
            payload["relevant_retrieved_at_1"],
            payload["relevant_retrieved_at_3"],
            payload["relevant_retrieved_at_5"],
        )
    )
    if not actual_counts[0] <= actual_counts[1] <= actual_counts[2]:
        raise NumericArtifactValidationError
    if actual_counts != expected_counts:
        raise NumericArtifactValidationError
    expected_rank = next(
        (
            rank
            for rank, locator in enumerate(locators[:5], start=1)
            if locator in relevant
        ),
        None,
    )
    raw_rank = payload["first_relevant_rank"]
    first_relevant_rank = (
        None
        if raw_rank is None
        else _require_integer(raw_rank, minimum=1, maximum=5)
    )
    if first_relevant_rank != expected_rank:
        raise NumericArtifactValidationError
    ask_status = payload["ask_status"]
    if ask_status not in {"evidence_found", "insufficient_evidence"}:
        raise NumericArtifactValidationError
    if bool(locators) != (ask_status == "evidence_found"):
        raise NumericArtifactValidationError
    return locators, cast(AskStatus, ask_status)


def _validate_locator(
    value: object,
    document_ids: frozenset[str],
) -> StableLocator:
    payload = _require_object_fields(
        value,
        {"document_id", "locator_kind", "locator_start", "locator_end"},
    )
    if (
        not _is_nonempty_string(payload["document_id"])
        or payload["document_id"] not in document_ids
    ):
        raise NumericArtifactValidationError
    if payload["locator_kind"] not in {"page", "timestamp_ms"}:
        raise NumericArtifactValidationError
    start = payload["locator_start"]
    end = payload["locator_end"]
    if not _is_int(start) or not _is_int(end):
        raise NumericArtifactValidationError
    if payload["locator_kind"] == "page":
        if cast(int, start) <= 0 or end != start:
            raise NumericArtifactValidationError
    elif cast(int, start) < 0 or cast(int, end) <= cast(int, start):
        raise NumericArtifactValidationError
    return StableLocator(
        document_id=cast(str, payload["document_id"]),
        locator_kind=cast(LocatorKind, payload["locator_kind"]),
        locator_start=cast(int, start),
        locator_end=cast(int, end),
    )


def _validate_metrics(value: object, expected: object) -> None:
    from mke.evaluation.metrics import RetrievalMetrics

    if not isinstance(expected, RetrievalMetrics):
        raise NumericArtifactValidationError
    metrics = _require_object_fields(value, set(_METRIC_NAMES))
    for name in _METRIC_NAMES:
        metric = _require_object_fields(metrics[name], {"value", "sum", "count"})
        expected_metric = getattr(expected, name)
        value_number = _require_ratio(metric["value"])
        sum_number = _require_finite_number(metric["sum"])
        count = _require_integer(metric["count"], minimum=1)
        if not 0.0 <= sum_number <= float(count):
            raise NumericArtifactValidationError
        if (
            value_number != expected_metric.value
            or sum_number != expected_metric.sum
            or count != expected_metric.count
        ):
            raise NumericArtifactValidationError


def _validate_compiled_queries(
    value: object,
    protocol: NumericProtocol,
) -> None:
    queries = _require_list(value)
    expected = tuple(
        (partition, query)
        for partition in ("development", "holdout", "e1")
        for query in protocol.loaded_manifests[partition].queries
    )
    if len(queries) != len(expected):
        raise NumericArtifactValidationError
    for raw, (partition, query) in zip(queries, expected, strict=True):
        payload = _require_object_fields(
            raw,
            {
                "partition",
                "query_id",
                "current",
                "candidate",
                "eligible_tokens",
            },
        )
        expected_payload = {
            "partition": partition,
            "query_id": query.query_id,
            "current": compile_fts5_query(query.text, policy="current"),
            "candidate": compile_fts5_query(
                query.text,
                policy="numeric-grouping-v1",
            ),
            "eligible_tokens": list(numeric_grouping_eligible_tokens(query.text)),
        }
        if payload != expected_payload:
            raise NumericArtifactValidationError


def _validate_gates(value: object) -> list[dict[str, object]]:
    raw_gates = _require_list(value)
    if len(raw_gates) != len(GATE_ORDER):
        raise NumericArtifactValidationError
    gates: list[dict[str, object]] = []
    for raw, gate_id, required in zip(
        raw_gates,
        GATE_ORDER,
        _GATE_REQUIREMENTS,
        strict=True,
    ):
        gate = _require_object_fields(
            raw,
            {"gate_id", "status", "observed", "required", "next_step"},
        )
        if gate["gate_id"] != gate_id or gate["required"] != required:
            raise NumericArtifactValidationError
        if gate["status"] == "passed":
            if gate["observed"] != required or gate["next_step"] != "none":
                raise NumericArtifactValidationError
        elif gate["status"] == "failed":
            if gate["observed"] != "requirement_not_met" or gate["next_step"] != "do_not_promote":
                raise NumericArtifactValidationError
        else:
            raise NumericArtifactValidationError
        gates.append(gate)
    return gates


def _validate_derivable_gates(
    comparison: dict[str, object],
    gates: list[dict[str, object]],
) -> None:
    partitions = {
        partition: cast(dict[str, object], comparison[partition])
        for partition in ("development", "holdout", "e1")
    }
    results = {
        partition: {
            policy: _result_map(
                cast(dict[str, object], payload[policy])["results"]
            )
            for policy in ("current", "candidate")
        }
        for partition, payload in partitions.items()
    }
    development = results["development"]
    holdout = results["holdout"]
    e1 = results["e1"]
    development_controls = (
        "numeric-dev-compact-01",
        "numeric-dev-leading-zero-01",
        "numeric-dev-identifier-01",
        "numeric-dev-short-01",
        "numeric-dev-outside-01",
    )
    holdout_controls = (
        "numeric-holdout-compact-01",
        "numeric-holdout-leading-zero-01",
        "numeric-holdout-identifier-01",
        "numeric-holdout-short-01",
        "numeric-holdout-outside-01",
    )
    compiled_queries = cast(
        list[dict[str, object]],
        comparison["compiled_queries"],
    )
    e1_current = cast(
        dict[str, object],
        cast(dict[str, object], partitions["e1"]["current"])["metrics"],
    )
    e1_candidate = cast(
        dict[str, object],
        cast(dict[str, object], partitions["e1"]["candidate"])["metrics"],
    )
    derivable = {
        "protocol_integrity": True,
        "all_evaluations_deterministic": all(
            cast(dict[str, object], partitions[partition][policy])["status"]
            == "passed"
            for partition in ("development", "holdout", "e1")
            for policy in ("current", "candidate")
        ),
        "development_grouped_improves": (
            development["current"][
                "numeric-dev-grouped-01"
            ]["first_relevant_rank"]
            is None
            and development["candidate"][
                "numeric-dev-grouped-01"
            ]["first_relevant_rank"]
            == 1
        ),
        "development_controls_preserved": all(
            development["current"][query_id]
            == development["candidate"][query_id]
            for query_id in development_controls
        ),
        "development_non_adjacent_no_hit": (
            development["candidate"][
                "numeric-dev-non-adjacent-01"
            ]["retrieved_locator_count"]
            == 0
        ),
        "holdout_grouped_improves": (
            holdout["current"][
                "numeric-holdout-grouped-01"
            ]["first_relevant_rank"]
            is None
            and holdout["candidate"][
                "numeric-holdout-grouped-01"
            ]["first_relevant_rank"]
            == 1
        ),
        "holdout_controls_preserved": all(
            holdout["current"][query_id] == holdout["candidate"][query_id]
            for query_id in holdout_controls
        ),
        "holdout_non_adjacent_no_hit": (
            holdout["candidate"][
                "numeric-holdout-non-adjacent-01"
            ]["retrieved_locator_count"]
            == 0
        ),
        "noneligible_compilation_identity": all(
            item["current"] == item["candidate"]
            for item in compiled_queries
            if item["eligible_tokens"] == []
        ),
        "e1_unrelated_exact": all(
            e1["current"][query_id] == e1["candidate"][query_id]
            for query_id in e1["current"]
            if query_id != "water-answerable-01"
        ),
        "e1_water_answerable_rank_1": (
            e1["current"]["water-answerable-01"]["first_relevant_rank"]
            is None
            and e1["candidate"][
                "water-answerable-01"
            ]["first_relevant_rank"]
            == 1
        ),
        "e1_aggregate_non_regression": all(
            _metric_value(e1_candidate, name)
            >= _metric_value(e1_current, name)
            for name in (
                "locator_recall_at_1",
                "locator_recall_at_3",
                "locator_recall_at_5",
                "mrr_at_5",
            )
        ),
    }
    gate_by_id = {
        cast(str, gate["gate_id"]): gate
        for gate in gates
    }
    for gate_id, passed in derivable.items():
        expected_status = "passed" if passed else "failed"
        if gate_by_id[gate_id]["status"] != expected_status:
            raise NumericArtifactValidationError


def _result_map(value: object) -> dict[str, dict[str, object]]:
    return {
        cast(str, result["query_id"]): result
        for result in cast(list[dict[str, object]], value)
    }


def _metric_value(metrics: dict[str, object], name: str) -> float:
    metric = cast(dict[str, object], metrics[name])
    return _require_ratio(metric["value"])


def _require_object_fields(
    value: object,
    fields: set[str],
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise NumericArtifactValidationError
    payload = cast(dict[str, object], value)
    if set(payload) != fields:
        raise NumericArtifactValidationError
    return payload


def _require_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise NumericArtifactValidationError
    return cast(list[object], value)


def _require_sha256(value: object) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise NumericArtifactValidationError


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_integer(
    value: object,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if not _is_int(value):
        raise NumericArtifactValidationError
    result = cast(int, value)
    if result < minimum or (maximum is not None and result > maximum):
        raise NumericArtifactValidationError
    return result


def _require_finite_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NumericArtifactValidationError
    result = float(value)
    if not math.isfinite(result):
        raise NumericArtifactValidationError
    return result


def _require_ratio(value: object) -> float:
    result = _require_finite_number(value)
    if not 0.0 <= result <= 1.0:
        raise NumericArtifactValidationError
    return result


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _load_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise NumericArtifactValidationError from error
    if not isinstance(payload, dict):
        raise NumericArtifactValidationError
    return cast(dict[str, object], payload)


def _sha256(path: Path) -> str:
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
