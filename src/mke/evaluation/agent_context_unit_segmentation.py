"""Deterministic, byte-exact page-local segmentation for context evaluation."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from bisect import bisect_right
from dataclasses import dataclass
from typing import Literal

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SENTENCE_TERMINATORS = frozenset(".?!。！？；;")


@dataclass(frozen=True)
class SegmentationProfile:
    target_utf8_bytes: int
    minimum_utf8_bytes: int
    maximum_utf8_bytes: int
    overlap_utf8_bytes: int
    hard_page_boundary: bool
    original_whitespace_retained: bool
    heading_patterns: tuple[str, ...]

    def __post_init__(self) -> None:
        valid_sizes = (
            type(self.minimum_utf8_bytes) is int
            and type(self.target_utf8_bytes) is int
            and type(self.maximum_utf8_bytes) is int
            and 0 < self.minimum_utf8_bytes <= self.target_utf8_bytes
            <= self.maximum_utf8_bytes
        )
        if (
            not valid_sizes
            or self.overlap_utf8_bytes != 0
            or self.hard_page_boundary is not True
            or self.original_whitespace_retained is not True
            or not self.heading_patterns
            or len(set(self.heading_patterns)) != len(self.heading_patterns)
        ):
            raise ValueError("segmentation profile is invalid")
        try:
            for pattern in self.heading_patterns:
                re.compile(pattern)
        except re.error as error:
            raise ValueError("segmentation heading profile is invalid") from error


DEFAULT_SEGMENTATION_PROFILE = SegmentationProfile(
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


@dataclass(frozen=True)
class SegmentationBounds:
    max_parent_utf8_bytes: int = 16 * 1024 * 1024
    max_units_per_evidence: int = 64
    max_total_units: int = 4096

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value < 1
            for value in (
                self.max_parent_utf8_bytes,
                self.max_units_per_evidence,
                self.max_total_units,
            )
        ):
            raise ValueError("segmentation bounds are invalid")


DEFAULT_SEGMENTATION_BOUNDS = SegmentationBounds()


@dataclass(frozen=True)
class ParentPageEvidence:
    source_id: str
    source_content_fingerprint: str
    publication_id: str
    evidence_id: str
    locator_kind: Literal["page"]
    locator_start: int
    locator_end: int
    text_bytes: bytes

    def __post_init__(self) -> None:
        if (
            not self.source_id
            or not self.publication_id
            or not self.evidence_id
            or _SHA256.fullmatch(self.source_content_fingerprint) is None
            or self.locator_kind != "page"
            or type(self.locator_start) is not int
            or self.locator_start < 1
            or self.locator_end != self.locator_start
            or type(self.text_bytes) is not bytes
            or not self.text_bytes
        ):
            raise ValueError("parent page authority is invalid")


@dataclass(frozen=True)
class ContextUnit:
    source_id: str
    source_content_fingerprint: str
    publication_id: str
    evidence_id: str
    locator_kind: Literal["page"]
    locator_start: int
    locator_end: int
    parent_locator: tuple[Literal["page"], int, int]
    parent_text_sha256: str
    start_utf8_byte: int
    end_utf8_byte: int
    text_bytes: bytes
    text_sha256: str
    stable_context_unit_id: str
    rank_profile_id: str


@dataclass(frozen=True)
class _BoundaryInventory:
    heading: tuple[int, ...]
    paragraph: tuple[int, ...]
    sentence: tuple[int, ...]
    character: tuple[int, ...]


def segment_page_context_units(
    parent: ParentPageEvidence,
    *,
    profile: SegmentationProfile = DEFAULT_SEGMENTATION_PROFILE,
    bounds: SegmentationBounds = DEFAULT_SEGMENTATION_BOUNDS,
) -> tuple[ContextUnit, ...]:
    parent_digest, ranges = _segmentation_ranges(
        parent,
        profile=profile,
        bounds=bounds,
        total_unit_limit=None,
    )
    units = tuple(
        _context_unit(parent, parent_digest, start, end)
        for start, end in ranges
    )
    if b"".join(unit.text_bytes for unit in units) != parent.text_bytes:
        raise ValueError("segmentation byte fidelity is invalid")
    return units


def _segmentation_ranges(
    parent: ParentPageEvidence,
    *,
    profile: SegmentationProfile,
    bounds: SegmentationBounds,
    total_unit_limit: int | None,
) -> tuple[str, tuple[tuple[int, int], ...]]:
    byte_count = len(parent.text_bytes)
    if byte_count > bounds.max_parent_utf8_bytes:
        raise ValueError("segmentation source capacity exceeded")
    minimum_units = _ceiling_division(byte_count, profile.maximum_utf8_bytes)
    if minimum_units > bounds.max_units_per_evidence:
        raise ValueError("segmentation unit capacity exceeded")
    if total_unit_limit is not None and minimum_units > total_unit_limit:
        raise ValueError("segmentation total unit capacity exceeded")
    try:
        parent.text_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("parent page UTF-8 is invalid") from error

    inventory = _discover_boundaries(parent.text_bytes, profile)
    ranges = _segment_ranges(byte_count, profile, inventory)
    if len(ranges) > bounds.max_units_per_evidence:
        raise ValueError("segmentation unit capacity exceeded")
    if total_unit_limit is not None and len(ranges) > total_unit_limit:
        raise ValueError("segmentation total unit capacity exceeded")
    return hashlib.sha256(parent.text_bytes).hexdigest(), ranges


def segment_parent_pages(
    parents: tuple[ParentPageEvidence, ...],
    *,
    profile: SegmentationProfile = DEFAULT_SEGMENTATION_PROFILE,
    bounds: SegmentationBounds = DEFAULT_SEGMENTATION_BOUNDS,
) -> tuple[ContextUnit, ...]:
    if not parents:
        raise ValueError("segmentation parent inventory is invalid")
    stable_parents = [
        (
            parent.source_content_fingerprint,
            parent.locator_kind,
            parent.locator_start,
            parent.locator_end,
        )
        for parent in parents
    ]
    if len(stable_parents) != len(set(stable_parents)):
        raise ValueError("segmentation parent inventory is invalid")
    minimum_units = sum(
        _ceiling_division(len(parent.text_bytes), profile.maximum_utf8_bytes)
        for parent in parents
    )
    if minimum_units > bounds.max_total_units:
        raise ValueError("segmentation total unit capacity exceeded")

    units: list[ContextUnit] = []
    remaining_total_units = bounds.max_total_units
    for parent in parents:
        parent_digest, ranges = _segmentation_ranges(
            parent,
            profile=profile,
            bounds=bounds,
            total_unit_limit=remaining_total_units,
        )
        parent_units = tuple(
            _context_unit(parent, parent_digest, start, end)
            for start, end in ranges
        )
        if b"".join(unit.text_bytes for unit in parent_units) != parent.text_bytes:
            raise ValueError("segmentation byte fidelity is invalid")
        units.extend(parent_units)
        remaining_total_units -= len(ranges)
    return tuple(units)


def _discover_boundaries(
    text_bytes: bytes, profile: SegmentationProfile
) -> _BoundaryInventory:
    text = text_bytes.decode("utf-8")
    offsets = _utf8_offsets(text)
    heading_patterns = tuple(re.compile(pattern) for pattern in profile.heading_patterns)

    heading: set[int] = set()
    character_position = 0
    for line in text.splitlines(keepends=True):
        candidate = unicodedata.normalize("NFKC", line.rstrip("\r\n"))
        if character_position and any(
            pattern.fullmatch(candidate) is not None for pattern in heading_patterns
        ):
            heading.add(offsets[character_position])
        character_position += len(line)

    paragraph = {
        offsets[match.end()]
        for match in re.finditer(r"(?:\r?\n)[ \t]*(?:\r?\n)+", text)
    }
    sentence: set[int] = set()
    index = 0
    while index < len(text):
        if text[index] not in _SENTENCE_TERMINATORS:
            index += 1
            continue
        end = index + 1
        while end < len(text) and text[end].isspace():
            end += 1
        sentence.add(offsets[end])
        index = end

    return _BoundaryInventory(
        heading=tuple(sorted(heading)),
        paragraph=tuple(sorted(paragraph)),
        sentence=tuple(sorted(sentence)),
        character=tuple(offsets),
    )


def _segment_ranges(
    byte_count: int,
    profile: SegmentationProfile,
    inventory: _BoundaryInventory,
) -> tuple[tuple[int, int], ...]:
    ranges: list[tuple[int, int]] = []
    start = 0
    while start < byte_count:
        remaining = byte_count - start
        if remaining <= profile.target_utf8_bytes:
            ranges.append((start, byte_count))
            break
        lower = start + profile.minimum_utf8_bytes
        upper = min(byte_count, start + profile.maximum_utf8_bytes)
        target = start + profile.target_utf8_bytes
        end = _preferred_boundary(inventory, lower, upper, target)
        if end is None:
            end = _hard_split(inventory.character, start, target)
        ranges.append((start, end))
        start = end

    if (
        len(ranges) > 1
        and ranges[-1][1] - ranges[-1][0] < profile.minimum_utf8_bytes
        and ranges[-1][1] - ranges[-2][0] <= profile.maximum_utf8_bytes
    ):
        ranges[-2:] = [(ranges[-2][0], ranges[-1][1])]
    return tuple(ranges)


def _preferred_boundary(
    inventory: _BoundaryInventory, lower: int, upper: int, target: int
) -> int | None:
    for candidates in (
        inventory.heading,
        inventory.paragraph,
        inventory.sentence,
    ):
        eligible = [value for value in candidates if lower <= value <= upper]
        if eligible:
            return min(eligible, key=lambda value: (abs(value - target), value))
    return None


def _hard_split(character_offsets: tuple[int, ...], start: int, target: int) -> int:
    index = bisect_right(character_offsets, target) - 1
    end = character_offsets[index]
    if end <= start:
        end = character_offsets[index + 1]
    return end


def _context_unit(
    parent: ParentPageEvidence,
    parent_digest: str,
    start: int,
    end: int,
) -> ContextUnit:
    text_bytes = parent.text_bytes[start:end]
    text_digest = hashlib.sha256(text_bytes).hexdigest()
    stable_projection = {
        "content_fingerprint": parent.source_content_fingerprint,
        "end_utf8_byte": end,
        "locator_end": parent.locator_end,
        "locator_kind": parent.locator_kind,
        "locator_start": parent.locator_start,
        "rank_profile_id": "deterministic-unit-rank-v1",
        "start_utf8_byte": start,
        "text_sha256": text_digest,
    }
    encoded = json.dumps(
        stable_projection, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return ContextUnit(
        source_id=parent.source_id,
        source_content_fingerprint=parent.source_content_fingerprint,
        publication_id=parent.publication_id,
        evidence_id=parent.evidence_id,
        locator_kind=parent.locator_kind,
        locator_start=parent.locator_start,
        locator_end=parent.locator_end,
        parent_locator=(
            parent.locator_kind,
            parent.locator_start,
            parent.locator_end,
        ),
        parent_text_sha256=parent_digest,
        start_utf8_byte=start,
        end_utf8_byte=end,
        text_bytes=text_bytes,
        text_sha256=text_digest,
        stable_context_unit_id="sha256:" + hashlib.sha256(encoded).hexdigest(),
        rank_profile_id="deterministic-unit-rank-v1",
    )


def _utf8_offsets(text: str) -> list[int]:
    offsets = [0]
    total = 0
    for character in text:
        total += len(character.encode("utf-8"))
        offsets.append(total)
    return offsets


def _ceiling_division(value: int, divisor: int) -> int:
    return (value + divisor - 1) // divisor
