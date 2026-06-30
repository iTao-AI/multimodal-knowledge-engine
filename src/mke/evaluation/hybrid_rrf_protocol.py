"""Frozen E3-D hybrid RRF protocol lock."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import cast

from mke.evaluation.rrf_fusion import RrfCandidateConfig

SCHEMA_VERSION = "mke.hybrid_rrf_protocol.v1"
CANDIDATE_ID = "cjk-active-scan-qwen3-rrf-v1"
CANDIDATE_REVISION = 1
LEXICAL_ARM_ID = "cjk-active-scan-overlap-v1"
DENSE_ARM_ID = "qwen3-embedding-0.6b-exact-v1"

_SPLITS = ("development", "holdout")
_TIE_BREAK_ORDER = [
    "fused_score_desc",
    "arm_hit_count_desc",
    "best_individual_rank_asc",
    "lexical_rank_asc",
    "dense_rank_asc",
    "stable_locator_id_asc",
]
_INPUTS = {
    "chinese_protocol": "tests/fixtures/retrieval-chinese-v1/protocol.json",
    "qrel_adjudication": "tests/fixtures/retrieval-chinese-v1/qrel-adjudication.json",
    "dense_artifact": "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json",
    "runtime_strategy_source": "src/mke/retrieval/strategy.py",
    "rrf_source": "src/mke/evaluation/rrf_fusion.py",
    "workflow_source": "src/mke/evaluation/hybrid_rrf_workflow.py",
    "artifact_source": "src/mke/evaluation/hybrid_rrf_artifact.py",
    "metrics_source": "src/mke/evaluation/graded_metrics.py",
    "cli_source": "src/mke/cli.py",
}


class HybridRrfProtocolError(ValueError):
    """Raised when the hybrid RRF protocol lock is invalid."""


def build_hybrid_rrf_protocol_lock(
    *,
    repository_root: Path,
) -> dict[str, object]:
    root = repository_root.resolve()
    config = RrfCandidateConfig.default()
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate": {
            "candidate_id": CANDIDATE_ID,
            "candidate_revision": CANDIDATE_REVISION,
        },
        "arms": {
            "lexical": LEXICAL_ARM_ID,
            "dense": DENSE_ARM_ID,
        },
        "rrf": {
            "k": config.k,
            "lexical_weight": config.lexical_weight,
            "dense_weight": config.dense_weight,
            "input_depth": config.input_depth,
            "output_depth": config.output_depth,
            "score_decimals": config.score_decimals,
            "rank_base": 1,
            "tie_break_order": list(_TIE_BREAK_ORDER),
        },
        "dedupe": {
            "key": ["stable_locator_id", "source_text_digest"],
            "source_text_digest_required": True,
        },
        "splits": list(_SPLITS),
        "state": {
            "development_freeze_required_before_holdout": True,
            "holdout_receipt_mode": "exclusive_create",
            "candidate_status_initial": "not_evaluated",
            "runtime_promotion_status": "not_evaluated",
        },
        "inputs": {
            name: _file_identity(root, relative_path)
            for name, relative_path in _INPUTS.items()
        },
    }


def render_hybrid_rrf_protocol_lock_json(protocol: dict[str, object]) -> str:
    return json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_hybrid_rrf_protocol_lock(
    path: Path,
    *,
    repository_root: Path,
) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HybridRrfProtocolError("hybrid RRF protocol is invalid") from error
    if not isinstance(payload, dict):
        raise HybridRrfProtocolError("hybrid RRF protocol is invalid")
    protocol = cast(dict[str, object], payload)
    validate_hybrid_rrf_protocol_lock(protocol, repository_root=repository_root)
    return protocol


def validate_hybrid_rrf_protocol_lock(
    protocol: dict[str, object],
    *,
    repository_root: Path,
) -> None:
    expected = build_hybrid_rrf_protocol_lock(repository_root=repository_root)
    if protocol.get("schema_version") != SCHEMA_VERSION:
        raise HybridRrfProtocolError("schema is invalid")
    _validate_candidate(protocol.get("candidate"))
    _validate_arms(protocol.get("arms"))
    _validate_rrf(protocol.get("rrf"))
    _validate_dedupe(protocol.get("dedupe"))
    _validate_splits(protocol.get("splits"))
    _validate_state(protocol.get("state"))
    _validate_inputs(protocol.get("inputs"), repository_root=repository_root)
    if protocol != expected:
        raise HybridRrfProtocolError("hybrid RRF protocol identity drift")


def _validate_candidate(value: object) -> None:
    data = _object(value, "candidate")
    if (
        data.get("candidate_id") != CANDIDATE_ID
        or data.get("candidate_revision") != CANDIDATE_REVISION
        or type(data.get("candidate_revision")) is not int
    ):
        raise HybridRrfProtocolError("candidate identity is invalid")


def _validate_arms(value: object) -> None:
    if value != {"lexical": LEXICAL_ARM_ID, "dense": DENSE_ARM_ID}:
        raise HybridRrfProtocolError("arms are invalid")


def _validate_rrf(value: object) -> None:
    config = RrfCandidateConfig.default()
    if value != {
        "k": config.k,
        "lexical_weight": config.lexical_weight,
        "dense_weight": config.dense_weight,
        "input_depth": config.input_depth,
        "output_depth": config.output_depth,
        "score_decimals": config.score_decimals,
        "rank_base": 1,
        "tie_break_order": list(_TIE_BREAK_ORDER),
    }:
        raise HybridRrfProtocolError("RRF contract is invalid")


def _validate_dedupe(value: object) -> None:
    if value != {
        "key": ["stable_locator_id", "source_text_digest"],
        "source_text_digest_required": True,
    }:
        raise HybridRrfProtocolError("locator dedupe contract is invalid")


def _validate_splits(value: object) -> None:
    if value != list(_SPLITS):
        raise HybridRrfProtocolError("splits are invalid")


def _validate_state(value: object) -> None:
    data = _object(value, "state")
    if (
        data.get("development_freeze_required_before_holdout") is not True
        or data.get("holdout_receipt_mode") != "exclusive_create"
        or data.get("candidate_status_initial") != "not_evaluated"
        or data.get("runtime_promotion_status") != "not_evaluated"
    ):
        raise HybridRrfProtocolError("holdout state is invalid")


def _validate_inputs(value: object, *, repository_root: Path) -> None:
    data = _object(value, "input identities")
    if set(data) != set(_INPUTS):
        raise HybridRrfProtocolError("input identities are invalid")
    root = repository_root.resolve()
    for name, expected_path in _INPUTS.items():
        record = _object(data.get(name), f"{name} identity")
        recorded_path = record.get("path")
        if type(recorded_path) is not str:
            raise HybridRrfProtocolError("repository path is invalid")
        _repository_path(root, recorded_path)
        if record != _file_identity(root, expected_path):
            raise HybridRrfProtocolError("input identity drift")


def _file_identity(root: Path, relative_path: str) -> dict[str, object]:
    path = _repository_path(root, relative_path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise HybridRrfProtocolError("hybrid RRF protocol identity drift") from error
    return {
        "path": relative_path,
        "bytes": len(data),
        "sha256": sha256(data).hexdigest(),
    }


def _repository_path(root: Path, relative_path: str) -> Path:
    posix_path = PurePosixPath(relative_path)
    if posix_path.is_absolute() or ".." in posix_path.parts:
        raise HybridRrfProtocolError("repository path is invalid")
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise HybridRrfProtocolError("repository path is invalid")
    return path


def _object(value: object, subject: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise HybridRrfProtocolError(f"{subject} is invalid")
    return cast(dict[str, object], value)
