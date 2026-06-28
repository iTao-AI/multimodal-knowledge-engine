"""Local embedding adapters kept behind project-owned ports."""

from mke.adapters.embedding.sentence_transformers import (
    EmbeddingAdapterError,
    SentenceTransformersEmbeddingAdapter,
    create_sentence_transformers_embedding,
)

__all__ = [
    "EmbeddingAdapterError",
    "SentenceTransformersEmbeddingAdapter",
    "create_sentence_transformers_embedding",
]
