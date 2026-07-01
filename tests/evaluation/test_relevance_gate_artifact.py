from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.relevance_gate_artifact import (
    RelevanceGateArtifactError,
    validate_relevance_gate_artifact,
)
from mke.evaluation.relevance_gate_workflow import (
    run_relevance_gate_holdout,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json"
FREEZE = ROOT / "benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json"
ARTIFACT = ROOT / "benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json"
RECEIPT = ROOT / "benchmarks/retrieval/cjk-relevance-gate-reranker-v1-holdout-receipt.json"


def test_validator_accepts_canonical_artifact() -> None:
    validate_relevance_gate_artifact(
        artifact_path=ARTIFACT,
        protocol_path=PROTOCOL,
        repository_root=ROOT,
    )


def test_validator_rejects_qrel_category_split_leakage(tmp_path: Path) -> None:
    payload = _artifact_copy()
    feature = _first_feature(payload)
    feature["qrel_grade"] = 2
    feature["category"] = "semantic_paraphrase"
    feature["split"] = "development"
    feature["expected_locator"] = "doc|page|1|1|sha"
    path = tmp_path / "leaky.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RelevanceGateArtifactError, match="forbidden"):
        validate_relevance_gate_artifact(
            artifact_path=path,
            protocol_path=PROTOCOL,
            repository_root=ROOT,
        )


def test_validator_rejects_modified_source_text_digest(tmp_path: Path) -> None:
    payload = _artifact_copy()
    feature = _first_feature(payload)
    feature["source_text_digest"] = "0" * 64
    path = tmp_path / "digest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RelevanceGateArtifactError, match="feature"):
        validate_relevance_gate_artifact(
            artifact_path=path,
            protocol_path=PROTOCOL,
            repository_root=ROOT,
        )


def test_validator_rejects_coordinated_metric_and_result_tampering(tmp_path: Path) -> None:
    payload = _artifact_copy()
    holdout = cast(dict[str, object], payload["holdout"])
    metrics = cast(dict[str, object], holdout["metrics"])
    cast(dict[str, object], metrics["recall_at_5"])["value"] = 1.0
    results = cast(list[dict[str, object]], holdout["results"])
    cast(list[dict[str, object]], results[0]["allowed_results"]).clear()
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RelevanceGateArtifactError, match="recompute"):
        validate_relevance_gate_artifact(
            artifact_path=path,
            protocol_path=PROTOCOL,
            repository_root=ROOT,
        )


def test_validator_rejects_missing_development_freeze(tmp_path: Path) -> None:
    payload = _artifact_copy()
    state = cast(dict[str, object], payload["state"])
    state["development_freeze_path"] = "benchmarks/retrieval/missing-freeze.json"
    path = tmp_path / "missing-freeze.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RelevanceGateArtifactError, match="development freeze"):
        validate_relevance_gate_artifact(
            artifact_path=path,
            protocol_path=PROTOCOL,
            repository_root=ROOT,
        )


def test_validator_rejects_holdout_when_development_did_not_pass(tmp_path: Path) -> None:
    payload = _artifact_copy()
    payload["development_status"] = "valid_negative"
    payload["holdout_status"] = "observed"
    path = tmp_path / "invalid-holdout.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RelevanceGateArtifactError, match="holdout"):
        validate_relevance_gate_artifact(
            artifact_path=path,
            protocol_path=PROTOCOL,
            repository_root=ROOT,
        )


@pytest.mark.parametrize(
    ("field", "tampered_value"),
    [
        ("holdout_status", "not_observed"),
        ("reranker_model_status", "not_evaluated"),
        ("query_rewrite_status", "eligible"),
        ("segmentation_status", "not_evaluated"),
        ("e3f_runtime_status", "eligible"),
    ],
)
def test_validator_rejects_top_level_decision_status_drift(
    tmp_path: Path,
    field: str,
    tampered_value: str,
) -> None:
    payload = _artifact_copy()
    payload[field] = tampered_value
    path = tmp_path / f"{field}-drift.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RelevanceGateArtifactError, match="status"):
        validate_relevance_gate_artifact(
            artifact_path=path,
            protocol_path=PROTOCOL,
            repository_root=ROOT,
        )


def test_validator_rejects_bool_int_confusion(tmp_path: Path) -> None:
    payload = _artifact_copy()
    feature = _first_feature(payload)
    feature["locator_start"] = True
    path = tmp_path / "bool-int.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RelevanceGateArtifactError, match="feature"):
        validate_relevance_gate_artifact(
            artifact_path=path,
            protocol_path=PROTOCOL,
            repository_root=ROOT,
        )


def test_holdout_records_receipt_before_comparison(tmp_path: Path) -> None:
    artifact_path = tmp_path / "comparison.json"
    receipt_path = tmp_path / "receipt.json"

    artifact = run_relevance_gate_holdout(
        protocol_path=PROTOCOL,
        candidate_id="cjk-relevance-gate-reranker-v1",
        development_freeze_path=FREEZE,
        record_path=artifact_path,
        holdout_receipt_path=receipt_path,
        repository_root=ROOT,
    )

    assert receipt_path.exists()
    assert artifact_path.exists()
    assert artifact["holdout_status"] == "observed"
    state = cast(dict[str, object], artifact["state"])
    assert isinstance(state["holdout_receipt_sha256"], str)


def _artifact_copy() -> dict[str, object]:
    return cast(dict[str, object], json.loads(ARTIFACT.read_text(encoding="utf-8")))


def _first_feature(payload: dict[str, object]) -> dict[str, object]:
    holdout = cast(dict[str, object], payload["holdout"])
    results = cast(list[dict[str, object]], holdout["results"])
    rows = cast(list[dict[str, object]], results[0]["feature_rows"])
    return rows[0]
