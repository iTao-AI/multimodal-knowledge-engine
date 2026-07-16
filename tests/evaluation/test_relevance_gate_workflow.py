from __future__ import annotations

from pathlib import Path

import pytest

import mke.evaluation.relevance_gate_workflow as workflow
from mke.evaluation.relevance_gate_workflow import (
    RelevanceGateWorkflowError,
    load_relevance_gate_inputs,
    record_relevance_gate_development_freeze,
    run_relevance_gate_development,
    run_relevance_gate_holdout,
    select_development_profile,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json"


def test_loads_protocol_bound_e3c_e3d_artifacts_and_rebuilds_union() -> None:
    inputs = load_relevance_gate_inputs(
        protocol_path=PROTOCOL,
        repository_root=ROOT,
        split="development",
    )

    assert inputs.split == "development"
    assert inputs.dense_artifact_sha256 == (
        "3e14f011ab6fb5605d1fcf0834f7734ba4a3ef2c5d398bc80a6a94f0b93b1e4f"
    )
    assert inputs.rrf_artifact_sha256 == (
        "410f64736fc77a3d7c88f9eef34872282270b1fa02ff9ff1c79989f85924d1f4"
    )
    assert len(inputs.queries) == 24
    first = inputs.queries[0]
    assert first.query_id == "zh-dev-exact-01"
    assert first.union_rows[0].features.stable_locator_id == (
        "ub-service-core|page|14|14|"
        "319c778a244f0d83ac2822883509fdfcf51ffae54063ea293648487b0ef8ef7b"
    )
    assert first.union_rows[0].features.source_text_digest == (
        "319c778a244f0d83ac2822883509fdfcf51ffae54063ea293648487b0ef8ef7b"
    )


def test_development_only_does_not_read_holdout(monkeypatch: pytest.MonkeyPatch) -> None:
    original = workflow._load_rrf_partition  # pyright: ignore[reportPrivateUsage]

    def fail_on_holdout(*args: object, **kwargs: object) -> object:
        if kwargs.get("split") == "holdout":
            raise AssertionError("holdout was observed")
        return original(*args, **kwargs)  # type: ignore[misc]

    monkeypatch.setattr(workflow, "_load_rrf_partition", fail_on_holdout)

    report = run_relevance_gate_development(
        protocol_path=PROTOCOL,
        candidate_id="cjk-relevance-gate-reranker-v1",
        repository_root=ROOT,
    )

    assert report["holdout_status"] == "not_observed"
    assert "holdout" not in report


def test_selected_profile_follows_frozen_objective() -> None:
    selected = select_development_profile(
        {
            "lexical-floor": _profile_report(
                passed=True,
                recall=0.7,
                ndcg=0.7,
                dense_recovery=0,
            ),
            "balanced-constraint": _profile_report(
                passed=True,
                recall=0.8,
                ndcg=0.6,
                dense_recovery=1,
            ),
            "strict-constraint": _profile_report(
                passed=True,
                recall=0.8,
                ndcg=0.6,
                dense_recovery=1,
            ),
        }
    )

    assert selected == "strict-constraint"


def test_no_profile_passing_records_valid_negative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_score(*args: object, **kwargs: object) -> dict[str, object]:
        del args, kwargs
        return _profile_report(
            passed=False,
            recall=0.1,
            ndcg=0.1,
            dense_recovery=0,
        )

    monkeypatch.setattr(workflow, "_score_partition_for_profile", failing_score)

    report = run_relevance_gate_development(
        protocol_path=PROTOCOL,
        candidate_id="cjk-relevance-gate-reranker-v1",
        repository_root=ROOT,
    )

    assert report["development_status"] == "valid_negative"
    assert report["holdout_status"] == "not_observed"
    assert report["selected_profile"] is None


def test_development_freeze_uses_exclusive_create(tmp_path: Path) -> None:
    report = run_relevance_gate_development(
        protocol_path=PROTOCOL,
        candidate_id="cjk-relevance-gate-reranker-v1",
        repository_root=ROOT,
    )
    target = tmp_path / "freeze.json"
    record_relevance_gate_development_freeze(report=report, target_path=target)

    with pytest.raises(RelevanceGateWorkflowError, match="development freeze"):
        record_relevance_gate_development_freeze(report=report, target_path=target)


def test_holdout_before_development_freeze_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(RelevanceGateWorkflowError, match="development freeze"):
        run_relevance_gate_holdout(
            protocol_path=PROTOCOL,
            candidate_id="cjk-relevance-gate-reranker-v1",
            development_freeze_path=tmp_path / "missing-freeze.json",
            record_path=tmp_path / "comparison.json",
            holdout_receipt_path=tmp_path / "holdout-receipt.json",
            repository_root=ROOT,
        )


def _profile_report(
    *,
    passed: bool,
    recall: float,
    ndcg: float,
    dense_recovery: int,
) -> dict[str, object]:
    return {
        "profile_id": "synthetic",
        "passed_development_gates": passed,
        "metrics": {
            "recall_at_5": {"value": recall},
            "ndcg_at_10": {"value": ndcg},
            "mrr_at_5": {"value": 0.6},
        },
        "diagnostics": {
            "dense_only_recovery_retained_count": dense_recovery,
            "union_only_recovery_retained_count": dense_recovery,
        },
    }
