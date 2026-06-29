"""Project-owned embedding contracts for comparison-only local dense retrieval."""

from mke.embeddings.contracts import (
    CANDIDATE_ID,
    CANDIDATE_REVISION,
    MODEL_ID,
    MODEL_REVISION,
    EmbeddedEvidence,
    EmbeddingBatch,
    EmbeddingEvidenceInput,
    EmbeddingModelSpec,
    EmbeddingProvider,
    EmbeddingValidationError,
    LocalEmbeddingRuntime,
    build_embedding_batch,
    canonical_model_spec,
    format_embedding_query,
)

__all__ = [
    "CANDIDATE_ID",
    "CANDIDATE_REVISION",
    "MODEL_ID",
    "MODEL_REVISION",
    "EmbeddedEvidence",
    "EmbeddingBatch",
    "EmbeddingEvidenceInput",
    "EmbeddingModelSpec",
    "EmbeddingProvider",
    "EmbeddingValidationError",
    "LocalEmbeddingRuntime",
    "build_embedding_batch",
    "canonical_model_spec",
    "format_embedding_query",
]
