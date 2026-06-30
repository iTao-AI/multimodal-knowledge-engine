"""E3-D hybrid RRF workflow and arm binding."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast

from mke.evaluation.chinese_protocol import (
    ChineseQueryCategory,
    ChineseSplit,
    GradedQrel,
    load_chinese_retrieval_protocol,
)
from mke.evaluation.dense_artifact import (
    DenseArtifactValidationError,
    validate_dense_comparison_artifact,
)
from mke.evaluation.graded_metrics import (
    GradedQueryMetricInput,
    calculate_graded_metrics,
)
from mke.evaluation.hybrid_rrf_protocol import load_hybrid_rrf_protocol_lock
from mke.evaluation.manifest import StableLocator
from mke.evaluation.rrf_fusion import (
    ArmRankedResult,
    FusedRrfResult,
    RrfCandidateConfig,
    fuse_ranked_results,
)


class HybridRrfWorkflowError(ValueError):
    """Raised when hybrid RRF workflow inputs or state are invalid."""


@dataclass(frozen=True)
class HybridRrfState:
    candidate_status: str
    e3d_status: str
    runtime_promotion_status: str
    selected_threshold: float


@dataclass(frozen=True)
class HybridRrfQueryInput:
    split: ChineseSplit
    query_id: str
    category: ChineseQueryCategory
    lexical: tuple[ArmRankedResult, ...]
    dense: tuple[ArmRankedResult, ...]
    qrels: tuple[GradedQrel, ...]
    ask_status: Literal[
        "evidence_found",
        "insufficient_evidence",
        "invalid_question",
    ]
    compiled_query_empty: bool
    ascii_token_count: int


@dataclass(frozen=True)
class HybridRrfPartitionInput:
    split: ChineseSplit
    queries: tuple[HybridRrfQueryInput, ...]


@dataclass(frozen=True)
class HybridRrfInputs:
    development: HybridRrfPartitionInput
    holdout: HybridRrfPartitionInput
    state: HybridRrfState
    dense_artifact_sha256: str
    current_runtime_semantic_digest: str


def run_hybrid_rrf_development(
    *,
    protocol_path: Path,
    dense_artifact_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    inputs = load_hybrid_rrf_inputs(
        dense_artifact_path=dense_artifact_path,
        protocol_path=protocol_path,
        repository_root=repository_root,
    )
    config = RrfCandidateConfig.default()
    fused_by_query = {
        query.query_id: fuse_ranked_results(
            query_id=query.query_id,
            lexical=query.lexical,
            dense=query.dense,
            config=config,
        )
        for query in inputs.development.queries
    }
    metrics = {
        "fused": _metrics_for(inputs.development.queries, fused_by_query),
        "lexical": _metrics_for_arm(inputs.development.queries, arm="lexical"),
        "dense": _metrics_for_arm(inputs.development.queries, arm="dense"),
    }
    diagnostics = _diagnostics(inputs.development.queries, fused_by_query)
    status = _development_status(metrics, diagnostics)
    return {
        "schema_version": "mke.hybrid_rrf_development.v1",
        "candidate": {
            "candidate_id": config.candidate_id,
            "candidate_revision": config.candidate_revision,
        },
        "dense_artifact_sha256": inputs.dense_artifact_sha256,
        "protocol_sha256": _file_sha256(protocol_path),
        "current_runtime_semantic_digest": inputs.current_runtime_semantic_digest,
        "development_status": status,
        "holdout_status": "not_observed",
        "runtime_promotion_status": "not_evaluated",
        "metrics": metrics,
        "diagnostics": diagnostics,
        "results": [
            {
                "query_id": query.query_id,
                "split": query.split,
                "category": query.category,
                "fused_results": [
                    _fused_result_payload(row)
                    for row in fused_by_query[query.query_id]
                ],
            }
            for query in inputs.development.queries
        ],
    }


def record_hybrid_rrf_development_freeze(
    *,
    report: dict[str, object],
    target_path: Path,
) -> dict[str, object]:
    freeze = build_hybrid_rrf_development_freeze(report=report)
    _write_json_exclusive(target_path, freeze, subject="development freeze")
    return freeze


def build_hybrid_rrf_development_freeze(
    *,
    report: dict[str, object],
) -> dict[str, object]:
    return _json_normalized(
        {
            "schema_version": "mke.hybrid_rrf_development_freeze.v1",
            "candidate": report["candidate"],
            "development_status": report["development_status"],
            "holdout_status": "not_observed",
            "runtime_promotion_status": "not_evaluated",
            "protocol_sha256": report["protocol_sha256"],
            "dense_artifact_sha256": report["dense_artifact_sha256"],
            "current_runtime_semantic_digest": report[
                "current_runtime_semantic_digest"
            ],
            "metrics": report["metrics"],
            "diagnostics": report["diagnostics"],
        }
    )


def run_hybrid_rrf_holdout(
    *,
    protocol_path: Path,
    dense_artifact_path: Path,
    development_freeze_path: Path,
    record_path: Path,
    holdout_receipt_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    if holdout_receipt_path.exists():
        raise HybridRrfWorkflowError("holdout receipt already exists")
    freeze = _load_freeze(development_freeze_path)
    if freeze.get("development_status") == "valid_negative":
        raise HybridRrfWorkflowError("valid_negative development blocks holdout")
    if freeze.get("development_status") != "passed":
        raise HybridRrfWorkflowError("development freeze is invalid")
    _validate_freeze_identity(
        freeze,
        protocol_path=protocol_path,
        dense_artifact_path=dense_artifact_path,
    )
    inputs = load_hybrid_rrf_inputs(
        dense_artifact_path=dense_artifact_path,
        protocol_path=protocol_path,
        repository_root=repository_root,
    )
    config = RrfCandidateConfig.default()
    fused_by_query = {
        query.query_id: fuse_ranked_results(
            query_id=query.query_id,
            lexical=query.lexical,
            dense=query.dense,
            config=config,
        )
        for query in inputs.holdout.queries
    }
    metrics = {
        "fused": _metrics_for(inputs.holdout.queries, fused_by_query),
        "lexical": _metrics_for_arm(inputs.holdout.queries, arm="lexical"),
        "dense": _metrics_for_arm(inputs.holdout.queries, arm="dense"),
    }
    diagnostics = _diagnostics(inputs.holdout.queries, fused_by_query)
    receipt: dict[str, object] = {
        "schema_version": "mke.hybrid_rrf_holdout_receipt.v1",
        "candidate": freeze["candidate"],
        "protocol_sha256": freeze["protocol_sha256"],
        "dense_artifact_sha256": freeze["dense_artifact_sha256"],
    }
    _write_json_exclusive(holdout_receipt_path, receipt, subject="holdout receipt")
    artifact = _json_normalized(
        {
            "schema_version": "mke.hybrid_rrf_comparison_artifact.v1",
            "candidate": freeze["candidate"],
            "candidate_status": "completed",
            "development_status": "passed",
            "holdout_status": "observed",
            "runtime_promotion_status": "not_evaluated",
            "e3e_status": _followup_status(diagnostics),
            "segmentation_status": _segmentation_status(diagnostics),
            "development": freeze,
            "holdout": {
                "metrics": metrics,
                "diagnostics": diagnostics,
                "results": [
                    {
                        "query_id": query.query_id,
                        "split": query.split,
                        "category": query.category,
                        "fused_results": [
                            _fused_result_payload(row)
                            for row in fused_by_query[query.query_id]
                        ],
                    }
                    for query in inputs.holdout.queries
                ],
            },
            "state": {
                "development_freeze_sha256": _file_sha256(
                    development_freeze_path
                ),
                "holdout_receipt_sha256": _file_sha256(holdout_receipt_path),
            },
        }
    )
    _write_json_exclusive(record_path, artifact, subject="comparison artifact")
    return artifact


def load_hybrid_rrf_inputs(
    *,
    dense_artifact_path: Path,
    protocol_path: Path,
    repository_root: Path,
) -> HybridRrfInputs:
    root = repository_root.resolve()
    protocol = load_hybrid_rrf_protocol_lock(protocol_path, repository_root=root)
    dense_artifact = _load_dense_artifact(dense_artifact_path)
    state = _state(dense_artifact)
    chinese_path = _input_path(protocol, "chinese_protocol", root)
    chinese = load_chinese_retrieval_protocol(chinese_path)
    inventory = _locator_inventory(dense_artifact)
    runtime_results = _runtime_results(dense_artifact)
    dense_by_split = {
        "development": _dense_observations(
            dense_artifact,
            partition="development",
            threshold=state.selected_threshold,
        ),
        "holdout": _dense_observations(
            dense_artifact,
            partition="holdout",
            threshold=state.selected_threshold,
        ),
    }

    partitions: dict[ChineseSplit, HybridRrfPartitionInput] = {}
    for split in ("development", "holdout"):
        queries: list[HybridRrfQueryInput] = []
        runtime_by_id = {
            _string(item.get("query_id"), "query_id"): item
            for item in runtime_results
            if item.get("split") == split
        }
        dense_by_id = {
            _string(item.get("query_id"), "query_id"): item
            for item in dense_by_split[split]
        }
        for query in (item for item in chinese.queries if item.split == split):
            runtime = runtime_by_id.get(query.query_id)
            dense = dense_by_id.get(query.query_id)
            if runtime is None or dense is None:
                raise HybridRrfWorkflowError("query observation is missing")
            category = _string(runtime.get("category"), "category")
            if category != query.category:
                raise HybridRrfWorkflowError("query category is invalid")
            queries.append(
                HybridRrfQueryInput(
                    split=split,
                    query_id=query.query_id,
                    category=query.category,
                    lexical=_lexical_rows(runtime, inventory),
                    dense=_dense_rows(dense, threshold=state.selected_threshold),
                    qrels=query.qrels,
                    ask_status=_ask_status(query.category),
                    compiled_query_empty=False,
                    ascii_token_count=0,
                )
            )
        partitions[split] = HybridRrfPartitionInput(
            split=split,
            queries=tuple(queries),
        )
    _validate_dense_artifact(
        dense_artifact,
        dense_artifact_path=dense_artifact_path,
        protocol_path=root
        / "tests/fixtures/retrieval-dense-v1/protocol-lock.json",
        repository_root=root,
    )
    return HybridRrfInputs(
        development=partitions["development"],
        holdout=partitions["holdout"],
        state=state,
        dense_artifact_sha256=sha256(dense_artifact_path.read_bytes()).hexdigest(),
        current_runtime_semantic_digest=_string(
            cast(dict[str, Any], dense_artifact["current_runtime"]).get(
                "semantic_digest"
            ),
            "current runtime semantic digest",
        ),
    )


def _metrics_for(
    queries: tuple[HybridRrfQueryInput, ...],
    fused_by_query: dict[str, tuple[FusedRrfResult, ...]],
) -> dict[str, Any]:
    return _metric_payload(
        tuple(
            GradedQueryMetricInput(
                query_id=query.query_id,
                category=query.category,
                qrels=query.qrels,
                retrieved=tuple(
                    _stable_locator(row)
                    for row in fused_by_query[query.query_id]
                ),
                ask_status=query.ask_status,
                compiled_query_empty=query.compiled_query_empty,
                ascii_token_count=query.ascii_token_count,
            )
            for query in queries
        )
    )


def _metrics_for_arm(
    queries: tuple[HybridRrfQueryInput, ...],
    *,
    arm: Literal["lexical", "dense"],
) -> dict[str, Any]:
    return _metric_payload(
        tuple(
            GradedQueryMetricInput(
                query_id=query.query_id,
                category=query.category,
                qrels=query.qrels,
                retrieved=tuple(
                    _stable_locator(row)
                    for row in (query.lexical if arm == "lexical" else query.dense)
                ),
                ask_status=query.ask_status,
                compiled_query_empty=query.compiled_query_empty,
                ascii_token_count=query.ascii_token_count,
            )
            for query in queries
        )
    )


def _metric_payload(inputs: tuple[GradedQueryMetricInput, ...]) -> dict[str, Any]:
    return _json_normalized(asdict(calculate_graded_metrics(inputs)))


def _diagnostics(
    queries: tuple[HybridRrfQueryInput, ...],
    fused_by_query: dict[str, tuple[FusedRrfResult, ...]],
) -> dict[str, object]:
    union_grade2 = 0
    fused_lost = 0
    lexical_only = 0
    dense_only = 0
    both = 0
    neither = 0
    per_category: dict[str, dict[str, int]] = {}
    for query in queries:
        category = per_category.setdefault(
            query.category,
            {
                "query_count": 0,
                "union_grade2_coverage_at_10_count": 0,
                "fused_lost_union_grade2_count": 0,
            },
        )
        category["query_count"] += 1
        if query.category == "unanswerable":
            continue
        grade2 = {qrel.locator for qrel in query.qrels if qrel.grade == 2}
        lexical_hit = bool(grade2 & {_stable_locator(row) for row in query.lexical[:10]})
        dense_hit = bool(grade2 & {_stable_locator(row) for row in query.dense[:10]})
        fused_hit = bool(
            grade2
            & {
                _stable_locator(row)
                for row in fused_by_query[query.query_id][:5]
            }
        )
        union_hit = lexical_hit or dense_hit
        if union_hit:
            union_grade2 += 1
            category["union_grade2_coverage_at_10_count"] += 1
        if union_hit and not fused_hit:
            fused_lost += 1
            category["fused_lost_union_grade2_count"] += 1
        if lexical_hit and dense_hit:
            both += 1
        elif lexical_hit:
            lexical_only += 1
        elif dense_hit:
            dense_only += 1
        else:
            neither += 1
    return {
        "query_count": len(queries),
        "union_grade2_coverage_at_10": union_grade2,
        "fused_lost_union_grade2_count": fused_lost,
        "ranking_headroom_count": fused_lost,
        "lexical_only_recovery_count": lexical_only,
        "dense_only_recovery_count": dense_only,
        "both_arm_recovery_count": both,
        "neither_arm_miss_count": neither,
        "per_category_delta": per_category,
    }


def _development_status(
    metrics: dict[str, dict[str, Any]],
    diagnostics: dict[str, object],
) -> Literal["passed", "valid_negative"]:
    fused = metrics["fused"]
    lexical = metrics["lexical"]
    dense = metrics["dense"]
    quality_gates = (
        _metric_value(fused, "recall_at_5") >= _metric_value(lexical, "recall_at_5")
        and _metric_value(fused, "recall_at_5") >= _metric_value(dense, "recall_at_5")
        and _metric_value(fused, "ndcg_at_10") >= _metric_value(lexical, "ndcg_at_10")
        and _metric_value(fused, "ndcg_at_10") >= _metric_value(dense, "ndcg_at_10")
        and _metric_value(fused, "unanswerable_no_hit_rate")
        >= _metric_value(lexical, "unanswerable_no_hit_rate")
        and _metric_value(fused, "hard_negative_failure_rate")
        <= _metric_value(lexical, "hard_negative_failure_rate")
    )
    strict_improvement = (
        _metric_value(fused, "recall_at_5")
        > max(
            _metric_value(lexical, "recall_at_5"),
            _metric_value(dense, "recall_at_5"),
        )
        or _metric_value(fused, "ndcg_at_10")
        > max(
            _metric_value(lexical, "ndcg_at_10"),
            _metric_value(dense, "ndcg_at_10"),
        )
        or _metric_value(fused, "mrr_at_5")
        > max(
            _metric_value(lexical, "mrr_at_5"),
            _metric_value(dense, "mrr_at_5"),
        )
        or cast(int, diagnostics["dense_only_recovery_count"]) > 0
    )
    return "passed" if quality_gates and strict_improvement else "valid_negative"


def _metric_value(payload: dict[str, Any], name: str) -> float:
    value = _object(payload.get(name), name).get("value")
    return _float(value, "metric value")


def _fused_result_payload(row: FusedRrfResult) -> dict[str, object]:
    return {
        "rank": row.rank,
        "stable_locator_id": row.stable_locator_id,
        "document_id": row.document_id,
        "locator_kind": row.locator_kind,
        "locator_start": row.locator_start,
        "locator_end": row.locator_end,
        "source_text_digest": row.source_text_digest,
        "portable_score": row.portable_score,
        "arms": list(row.arms),
        "lexical_rank": row.lexical_rank,
        "dense_rank": row.dense_rank,
        "best_individual_rank": row.best_individual_rank,
    }


def _stable_locator(row: ArmRankedResult | FusedRrfResult) -> StableLocator:
    return StableLocator(
        document_id=row.document_id,
        locator_kind=cast(Literal["page", "timestamp_ms"], row.locator_kind),
        locator_start=row.locator_start,
        locator_end=row.locator_end,
    )


def _json_normalized(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(value, ensure_ascii=False)))


def _load_freeze(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise HybridRrfWorkflowError("development freeze is missing") from error
    except (OSError, json.JSONDecodeError) as error:
        raise HybridRrfWorkflowError("development freeze is invalid") from error
    if not isinstance(payload, dict):
        raise HybridRrfWorkflowError("development freeze is invalid")
    return cast(dict[str, Any], payload)


def _validate_freeze_identity(
    freeze: dict[str, Any],
    *,
    protocol_path: Path,
    dense_artifact_path: Path,
) -> None:
    if (
        freeze.get("protocol_sha256") != _file_sha256(protocol_path)
        or freeze.get("dense_artifact_sha256") != _file_sha256(dense_artifact_path)
    ):
        raise HybridRrfWorkflowError("freeze identity mismatch")


def _write_json_exclusive(
    path: Path,
    payload: dict[str, object],
    *,
    subject: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            handle.write("\n")
    except FileExistsError as error:
        raise HybridRrfWorkflowError(f"{subject} already exists") from error
    except OSError as error:
        raise HybridRrfWorkflowError(f"{subject} is not writable") from error


def _followup_status(diagnostics: dict[str, object]) -> str:
    if cast(int, diagnostics["ranking_headroom_count"]) > 0:
        return "eligible"
    return "not_evaluated"


def _segmentation_status(diagnostics: dict[str, object]) -> str:
    if cast(int, diagnostics["neither_arm_miss_count"]) > 0:
        return "eligible"
    return "not_evaluated"


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_dense_artifact(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HybridRrfWorkflowError("dense artifact is invalid") from error
    if not isinstance(payload, dict):
        raise HybridRrfWorkflowError("dense artifact is invalid")
    return cast(dict[str, Any], payload)


def _state(artifact: dict[str, Any]) -> HybridRrfState:
    comparison = _object(artifact.get("comparison"), "comparison")
    threshold_report = _object(artifact.get("threshold_report"), "threshold report")
    development = _object(comparison.get("development"), "development comparison")
    selected = _object(threshold_report.get("selected"), "selected threshold")
    if comparison.get("e3d_status") != "eligible":
        raise HybridRrfWorkflowError("e3d_status is not eligible")
    if comparison.get("runtime_promotion_status") != "not_evaluated":
        raise HybridRrfWorkflowError("runtime_promotion_status is invalid")
    if comparison.get("candidate_status") != "completed":
        raise HybridRrfWorkflowError("candidate_status is invalid")
    threshold = _float(threshold_report.get("selected_threshold"), "threshold")
    if (
        development.get("selected_threshold") != threshold
        or selected.get("threshold") != threshold
    ):
        raise HybridRrfWorkflowError("selected threshold mismatch")
    return HybridRrfState(
        candidate_status="completed",
        e3d_status="eligible",
        runtime_promotion_status="not_evaluated",
        selected_threshold=threshold,
    )


def _validate_dense_artifact(
    artifact: dict[str, Any],
    *,
    dense_artifact_path: Path,
    protocol_path: Path,
    repository_root: Path,
) -> None:
    try:
        validate_dense_comparison_artifact(
            artifact,
            protocol_path=protocol_path,
            repository_root=repository_root,
        )
    except DenseArtifactValidationError as error:
        raise HybridRrfWorkflowError("dense artifact is invalid") from error
    except Exception as error:
        raise HybridRrfWorkflowError("dense artifact is invalid") from error
    if not dense_artifact_path.exists():
        raise HybridRrfWorkflowError("dense artifact is invalid")


def _input_path(
    protocol: dict[str, object],
    name: str,
    root: Path,
) -> Path:
    inputs = _object(protocol.get("inputs"), "protocol inputs")
    record = _object(inputs.get(name), f"{name} input")
    relative_path = _string(record.get("path"), "input path")
    return root / relative_path


def _locator_inventory(
    artifact: dict[str, Any],
) -> dict[tuple[str, str, int, int], tuple[str, str]]:
    inventory: dict[tuple[str, str, int, int], tuple[str, str]] = {}
    for partition in ("development_candidate", "holdout_candidate"):
        candidate = _object(artifact.get(partition), partition)
        observations = _list(candidate.get("observations"), "dense observations")
        for observation in observations:
            for result in _list(
                _object(observation, "dense observation").get("results"),
                "dense results",
            ):
                row = _object(result, "dense result")
                locator = _object(row.get("locator"), "dense locator")
                key = _locator_key(locator)
                stable_locator_id = _string(
                    row.get("stable_locator_id"), "stable locator id"
                )
                digest = stable_locator_id.rsplit("|", 1)[-1]
                value = (stable_locator_id, digest)
                existing = inventory.get(key)
                if existing is not None and existing != value:
                    raise HybridRrfWorkflowError(
                        "duplicate locator inventory is invalid"
                    )
                inventory[key] = value
    return inventory


def _runtime_results(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    current_runtime = _object(artifact.get("current_runtime"), "current runtime")
    semantics = _object(current_runtime.get("semantics"), "current runtime semantics")
    return [
        _object(item, "runtime result")
        for item in _list(semantics.get("results"), "runtime results")
    ]


def _dense_observations(
    artifact: dict[str, Any],
    *,
    partition: ChineseSplit,
    threshold: float,
) -> list[dict[str, Any]]:
    if threshold <= 0:
        raise HybridRrfWorkflowError("selected threshold is invalid")
    candidate = _object(artifact.get(f"{partition}_candidate"), partition)
    if candidate.get("partition") != partition:
        raise HybridRrfWorkflowError("dense partition is invalid")
    return [
        _object(item, "dense observation")
        for item in _list(candidate.get("observations"), "dense observations")
    ]


def _lexical_rows(
    observation: dict[str, Any],
    inventory: dict[tuple[str, str, int, int], tuple[str, str]],
) -> tuple[ArmRankedResult, ...]:
    query_id = _string(observation.get("query_id"), "query_id")
    _string(observation.get("split"), "split")
    _string(observation.get("category"), "category")
    raw_locators = observation.get("retrieved_locators")
    if not isinstance(raw_locators, list):
        raise HybridRrfWorkflowError("retrieved_locators is invalid")
    locator_values = cast(list[object], raw_locators)
    seen: set[tuple[str, str]] = set()
    rows: list[ArmRankedResult] = []
    for rank, raw in enumerate(locator_values, start=1):
        locator = _object(raw, "lexical locator")
        key = _locator_key(locator)
        bound = inventory.get(key)
        if bound is None:
            raise HybridRrfWorkflowError("lexical locator cannot be rebound")
        stable_locator_id, digest = bound
        dedupe_key = (stable_locator_id, digest)
        if dedupe_key in seen:
            raise HybridRrfWorkflowError("duplicate lexical locator")
        seen.add(dedupe_key)
        rows.append(
            ArmRankedResult(
                arm_id="lexical",
                stable_locator_id=stable_locator_id,
                document_id=key[0],
                locator_kind=key[1],
                locator_start=key[2],
                locator_end=key[3],
                source_text_digest="sha256:" + digest,
                rank=rank,
            )
        )
    if query_id == "":
        raise HybridRrfWorkflowError("query_id is invalid")
    return tuple(rows)


def _dense_rows(
    observation: dict[str, Any],
    *,
    threshold: float,
) -> tuple[ArmRankedResult, ...]:
    observation_threshold = _float(observation.get("threshold"), "dense threshold")
    if observation_threshold != 0.0:
        raise HybridRrfWorkflowError("dense threshold is invalid")
    seen: set[str] = set()
    rows: list[ArmRankedResult] = []
    for expected_index, raw in enumerate(
        _list(observation.get("results"), "dense results"),
        start=1,
    ):
        result = _object(raw, "dense result")
        rank = _int(result.get("rank"), "dense rank")
        if rank != expected_index:
            raise HybridRrfWorkflowError("dense rank order is invalid")
        stable_locator_id = _string(result.get("stable_locator_id"), "stable locator id")
        if stable_locator_id in seen:
            raise HybridRrfWorkflowError("duplicate dense locator")
        seen.add(stable_locator_id)
        if _float(result.get("portable_score"), "dense score") < threshold:
            continue
        locator = _object(result.get("locator"), "dense locator")
        key = _locator_key(locator)
        digest = stable_locator_id.rsplit("|", 1)[-1]
        rows.append(
            ArmRankedResult(
                arm_id="dense",
                stable_locator_id=stable_locator_id,
                document_id=key[0],
                locator_kind=key[1],
                locator_start=key[2],
                locator_end=key[3],
                source_text_digest="sha256:" + digest,
                rank=rank,
            )
        )
    return tuple(rows)


def _ask_status(
    category: ChineseQueryCategory,
) -> Literal["evidence_found", "insufficient_evidence", "invalid_question"]:
    if category == "unanswerable":
        return "insufficient_evidence"
    return "evidence_found"


def _locator_key(locator: dict[str, object]) -> tuple[str, str, int, int]:
    document_id = _string(locator.get("document_id"), "document_id")
    locator_kind = _string(locator.get("locator_kind"), "locator_kind")
    locator_start = _int(locator.get("locator_start"), "locator_start")
    locator_end = _int(locator.get("locator_end"), "locator_end")
    if locator_kind != "page" or locator_start <= 0 or locator_end < locator_start:
        raise HybridRrfWorkflowError("locator is invalid")
    return (document_id, locator_kind, locator_start, locator_end)


def _object(value: object, subject: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HybridRrfWorkflowError(f"{subject} is invalid")
    return cast(dict[str, Any], value)


def _list(value: object, subject: str) -> list[object]:
    if not isinstance(value, list):
        raise HybridRrfWorkflowError(f"{subject} is invalid")
    return cast(list[object], value)


def _string(value: object, subject: str) -> str:
    if type(value) is not str or not value:
        raise HybridRrfWorkflowError(f"{subject} is invalid")
    return value


def _int(value: object, subject: str) -> int:
    if type(value) is not int or value <= 0:
        raise HybridRrfWorkflowError(f"{subject} is invalid")
    return value


def _float(value: object, subject: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise HybridRrfWorkflowError(f"{subject} is invalid")
    return float(value)
