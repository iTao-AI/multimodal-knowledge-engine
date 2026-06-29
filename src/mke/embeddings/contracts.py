"""Provider-neutral embedding values and validation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal, Protocol

MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"
MODEL_REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
CANDIDATE_ID = "qwen3-embedding-0.6b-exact-v1"
CANDIDATE_REVISION = 1
QUERY_INSTRUCTION = (
    "Given a Chinese user query, retrieve relevant evidence passages that answer the query"
)
EMBEDDING_DIMENSION = 1024
MAX_MODEL_LENGTH = 8192
MAX_QUERY_CHARACTERS = 1000
QUERY_BATCH_SIZE = 1
DOCUMENT_BATCH_SIZE = 4


class EmbeddingValidationError(ValueError):
    """Project-owned embedding input or output violated the frozen contract."""


def _require_nonempty_string(value: object, *, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise EmbeddingValidationError(f"{field} must be a non-empty string")
    return value


def _require_exact(value: object, expected: object, *, field: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise EmbeddingValidationError(f"{field} must use the frozen value")


@dataclass(frozen=True)
class EmbeddingModelSpec:
    model_id: str
    model_revision: str
    query_instruction: str
    dimension: int
    max_length: int
    input_dtype: Literal["float32"]
    output_dtype: Literal["float32"]
    normalize: Literal[True]
    query_batch_size: Literal[1]
    document_batch_size: Literal[4]

    def __post_init__(self) -> None:
        frozen_values = {
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "query_instruction": QUERY_INSTRUCTION,
            "dimension": EMBEDDING_DIMENSION,
            "max_length": MAX_MODEL_LENGTH,
            "input_dtype": "float32",
            "output_dtype": "float32",
            "normalize": True,
            "query_batch_size": QUERY_BATCH_SIZE,
            "document_batch_size": DOCUMENT_BATCH_SIZE,
        }
        for field, expected in frozen_values.items():
            _require_exact(getattr(self, field), expected, field=field)


def canonical_model_spec() -> EmbeddingModelSpec:
    return EmbeddingModelSpec(
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
        query_instruction=QUERY_INSTRUCTION,
        dimension=EMBEDDING_DIMENSION,
        max_length=MAX_MODEL_LENGTH,
        input_dtype="float32",
        output_dtype="float32",
        normalize=True,
        query_batch_size=QUERY_BATCH_SIZE,
        document_batch_size=DOCUMENT_BATCH_SIZE,
    )


def require_candidate_identity(candidate_id: object, revision: object) -> tuple[str, int]:
    _require_exact(candidate_id, CANDIDATE_ID, field="candidate_id")
    _require_exact(revision, CANDIDATE_REVISION, field="candidate_revision")
    return CANDIDATE_ID, CANDIDATE_REVISION


def format_embedding_query(query: object) -> str:
    validated = _require_nonempty_string(query, field="embedding query")
    if len(validated) > MAX_QUERY_CHARACTERS:
        raise EmbeddingValidationError(
            f"embedding query must be {MAX_QUERY_CHARACTERS} characters or fewer"
        )
    return f"Instruct: {QUERY_INSTRUCTION}\nQuery:{validated}"


@dataclass(frozen=True)
class EmbeddingEvidenceInput:
    document_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    text: str
    text_sha256: str
    runtime_evidence_id: str
    runtime_publication_id: str

    def __post_init__(self) -> None:
        for field in (
            "document_id",
            "locator_kind",
            "text",
            "runtime_evidence_id",
            "runtime_publication_id",
        ):
            _require_nonempty_string(getattr(self, field), field=field)
        if type(self.locator_start) is not int or self.locator_start < 0:
            raise EmbeddingValidationError("locator_start must be a non-negative integer")
        if type(self.locator_end) is not int or self.locator_end < self.locator_start:
            raise EmbeddingValidationError("locator_end must not precede locator_start")
        expected_digest = sha256(self.text.encode("utf-8")).hexdigest()
        if self.text_sha256 != expected_digest:
            raise EmbeddingValidationError("text_sha256 does not match Evidence text")

    @property
    def stable_locator_id(self) -> str:
        return "|".join(
            (
                self.document_id,
                self.locator_kind,
                str(self.locator_start),
                str(self.locator_end),
                self.text_sha256,
            )
        )


@dataclass(frozen=True)
class EmbeddedEvidence:
    stable_locator_id: str
    vector: tuple[float, ...]


@dataclass(frozen=True)
class EmbeddingBatch:
    model_fingerprint: str
    evidence: tuple[EmbeddedEvidence, ...]


class EmbeddingProvider(Protocol):
    def embed_documents(
        self, evidence: tuple[EmbeddingEvidenceInput, ...]
    ) -> EmbeddingBatch: ...

    def embed_query(self, query: str) -> tuple[float, ...]: ...


class LocalEmbeddingRuntime(Protocol):
    def tokenize_lengths(self, texts: tuple[str, ...]) -> tuple[int, ...]: ...


def _validate_vector(vector: tuple[float, ...]) -> None:
    if type(vector) is not tuple or len(vector) != EMBEDDING_DIMENSION:
        raise EmbeddingValidationError("embedding output dimension is invalid")
    if any(type(component) is not float or not math.isfinite(component) for component in vector):
        raise EmbeddingValidationError("embedding output contains non-finite values")
    norm = math.sqrt(math.fsum(component * component for component in vector))
    if abs(norm - 1.0) > 1e-5:
        raise EmbeddingValidationError("embedding output is not normalized")


def validate_embedding_vector(
    vector: tuple[float, ...], *, output_dtype: str
) -> tuple[float, ...]:
    if output_dtype != "float32":
        raise EmbeddingValidationError("embedding output dtype must be float32")
    _validate_vector(vector)
    return vector


def build_embedding_batch(
    evidence: tuple[EmbeddingEvidenceInput, ...],
    vectors: tuple[tuple[float, ...], ...],
    *,
    model_fingerprint: str,
    output_dtype: str,
) -> EmbeddingBatch:
    if type(evidence) is not tuple or type(vectors) is not tuple or len(evidence) != len(vectors):
        raise EmbeddingValidationError("embedding output count is invalid")
    if not evidence:
        raise EmbeddingValidationError("embedding output count is invalid")
    _require_nonempty_string(model_fingerprint, field="model_fingerprint")
    locator_ids = tuple(item.stable_locator_id for item in evidence)
    if len(set(locator_ids)) != len(locator_ids):
        raise EmbeddingValidationError("embedding Evidence identities must be unique")
    for vector in vectors:
        validate_embedding_vector(vector, output_dtype=output_dtype)
    return EmbeddingBatch(
        model_fingerprint=model_fingerprint,
        evidence=tuple(
            EmbeddedEvidence(stable_locator_id=locator_id, vector=vector)
            for locator_id, vector in zip(locator_ids, vectors, strict=True)
        ),
    )
