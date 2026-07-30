from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation import agent_context_unit_ranking as ranking
from mke.evaluation.agent_context_unit_segmentation import (
    ContextUnit,
    ParentPageEvidence,
    SegmentationProfile,
    segment_page_context_units,
)

ROOT = Path(__file__).resolve().parents[2]


def _parent(
    text: str,
    *,
    page: int = 1,
    source_id: str = "source-opaque-a",
    publication_id: str = "publication-opaque-a",
    evidence_id: str = "evidence-opaque-a",
    fingerprint_digit: str = "1",
) -> ParentPageEvidence:
    return ParentPageEvidence(
        source_id=source_id,
        source_content_fingerprint="sha256:" + fingerprint_digit * 64,
        publication_id=publication_id,
        evidence_id=evidence_id,
        locator_kind="page",
        locator_start=page,
        locator_end=page,
        text_bytes=text.encode("utf-8"),
    )


def _small_units(
    text: str,
    *,
    page: int = 1,
    source_id: str = "source-opaque-a",
    publication_id: str = "publication-opaque-a",
    evidence_id: str = "evidence-opaque-a",
    fingerprint_digit: str = "1",
) -> tuple[ContextUnit, ...]:
    return segment_page_context_units(
        _parent(
            text,
            page=page,
            source_id=source_id,
            publication_id=publication_id,
            evidence_id=evidence_id,
            fingerprint_digit=fingerprint_digit,
        ),
        profile=SegmentationProfile(
            target_utf8_bytes=12,
            minimum_utf8_bytes=4,
            maximum_utf8_bytes=16,
            overlap_utf8_bytes=0,
            hard_page_boundary=True,
            original_whitespace_retained=True,
            heading_patterns=(r"^HEADING$",),
        ),
    )


def _whole_units(
    text: str,
    *,
    page: int = 1,
) -> tuple[ContextUnit, ...]:
    return segment_page_context_units(_parent(text, page=page))


def _stable_unit_id(row: ranking.UnitProjectionRow) -> str:
    payload = {
        "content_fingerprint": row.source_content_fingerprint,
        "end_utf8_byte": row.end_utf8_byte,
        "locator_end": row.parent_locator[2],
        "locator_kind": row.parent_locator[0],
        "locator_start": row.parent_locator[1],
        "rank_profile_id": row.rank_profile_id,
        "start_utf8_byte": row.start_utf8_byte,
        "text_sha256": row.text_sha256,
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def test_default_bounds_match_protocol_and_scientific_lock() -> None:
    protocol = json.loads(
        (ROOT / "tests/fixtures/agent-context-unit-v2/protocol.json").read_bytes()
    )
    scientific_lock = json.loads(
        (ROOT / "tests/fixtures/agent-context-unit-v2/scientific-input-lock.json").read_bytes()
    )
    expected = {
        "max_projection_rows": 16_384,
        "max_projection_utf8_bytes": 33_554_432,
        "max_candidate_pool": 1_000,
        "max_diagnostic_rank": 10,
        "max_primary_results": 5,
    }

    assert ranking.DEFAULT_RANKING_BOUNDS == ranking.RankingBounds(**expected)
    assert {key: protocol["projection_bounds"][key] for key in expected} == expected
    assert {key: scientific_lock["projection_bounds"][key] for key in expected} == expected


def test_projection_rows_bind_exact_bytes_and_stable_provenance() -> None:
    units = _small_units("alpha beta gamma delta epsilon")

    rows = ranking.build_unit_projection(units)

    assert b"".join(row.text_bytes for row in rows) == b"alpha beta gamma delta epsilon"
    assert all(row.text_sha256 == hashlib.sha256(row.text_bytes).hexdigest() for row in rows)
    assert all(row.source_content_fingerprint == "sha256:" + "1" * 64 for row in rows)
    assert all(row.parent_locator == ("page", 1, 1) for row in rows)
    assert all(row.rank_profile_id == "deterministic-unit-rank-v1" for row in rows)


def test_rank_profile_id_matches_frozen_o1_scientific_authority() -> None:
    scientific_lock = json.loads(
        (ROOT / "tests/fixtures/agent-context-unit-v2/scientific-input-lock.json").read_bytes()
    )
    o1_profile = scientific_lock["mechanism_profile"]["o1"]
    o1_mechanism_id = scientific_lock["mechanism_profile"]["mechanism_ids"]["o1"]
    assert o1_profile["rank_profile_id"] == o1_mechanism_id

    fts_rows = ranking.build_unit_projection(_whole_units("alpha beta"))
    cjk_rows = ranking.build_unit_projection(_whole_units("中华人民共和国数据安全治理"))
    fts_result = ranking.rank_fts_units(
        fts_rows,
        query_id="q-frozen-fts-profile",
        query_text="alpha",
    )
    cjk_result = ranking.rank_cjk_units(
        cjk_rows,
        query_id="q-frozen-cjk-profile",
        query_text="中华人民共和国数据安全",
    )

    assert {row.rank_profile_id for row in (*fts_rows, *cjk_rows)} == {
        o1_profile["rank_profile_id"]
    }
    assert fts_result.rank_profile_id == o1_profile["rank_profile_id"]
    assert cjk_result.rank_profile_id == o1_profile["rank_profile_id"]


def test_projection_count_one_over_fails_before_row_access() -> None:
    class Bomb:
        def __getattribute__(self, name: str) -> object:
            raise AssertionError(f"row field accessed before count gate: {name}")

    bounds = ranking.RankingBounds(max_projection_rows=1)
    with pytest.raises(ValueError, match="projection row capacity exceeded"):
        ranking.build_unit_projection(
            cast(tuple[ContextUnit, ...], (Bomb(), Bomb())),
            bounds=bounds,
        )


def test_projection_bytes_exact_boundary_and_one_over_precede_row_parsing() -> None:
    class SizedBomb:
        text_bytes = b"xxx"

        def __getattribute__(self, name: str) -> object:
            if name == "text_bytes":
                return b"xxx"
            raise AssertionError(f"row parsed before byte gate: {name}")

    exact = _small_units("xx")
    bounds = ranking.RankingBounds(max_projection_utf8_bytes=2)
    assert ranking.build_unit_projection(exact, bounds=bounds)[0].text_bytes == b"xx"

    with pytest.raises(ValueError, match="projection byte capacity exceeded"):
        ranking.build_unit_projection(
            cast(tuple[ContextUnit, ...], (SizedBomb(),)),
            bounds=bounds,
        )


def test_projection_rejects_duplicate_gap_and_authority_tamper() -> None:
    units = _small_units("alpha beta gamma delta epsilon")

    with pytest.raises(ValueError, match="projection unit identity is duplicated"):
        ranking.build_unit_projection((units[0], units[0]))
    with pytest.raises(ValueError, match="projection parent coverage is invalid"):
        ranking.build_unit_projection(units[1:])
    with pytest.raises(ValueError, match="projection row authority is invalid"):
        ranking.build_unit_projection((replace(units[0], text_sha256="0" * 64), *units[1:]))


def test_fts_rank_uses_canonical_finite_float_hex_and_separate_arm() -> None:
    rows = ranking.build_unit_projection(_small_units("alpha beta gamma alpha beta gamma"))

    result = ranking.rank_fts_units(rows, query_id="q-fts", query_text="alpha")

    assert result.route == "fts"
    assert result.rank_profile_id == "deterministic-unit-rank-v1"
    assert result.candidate_count > 0
    assert all(item.score.arm == "fts" for item in result.diagnostic)
    scores = tuple(cast(ranking.FtsUnitScore, item.score) for item in result.diagnostic)
    assert all(
        math.isfinite(float.fromhex(score.rank_score_hex))
        and float.fromhex(score.rank_score_hex).hex() == score.rank_score_hex
        for score in scores
    )


@pytest.mark.parametrize(
    "score",
    ("nan", "inf", "-inf", "0x1p+0", "1.0"),
)
def test_fts_score_rejects_nonfinite_or_noncanonical_tokens(score: str) -> None:
    with pytest.raises(ValueError, match="FTS score authority is invalid"):
        ranking.FtsUnitScore(
            arm="fts",
            rank_score_hex=score,
            bm25_score_hex="0x1.0000000000000p+0",
        )


def test_fts_score_rejects_divergent_rank_and_bm25_tokens() -> None:
    with pytest.raises(ValueError, match="FTS score authority is invalid"):
        ranking.FtsUnitScore(
            arm="fts",
            rank_score_hex=(1.0).hex(),
            bm25_score_hex=(2.0).hex(),
        )


def test_cjk_rank_records_exact_overlap_ratio_and_matched_terms() -> None:
    rows = ranking.build_unit_projection(_whole_units("中华人民共和国数据安全治理"))

    result = ranking.rank_cjk_units(
        rows,
        query_id="q-cjk",
        query_text="中华人民共和国数据安全",
    )

    assert result.route == "cjk"
    assert result.rank_profile_id == "deterministic-unit-rank-v1"
    first = result.diagnostic[0]
    assert first.score.arm == "cjk"
    assert first.score.overlap_count == len(first.score.matched_terms)
    assert first.score.query_term_count == len(
        ranking.compile_cjk_overlap_terms_for_units("中华人民共和国数据安全")
    )
    assert float.fromhex(first.score.overlap_ratio_hex) == pytest.approx(
        first.score.overlap_count / first.score.query_term_count
    )
    assert first.score.matched_terms == tuple(dict.fromkeys(first.score.matched_terms))


def test_cjk_ties_use_fingerprint_before_locator_and_offsets() -> None:
    fingerprint_one = segment_page_context_units(
        _parent("中华人民共和国", page=2, fingerprint_digit="1")
    )
    fingerprint_nine = segment_page_context_units(
        _parent("中华人民共和国", page=1, fingerprint_digit="9")
    )
    rows = ranking.build_unit_projection((*fingerprint_nine, *fingerprint_one))

    result = ranking.rank_cjk_units(
        rows,
        query_id="q-cjk-order",
        query_text="中华人民共和国",
    )

    assert [
        (item.source_content_fingerprint[-64:-63], item.parent_locator[1])
        for item in result.diagnostic
    ] == [("1", 2), ("9", 1)]


def test_cjk_score_rejects_ratio_inconsistent_with_term_denominator() -> None:
    with pytest.raises(ValueError, match="CJK score authority is invalid"):
        ranking.CjkUnitScore(
            arm="cjk",
            overlap_count=2,
            query_term_count=3,
            overlap_ratio_hex=(0.5).hex(),
            matched_terms=("数据安", "据安全"),
        )


def test_cjk_score_rejects_non_tuple_matched_terms() -> None:
    with pytest.raises(ValueError, match="CJK score authority is invalid"):
        ranking.CjkUnitScore(
            arm="cjk",
            overlap_count=2,
            query_term_count=4,
            overlap_ratio_hex=(0.5).hex(),
            matched_terms=cast(tuple[str, ...], ["数据安", "据安全"]),
        )


def test_arm_local_scores_cannot_be_compared_across_routes() -> None:
    fts = ranking.FtsUnitScore(
        arm="fts",
        rank_score_hex=(1.0).hex(),
        bm25_score_hex=(1.0).hex(),
    )
    cjk = ranking.CjkUnitScore(
        arm="cjk",
        overlap_count=2,
        query_term_count=4,
        overlap_ratio_hex=(0.5).hex(),
        matched_terms=("数据安", "据安全"),
    )

    with pytest.raises(ValueError, match="cross-arm score comparison is forbidden"):
        ranking.compare_arm_local_scores(fts, cjk)


def test_stable_ties_ignore_opaque_ids_and_insertion_order() -> None:
    first_units = _small_units(
        "alpha same",
        page=2,
        source_id="source-z",
        publication_id="publication-z",
        evidence_id="evidence-z",
    )
    second_units = _small_units(
        "alpha same",
        page=1,
        source_id="source-a",
        publication_id="publication-a",
        evidence_id="evidence-a",
    )
    forward = ranking.build_unit_projection((*first_units, *second_units))
    reverse = ranking.build_unit_projection((*second_units, *first_units))

    forward_result = ranking.rank_fts_units(forward, query_id="q-tie", query_text="alpha")
    reverse_result = ranking.rank_fts_units(reverse, query_id="q-tie", query_text="alpha")

    assert forward_result.portable_bytes() == reverse_result.portable_bytes()
    assert [item.parent_locator for item in forward_result.diagnostic] == [
        ("page", 1, 1),
        ("page", 2, 2),
    ]


def test_fts_ties_use_locator_before_source_fingerprint() -> None:
    page_two = _small_units(
        "alpha same",
        page=2,
        fingerprint_digit="1",
    )
    page_one = _small_units(
        "alpha same",
        page=1,
        fingerprint_digit="9",
    )
    rows = ranking.build_unit_projection((*page_two, *page_one))

    result = ranking.rank_fts_units(rows, query_id="q-fts-tie", query_text="alpha")

    assert [item.parent_locator for item in result.diagnostic] == [
        ("page", 1, 1),
        ("page", 2, 2),
    ]


def test_fts_ties_use_byte_offsets_before_source_fingerprint() -> None:
    profile = SegmentationProfile(
        target_utf8_bytes=5,
        minimum_utf8_bytes=4,
        maximum_utf8_bytes=6,
        overlap_utf8_bytes=0,
        hard_page_boundary=True,
        original_whitespace_retained=True,
        heading_patterns=(r"^alpha$",),
    )
    later = segment_page_context_units(
        _parent("xxxx\nalpha", fingerprint_digit="1"),
        profile=profile,
    )
    earlier = segment_page_context_units(_parent("alpha", fingerprint_digit="9"))
    rows = ranking.build_unit_projection((*later, *earlier))

    result = ranking.rank_fts_units(rows, query_id="q-byte-tie", query_text="alpha")

    assert [
        (item.source_content_fingerprint[-64:-63], item.start_utf8_byte)
        for item in result.diagnostic
    ] == [("9", 0), ("1", 5)]


@pytest.mark.parametrize(
    "field",
    (
        "stable_context_unit_id",
        "source_content_fingerprint",
        "parent_text_sha256",
        "text_sha256",
    ),
)
def test_rank_rejects_noncanonical_digest_field_shapes(field: str) -> None:
    rows = ranking.build_unit_projection(_small_units("alpha beta"))
    row = rows[0]
    if field == "stable_context_unit_id":
        forged = replace(row, stable_context_unit_id=row.stable_context_unit_id[7:])
    elif field == "source_content_fingerprint":
        forged = replace(
            row,
            source_content_fingerprint=row.source_content_fingerprint[7:],
        )
        forged = replace(forged, stable_context_unit_id=_stable_unit_id(forged))
    elif field == "parent_text_sha256":
        forged = replace(row, parent_text_sha256="sha256:" + row.parent_text_sha256)
    else:
        forged = replace(row, text_sha256="sha256:" + row.text_sha256)

    with pytest.raises(ValueError, match="projection row authority is invalid"):
        ranking.rank_fts_units(
            (forged, *rows[1:]),
            query_id=f"q-{field}",
            query_text="alpha",
        )


def test_rank_rejects_projection_row_digest_tamper() -> None:
    rows = ranking.build_unit_projection(_small_units("alpha beta"))
    tampered = (replace(rows[0], text_sha256="0" * 64), *rows[1:])

    with pytest.raises(ValueError, match="projection row authority is invalid"):
        ranking.rank_fts_units(
            tampered,
            query_id="q-tamper",
            query_text="alpha",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("source_content_fingerprint", None),
        ("stable_context_unit_id", 7),
        ("parent_text_sha256", None),
        ("text_sha256", None),
        ("parent_locator", ["page", 1, 1]),
        ("parent_locator", ()),
        ("parent_locator", ("page", 1)),
        ("parent_locator", ("page", 1, True)),
        ("parent_locator", ("page", 1, "1")),
    ),
)
def test_rank_rejects_malformed_projection_fields_with_closed_error(
    field: str,
    value: object,
) -> None:
    rows = ranking.build_unit_projection(_small_units("alpha beta"))
    forged = replace(rows[0], **{field: value})

    with pytest.raises(ValueError, match="^projection row authority is invalid$"):
        ranking.rank_fts_units(
            (forged, *rows[1:]),
            query_id=f"q-malformed-{field}",
            query_text="alpha",
        )


def test_top_limits_parent_collapse_and_candidate_expansion_are_exact() -> None:
    units = _small_units("alpha " * 40)
    rows = ranking.build_unit_projection(units)

    result = ranking.rank_fts_units(rows, query_id="q-expand", query_text="alpha")

    assert len(result.diagnostic) == min(10, result.candidate_count)
    assert len(result.primary_stable_context_unit_ids) == min(5, result.candidate_count)
    assert result.unique_parent_count == 1
    assert {item.parent_collapsed_rank for item in result.diagnostic} == {1}
    assert result.candidate_expansion.unit_candidate_count == result.candidate_count
    assert result.candidate_expansion.unique_parent_count == 1
    assert float.fromhex(result.candidate_expansion.ratio_hex) == result.candidate_count


@pytest.mark.parametrize("route", ("fts", "cjk"))
def test_candidate_pool_exact_boundary_passes_and_one_over_fails(route: str) -> None:
    rows = ranking.build_unit_projection(
        (
            *_whole_units("alpha 中华人民共和国", page=1),
            *_whole_units("alpha 中华人民共和国", page=2),
        )
    )
    bounds = ranking.RankingBounds(max_candidate_pool=1)
    rank = ranking.rank_fts_units if route == "fts" else ranking.rank_cjk_units
    query = "alpha" if route == "fts" else "中华人民共和国"

    with pytest.raises(ValueError, match="candidate pool capacity exceeded"):
        rank(rows, query_id=f"q-{route}", query_text=query, bounds=bounds)

    one = ranking.build_unit_projection(_small_units(query, page=1))
    assert (
        rank(one, query_id=f"q-{route}-boundary", query_text=query, bounds=bounds).candidate_count
        == 1
    )


def test_fresh_workspace_projection_and_rank_bytes_are_identical() -> None:
    workspace_a = _small_units(
        "alpha beta gamma",
        source_id="source-workspace-a",
        publication_id="publication-workspace-a",
        evidence_id="evidence-workspace-a",
    )
    workspace_b = _small_units(
        "alpha beta gamma",
        source_id="source-workspace-b",
        publication_id="publication-workspace-b",
        evidence_id="evidence-workspace-b",
    )

    rows_a = ranking.build_unit_projection(workspace_a)
    rows_b = ranking.build_unit_projection(workspace_b)
    result_a = ranking.rank_fts_units(rows_a, query_id="q-portable", query_text="alpha")
    result_b = ranking.rank_fts_units(rows_b, query_id="q-portable", query_text="alpha")

    assert rows_a == rows_b
    assert result_a.portable_bytes() == result_b.portable_bytes()


def test_ranking_contract_has_no_label_filename_or_delivery_authority() -> None:
    row_fields = {field.name for field in dataclasses.fields(ranking.UnitProjectionRow)}
    result_fields = {field.name for field in dataclasses.fields(ranking.UnitRankResult)}
    forbidden = {
        "label",
        "qrel",
        "filename",
        "display_name",
        "delivered_text",
        "residual_gate",
        "verdict",
    }

    assert row_fields.isdisjoint(forbidden)
    assert result_fields.isdisjoint(forbidden)
    source = inspect.getsource(ranking)
    assert "agent_context_unit_grading" not in source
    assert "agent_context_unit_assembly" not in source


def _context_component(
    row: ranking.UnitProjectionRow,
    *,
    kind: str = "heading",
    text: bytes = b"source heading",
) -> ranking.SourceContextProjectionComponent:
    return ranking.SourceContextProjectionComponent(
        stable_context_unit_id=row.stable_context_unit_id,
        kind=kind,
        status="available",
        source_content_fingerprint=row.source_content_fingerprint,
        publication_identity="sha256:" + "2" * 64,
        origin_evidence_ref="sha256:" + "3" * 64,
        parent_locator=row.parent_locator,
        origin_start_utf8_byte=0,
        origin_end_utf8_byte=len(text),
        text_bytes=text,
        text_sha256=hashlib.sha256(text).hexdigest(),
    )


def test_o3_projection_reuses_o1_units_and_separates_context_origin() -> None:
    rows = ranking.build_unit_projection(_whole_units("alpha body"))
    component = _context_component(rows[0])

    projection = ranking.build_source_context_projection(
        rows,
        (component,),
        variant="heading",
    )

    assert len(projection) == 1
    assert projection[0].unit == rows[0]
    assert projection[0].unit.text_bytes == b"alpha body"
    assert projection[0].retrieval_text_bytes == b"alpha body\n[heading]\nsource heading"
    assert projection[0].components == (component,)
    assert projection[0].projection_policy_id == ("source-context-index-v1:heading:projection")
    assert projection[0].rank_profile_id == "source-context-index-v1:heading:rank"


def test_o3_route_specific_rank_preserves_selected_evidence_and_attribution() -> None:
    fts_rows = ranking.build_unit_projection(_whole_units("plain body"))
    fts_projection = ranking.build_source_context_projection(
        fts_rows,
        (_context_component(fts_rows[0], text=b"needle heading"),),
        variant="heading",
    )
    fts_result = ranking.rank_source_context_fts(
        fts_projection,
        query_id="q-o3-fts",
        query_text="needle",
    )
    assert fts_result.rank.route == "fts"
    assert fts_result.rank.primary_stable_context_unit_ids == (fts_rows[0].stable_context_unit_id,)
    assert fts_result.attributions[0].unit_match is False
    assert fts_result.attributions[0].context_only is True
    assert fts_result.attributions[0].component_kinds == ("heading",)
    assert fts_result.attributions[0].origin_evidence_refs == ("sha256:" + "3" * 64,)

    cjk_rows = ranking.build_unit_projection(_whole_units("不含检索词"))
    cjk_projection = ranking.build_source_context_projection(
        cjk_rows,
        (_context_component(cjk_rows[0], text="数据安全治理".encode()),),
        variant="heading",
    )
    cjk_result = ranking.rank_source_context_cjk(
        cjk_projection,
        query_id="q-o3-cjk",
        query_text="数据安全治理",
    )
    assert cjk_result.rank.route == "cjk"
    assert cjk_result.attributions[0].context_only is True


def test_o3_false_authority_and_capacity_fail_before_decode() -> None:
    row = ranking.build_unit_projection(_whole_units("alpha"))[0]
    component = _context_component(row, text=b"x" * 513)
    with pytest.raises(ValueError, match="source context capacity exceeded"):
        ranking.build_source_context_projection(
            (row,),
            (component,),
            variant="heading",
        )

    malformed = dataclasses.replace(
        _context_component(row),
        text_bytes=b"\xff",
        text_sha256=hashlib.sha256(b"\xff").hexdigest(),
    )
    with pytest.raises(ValueError, match="source context authority is invalid"):
        ranking.build_source_context_projection(
            (row,),
            (malformed,),
            variant="heading",
        )


def test_o3_rejects_filename_labels_duplicates_and_variant_drift() -> None:
    row = ranking.build_unit_projection(_whole_units("alpha"))[0]
    component = _context_component(row)
    with pytest.raises(ValueError, match="source context authority is invalid"):
        ranking.build_source_context_projection(
            (row,),
            (dataclasses.replace(component, kind="filename"),),
            variant="heading",
        )
    with pytest.raises(ValueError, match="source context authority is invalid"):
        ranking.build_source_context_projection(
            (row,),
            (component, component),
            variant="heading",
        )
    with pytest.raises(ValueError, match="source context authority is invalid"):
        ranking.build_source_context_projection(
            (row,),
            (component,),
            variant="combined",
        )


def test_o3_rank_rejects_forged_retrieval_text_and_component_duplication() -> None:
    row = ranking.build_unit_projection(_whole_units("plain body"))[0]
    component = _context_component(row, text=b"needle")
    projection = ranking.build_source_context_projection((row,), (component,), variant="heading")
    forged_text = b"forged needle"
    forged = dataclasses.replace(
        projection[0],
        retrieval_text_bytes=forged_text,
        retrieval_text_sha256=hashlib.sha256(forged_text).hexdigest(),
    )
    with pytest.raises(ValueError, match="source context ranking request is invalid"):
        ranking.rank_source_context_fts((forged,), query_id="q-forged", query_text="needle")

    duplicated = _context_component(
        row,
        kind="previous_unit",
        text=component.text_bytes,
    )
    with pytest.raises(ValueError, match="source context authority is invalid"):
        ranking.build_source_context_projection(
            (row,),
            (
                component,
                duplicated,
                _context_component(row, kind="next_unit", text=b"next"),
            ),
            variant="combined",
        )


def test_o3_bounds_and_row_types_fail_closed_before_field_access() -> None:
    row = ranking.build_unit_projection(_whole_units("plain body"))[0]
    component = _context_component(row)
    with pytest.raises(ValueError, match="ranking bounds are invalid"):
        ranking.build_source_context_projection(
            (row,),
            (component,),
            variant="heading",
            bounds=cast(ranking.RankingBounds, None),
        )
    with pytest.raises(ValueError, match="source context authority is invalid"):
        ranking.build_source_context_projection(
            cast(tuple[ranking.UnitProjectionRow, ...], (object(),)),
            (component,),
            variant="heading",
        )
