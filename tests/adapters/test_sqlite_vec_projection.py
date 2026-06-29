from __future__ import annotations

import inspect
import math
from hashlib import sha256
from pathlib import Path

import pytest

from mke.adapters.vector.exact_cosine import ExactCosineProjection
from mke.adapters.vector.sqlite_vec import SqliteVecProjection
from mke.embeddings.contracts import (
    EMBEDDING_DIMENSION,
    EmbeddingEvidenceInput,
    build_embedding_batch,
)
from mke.vector.contracts import VectorProjectionError


@pytest.fixture
def sqlite_vec_runtime() -> None:
    pytest.importorskip(
        "sqlite_vec",
        reason="sqlite-vec optional dependency is not installed",
    )


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
    return build_embedding_batch(
        tuple(_input(locator, index + 1) for index, (locator, _) in enumerate(records)),
        tuple(vector for _, vector in records),
        model_fingerprint="sha256:" + "a" * 64,
        output_dtype="float32",
    )


def test_sqlite_vec_matches_exact_oracle_for_normal_tie_negative_and_near_tie(
    tmp_path: Path,
    sqlite_vec_runtime: None,
) -> None:
    del sqlite_vec_runtime
    records = [
        ("positive", _basis(0)),
        ("zero", _basis(1)),
        ("negative", _basis(0, -1.0)),
        ("z-near-tie", _score_vector(0.5000004)),
        ("a-near-tie", _score_vector(0.5000001)),
    ]
    records.extend((f"filler-{index}", _score_vector(0.4 - index * 0.01)) for index in range(8))
    batch = _batch(records)
    exact = ExactCosineProjection()
    sqlite_projection = SqliteVecProjection(tmp_path / "projection.sqlite")
    exact.replace(batch)
    sqlite_projection.replace(batch)

    expected = exact.search(_basis(0), top_k=10)
    observed = sqlite_projection.search(_basis(0), top_k=10)

    assert observed == tuple(
        type(item)(item.stable_locator_id, item.rank, item.score, "sqlite-vec-0.1.9-v1")
        for item in expected
    )
    source = inspect.getsource(SqliteVecProjection.search).upper()
    assert "LIMIT 10" not in source
    sqlite_projection.close()


def test_sqlite_vec_insert_delete_rebuild_and_validate(
    tmp_path: Path,
    sqlite_vec_runtime: None,
) -> None:
    del sqlite_vec_runtime
    path = tmp_path / "projection.sqlite"
    projection = SqliteVecProjection(path)
    first = projection.replace(_batch([("first", _basis(0)), ("removed", _basis(1))]))
    projection.validate(first)

    second = projection.replace(_batch([("second", _basis(0))]))

    projection.validate(second)
    results = projection.search(_basis(0), top_k=10)
    assert len(results) == 1
    assert results[0].stable_locator_id.startswith("second|")
    assert path.exists()
    projection.close()
    assert not path.exists()


def test_sqlite_vec_failed_replace_rolls_back_to_previous_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sqlite_vec_runtime: None,
) -> None:
    del sqlite_vec_runtime
    projection = SqliteVecProjection(tmp_path / "projection.sqlite")
    original = projection.replace(_batch([("original", _basis(0))]))
    original_insert = projection._insert_row  # pyright: ignore[reportPrivateUsage]
    calls = 0

    def fail_second(rowid: int, locator: str, vector: tuple[float, ...]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected")
        original_insert(rowid, locator, vector)

    monkeypatch.setattr(projection, "_insert_row", fail_second)  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(VectorProjectionError, match="replace"):
        projection.replace(_batch([("new-a", _basis(0)), ("new-b", _basis(1))]))

    projection.validate(original)
    assert projection.search(_basis(0), top_k=10)[0].stable_locator_id.startswith("original|")
    projection.close()


def test_sqlite_vec_rejects_repository_file_and_unavailable_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    with pytest.raises(VectorProjectionError, match="outside"):
        SqliteVecProjection(repository / "projection.sqlite", repository_root=repository)

    def missing(name: str) -> object:
        raise ImportError(name)

    monkeypatch.setattr("mke.adapters.vector.sqlite_vec.import_module", missing)
    with pytest.raises(VectorProjectionError) as exc_info:
        SqliteVecProjection(tmp_path / "missing.sqlite")
    assert exc_info.value.cause == "vector extension is unavailable or incompatible"


def test_sqlite_vec_enforces_canonical_top_k_and_query_integrity(
    tmp_path: Path,
    sqlite_vec_runtime: None,
) -> None:
    del sqlite_vec_runtime
    projection = SqliteVecProjection(tmp_path / "projection.sqlite")
    projection.replace(_batch([("doc", _basis(0))]))

    with pytest.raises(VectorProjectionError, match="top_k"):
        projection.search(_basis(0), top_k=9)
    with pytest.raises(VectorProjectionError, match="normalized"):
        projection.search(tuple(0.5 if index == 0 else 0.0 for index in range(1024)), top_k=10)
    projection.close()
