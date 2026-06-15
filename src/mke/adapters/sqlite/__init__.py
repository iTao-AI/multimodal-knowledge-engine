"""SQLite domain-truth adapter and active FTS5 projection."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Self
from uuid import uuid4

from mke.domain import (
    ActivationResult,
    CandidateEvidence,
    FailurePoint,
    RunEvent,
    RunManifest,
    RunRecord,
    RunState,
    SearchResult,
    SourceRecord,
    validate_manifest,
)

_BUSY_TIMEOUT_MS = 5000


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class InjectedStorageFailure(RuntimeError):
    """Raised by deterministic reliability proof failure injection."""


class SQLiteStore:
    """Persistence adapter for Source-level Publication semantics."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.db_path)
        self._connection.row_factory = sqlite3.Row
        self._configure()
        self.migrate()
        self.interrupt_unfinished_runs()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def _configure(self) -> None:
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        self._probe_fts5()

    def _probe_fts5(self) -> None:
        self._connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS temp.fts5_probe USING fts5(value)"
        )
        self._connection.execute("DROP TABLE temp.fts5_probe")

    def migrate(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS libraries (
              library_id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS assets (
              asset_id TEXT PRIMARY KEY,
              sha256 TEXT NOT NULL UNIQUE,
              media_type TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sources (
              source_id TEXT PRIMARY KEY,
              library_id TEXT NOT NULL REFERENCES libraries(library_id),
              asset_id TEXT NOT NULL REFERENCES assets(asset_id),
              display_name TEXT NOT NULL,
              active_publication_id TEXT,
              active_revision INTEGER NOT NULL DEFAULT 0,
              requested_generation INTEGER NOT NULL DEFAULT 0,
              UNIQUE(library_id, asset_id)
            );

            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY,
              source_id TEXT NOT NULL REFERENCES sources(source_id),
              state TEXT NOT NULL,
              source_generation INTEGER NOT NULL,
              based_on_active_revision INTEGER NOT NULL,
              retry_of_run_id TEXT REFERENCES runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS run_manifests (
              run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
              evidence_count INTEGER NOT NULL,
              required_stages TEXT NOT NULL,
              extractor_fingerprint TEXT NOT NULL,
              asset_sha256 TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evidence (
              evidence_id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL REFERENCES runs(run_id),
              source_id TEXT NOT NULL REFERENCES sources(source_id),
              locator_kind TEXT NOT NULL,
              locator_start INTEGER NOT NULL,
              locator_end INTEGER NOT NULL,
              text TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS publications (
              publication_id TEXT PRIMARY KEY,
              source_id TEXT NOT NULL REFERENCES sources(source_id),
              run_id TEXT NOT NULL UNIQUE REFERENCES runs(run_id),
              revision INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS run_events (
              event_id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL REFERENCES runs(run_id),
              event_index INTEGER NOT NULL,
              event_type TEXT NOT NULL
            );
            """
        )
        self._connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS active_evidence_fts USING fts5(
              library_id UNINDEXED,
              source_id UNINDEXED,
              publication_id UNINDEXED,
              evidence_id UNINDEXED,
              locator_label UNINDEXED,
              text
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_evidence_run_id ON evidence(run_id)"
        )
        self._ensure_column("runs", "retry_of_run_id", "TEXT REFERENCES runs(run_id)")
        self._ensure_column("run_events", "event_index", "INTEGER NOT NULL DEFAULT 0")
        self._connection.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {
            str(row["name"])
            for row in self._connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def ensure_default_library(self) -> str:
        row = self._connection.execute(
            "SELECT library_id FROM libraries WHERE name = ?", ("default",)
        ).fetchone()
        if row is not None:
            return str(row["library_id"])
        library_id = _new_id("lib")
        self._connection.execute(
            "INSERT INTO libraries(library_id, name) VALUES (?, ?)", (library_id, "default")
        )
        self._connection.commit()
        return library_id

    def get_first_source(self) -> SourceRecord | None:
        row = self._connection.execute(
            """
            SELECT source_id, active_publication_id, active_revision, requested_generation
            FROM sources ORDER BY rowid LIMIT 1
            """
        ).fetchone()
        return _source_from_row(row) if row is not None else None

    def get_source(self, source_id: str) -> SourceRecord:
        row = self._connection.execute(
            """
            SELECT source_id, active_publication_id, active_revision, requested_generation
            FROM sources WHERE source_id = ?
            """,
            (source_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown source: {source_id}")
        return _source_from_row(row)

    def ensure_source(self, display_name: str, asset_sha256: str) -> SourceRecord:
        library_id = self.ensure_default_library()
        asset_id = self._ensure_asset(asset_sha256)
        row = self._connection.execute(
            """
            SELECT source_id, active_publication_id, active_revision, requested_generation
            FROM sources WHERE library_id = ? AND asset_id = ?
            """,
            (library_id, asset_id),
        ).fetchone()
        if row is None:
            source_id = _new_id("src")
            self._connection.execute(
                """
                INSERT INTO sources(
                  source_id, library_id, asset_id, display_name,
                  active_publication_id, active_revision, requested_generation
                ) VALUES (?, ?, ?, ?, NULL, 0, 0)
                """,
                (source_id, library_id, asset_id, display_name),
            )
            self._connection.commit()
            return SourceRecord(source_id, None, 0, 0)
        return _source_from_row(row)

    def _ensure_asset(self, asset_sha256: str) -> str:
        row = self._connection.execute(
            "SELECT asset_id FROM assets WHERE sha256 = ?", (asset_sha256,)
        ).fetchone()
        if row is not None:
            return str(row["asset_id"])
        asset_id = _new_id("asset")
        self._connection.execute(
            "INSERT INTO assets(asset_id, sha256, media_type) VALUES (?, ?, ?)",
            (asset_id, asset_sha256, "application/pdf"),
        )
        self._connection.commit()
        return asset_id

    def create_run(self, source_id: str, retry_of_run_id: str | None = None) -> RunRecord:
        with self._connection:
            source = self._connection.execute(
                "SELECT active_revision, requested_generation FROM sources WHERE source_id = ?",
                (source_id,),
            ).fetchone()
            if source is None:
                raise KeyError(f"unknown source: {source_id}")
            source_generation = int(source["requested_generation"]) + 1
            based_on_active_revision = int(source["active_revision"])
            self._connection.execute(
                "UPDATE sources SET requested_generation = ? WHERE source_id = ?",
                (source_generation, source_id),
            )
            run_id = _new_id("run")
            self._connection.execute(
                """
                INSERT INTO runs(
                  run_id, source_id, state, source_generation, based_on_active_revision,
                  retry_of_run_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    source_id,
                    RunState.QUEUED.value,
                    source_generation,
                    based_on_active_revision,
                    retry_of_run_id,
                ),
            )
            self._append_event(run_id, "run_created")
        return RunRecord(
            run_id,
            source_id,
            RunState.QUEUED,
            source_generation,
            based_on_active_revision,
            retry_of_run_id,
        )

    def get_run(self, run_id: str) -> RunRecord:
        row = self._connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown run: {run_id}")
        return _run_from_row(row)

    def mark_run_failed(self, run_id: str) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE runs SET state = ? WHERE run_id = ?", (RunState.FAILED.value, run_id)
            )
            self._append_event(run_id, "run_failed")

    def mark_run_running(self, run_id: str) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE runs SET state = ? WHERE run_id = ?", (RunState.RUNNING.value, run_id)
            )
            self._append_event(run_id, "run_started")

    def interrupt_unfinished_runs(self) -> None:
        rows = self._connection.execute(
            "SELECT run_id FROM runs WHERE state IN (?, ?)",
            (RunState.QUEUED.value, RunState.RUNNING.value),
        ).fetchall()
        with self._connection:
            for row in rows:
                run_id = str(row["run_id"])
                self._connection.execute(
                    "UPDATE runs SET state = ? WHERE run_id = ?",
                    (RunState.INTERRUPTED.value, run_id),
                )
                self._append_event(run_id, "run_interrupted")

    def persist_validated_candidate(
        self,
        run_id: str,
        evidence: list[CandidateEvidence],
        manifest: RunManifest,
        failure_point: FailurePoint | None = None,
    ) -> None:
        validate_manifest(manifest, evidence)
        run = self.get_run(run_id)
        with self._connection:
            self._connection.execute("DELETE FROM evidence WHERE run_id = ?", (run_id,))
            if failure_point == FailurePoint.DURING_CANDIDATE_WRITES:
                raise InjectedStorageFailure(failure_point.value)
            for item in evidence:
                self._connection.execute(
                    """
                    INSERT INTO evidence(
                      evidence_id, run_id, source_id, locator_kind, locator_start, locator_end, text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.evidence_id,
                        run_id,
                        run.source_id,
                        item.locator_kind,
                        item.locator_start,
                        item.locator_end,
                        item.text,
                    ),
                )
            self._connection.execute(
                """
                INSERT OR REPLACE INTO run_manifests(
                  run_id, evidence_count, required_stages, extractor_fingerprint, asset_sha256
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    manifest.run_id,
                    manifest.evidence_count,
                    ",".join(manifest.required_stages),
                    manifest.extractor_fingerprint,
                    manifest.asset_sha256,
                ),
            )
            self._connection.execute(
                "UPDATE runs SET state = ? WHERE run_id = ?", (RunState.VALIDATED.value, run_id)
            )
            self._append_event(run_id, "candidate_validated")

    def activate_publication(
        self, run_id: str, failure_point: FailurePoint | None = None
    ) -> ActivationResult:
        with self._connection:
            run_row = self._connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if run_row is None:
                raise KeyError(f"unknown run: {run_id}")
            run = _run_from_row(run_row)
            source_row = self._connection.execute(
                "SELECT * FROM sources WHERE source_id = ?", (run.source_id,)
            ).fetchone()
            if source_row is None:
                raise KeyError(f"unknown source: {run.source_id}")
            source = _source_from_row(source_row)
            if (
                run.state != RunState.VALIDATED
                or run.source_generation != source.requested_generation
                or run.based_on_active_revision != source.active_revision
            ):
                self._connection.execute(
                    "UPDATE runs SET state = ? WHERE run_id = ?",
                    (RunState.SUPERSEDED.value, run_id),
                )
                self._append_event(run_id, "run_superseded")
                return ActivationResult(run_id, RunState.SUPERSEDED, False, None)

            evidence_rows = self._connection.execute(
                "SELECT * FROM evidence WHERE run_id = ? ORDER BY locator_start, evidence_id",
                (run_id,),
            ).fetchall()
            publication_id = _new_id("pub")
            next_revision = source.active_revision + 1
            self._connection.execute(
                """
                INSERT INTO publications(publication_id, source_id, run_id, revision)
                VALUES (?, ?, ?, ?)
                """,
                (publication_id, run.source_id, run_id, next_revision),
            )
            if failure_point == FailurePoint.AFTER_PUBLICATION_INSERT:
                raise InjectedStorageFailure(failure_point.value)
            self._connection.execute(
                "DELETE FROM active_evidence_fts WHERE source_id = ?", (run.source_id,)
            )
            if failure_point == FailurePoint.DURING_ACTIVE_FTS_REPLACEMENT:
                raise InjectedStorageFailure(failure_point.value)
            library_id = str(source_row["library_id"])
            for row in evidence_rows:
                self._connection.execute(
                    """
                    INSERT INTO active_evidence_fts(
                      library_id, source_id, publication_id, evidence_id, locator_label, text
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        library_id,
                        run.source_id,
                        publication_id,
                        str(row["evidence_id"]),
                        f"page:{int(row['locator_start'])}",
                        str(row["text"]),
                    ),
                )
            self._connection.execute(
                """
                UPDATE sources
                SET active_publication_id = ?, active_revision = ?
                WHERE source_id = ?
                """,
                (publication_id, next_revision, run.source_id),
            )
            if failure_point == FailurePoint.AFTER_ACTIVE_POINTER_SWITCH:
                raise InjectedStorageFailure(failure_point.value)
            self._connection.execute(
                "UPDATE runs SET state = ? WHERE run_id = ?", (RunState.PUBLISHED.value, run_id)
            )
            self._append_event(run_id, "publication_activated")
        return ActivationResult(run_id, RunState.PUBLISHED, True, publication_id)

    def get_run_events(self, run_id: str) -> list[RunEvent]:
        rows = self._connection.execute(
            """
            SELECT run_id, event_index, event_type
            FROM run_events
            WHERE run_id = ?
            ORDER BY event_index
            """,
            (run_id,),
        ).fetchall()
        return [
            RunEvent(
                run_id=str(row["run_id"]),
                event_index=int(row["event_index"]),
                event_type=str(row["event_type"]),
            )
            for row in rows
        ]

    def _append_event(self, run_id: str, event_type: str) -> None:
        row = self._connection.execute(
            """
            SELECT COALESCE(MAX(event_index), 0) + 1 AS next_index
            FROM run_events
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        event_index = int(row["next_index"]) if row is not None else 1
        self._connection.execute(
            """
            INSERT INTO run_events(event_id, run_id, event_index, event_type)
            VALUES (?, ?, ?, ?)
            """,
            (_new_id("evt"), run_id, event_index, event_type),
        )

    def search(self, query: str) -> list[SearchResult]:
        match_query = _to_fts_query(query)
        if not match_query:
            return []
        rows = self._connection.execute(
            """
            SELECT evidence.evidence_id, active_evidence_fts.publication_id,
                   evidence.source_id, evidence.locator_start, evidence.text
            FROM active_evidence_fts
            JOIN evidence ON evidence.evidence_id = active_evidence_fts.evidence_id
            JOIN sources ON sources.source_id = evidence.source_id
            WHERE active_evidence_fts MATCH ?
              AND sources.active_publication_id = active_evidence_fts.publication_id
            ORDER BY rank, evidence.locator_start, evidence.evidence_id
            """,
            (match_query,),
        ).fetchall()
        return [
            SearchResult(
                evidence_id=str(row["evidence_id"]),
                publication_id=str(row["publication_id"]),
                source_id=str(row["source_id"]),
                page_number=int(row["locator_start"]),
                text=str(row["text"]),
            )
            for row in rows
        ]


def _source_from_row(row: sqlite3.Row) -> SourceRecord:
    active_publication_id = row["active_publication_id"]
    return SourceRecord(
        source_id=str(row["source_id"]),
        active_publication_id=(
            str(active_publication_id) if active_publication_id is not None else None
        ),
        active_revision=int(row["active_revision"]),
        requested_generation=int(row["requested_generation"]),
    )


def _run_from_row(row: sqlite3.Row) -> RunRecord:
    retry_of_run_id = row["retry_of_run_id"]
    return RunRecord(
        run_id=str(row["run_id"]),
        source_id=str(row["source_id"]),
        state=RunState(str(row["state"])),
        source_generation=int(row["source_generation"]),
        based_on_active_revision=int(row["based_on_active_revision"]),
        retry_of_run_id=str(retry_of_run_id) if retry_of_run_id is not None else None,
    )


def _to_fts_query(query: str) -> str:
    terms = re.findall(r"[A-Za-z0-9_]+", query.casefold())
    return " ".join(f'"{term}"' for term in terms)
