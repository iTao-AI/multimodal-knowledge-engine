from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import pytest

from mke.embeddings.contracts import (
    EMBEDDING_DIMENSION,
    EmbeddingEvidenceInput,
    build_embedding_batch,
)
from mke.vector.contracts import (
    CANONICAL_TOP_K,
    RankedEvidence,
    VectorProjectionError,
    build_projection_identity,
)


def _input(document_id: str, page: int, text: str) -> EmbeddingEvidenceInput:
    return EmbeddingEvidenceInput(
        document_id=document_id,
        locator_kind="page",
        locator_start=page,
        locator_end=page,
        text=text,
        text_sha256=sha256(text.encode("utf-8")).hexdigest(),
        runtime_evidence_id=f"evidence-{page}",
        runtime_publication_id="publication-1",
    )


def _vector(index: int) -> tuple[float, ...]:
    return tuple(1.0 if position == index else 0.0 for position in range(EMBEDDING_DIMENSION))


def _batch():
    return build_embedding_batch(
        (_input("doc", 1, "first"), _input("doc", 2, "second")),
        (_vector(0), _vector(1)),
        model_fingerprint="sha256:" + "a" * 64,
        output_dtype="float32",
    )


def test_projection_identity_binds_model_locator_text_and_float32_vectors() -> None:
    batch = _batch()
    identity = build_projection_identity(batch, adapter_id="exact-cosine-v1")

    assert identity.adapter_id == "exact-cosine-v1"
    assert identity.model_fingerprint == batch.model_fingerprint
    assert identity.dimension == 1024
    assert identity.row_count == 2
    assert identity.locator_digest.startswith("sha256:")
    assert identity.source_text_digest.startswith("sha256:")
    assert identity.vector_digest.startswith("sha256:")
    assert identity == build_projection_identity(batch, adapter_id="exact-cosine-v1")

    changed = replace(
        batch,
        model_fingerprint="sha256:" + "b" * 64,
    )
    changed_identity = build_projection_identity(changed, adapter_id="exact-cosine-v1")
    assert changed_identity.model_fingerprint != identity.model_fingerprint


@pytest.mark.parametrize(
    "kwargs",
    [
        {"stable_locator_id": ""},
        {"rank": True},
        {"rank": 0},
        {"score": float("nan")},
        {"score": 1.000001},
        {"adapter_id": ""},
    ],
)
def test_ranked_evidence_rejects_invalid_portable_values(kwargs: dict[str, object]) -> None:
    values: dict[str, object] = {
        "stable_locator_id": "doc|page|1|1|" + "a" * 64,
        "rank": 1,
        "score": 0.5,
        "adapter_id": "exact-cosine-v1",
    }
    values.update(kwargs)

    with pytest.raises(VectorProjectionError):
        RankedEvidence(**values)  # type: ignore[arg-type]


def test_canonical_candidate_depth_is_exactly_ten() -> None:
    assert CANONICAL_TOP_K == 10
