"""Bounded sqlite-vec compatibility adapter over a temporary local projection."""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import asdict
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from mke.embeddings.contracts import EmbeddingBatch, validate_embedding_vector
from mke.vector.contracts import (
    ProjectionIdentity,
    RankedEvidence,
    VectorProjectionError,
    build_projection_identity,
    rank_portable_scores,
    validated_projection_rows,
)

SQLITE_VEC_ADAPTER_ID = "sqlite-vec-0.1.9-v1"


class _LoadExtension(Protocol):
    def __call__(self, connection: sqlite3.Connection) -> None: ...


class _SerializeFloat32(Protocol):
    def __call__(self, vector: list[float]) -> bytes: ...


class SqliteVecProjection:
    def __init__(
        self,
        database_path: Path,
        *,
        repository_root: Path | None = None,
    ) -> None:
        self._path = database_path.resolve(strict=False)
        if repository_root is not None:
            repository = repository_root.resolve(strict=False)
            if self._path == repository or self._path.is_relative_to(repository):
                raise VectorProjectionError("vector projection path must be outside the repository")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = None
        self._serialize_float32: _SerializeFloat32
        self._identity: ProjectionIdentity | None = None
        try:
            sqlite_vec = import_module("sqlite_vec")
            load = cast(_LoadExtension, sqlite_vec.load)
            self._serialize_float32 = cast(
                _SerializeFloat32,
                sqlite_vec.serialize_float32,
            )
            connection = sqlite3.connect(self._path, isolation_level=None)
            connection.enable_load_extension(True)
            load(connection)
            connection.enable_load_extension(False)
            version = connection.execute("select vec_version()").fetchone()
            if version is None or version[0] != "v0.1.9":
                raise RuntimeError("unexpected extension version")
            self._connection = connection
            self._identity = self._read_identity()
        except Exception as error:
            self._close_connection()
            self._remove_files()
            raise VectorProjectionError(
                "vector extension is unavailable or incompatible",
                "use_exact_cosine_reference",
            ) from error

    def replace(self, batch: EmbeddingBatch) -> ProjectionIdentity:
        connection = self._require_connection()
        rows = validated_projection_rows(batch)
        candidate = EmbeddingBatch(batch.model_fingerprint, rows)
        identity = build_projection_identity(candidate, adapter_id=SQLITE_VEC_ADAPTER_ID)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DROP TABLE IF EXISTS vector_rows")
            connection.execute("DROP TABLE IF EXISTS projection_rows")
            connection.execute("DROP TABLE IF EXISTS projection_identity")
            connection.execute(
                "CREATE VIRTUAL TABLE vector_rows USING vec0("
                "embedding float[1024] distance_metric=cosine)"
            )
            connection.execute(
                "CREATE TABLE projection_rows("
                "rowid INTEGER PRIMARY KEY, stable_locator_id TEXT NOT NULL UNIQUE)"
            )
            connection.execute(
                "CREATE TABLE projection_identity(identity_json TEXT NOT NULL)"
            )
            for rowid, item in enumerate(rows, start=1):
                self._insert_row(rowid, item.stable_locator_id, item.vector)
            connection.execute(
                "INSERT INTO projection_identity(identity_json) VALUES (?)",
                (json.dumps(asdict(identity), sort_keys=True, separators=(",", ":")),),
            )
            connection.execute("COMMIT")
        except Exception as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            self._identity = self._read_identity()
            raise VectorProjectionError("vector projection replace failed") from error
        self._identity = identity
        self.validate(identity)
        return identity

    def validate(self, expected: ProjectionIdentity) -> None:
        observed = self._read_identity()
        if observed is None or observed != expected or observed != self._identity:
            raise VectorProjectionError("vector projection identity mismatch")
        connection = self._require_connection()
        vector_count = connection.execute("SELECT count(*) FROM vector_rows").fetchone()
        locator_count = connection.execute("SELECT count(*) FROM projection_rows").fetchone()
        if vector_count != (expected.row_count,) or locator_count != (expected.row_count,):
            raise VectorProjectionError("vector projection inventory is incomplete")

    def search(
        self, query_vector: tuple[float, ...], *, top_k: int
    ) -> tuple[RankedEvidence, ...]:
        if self._identity is None:
            raise VectorProjectionError("vector projection is not active")
        try:
            query = validate_embedding_vector(query_vector, output_dtype="float32")
        except ValueError as error:
            raise VectorProjectionError(str(error)) from error
        connection = self._require_connection()
        raw = connection.execute(
            "SELECT rowid, distance FROM vector_rows "
            "WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (self._serialize_float32(list(query)), self._identity.row_count),
        ).fetchall()
        if len(raw) != self._identity.row_count:
            raise VectorProjectionError("vector projection search inventory is incomplete")
        locators = dict(
            connection.execute(
                "SELECT rowid, stable_locator_id FROM projection_rows"
            ).fetchall()
        )
        scores: list[tuple[str, float]] = []
        for raw_rowid, raw_distance in raw:
            if type(raw_rowid) is not int or raw_rowid not in locators:
                raise VectorProjectionError("vector projection search identity mismatch")
            if type(raw_distance) is not float or not math.isfinite(raw_distance):
                raise VectorProjectionError("vector projection distance is invalid")
            if raw_distance < -1e-6 or raw_distance > 2.000001:
                raise VectorProjectionError("vector projection distance is invalid")
            locator = locators[raw_rowid]
            if type(locator) is not str:
                raise VectorProjectionError("vector projection search identity mismatch")
            scores.append((locator, float(1.0 - raw_distance)))
        return rank_portable_scores(
            tuple(scores),
            adapter_id=SQLITE_VEC_ADAPTER_ID,
            top_k=top_k,
        )

    def close(self) -> None:
        self._identity = None
        self._close_connection()
        self._remove_files()

    def _insert_row(
        self,
        rowid: int,
        locator: str,
        vector: tuple[float, ...],
    ) -> None:
        connection = self._require_connection()
        connection.execute(
            "INSERT INTO vector_rows(rowid, embedding) VALUES (?, ?)",
            (rowid, self._serialize_float32(list(vector))),
        )
        connection.execute(
            "INSERT INTO projection_rows(rowid, stable_locator_id) VALUES (?, ?)",
            (rowid, locator),
        )

    def _read_identity(self) -> ProjectionIdentity | None:
        if self._connection is None:
            return None
        table = self._connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='projection_identity'"
        ).fetchone()
        if table is None:
            return None
        row = self._connection.execute(
            "SELECT identity_json FROM projection_identity"
        ).fetchone()
        if row is None or type(row[0]) is not str:
            return None
        try:
            raw_payload = json.loads(row[0])
            if not isinstance(raw_payload, dict):
                return None
            payload = cast(dict[object, object], raw_payload)
            return ProjectionIdentity(
                adapter_id=_identity_string(payload, "adapter_id"),
                model_fingerprint=_identity_string(payload, "model_fingerprint"),
                dimension=_identity_integer(payload, "dimension"),
                row_count=_identity_integer(payload, "row_count"),
                locator_digest=_identity_string(payload, "locator_digest"),
                source_text_digest=_identity_string(payload, "source_text_digest"),
                vector_digest=_identity_string(payload, "vector_digest"),
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise VectorProjectionError("vector projection is closed")
        return self._connection

    def _close_connection(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _remove_files(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            self._path.with_name(self._path.name + suffix).unlink(missing_ok=True)


def _identity_string(payload: dict[object, object], key: str) -> str:
    value = payload.get(key)
    if type(value) is not str or not value:
        raise ValueError("invalid projection identity")
    return value


def _identity_integer(payload: dict[object, object], key: str) -> int:
    value = payload.get(key)
    if type(value) is not int or value <= 0:
        raise ValueError("invalid projection identity")
    return value
