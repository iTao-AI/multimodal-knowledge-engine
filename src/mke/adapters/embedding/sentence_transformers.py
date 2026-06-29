"""Cache-only SentenceTransformers adapter for the frozen Qwen3 candidate."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from mke.embeddings.contracts import (
    DOCUMENT_BATCH_SIZE,
    MAX_MODEL_LENGTH,
    QUERY_BATCH_SIZE,
    EmbeddingBatch,
    EmbeddingEvidenceInput,
    EmbeddingValidationError,
    build_embedding_batch,
    format_embedding_query,
    validate_embedding_vector,
)
from mke.embeddings.readiness import (
    EmbeddingModelError,
    load_cached_embedding_snapshot,
)


class _Tokenizer(Protocol):
    padding_side: str

    def __call__(
        self, texts: list[str], **kwargs: object
    ) -> dict[str, object]: ...


class _Array(Protocol):
    dtype: object
    shape: tuple[int, ...]

    def tolist(self) -> object: ...


class _SentenceTransformerModel(Protocol):
    max_seq_length: int
    tokenizer: _Tokenizer

    def float(self) -> _SentenceTransformerModel: ...

    def eval(self) -> _SentenceTransformerModel: ...

    def encode(self, texts: list[str], **kwargs: object) -> _Array: ...


class _SentenceTransformerFactory(Protocol):
    def __call__(
        self,
        model_name_or_path: str,
        *,
        device: str,
        local_files_only: bool,
        trust_remote_code: bool,
    ) -> _SentenceTransformerModel: ...


class EmbeddingAdapterError(RuntimeError):
    """Stable adapter failure without provider objects, paths, or SDK text."""

    def __init__(self, cause: str, next_step: str) -> None:
        super().__init__(cause)
        self.cause = cause
        self.next_step = next_step


class SentenceTransformersEmbeddingAdapter:
    """Implements project-owned embedding ports over one cache-only local model."""

    def __init__(
        self,
        model: _SentenceTransformerModel,
        *,
        model_fingerprint: str,
        cancelled: Callable[[], bool],
    ) -> None:
        self._model = model
        self._model_fingerprint = model_fingerprint
        self._cancelled = cancelled

    def __repr__(self) -> str:
        return (
            "SentenceTransformersEmbeddingAdapter("
            f"model_fingerprint={self._model_fingerprint!r})"
        )

    def tokenize_lengths(self, texts: tuple[str, ...]) -> tuple[int, ...]:
        try:
            tokens = self._model.tokenizer(
                list(texts),
                padding=False,
                truncation=False,
                add_special_tokens=True,
            )
            raw_input_ids = tokens["input_ids"]
            if not isinstance(raw_input_ids, list):
                raise TypeError("token IDs must be a list")
            rows = cast(list[object], raw_input_ids)
            if len(rows) != len(texts):
                raise ValueError("token count mismatch")
            lengths = tuple(len(cast(list[object], row)) for row in rows)
        except EmbeddingAdapterError:
            raise
        except Exception as error:
            raise EmbeddingAdapterError(
                "embedding tokenizer output is invalid",
                "inspect_embedding_runtime",
            ) from error
        return lengths

    def embed_query(self, query: str) -> tuple[float, ...]:
        encoded_query = format_embedding_query(query)
        self._require_not_truncated((encoded_query,))
        self._require_not_cancelled()
        output = self._encode([encoded_query], batch_size=QUERY_BATCH_SIZE)
        rows, dtype = _portable_rows(output)
        if len(rows) != 1:
            raise EmbeddingAdapterError(
                "embedding output count is invalid",
                "inspect_embedding_runtime",
            )
        try:
            return validate_embedding_vector(rows[0], output_dtype=dtype)
        except EmbeddingValidationError as error:
            raise EmbeddingAdapterError(str(error), "inspect_embedding_runtime") from error

    def embed_documents(
        self, evidence: tuple[EmbeddingEvidenceInput, ...]
    ) -> EmbeddingBatch:
        ordered = tuple(sorted(evidence, key=lambda item: item.stable_locator_id))
        if not ordered:
            raise EmbeddingAdapterError(
                "embedding output count is invalid",
                "provide_embedding_evidence",
            )
        self._require_not_truncated(tuple(item.text for item in ordered))
        vectors: list[tuple[float, ...]] = []
        dtype: str | None = None
        for start in range(0, len(ordered), DOCUMENT_BATCH_SIZE):
            self._require_not_cancelled()
            batch = ordered[start : start + DOCUMENT_BATCH_SIZE]
            output = self._encode(
                [item.text for item in batch],
                batch_size=DOCUMENT_BATCH_SIZE,
            )
            rows, batch_dtype = _portable_rows(output)
            if len(rows) != len(batch):
                raise EmbeddingAdapterError(
                    "embedding output count is invalid",
                    "inspect_embedding_runtime",
                )
            if dtype is not None and dtype != batch_dtype:
                raise EmbeddingAdapterError(
                    "embedding output dtype must be float32",
                    "inspect_embedding_runtime",
                )
            dtype = batch_dtype
            vectors.extend(rows)
        try:
            return build_embedding_batch(
                ordered,
                tuple(vectors),
                model_fingerprint=self._model_fingerprint,
                output_dtype=dtype or "invalid",
            )
        except EmbeddingValidationError as error:
            raise EmbeddingAdapterError(str(error), "inspect_embedding_runtime") from error

    def _require_not_truncated(self, texts: tuple[str, ...]) -> None:
        if any(length > MAX_MODEL_LENGTH for length in self.tokenize_lengths(texts)):
            raise EmbeddingAdapterError(
                "embedding input would be truncated",
                "select_non_truncating_embedding_candidate",
            )

    def _require_not_cancelled(self) -> None:
        if self._cancelled():
            raise EmbeddingAdapterError("embedding cancelled", "retry_embedding")

    def _encode(self, texts: list[str], *, batch_size: int) -> _Array:
        try:
            return self._model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                precision="float32",
                convert_to_numpy=True,
                convert_to_tensor=False,
                device="cpu",
                normalize_embeddings=True,
            )
        except Exception as error:
            raise EmbeddingAdapterError(
                "embedding adapter failed",
                "inspect_embedding_runtime",
            ) from error


def create_sentence_transformers_embedding(
    *,
    cache_dir: Path,
    cancelled: Callable[[], bool] | None = None,
) -> SentenceTransformersEmbeddingAdapter:
    try:
        snapshot, manifest = load_cached_embedding_snapshot(cache_dir)
        sentence_transformers = import_module("sentence_transformers")
        factory = cast(
            _SentenceTransformerFactory,
            sentence_transformers.SentenceTransformer,
        )
    except (ImportError, AttributeError) as error:
        raise EmbeddingAdapterError(
            "embedding optional dependency is not installed",
            "install_embedding_extra",
        ) from error
    except EmbeddingModelError as error:
        raise EmbeddingAdapterError(error.cause, error.next_step) from error
    try:
        model = factory(
            str(snapshot),
            device="cpu",
            local_files_only=True,
            trust_remote_code=False,
        )
        model.max_seq_length = MAX_MODEL_LENGTH
        model.tokenizer.padding_side = "left"
        model.float()
        model.eval()
    except Exception as error:
        raise EmbeddingAdapterError(
            "embedding adapter failed",
            "inspect_embedding_runtime",
        ) from error
    return SentenceTransformersEmbeddingAdapter(
        model,
        model_fingerprint=manifest.snapshot_fingerprint,
        cancelled=cancelled or (lambda: False),
    )


def _portable_rows(output: _Array) -> tuple[tuple[tuple[float, ...], ...], str]:
    dtype = str(output.dtype)
    if dtype != "float32":
        raise EmbeddingAdapterError(
            "embedding output dtype must be float32",
            "inspect_embedding_runtime",
        )
    try:
        raw_rows = output.tolist()
        if not isinstance(raw_rows, list):
            raise TypeError("embedding output rows must be a list")
        rows = tuple(
            tuple(_require_float_component(component) for component in cast(list[object], row))
            for row in cast(list[object], raw_rows)
        )
    except Exception as error:
        raise EmbeddingAdapterError(
            "embedding output count is invalid",
            "inspect_embedding_runtime",
        ) from error
    return rows, dtype


def _require_float_component(component: object) -> float:
    if type(component) is not float:
        raise TypeError("embedding output component must be float32-derived float")
    return component
