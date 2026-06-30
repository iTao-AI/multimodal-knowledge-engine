"""Cache-only dense candidate retrieval observations for E3-C."""

from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Literal, cast

from mke.adapters.vector.exact_cosine import ExactCosineProjection
from mke.embeddings.contracts import (
    CANDIDATE_ID,
    CANDIDATE_REVISION,
    EmbeddingEvidenceInput,
    EmbeddingProvider,
)
from mke.evaluation.chinese_protocol import load_chinese_retrieval_protocol
from mke.evaluation.dense_compatibility import load_dense_corpus_lock
from mke.vector.contracts import CANONICAL_TOP_K, VectorProjection

DensePartition = Literal["development", "holdout"]


class DenseCandidateError(RuntimeError):
    """Dense candidate observation failed before qrel grading."""


def run_dense_development_candidate(
    protocol: dict[str, object],
    *,
    repository_root: Path,
    provider: EmbeddingProvider,
    threshold: float = 0.0,
    partition: DensePartition = "development",
) -> dict[str, object]:
    if partition != "development":
        raise DenseCandidateError("holdout is not available through development API")
    return run_dense_candidate_partition(
        protocol,
        repository_root=repository_root,
        partition="development",
        provider=provider,
        threshold=threshold,
    )


def run_dense_candidate_partition(
    protocol: dict[str, object],
    *,
    repository_root: Path,
    partition: DensePartition,
    provider: EmbeddingProvider,
    threshold: float = 0.0,
    projection: VectorProjection | None = None,
) -> dict[str, object]:
    _validate_threshold(threshold)
    root = repository_root.resolve()
    inputs = cast(dict[str, dict[str, object]], protocol["inputs"])
    corpus_lock_path = root / cast(str, inputs["corpus_lock"]["path"])
    chinese_protocol_path = root / cast(str, inputs["chinese_protocol"]["path"])
    corpus = load_dense_corpus_lock(corpus_lock_path, repository_root=root)
    chinese = load_chinese_retrieval_protocol(chinese_protocol_path)
    pages = tuple(page for page in corpus.pages if page.split == partition)
    if not pages:
        raise DenseCandidateError("dense candidate snapshot is empty")
    evidence = tuple(
        EmbeddingEvidenceInput(
            document_id=page.document_id,
            locator_kind="page",
            locator_start=page.page,
            locator_end=page.page,
            text=page.text,
            text_sha256=page.text_sha256,
            runtime_evidence_id=f"dense:{partition}:{page.document_id}:{page.page}",
            runtime_publication_id=f"dense:{partition}",
        )
        for page in sorted(pages, key=lambda item: (item.document_id, item.page))
    )
    locator_by_id = {item.stable_locator_id: item for item in evidence}
    started = time.monotonic()
    batch = provider.embed_documents(evidence)
    active_projection = projection or ExactCosineProjection()
    try:
        identity = active_projection.replace(batch)
        active_projection.validate(identity)
        observations: list[dict[str, object]] = []
        for query in chinese.queries:
            if query.split != partition:
                continue
            query_started = time.monotonic()
            query_vector = provider.embed_query(query.text)
            ranked = active_projection.search(query_vector, top_k=CANONICAL_TOP_K)
            results = [
                {
                    "stable_locator_id": item.stable_locator_id,
                    "rank": item.rank,
                    "portable_score": item.score,
                    "raw_score": item.score,
                    "adapter_id": item.adapter_id,
                    "locator": _locator_payload(locator_by_id[item.stable_locator_id]),
                }
                for item in ranked
                if item.score >= threshold
            ]
            observations.append(
                {
                    "query_id": query.query_id,
                    "split": query.split,
                    "category": query.category,
                    "threshold": threshold,
                    "results": results,
                    "latency_ms": _elapsed_ms(query_started),
                }
            )
        return {
            "schema_version": "mke.dense_candidate_observations.v1",
            "candidate_id": CANDIDATE_ID,
            "candidate_revision": CANDIDATE_REVISION,
            "partition": partition,
            "snapshot": {
                "snapshot_id": cast(
                    dict[str, dict[str, object]],
                    protocol["partitions"],
                )[partition]["snapshot_id"],
                "evidence_count": len(evidence),
                "source_text_digest": identity.source_text_digest,
                "locator_digest": identity.locator_digest,
            },
            "projection": {
                "projection_id": cast(
                    dict[str, dict[str, object]],
                    protocol["partitions"],
                )[partition]["projection_id"],
                "adapter_id": identity.adapter_id,
                "identity": asdict(identity),
            },
            "observations": observations,
            "duration_ms": _elapsed_ms(started),
        }
    finally:
        active_projection.close()


def _validate_threshold(value: float) -> None:
    if type(value) is not float or value < 0.0 or value > 1.0:
        raise DenseCandidateError("threshold must be between 0.0 and 1.0")


def _locator_payload(item: EmbeddingEvidenceInput) -> dict[str, object]:
    return {
        "document_id": item.document_id,
        "locator_kind": item.locator_kind,
        "locator_start": item.locator_start,
        "locator_end": item.locator_end,
    }


def _elapsed_ms(started: float) -> int:
    return max(0, int(round((time.monotonic() - started) * 1000)))
