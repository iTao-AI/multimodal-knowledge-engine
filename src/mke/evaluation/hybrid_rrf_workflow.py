"""E3-D hybrid RRF workflow and arm binding."""

from __future__ import annotations

import json
from dataclasses import dataclass
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
from mke.evaluation.hybrid_rrf_protocol import load_hybrid_rrf_protocol_lock
from mke.evaluation.rrf_fusion import ArmRankedResult


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
    seen: set[tuple[str, str]] = set()
    rows: list[ArmRankedResult] = []
    for rank, raw in enumerate(raw_locators, start=1):
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


def _list(value: object, subject: str) -> list[Any]:
    if not isinstance(value, list):
        raise HybridRrfWorkflowError(f"{subject} is invalid")
    return value


def _string(value: object, subject: str) -> str:
    if type(value) is not str or not value:
        raise HybridRrfWorkflowError(f"{subject} is invalid")
    return value


def _int(value: object, subject: str) -> int:
    if type(value) is not int or value <= 0:
        raise HybridRrfWorkflowError(f"{subject} is invalid")
    return value


def _float(value: object, subject: str) -> float:
    if type(value) not in {float, int}:
        raise HybridRrfWorkflowError(f"{subject} is invalid")
    return float(value)
