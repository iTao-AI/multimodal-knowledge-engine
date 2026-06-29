from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from mke.adapters.embedding.sentence_transformers import (
    EmbeddingAdapterError,
    SentenceTransformersEmbeddingAdapter,
    create_sentence_transformers_embedding,
)
from mke.embeddings.contracts import (
    EMBEDDING_DIMENSION,
    EmbeddingEvidenceInput,
)
from mke.embeddings.readiness import EmbeddingSnapshotManifest


def _input(document_id: str, page: int, text: str) -> EmbeddingEvidenceInput:
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


def _vector(index: int = 0) -> list[float]:
    return [1.0 if position == index else 0.0 for position in range(EMBEDDING_DIMENSION)]


@dataclass
class _FakeArray:
    rows: list[list[float]]
    dtype: str = "float32"

    @property
    def shape(self) -> tuple[int, int]:
        width = len(self.rows[0]) if self.rows else EMBEDDING_DIMENSION
        return len(self.rows), width

    def tolist(self) -> list[list[float]]:
        return self.rows


class _FakeTokenizer:
    padding_side = "right"

    def __init__(self) -> None:
        self.lengths: dict[str, int] = {}
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, texts: list[str], **kwargs: object) -> dict[str, list[list[int]]]:
        self.calls.append((list(texts), dict(kwargs)))
        return {
            "input_ids": [list(range(self.lengths.get(text, len(text)))) for text in texts]
        }


class _FakeModel:
    def __init__(self) -> None:
        self.max_seq_length = 0
        self.tokenizer = _FakeTokenizer()
        self.encode_calls: list[tuple[list[str], dict[str, object]]] = []
        self.float_called = False
        self.eval_called = False
        self.outputs: list[_FakeArray] = []

    def float(self) -> _FakeModel:
        self.float_called = True
        return self

    def eval(self) -> _FakeModel:
        self.eval_called = True
        return self

    def encode(self, texts: list[str], **kwargs: object) -> _FakeArray:
        self.encode_calls.append((list(texts), dict(kwargs)))
        if self.outputs:
            return self.outputs.pop(0)
        return _FakeArray([_vector(index % 2) for index, _ in enumerate(texts)])


def _install_factory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[_FakeModel, list[tuple[tuple[object, ...], dict[str, object]]]]:
    model = _FakeModel()
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def factory(*args: object, **kwargs: object) -> _FakeModel:
        calls.append((args, dict(kwargs)))
        return model

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=factory),
    )
    snapshot = tmp_path / "cache" / "snapshot"
    snapshot.mkdir(parents=True)
    manifest = EmbeddingSnapshotManifest(
        snapshot_fingerprint="sha256:" + "a" * 64,
        total_bytes=7,
        files=(),
    )
    def load_snapshot(cache_dir: Path) -> tuple[Path, EmbeddingSnapshotManifest]:
        return snapshot, manifest

    monkeypatch.setattr(
        "mke.adapters.embedding.sentence_transformers.load_cached_embedding_snapshot",
        load_snapshot,
    )
    return model, calls


def test_factory_lazily_maps_missing_optional_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = EmbeddingSnapshotManifest("sha256:" + "a" * 64, 7, ())
    def load_snapshot(cache_dir: Path) -> tuple[Path, EmbeddingSnapshotManifest]:
        return tmp_path / "snapshot", manifest

    monkeypatch.setattr(
        "mke.adapters.embedding.sentence_transformers.load_cached_embedding_snapshot",
        load_snapshot,
    )

    def missing(name: str) -> object:
        raise ImportError(name)

    monkeypatch.setattr("mke.adapters.embedding.sentence_transformers.import_module", missing)

    with pytest.raises(EmbeddingAdapterError) as exc_info:
        create_sentence_transformers_embedding(cache_dir=tmp_path / "cache")

    assert exc_info.value.cause == "embedding optional dependency is not installed"
    assert str(tmp_path) not in str(exc_info.value)


def test_factory_uses_exact_local_cpu_float32_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, calls = _install_factory(monkeypatch, tmp_path)

    adapter = create_sentence_transformers_embedding(cache_dir=tmp_path / "cache")

    snapshot = tmp_path / "cache" / "snapshot"
    assert calls == [
        (
            (str(snapshot),),
            {
                "device": "cpu",
                "local_files_only": True,
                "trust_remote_code": False,
            },
        )
    ]
    assert model.max_seq_length == 8192
    assert model.tokenizer.padding_side == "left"
    assert model.float_called is True
    assert model.eval_called is True
    assert isinstance(adapter, SentenceTransformersEmbeddingAdapter)
    assert str(snapshot) not in repr(adapter)


def test_query_uses_exact_instruction_batch_and_normalized_float32_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, _ = _install_factory(monkeypatch, tmp_path)
    adapter = create_sentence_transformers_embedding(cache_dir=tmp_path / "cache")

    vector = adapter.embed_query("来源如何验证")

    expected = (
        "Instruct: Given a Chinese user query, retrieve relevant evidence passages "
        "that answer the query\nQuery:来源如何验证"
    )
    assert vector == tuple(_vector())
    assert model.tokenizer.calls == [
        (
            [expected],
            {"padding": False, "truncation": False, "add_special_tokens": True},
        )
    ]
    assert model.encode_calls == [
        (
            [expected],
            {
                "batch_size": 1,
                "show_progress_bar": False,
                "precision": "float32",
                "convert_to_numpy": True,
                "convert_to_tensor": False,
                "device": "cpu",
                "normalize_embeddings": True,
            },
        )
    ]


def test_documents_are_unprefixed_sorted_and_batched_by_four(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, _ = _install_factory(monkeypatch, tmp_path)
    adapter = create_sentence_transformers_embedding(cache_dir=tmp_path / "cache")
    inputs = tuple(
        reversed(tuple(_input("doc", page, f"document-{page}") for page in range(1, 6)))
    )

    batch = adapter.embed_documents(inputs)

    sorted_inputs = tuple(sorted(inputs, key=lambda item: item.stable_locator_id))
    assert tuple(item.stable_locator_id for item in batch.evidence) == tuple(
        item.stable_locator_id for item in sorted_inputs
    )
    assert [texts for texts, _ in model.encode_calls] == [
        [item.text for item in sorted_inputs[:4]],
        [item.text for item in sorted_inputs[4:]],
    ]
    assert all(not text.startswith("Instruct:") for text in model.tokenizer.calls[0][0])
    assert [call[1]["batch_size"] for call in model.encode_calls] == [4, 4]


def test_token_preflight_rejects_truncation_before_encode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, _ = _install_factory(monkeypatch, tmp_path)
    model.tokenizer.lengths["too-long"] = 8193
    adapter = create_sentence_transformers_embedding(cache_dir=tmp_path / "cache")

    with pytest.raises(EmbeddingAdapterError) as exc_info:
        adapter.embed_documents((_input("doc", 1, "too-long"),))

    assert exc_info.value.cause == "embedding input would be truncated"
    assert model.encode_calls == []


def test_tokenize_lengths_returns_actual_untruncated_lengths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, _ = _install_factory(monkeypatch, tmp_path)
    model.tokenizer.lengths.update({"first": 17, "second": 23})
    adapter = create_sentence_transformers_embedding(cache_dir=tmp_path / "cache")

    assert adapter.tokenize_lengths(("first", "second")) == (17, 23)


def test_cancellation_between_document_batches_stops_before_next_encode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, _ = _install_factory(monkeypatch, tmp_path)
    adapter = create_sentence_transformers_embedding(
        cache_dir=tmp_path / "cache",
        cancelled=lambda: len(model.encode_calls) == 1,
    )
    inputs = tuple(_input("doc", page, f"document-{page}") for page in range(1, 6))

    with pytest.raises(EmbeddingAdapterError, match="cancelled"):
        adapter.embed_documents(inputs)

    assert len(model.encode_calls) == 1


@pytest.mark.parametrize(
    ("output", "cause"),
    [
        (_FakeArray([]), "embedding output count is invalid"),
        (_FakeArray([[1.0]]), "embedding output dimension is invalid"),
        (_FakeArray([_vector()], dtype="float64"), "embedding output dtype must be float32"),
        (
            _FakeArray([[math.inf, *_vector()[1:]]]),
            "embedding output contains non-finite values",
        ),
        (
            _FakeArray([[0.5, *_vector()[1:]]]),
            "embedding output is not normalized",
        ),
    ],
)
def test_invalid_provider_outputs_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: _FakeArray,
    cause: str,
) -> None:
    model, _ = _install_factory(monkeypatch, tmp_path)
    model.outputs.append(output)
    adapter = create_sentence_transformers_embedding(cache_dir=tmp_path / "cache")

    with pytest.raises(EmbeddingAdapterError) as exc_info:
        adapter.embed_query("query")

    assert exc_info.value.cause == cause
    assert str(tmp_path) not in str(exc_info.value)


def test_adapter_result_exposes_only_project_owned_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_factory(monkeypatch, tmp_path)
    adapter = create_sentence_transformers_embedding(cache_dir=tmp_path / "cache")
    result = adapter.embed_documents((_input("doc", 1, "text"),))

    assert type(result).__module__ == "mke.embeddings.contracts"
    assert all(type(item).__module__ == "mke.embeddings.contracts" for item in result.evidence)
    assert isinstance(result.evidence[0].vector, tuple)
