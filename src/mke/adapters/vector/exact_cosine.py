"""Independent project-owned exact-cosine correctness oracle."""

from __future__ import annotations

import math

from mke.embeddings.contracts import EmbeddingBatch, validate_embedding_vector
from mke.vector.contracts import (
    ProjectionIdentity,
    RankedEvidence,
    VectorProjectionError,
    build_projection_identity,
    rank_portable_scores,
    validated_projection_rows,
)

EXACT_COSINE_ADAPTER_ID = "exact-cosine-v1"


class ExactCosineProjection:
    def __init__(self) -> None:
        self._batch: EmbeddingBatch | None = None
        self._identity: ProjectionIdentity | None = None

    def replace(self, batch: EmbeddingBatch) -> ProjectionIdentity:
        ordered = validated_projection_rows(batch)
        candidate = EmbeddingBatch(batch.model_fingerprint, ordered)
        identity = build_projection_identity(candidate, adapter_id=EXACT_COSINE_ADAPTER_ID)
        self._batch = candidate
        self._identity = identity
        return identity

    def validate(self, expected: ProjectionIdentity) -> None:
        if self._batch is None or self._identity is None:
            raise VectorProjectionError("vector projection is not active")
        observed = build_projection_identity(
            self._batch,
            adapter_id=EXACT_COSINE_ADAPTER_ID,
        )
        if observed != self._identity or observed != expected:
            raise VectorProjectionError("vector projection identity mismatch")

    def search(
        self, query_vector: tuple[float, ...], *, top_k: int
    ) -> tuple[RankedEvidence, ...]:
        if self._batch is None:
            raise VectorProjectionError("vector projection is not active")
        try:
            query = validate_embedding_vector(query_vector, output_dtype="float32")
        except ValueError as error:
            raise VectorProjectionError(str(error)) from error
        scores = tuple(
            (
                item.stable_locator_id,
                float(
                    math.fsum(
                        left * right
                        for left, right in zip(query, item.vector, strict=True)
                    )
                ),
            )
            for item in self._batch.evidence
        )
        return rank_portable_scores(
            scores,
            adapter_id=EXACT_COSINE_ADAPTER_ID,
            top_k=top_k,
        )

    def close(self) -> None:
        self._batch = None
        self._identity = None
