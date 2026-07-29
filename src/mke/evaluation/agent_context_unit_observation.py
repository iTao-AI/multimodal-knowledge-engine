"""Closed, label-blind observation records for the diagnostic context protocol."""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Literal

from mke.application.evidence_access import EvidenceExcerpt

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_OBSERVATION_STATUSES = {
    "query_policy_hit",
    "query_policy_miss",
    "candidate_hit",
    "candidate_miss",
    "rank_hit",
    "rank_miss",
    "delivery_hit",
    "delivery_miss",
    "output_complete",
    "output_incomplete",
    "exact_read_complete",
    "exact_read_incomplete",
    "provenance_complete",
    "provenance_incomplete",
}


@dataclass(frozen=True)
class ObservationBounds:
    max_sources: int = 8
    max_evidence_items: int = 512
    max_pages: int = 512
    max_source_text_utf8_bytes: int = 16 * 1024 * 1024
    max_candidate_pool: int = 1_000
    max_diagnostic_rank: int = 10
    max_primary_results: int = 5

    def __post_init__(self) -> None:
        if any(type(value) is not int or value < 1 for value in asdict(self).values()):
            raise ValueError("observation bounds are invalid")


def validate_observation_inventory(
    bounds: ObservationBounds,
    *,
    source_count: int,
    evidence_count: int,
    page_count: int,
    source_text_utf8_bytes: int,
    candidate_count: int,
    rank_count: int,
    result_count: int,
) -> None:
    values = (
        (source_count, bounds.max_sources),
        (evidence_count, bounds.max_evidence_items),
        (page_count, bounds.max_pages),
        (source_text_utf8_bytes, bounds.max_source_text_utf8_bytes),
        (candidate_count, bounds.max_candidate_pool),
        (rank_count, bounds.max_diagnostic_rank),
        (result_count, bounds.max_primary_results),
    )
    if any(type(value) is not int or value < 0 or value > limit for value, limit in values):
        raise ValueError("observation capacity exceeded")


@dataclass(frozen=True)
class PortableScoreToken:
    kind: Literal["fts5_rank", "cjk_overlap"]
    primary: str
    secondary: str

    def __post_init__(self) -> None:
        try:
            values = tuple(float.fromhex(value) for value in (self.primary, self.secondary))
        except ValueError:
            values = ()
        if len(values) != 2 or not all(math.isfinite(value) for value in values):
            raise ValueError("score token is invalid")
        if tuple(value.hex() for value in values) != (self.primary, self.secondary):
            raise ValueError("score token is invalid")


@dataclass(frozen=True)
class PortableObservationItem:
    content_fingerprint: str
    locator_kind: Literal["page", "timestamp_ms"]
    locator_start: int
    locator_end: int
    text_sha256: str
    route: Literal["fts5", "cjk-active-scan-overlap-v1"]
    rank: int
    score: PortableScoreToken
    hints: tuple[str, ...]
    excerpt: EvidenceExcerpt
    exact_read_sha256: str
    original_utf8_bytes: int
    excerpt_utf8_bytes: int
    exact_read_utf8_bytes: int

    def __post_init__(self) -> None:
        if any(
            _SHA256.fullmatch(value) is None
            for value in (
                self.content_fingerprint,
                self.text_sha256,
                self.exact_read_sha256,
            )
        ):
            raise ValueError("observation digest is invalid")
        valid_locator = (
            self.locator_kind == "page"
            and self.locator_start > 0
            and self.locator_end == self.locator_start
            or self.locator_kind == "timestamp_ms"
            and self.locator_start >= 0
            and self.locator_end > self.locator_start
        )
        if not valid_locator or self.rank < 1:
            raise ValueError("observation locator or rank is invalid")
        if self.excerpt_utf8_bytes != len(self.excerpt.text.encode("utf-8")):
            raise ValueError("observation byte accounting is invalid")
        if (
            min(
                self.original_utf8_bytes,
                self.excerpt_utf8_bytes,
                self.exact_read_utf8_bytes,
            )
            < 1
            or self.excerpt_utf8_bytes > self.original_utf8_bytes
            or self.exact_read_utf8_bytes != self.original_utf8_bytes
            or self.text_sha256 != self.exact_read_sha256
        ):
            raise ValueError("observation byte accounting is invalid")
        if not self.hints or len(set(self.hints)) != len(self.hints):
            raise ValueError("observation hints are invalid")


@dataclass(frozen=True)
class PortableObservation:
    query_id: str
    query_text: str
    expected_route: str
    profile_identity: str
    statuses: tuple[str, ...]
    items: tuple[PortableObservationItem, ...]
    candidate_count: int
    selected_count: int
    delivered_utf8_bytes: int

    def __post_init__(self) -> None:
        if not all(
            value
            for value in (
                self.query_id,
                self.query_text,
                self.expected_route,
                self.profile_identity,
            )
        ):
            raise ValueError("observation contract identity is invalid")
        if self.expected_route not in {"fts5", "cjk-active-scan-overlap-v1"}:
            raise ValueError("observation route is invalid")
        if len(self.statuses) != 7 or not set(self.statuses) <= _OBSERVATION_STATUSES:
            raise ValueError("observation status inventory is invalid")
        if (
            self.selected_count != len(self.items)
            or self.candidate_count < self.selected_count
            or self.delivered_utf8_bytes
            != sum(item.excerpt_utf8_bytes for item in self.items)
        ):
            raise ValueError("observation inventory is invalid")


@dataclass(frozen=True)
class AuthorityObservation:
    portable: PortableObservation
    source_ids: tuple[str, ...]
    publication_ids: tuple[str, ...]
    run_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        cardinalities = {
            len(self.portable.items),
            len(self.source_ids),
            len(self.publication_ids),
            len(self.run_ids),
            len(self.evidence_ids),
        }
        if len(cardinalities) != 1:
            raise ValueError("authority observation inventory is invalid")


@dataclass(frozen=True)
class PortableObservationSeal:
    bytes: bytes
    sha256: str


def seal_portable_observations(
    observations: tuple[PortableObservation, ...],
) -> PortableObservationSeal:
    if not observations or len({item.query_id for item in observations}) != len(
        observations
    ):
        raise ValueError("portable observation inventory is invalid")
    ordered = tuple(sorted(observations, key=lambda item: item.query_id.encode("utf-8")))
    payload = {
        "observations": [asdict(item) for item in ordered],
        "schema_version": "mke.agent_context_unit_observation.v2",
    }
    encoded = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")
    return PortableObservationSeal(encoded, f"sha256:{sha256(encoded).hexdigest()}")
