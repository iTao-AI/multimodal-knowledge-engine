from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.relevance_gate_features import (
    EvidenceCandidateInput,
    RelevanceGateFeatureError,
    build_relevance_features,
    load_repository_text,
)

ROOT = Path(__file__).resolve().parents[2]


def test_extracts_public_query_and_evidence_features() -> None:
    features = build_relevance_features(
        EvidenceCandidateInput(
            query_id="zh-dev-mixed-01",
            query_text="UB 服务 2.0 在 2025 年的限额是多少？API-7 是否适用？",
            stable_locator_id="ub-service-core|page|14|14|sha",
            document_id="ub-service-core",
            locator_kind="page",
            locator_start=14,
            locator_end=14,
            evidence_text="UB服务2.0的API-7限额为30GB，适用于2025年。",
            arm_contributions=("lexical", "dense"),
            lexical_rank=1,
            dense_rank=3,
            rrf_rank=1,
        )
    )

    assert features.query_id == "zh-dev-mixed-01"
    assert "服务" in features.query_terms.cjk
    assert features.query_terms.ascii == ("ub", "api")
    assert features.query_terms.mixed == ("api-7",)
    assert features.query_terms.numbers == ("2.0", "2025", "7")
    assert features.query_terms.units == ()
    assert features.evidence_terms.numbers == ("2.0", "7", "30", "2025")
    assert features.required_constraints.numbers == ("2.0", "2025", "7")
    assert features.required_constraints.mixed == ("api-7",)
    assert features.coverage.cjk_overlap_count >= 1
    assert features.coverage.ascii_overlap_count == 2
    assert features.coverage.missing_numbers == ()
    assert features.coverage.missing_mixed == ()
    assert features.source_text_digest
    assert features.to_json()["source_text_digest"] == features.source_text_digest


def test_normalizes_full_width_ascii_numbers_dates_and_units() -> None:
    features = build_relevance_features(
        EvidenceCandidateInput(
            query_id="zh-dev-unit-01",
            query_text="２０２５年 ＡＰＩ-７ 需要 ３０GB 吗？",
            stable_locator_id="doc|page|1|1|sha",
            document_id="doc",
            locator_kind="page",
            locator_start=1,
            locator_end=1,
            evidence_text="2025 年 API-7 需要 30gb。",
            arm_contributions=("dense",),
            lexical_rank=None,
            dense_rank=2,
            rrf_rank=2,
        )
    )

    assert features.query_terms.ascii == ("api", "gb")
    assert features.query_terms.mixed == ("api-7",)
    assert features.query_terms.numbers == ("2025", "7", "30")
    assert features.query_terms.units == ("gb",)
    assert features.coverage.missing_numbers == ()
    assert features.coverage.missing_units == ()


def test_detects_missing_numeric_date_unit_and_mixed_constraints() -> None:
    features = build_relevance_features(
        EvidenceCandidateInput(
            query_id="zh-dev-missing-01",
            query_text="API-7 在 2025 年需要 30GB 吗？",
            stable_locator_id="doc|page|2|2|sha",
            document_id="doc",
            locator_kind="page",
            locator_start=2,
            locator_end=2,
            evidence_text="API-8 在 2024 年需要 20MB。",
            arm_contributions=("dense",),
            lexical_rank=None,
            dense_rank=1,
            rrf_rank=1,
        )
    )

    assert features.coverage.missing_numbers == ("7", "2025", "30")
    assert features.coverage.missing_units == ("gb",)
    assert features.coverage.missing_mixed == ("api-7",)


def test_rejects_forbidden_scoring_inputs() -> None:
    forbidden = {
        "qrel_grade": 2,
        "category": "semantic_paraphrase",
        "split": "development",
        "expected_locator": "doc|page|1|1|sha",
    }

    with pytest.raises(RelevanceGateFeatureError, match="forbidden"):
        build_relevance_features(
            EvidenceCandidateInput(
                query_id="zh-dev-leak-01",
                query_text="测试",
                stable_locator_id="doc|page|1|1|sha",
                document_id="doc",
                locator_kind="page",
                locator_start=1,
                locator_end=1,
                evidence_text="测试",
                arm_contributions=("lexical",),
                lexical_rank=1,
                dense_rank=None,
                rrf_rank=1,
                extra_fields=forbidden,
            )
        )


def test_serialized_features_do_not_include_forbidden_inputs() -> None:
    features = build_relevance_features(
        EvidenceCandidateInput(
            query_id="zh-dev-safe-01",
            query_text="测试 2025",
            stable_locator_id="doc|page|1|1|sha",
            document_id="doc",
            locator_kind="page",
            locator_start=1,
            locator_end=1,
            evidence_text="测试 2025",
            arm_contributions=("lexical",),
            lexical_rank=1,
            dense_rank=None,
            rrf_rank=1,
            extra_fields={"debug_note": "not serialized"},
        )
    )

    payload = cast(dict[str, object], features.to_json())
    assert "extra_fields" not in payload
    assert "category" not in payload
    assert "split" not in payload
    assert "expected_locator" not in payload
    assert "qrel_grade" not in payload


def test_rejects_repo_external_or_missing_source_text(tmp_path: Path) -> None:
    with pytest.raises(RelevanceGateFeatureError, match="repository path"):
        load_repository_text(ROOT, str(tmp_path / "outside.txt"))

    with pytest.raises(RelevanceGateFeatureError, match="missing"):
        load_repository_text(ROOT, "tests/fixtures/retrieval-chinese-v1/missing.txt")
