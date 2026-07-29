"""Deterministic route-local ranking over evaluation-only ContextUnit rows."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import asdict, dataclass
from typing import Literal

from mke.evaluation.agent_context_unit_segmentation import ContextUnit
from mke.retrieval.cjk_active_scan import (
    CJK_ACTIVE_SCAN_PARAMETERS,
    compile_cjk_overlap_terms,
)
from mke.retrieval.query_policy import compile_fts5_query_diagnostic

_PREFIXED_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_BARE_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_O1_RANK_PROFILE_ID = "deterministic-unit-rank-v1"


@dataclass(frozen=True)
class RankingBounds:
    max_projection_rows: int = 16_384
    max_projection_utf8_bytes: int = 32 * 1024 * 1024
    max_candidate_pool: int = 1_000
    max_diagnostic_rank: int = 10
    max_primary_results: int = 5

    def __post_init__(self) -> None:
        values = (
            self.max_projection_rows,
            self.max_projection_utf8_bytes,
            self.max_candidate_pool,
            self.max_diagnostic_rank,
            self.max_primary_results,
        )
        if (
            any(type(value) is not int or value < 1 for value in values)
            or self.max_primary_results > self.max_diagnostic_rank
        ):
            raise ValueError("ranking bounds are invalid")


DEFAULT_RANKING_BOUNDS = RankingBounds()


@dataclass(frozen=True)
class UnitProjectionRow:
    stable_context_unit_id: str
    source_content_fingerprint: str
    parent_locator: tuple[Literal["page"], int, int]
    parent_text_sha256: str
    start_utf8_byte: int
    end_utf8_byte: int
    text_bytes: bytes
    text_sha256: str
    rank_profile_id: str


@dataclass(frozen=True)
class FtsUnitScore:
    arm: Literal["fts"]
    rank_score_hex: str
    bm25_score_hex: str

    def __post_init__(self) -> None:
        if (
            self.arm != "fts"
            or not _canonical_finite_float_hex(self.rank_score_hex)
            or not _canonical_finite_float_hex(self.bm25_score_hex)
            or self.rank_score_hex != self.bm25_score_hex
        ):
            raise ValueError("FTS score authority is invalid")


@dataclass(frozen=True)
class CjkUnitScore:
    arm: Literal["cjk"]
    overlap_count: int
    query_term_count: int
    overlap_ratio_hex: str
    matched_terms: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            self.arm != "cjk"
            or type(self.overlap_count) is not int
            or self.overlap_count < 1
            or type(self.query_term_count) is not int
            or self.query_term_count < self.overlap_count
            or not _canonical_finite_float_hex(self.overlap_ratio_hex)
            or not 0.0 < float.fromhex(self.overlap_ratio_hex) <= 1.0
            or float.fromhex(self.overlap_ratio_hex)
            != self.overlap_count / self.query_term_count
            or type(self.matched_terms) is not tuple
            or len(self.matched_terms) != self.overlap_count
            or not self.matched_terms
            or len(set(self.matched_terms)) != len(self.matched_terms)
            or any(type(term) is not str or not term for term in self.matched_terms)
        ):
            raise ValueError("CJK score authority is invalid")


UnitScore = FtsUnitScore | CjkUnitScore


@dataclass(frozen=True)
class RankedUnit:
    stable_context_unit_id: str
    source_content_fingerprint: str
    parent_locator: tuple[Literal["page"], int, int]
    start_utf8_byte: int
    end_utf8_byte: int
    diagnostic_rank: int
    parent_collapsed_rank: int
    score: UnitScore


@dataclass(frozen=True)
class CandidateExpansion:
    unit_candidate_count: int
    unique_parent_count: int
    ratio_hex: str

    def __post_init__(self) -> None:
        if (
            type(self.unit_candidate_count) is not int
            or type(self.unique_parent_count) is not int
            or self.unit_candidate_count < 0
            or self.unique_parent_count < 0
            or self.unique_parent_count > self.unit_candidate_count
            or not _canonical_finite_float_hex(self.ratio_hex)
            or (
                self.unit_candidate_count == 0
                and (
                    self.unique_parent_count != 0
                    or float.fromhex(self.ratio_hex) != 0.0
                )
            )
            or (
                self.unit_candidate_count > 0
                and (
                    self.unique_parent_count == 0
                    or float.fromhex(self.ratio_hex)
                    != self.unit_candidate_count / self.unique_parent_count
                )
            )
        ):
            raise ValueError("candidate expansion authority is invalid")


@dataclass(frozen=True)
class UnitRankResult:
    query_id: str
    route: Literal["fts", "cjk"]
    rank_profile_id: str
    candidate_count: int
    unique_parent_count: int
    candidate_expansion: CandidateExpansion
    diagnostic: tuple[RankedUnit, ...]
    primary_stable_context_unit_ids: tuple[str, ...]

    def portable_bytes(self) -> bytes:
        return (
            json.dumps(
                asdict(self),
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")


def build_unit_projection(
    units: tuple[ContextUnit, ...],
    *,
    bounds: RankingBounds = DEFAULT_RANKING_BOUNDS,
) -> tuple[UnitProjectionRow, ...]:
    if len(units) > bounds.max_projection_rows:
        raise ValueError("projection row capacity exceeded")
    projection_utf8_bytes = sum(len(unit.text_bytes) for unit in units)
    if projection_utf8_bytes > bounds.max_projection_utf8_bytes:
        raise ValueError("projection byte capacity exceeded")
    if not units:
        raise ValueError("projection inventory is invalid")

    rows = tuple(_projection_row(unit) for unit in units)
    stable_ids = tuple(row.stable_context_unit_id for row in rows)
    if len(stable_ids) != len(set(stable_ids)):
        raise ValueError("projection unit identity is duplicated")
    _validate_parent_coverage(rows)
    return tuple(sorted(rows, key=_stable_row_key))


def rank_fts_units(
    rows: tuple[UnitProjectionRow, ...],
    *,
    query_id: str,
    query_text: str,
    bounds: RankingBounds = DEFAULT_RANKING_BOUNDS,
) -> UnitRankResult:
    _validate_rank_request(rows, query_id, query_text, bounds)
    compiled = compile_fts5_query_diagnostic(query_text).compiled_query
    if not compiled:
        return _rank_result(
            query_id=query_id,
            route="fts",
            rank_profile_id=_O1_RANK_PROFILE_ID,
            ranked=(),
            bounds=bounds,
        )

    by_id = {row.stable_context_unit_id: row for row in rows}
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE unit_projection_fts "
            "USING fts5(stable_context_unit_id UNINDEXED, text)"
        )
        connection.executemany(
            "INSERT INTO unit_projection_fts(stable_context_unit_id, text) "
            "VALUES (?, ?)",
            (
                (row.stable_context_unit_id, row.text_bytes.decode("utf-8"))
                for row in rows
            ),
        )
        candidate_count = int(
            connection.execute(
                "SELECT count(*) FROM unit_projection_fts "
                "WHERE unit_projection_fts MATCH ?",
                (compiled,),
            ).fetchone()[0]
        )
        if candidate_count > bounds.max_candidate_pool:
            raise ValueError("candidate pool capacity exceeded")
        scored = tuple(
            (
                by_id[str(stable_id)],
                float(rank_score),
                float(bm25_score),
            )
            for stable_id, rank_score, bm25_score in connection.execute(
                "SELECT stable_context_unit_id, rank, "
                "bm25(unit_projection_fts) "
                "FROM unit_projection_fts "
                "WHERE unit_projection_fts MATCH ?",
                (compiled,),
            )
        )
    finally:
        connection.close()

    ordered = tuple(
        sorted(scored, key=lambda item: (item[1], _fts_tie_key(item[0])))
    )
    return _rank_result(
        query_id=query_id,
        route="fts",
        rank_profile_id=_O1_RANK_PROFILE_ID,
        ranked=tuple(
            (
                row,
                FtsUnitScore(
                    arm="fts",
                    rank_score_hex=rank_score.hex(),
                    bm25_score_hex=bm25_score.hex(),
                ),
            )
            for row, rank_score, bm25_score in ordered
        ),
        bounds=bounds,
    )


def compile_cjk_overlap_terms_for_units(query_text: str) -> tuple[str, ...]:
    return compile_cjk_overlap_terms(query_text, require_terms=True).terms


def rank_cjk_units(
    rows: tuple[UnitProjectionRow, ...],
    *,
    query_id: str,
    query_text: str,
    bounds: RankingBounds = DEFAULT_RANKING_BOUNDS,
) -> UnitRankResult:
    _validate_rank_request(rows, query_id, query_text, bounds)
    terms = compile_cjk_overlap_terms_for_units(query_text)
    scored: list[tuple[UnitProjectionRow, CjkUnitScore]] = []
    eligible_count = 0
    for row in rows:
        normalized_text = "".join(
            character
            for character in row.text_bytes.decode("utf-8").casefold()
            if not character.isspace()
        )
        matched_terms = tuple(term for term in terms if term in normalized_text)
        overlap_count = len(matched_terms)
        overlap_ratio = overlap_count / len(terms)
        if (
            overlap_count < CJK_ACTIVE_SCAN_PARAMETERS.minimum_overlap_count
            or overlap_ratio < CJK_ACTIVE_SCAN_PARAMETERS.minimum_overlap_ratio
        ):
            continue
        eligible_count += 1
        if eligible_count > bounds.max_candidate_pool:
            raise ValueError("candidate pool capacity exceeded")
        scored.append(
            (
                row,
                CjkUnitScore(
                    arm="cjk",
                    overlap_count=overlap_count,
                    query_term_count=len(terms),
                    overlap_ratio_hex=overlap_ratio.hex(),
                    matched_terms=matched_terms,
                ),
            )
        )
    ordered = tuple(
        sorted(
            scored,
            key=lambda item: (
                -item[1].overlap_count,
                -float.fromhex(item[1].overlap_ratio_hex),
                _stable_row_key(item[0]),
            ),
        )
    )
    return _rank_result(
        query_id=query_id,
        route="cjk",
        rank_profile_id=_O1_RANK_PROFILE_ID,
        ranked=ordered,
        bounds=bounds,
    )


def compare_arm_local_scores(left: UnitScore, right: UnitScore) -> int:
    if left.arm != right.arm:
        raise ValueError("cross-arm score comparison is forbidden")
    if isinstance(left, FtsUnitScore) and isinstance(right, FtsUnitScore):
        left_key = (float.fromhex(left.rank_score_hex),)
        right_key = (float.fromhex(right.rank_score_hex),)
    elif isinstance(left, CjkUnitScore) and isinstance(right, CjkUnitScore):
        left_key = (-left.overlap_count, -float.fromhex(left.overlap_ratio_hex))
        right_key = (-right.overlap_count, -float.fromhex(right.overlap_ratio_hex))
    else:
        raise ValueError("score authority is invalid")
    return (left_key > right_key) - (left_key < right_key)


def _projection_row(unit: ContextUnit) -> UnitProjectionRow:
    if type(unit) is not ContextUnit:
        raise ValueError("projection row authority is invalid")
    text_digest = hashlib.sha256(unit.text_bytes).hexdigest()
    stable_payload = {
        "content_fingerprint": unit.source_content_fingerprint,
        "end_utf8_byte": unit.end_utf8_byte,
        "locator_end": unit.locator_end,
        "locator_kind": unit.locator_kind,
        "locator_start": unit.locator_start,
        "rank_profile_id": unit.rank_profile_id,
        "start_utf8_byte": unit.start_utf8_byte,
        "text_sha256": text_digest,
    }
    stable_id = "sha256:" + hashlib.sha256(
        json.dumps(
            stable_payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    if (
        unit.parent_locator
        != (unit.locator_kind, unit.locator_start, unit.locator_end)
        or unit.locator_kind != "page"
        or unit.locator_start < 1
        or unit.locator_end != unit.locator_start
        or unit.start_utf8_byte < 0
        or unit.end_utf8_byte <= unit.start_utf8_byte
        or unit.end_utf8_byte - unit.start_utf8_byte != len(unit.text_bytes)
        or unit.text_sha256 != text_digest
        or unit.stable_context_unit_id != stable_id
        or unit.rank_profile_id != _O1_RANK_PROFILE_ID
    ):
        raise ValueError("projection row authority is invalid")
    try:
        unit.text_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("projection row authority is invalid") from error
    return UnitProjectionRow(
        stable_context_unit_id=unit.stable_context_unit_id,
        source_content_fingerprint=unit.source_content_fingerprint,
        parent_locator=unit.parent_locator,
        parent_text_sha256=unit.parent_text_sha256,
        start_utf8_byte=unit.start_utf8_byte,
        end_utf8_byte=unit.end_utf8_byte,
        text_bytes=unit.text_bytes,
        text_sha256=unit.text_sha256,
        rank_profile_id=unit.rank_profile_id,
    )


def _validate_parent_coverage(rows: tuple[UnitProjectionRow, ...]) -> None:
    grouped: dict[
        tuple[str, tuple[Literal["page"], int, int], str],
        list[UnitProjectionRow],
    ] = {}
    for row in rows:
        key = (
            row.source_content_fingerprint,
            row.parent_locator,
            row.parent_text_sha256,
        )
        grouped.setdefault(key, []).append(row)
    for key_rows in grouped.values():
        ordered = sorted(key_rows, key=lambda row: row.start_utf8_byte)
        if (
            ordered[0].start_utf8_byte != 0
            or any(
                left.end_utf8_byte != right.start_utf8_byte
                for left, right in zip(ordered, ordered[1:], strict=False)
            )
            or hashlib.sha256(
                b"".join(row.text_bytes for row in ordered)
            ).hexdigest()
            != ordered[0].parent_text_sha256
        ):
            raise ValueError("projection parent coverage is invalid")


def _validate_rank_request(
    rows: tuple[UnitProjectionRow, ...],
    query_id: str,
    query_text: str,
    bounds: RankingBounds,
) -> None:
    if (
        not rows
        or type(query_id) is not str
        or not query_id
        or type(query_text) is not str
        or not query_text
        or len(rows) > bounds.max_projection_rows
        or sum(len(row.text_bytes) for row in rows)
        > bounds.max_projection_utf8_bytes
    ):
        raise ValueError("ranking request authority is invalid")
    if len({row.stable_context_unit_id for row in rows}) != len(rows):
        raise ValueError("projection unit identity is duplicated")
    for row in rows:
        _validate_projection_row(row)
    _validate_parent_coverage(rows)


def _rank_result(
    *,
    query_id: str,
    route: Literal["fts", "cjk"],
    rank_profile_id: str,
    ranked: tuple[tuple[UnitProjectionRow, UnitScore], ...],
    bounds: RankingBounds,
) -> UnitRankResult:
    parent_ranks: dict[tuple[str, tuple[Literal["page"], int, int]], int] = {}
    ranked_items: list[RankedUnit] = []
    for diagnostic_rank, (row, score) in enumerate(ranked, start=1):
        parent_key = (row.source_content_fingerprint, row.parent_locator)
        if parent_key not in parent_ranks:
            parent_ranks[parent_key] = len(parent_ranks) + 1
        if diagnostic_rank <= bounds.max_diagnostic_rank:
            ranked_items.append(
                RankedUnit(
                    stable_context_unit_id=row.stable_context_unit_id,
                    source_content_fingerprint=row.source_content_fingerprint,
                    parent_locator=row.parent_locator,
                    start_utf8_byte=row.start_utf8_byte,
                    end_utf8_byte=row.end_utf8_byte,
                    diagnostic_rank=diagnostic_rank,
                    parent_collapsed_rank=parent_ranks[parent_key],
                    score=score,
                )
            )
    candidate_count = len(ranked)
    unique_parent_count = len(parent_ranks)
    ratio = candidate_count / unique_parent_count if candidate_count else 0.0
    diagnostic = tuple(ranked_items)
    return UnitRankResult(
        query_id=query_id,
        route=route,
        rank_profile_id=rank_profile_id,
        candidate_count=candidate_count,
        unique_parent_count=unique_parent_count,
        candidate_expansion=CandidateExpansion(
            unit_candidate_count=candidate_count,
            unique_parent_count=unique_parent_count,
            ratio_hex=ratio.hex(),
        ),
        diagnostic=diagnostic,
        primary_stable_context_unit_ids=tuple(
            item.stable_context_unit_id
            for item in diagnostic[: bounds.max_primary_results]
        ),
    )


def _stable_row_key(
    row: UnitProjectionRow,
) -> tuple[str, str, int, int, int, int, str]:
    return (
        row.source_content_fingerprint,
        row.parent_locator[0],
        row.parent_locator[1],
        row.parent_locator[2],
        row.start_utf8_byte,
        row.end_utf8_byte,
        row.stable_context_unit_id,
    )


def _fts_tie_key(
    row: UnitProjectionRow,
) -> tuple[int, str, int, int, int, str, str]:
    return (
        row.parent_locator[1],
        row.parent_locator[0],
        row.parent_locator[2],
        row.start_utf8_byte,
        row.end_utf8_byte,
        row.source_content_fingerprint,
        row.stable_context_unit_id,
    )


def _validate_projection_row(row: UnitProjectionRow) -> None:
    if (
        type(row) is not UnitProjectionRow
        or type(row.stable_context_unit_id) is not str
        or type(row.source_content_fingerprint) is not str
        or type(row.parent_text_sha256) is not str
        or type(row.text_sha256) is not str
        or type(row.parent_locator) is not tuple
        or len(row.parent_locator) != 3
        or type(row.parent_locator[0]) is not str
        or type(row.parent_locator[1]) is not int
        or type(row.parent_locator[2]) is not int
        or type(row.start_utf8_byte) is not int
        or type(row.end_utf8_byte) is not int
        or type(row.text_bytes) is not bytes
        or type(row.rank_profile_id) is not str
    ):
        raise ValueError("projection row authority is invalid")
    if (
        _PREFIXED_SHA256.fullmatch(row.stable_context_unit_id) is None
        or _PREFIXED_SHA256.fullmatch(row.source_content_fingerprint) is None
        or _BARE_SHA256.fullmatch(row.parent_text_sha256) is None
        or _BARE_SHA256.fullmatch(row.text_sha256) is None
        or row.parent_locator[0] != "page"
        or row.parent_locator[1] < 1
        or row.parent_locator[2] != row.parent_locator[1]
        or row.start_utf8_byte < 0
        or row.end_utf8_byte <= row.start_utf8_byte
        or row.end_utf8_byte - row.start_utf8_byte != len(row.text_bytes)
        or row.text_sha256 != hashlib.sha256(row.text_bytes).hexdigest()
        or row.rank_profile_id != _O1_RANK_PROFILE_ID
        or row.stable_context_unit_id != _stable_unit_id(row)
    ):
        raise ValueError("projection row authority is invalid")
    try:
        row.text_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("projection row authority is invalid") from error


def _stable_unit_id(row: UnitProjectionRow) -> str:
    stable_payload = {
        "content_fingerprint": row.source_content_fingerprint,
        "end_utf8_byte": row.end_utf8_byte,
        "locator_end": row.parent_locator[2],
        "locator_kind": row.parent_locator[0],
        "locator_start": row.parent_locator[1],
        "rank_profile_id": row.rank_profile_id,
        "start_utf8_byte": row.start_utf8_byte,
        "text_sha256": row.text_sha256,
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(
            stable_payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _canonical_finite_float_hex(value: str) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = float.fromhex(value)
    except ValueError:
        return False
    return math.isfinite(parsed) and parsed.hex() == value
