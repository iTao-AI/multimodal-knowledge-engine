from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.chinese_protocol import load_chinese_retrieval_protocol
from mke.evaluation.dense_miss_audit import (
    DenseMissAuditValidationError,
    run_development_miss_audit,
    validate_development_miss_audit_report,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/retrieval-chinese-v1/protocol.json"
ARTIFACT = ROOT / "benchmarks/retrieval/qwen3-embedding-0.6b-development-miss-audit.json"
TARGET_MISSES = {
    "zh-dev-semantic-04",
    "zh-dev-multi-01",
    "zh-dev-multi-02",
    "zh-dev-hard-01",
}
TARGET_CLASSES = {
    "semantic_paraphrase",
    "multi_condition",
    "ranking_hard_negative",
}


def test_development_miss_audit_records_current_runtime_target_misses_only() -> None:
    protocol = load_chinese_retrieval_protocol(PROTOCOL)

    report = run_development_miss_audit(PROTOCOL, repository_root=ROOT)
    validate_development_miss_audit_report(report, protocol, repository_root=ROOT)
    misses = cast(list[dict[str, object]], report["misses"])

    assert report["schema_version"] == "mke.dense_development_miss_audit.v1"
    assert report["runtime_strategy"] == "cjk-active-scan-overlap-v1"
    assert report["split"] == "development"
    assert report["target_classes"] == sorted(TARGET_CLASSES)
    assert {item["query_id"] for item in misses} == TARGET_MISSES
    assert all(item["split"] == "development" for item in misses)
    assert all(item["category"] in TARGET_CLASSES for item in misses)
    assert all(item["grade_2_pages"] for item in misses)
    assert all(
        "hypotheses" in item and "causal_label" not in item
        for item in misses
    )


def test_audit_records_compiled_query_active_scan_terms_overlap_and_constraints() -> None:
    report = run_development_miss_audit(PROTOCOL, repository_root=ROOT)
    misses = cast(list[dict[str, object]], report["misses"])
    by_id = {item["query_id"]: item for item in misses}

    multi = by_id["zh-dev-multi-01"]
    assert multi["compiled_query"] == '"rdma" "tcp" "urma" "shm" "api"'
    assert multi["active_scan_terms"]
    assert multi["constraints"] == {
        "has_numeric_or_date": False,
        "has_entity_like_ascii": True,
        "has_multi_condition": True,
    }
    assert multi["retrieved_locators"] == [
        {
            "document_id": "ub-service-core",
            "locator_kind": "page",
            "locator_start": 26,
            "locator_end": 26,
        }
    ]
    grade_2_pages = cast(list[dict[str, object]], multi["grade_2_pages"])
    assert all(
        {
            "locator",
            "page_text_sha256",
            "page_text_chars",
            "lexical_overlap",
            "answer_span_locality",
        }
        <= set(page)
        for page in grade_2_pages
    )

    semantic = by_id["zh-dev-semantic-04"]
    assert semantic["compiled_query"] == ""
    assert semantic["compiled_query_empty"] is True
    assert semantic["active_scan_terms"]
    semantic_constraints = cast(dict[str, object], semantic["constraints"])
    assert semantic_constraints["has_multi_condition"] is False


def test_audit_validator_rejects_holdout_missing_or_reclassified_misses() -> None:
    protocol = load_chinese_retrieval_protocol(PROTOCOL)
    report = run_development_miss_audit(PROTOCOL, repository_root=ROOT)

    changed = _copy(report)
    changed["split"] = "holdout"
    with pytest.raises(DenseMissAuditValidationError, match="holdout"):
        validate_development_miss_audit_report(changed, protocol, repository_root=ROOT)

    changed = _copy(report)
    cast(list[dict[str, object]], changed["misses"]).pop()
    with pytest.raises(DenseMissAuditValidationError, match="target misses"):
        validate_development_miss_audit_report(changed, protocol, repository_root=ROOT)

    changed = _copy(report)
    cast(list[dict[str, object]], changed["misses"])[0]["category"] = "number_date_unit"
    with pytest.raises(DenseMissAuditValidationError, match="reclassifies"):
        validate_development_miss_audit_report(changed, protocol, repository_root=ROOT)


def test_audit_validator_rejects_subjective_labels_private_paths_and_locator_drift() -> None:
    protocol = load_chinese_retrieval_protocol(PROTOCOL)
    report = run_development_miss_audit(PROTOCOL, repository_root=ROOT)

    changed = _copy(report)
    cast(list[dict[str, object]], changed["misses"])[0]["causal_label"] = "dense_required"
    with pytest.raises(DenseMissAuditValidationError, match="subjective"):
        validate_development_miss_audit_report(changed, protocol, repository_root=ROOT)

    changed = _copy(report)
    cast(list[dict[str, object]], changed["misses"])[0]["debug_path"] = "/Users/mac/private"
    with pytest.raises(DenseMissAuditValidationError, match="private"):
        validate_development_miss_audit_report(changed, protocol, repository_root=ROOT)

    changed = _copy(report)
    first_page = cast(
        list[dict[str, object]],
        cast(list[dict[str, object]], changed["misses"])[0]["grade_2_pages"],
    )[0]
    locator = cast(dict[str, object], first_page["locator"])
    locator["locator_start"] = 999
    locator["locator_end"] = 999
    with pytest.raises(DenseMissAuditValidationError, match="locator"):
        validate_development_miss_audit_report(changed, protocol, repository_root=ROOT)


def test_checked_in_development_miss_audit_artifact_matches_generated_report() -> None:
    protocol = load_chinese_retrieval_protocol(PROTOCOL)
    generated = run_development_miss_audit(PROTOCOL, repository_root=ROOT)
    checked_in = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    validate_development_miss_audit_report(checked_in, protocol, repository_root=ROOT)
    assert checked_in == generated


def _copy(report: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(json.dumps(report, ensure_ascii=False)))
