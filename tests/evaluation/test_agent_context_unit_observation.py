from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace

import pytest

from mke.application.evidence_access import EvidenceExcerpt
from mke.evaluation.agent_context_unit_observation import (
    AuthorityObservation,
    ObservationBounds,
    PortableObservation,
    PortableObservationItem,
    PortableScoreToken,
    seal_portable_observations,
    validate_observation_inventory,
)


def _portable_item() -> PortableObservationItem:
    return PortableObservationItem(
        content_fingerprint="sha256:" + "1" * 64,
        locator_kind="page",
        locator_start=3,
        locator_end=3,
        text_sha256="sha256:" + "2" * 64,
        route="fts5",
        rank=1,
        score=PortableScoreToken("fts5_rank", (-1.0).hex(), (-2.0).hex()),
        hints=("volcano",),
        excerpt=EvidenceExcerpt(
            "query_window",
            "volcano evidence",
            0,
            16,
            False,
            False,
            True,
            16,
        ),
        exact_read_sha256="sha256:" + "2" * 64,
        original_utf8_bytes=16,
        excerpt_utf8_bytes=16,
        exact_read_utf8_bytes=16,
    )


def test_portable_seal_excludes_runtime_authority_and_duration() -> None:
    portable = PortableObservation(
        query_id="q-one",
        query_text="volcano",
        expected_route="fts5",
        profile_identity="current-runtime-baseline-v1",
        statuses=(
            "query_policy_hit",
            "candidate_hit",
            "rank_hit",
            "delivery_hit",
            "output_complete",
            "exact_read_complete",
            "provenance_complete",
        ),
        items=(_portable_item(),),
        candidate_count=1,
        selected_count=1,
        delivered_utf8_bytes=16,
    )
    authority = AuthorityObservation(
        portable=portable,
        source_ids=("src_" + "1" * 32,),
        publication_ids=("pub_" + "2" * 32,),
        run_ids=("run_" + "3" * 32,),
        evidence_ids=("ev_" + "4" * 32,),
    )

    sealed = seal_portable_observations((authority.portable,))
    decoded = json.loads(sealed.bytes)
    rendered = sealed.bytes.decode()

    assert decoded["schema_version"] == "mke.agent_context_unit_observation.v2"
    assert sealed.sha256.startswith("sha256:")
    assert asdict(authority)["source_ids"]
    for forbidden in (
        "source_id",
        "publication_id",
        "run_id",
        "evidence_id",
        "database",
        "workspace",
        "duration",
    ):
        assert forbidden not in rendered

    second = replace(portable, query_id="q-two")
    assert seal_portable_observations((second, portable)) == seal_portable_observations(
        (portable, second)
    )


def test_observation_inventory_accepts_exact_bounds_and_rejects_one_over_first() -> None:
    bounds = ObservationBounds(
        max_sources=2,
        max_evidence_items=3,
        max_pages=3,
        max_source_text_utf8_bytes=20,
        max_candidate_pool=3,
        max_diagnostic_rank=2,
        max_primary_results=2,
    )
    validate_observation_inventory(
        bounds,
        source_count=2,
        evidence_count=3,
        page_count=3,
        source_text_utf8_bytes=20,
        candidate_count=3,
        rank_count=2,
        result_count=2,
    )

    for name, value in (
        ("source_count", 3),
        ("evidence_count", 4),
        ("page_count", 4),
        ("source_text_utf8_bytes", 21),
        ("candidate_count", 4),
        ("rank_count", 3),
        ("result_count", 3),
    ):
        values = {
            "source_count": 2,
            "evidence_count": 3,
            "page_count": 3,
            "source_text_utf8_bytes": 20,
            "candidate_count": 3,
            "rank_count": 2,
            "result_count": 2,
        }
        values[name] = value
        with pytest.raises(ValueError, match="observation capacity exceeded"):
            validate_observation_inventory(bounds, **values)


def test_portable_observation_rejects_opaque_score_and_byte_drift() -> None:
    with pytest.raises(ValueError, match="score token"):
        PortableScoreToken("fts5_rank", "nan", "0x0.0p+0")
    item = _portable_item()
    with pytest.raises(ValueError, match="byte accounting"):
        replace(item, excerpt_utf8_bytes=15)


def test_observation_module_has_no_grading_or_holdout_import_authority() -> None:
    imported = {
        name
        for name in sys.modules
        if name.startswith("mke.evaluation.agent_context_unit")
    }
    assert "mke.evaluation.agent_context_unit_grading_protocol" not in imported
    assert not any("holdout" in name for name in imported)
