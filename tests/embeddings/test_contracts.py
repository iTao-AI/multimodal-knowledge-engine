from __future__ import annotations

import inspect
import math
from dataclasses import FrozenInstanceError

import pytest

from mke.embeddings.contracts import (
    CANDIDATE_ID,
    CANDIDATE_REVISION,
    DOCUMENT_BATCH_SIZE,
    EMBEDDING_DIMENSION,
    MAX_QUERY_CHARACTERS,
    MODEL_ID,
    MODEL_REVISION,
    QUERY_BATCH_SIZE,
    QUERY_INSTRUCTION,
    EmbeddingEvidenceInput,
    EmbeddingModelSpec,
    EmbeddingValidationError,
    build_embedding_batch,
    canonical_model_spec,
    format_embedding_query,
    require_candidate_identity,
)


def _input(
    *, document_id: str = "doc-a", page: int = 3, text: str = "evidence"
) -> EmbeddingEvidenceInput:
    from hashlib import sha256

    return EmbeddingEvidenceInput(
        document_id=document_id,
        locator_kind="page",
        locator_start=page,
        locator_end=page,
        text=text,
        text_sha256=sha256(text.encode("utf-8")).hexdigest(),
        runtime_evidence_id=f"evidence-{document_id}-{page}",
        runtime_publication_id=f"publication-{document_id}",
    )


def _unit_vector(index: int = 0) -> tuple[float, ...]:
    return tuple(1.0 if position == index else 0.0 for position in range(EMBEDDING_DIMENSION))


def test_canonical_model_spec_freezes_exact_candidate_values() -> None:
    spec = canonical_model_spec()

    assert spec == EmbeddingModelSpec(
        model_id="Qwen/Qwen3-Embedding-0.6B",
        model_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        query_instruction=(
            "Given a Chinese user query, retrieve relevant evidence passages that answer the query"
        ),
        dimension=1024,
        max_length=8192,
        input_dtype="float32",
        output_dtype="float32",
        normalize=True,
        query_batch_size=1,
        document_batch_size=4,
    )
    assert MODEL_ID == spec.model_id
    assert MODEL_REVISION == spec.model_revision
    assert QUERY_INSTRUCTION == spec.query_instruction
    assert EMBEDDING_DIMENSION == spec.dimension
    assert QUERY_BATCH_SIZE == spec.query_batch_size
    assert DOCUMENT_BATCH_SIZE == spec.document_batch_size
    assert CANDIDATE_ID == "qwen3-embedding-0.6b-exact-v1"
    assert CANDIDATE_REVISION == 1

    with pytest.raises(FrozenInstanceError):
        spec.dimension = 768  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model_id", "qwen3-embedding-0.6b"),
        ("model_id", ""),
        ("model_revision", "main"),
        ("model_revision", ""),
        ("model_revision", True),
        ("model_revision", 1.0),
        ("dimension", True),
        ("dimension", 768),
        ("max_length", 32768),
        ("input_dtype", "float16"),
        ("output_dtype", "float64"),
        ("normalize", False),
        ("query_batch_size", True),
        ("query_batch_size", 2),
        ("document_batch_size", 8),
    ],
)
def test_model_spec_rejects_noncanonical_or_weakly_typed_values(field: str, value: object) -> None:
    values = canonical_model_spec().__dict__ | {field: value}

    with pytest.raises(EmbeddingValidationError):
        EmbeddingModelSpec(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("candidate_id", "revision"),
    [
        ("dense", 1),
        ("", 1),
        (CANDIDATE_ID, True),
        (CANDIDATE_ID, 1.0),
        (CANDIDATE_ID, 2),
    ],
)
def test_candidate_identity_rejects_aliases_and_non_integer_revision(
    candidate_id: object, revision: object
) -> None:
    with pytest.raises(EmbeddingValidationError):
        require_candidate_identity(candidate_id, revision)


def test_query_template_is_exact_and_bounded() -> None:
    query = "如何验证证据来源"

    assert format_embedding_query(query) == (
        "Instruct: Given a Chinese user query, retrieve relevant evidence passages "
        "that answer the query\n"
        "Query:如何验证证据来源"
    )

    for invalid in ("", "   ", "x" * (MAX_QUERY_CHARACTERS + 1)):
        with pytest.raises(EmbeddingValidationError, match="embedding query"):
            format_embedding_query(invalid)


def test_evidence_input_binds_stable_locator_and_text_digest_without_prefixing_text() -> None:
    item = _input(document_id="document-z", page=7, text="原始 Evidence 文本")

    assert item.stable_locator_id == (
        "document-z|page|7|7|0d56332094b3acc0821382a7c0675f58e4cc2dee34b461bf4207062cbe239f49"
    )
    assert item.text == "原始 Evidence 文本"
    assert not item.text.startswith("Instruct:")


@pytest.mark.parametrize(
    "changes",
    [
        {"document_id": ""},
        {"locator_kind": ""},
        {"locator_start": True},
        {"locator_start": -1},
        {"locator_end": 2},
        {"text": ""},
        {"text_sha256": "0" * 64},
        {"runtime_evidence_id": ""},
        {"runtime_publication_id": ""},
    ],
)
def test_evidence_input_rejects_invalid_snapshot_identity(changes: dict[str, object]) -> None:
    values = _input().__dict__ | changes

    with pytest.raises(EmbeddingValidationError):
        EmbeddingEvidenceInput(**values)  # type: ignore[arg-type]


def test_embedding_batch_preserves_stable_input_order_and_validates_vectors() -> None:
    inputs = (_input(document_id="doc-b", page=2), _input(document_id="doc-a", page=1))
    batch = build_embedding_batch(
        inputs,
        (_unit_vector(1), _unit_vector(2)),
        model_fingerprint="sha256:" + "a" * 64,
        output_dtype="float32",
    )

    assert tuple(item.stable_locator_id for item in batch.evidence) == tuple(
        item.stable_locator_id for item in inputs
    )
    assert batch.model_fingerprint == "sha256:" + "a" * 64


def test_embedding_batch_rejects_count_identity_dimension_finite_and_norm_failures() -> None:
    first = _input(document_id="doc-a", page=1)
    duplicate = _input(document_id="doc-a", page=1)
    fingerprint = "sha256:" + "b" * 64

    with pytest.raises(EmbeddingValidationError, match="count"):
        build_embedding_batch((first,), (), model_fingerprint=fingerprint, output_dtype="float32")
    with pytest.raises(EmbeddingValidationError, match="unique"):
        build_embedding_batch(
            (first, duplicate),
            (_unit_vector(), _unit_vector(1)),
            model_fingerprint=fingerprint,
            output_dtype="float32",
        )
    with pytest.raises(EmbeddingValidationError, match="dimension"):
        build_embedding_batch(
            (first,), ((1.0,),), model_fingerprint=fingerprint, output_dtype="float32"
        )
    non_finite = list(_unit_vector())
    non_finite[0] = math.inf
    with pytest.raises(EmbeddingValidationError, match="non-finite"):
        build_embedding_batch(
            (first,),
            (tuple(non_finite),),
            model_fingerprint=fingerprint,
            output_dtype="float32",
        )
    with pytest.raises(EmbeddingValidationError, match="normalized"):
        build_embedding_batch(
            (first,),
            (tuple(0.5 if index == 0 else 0.0 for index in range(EMBEDDING_DIMENSION)),),
            model_fingerprint=fingerprint,
            output_dtype="float32",
        )
    with pytest.raises(EmbeddingValidationError, match="float32"):
        build_embedding_batch(
            (first,), (_unit_vector(),), model_fingerprint=fingerprint, output_dtype="float64"
        )


def test_project_contracts_do_not_import_provider_or_numeric_sdk_objects() -> None:
    import mke.embeddings.contracts as contracts

    source = inspect.getsource(contracts)
    forbidden = ("sentence_transformers", "torch", "huggingface_hub", "numpy", "sqlite_vec")

    assert all(name not in source for name in forbidden)
    assert all(
        not type(value).__module__.startswith(forbidden)
        for value in vars(contracts).values()
        if not inspect.ismodule(value)
    )
