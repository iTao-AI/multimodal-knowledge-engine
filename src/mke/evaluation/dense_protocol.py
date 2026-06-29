"""Frozen E3-C dense comparison protocol lock."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import cast

from mke.adapters.vector.exact_cosine import EXACT_COSINE_ADAPTER_ID
from mke.embeddings.contracts import (
    CANDIDATE_ID,
    CANDIDATE_REVISION,
    EMBEDDING_DIMENSION,
    MAX_MODEL_LENGTH,
    MODEL_ID,
    MODEL_REVISION,
)

_SCHEMA = "mke.dense_retrieval_protocol.v1"
_TARGET_CLASSES = [
    "semantic_paraphrase",
    "multi_condition",
    "ranking_hard_negative",
]
_INPUTS = {
    "chinese_protocol": "tests/fixtures/retrieval-chinese-v1/protocol.json",
    "qrel_adjudication": "tests/fixtures/retrieval-chinese-v1/qrel-adjudication.json",
    "e3b_artifact": "benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json",
    "runtime_strategy_source": "src/mke/retrieval/strategy.py",
    "compatibility_artifact": "benchmarks/retrieval/qwen3-embedding-0.6b-compatibility.json",
    "corpus_lock": "tests/fixtures/retrieval-dense-v1/corpus-lock.json",
}


class DenseProtocolValidationError(ValueError):
    """Raised when the dense comparison protocol lock is invalid."""


def build_dense_protocol_lock(*, repository_root: Path) -> dict[str, object]:
    root = repository_root.resolve()
    return {
        "schema_version": _SCHEMA,
        "candidate": {
            "candidate_id": CANDIDATE_ID,
            "candidate_revision": CANDIDATE_REVISION,
        },
        "model": {
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "dimension": EMBEDDING_DIMENSION,
            "dtype": "float32",
            "output_dtype": "float32",
            "normalized": True,
            "device": "cpu",
            "remote_code": "prohibited",
        },
        "encoding": {
            "query_instruction": (
                "Given a Chinese user query, retrieve relevant evidence passages "
                "that answer the query"
            ),
            "query_template": (
                "Instruct: Given a Chinese user query, retrieve relevant evidence "
                "passages that answer the query\nQuery:{query}"
            ),
            "document_prompt": None,
            "max_length": MAX_MODEL_LENGTH,
            "padding_side": "left",
            "query_batch_size": 1,
            "document_batch_size": 4,
        },
        "projection": {
            "selected_adapter": EXACT_COSINE_ADAPTER_ID,
            "reference_adapter": EXACT_COSINE_ADAPTER_ID,
            "temporary": True,
            "production_projection": "none",
        },
        "ranking": {
            "top_k": 10,
            "portable_score_decimals": 6,
            "order": ["score_desc", "stable_locator_id_asc"],
        },
        "thresholds": {
            "grid": [round(index / 100, 2) for index in range(101)],
            "selection_order": [
                "reject_unanswerable_no_hit_below_0.500000",
                "reject_hard_negative_failure_above_0.300000",
                "maximize_target_grade_2_recovery",
                "tie_break_dense_ndcg_at_10_desc",
                "tie_break_higher_threshold",
            ],
        },
        "target_classes": list(_TARGET_CLASSES),
        "gates": {
            "development": {
                "target_recovery_minimum": 2,
                "unanswerable_no_hit_minimum": 0.5,
                "hard_negative_failure_maximum": 0.3,
            },
            "holdout": {
                "target_recovery_minimum": 2,
                "unanswerable_no_hit_minimum": 0.5,
                "hard_negative_failure_maximum": 0.142857,
            },
        },
        "arms": [
            "e3a-historical-fts5-baseline",
            "cjk-trigram-overlap-v1",
            "cjk-active-scan-overlap-v1",
            CANDIDATE_ID,
        ],
        "partitions": {
            "development": {
                "split": "development",
                "snapshot_id": "retrieval-dense-v1-development",
                "projection_id": "qwen3-embedding-0.6b-exact-v1-development",
            },
            "holdout": {
                "split": "holdout",
                "snapshot_id": "retrieval-dense-v1-holdout",
                "projection_id": "qwen3-embedding-0.6b-exact-v1-holdout",
            },
        },
        "state": {
            "development_freeze_required_before_holdout": True,
            "holdout_receipt_mode": "exclusive_create",
            "candidate_status_initial": "not_evaluated",
            "e3d_status_initial": "not_evaluated",
            "runtime_promotion_status": "not_evaluated",
        },
        "inputs": {
            name: _file_identity(root, relative_path)
            for name, relative_path in _INPUTS.items()
        },
    }


def load_dense_protocol_lock(
    path: Path,
    *,
    repository_root: Path,
) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DenseProtocolValidationError("dense protocol lock is invalid") from error
    if not isinstance(payload, dict):
        raise DenseProtocolValidationError("dense protocol lock is invalid")
    protocol = cast(dict[str, object], payload)
    validate_dense_protocol_lock(protocol, repository_root=repository_root)
    return protocol


def validate_dense_protocol_lock(
    protocol: dict[str, object],
    *,
    repository_root: Path,
) -> None:
    expected = build_dense_protocol_lock(repository_root=repository_root)
    _validate_candidate(protocol.get("candidate"))
    _validate_model(protocol.get("model"))
    _validate_encoding(protocol.get("encoding"))
    _validate_projection(protocol.get("projection"))
    _validate_ranking(protocol.get("ranking"))
    _validate_thresholds(protocol.get("thresholds"))
    if protocol.get("schema_version") != _SCHEMA:
        raise DenseProtocolValidationError("schema is invalid")
    if protocol.get("target_classes") != _TARGET_CLASSES:
        raise DenseProtocolValidationError("target classes are invalid")
    if protocol.get("arms") != expected["arms"]:
        raise DenseProtocolValidationError("comparison arms are invalid")
    _validate_gates(protocol.get("gates"))
    _validate_partitions(protocol.get("partitions"))
    _validate_state(protocol.get("state"))
    _validate_inputs(protocol.get("inputs"), repository_root=repository_root)
    if protocol != expected:
        raise DenseProtocolValidationError("dense protocol identity drift")


def render_dense_protocol_lock_json(protocol: dict[str, object]) -> str:
    return json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _validate_candidate(value: object) -> None:
    data = _object(value, "candidate")
    if (
        data.get("candidate_id") != CANDIDATE_ID
        or data.get("candidate_revision") != CANDIDATE_REVISION
    ):
        raise DenseProtocolValidationError("candidate identity is invalid")
    if type(data.get("candidate_revision")) is not int:
        raise DenseProtocolValidationError("candidate revision is invalid")


def _validate_model(value: object) -> None:
    data = _object(value, "model")
    if (
        data.get("model_id") != MODEL_ID
        or data.get("model_revision") != MODEL_REVISION
        or data.get("dimension") != EMBEDDING_DIMENSION
        or data.get("dtype") != "float32"
        or data.get("output_dtype") != "float32"
        or data.get("normalized") is not True
        or data.get("device") != "cpu"
        or data.get("remote_code") != "prohibited"
    ):
        raise DenseProtocolValidationError("model identity is invalid")


def _validate_encoding(value: object) -> None:
    data = _object(value, "encoding")
    if (
        data.get("max_length") != MAX_MODEL_LENGTH
        or data.get("padding_side") != "left"
        or data.get("query_batch_size") != 1
        or data.get("document_batch_size") != 4
        or data.get("document_prompt") is not None
    ):
        raise DenseProtocolValidationError("encoding contract is invalid")


def _validate_projection(value: object) -> None:
    data = _object(value, "projection")
    if (
        data.get("selected_adapter") != EXACT_COSINE_ADAPTER_ID
        or data.get("reference_adapter") != EXACT_COSINE_ADAPTER_ID
        or data.get("temporary") is not True
        or data.get("production_projection") != "none"
    ):
        raise DenseProtocolValidationError("projection contract is invalid")


def _validate_ranking(value: object) -> None:
    data = _object(value, "ranking")
    if data != {
        "top_k": 10,
        "portable_score_decimals": 6,
        "order": ["score_desc", "stable_locator_id_asc"],
    }:
        raise DenseProtocolValidationError("ranking contract is invalid")


def _validate_thresholds(value: object) -> None:
    data = _object(value, "threshold")
    grid = data.get("grid")
    if grid != [round(index / 100, 2) for index in range(101)]:
        raise DenseProtocolValidationError("threshold grid is invalid")


def _validate_gates(value: object) -> None:
    data = _object(value, "gates")
    if data.get("development") != {
        "target_recovery_minimum": 2,
        "unanswerable_no_hit_minimum": 0.5,
        "hard_negative_failure_maximum": 0.3,
    }:
        raise DenseProtocolValidationError("development gates are invalid")
    if data.get("holdout") != {
        "target_recovery_minimum": 2,
        "unanswerable_no_hit_minimum": 0.5,
        "hard_negative_failure_maximum": 0.142857,
    }:
        raise DenseProtocolValidationError("holdout gates are invalid")


def _validate_partitions(value: object) -> None:
    data = _object(value, "partitions")
    development = _object(data.get("development"), "development partition")
    holdout = _object(data.get("holdout"), "holdout partition")
    if (
        development.get("snapshot_id") == holdout.get("snapshot_id")
        or development.get("projection_id") == holdout.get("projection_id")
    ):
        raise DenseProtocolValidationError("partition projections are invalid")


def _validate_state(value: object) -> None:
    data = _object(value, "state")
    if (
        data.get("development_freeze_required_before_holdout") is not True
        or data.get("holdout_receipt_mode") != "exclusive_create"
        or data.get("runtime_promotion_status") != "not_evaluated"
    ):
        raise DenseProtocolValidationError("holdout state is invalid")


def _validate_inputs(value: object, *, repository_root: Path) -> None:
    data = _object(value, "input identities")
    if set(data) != set(_INPUTS):
        raise DenseProtocolValidationError("input identities are invalid")
    for name, expected_path in _INPUTS.items():
        record = _object(data.get(name), f"{name} identity")
        recorded_path = record.get("path")
        if type(recorded_path) is not str:
            raise DenseProtocolValidationError("repository path is invalid")
        _repository_path(repository_root.resolve(), recorded_path)
        if record != _file_identity(repository_root.resolve(), expected_path):
            raise DenseProtocolValidationError("input identity drift")


def _file_identity(root: Path, relative_path: str) -> dict[str, object]:
    path = _repository_path(root, relative_path)
    return {
        "path": relative_path,
        "bytes": path.stat().st_size,
        "sha256": sha256(path.read_bytes()).hexdigest(),
    }


def _repository_path(root: Path, relative_path: str) -> Path:
    if PurePosixPath(relative_path).is_absolute() or ".." in PurePosixPath(relative_path).parts:
        raise DenseProtocolValidationError("repository path is invalid")
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise DenseProtocolValidationError("repository path is invalid")
    return path


def _object(value: object, subject: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise DenseProtocolValidationError(f"{subject} is invalid")
    return cast(dict[str, object], value)
