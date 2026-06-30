"""Pure rank-only Reciprocal Rank Fusion for E3-D evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


class RrfFusionError(ValueError):
    """Raised when RRF input or derived output is invalid."""


@dataclass(frozen=True)
class RrfCandidateConfig:
    candidate_id: str
    candidate_revision: int
    k: int
    lexical_weight: float
    dense_weight: float
    input_depth: int
    output_depth: int
    score_decimals: int

    @classmethod
    def default(cls) -> RrfCandidateConfig:
        return cls(
            candidate_id="cjk-active-scan-qwen3-rrf-v1",
            candidate_revision=1,
            k=60,
            lexical_weight=1.0,
            dense_weight=1.0,
            input_depth=10,
            output_depth=10,
            score_decimals=12,
        )


@dataclass(frozen=True)
class ArmRankedResult:
    arm_id: str
    stable_locator_id: str
    document_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    source_text_digest: str
    rank: int


@dataclass(frozen=True)
class FusedRrfResult:
    query_id: str
    stable_locator_id: str
    document_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    source_text_digest: str
    rank: int
    portable_score: str
    arms: tuple[str, ...]
    lexical_rank: int | None
    dense_rank: int | None
    best_individual_rank: int


@dataclass(frozen=True)
class _Accumulator:
    row: ArmRankedResult
    lexical_rank: int | None
    dense_rank: int | None
    score: Decimal


def fuse_ranked_results(
    *,
    query_id: str,
    lexical: tuple[ArmRankedResult, ...],
    dense: tuple[ArmRankedResult, ...],
    config: RrfCandidateConfig,
) -> tuple[FusedRrfResult, ...]:
    _validate_query_id(query_id)
    _validate_config(config)
    accumulators: dict[tuple[str, str], _Accumulator] = {}

    for arm_name, rows, weight in (
        ("lexical", lexical, config.lexical_weight),
        ("dense", dense, config.dense_weight),
    ):
        seen: set[tuple[str, str]] = set()
        for row in rows[: config.input_depth]:
            _validate_row(row, expected_arm=arm_name)
            key = (row.stable_locator_id, row.source_text_digest)
            if key in seen:
                raise RrfFusionError(f"duplicate {arm_name} locator")
            seen.add(key)
            contribution = _score_contribution(weight, config.k, row.rank)
            current = accumulators.get(key)
            if current is None:
                accumulators[key] = _Accumulator(
                    row=row,
                    lexical_rank=row.rank if arm_name == "lexical" else None,
                    dense_rank=row.rank if arm_name == "dense" else None,
                    score=contribution,
                )
                continue
            if _locator_identity(current.row) != _locator_identity(row):
                raise RrfFusionError("duplicate locator identity mismatch")
            accumulators[key] = _Accumulator(
                row=current.row,
                lexical_rank=(
                    row.rank if arm_name == "lexical" else current.lexical_rank
                ),
                dense_rank=row.rank if arm_name == "dense" else current.dense_rank,
                score=current.score + contribution,
            )

    quant = Decimal("1").scaleb(-config.score_decimals)
    sorted_rows = sorted(
        accumulators.values(),
        key=lambda item: (
            -item.score,
            -_arm_count(item),
            _best_rank(item),
            _missing_last(item.lexical_rank),
            _missing_last(item.dense_rank),
            item.row.stable_locator_id,
        ),
    )
    fused: list[FusedRrfResult] = []
    for rank, item in enumerate(sorted_rows[: config.output_depth], start=1):
        row = item.row
        fused.append(
            FusedRrfResult(
                query_id=query_id,
                stable_locator_id=row.stable_locator_id,
                document_id=row.document_id,
                locator_kind=row.locator_kind,
                locator_start=row.locator_start,
                locator_end=row.locator_end,
                source_text_digest=row.source_text_digest,
                rank=rank,
                portable_score=str(item.score.quantize(quant, ROUND_HALF_UP)),
                arms=_arms(item),
                lexical_rank=item.lexical_rank,
                dense_rank=item.dense_rank,
                best_individual_rank=_best_rank(item),
            )
        )
    return tuple(fused)


def _validate_query_id(query_id: str) -> None:
    if type(query_id) is not str or not query_id:
        raise RrfFusionError("query_id must be a non-empty string")


def _validate_config(config: RrfCandidateConfig) -> None:
    for name in ("candidate_id",):
        value = getattr(config, name)
        if type(value) is not str or not value:
            raise RrfFusionError(f"{name} is invalid")
    for name in (
        "candidate_revision",
        "k",
        "input_depth",
        "output_depth",
        "score_decimals",
    ):
        value = getattr(config, name)
        if type(value) is not int or value <= 0:
            raise RrfFusionError(f"{name} is invalid")
    for name in ("lexical_weight", "dense_weight"):
        value = getattr(config, name)
        if type(value) not in {float, int} or value <= 0:
            raise RrfFusionError(f"{name} is invalid")


def _validate_row(row: ArmRankedResult, *, expected_arm: str) -> None:
    if row.arm_id != expected_arm:
        raise RrfFusionError("arm_id is invalid")
    for field in (
        "stable_locator_id",
        "document_id",
        "locator_kind",
        "source_text_digest",
    ):
        value = getattr(row, field)
        if type(value) is not str or not value:
            raise RrfFusionError(f"{field} is invalid")
    if type(row.locator_start) is not int or type(row.locator_end) is not int:
        raise RrfFusionError("locator bounds are invalid")
    if row.locator_start <= 0 or row.locator_end < row.locator_start:
        raise RrfFusionError("locator bounds are invalid")
    if type(row.rank) is not int or row.rank <= 0:
        raise RrfFusionError("rank is invalid")


def _score_contribution(weight: float, k: int, rank: int) -> Decimal:
    return Decimal(str(weight)) / Decimal(k + rank)


def _locator_identity(
    row: ArmRankedResult,
) -> tuple[str, str, int, int, str]:
    return (
        row.document_id,
        row.locator_kind,
        row.locator_start,
        row.locator_end,
        row.source_text_digest,
    )


def _arm_count(item: _Accumulator) -> int:
    return int(item.lexical_rank is not None) + int(item.dense_rank is not None)


def _best_rank(item: _Accumulator) -> int:
    ranks = tuple(
        rank for rank in (item.lexical_rank, item.dense_rank) if rank is not None
    )
    return min(ranks)


def _missing_last(rank: int | None) -> int:
    return rank if rank is not None else 999999


def _arms(item: _Accumulator) -> tuple[str, ...]:
    arms: list[str] = []
    if item.dense_rank is not None:
        arms.append("dense")
    if item.lexical_rank is not None:
        arms.append("lexical")
    return tuple(arms)
