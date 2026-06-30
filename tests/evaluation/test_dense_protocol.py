from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.dense_protocol import (
    DenseProtocolValidationError,
    load_dense_protocol_lock,
    validate_dense_protocol_lock,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_LOCK = ROOT / "tests/fixtures/retrieval-dense-v1/protocol-lock.json"


def test_checked_in_dense_protocol_freezes_candidate_model_and_ranking_contract() -> None:
    protocol = load_dense_protocol_lock(PROTOCOL_LOCK, repository_root=ROOT)
    candidate = cast(dict[str, object], protocol["candidate"])
    model = cast(dict[str, object], protocol["model"])
    encoding = cast(dict[str, object], protocol["encoding"])
    ranking = cast(dict[str, object], protocol["ranking"])
    thresholds = cast(dict[str, object], protocol["thresholds"])

    assert protocol["schema_version"] == "mke.dense_retrieval_protocol.v1"
    assert candidate == {
        "candidate_id": "qwen3-embedding-0.6b-exact-v1",
        "candidate_revision": 1,
    }
    assert model["model_id"] == "Qwen/Qwen3-Embedding-0.6B"
    assert (
        model["model_revision"]
        == "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
    )
    assert model["dimension"] == 1024
    assert model["dtype"] == "float32"
    assert model["device"] == "cpu"
    assert model["remote_code"] == "prohibited"
    assert encoding["query_batch_size"] == 1
    assert encoding["document_batch_size"] == 4
    assert encoding["max_length"] == 8192
    assert ranking == {
        "top_k": 10,
        "portable_score_decimals": 6,
        "order": ["score_desc", "stable_locator_id_asc"],
    }
    assert thresholds["grid"] == [round(index / 100, 2) for index in range(101)]
    assert protocol["target_classes"] == [
        "semantic_paraphrase",
        "multi_condition",
        "ranking_hard_negative",
    ]


def test_dense_protocol_binds_inputs_and_separate_partition_state() -> None:
    protocol = load_dense_protocol_lock(PROTOCOL_LOCK, repository_root=ROOT)

    validate_dense_protocol_lock(protocol, repository_root=ROOT)
    inputs = cast(dict[str, dict[str, object]], protocol["inputs"])
    assert set(inputs) == {
        "chinese_protocol",
        "qrel_adjudication",
        "e3b_artifact",
        "runtime_strategy_source",
        "compatibility_artifact",
        "corpus_lock",
    }
    assert all(cast(int, item["bytes"]) > 0 for item in inputs.values())
    assert all(
        isinstance(item["sha256"], str) and len(item["sha256"]) == 64
        for item in inputs.values()
    )

    state = cast(dict[str, object], protocol["state"])
    assert state["development_freeze_required_before_holdout"] is True
    assert state["holdout_receipt_mode"] == "exclusive_create"
    assert state["runtime_promotion_status"] == "not_evaluated"
    partitions = cast(dict[str, dict[str, object]], protocol["partitions"])
    assert partitions["development"]["snapshot_id"] != partitions["holdout"]["snapshot_id"]
    assert partitions["development"]["projection_id"] != partitions["holdout"]["projection_id"]


def test_dense_protocol_rejects_identity_threshold_and_candidate_tampering(
    tmp_path: Path,
) -> None:
    protocol = load_dense_protocol_lock(PROTOCOL_LOCK, repository_root=ROOT)

    mutations: tuple[tuple[Callable[[dict[str, object]], None], str], ...] = (
        (_mutate_candidate_revision_bool, "candidate"),
        (_mutate_model_dimension, "model"),
        (_mutate_threshold_grid, "threshold"),
        (_mutate_missing_e3b_input, "input"),
        (_mutate_holdout_state, "holdout"),
    )
    for mutation, match in mutations:
        changed = _copy(protocol)
        mutation(changed)
        path = tmp_path / "protocol-lock.json"
        path.write_text(json.dumps(changed), encoding="utf-8")

        with pytest.raises(DenseProtocolValidationError, match=match):
            load_dense_protocol_lock(path, repository_root=ROOT)


def test_dense_protocol_rejects_absolute_paths_unknown_targets_and_identity_drift(
    tmp_path: Path,
) -> None:
    protocol = load_dense_protocol_lock(PROTOCOL_LOCK, repository_root=ROOT)

    changed = _copy(protocol)
    inputs = cast(dict[str, dict[str, object]], changed["inputs"])
    inputs["chinese_protocol"]["path"] = str(
        ROOT / "tests/fixtures/retrieval-chinese-v1/protocol.json"
    )
    path = tmp_path / "absolute.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(DenseProtocolValidationError, match="path"):
        load_dense_protocol_lock(path, repository_root=ROOT)

    changed = _copy(protocol)
    inputs = cast(dict[str, dict[str, object]], changed["inputs"])
    inputs["chinese_protocol"]["sha256"] = "0" * 64
    path = tmp_path / "drift.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(DenseProtocolValidationError, match="identity"):
        load_dense_protocol_lock(path, repository_root=ROOT)


def _copy(payload: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(json.dumps(payload)))


def _mutate_candidate_revision_bool(payload: dict[str, object]) -> None:
    cast(dict[str, object], payload["candidate"])["candidate_revision"] = True


def _mutate_model_dimension(payload: dict[str, object]) -> None:
    cast(dict[str, object], payload["model"])["dimension"] = 768


def _mutate_threshold_grid(payload: dict[str, object]) -> None:
    cast(dict[str, object], payload["thresholds"])["grid"] = [0.0, 0.5, 1.0]


def _mutate_missing_e3b_input(payload: dict[str, object]) -> None:
    del cast(dict[str, object], payload["inputs"])["e3b_artifact"]


def _mutate_holdout_state(payload: dict[str, object]) -> None:
    cast(dict[str, object], payload["state"])[
        "development_freeze_required_before_holdout"
    ] = False
