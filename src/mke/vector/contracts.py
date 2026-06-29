"""Provider-neutral vector projection values and identity derivation."""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from mke.embeddings.contracts import (
    EMBEDDING_DIMENSION,
    EmbeddedEvidence,
    EmbeddingBatch,
    EmbeddingValidationError,
    validate_embedding_vector,
)

CANONICAL_TOP_K = 10


class VectorProjectionError(RuntimeError):
    """Stable projection integrity or compatibility failure."""

    def __init__(self, cause: str, next_step: str = "rebuild_vector_projection") -> None:
        super().__init__(cause)
        self.cause = cause
        self.next_step = next_step


@dataclass(frozen=True)
class ProjectionIdentity:
    adapter_id: str
    model_fingerprint: str
    dimension: int
    row_count: int
    locator_digest: str
    source_text_digest: str
    vector_digest: str


@dataclass(frozen=True)
class RankedEvidence:
    stable_locator_id: str
    rank: int
    score: float
    adapter_id: str

    def __post_init__(self) -> None:
        if type(self.stable_locator_id) is not str or not self.stable_locator_id:
            raise VectorProjectionError("ranked Evidence locator is invalid")
        if type(self.rank) is not int or self.rank <= 0:
            raise VectorProjectionError("ranked Evidence rank is invalid")
        if type(self.score) is not float or not math.isfinite(self.score):
            raise VectorProjectionError("ranked Evidence score is invalid")
        if self.score < -1.0 or self.score > 1.0:
            raise VectorProjectionError("ranked Evidence score is invalid")
        if type(self.adapter_id) is not str or not self.adapter_id:
            raise VectorProjectionError("vector adapter identity is invalid")


class VectorProjection(Protocol):
    def replace(self, batch: EmbeddingBatch) -> ProjectionIdentity: ...

    def validate(self, expected: ProjectionIdentity) -> None: ...

    def search(
        self, query_vector: tuple[float, ...], *, top_k: int
    ) -> tuple[RankedEvidence, ...]: ...

    def close(self) -> None: ...


def build_projection_identity(
    batch: EmbeddingBatch,
    *,
    adapter_id: str,
) -> ProjectionIdentity:
    if type(adapter_id) is not str or not adapter_id:
        raise VectorProjectionError("vector adapter identity is invalid")
    if type(batch.model_fingerprint) is not str or not batch.model_fingerprint:
        raise VectorProjectionError("embedding model fingerprint is invalid")
    ordered = _validated_evidence(batch.evidence)
    locator_values = [item.stable_locator_id for item in ordered]
    source_digests = [_source_text_digest(locator) for locator in locator_values]
    vector_hash = sha256()
    for item in ordered:
        vector_hash.update(item.stable_locator_id.encode("utf-8"))
        vector_hash.update(b"\0")
        vector_hash.update(struct.pack(f"<{EMBEDDING_DIMENSION}f", *item.vector))
    return ProjectionIdentity(
        adapter_id=adapter_id,
        model_fingerprint=batch.model_fingerprint,
        dimension=EMBEDDING_DIMENSION,
        row_count=len(ordered),
        locator_digest=_digest_json(locator_values),
        source_text_digest=_digest_json(source_digests),
        vector_digest="sha256:" + vector_hash.hexdigest(),
    )


def validated_projection_rows(
    batch: EmbeddingBatch,
) -> tuple[EmbeddedEvidence, ...]:
    return _validated_evidence(batch.evidence)


def rank_portable_scores(
    scores: tuple[tuple[str, float], ...],
    *,
    adapter_id: str,
    top_k: int,
) -> tuple[RankedEvidence, ...]:
    if type(top_k) is not int or top_k != CANONICAL_TOP_K:
        raise VectorProjectionError("top_k must equal 10 for the canonical dense candidate")
    portable: list[tuple[str, float]] = []
    for locator, raw_score in scores:
        if type(locator) is not str or not locator:
            raise VectorProjectionError("ranked Evidence locator is invalid")
        if type(raw_score) is not float or not math.isfinite(raw_score):
            raise VectorProjectionError("vector score is invalid")
        if raw_score < -1.000001 or raw_score > 1.000001:
            raise VectorProjectionError("vector score is invalid")
        score = round(min(1.0, max(-1.0, raw_score)), 6)
        portable.append((locator, 0.0 if score == 0.0 else score))
    portable.sort(key=lambda item: (-item[1], item[0]))
    return tuple(
        RankedEvidence(locator, rank, score, adapter_id)
        for rank, (locator, score) in enumerate(portable[:top_k], start=1)
    )


def _validated_evidence(
    evidence: tuple[EmbeddedEvidence, ...],
) -> tuple[EmbeddedEvidence, ...]:
    if type(evidence) is not tuple or not evidence:
        raise VectorProjectionError("vector projection inventory is incomplete")
    ordered = tuple(sorted(evidence, key=lambda item: item.stable_locator_id))
    locators = tuple(item.stable_locator_id for item in ordered)
    if any(type(locator) is not str or not locator for locator in locators):
        raise VectorProjectionError("vector projection locator is invalid")
    if len(set(locators)) != len(locators):
        raise VectorProjectionError("vector projection locator inventory is not unique")
    try:
        for item in ordered:
            validate_embedding_vector(item.vector, output_dtype="float32")
    except EmbeddingValidationError as error:
        raise VectorProjectionError(str(error)) from error
    return ordered


def _source_text_digest(stable_locator_id: str) -> str:
    digest = stable_locator_id.rsplit("|", 1)[-1]
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise VectorProjectionError("vector projection source text identity is invalid")
    return digest


def _digest_json(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return "sha256:" + sha256(canonical.encode("utf-8")).hexdigest()
