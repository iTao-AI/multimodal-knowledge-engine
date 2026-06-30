"""Canonical model-free E3-C dense comparison artifact."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections.abc import Callable
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from mke.adapters.vector.exact_cosine import EXACT_COSINE_ADAPTER_ID
from mke.embeddings.contracts import (
    CANDIDATE_ID,
    CANDIDATE_REVISION,
    EMBEDDING_DIMENSION,
    MODEL_ID,
    MODEL_REVISION,
)
from mke.evaluation.chinese_protocol import (
    ChineseEvaluationQuery,
    ChineseRetrievalProtocol,
    load_chinese_retrieval_protocol,
)
from mke.evaluation.dense_comparison import (
    DenseArmEvidence,
    DenseComparisonIdentity,
    DenseComparisonState,
    DenseHoldoutEvidence,
    DensePartitionObservation,
    freeze_dense_development,
)
from mke.evaluation.dense_compatibility import (
    DenseCorpusLock,
    load_dense_corpus_lock,
    validate_dense_compatibility_report,
)
from mke.evaluation.dense_protocol import load_dense_protocol_lock
from mke.evaluation.dense_threshold import (
    DenseThresholdInput,
    select_dense_threshold,
)
from mke.evaluation.graded_metrics import (
    GradedQueryMetricInput,
    calculate_graded_metrics,
)
from mke.evaluation.manifest import StableLocator

ARTIFACT_SCHEMA = "mke.dense_comparison_artifact.v1"
_PROTOCOL_PATH = "tests/fixtures/retrieval-chinese-v1/protocol.json"
_CORPUS_LOCK_PATH = "tests/fixtures/retrieval-dense-v1/corpus-lock.json"
_COMPATIBILITY_PATH = "benchmarks/retrieval/qwen3-embedding-0.6b-compatibility.json"
_E3A_PATH = "benchmarks/retrieval/retrieval-chinese-v1-baseline.json"
_E3B_PATH = "benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json"
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_FINGERPRINT_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SOURCE_PATHS = (
    "pyproject.toml",
    "uv.lock",
    ".github/workflows/ci.yml",
    "src/mke/cli.py",
    "src/mke/evaluation/dense_artifact.py",
    "src/mke/evaluation/dense_candidate.py",
    "src/mke/evaluation/dense_comparison.py",
    "src/mke/evaluation/dense_protocol.py",
    "src/mke/evaluation/dense_replay.py",
    "src/mke/evaluation/dense_threshold.py",
    "src/mke/evaluation/dense_workflow.py",
    "src/mke/evaluation/graded_metrics.py",
    "scripts/dense_retrieval_measurement.py",
)


class DenseArtifactValidationError(ValueError):
    """The dense comparison artifact failed a frozen integrity rule."""

    def __init__(self) -> None:
        super().__init__("dense comparison artifact is invalid")


def build_dense_comparison_artifact(
    *,
    protocol_path: Path,
    repository_root: Path,
    development_candidate: dict[str, Any],
    holdout_candidate: dict[str, Any] | None,
    current_runtime_payload: dict[str, Any],
    development_freeze_sha256: str,
    holdout_receipt_sha256: str | None,
) -> dict[str, Any]:
    """Recompute every deterministic artifact field from recorded observations."""
    root = repository_root.resolve()
    protocol = load_dense_protocol_lock(protocol_path, repository_root=root)
    chinese = load_chinese_retrieval_protocol(root / _PROTOCOL_PATH)
    corpus = load_dense_corpus_lock(root / _CORPUS_LOCK_PATH, repository_root=root)
    compatibility = _compatibility(root, corpus)
    runtime = normalize_current_runtime_semantics(current_runtime_payload, chinese)
    development = _canonical_candidate(
        development_candidate,
        partition="development",
        protocol=protocol,
        corpus=corpus,
        chinese=chinese,
        model_fingerprint=compatibility["model_fingerprint"],
    )
    threshold_inputs = derive_dense_threshold_inputs(
        development,
        partition="development",
        chinese=chinese,
        runtime=runtime,
    )
    threshold_report = select_dense_threshold(threshold_inputs)
    historical = {
        "e3a": _file_identity(root, _E3A_PATH),
        "e3b": _file_identity(root, _E3B_PATH),
    }
    runtime_digest = _digest(runtime)
    development_projection = cast(dict[str, Any], development["projection"])
    partition_contract = cast(dict[str, Any], protocol["partitions"])["development"]
    freeze = freeze_dense_development(
        e3a=DenseArmEvidence(
            "e3a-historical-fts5-baseline", historical["e3a"]["sha256"]
        ),
        e3b=DenseArmEvidence(
            "cjk-trigram-overlap-v1", historical["e3b"]["sha256"]
        ),
        current_runtime_expected_digest=runtime_digest,
        current_runtime_observed_digest=runtime_digest,
        threshold_report=threshold_report,
        identity=_comparison_identity(),
        snapshot_id=cast(str, partition_contract["snapshot_id"]),
        projection_id=cast(str, development_projection["projection_id"]),
    )
    state = DenseComparisonState()
    holdout: dict[str, Any] | None = None
    if freeze.development_status == "passed":
        if holdout_candidate is None or holdout_receipt_sha256 is None:
            raise DenseArtifactValidationError
        holdout = _canonical_candidate(
            holdout_candidate,
            partition="holdout",
            protocol=protocol,
            corpus=corpus,
            chinese=chinese,
            model_fingerprint=compatibility["model_fingerprint"],
        )
        holdout_evidence = _holdout_evidence(
            holdout,
            chinese=chinese,
            runtime=runtime,
            threshold=cast(float, freeze.selected_threshold),
        )
        comparison = state.complete(freeze, holdout_loader=lambda: holdout_evidence)
    else:
        if holdout_candidate is not None or holdout_receipt_sha256 is not None:
            raise DenseArtifactValidationError
        comparison = state.complete(
            freeze,
            holdout_loader=lambda: _unreachable_holdout(),
        )
    _sha256(development_freeze_sha256)
    if holdout_receipt_sha256 is not None:
        _sha256(holdout_receipt_sha256)

    artifact = {
        "schema_version": ARTIFACT_SCHEMA,
        "protocol": _file_identity(
            root,
            protocol_path.resolve().relative_to(root).as_posix(),
        ),
        "compatibility": compatibility,
        "historical_arms": historical,
        "source": dense_source_identity(root),
        "current_runtime": {
            "strategy": "cjk-active-scan-overlap-v1",
            "semantic_digest": runtime_digest,
            "semantics": runtime,
        },
        "candidate": {
            "candidate_id": CANDIDATE_ID,
            "candidate_revision": CANDIDATE_REVISION,
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "adapter_id": EXACT_COSINE_ADAPTER_ID,
        },
        "development_candidate": development,
        "holdout_candidate": holdout,
        "threshold_report": threshold_report,
        "metrics": {
            "development": _partition_metrics(
                development,
                partition="development",
                chinese=chinese,
                threshold=cast(float, threshold_report["selected_threshold"] or 0.0),
            ),
            "holdout": (
                _partition_metrics(
                    holdout,
                    partition="holdout",
                    chinese=chinese,
                    threshold=cast(float, threshold_report["selected_threshold"]),
                )
                if holdout is not None
                else None
            ),
        },
        "comparison": comparison,
        "state": {
            "development_freeze_sha256": development_freeze_sha256,
            "holdout_receipt_sha256": holdout_receipt_sha256,
        },
    }
    return _json_normalized(artifact)


def validate_dense_comparison_artifact(
    artifact: dict[str, Any],
    *,
    protocol_path: Path,
    repository_root: Path,
    current_runtime_loader: Callable[[], dict[str, Any]] | None = None,
) -> None:
    """Validate deterministic content without importing an embedding runtime."""
    try:
        if artifact.get("schema_version") != ARTIFACT_SCHEMA:
            raise DenseArtifactValidationError
        state = _object(artifact.get("state"))
        development_sha = _sha256(state.get("development_freeze_sha256"))
        receipt_value = state.get("holdout_receipt_sha256")
        receipt_sha = None if receipt_value is None else _sha256(receipt_value)
        current_runtime = _object(artifact.get("current_runtime"))
        loader = current_runtime_loader or (
            lambda: _object(current_runtime.get("semantics"))
        )
        expected = build_dense_comparison_artifact(
            protocol_path=protocol_path,
            repository_root=repository_root,
            development_candidate=_object(artifact.get("development_candidate")),
            holdout_candidate=(
                None
                if artifact.get("holdout_candidate") is None
                else _object(artifact.get("holdout_candidate"))
            ),
            current_runtime_payload=loader(),
            development_freeze_sha256=development_sha,
            holdout_receipt_sha256=receipt_sha,
        )
        if artifact != expected:
            raise DenseArtifactValidationError
    except DenseArtifactValidationError:
        raise
    except Exception as error:
        raise DenseArtifactValidationError from error


def render_dense_comparison_artifact_json(artifact: dict[str, Any]) -> str:
    return json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mke.evaluation.dense_artifact")
    parser.add_argument("command", choices=("validate",))
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.artifact.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise DenseArtifactValidationError
        validate_dense_comparison_artifact(
            cast(dict[str, Any], payload),
            protocol_path=args.protocol,
            repository_root=args.repository,
        )
    except Exception:
        print("dense comparison artifact is invalid", file=sys.stderr)
        return 1
    print("dense comparison artifact valid")
    return 0


def _canonical_candidate(
    report: dict[str, Any],
    *,
    partition: str,
    protocol: dict[str, object],
    corpus: DenseCorpusLock,
    chinese: ChineseRetrievalProtocol,
    model_fingerprint: object,
) -> dict[str, Any]:
    canonical_keys = {
        "schema_version",
        "candidate_id",
        "candidate_revision",
        "partition",
        "snapshot",
        "projection",
        "observations",
    }
    report_keys = frozenset(report)
    if report_keys not in {
        frozenset(canonical_keys),
        frozenset((*canonical_keys, "duration_ms")),
    } or (
        report.get("schema_version") != "mke.dense_candidate_observations.v1"
        or report.get("candidate_id") != CANDIDATE_ID
        or report.get("candidate_revision") != CANDIDATE_REVISION
        or type(report.get("candidate_revision")) is not int
        or report.get("partition") != partition
    ):
        raise DenseArtifactValidationError
    if "duration_ms" in report and (
        type(report["duration_ms"]) is not int or report["duration_ms"] < 0
    ):
        raise DenseArtifactValidationError
    snapshot = _object(report.get("snapshot"))
    projection = _object(report.get("projection"))
    projection_identity = _object(projection.get("identity"))
    pages = tuple(item for item in corpus.pages if item.split == partition)
    stable_by_locator = {
        (item.document_id, item.page): (
            f"{item.document_id}|page|{item.page}|{item.page}|{item.text_sha256}"
        )
        for item in pages
    }
    stable_ids = sorted(stable_by_locator.values())
    source_digests = [item.rsplit("|", 1)[-1] for item in stable_ids]
    contract = cast(dict[str, dict[str, object]], protocol["partitions"])[partition]
    if snapshot != {
        "snapshot_id": contract["snapshot_id"],
        "evidence_count": len(pages),
        "source_text_digest": _digest(source_digests),
        "locator_digest": _digest(stable_ids),
    }:
        raise DenseArtifactValidationError
    if (
        projection.get("projection_id") != contract["projection_id"]
        or projection.get("adapter_id") != EXACT_COSINE_ADAPTER_ID
        or projection_identity.get("adapter_id") != EXACT_COSINE_ADAPTER_ID
        or projection_identity.get("model_fingerprint") != model_fingerprint
        or projection_identity.get("dimension") != EMBEDDING_DIMENSION
        or projection_identity.get("row_count") != len(pages)
        or projection_identity.get("locator_digest") != _digest(stable_ids)
        or projection_identity.get("source_text_digest") != _digest(source_digests)
        or _FINGERPRINT_RE.fullmatch(
            cast(str, projection_identity.get("vector_digest", ""))
        )
        is None
    ):
        raise DenseArtifactValidationError
    raw_observations = report.get("observations")
    if not isinstance(raw_observations, list):
        raise DenseArtifactValidationError
    observation_values = cast(list[object], raw_observations)
    expected_queries = tuple(item for item in chinese.queries if item.split == partition)
    if len(observation_values) != len(expected_queries):
        raise DenseArtifactValidationError
    observations: list[dict[str, Any]] = []
    for raw, query in zip(observation_values, expected_queries, strict=True):
        observation = _object(raw)
        latency = observation.get("latency_ms")
        if (
            observation.get("query_id") != query.query_id
            or observation.get("split") != partition
            or observation.get("category") != query.category
            or observation.get("threshold") != 0.0
            or (
                latency is not None
                and (type(latency) is not int or latency < 0)
            )
        ):
            raise DenseArtifactValidationError
        results = _candidate_results(
            observation.get("results"), stable_by_locator=stable_by_locator
        )
        observations.append(
            {
                "query_id": query.query_id,
                "split": partition,
                "category": query.category,
                "threshold": 0.0,
                "results": results,
            }
        )
    return {
        "schema_version": "mke.dense_candidate_observations.v1",
        "candidate_id": CANDIDATE_ID,
        "candidate_revision": CANDIDATE_REVISION,
        "partition": partition,
        "snapshot": snapshot,
        "projection": projection,
        "observations": observations,
    }


def _candidate_results(
    value: object,
    *,
    stable_by_locator: dict[tuple[str, int], str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise DenseArtifactValidationError
    raw_results = cast(list[object], value)
    if len(raw_results) > 10:
        raise DenseArtifactValidationError
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for expected_rank, raw in enumerate(raw_results, start=1):
        result = _object(raw)
        locator = _object(result.get("locator"))
        document_id = locator.get("document_id")
        start = locator.get("locator_start")
        if (
            set(locator)
            != {"document_id", "locator_kind", "locator_start", "locator_end"}
            or type(document_id) is not str
            or locator.get("locator_kind") != "page"
            or type(start) is not int
            or locator.get("locator_end") != start
        ):
            raise DenseArtifactValidationError
        stable_id = stable_by_locator.get((document_id, start))
        score = result.get("portable_score")
        raw_score = result.get("raw_score")
        if (
            set(result)
            != {
                "stable_locator_id",
                "rank",
                "portable_score",
                "raw_score",
                "adapter_id",
                "locator",
            }
            or stable_id is None
            or result.get("stable_locator_id") != stable_id
            or stable_id in seen
            or result.get("rank") != expected_rank
            or type(result.get("rank")) is not int
            or type(score) is not float
            or not math.isfinite(score)
            or not -1.0 <= score <= 1.0
            or round(score, 6) != score
            or type(raw_score) is not float
            or not math.isfinite(raw_score)
            or abs(raw_score - score) > 1e-5
            or result.get("adapter_id") != EXACT_COSINE_ADAPTER_ID
        ):
            raise DenseArtifactValidationError
        seen.add(stable_id)
        results.append(dict(result))
    if results != sorted(
        results,
        key=lambda item: (-item["portable_score"], item["stable_locator_id"]),
    ):
        raise DenseArtifactValidationError
    return results


def derive_dense_threshold_inputs(
    candidate: dict[str, Any],
    *,
    partition: str,
    chinese: ChineseRetrievalProtocol,
    runtime: dict[str, Any],
) -> tuple[DenseThresholdInput, ...]:
    runtime_by_id = {
        item["query_id"]: item for item in cast(list[dict[str, Any]], runtime["results"])
    }
    query_by_id = {
        item.query_id: item for item in chinese.queries if item.split == partition
    }
    inputs: list[DenseThresholdInput] = []
    for observation in cast(list[dict[str, Any]], candidate["observations"]):
        query = query_by_id[cast(str, observation["query_id"])]
        ranked = _ranked_grades(observation, query)
        grade_two_scores = [score for score, grade in ranked if grade == 2]
        hard_score = _hard_negative_failure_score(ranked)
        results = cast(list[dict[str, Any]], observation["results"])
        runtime_item = runtime_by_id[query.query_id]
        current_runtime_missed = (
            query.category != "unanswerable"
            and not cast(list[object], runtime_item["direct_ranks"])
        )
        inputs.append(
            DenseThresholdInput(
                query_id=query.query_id,
                category=query.category,
                current_runtime_missed=current_runtime_missed,
                recovery_score=(
                    max(grade_two_scores, default=None)
                    if current_runtime_missed
                    else None
                ),
                dense_ndcg_at_10=0.0,
                unanswerable_top_score=(
                    cast(float, results[0]["portable_score"])
                    if query.category == "unanswerable" and results
                    else (-1.0 if query.category == "unanswerable" else None)
                ),
                hard_negative_failure_score=(
                    hard_score if any(item.grade == 0 for item in query.qrels) else None
                ),
                ranked_scores_and_grades=ranked,
                ideal_grades=tuple(
                    sorted((item.grade for item in query.qrels), reverse=True)
                ),
            )
        )
    return tuple(inputs)


def _holdout_evidence(
    candidate: dict[str, Any],
    *,
    chinese: ChineseRetrievalProtocol,
    runtime: dict[str, Any],
    threshold: float,
) -> DenseHoldoutEvidence:
    runtime_by_id = {
        item["query_id"]: item for item in cast(list[dict[str, Any]], runtime["results"])
    }
    query_by_id = {item.query_id: item for item in chinese.queries if item.split == "holdout"}
    observations: list[DensePartitionObservation] = []
    for item in cast(list[dict[str, Any]], candidate["observations"]):
        query = query_by_id[cast(str, item["query_id"])]
        ranked = tuple(
            pair for pair in _ranked_grades(item, query) if pair[0] >= threshold
        )
        runtime_item = runtime_by_id[query.query_id]
        observations.append(
            DensePartitionObservation(
                query_id=query.query_id,
                category=query.category,
                current_runtime_missed=(
                    query.category != "unanswerable"
                    and not cast(list[object], runtime_item["direct_ranks"])
                ),
                recovered_grade2=any(grade == 2 for _, grade in ranked),
                unanswerable_no_hit=(
                    not ranked if query.category == "unanswerable" else None
                ),
                hard_negative_failure=(
                    _hard_negative_failure(ranked)
                    if any(qrel.grade == 0 for qrel in query.qrels)
                    else None
                ),
            )
        )
    projection = cast(dict[str, Any], candidate["projection"])
    snapshot = cast(dict[str, Any], candidate["snapshot"])
    return DenseHoldoutEvidence(
        identity=_comparison_identity(),
        snapshot_id=cast(str, snapshot["snapshot_id"]),
        projection_id=cast(str, projection["projection_id"]),
        selected_threshold=threshold,
        observations=tuple(observations),
    )


def _partition_metrics(
    candidate: dict[str, Any],
    *,
    partition: str,
    chinese: ChineseRetrievalProtocol,
    threshold: float,
) -> dict[str, Any]:
    query_by_id = {
        item.query_id: item for item in chinese.queries if item.split == partition
    }
    metric_inputs: list[GradedQueryMetricInput] = []
    for item in cast(list[dict[str, Any]], candidate["observations"]):
        query = query_by_id[cast(str, item["query_id"])]
        results = tuple(
            result
            for result in cast(list[dict[str, Any]], item["results"])
            if cast(float, result["portable_score"]) >= threshold
        )
        retrieved = tuple(_stable_locator(result) for result in results)
        direct = {qrel.locator for qrel in query.qrels if qrel.grade == 2}
        found = any(locator in direct for locator in retrieved)
        metric_inputs.append(
            GradedQueryMetricInput(
                query_id=query.query_id,
                category=query.category,
                qrels=query.qrels,
                retrieved=retrieved,
                ask_status=(
                    "insufficient_evidence"
                    if query.category == "unanswerable" or not found
                    else "evidence_found"
                ),
                compiled_query_empty=False,
                ascii_token_count=0,
            )
        )
    return _json_normalized(asdict(calculate_graded_metrics(tuple(metric_inputs))))


def _ranked_grades(
    observation: dict[str, Any], query: ChineseEvaluationQuery
) -> tuple[tuple[float, int], ...]:
    grades = {item.locator: item.grade for item in query.qrels}
    return tuple(
        (cast(float, result["portable_score"]), grades.get(_stable_locator(result), 0))
        for result in cast(list[dict[str, Any]], observation["results"])
    )


def _stable_locator(result: dict[str, Any]) -> StableLocator:
    locator = cast(dict[str, Any], result["locator"])
    return StableLocator(
        document_id=cast(str, locator["document_id"]),
        locator_kind="page",
        locator_start=cast(int, locator["locator_start"]),
        locator_end=cast(int, locator["locator_end"]),
    )


def _hard_negative_failure_score(
    ranked: tuple[tuple[float, int], ...]
) -> float | None:
    first_direct = next((index for index, (_, grade) in enumerate(ranked) if grade == 2), None)
    failures = [
        score
        for index, (score, grade) in enumerate(ranked)
        if grade == 0 and (first_direct is None or index < first_direct)
    ]
    return max(failures, default=None)


def _hard_negative_failure(ranked: tuple[tuple[float, int], ...]) -> bool:
    direct = next((index for index, (_, grade) in enumerate(ranked) if grade == 2), None)
    distractor = next((index for index, (_, grade) in enumerate(ranked) if grade == 0), None)
    return distractor is not None and (direct is None or distractor < direct)


def normalize_current_runtime_semantics(
    payload: dict[str, Any], chinese: ChineseRetrievalProtocol
) -> dict[str, Any]:
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise DenseArtifactValidationError
    runtime_results = cast(list[object], raw_results)
    expected = list(chinese.queries)
    if len(runtime_results) != len(expected):
        raise DenseArtifactValidationError
    results: list[dict[str, Any]] = []
    for raw, query in zip(runtime_results, expected, strict=True):
        item = _object(raw)
        locators = item.get("retrieved_locators")
        direct_ranks = item.get("direct_ranks")
        hard_failure = item.get("hard_negative_failure")
        if (
            item.get("query_id") != query.query_id
            or item.get("split") != query.split
            or item.get("category") != query.category
            or not isinstance(locators, list)
            or not isinstance(direct_ranks, list)
            or type(hard_failure) is not bool
        ):
            raise DenseArtifactValidationError
        results.append(
            {
                "query_id": query.query_id,
                "split": query.split,
                "category": query.category,
                "retrieved_locators": locators,
                "direct_ranks": direct_ranks,
                "hard_negative_failure": hard_failure,
            }
        )
    return {"results": results}


def _compatibility(root: Path, corpus: DenseCorpusLock) -> dict[str, Any]:
    path = root / _COMPATIBILITY_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DenseArtifactValidationError
    report = cast(dict[str, object], payload)
    validate_dense_compatibility_report(report, corpus)
    model = _object(report.get("model"))
    projection = _object(report.get("projection"))
    exact = _object(projection.get("exact_reference"))
    identity = _object(exact.get("identity"))
    resources = _object(report.get("resources"))
    return {
        **_file_identity(root, _COMPATIBILITY_PATH),
        "schema_version": report.get("schema_version"),
        "compatibility_status": report.get("compatibility_status"),
        "model_fingerprint": model.get("snapshot_fingerprint"),
        "selected_adapter": projection.get("selected_adapter"),
        "reference_vector_digest": identity.get("vector_digest"),
        "resource_status": resources.get("passed"),
        "compatibility_stress_peak_rss_bytes": resources.get(
            "compatibility_stress_peak_rss_bytes"
        ),
        "single_query_peak_rss_bytes": _object(
            resources.get("single_query_smoke")
        ).get("peak_rss_bytes"),
    }


def dense_source_identity(root: Path) -> dict[str, Any]:
    files = [
        _file_identity(root, path)
        for path in _SOURCE_PATHS
        if (root / path).is_file()
    ]
    return {"sha256": _digest(files), "files": files}


def _file_identity(root: Path, relative_path: str) -> dict[str, Any]:
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise DenseArtifactValidationError
    data = path.read_bytes()
    return {
        "path": relative_path,
        "bytes": len(data),
        "sha256": sha256(data).hexdigest(),
    }


def _comparison_identity() -> DenseComparisonIdentity:
    return DenseComparisonIdentity(
        candidate_id=CANDIDATE_ID,
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
        adapter_id=EXACT_COSINE_ADAPTER_ID,
    )


def _unreachable_holdout() -> DenseHoldoutEvidence:
    raise DenseArtifactValidationError


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DenseArtifactValidationError
    return cast(dict[str, Any], value)


def _sha256(value: object) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise DenseArtifactValidationError
    return value


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _json_normalized(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )


if __name__ == "__main__":
    raise SystemExit(main())
