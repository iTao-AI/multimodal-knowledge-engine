from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import pytest

from mke.embeddings.contracts import (
    EMBEDDING_DIMENSION,
    EmbeddingBatch,
    EmbeddingEvidenceInput,
    build_embedding_batch,
)
from mke.evaluation.dense_candidate import (
    DenseCandidateError,
    run_dense_candidate_partition,
    run_dense_development_candidate,
)
from mke.evaluation.dense_protocol import load_dense_protocol_lock

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_LOCK = ROOT / "tests/fixtures/retrieval-dense-v1/protocol-lock.json"


def test_dense_candidate_development_uses_only_development_snapshot() -> None:
    provider = _PartitionAwareProvider()
    protocol = load_dense_protocol_lock(PROTOCOL_LOCK, repository_root=ROOT)

    report = run_dense_development_candidate(
        protocol,
        repository_root=ROOT,
        provider=provider,
    )

    assert report["partition"] == "development"
    assert report["candidate_id"] == "qwen3-embedding-0.6b-exact-v1"
    snapshot = cast(dict[str, object], report["snapshot"])
    projection = cast(dict[str, object], report["projection"])
    observations = cast(list[dict[str, object]], report["observations"])
    assert snapshot["evidence_count"] == 34
    assert projection["adapter_id"] == "exact-cosine-v1"
    assert provider.document_call_count == 1
    assert all(
        cast(dict[str, object], result["locator"])["document_id"]
        in {"ub-service-core", "development-adversarial"}
        for observation in observations
        for result in cast(list[dict[str, object]], observation["results"])
    )


def test_dense_candidate_holdout_requires_explicit_partition_and_separate_projection() -> None:
    protocol = load_dense_protocol_lock(PROTOCOL_LOCK, repository_root=ROOT)
    provider = _PartitionAwareProvider()

    development = run_dense_candidate_partition(
        protocol,
        repository_root=ROOT,
        partition="development",
        provider=provider,
    )
    holdout = run_dense_candidate_partition(
        protocol,
        repository_root=ROOT,
        partition="holdout",
        provider=provider,
    )

    development_snapshot = cast(dict[str, object], development["snapshot"])
    holdout_snapshot = cast(dict[str, object], holdout["snapshot"])
    development_projection = cast(dict[str, object], development["projection"])
    holdout_projection = cast(dict[str, object], holdout["projection"])
    holdout_observations = cast(list[dict[str, object]], holdout["observations"])
    assert development_snapshot["snapshot_id"] != holdout_snapshot["snapshot_id"]
    assert development_projection["projection_id"] != holdout_projection["projection_id"]
    assert development_projection["identity"] != holdout_projection["identity"]
    assert all(
        cast(dict[str, object], result["locator"])["document_id"]
        in {"copyright-law", "administrative-compulsion-law", "holdout-adversarial"}
        for observation in holdout_observations
        for result in cast(list[dict[str, object]], observation["results"])
    )


def test_dense_candidate_threshold_filters_without_reordering_knn_results() -> None:
    protocol = load_dense_protocol_lock(PROTOCOL_LOCK, repository_root=ROOT)

    unfiltered = run_dense_development_candidate(
        protocol,
        repository_root=ROOT,
        provider=_PartitionAwareProvider(),
        threshold=0.0,
    )
    filtered = run_dense_development_candidate(
        protocol,
        repository_root=ROOT,
        provider=_PartitionAwareProvider(),
        threshold=0.5,
    )

    first_unfiltered = cast(
        list[dict[str, object]],
        cast(list[dict[str, object]], unfiltered["observations"])[0]["results"],
    )
    first_filtered = cast(
        list[dict[str, object]],
        cast(list[dict[str, object]], filtered["observations"])[0]["results"],
    )
    assert [
        result["stable_locator_id"] for result in first_filtered
    ] == [
        result["stable_locator_id"]
        for result in first_unfiltered
        if cast(float, result["portable_score"]) >= 0.5
    ]


def test_dense_candidate_rejects_holdout_through_development_api_and_bad_threshold() -> None:
    protocol = load_dense_protocol_lock(PROTOCOL_LOCK, repository_root=ROOT)
    with pytest.raises(DenseCandidateError, match="holdout"):
        run_dense_development_candidate(
            protocol,
            repository_root=ROOT,
            provider=_PartitionAwareProvider(),
            partition="holdout",
        )
    with pytest.raises(DenseCandidateError, match="threshold"):
        run_dense_development_candidate(
            protocol,
            repository_root=ROOT,
            provider=_PartitionAwareProvider(),
            threshold=1.5,
        )


def test_dense_candidate_does_not_import_runtime_or_use_lexical_fallback() -> None:
    source = (ROOT / "src/mke/evaluation/dense_candidate.py").read_text(encoding="utf-8")

    assert "KnowledgeEngine" not in source
    assert "active_evidence_fts" not in source
    assert "retrieval_strategy" not in source
    assert "compile_fts5" not in source


class _PartitionAwareProvider:
    def __init__(self) -> None:
        self.document_call_count = 0

    def embed_documents(
        self,
        evidence: tuple[EmbeddingEvidenceInput, ...],
    ) -> EmbeddingBatch:
        self.document_call_count += 1
        vectors = tuple(_document_vector(item.document_id) for item in evidence)
        return build_embedding_batch(
            evidence,
            vectors,
            model_fingerprint="sha256:" + "a" * 64,
            output_dtype="float32",
        )

    def embed_query(self, query: str) -> tuple[float, ...]:
        del query
        return _unit_vector(0)


def _document_vector(document_id: str) -> tuple[float, ...]:
    if document_id in {
        "copyright-law",
        "administrative-compulsion-law",
        "holdout-adversarial",
    }:
        return _unit_vector(0)
    return _unit_vector(1)


def _unit_vector(index: Literal[0, 1]) -> tuple[float, ...]:
    return tuple(
        1.0 if position == index else 0.0
        for position in range(EMBEDDING_DIMENSION)
    )
