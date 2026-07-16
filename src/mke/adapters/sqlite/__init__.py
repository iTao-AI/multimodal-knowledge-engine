"""SQLite domain-truth adapter and active FTS5 projection."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Self
from uuid import uuid4

from mke.domain import (
    DEFAULT_EXPORT_LIMITS,
    ActivationResult,
    ActiveEvidenceRef,
    ActivePublicationObservation,
    CandidateEvidence,
    CompiledEvidenceSnapshot,
    CompiledLibrarySnapshot,
    CompiledSourceSnapshot,
    ExportLimits,
    FailurePoint,
    LibraryExportDataError,
    ManifestValidationError,
    PdfIntakeReport,
    RunEvent,
    RunEventType,
    RunManifest,
    RunRecord,
    RunState,
    RunTransitionError,
    SearchResult,
    SearchResultProvenance,
    SearchSnapshot,
    SourceRecord,
    TranscriptIntakeReport,
    is_recognized_video_fingerprint,
    validate_manifest,
)
from mke.retrieval import (
    DEFAULT_RETRIEVAL_STRATEGY,
    RetrievalQueryPolicy,
    RetrievalStrategy,
    compile_fts5_query,
)
from mke.retrieval.cjk_active_scan import (
    CJK_ACTIVE_SCAN_PARAMETERS,
    CjkActiveScanCandidate,
    CjkActiveScanError,
    CjkActiveScanParameters,
    compile_cjk_overlap_terms,
    rank_cjk_active_scan_candidates,
)
from mke.retrieval.query_policy import require_retrieval_query_policy
from mke.retrieval.strategy import (
    get_retrieval_strategy_descriptor,
    require_retrieval_strategy,
)

if TYPE_CHECKING:
    from mke.evaluation.diagnostic_ports import (
        EvaluationEvidenceSnapshot,
        FtsProjectionSnapshot,
        FtsRankObservation,
        FtsRankProfile,
    )

_BUSY_TIMEOUT_MS = 5000

_EXPORT_SCHEMA: dict[str, dict[str, tuple[str, int, int]]] = {
    "libraries": {
        "library_id": ("TEXT", 0, 1),
        "name": ("TEXT", 1, 0),
    },
    "assets": {
        "asset_id": ("TEXT", 0, 1),
        "sha256": ("TEXT", 1, 0),
        "media_type": ("TEXT", 1, 0),
    },
    "sources": {
        "source_id": ("TEXT", 0, 1),
        "library_id": ("TEXT", 1, 0),
        "asset_id": ("TEXT", 1, 0),
        "display_name": ("TEXT", 1, 0),
        "active_publication_id": ("TEXT", 0, 0),
        "active_revision": ("INTEGER", 1, 0),
    },
    "runs": {
        "run_id": ("TEXT", 0, 1),
        "source_id": ("TEXT", 1, 0),
        "state": ("TEXT", 1, 0),
    },
    "run_manifests": {
        "run_id": ("TEXT", 0, 1),
        "evidence_count": ("INTEGER", 1, 0),
        "required_stages": ("TEXT", 1, 0),
        "extractor_fingerprint": ("TEXT", 1, 0),
        "asset_sha256": ("TEXT", 1, 0),
    },
    "evidence": {
        "evidence_id": ("TEXT", 0, 1),
        "run_id": ("TEXT", 1, 0),
        "source_id": ("TEXT", 1, 0),
        "locator_kind": ("TEXT", 1, 0),
        "locator_start": ("INTEGER", 1, 0),
        "locator_end": ("INTEGER", 1, 0),
        "text": ("TEXT", 1, 0),
    },
    "publications": {
        "publication_id": ("TEXT", 0, 1),
        "source_id": ("TEXT", 1, 0),
        "run_id": ("TEXT", 1, 0),
        "revision": ("INTEGER", 1, 0),
    },
}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class InjectedStorageFailure(RuntimeError):
    """Raised by deterministic reliability proof failure injection."""


class SQLiteStore:
    """Persistence adapter for Source-level Publication semantics."""

    def __init__(
        self,
        db_path: Path,
        *,
        query_policy: RetrievalQueryPolicy | None = None,
        retrieval_strategy: RetrievalStrategy | None = None,
        search_observer: Callable[[int], None] | None = None,
        _read_only_export: bool = False,
    ) -> None:
        self.db_path = db_path
        if retrieval_strategy is None:
            self._retrieval_strategy = require_retrieval_strategy(
                require_retrieval_query_policy(query_policy)
                if query_policy is not None
                else DEFAULT_RETRIEVAL_STRATEGY
            )
        else:
            self._retrieval_strategy = require_retrieval_strategy(retrieval_strategy)
        descriptor = get_retrieval_strategy_descriptor(self._retrieval_strategy)
        self._query_policy: RetrievalQueryPolicy = require_retrieval_query_policy(
            descriptor.base_query_policy
        )
        self._search_observer = search_observer
        if _read_only_export:
            self._open_read_only_export()
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.db_path)
        self._connection.row_factory = sqlite3.Row
        self._configure()
        self.migrate()

    @classmethod
    def open_read_only_export(cls, db_path: Path) -> SQLiteStore:
        return cls(db_path, _read_only_export=True)

    def _open_read_only_export(self) -> None:
        uri = self.db_path.absolute().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, autocommit=False)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA query_only = ON")
            self._connection = connection
            self._validate_export_schema()
        except Exception:
            connection.close()
            raise

    def _validate_export_schema(self) -> None:
        query_only = self._connection.execute("PRAGMA query_only").fetchone()
        encoding = self._connection.execute("PRAGMA encoding").fetchone()
        if query_only is None or query_only[0] != 1 or encoding is None or encoding[0] != "UTF-8":
            raise LibraryExportDataError("provenance")
        for table, expected_columns in _EXPORT_SCHEMA.items():
            actual_columns = {
                str(row["name"]): (
                    str(row["type"]).upper(),
                    int(row["notnull"]),
                    int(row["pk"]),
                )
                for row in self._connection.execute(
                    f"PRAGMA table_xinfo({table})"
                ).fetchall()
            }
            if any(
                actual_columns.get(column) != expected
                for column, expected in expected_columns.items()
            ):
                raise LibraryExportDataError("provenance")

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
        self._connection.autocommit = False  # Explicit: PEP 249 tx semantics (rollback-safe)
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

            -- Rollback: deploy code that stops reading/writing this table,
            -- then DROP TABLE IF EXISTS pdf_intake_reports locally.
            CREATE TABLE IF NOT EXISTS pdf_intake_reports (
              run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
              total_pages INTEGER NOT NULL,
              extracted_pages INTEGER NOT NULL,
              empty_pages INTEGER NOT NULL,
              total_extracted_chars INTEGER NOT NULL,
              page_char_counts TEXT NOT NULL,
              suspected_scanned_pages INTEGER NOT NULL,
              extraction_mode TEXT NOT NULL,
              failure_reason TEXT
            );

            CREATE TABLE IF NOT EXISTS transcript_intake_reports (
              run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
              provider TEXT NOT NULL CHECK(length(provider) BETWEEN 1 AND 256),
              model TEXT NOT NULL CHECK(length(model) BETWEEN 1 AND 256),
              model_revision TEXT NOT NULL CHECK(length(model_revision) BETWEEN 1 AND 256),
              library_version TEXT NOT NULL CHECK(length(library_version) BETWEEN 1 AND 256),
              device TEXT NOT NULL CHECK(length(device) BETWEEN 1 AND 256),
              compute_type TEXT NOT NULL CHECK(length(compute_type) BETWEEN 1 AND 256),
              language TEXT NOT NULL CHECK(length(language) BETWEEN 2 AND 4),
              detected_language TEXT NOT NULL CHECK(length(detected_language) BETWEEN 2 AND 4),
              media_duration_ms INTEGER NOT NULL CHECK(media_duration_ms > 0),
              transcription_duration_ms INTEGER NOT NULL
                CHECK(transcription_duration_ms >= 0),
              segment_count INTEGER NOT NULL CHECK(segment_count > 0),
              model_source TEXT NOT NULL CHECK(model_source = 'cache')
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
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_retry_of_run_id ON runs(retry_of_run_id)"
        )
        self._connection.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        """Add a column if it does not already exist.

        WARNING: ``table`` and ``column`` must be hardcoded string literals, never
        caller-controlled input. This method uses f-string interpolation for SQL
        identifiers because SQLite PRAGMA and ALTER TABLE do not accept bound
        parameters for them.
        """
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

    def ensure_source(
        self, display_name: str, asset_sha256: str, media_type: str = "application/pdf"
    ) -> SourceRecord:
        library_id = self.ensure_default_library()
        asset_id = self._ensure_asset(asset_sha256, media_type)
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

    def _ensure_asset(self, asset_sha256: str, media_type: str) -> str:
        row = self._connection.execute(
            "SELECT asset_id FROM assets WHERE sha256 = ?", (asset_sha256,)
        ).fetchone()
        if row is not None:
            return str(row["asset_id"])
        asset_id = _new_id("asset")
        self._connection.execute(
            "INSERT INTO assets(asset_id, sha256, media_type) VALUES (?, ?, ?)",
            (asset_id, asset_sha256, media_type),
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
            self._append_event(run_id, RunEventType.RUN_CREATED)
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

    def persist_pdf_intake_report(self, run_id: str, report: PdfIntakeReport) -> None:
        self._connection.execute(
            """
            INSERT OR REPLACE INTO pdf_intake_reports(
              run_id, total_pages, extracted_pages, empty_pages, total_extracted_chars,
              page_char_counts, suspected_scanned_pages, extraction_mode, failure_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                report.total_pages,
                report.extracted_pages,
                report.empty_pages,
                report.total_extracted_chars,
                json.dumps(list(report.page_char_counts), separators=(",", ":")),
                report.suspected_scanned_pages,
                report.extraction_mode,
                report.failure_reason,
            ),
        )
        self._connection.commit()

    def get_pdf_intake_report(self, run_id: str) -> PdfIntakeReport | None:
        row = self._connection.execute(
            """
            SELECT total_pages, extracted_pages, empty_pages, total_extracted_chars,
                   page_char_counts, suspected_scanned_pages, extraction_mode, failure_reason
            FROM pdf_intake_reports WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return PdfIntakeReport(
            total_pages=int(row["total_pages"]),
            extracted_pages=int(row["extracted_pages"]),
            empty_pages=int(row["empty_pages"]),
            total_extracted_chars=int(row["total_extracted_chars"]),
            page_char_counts=tuple(
                int(value) for value in json.loads(str(row["page_char_counts"]))
            ),
            suspected_scanned_pages=int(row["suspected_scanned_pages"]),
            extraction_mode=str(row["extraction_mode"]),
            failure_reason=(
                str(row["failure_reason"]) if row["failure_reason"] is not None else None
            ),
        )

    def mark_run_failed(self, run_id: str) -> None:
        with self._connection:
            self._transition_run(
                run_id,
                expected=(RunState.QUEUED, RunState.RUNNING),
                target=RunState.FAILED,
                event_type=RunEventType.RUN_FAILED,
            )

    def mark_run_running(self, run_id: str) -> None:
        with self._connection:
            self._transition_run(
                run_id,
                expected=(RunState.QUEUED,),
                target=RunState.RUNNING,
                event_type=RunEventType.RUN_STARTED,
            )

    def interrupt_unfinished_runs(self) -> None:
        with self._connection:
            rows = self._connection.execute(
                "SELECT run_id FROM runs WHERE state IN (?, ?)",
                (RunState.QUEUED.value, RunState.RUNNING.value),
            ).fetchall()
            for row in rows:
                run_id = str(row["run_id"])
                self._transition_run(
                    run_id,
                    expected=(RunState.QUEUED, RunState.RUNNING),
                    target=RunState.INTERRUPTED,
                    event_type=RunEventType.RUN_INTERRUPTED,
                )

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
            self._transition_run(
                run_id,
                expected=(RunState.RUNNING,),
                target=RunState.VALIDATED,
                event_type=RunEventType.CANDIDATE_VALIDATED,
            )

    def activate_publication(
        self,
        run_id: str,
        failure_point: FailurePoint | None = None,
        *,
        transcript_intake_report: TranscriptIntakeReport | None = None,
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
            if run.state != RunState.VALIDATED:
                raise ManifestValidationError("Run must be validated before activation")
            if (
                run.source_generation != source.requested_generation
                or run.based_on_active_revision != source.active_revision
            ):
                self._transition_run(
                    run_id,
                    expected=(RunState.VALIDATED,),
                    target=RunState.SUPERSEDED,
                    event_type=RunEventType.RUN_SUPERSEDED,
                )
                return ActivationResult(run_id, RunState.SUPERSEDED, False, None)

            manifest_row = self._connection.execute(
                "SELECT extractor_fingerprint FROM run_manifests WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if manifest_row is None:
                raise KeyError(f"missing RunManifest for Run: {run_id}")
            fingerprint = str(manifest_row["extractor_fingerprint"])
            is_faster_whisper = (
                fingerprint.startswith("faster-whisper-v1:")
                and is_recognized_video_fingerprint(fingerprint)
            )
            if is_faster_whisper and transcript_intake_report is None:
                raise ManifestValidationError(
                    "faster-whisper Publication requires a successful transcript intake report"
                )
            if (
                transcript_intake_report is not None
                and transcript_intake_report.provider != "faster-whisper"
            ):
                raise ManifestValidationError(
                    "transcript intake report provider must be faster-whisper"
                )

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
                locator_kind = str(row["locator_kind"])
                locator_start = int(row["locator_start"])
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
                        _locator_label(locator_kind, locator_start, int(row["locator_end"])),
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
            if transcript_intake_report is not None:
                self._insert_transcript_intake_report(run_id, transcript_intake_report)
            self._transition_run(
                run_id,
                expected=(RunState.VALIDATED,),
                target=RunState.PUBLISHED,
                event_type=RunEventType.PUBLICATION_ACTIVATED,
            )
        return ActivationResult(run_id, RunState.PUBLISHED, True, publication_id)

    def _insert_transcript_intake_report(
        self, run_id: str, report: TranscriptIntakeReport
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO transcript_intake_reports(
              run_id, provider, model, model_revision, library_version, device,
              compute_type, language, detected_language, media_duration_ms,
              transcription_duration_ms, segment_count, model_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                report.provider,
                report.model,
                report.model_revision,
                report.library_version,
                report.device,
                report.compute_type,
                report.language,
                report.detected_language,
                report.media_duration_ms,
                report.transcription_duration_ms,
                report.segment_count,
                report.model_source,
            ),
        )

    def get_transcript_intake_report(
        self, run_id: str
    ) -> TranscriptIntakeReport | None:
        row = self._connection.execute(
            """
            SELECT provider, model, model_revision, library_version, device,
                   compute_type, language, detected_language, media_duration_ms,
                   transcription_duration_ms, segment_count, model_source
            FROM transcript_intake_reports
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return TranscriptIntakeReport(
            provider=str(row["provider"]),
            model=str(row["model"]),
            model_revision=str(row["model_revision"]),
            library_version=str(row["library_version"]),
            device=str(row["device"]),
            compute_type=str(row["compute_type"]),
            language=str(row["language"]),
            detected_language=str(row["detected_language"]),
            media_duration_ms=int(row["media_duration_ms"]),
            transcription_duration_ms=int(row["transcription_duration_ms"]),
            segment_count=int(row["segment_count"]),
            model_source=str(row["model_source"]),
        )

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

    def _transition_run(
        self,
        run_id: str,
        *,
        expected: tuple[RunState, ...],
        target: RunState,
        event_type: str,
    ) -> None:
        slots = ",".join("?" for _ in expected)
        cursor = self._connection.execute(
            f"UPDATE runs SET state = ? WHERE run_id = ? AND state IN ({slots})",
            (target.value, run_id, *(state.value for state in expected)),
        )
        if cursor.rowcount != 1:
            row = self._connection.execute(
                "SELECT state FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown run: {run_id}")
            raise RunTransitionError(
                run_id,
                expected=expected,
                actual=RunState(str(row["state"])),
                target=target,
            )
        self._append_event(run_id, event_type)

    def list_active_evidence(self) -> list[ActiveEvidenceRef]:
        rows = self._connection.execute(
            """
            SELECT evidence.source_id, evidence.locator_kind,
                   evidence.locator_start, evidence.locator_end
            FROM sources
            JOIN publications
              ON publications.publication_id = sources.active_publication_id
            JOIN evidence
              ON evidence.run_id = publications.run_id
             AND evidence.source_id = sources.source_id
            ORDER BY evidence.source_id, evidence.locator_kind,
                     evidence.locator_start, evidence.locator_end
            """
        ).fetchall()
        return [
            ActiveEvidenceRef(
                source_id=str(row["source_id"]),
                locator_kind=str(row["locator_kind"]),
                locator_start=int(row["locator_start"]),
                locator_end=int(row["locator_end"]),
            )
            for row in rows
        ]

    def list_evaluation_evidence(
        self,
    ) -> tuple[EvaluationEvidenceSnapshot, ...]:
        from mke.evaluation.diagnostic_ports import EvaluationEvidenceSnapshot

        rows = self._connection.execute(
            """
            SELECT evidence.evidence_id, publications.publication_id,
                   evidence.source_id, evidence.locator_kind,
                   evidence.locator_start, evidence.locator_end, evidence.text
            FROM sources
            JOIN publications
              ON publications.publication_id = sources.active_publication_id
            JOIN evidence
              ON evidence.run_id = publications.run_id
             AND evidence.source_id = sources.source_id
            ORDER BY evidence.source_id, evidence.locator_kind,
                     evidence.locator_start, evidence.locator_end,
                     evidence.evidence_id
            """
        ).fetchall()
        return tuple(
            EvaluationEvidenceSnapshot(
                evidence_id=str(row["evidence_id"]),
                publication_id=str(row["publication_id"]),
                source_id=str(row["source_id"]),
                locator_kind=str(row["locator_kind"]),
                locator_start=int(row["locator_start"]),
                locator_end=int(row["locator_end"]),
                text=str(row["text"]),
            )
            for row in rows
        )

    def list_fts_projection(self) -> tuple[FtsProjectionSnapshot, ...]:
        from mke.evaluation.diagnostic_ports import FtsProjectionSnapshot

        rows = self._connection.execute(
            """
            SELECT evidence_id, publication_id, source_id, locator_label, text
            FROM active_evidence_fts
            ORDER BY source_id, locator_label, evidence_id, rowid
            """
        ).fetchall()
        return tuple(
            FtsProjectionSnapshot(
                evidence_id=str(row["evidence_id"]),
                publication_id=str(row["publication_id"]),
                source_id=str(row["source_id"]),
                locator_label=str(row["locator_label"]),
                text_sha256=sha256(str(row["text"]).encode("utf-8")).hexdigest(),
            )
            for row in rows
        )

    def observe_fts5_rank(self, compiled_query: str) -> FtsRankProfile:
        from mke.evaluation.diagnostic_ports import (
            FtsRankObservation,
            FtsRankProfile,
        )

        if (
            type(compiled_query) is not str
            or not compiled_query.strip()
            or len(compiled_query) > 10_000
            or any(ord(character) < 32 for character in compiled_query)
        ):
            raise ValueError("compiled query is invalid")
        base = """
            SELECT evidence.evidence_id, evidence.locator_start, {score} AS score
            FROM active_evidence_fts
            JOIN evidence ON evidence.evidence_id = active_evidence_fts.evidence_id
            JOIN sources ON sources.source_id = evidence.source_id
            WHERE active_evidence_fts MATCH ?
              AND sources.active_publication_id = active_evidence_fts.publication_id
            ORDER BY {score}, evidence.locator_start, evidence.evidence_id
        """
        statements: list[str] = []
        self._connection.set_trace_callback(statements.append)
        try:
            rank_rows = self._connection.execute(
                base.format(score="rank"), (compiled_query,)
            ).fetchall()
            bm25_rows = self._connection.execute(
                base.format(score="bm25(active_evidence_fts)"),
                (compiled_query,),
            ).fetchall()
            override = self._connection.execute(
                "SELECT 1 FROM active_evidence_fts_config "
                "WHERE k = 'rank' LIMIT 1"
            ).fetchone()
        finally:
            self._connection.set_trace_callback(None)
        rank_scores = {
            str(row["evidence_id"]): float(row["score"]) for row in rank_rows
        }
        bm25_scores = {
            str(row["evidence_id"]): float(row["score"]) for row in bm25_rows
        }

        def observation(row: sqlite3.Row) -> FtsRankObservation:
            evidence_id = str(row["evidence_id"])
            return FtsRankObservation(
                evidence_id=evidence_id,
                locator_start=int(row["locator_start"]),
                rank_score=rank_scores[evidence_id],
                bm25_score=bm25_scores[evidence_id],
            )

        return FtsRankProfile(
            rank_order=tuple(observation(row) for row in rank_rows),
            bm25_order=tuple(observation(row) for row in bm25_rows),
            rank_override_present=override is not None,
            sql_trace=tuple(statements),
        )

    def schema_sha256(self) -> str:
        rows = self._connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_master
            WHERE sql IS NOT NULL
              AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name, tbl_name, sql
            """
        ).fetchall()
        payload = [
            {
                "type": str(row["type"]),
                "name": str(row["name"]),
                "table": str(row["tbl_name"]),
                "sql": str(row["sql"]),
            }
            for row in rows
        ]
        return sha256(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()

    def search(self, query: str, limit: int | None = None) -> list[SearchResult]:
        match_query = compile_fts5_query(query, policy=self._query_policy)
        if match_query:
            return self._search_fts(match_query, limit=limit)
        if self._retrieval_strategy == "cjk-active-scan-overlap-v1":
            return self.search_cjk_active_scan(query, limit=limit)
        return []

    def observe_active_publications(self) -> ActivePublicationObservation:
        try:
            observation = self._observe_active_publications()
            self._connection.commit()
            return observation
        except Exception:
            self._connection.rollback()
            raise

    def _observe_active_publications(self) -> ActivePublicationObservation:
        observation, _ = self._read_and_validate_active_publication_rows()
        return observation

    def _read_and_validate_active_publication_rows(
        self,
    ) -> tuple[ActivePublicationObservation, list[sqlite3.Row]]:
        library_error = "implicit local Library ownership is invalid"
        graph_error = "active Publication provenance graph is invalid"
        libraries = self._connection.execute(
            "SELECT library_id, name FROM libraries ORDER BY library_id"
        ).fetchall()
        if not libraries:
            return ActivePublicationObservation("local", "empty", 0, 0, 0), []
        for library in libraries:
            self._require_sqlite_text(library["library_id"], library_error)
            self._require_sqlite_text(library["name"], library_error)
        if (
            len(libraries) != 1
            or libraries[0]["name"] != "default"
        ):
            raise ManifestValidationError(library_error)
        library_id = self._require_sqlite_text(libraries[0]["library_id"], library_error)
        source_counts = self._connection.execute(
            """
            SELECT COUNT(*) AS source_count,
                   COALESCE(SUM(CASE WHEN library_id = ? THEN 1 ELSE 0 END), 0)
                     AS owned_source_count,
                   COALESCE(SUM(
                     CASE WHEN active_publication_id IS NOT NULL THEN 1 ELSE 0 END
                   ), 0)
                     AS active_pointer_count
            FROM sources
            """,
            (library_id,),
        ).fetchone()
        assert source_counts is not None
        source_count = self._require_sqlite_int(
            source_counts["source_count"], library_error
        )
        owned_source_count = self._require_sqlite_int(
            source_counts["owned_source_count"], library_error
        )
        active_pointer_count = self._require_sqlite_int(
            source_counts["active_pointer_count"], graph_error
        )
        if owned_source_count != source_count:
            raise ManifestValidationError(library_error)
        rows = self._connection.execute(
            """
            SELECT sources.source_id, sources.library_id, sources.active_publication_id,
                   sources.active_revision, sources.display_name,
                   assets.sha256 AS source_sha256, assets.media_type,
                   publications.publication_id, publications.source_id AS publication_source_id,
                   publications.run_id, publications.revision,
                   runs.source_id AS run_source_id, runs.state,
                   run_manifests.asset_sha256 AS manifest_sha256,
                   run_manifests.evidence_count AS manifest_evidence_count,
                   run_manifests.required_stages, run_manifests.extractor_fingerprint,
                   COUNT(evidence.evidence_id) AS evidence_count,
                   SUM(CASE WHEN evidence.source_id = sources.source_id
                                  AND evidence.run_id = publications.run_id THEN 0 ELSE 1 END)
                       AS evidence_mismatch_count
            FROM sources
            LEFT JOIN assets ON assets.asset_id = sources.asset_id
            LEFT JOIN publications
              ON publications.publication_id = sources.active_publication_id
            LEFT JOIN runs ON runs.run_id = publications.run_id
            LEFT JOIN run_manifests ON run_manifests.run_id = runs.run_id
            LEFT JOIN evidence ON evidence.run_id = publications.run_id
            WHERE sources.library_id = ? AND sources.active_publication_id IS NOT NULL
            GROUP BY sources.source_id
            ORDER BY sources.source_id
            """
            ,
            (library_id,),
        ).fetchall()
        if active_pointer_count != len(rows):
            raise ManifestValidationError(graph_error)
        active_evidence_count = 0
        for row in rows:
            for field in (
                "source_id",
                "library_id",
                "active_publication_id",
                "display_name",
                "source_sha256",
                "media_type",
                "publication_id",
                "publication_source_id",
                "run_id",
                "run_source_id",
                "state",
                "manifest_sha256",
                "required_stages",
                "extractor_fingerprint",
            ):
                self._require_sqlite_text(row[field], graph_error)
            for field in (
                "active_revision",
                "revision",
                "manifest_evidence_count",
                "evidence_count",
                "evidence_mismatch_count",
            ):
                self._require_sqlite_int(row[field], graph_error)
            evidence_count = self._require_sqlite_int(row["evidence_count"], graph_error)
            valid = (
                row["library_id"] == library_id
                and row["active_publication_id"] == row["publication_id"]
                and row["source_id"] == row["publication_source_id"]
                and row["source_id"] == row["run_source_id"]
                and row["state"] == RunState.PUBLISHED.value
                and row["active_revision"] == row["revision"]
                and row["manifest_evidence_count"] == evidence_count
                and row["manifest_sha256"] == row["source_sha256"]
                and row["evidence_mismatch_count"] == 0
                and evidence_count > 0
            )
            if not valid:
                raise ManifestValidationError(graph_error)
            active_evidence_count += evidence_count
        active_publication_count = len(rows)
        if source_count == 0:
            state = "empty"
        elif active_publication_count == 0:
            state = "no_active_publication"
        else:
            state = "active"
        return ActivePublicationObservation(
            "local", state, source_count, active_publication_count, active_evidence_count
        ), rows

    def compiled_library_snapshot(
        self, *, limits: ExportLimits = DEFAULT_EXPORT_LIMITS
    ) -> CompiledLibrarySnapshot:
        try:
            observation, active_rows = self._read_and_validate_active_publication_rows()
            if observation.state != "active":
                raise LibraryExportDataError("empty")
            if len(active_rows) > limits.max_active_publications:
                raise LibraryExportDataError("too_large")
            self._validate_export_metadata(active_rows)
            evidence_count, evidence_utf8_bytes = self._preflight_export_evidence()
            if evidence_count > limits.max_active_evidence or (
                evidence_utf8_bytes > limits.max_evidence_utf8_bytes
            ):
                raise LibraryExportDataError("too_large")
            evidence_rows = self._read_export_evidence_rows()
            snapshot = self._build_compiled_library_snapshot(
                observation, active_rows, evidence_rows
            )
            self._connection.commit()
            return snapshot
        except LibraryExportDataError:
            self._connection.rollback()
            raise
        except ManifestValidationError as exc:
            self._connection.rollback()
            raise LibraryExportDataError("provenance") from exc
        except Exception:
            self._connection.rollback()
            raise

    def _validate_export_metadata(self, active_rows: list[sqlite3.Row]) -> None:
        fingerprints: set[str] = set()
        for row in active_rows:
            if row["media_type"] not in {"application/pdf", "video/mp4"}:
                raise LibraryExportDataError("provenance")
            self._parse_export_required_stages(row["required_stages"])
            fingerprint = self._require_sqlite_text(
                row["source_sha256"], "active Publication provenance graph is invalid"
            )
            if fingerprint in fingerprints:
                raise LibraryExportDataError("provenance")
            fingerprints.add(fingerprint)

    def _preflight_export_evidence(self) -> tuple[int, int]:
        row = self._connection.execute(
            """
            SELECT COUNT(*) AS evidence_count,
                   COALESCE(SUM(length(CAST(text AS BLOB))), 0)
                     AS evidence_utf8_bytes
            FROM sources
            JOIN publications
              ON publications.publication_id = sources.active_publication_id
            JOIN evidence ON evidence.run_id = publications.run_id
            """
        ).fetchone()
        assert row is not None
        error = "active Publication provenance graph is invalid"
        return (
            self._require_sqlite_int(row["evidence_count"], error),
            self._require_sqlite_int(row["evidence_utf8_bytes"], error),
        )

    def _read_export_evidence_rows(self) -> list[sqlite3.Row]:
        rows = self._connection.execute(
            """
            SELECT evidence.evidence_id, evidence.source_id, evidence.run_id,
                   evidence.locator_kind, evidence.locator_start,
                   evidence.locator_end, evidence.text,
                   publications.publication_id, publications.revision,
                   assets.sha256 AS source_sha256
            FROM evidence
            JOIN publications ON publications.run_id = evidence.run_id
            JOIN sources
              ON sources.source_id = evidence.source_id
             AND sources.active_publication_id = publications.publication_id
            JOIN assets ON assets.asset_id = sources.asset_id
            ORDER BY evidence.source_id, evidence.locator_kind,
                     evidence.locator_start, evidence.locator_end, evidence.evidence_id
            """
        ).fetchall()
        error = "active Publication provenance graph is invalid"
        for row in rows:
            for field in (
                "evidence_id",
                "source_id",
                "run_id",
                "locator_kind",
                "text",
                "publication_id",
                "source_sha256",
            ):
                self._require_sqlite_text(row[field], error)
            for field in ("locator_start", "locator_end", "revision"):
                self._require_sqlite_int(row[field], error)
        return rows

    def _build_compiled_library_snapshot(
        self,
        observation: ActivePublicationObservation,
        active_rows: list[sqlite3.Row],
        evidence_rows: list[sqlite3.Row],
    ) -> CompiledLibrarySnapshot:
        evidence_by_run: dict[str, list[sqlite3.Row]] = {}
        for evidence_row in evidence_rows:
            run_id = self._require_sqlite_text(
                evidence_row["run_id"], "active Publication provenance graph is invalid"
            )
            evidence_by_run.setdefault(run_id, []).append(evidence_row)
        sources: list[CompiledSourceSnapshot] = []
        for row in active_rows:
            error = "active Publication provenance graph is invalid"
            run_id = self._require_sqlite_text(row["run_id"], error)
            source_sha256 = self._require_sqlite_text(row["source_sha256"], error)
            content_fingerprint = f"sha256:{source_sha256}"
            publication_id = self._require_sqlite_text(row["publication_id"], error)
            publication_revision = self._require_sqlite_int(row["revision"], error)
            evidence = tuple(
                CompiledEvidenceSnapshot(
                    evidence_id=self._require_sqlite_text(
                        evidence_row["evidence_id"], error
                    ),
                    source_id=self._require_sqlite_text(
                        evidence_row["source_id"], error
                    ),
                    content_fingerprint=content_fingerprint,
                    publication_id=publication_id,
                    publication_revision=publication_revision,
                    run_id=run_id,
                    locator_kind=self._require_sqlite_text(  # type: ignore[arg-type]
                        evidence_row["locator_kind"], error
                    ),
                    locator_start=self._require_sqlite_int(
                        evidence_row["locator_start"], error
                    ),
                    locator_end=self._require_sqlite_int(
                        evidence_row["locator_end"], error
                    ),
                    text=self._require_sqlite_text(evidence_row["text"], error),
                )
                for evidence_row in evidence_by_run.get(run_id, [])
            )
            sources.append(
                CompiledSourceSnapshot(
                    source_id=self._require_sqlite_text(row["source_id"], error),
                    display_name=self._require_sqlite_text(row["display_name"], error),
                    content_fingerprint=content_fingerprint,
                    media_type=self._require_sqlite_text(  # type: ignore[arg-type]
                        row["media_type"], error
                    ),
                    publication_id=publication_id,
                    publication_revision=publication_revision,
                    run_id=run_id,
                    extractor_fingerprint=self._require_sqlite_text(
                        row["extractor_fingerprint"], error
                    ),
                    required_stages=self._parse_export_required_stages(
                        row["required_stages"]
                    ),
                    evidence=evidence,
                )
            )
        return CompiledLibrarySnapshot(
            observation,
            tuple(sorted(sources, key=lambda item: (item.content_fingerprint, item.source_id))),
        )

    @staticmethod
    def _require_sqlite_text(value: object, error: str) -> str:
        if type(value) is not str:
            raise ManifestValidationError(error)
        return value

    @staticmethod
    def _require_sqlite_int(value: object, error: str) -> int:
        if type(value) is not int:
            raise ManifestValidationError(error)
        return value

    @staticmethod
    def _parse_export_required_stages(value: object) -> tuple[str, ...]:
        if type(value) is not str or not value or any(
            marker in value for marker in ('[', ']', '"')
        ):
            raise LibraryExportDataError("provenance")
        stages = tuple(value.split(","))
        if any(not stage or stage != stage.strip() for stage in stages):
            raise LibraryExportDataError("provenance")
        if stages != tuple(sorted(stages)) or len(stages) != len(set(stages)):
            raise LibraryExportDataError("provenance")
        return stages

    def search_provenance_snapshot(
        self, query: str, limit: int | None = None
    ) -> SearchSnapshot:
        try:
            observation = self._observe_active_publications()
            results = self.search(query, limit=limit)
            enriched = self._bulk_enrich_provenance(results)
            self._connection.commit()
            return SearchSnapshot(observation, enriched)
        except Exception:
            self._connection.rollback()
            raise

    def _bulk_enrich_provenance(
        self, results: list[SearchResult]
    ) -> tuple[SearchResultProvenance, ...]:
        if not results:
            return ()
        placeholders = ",".join("?" for _ in results)
        rows = self._connection.execute(
            f"""
            SELECT evidence.evidence_id, evidence.source_id, evidence.run_id,
                   publications.publication_id, publications.revision,
                   run_manifests.asset_sha256, runs.state,
                   sources.active_publication_id, sources.active_revision,
                   sources.library_id, assets.sha256 AS source_sha256
            FROM evidence
            JOIN publications ON publications.run_id = evidence.run_id
            JOIN runs ON runs.run_id = publications.run_id
            JOIN run_manifests ON run_manifests.run_id = runs.run_id
            JOIN sources ON sources.source_id = evidence.source_id
            JOIN assets ON assets.asset_id = sources.asset_id
            WHERE evidence.evidence_id IN ({placeholders})
            """,
            [item.evidence_id for item in results],
        ).fetchall()
        by_id = {str(row["evidence_id"]): row for row in rows}
        enriched: list[SearchResultProvenance] = []
        for result in results:
            row = by_id.get(result.evidence_id)
            if row is None or not (
                row["source_id"] == result.source_id
                and row["publication_id"] == result.publication_id
                and row["active_publication_id"] == result.publication_id
                and row["active_revision"] == row["revision"]
                and row["state"] == RunState.PUBLISHED.value
                and row["library_id"]
                and row["asset_sha256"] == row["source_sha256"]
            ):
                raise ManifestValidationError("Evidence provenance enrichment is invalid")
            enriched.append(
                SearchResultProvenance(
                    result,
                    f"sha256:{row['asset_sha256']}",
                    int(row["revision"]),
                    str(row["run_id"]),
                )
            )
        return tuple(enriched)

    def _search_fts(
        self, match_query: str, limit: int | None = None
    ) -> list[SearchResult]:
        sql = """
            SELECT evidence.evidence_id, active_evidence_fts.publication_id,
                   evidence.source_id, evidence.locator_kind, evidence.locator_start,
                   evidence.locator_end, evidence.text
            FROM active_evidence_fts
            JOIN evidence ON evidence.evidence_id = active_evidence_fts.evidence_id
            JOIN sources ON sources.source_id = evidence.source_id
            WHERE active_evidence_fts MATCH ?
              AND sources.active_publication_id = active_evidence_fts.publication_id
            ORDER BY rank, evidence.locator_start, evidence.evidence_id
            """
        params: list[object] = [match_query]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        statements: list[str] = []
        if self._search_observer is not None:
            self._connection.set_trace_callback(statements.append)
        try:
            rows = self._connection.execute(sql, params).fetchall()
        finally:
            if self._search_observer is not None:
                self._connection.set_trace_callback(None)
                self._search_observer(
                    sum(
                        "active_evidence_fts MATCH" in statement
                        for statement in statements
                    )
                )
        return [
            SearchResult(
                evidence_id=str(row["evidence_id"]),
                publication_id=str(row["publication_id"]),
                source_id=str(row["source_id"]),
                locator_kind=str(row["locator_kind"]),
                locator_start=int(row["locator_start"]),
                locator_end=int(row["locator_end"]),
                text=str(row["text"]),
            )
            for row in rows
        ]

    def search_cjk_active_scan(
        self,
        query: str,
        limit: int | None = None,
        *,
        parameters: CjkActiveScanParameters = CJK_ACTIVE_SCAN_PARAMETERS,
    ) -> list[SearchResult]:
        try:
            compiled = compile_cjk_overlap_terms(
                query,
                parameters=parameters,
                require_terms=True,
            )
        except CjkActiveScanError as error:
            if error.problem == "cjk_query_not_eligible":
                return []
            raise
        budget_row = self._connection.execute(
            """
                SELECT COUNT(*) AS active_row_count,
                       COALESCE(
                         SUM(length(CAST(evidence.text AS BLOB))),
                         0
                       ) AS active_text_bytes
                FROM sources
                JOIN publications
                  ON publications.publication_id = sources.active_publication_id
                JOIN evidence
                  ON evidence.run_id = publications.run_id
                 AND evidence.source_id = sources.source_id
            """
        ).fetchone()
        active_row_count = int(budget_row["active_row_count"])
        active_text_bytes = int(budget_row["active_text_bytes"])
        if (
            active_row_count > parameters.max_active_evidence_rows
            or active_text_bytes > parameters.max_active_evidence_text_bytes
        ):
            raise CjkActiveScanError(
                "cjk_scan_budget_exceeded",
                "CJK active Evidence scan would exceed configured local budget",
                "narrow_query_or_use_projection_strategy",
            )
        rows = self._connection.execute(
            """
            SELECT evidence.evidence_id, publications.publication_id,
                   evidence.source_id, evidence.locator_kind,
                   evidence.locator_start, evidence.locator_end, evidence.text
            FROM sources
            JOIN publications
              ON publications.publication_id = sources.active_publication_id
            JOIN evidence
              ON evidence.run_id = publications.run_id
             AND evidence.source_id = sources.source_id
            ORDER BY evidence.source_id, evidence.locator_kind,
                     evidence.locator_start, evidence.locator_end,
                     evidence.evidence_id
            """
        ).fetchall()
        candidates = tuple(
            CjkActiveScanCandidate(
                evidence_id=str(row["evidence_id"]),
                publication_id=str(row["publication_id"]),
                source_id=str(row["source_id"]),
                locator_kind=str(row["locator_kind"]),
                locator_start=int(row["locator_start"]),
                locator_end=int(row["locator_end"]),
                text=str(row["text"]),
                document_id=str(row["source_id"]),
            )
            for row in rows
        )
        ranked = rank_cjk_active_scan_candidates(
            candidates,
            compiled.terms,
            parameters=parameters,
        )
        if limit is not None:
            ranked = ranked[:limit]
        return [
            SearchResult(
                evidence_id=item.evidence_id,
                publication_id=item.publication_id,
                source_id=item.source_id,
                locator_kind=item.locator_kind,
                locator_start=item.locator_start,
                locator_end=item.locator_end,
                text=item.text,
            )
            for item in ranked
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
def _locator_label(locator_kind: str, locator_start: int, locator_end: int) -> str:
    if locator_kind == "page":
        return f"page:{locator_start}"
    if locator_kind == "timestamp_ms":
        return f"timestamp_ms:{locator_start}..{locator_end}"
    return f"{locator_kind}:{locator_start}..{locator_end}"
