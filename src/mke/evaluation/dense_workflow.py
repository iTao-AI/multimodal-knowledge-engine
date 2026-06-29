"""Cache-only two-phase execution for the E3-C comparison CLI."""

from __future__ import annotations

import json
import os
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast

from mke.adapters.embedding import create_sentence_transformers_embedding
from mke.application import KnowledgeEngine
from mke.domain import RunState
from mke.embeddings.contracts import CANDIDATE_ID, CANDIDATE_REVISION
from mke.embeddings.readiness import resolve_embedding_cache
from mke.evaluation.chinese_protocol import (
    load_chinese_retrieval_protocol,
)
from mke.evaluation.dense_artifact import (
    build_dense_comparison_artifact,
    dense_source_identity,
    derive_dense_threshold_inputs,
    normalize_current_runtime_semantics,
    render_dense_comparison_artifact_json,
    validate_dense_comparison_artifact,
)
from mke.evaluation.dense_candidate import run_dense_candidate_partition
from mke.evaluation.dense_protocol import load_dense_protocol_lock
from mke.evaluation.dense_threshold import (
    select_dense_threshold,
    validate_threshold_report,
)

DensePhase = Literal["development", "holdout"]
_CHINESE_PROTOCOL = "tests/fixtures/retrieval-chinese-v1/protocol.json"
_COMPATIBILITY = "benchmarks/retrieval/qwen3-embedding-0.6b-compatibility.json"


class DenseWorkflowError(RuntimeError):
    """Dense evaluation could not produce trustworthy evidence."""


def run_dense_evaluation_phase(
    *,
    phase: DensePhase,
    protocol: Path,
    candidate: str,
    model_cache: Path,
    record_development_freeze: Path | None = None,
    development_freeze: Path | None = None,
    record: Path | None = None,
    record_holdout_receipt: Path | None = None,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    root = (repository_root or _discover_repository(protocol)).resolve()
    if candidate != CANDIDATE_ID:
        raise DenseWorkflowError("dense candidate is not allowlisted")
    cache = resolve_embedding_cache(model_cache, repository_root=root)
    if not cache.is_dir():
        raise DenseWorkflowError("embedding model cache is not ready")
    locked = load_dense_protocol_lock(protocol, repository_root=root)
    provider = create_sentence_transformers_embedding(cache_dir=cache)
    if phase == "development":
        if record_development_freeze is None:
            raise DenseWorkflowError("development freeze path is required")
        candidate_report = cast(
            dict[str, Any],
            run_dense_candidate_partition(
                locked,
                repository_root=root,
                partition="development",
                provider=provider,
                threshold=0.0,
            ),
        )
        runtime = _observe_current_runtime_partition(root, "development")
        chinese = load_chinese_retrieval_protocol(root / _CHINESE_PROTOCOL)
        threshold_report = select_dense_threshold(
            derive_dense_threshold_inputs(
                _canonical_runner_report(candidate_report),
                partition="development",
                chinese=chinese,
                runtime=runtime,
            )
        )
        freeze = _development_freeze_payload(
            root=root,
            protocol=protocol,
            candidate_report=candidate_report,
            runtime=runtime,
            threshold_report=threshold_report,
        )
        _write_exclusive_json(record_development_freeze, freeze)
        return {
            "phase": "development",
            "development_status": threshold_report["development_status"],
            "selected_threshold": threshold_report["selected_threshold"],
            "candidate_status": threshold_report["candidate_status"],
            "e3d_status": threshold_report["e3d_status"],
            "runtime_promotion_status": "not_evaluated",
            "development_freeze_sha256": _file_sha256(record_development_freeze),
            "threshold_report": threshold_report,
        }

    if development_freeze is None or record is None or record_holdout_receipt is None:
        raise DenseWorkflowError("holdout recording paths are required")
    if record.exists() or record_holdout_receipt.exists():
        raise DenseWorkflowError("holdout completion record already exists")
    freeze = _load_development_freeze(development_freeze, root=root, protocol=protocol)
    if freeze["threshold_report"]["development_status"] != "passed":
        raise DenseWorkflowError("development result is not eligible for holdout")
    holdout_report = cast(
        dict[str, Any],
        run_dense_candidate_partition(
            locked,
            repository_root=root,
            partition="holdout",
            provider=provider,
            threshold=0.0,
        ),
    )
    holdout_runtime = _observe_current_runtime_partition(root, "holdout")
    combined_runtime = _combine_runtime_semantics(
        cast(dict[str, Any], freeze["current_runtime"]),
        holdout_runtime,
        root=root,
    )
    receipt = {
        "schema_version": "mke.dense_holdout_receipt.v1",
        "development_freeze_sha256": _file_sha256(development_freeze),
        "holdout_result_sha256": _digest(
            {
                "candidate": _canonical_runner_report(holdout_report),
                "current_runtime": holdout_runtime,
            }
        ),
        "candidate_id": CANDIDATE_ID,
        "candidate_revision": CANDIDATE_REVISION,
        "projection": cast(dict[str, Any], holdout_report["projection"]),
        "execution": {
            "cache_only": True,
            "network": False,
            "holdout_observation_count": 1,
        },
    }
    _write_exclusive_json(record_holdout_receipt, receipt)
    artifact = build_dense_comparison_artifact(
        protocol_path=protocol,
        repository_root=root,
        development_candidate=cast(dict[str, Any], freeze["development_candidate"]),
        holdout_candidate=holdout_report,
        current_runtime_payload=combined_runtime,
        development_freeze_sha256=_file_sha256(development_freeze),
        holdout_receipt_sha256=_file_sha256(record_holdout_receipt),
    )
    _write_exclusive_text(record, render_dense_comparison_artifact_json(artifact))
    validate_dense_comparison_artifact(
        artifact,
        protocol_path=protocol,
        repository_root=root,
        current_runtime_loader=lambda: combined_runtime,
    )
    comparison = cast(dict[str, Any], artifact["comparison"])
    return {
        "phase": "holdout",
        "holdout_status": comparison["holdout_status"],
        "candidate_status": comparison["candidate_status"],
        "e3d_status": comparison["e3d_status"],
        "runtime_promotion_status": comparison["runtime_promotion_status"],
        "artifact_sha256": _file_sha256(record),
        "holdout_receipt_sha256": _file_sha256(record_holdout_receipt),
        "comparison": comparison,
    }


def _observe_current_runtime_partition(
    root: Path, partition: DensePhase
) -> dict[str, Any]:
    protocol = load_chinese_retrieval_protocol(root / _CHINESE_PROTOCOL)
    documents = tuple(item for item in protocol.documents if item.split == partition)
    queries = tuple(item for item in protocol.queries if item.split == partition)
    with tempfile.TemporaryDirectory(prefix=f"mke-dense-{partition}-runtime-") as temp:
        engine = KnowledgeEngine(
            Path(temp) / "runtime.sqlite",
            retrieval_strategy="cjk-active-scan-overlap-v1",
        )
        try:
            source_documents: dict[str, str] = {}
            for document in documents:
                result = engine.ingest_pdf(protocol.resolve(document.primary_file))
                if result.run_state is not RunState.PUBLISHED:
                    raise DenseWorkflowError("current runtime partition ingest failed")
                source_documents[engine.get_run(result.run_id).source_id] = document.document_id
            results: list[dict[str, Any]] = []
            for query in queries:
                retrieved = [
                    {
                        "document_id": source_documents[item.source_id],
                        "locator_kind": "page",
                        "locator_start": item.locator_start,
                        "locator_end": item.locator_end,
                    }
                    for item in engine.search(query.text, limit=10)
                ]
                grade_by_locator = {
                    (
                        item.locator.document_id,
                        item.locator.locator_start,
                    ): item.grade
                    for item in query.qrels
                }
                grades = [
                    grade_by_locator.get(
                        (
                            cast(str, item["document_id"]),
                            cast(int, item["locator_start"]),
                        )
                    )
                    for item in retrieved
                ]
                direct_ranks = [
                    rank
                    for rank, grade in enumerate(grades, start=1)
                    if grade == 2
                ]
                results.append(
                    {
                        "query_id": query.query_id,
                        "split": query.split,
                        "category": query.category,
                        "retrieved_locators": retrieved,
                        "direct_ranks": direct_ranks,
                        "hard_negative_failure": _hard_failure(grades),
                    }
                )
            return {"results": results}
        finally:
            engine.close()


def _hard_failure(grades: list[int | None]) -> bool:
    direct = next((index for index, grade in enumerate(grades) if grade == 2), None)
    distractor = next((index for index, grade in enumerate(grades) if grade == 0), None)
    return distractor is not None and (direct is None or distractor < direct)


def _development_freeze_payload(
    *,
    root: Path,
    protocol: Path,
    candidate_report: dict[str, Any],
    runtime: dict[str, Any],
    threshold_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "mke.dense_development_freeze.v1",
        "candidate": {
            "candidate_id": CANDIDATE_ID,
            "candidate_revision": CANDIDATE_REVISION,
        },
        "protocol": _file_identity(protocol),
        "compatibility": _file_identity(root / _COMPATIBILITY),
        "source": dense_source_identity(root),
        "development_candidate": candidate_report,
        "current_runtime": runtime,
        "threshold_report": threshold_report,
    }


def _load_development_freeze(
    path: Path, *, root: Path, protocol: Path
) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DenseWorkflowError("development freeze is invalid") from error
    if not isinstance(value, dict):
        raise DenseWorkflowError("development freeze is invalid")
    freeze = cast(dict[str, Any], value)
    if (
        freeze.get("schema_version") != "mke.dense_development_freeze.v1"
        or freeze.get("candidate")
        != {"candidate_id": CANDIDATE_ID, "candidate_revision": CANDIDATE_REVISION}
        or freeze.get("protocol") != _file_identity(protocol)
        or freeze.get("compatibility") != _file_identity(root / _COMPATIBILITY)
        or freeze.get("source") != dense_source_identity(root)
    ):
        raise DenseWorkflowError("development freeze identity drift")
    threshold = freeze.get("threshold_report")
    if not isinstance(threshold, dict):
        raise DenseWorkflowError("development freeze is invalid")
    validate_threshold_report(cast(dict[str, Any], threshold))
    return freeze


def _combine_runtime_semantics(
    development: dict[str, Any], holdout: dict[str, Any], *, root: Path
) -> dict[str, Any]:
    chinese = load_chinese_retrieval_protocol(root / _CHINESE_PROTOCOL)
    all_results = [
        *cast(list[dict[str, Any]], development["results"]),
        *cast(list[dict[str, Any]], holdout["results"]),
    ]
    by_id = {item["query_id"]: item for item in all_results}
    return normalize_current_runtime_semantics(
        {"results": [by_id[item.query_id] for item in chinese.queries]},
        chinese,
    )


def _canonical_runner_report(report: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(report, ensure_ascii=False))
    return cast(dict[str, Any], value)


def _write_exclusive_json(path: Path, payload: dict[str, Any]) -> None:
    _write_exclusive_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_exclusive_text(path: Path, text: str) -> None:
    if path.exists():
        raise DenseWorkflowError("record target already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            raise DenseWorkflowError("record target already exists")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _file_identity(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.name,
        "bytes": len(data),
        "sha256": sha256(data).hexdigest(),
    }


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _discover_repository(protocol: Path) -> Path:
    resolved = protocol.resolve()
    for candidate in (resolved.parent, *resolved.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    raise DenseWorkflowError("repository root could not be resolved")
