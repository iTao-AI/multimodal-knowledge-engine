"""E3-E relevance gate development and holdout workflow."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast

import mke.evaluation.hybrid_rrf_workflow as hybrid_rrf_workflow
from mke.adapters.pdf.extractor import PyMuPDFPdfExtractor
from mke.evaluation.chinese_protocol import (
    ChineseEvaluationQuery,
    ChineseQueryCategory,
    ChineseRetrievalProtocol,
    ChineseSplit,
    GradedQrel,
    load_chinese_retrieval_protocol,
)
from mke.evaluation.graded_metrics import (
    GradedQueryMetricInput,
    calculate_graded_metrics,
)
from mke.evaluation.manifest import StableLocator
from mke.evaluation.relevance_gate_candidate import (
    PROFILE_CATALOG,
    GateDecision,
    RankedRelevanceRow,
    gate_feature_row,
    rerank_allowed_rows,
)
from mke.evaluation.relevance_gate_features import (
    EvidenceCandidateInput,
    RelevanceFeatures,
    build_relevance_features,
)
from mke.evaluation.relevance_gate_protocol import (
    CANDIDATE_ID,
    load_relevance_gate_protocol_lock,
)
from mke.evaluation.rrf_fusion import (
    FusedRrfResult,
    RrfCandidateConfig,
    fuse_ranked_results,
)


class RelevanceGateWorkflowError(ValueError):
    """Raised when relevance gate workflow state is invalid."""


@dataclass(frozen=True)
class RelevanceGateUnionRow:
    features: RelevanceFeatures
    original_rrf_rank: int
    original_portable_score: str


@dataclass(frozen=True)
class RelevanceGateQueryInput:
    split: ChineseSplit
    query_id: str
    category: ChineseQueryCategory
    qrels: tuple[GradedQrel, ...]
    ask_status: Literal[
        "evidence_found",
        "insufficient_evidence",
        "invalid_question",
    ]
    union_rows: tuple[RelevanceGateUnionRow, ...]


@dataclass(frozen=True)
class RelevanceGateInputs:
    split: ChineseSplit
    queries: tuple[RelevanceGateQueryInput, ...]
    dense_artifact_sha256: str
    rrf_artifact_sha256: str
    protocol_sha256: str


def load_relevance_gate_inputs(
    *,
    protocol_path: Path,
    repository_root: Path,
    split: ChineseSplit,
) -> RelevanceGateInputs:
    root = repository_root.resolve()
    protocol = load_relevance_gate_protocol_lock(protocol_path, repository_root=root)
    dense_artifact_path = _input_path(protocol, "dense_artifact", root)
    rrf_artifact_path = _input_path(protocol, "rrf_artifact", root)
    chinese_protocol_path = _input_path(protocol, "chinese_protocol", root)
    rrf_artifact = _load_json(rrf_artifact_path, "RRF artifact")
    chinese = load_chinese_retrieval_protocol(chinese_protocol_path)
    page_text = _page_text_inventory(chinese)
    if split == "holdout" and rrf_artifact.get("holdout") is None:
        partition = _build_holdout_rrf_partition(
            dense_artifact_path=dense_artifact_path,
            repository_root=root,
        )
    else:
        partition = _load_rrf_partition(rrf_artifact, split=split)
    by_query = {query.query_id: query for query in chinese.queries if query.split == split}
    queries: list[RelevanceGateQueryInput] = []
    for raw_result in partition:
        result = _object(raw_result, "RRF query result")
        query_id = _string(result.get("query_id"), "query_id")
        query = by_query.get(query_id)
        if query is None:
            raise RelevanceGateWorkflowError("query is not bound by Chinese protocol")
        category = _string(result.get("category"), "category")
        if category != query.category:
            raise RelevanceGateWorkflowError("query category is invalid")
        rows = tuple(
            _union_row(raw_row, query=query, page_text=page_text)
            for raw_row in _list(result.get("fused_results"), "fused results")
        )
        queries.append(
            RelevanceGateQueryInput(
                split=split,
                query_id=query_id,
                category=query.category,
                qrels=tuple(query.qrels),
                ask_status=_ask_status(query.category),
                union_rows=rows,
            )
        )
    if len(queries) != len(by_query):
        raise RelevanceGateWorkflowError("query observation is missing")
    return RelevanceGateInputs(
        split=split,
        queries=tuple(queries),
        dense_artifact_sha256=_file_sha256(dense_artifact_path),
        rrf_artifact_sha256=_file_sha256(rrf_artifact_path),
        protocol_sha256=_file_sha256(protocol_path),
    )


def run_relevance_gate_development(
    *,
    protocol_path: Path,
    candidate_id: str,
    repository_root: Path,
) -> dict[str, object]:
    if candidate_id != CANDIDATE_ID:
        raise RelevanceGateWorkflowError("candidate is invalid")
    inputs = load_relevance_gate_inputs(
        protocol_path=protocol_path,
        repository_root=repository_root,
        split="development",
    )
    profile_reports = {
        profile_id: _score_partition_for_profile(inputs, profile_id=profile_id)
        for profile_id in PROFILE_CATALOG
    }
    selected_profile = select_development_profile(profile_reports)
    if selected_profile is None:
        selected_report: dict[str, object] | None = None
        development_status = "valid_negative"
    else:
        selected_report = profile_reports[selected_profile]
        development_status = "passed"
    return _json_normalized(
        {
            "schema_version": "mke.relevance_gate_development.v1",
            "candidate": {
                "candidate_id": CANDIDATE_ID,
                "candidate_revision": 1,
            },
            "candidate_status": "completed",
            "development_status": development_status,
            "holdout_status": "not_observed",
            "runtime_promotion_status": "not_evaluated",
            "selected_profile": selected_profile,
            "protocol_sha256": inputs.protocol_sha256,
            "dense_artifact_sha256": inputs.dense_artifact_sha256,
            "rrf_artifact_sha256": inputs.rrf_artifact_sha256,
            "metrics": selected_report["metrics"] if selected_report else None,
            "diagnostics": selected_report["diagnostics"] if selected_report else None,
            "profile_reports": profile_reports,
        }
    )


def select_development_profile(
    profile_reports: dict[str, dict[str, object]],
) -> str | None:
    passed = {
        profile_id: report
        for profile_id, report in profile_reports.items()
        if report.get("passed_development_gates") is True
    }
    if not passed:
        return None

    def objective(item: tuple[str, dict[str, object]]) -> tuple[float, float, int, int]:
        profile_id, report = item
        metrics = _object(report.get("metrics"), "metrics")
        diagnostics = _object(report.get("diagnostics"), "diagnostics")
        recovery_count = _int(
            diagnostics.get("dense_only_recovery_retained_count"),
            "dense recovery",
            allow_zero=True,
        ) + _int(
            diagnostics.get("union_only_recovery_retained_count"),
            "union recovery",
            allow_zero=True,
        )
        return (
            _metric_value(metrics, "recall_at_5"),
            _metric_value(metrics, "ndcg_at_10"),
            int(recovery_count > 0),
            _strictness(profile_id),
        )

    return max(passed.items(), key=objective)[0]


def record_relevance_gate_development_freeze(
    *,
    report: dict[str, object],
    target_path: Path,
) -> dict[str, object]:
    freeze = build_relevance_gate_development_freeze(report=report)
    _write_json_exclusive(target_path, freeze, subject="development freeze")
    return freeze


def build_relevance_gate_development_freeze(
    *,
    report: dict[str, object],
) -> dict[str, object]:
    return _json_normalized(
        {
            "schema_version": "mke.relevance_gate_development_freeze.v1",
            "candidate": report["candidate"],
            "candidate_status": report["candidate_status"],
            "development_status": report["development_status"],
            "holdout_status": "not_observed",
            "runtime_promotion_status": "not_evaluated",
            "selected_profile": report["selected_profile"],
            "protocol_sha256": report["protocol_sha256"],
            "dense_artifact_sha256": report["dense_artifact_sha256"],
            "rrf_artifact_sha256": report["rrf_artifact_sha256"],
            "metrics": report["metrics"],
            "diagnostics": report["diagnostics"],
        }
    )


def run_relevance_gate_holdout(
    *,
    protocol_path: Path,
    candidate_id: str,
    development_freeze_path: Path,
    record_path: Path,
    holdout_receipt_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    if candidate_id != CANDIDATE_ID:
        raise RelevanceGateWorkflowError("candidate is invalid")
    if record_path.exists():
        raise RelevanceGateWorkflowError("comparison artifact already exists")
    if holdout_receipt_path.exists():
        raise RelevanceGateWorkflowError("holdout receipt already exists")
    freeze = _load_freeze(development_freeze_path)
    if freeze.get("development_status") != "passed":
        raise RelevanceGateWorkflowError("development freeze does not allow holdout")
    _validate_freeze_identity(
        freeze,
        protocol_path=protocol_path,
        repository_root=repository_root,
    )
    receipt = {
        "schema_version": "mke.relevance_gate_holdout_receipt.v1",
        "candidate": freeze["candidate"],
        "development_freeze_sha256": _file_sha256(development_freeze_path),
        "protocol_sha256": freeze["protocol_sha256"],
        "dense_artifact_sha256": freeze["dense_artifact_sha256"],
        "rrf_artifact_sha256": freeze["rrf_artifact_sha256"],
        "selected_profile": freeze["selected_profile"],
    }
    _write_json_exclusive(
        holdout_receipt_path,
        _json_normalized(receipt),
        subject="holdout receipt",
    )
    holdout = build_relevance_gate_holdout_report(
        protocol_path=protocol_path,
        selected_profile=_string(freeze.get("selected_profile"), "selected profile"),
        repository_root=repository_root,
    )
    artifact = build_relevance_gate_comparison_artifact(
        freeze=freeze,
        holdout=holdout,
        development_freeze_path=development_freeze_path,
        holdout_receipt_path=holdout_receipt_path,
        repository_root=repository_root,
    )
    _write_json_exclusive(record_path, artifact, subject="comparison artifact")
    return artifact


def build_relevance_gate_holdout_report(
    *,
    protocol_path: Path,
    selected_profile: str,
    repository_root: Path,
) -> dict[str, object]:
    inputs = load_relevance_gate_inputs(
        protocol_path=protocol_path,
        repository_root=repository_root,
        split="holdout",
    )
    report = _score_partition_for_profile(inputs, profile_id=selected_profile)
    gate_failures = _holdout_gate_failures(cast(dict[str, Any], report["metrics"]))
    report["holdout_gate_failures"] = gate_failures
    report["holdout_gate_status"] = "passed" if not gate_failures else "failed"
    return _json_normalized(report)


def build_relevance_gate_comparison_artifact(
    *,
    freeze: dict[str, Any],
    holdout: dict[str, object],
    development_freeze_path: Path,
    holdout_receipt_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    return _json_normalized(
        {
            "schema_version": "mke.relevance_gate_comparison_artifact.v1",
            "candidate": freeze["candidate"],
            "candidate_status": "completed",
            "development_status": freeze["development_status"],
            "holdout_status": "observed",
            "runtime_promotion_status": "not_evaluated",
            "e3f_runtime_status": "not_evaluated",
            "reranker_model_status": "eligible",
            "query_rewrite_status": "not_evaluated",
            "segmentation_status": _segmentation_status(holdout),
            "selected_profile": freeze["selected_profile"],
            "development": freeze,
            "holdout": holdout,
            "state": {
                "development_freeze_path": _public_path(
                    development_freeze_path,
                    repository_root=repository_root,
                ),
                "development_freeze_sha256": _file_sha256(development_freeze_path),
                "holdout_receipt_path": _public_path(
                    holdout_receipt_path,
                    repository_root=repository_root,
                ),
                "holdout_receipt_sha256": _file_sha256(holdout_receipt_path),
            },
        }
    )


def _score_partition_for_profile(
    inputs: RelevanceGateInputs,
    *,
    profile_id: str,
) -> dict[str, object]:
    ranked_by_query = {
        query.query_id: rerank_allowed_rows(
            tuple(row.features for row in query.union_rows),
            profile_id=profile_id,
        )
        for query in inputs.queries
    }
    metrics = _metric_payload(inputs.queries, ranked_by_query)
    diagnostics = _diagnostics(inputs.queries, ranked_by_query, profile_id=profile_id)
    gate_failures = _gate_failures(metrics, diagnostics)
    return _json_normalized(
        {
            "profile_id": profile_id,
            "passed_development_gates": not gate_failures,
            "gate_failures": gate_failures,
            "metrics": metrics,
            "diagnostics": diagnostics,
            "results": [
                {
                    "query_id": query.query_id,
                    "split": query.split,
                    "category": query.category,
                    "input_union_count": len(query.union_rows),
                    "allowed_results": [
                        _ranked_payload(rank, row)
                        for rank, row in enumerate(
                            ranked_by_query[query.query_id],
                            start=1,
                        )
                    ],
                    "feature_rows": [
                        row.features.to_json() for row in query.union_rows
                    ],
                }
                for query in inputs.queries
            ],
        }
    )


def _holdout_gate_failures(metrics: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if _metric_value(metrics, "unanswerable_no_hit_rate") < 0.5:
        failures.append("holdout_unanswerable_no_hit_below_current_runtime")
    if _metric_value(metrics, "hard_negative_failure_rate") > 0.0:
        failures.append("holdout_hard_negative_failure_above_current_runtime")
    return failures


def _metric_payload(
    queries: tuple[RelevanceGateQueryInput, ...],
    ranked_by_query: dict[str, tuple[RankedRelevanceRow, ...]],
) -> dict[str, Any]:
    metric_inputs = tuple(
        GradedQueryMetricInput(
            query_id=query.query_id,
            category=query.category,
            qrels=query.qrels,
            retrieved=tuple(
                _stable_locator(row.features)
                for row in ranked_by_query[query.query_id]
            ),
            ask_status=query.ask_status,
            compiled_query_empty=False,
            ascii_token_count=0,
        )
        for query in queries
    )
    return _json_normalized(asdict(calculate_graded_metrics(metric_inputs)))


def _diagnostics(
    queries: tuple[RelevanceGateQueryInput, ...],
    ranked_by_query: dict[str, tuple[RankedRelevanceRow, ...]],
    *,
    profile_id: str,
) -> dict[str, object]:
    input_union_count = 0
    allowed_count = 0
    rejected_by_reason: dict[str, int] = {}
    dropped_grade2_count = 0
    dense_only_recovery = 0
    lexical_only_recovery = 0
    union_only_recovery = 0
    empty_result_no_hit = 0
    recovered_false_positive = 0
    per_category: dict[str, dict[str, int]] = {}
    for query in queries:
        category = per_category.setdefault(
            query.category,
            {
                "query_count": 0,
                "input_union_count": 0,
                "allowed_count": 0,
                "empty_result_no_hit_count": 0,
            },
        )
        category["query_count"] += 1
        input_union_count += len(query.union_rows)
        category["input_union_count"] += len(query.union_rows)
        ranked = ranked_by_query[query.query_id]
        allowed_count += len(ranked)
        category["allowed_count"] += len(ranked)
        if not ranked:
            empty_result_no_hit += 1
            category["empty_result_no_hit_count"] += 1
        allowed_ids = {row.features.stable_locator_id for row in ranked}
        for row in query.union_rows:
            if row.features.stable_locator_id in allowed_ids:
                continue
            decision = gate_feature_row(row.features, profile_id=profile_id)
            reason = _rejection_reason(decision)
            rejected_by_reason[reason] = rejected_by_reason.get(reason, 0) + 1
        grade2_locator_identities = {
            _locator_identity_from_locator(qrel.locator)
            for qrel in query.qrels
            if qrel.grade == 2
        }
        union_grade2 = {
            row.features.stable_locator_id
            for row in query.union_rows
            if _locator_identity(row.features) in grade2_locator_identities
        }
        allowed_grade2_rows = tuple(
            row for row in ranked if row.features.stable_locator_id in union_grade2
        )
        if union_grade2 and not allowed_grade2_rows:
            dropped_grade2_count += 1
        if query.category == "unanswerable" and query.union_rows and not ranked:
            recovered_false_positive += 1
        if allowed_grade2_rows:
            if any(row.features.arm_contributions == ("dense",) for row in allowed_grade2_rows):
                dense_only_recovery += 1
            if any(row.features.arm_contributions == ("lexical",) for row in allowed_grade2_rows):
                lexical_only_recovery += 1
            if any(
                row.features.arm_contributions in {("dense",), ("lexical",)}
                for row in allowed_grade2_rows
            ):
                union_only_recovery += 1
    return {
        "input_union_count": input_union_count,
        "allowed_count": allowed_count,
        "rejected_count_by_reason": rejected_by_reason,
        "dropped_grade2_count": dropped_grade2_count,
        "recovered_from_rrf_false_positive_count": recovered_false_positive,
        "dense_only_recovery_retained_count": dense_only_recovery,
        "lexical_only_recovery_retained_count": lexical_only_recovery,
        "union_only_recovery_retained_count": union_only_recovery,
        "empty_result_no_hit_count": empty_result_no_hit,
        "per_category_delta": per_category,
    }


def _gate_failures(metrics: dict[str, Any], diagnostics: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if _metric_value(metrics, "unanswerable_no_hit_rate") < 0.5:
        failures.append("unanswerable_no_hit_below_current_runtime")
    if _metric_value(metrics, "hard_negative_failure_rate") > 0.2:
        failures.append("hard_negative_failure_above_rrf")
    if _metric_value(metrics, "recall_at_5") < 0.681818:
        failures.append("recall_at_5_below_current_runtime")
    if _metric_value(metrics, "ndcg_at_10") < 0.643390:
        failures.append("ndcg_at_10_below_current_runtime")
    if _metric_value(metrics, "mrr_at_5") < 0.636364:
        failures.append("mrr_at_5_below_current_runtime")
    if (
        _int(
            diagnostics.get("dense_only_recovery_retained_count"),
            "dense recovery",
            allow_zero=True,
        )
        + _int(
            diagnostics.get("union_only_recovery_retained_count"),
            "union recovery",
            allow_zero=True,
        )
        < 1
    ):
        failures.append("dense_or_union_recovery_missing")
    return failures


def _ranked_payload(rank: int, row: RankedRelevanceRow) -> dict[str, object]:
    return {
        "rank": rank,
        "stable_locator_id": row.features.stable_locator_id,
        "document_id": row.features.document_id,
        "locator_kind": row.features.locator_kind,
        "locator_start": row.features.locator_start,
        "locator_end": row.features.locator_end,
        "source_text_digest": "sha256:" + row.features.source_text_digest,
        "gate_decision": {
            "allowed": row.decision.allowed,
            "reason_code": row.decision.reason_code,
            "rerank_score": row.decision.rerank_score,
        },
        "features": row.features.to_json(),
    }


def _rejection_reason(decision: GateDecision) -> str:
    if decision.allowed:
        raise RelevanceGateWorkflowError("allowed row cannot be counted as rejected")
    return decision.reason_code


def _union_row(
    value: object,
    *,
    query: ChineseEvaluationQuery,
    page_text: dict[StableLocator, str],
) -> RelevanceGateUnionRow:
    row = _object(value, "RRF row")
    locator = StableLocator(
        document_id=_string(row.get("document_id"), "document_id"),
        locator_kind=cast(Literal["page", "timestamp_ms"], row.get("locator_kind")),
        locator_start=_int(row.get("locator_start"), "locator_start"),
        locator_end=_int(row.get("locator_end"), "locator_end"),
    )
    if locator.locator_kind != "page":
        raise RelevanceGateWorkflowError("locator kind is invalid")
    text = page_text.get(locator)
    if text is None:
        raise RelevanceGateWorkflowError("source text is missing")
    digest = sha256(text.encode("utf-8")).hexdigest()
    recorded_digest = _string(row.get("source_text_digest"), "source text digest")
    if recorded_digest != "sha256:" + digest:
        raise RelevanceGateWorkflowError("source text digest mismatch")
    features = build_relevance_features(
        EvidenceCandidateInput(
            query_id=query.query_id,
            query_text=query.text,
            stable_locator_id=_string(row.get("stable_locator_id"), "stable locator id"),
            document_id=locator.document_id,
            locator_kind=locator.locator_kind,
            locator_start=locator.locator_start,
            locator_end=locator.locator_end,
            evidence_text=text,
            arm_contributions=tuple(
                cast(list[Literal["lexical", "dense"]], _list(row.get("arms"), "arms"))
            ),
            lexical_rank=_optional_int(row.get("lexical_rank"), "lexical_rank"),
            dense_rank=_optional_int(row.get("dense_rank"), "dense_rank"),
            rrf_rank=_int(row.get("rank"), "RRF rank"),
        )
    )
    return RelevanceGateUnionRow(
        features=features,
        original_rrf_rank=_int(row.get("rank"), "RRF rank"),
        original_portable_score=_string(row.get("portable_score"), "portable score"),
    )


def _build_holdout_rrf_partition(
    *,
    dense_artifact_path: Path,
    repository_root: Path,
) -> list[object]:
    dense_artifact = hybrid_rrf_workflow._load_dense_artifact(  # pyright: ignore[reportPrivateUsage]
        dense_artifact_path
    )
    state = hybrid_rrf_workflow._state(  # pyright: ignore[reportPrivateUsage]
        dense_artifact
    )
    inventory = hybrid_rrf_workflow._locator_inventory(  # pyright: ignore[reportPrivateUsage]
        dense_artifact
    )
    runtime_results = hybrid_rrf_workflow._runtime_results(  # pyright: ignore[reportPrivateUsage]
        dense_artifact
    )
    dense_observations = hybrid_rrf_workflow._dense_observations(  # pyright: ignore[reportPrivateUsage]
        dense_artifact,
        partition="holdout",
        threshold=state.selected_threshold,
    )
    chinese = load_chinese_retrieval_protocol(
        repository_root / "tests/fixtures/retrieval-chinese-v1/protocol.json"
    )
    runtime_by_id = {
        item["query_id"]: item
        for item in runtime_results
        if item.get("split") == "holdout"
    }
    dense_by_id = {item["query_id"]: item for item in dense_observations}
    config = RrfCandidateConfig.default()
    results: list[object] = []
    for query in (item for item in chinese.queries if item.split == "holdout"):
        runtime = runtime_by_id.get(query.query_id)
        dense = dense_by_id.get(query.query_id)
        if runtime is None or dense is None:
            raise RelevanceGateWorkflowError("holdout query observation is missing")
        lexical_rows = hybrid_rrf_workflow._lexical_rows(  # pyright: ignore[reportPrivateUsage]
            runtime,
            inventory,
        )
        dense_rows = hybrid_rrf_workflow._dense_rows(  # pyright: ignore[reportPrivateUsage]
            dense,
            threshold=state.selected_threshold,
        )
        fused = fuse_ranked_results(
            query_id=query.query_id,
            lexical=lexical_rows,
            dense=dense_rows,
            config=config,
        )
        results.append(
            {
                "query_id": query.query_id,
                "split": "holdout",
                "category": query.category,
                "fused_results": [_fused_result_payload(row) for row in fused],
            }
        )
    return results


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


def _page_text_inventory(
    protocol: ChineseRetrievalProtocol,
) -> dict[StableLocator, str]:
    inventory: dict[StableLocator, str] = {}
    extractor = PyMuPDFPdfExtractor()
    try:
        for document in protocol.documents:
            extracted = extractor.extract(protocol.resolve(document.primary_file))
            for page in extracted.pages:
                inventory[
                    StableLocator(
                        document_id=document.document_id,
                        locator_kind="page",
                        locator_start=page.page_number,
                        locator_end=page.page_number,
                    )
                ] = page.text
    except Exception as error:
        raise RelevanceGateWorkflowError("source text inventory is invalid") from error
    return inventory


def _load_rrf_partition(
    artifact: dict[str, Any],
    *,
    split: ChineseSplit,
) -> list[object]:
    partition = _object(artifact.get(split), split)
    if partition.get(f"{split}_status") not in {None, "passed", "valid_negative"}:
        raise RelevanceGateWorkflowError(f"{split} status is invalid")
    return _list(partition.get("results"), f"{split} results")


def _load_freeze(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RelevanceGateWorkflowError("development freeze is missing") from error
    except (OSError, json.JSONDecodeError) as error:
        raise RelevanceGateWorkflowError("development freeze is invalid") from error
    if not isinstance(payload, dict):
        raise RelevanceGateWorkflowError("development freeze is invalid")
    return cast(dict[str, Any], payload)


def _validate_freeze_identity(
    freeze: dict[str, Any],
    *,
    protocol_path: Path,
    repository_root: Path,
) -> None:
    protocol = load_relevance_gate_protocol_lock(
        protocol_path,
        repository_root=repository_root,
    )
    if freeze.get("protocol_sha256") != _file_sha256(protocol_path):
        raise RelevanceGateWorkflowError("development freeze identity mismatch")
    for name, field in (
        ("dense_artifact", "dense_artifact_sha256"),
        ("rrf_artifact", "rrf_artifact_sha256"),
    ):
        if freeze.get(field) != _file_sha256(_input_path(protocol, name, repository_root)):
            raise RelevanceGateWorkflowError("development freeze identity mismatch")


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
        raise RelevanceGateWorkflowError(f"{subject} already exists") from error
    except OSError as error:
        raise RelevanceGateWorkflowError(f"{subject} is not writable") from error


def _input_path(
    protocol: dict[str, object],
    name: str,
    root: Path,
) -> Path:
    inputs = _object(protocol.get("inputs"), "protocol inputs")
    record = _object(inputs.get(name), f"{name} input")
    relative_path = _string(record.get("path"), "input path")
    return root / relative_path


def _ask_status(
    category: ChineseQueryCategory,
) -> Literal["evidence_found", "insufficient_evidence", "invalid_question"]:
    if category == "unanswerable":
        return "insufficient_evidence"
    return "evidence_found"


def _stable_locator(features: RelevanceFeatures) -> StableLocator:
    return StableLocator(
        document_id=features.document_id,
        locator_kind=cast(Literal["page", "timestamp_ms"], features.locator_kind),
        locator_start=features.locator_start,
        locator_end=features.locator_end,
    )


def _locator_identity(features: RelevanceFeatures) -> tuple[str, str, int, int]:
    return (
        features.document_id,
        features.locator_kind,
        features.locator_start,
        features.locator_end,
    )


def _locator_identity_from_locator(locator: StableLocator) -> tuple[str, str, int, int]:
    return (
        locator.document_id,
        locator.locator_kind,
        locator.locator_start,
        locator.locator_end,
    )


def _metric_value(payload: dict[str, Any], name: str) -> float:
    value = _object(payload.get(name), name).get("value")
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise RelevanceGateWorkflowError("metric value is invalid")
    return float(value)


def _strictness(profile_id: str) -> int:
    if profile_id == "lexical-floor":
        return 0
    if profile_id == "balanced-constraint":
        return 1
    if profile_id == "strict-constraint":
        return 2
    raise RelevanceGateWorkflowError("profile is invalid")


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _public_path(path: Path, *, repository_root: Path) -> str:
    resolved = path.resolve()
    root = repository_root.resolve()
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    return path.name


def _segmentation_status(holdout: dict[str, object]) -> str:
    diagnostics = _object(holdout.get("diagnostics"), "holdout diagnostics")
    if _int(
        diagnostics.get("dropped_grade2_count"),
        "dropped grade2 count",
        allow_zero=True,
    ):
        return "eligible"
    return "not_evaluated"


def _load_json(path: Path, subject: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RelevanceGateWorkflowError(f"{subject} is invalid") from error
    if not isinstance(payload, dict):
        raise RelevanceGateWorkflowError(f"{subject} is invalid")
    return cast(dict[str, Any], payload)


def _json_normalized(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(value, ensure_ascii=False)))


def _object(value: object, subject: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RelevanceGateWorkflowError(f"{subject} is invalid")
    return cast(dict[str, Any], value)


def _list(value: object, subject: str) -> list[object]:
    if not isinstance(value, list):
        raise RelevanceGateWorkflowError(f"{subject} is invalid")
    return cast(list[object], value)


def _string(value: object, subject: str) -> str:
    if type(value) is not str or not value:
        raise RelevanceGateWorkflowError(f"{subject} is invalid")
    return value


def _int(value: object, subject: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum:
        raise RelevanceGateWorkflowError(f"{subject} is invalid")
    return value


def _optional_int(value: object, subject: str) -> int | None:
    if value is None:
        return None
    return _int(value, subject)
