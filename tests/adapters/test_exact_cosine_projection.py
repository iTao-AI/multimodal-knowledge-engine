from __future__ import annotations

import math
from hashlib import sha256

import pytest

from mke.adapters.vector.exact_cosine import ExactCosineProjection
from mke.embeddings.contracts import (
    EMBEDDING_DIMENSION,
    EmbeddedEvidence,
    EmbeddingBatch,
    EmbeddingEvidenceInput,
    build_embedding_batch,
)
from mke.vector.contracts import VectorProjectionError


def _input(locator: str, page: int) -> EmbeddingEvidenceInput:
    text = f"text-{locator}"
    return EmbeddingEvidenceInput(
        document_id=locator,
        locator_kind="page",
        locator_start=page,
        locator_end=page,
        text=text,
        text_sha256=sha256(text.encode("utf-8")).hexdigest(),
        runtime_evidence_id=f"evidence-{locator}",
        runtime_publication_id="publication-1",
    )


def _basis(index: int, sign: float = 1.0) -> tuple[float, ...]:
    return tuple(sign if position == index else 0.0 for position in range(EMBEDDING_DIMENSION))


def _score_vector(score: float) -> tuple[float, ...]:
    return (score, math.sqrt(1.0 - score * score), *([0.0] * (EMBEDDING_DIMENSION - 2)))


def _batch(records: list[tuple[str, tuple[float, ...]]]):
    inputs = tuple(_input(locator, index + 1) for index, (locator, _) in enumerate(records))
    return build_embedding_batch(
        inputs,
        tuple(vector for _, vector in records),
        model_fingerprint="sha256:" + "a" * 64,
        output_dtype="float32",
    )


def test_exact_cosine_orders_by_portable_score_then_locator() -> None:
    projection = ExactCosineProjection()
    records = [(f"doc-{index:02d}", _score_vector(0.9 - index * 0.02)) for index in range(9)]
    records.extend(
        [
            ("doc-z-tie", _score_vector(0.5000004)),
            ("doc-a-tie", _score_vector(0.5000001)),
        ]
    )
    projection.replace(_batch(records))

    results = projection.search(_basis(0), top_k=10)

    assert len(results) == 10
    assert [item.rank for item in results] == list(range(1, 11))
    tie_locators = [item.stable_locator_id for item in results if item.score == 0.5]
    assert tie_locators == sorted(tie_locators)
    assert all(len(f"{item.score:.6f}".split(".")[1]) == 6 for item in results)


def test_exact_cosine_handles_positive_zero_and_negative_similarity() -> None:
    projection = ExactCosineProjection()
    projection.replace(
        _batch(
            [
                ("positive", _basis(0)),
                ("zero", _basis(1)),
                ("negative", _basis(0, -1.0)),
            ]
        )
    )

    results = projection.search(_basis(0), top_k=10)

    assert [item.score for item in results] == [1.0, 0.0, -1.0]


def test_exact_projection_replace_is_atomic_and_validate_checks_full_identity() -> None:
    projection = ExactCosineProjection()
    original = projection.replace(_batch([("original", _basis(0))]))
    invalid = EmbeddingBatch(
        model_fingerprint="sha256:" + "a" * 64,
        evidence=(EmbeddedEvidence("invalid", (1.0,)),),
    )

    with pytest.raises(VectorProjectionError):
        projection.replace(invalid)

    projection.validate(original)
    assert projection.search(_basis(0), top_k=10)[0].stable_locator_id.startswith("original|")


def test_exact_projection_requires_active_projection_normalized_query_and_top_ten() -> None:
    projection = ExactCosineProjection()
    with pytest.raises(VectorProjectionError, match="active"):
        projection.search(_basis(0), top_k=10)

    projection.replace(_batch([("doc", _basis(0))]))
    with pytest.raises(VectorProjectionError, match="top_k"):
        projection.search(_basis(0), top_k=5)
    with pytest.raises(VectorProjectionError, match="dimension"):
        projection.search((1.0,), top_k=10)


def test_close_discards_active_projection() -> None:
    projection = ExactCosineProjection()
    identity = projection.replace(_batch([("doc", _basis(0))]))
    projection.close()

    with pytest.raises(VectorProjectionError):
        projection.validate(identity)
