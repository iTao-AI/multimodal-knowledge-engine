from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from mke.evaluation import agent_context_unit_segmentation as segmentation
from mke.evaluation.agent_context_unit_segmentation import (
    DEFAULT_SEGMENTATION_BOUNDS,
    DEFAULT_SEGMENTATION_PROFILE,
    ParentPageEvidence,
    SegmentationBounds,
    SegmentationProfile,
    segment_page_context_units,
    segment_parent_pages,
)


def _parent(
    text: str | bytes,
    *,
    page: int = 1,
    source_id: str = "src_opaque_a",
    publication_id: str = "pub_opaque_a",
    evidence_id: str = "ev_opaque_a",
) -> ParentPageEvidence:
    return ParentPageEvidence(
        source_id=source_id,
        source_content_fingerprint="sha256:" + "1" * 64,
        publication_id=publication_id,
        evidence_id=evidence_id,
        locator_kind="page",
        locator_start=page,
        locator_end=page,
        text_bytes=text.encode("utf-8") if isinstance(text, str) else text,
    )


def _small_profile() -> SegmentationProfile:
    return SegmentationProfile(
        target_utf8_bytes=20,
        minimum_utf8_bytes=5,
        maximum_utf8_bytes=30,
        overlap_utf8_bytes=0,
        hard_page_boundary=True,
        original_whitespace_retained=True,
        heading_patterns=DEFAULT_SEGMENTATION_PROFILE.heading_patterns,
    )


def test_default_profile_enforces_frozen_sizes_and_zero_overlap() -> None:
    assert DEFAULT_SEGMENTATION_PROFILE == SegmentationProfile(
        target_utf8_bytes=1024,
        minimum_utf8_bytes=256,
        maximum_utf8_bytes=1536,
        overlap_utf8_bytes=0,
        hard_page_boundary=True,
        original_whitespace_retained=True,
        heading_patterns=(
            r"^[0-9]+(?:\.[0-9]+)*[ \t]+\S.*$",
            r"^第[一二三四五六七八九十百千万0-9]+[章节条][ \t]*\S.*$",
            r"^[一二三四五六七八九十百千万0-9]+、[ \t]*\S.*$",
            r"^[A-Z][A-Z0-9 ,:;()/'&\".\-]{4,}$",
        ),
    )

    units = segment_page_context_units(_parent("x" * 3400))

    assert [len(unit.text_bytes) for unit in units] == [1024, 1024, 1024, 328]
    assert all(len(unit.text_bytes) >= 256 for unit in units[:-1])
    assert all(len(unit.text_bytes) <= 1536 for unit in units)
    assert [(unit.start_utf8_byte, unit.end_utf8_byte) for unit in units] == [
        (0, 1024),
        (1024, 2048),
        (2048, 3072),
        (3072, 3400),
    ]


def test_default_bounds_freeze_protocol_capacity_inventory() -> None:
    assert DEFAULT_SEGMENTATION_BOUNDS == SegmentationBounds(
        max_parent_utf8_bytes=16 * 1024 * 1024,
        max_units_per_evidence=64,
        max_total_units=4096,
    )


def test_boundary_precedence_is_heading_then_paragraph_then_sentence_then_hard_split() -> None:
    profile = _small_profile()

    heading_text = "a" * 12 + ". " + "b" * 10 + "\n1 HEADING\n" + "c" * 18
    heading = segment_page_context_units(_parent(heading_text), profile=profile)
    assert heading[0].text_bytes == (("a" * 12 + ". " + "b" * 10 + "\n").encode())

    paragraph_text = "a" * 11 + ". " + "b" * 8 + "\n\n" + "c" * 20
    paragraph = segment_page_context_units(_parent(paragraph_text), profile=profile)
    assert paragraph[0].text_bytes == (("a" * 11 + ". " + "b" * 8 + "\n\n").encode())

    sentence_text = "a" * 17 + ". " + "b" * 22
    sentence = segment_page_context_units(_parent(sentence_text), profile=profile)
    assert sentence[0].text_bytes == (("a" * 17 + ". ").encode())

    hard = segment_page_context_units(_parent("z" * 40), profile=profile)
    assert [len(unit.text_bytes) for unit in hard] == [20, 20]


def test_boundaries_above_target_run_before_short_final_merge() -> None:
    profile = _small_profile()

    split = segment_page_context_units(
        _parent("a" * 17 + ". " + "b" * 9), profile=profile
    )
    assert [len(unit.text_bytes) for unit in split] == [19, 9]

    merged = segment_page_context_units(
        _parent("a" * 17 + ". " + "b" * 4), profile=profile
    )
    assert [len(unit.text_bytes) for unit in merged] == [23]

    retained = segment_page_context_units(_parent("x" * 52), profile=profile)
    assert [len(unit.text_bytes) for unit in retained] == [20, 20, 12]


def test_nfkc_boundary_discovery_preserves_original_unicode_bytes() -> None:
    profile = _small_profile()
    original = "a" * 8 + ". " + "b" * 5 + "\nＡＢＣＤＥ\n" + "e\u0301🙂。后续文本"

    units = segment_page_context_units(_parent(original), profile=profile)

    assert b"".join(unit.text_bytes for unit in units) == original.encode("utf-8")
    assert units[0].text_bytes.endswith(b"\n")
    assert b"\xef\xbc\xa1" in b"".join(unit.text_bytes for unit in units)
    assert b"\xc3\xa9" not in b"".join(unit.text_bytes for unit in units)
    for unit in units:
        unit.text_bytes.decode("utf-8")


def test_crlf_cjk_punctuation_combining_marks_and_emoji_are_byte_exact() -> None:
    text = "第一句。第二句！\r\n\r\n第三句？e\u0301🙂结束。" * 80

    units = segment_page_context_units(_parent(text))

    assert b"".join(unit.text_bytes for unit in units) == text.encode("utf-8")
    assert units[0].start_utf8_byte == 0
    assert units[-1].end_utf8_byte == len(text.encode("utf-8"))
    assert all(
        unit.text_sha256 == hashlib.sha256(unit.text_bytes).hexdigest()
        for unit in units
    )
    assert all(
        unit.end_utf8_byte == next_unit.start_utf8_byte
        for unit, next_unit in zip(units, units[1:], strict=False)
    )


def test_projection_identity_ignores_opaque_ids_but_retains_provenance() -> None:
    first_parent = _parent("stable page bytes " * 100)
    second_parent = _parent(
        "stable page bytes " * 100,
        source_id="src_opaque_b",
        publication_id="pub_opaque_b",
        evidence_id="ev_opaque_b",
    )

    first = segment_page_context_units(first_parent)
    second = segment_page_context_units(second_parent)

    assert [unit.stable_context_unit_id for unit in first] == [
        unit.stable_context_unit_id for unit in second
    ]
    assert first[0].source_id == "src_opaque_a"
    assert first[0].publication_id == "pub_opaque_a"
    assert first[0].evidence_id == "ev_opaque_a"
    assert second[0].source_id == "src_opaque_b"
    assert second[0].publication_id == "pub_opaque_b"
    assert second[0].evidence_id == "ev_opaque_b"
    assert first[0].source_content_fingerprint == second[0].source_content_fingerprint
    assert first[0].parent_locator == ("page", 1, 1)


def test_parent_capacity_exact_boundary_passes_and_one_over_fails_before_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bounds = SegmentationBounds(
        max_parent_utf8_bytes=1536,
        max_units_per_evidence=64,
        max_total_units=4096,
    )
    segment_page_context_units(_parent(b"x" * 1536), bounds=bounds)

    calls = 0

    def unexpected_discovery(_text: bytes, _profile: SegmentationProfile) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("boundary discovery must not run")

    monkeypatch.setattr(segmentation, "_discover_boundaries", unexpected_discovery)
    with pytest.raises(ValueError, match="segmentation source capacity exceeded"):
        segment_page_context_units(_parent(b"x" * 1537), bounds=bounds)
    assert calls == 0


def test_over_cap_invalid_utf8_fails_before_decode_discovery_or_unit_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _parent(b"\xff" * 11)
    bounds = SegmentationBounds(
        max_parent_utf8_bytes=10,
        max_units_per_evidence=64,
        max_total_units=4096,
    )
    discovery_calls = 0
    allocation_calls = 0

    def unexpected_discovery(_text: bytes, _profile: SegmentationProfile) -> object:
        nonlocal discovery_calls
        discovery_calls += 1
        raise AssertionError("boundary discovery must not run")

    def unexpected_allocation(*_args: object) -> object:
        nonlocal allocation_calls
        allocation_calls += 1
        raise AssertionError("ContextUnit allocation must not run")

    monkeypatch.setattr(segmentation, "_discover_boundaries", unexpected_discovery)
    monkeypatch.setattr(segmentation, "_context_unit", unexpected_allocation)

    with pytest.raises(ValueError, match="segmentation source capacity exceeded"):
        segment_page_context_units(parent, bounds=bounds)
    assert discovery_calls == 0
    assert allocation_calls == 0


def test_within_cap_invalid_utf8_fails_before_discovery_or_unit_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _parent(b"\xff")
    discovery_calls = 0
    allocation_calls = 0

    def unexpected_discovery(_text: bytes, _profile: SegmentationProfile) -> object:
        nonlocal discovery_calls
        discovery_calls += 1
        raise AssertionError("boundary discovery must not run")

    def unexpected_allocation(*_args: object) -> object:
        nonlocal allocation_calls
        allocation_calls += 1
        raise AssertionError("ContextUnit allocation must not run")

    monkeypatch.setattr(segmentation, "_discover_boundaries", unexpected_discovery)
    monkeypatch.setattr(segmentation, "_context_unit", unexpected_allocation)

    with pytest.raises(ValueError, match="parent page UTF-8 is invalid"):
        segment_page_context_units(parent)
    assert discovery_calls == 0
    assert allocation_calls == 0


def test_unit_capacity_one_over_fails_before_boundary_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = replace(
        _small_profile(),
        target_utf8_bytes=10,
        minimum_utf8_bytes=5,
        maximum_utf8_bytes=10,
    )
    bounds = SegmentationBounds(
        max_parent_utf8_bytes=100,
        max_units_per_evidence=2,
        max_total_units=4096,
    )
    calls = 0

    def unexpected_discovery(_text: bytes, _profile: SegmentationProfile) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("boundary discovery must not run")

    monkeypatch.setattr(segmentation, "_discover_boundaries", unexpected_discovery)
    with pytest.raises(ValueError, match="segmentation unit capacity exceeded"):
        segment_page_context_units(_parent(b"x" * 21), profile=profile, bounds=bounds)
    assert calls == 0


def test_pages_never_cross_and_total_capacity_is_closed() -> None:
    first = _parent("first-page " * 160, page=1)
    second = _parent("second-page " * 160, page=2)

    units = segment_parent_pages((first, second))

    assert {unit.parent_locator for unit in units} == {
        ("page", 1, 1),
        ("page", 2, 2),
    }
    assert all(
        (b"first-page" in unit.text_bytes) ^ (b"second-page" in unit.text_bytes)
        for unit in units
    )
    assert (
        b"".join(unit.text_bytes for unit in units if unit.locator_start == 1)
        == first.text_bytes
    )
    assert (
        b"".join(unit.text_bytes for unit in units if unit.locator_start == 2)
        == second.text_bytes
    )

    with pytest.raises(ValueError, match="segmentation total unit capacity exceeded"):
        segment_parent_pages(
            (first, second),
            bounds=SegmentationBounds(
                max_parent_utf8_bytes=4096,
                max_units_per_evidence=64,
                max_total_units=2,
            ),
        )


def test_semantic_total_one_over_fails_before_context_unit_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = SegmentationProfile(
        target_utf8_bytes=10,
        minimum_utf8_bytes=5,
        maximum_utf8_bytes=20,
        overlap_utf8_bytes=0,
        hard_page_boundary=True,
        original_whitespace_retained=True,
        heading_patterns=DEFAULT_SEGMENTATION_PROFILE.heading_patterns,
    )
    bounds = SegmentationBounds(
        max_parent_utf8_bytes=20,
        max_units_per_evidence=64,
        max_total_units=1,
    )
    allocation_calls = 0

    def unexpected_allocation(*_args: object) -> object:
        nonlocal allocation_calls
        allocation_calls += 1
        raise AssertionError("ContextUnit allocation must not run")

    monkeypatch.setattr(segmentation, "_context_unit", unexpected_allocation)

    with pytest.raises(ValueError, match="segmentation total unit capacity exceeded"):
        segment_parent_pages((_parent(b"x" * 15),), profile=profile, bounds=bounds)
    assert allocation_calls == 0


@pytest.mark.parametrize(
    "change",
    (
        {"locator_kind": "timestamp_ms"},
        {"locator_start": 0, "locator_end": 0},
        {"source_content_fingerprint": "not-a-digest"},
        {"text_bytes": b""},
    ),
)
def test_parent_authority_rejects_non_page_or_invalid_provenance(
    change: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "source_id": "src_opaque",
        "source_content_fingerprint": "sha256:" + "1" * 64,
        "publication_id": "pub_opaque",
        "evidence_id": "ev_opaque",
        "locator_kind": "page",
        "locator_start": 1,
        "locator_end": 1,
        "text_bytes": b"page",
    }
    values.update(change)
    with pytest.raises(ValueError, match="parent page authority is invalid"):
        ParentPageEvidence(**values)  # type: ignore[arg-type]
