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
    ActivationResult,
    ActiveEvidenceRef,
    CandidateEvidence,
    FailurePoint,
    ManifestValidationError,
    PdfIntakeReport,
    RunEvent,
    RunEventType,
    RunManifest,
    RunRecord,
    RunState,
    SearchResult,
    SourceRecord,
    TranscriptIntakeReport,
    is_recognized_video_fingerprint,
    validate_manifest,
)
from mke.retrieval import (
    DEFAULT_RETRIEVAL_QUERY_POLICY,
    RetrievalQueryPolicy,
    compile_fts5_query,
)
from mke.retrieval.query_policy import require_retrieval_query_policy

if TYPE_CHECKING:
    from mke.evaluation.diagnostic_ports import (
        EvaluationEvidenceSnapshot,
        FtsProjectionSnapshot,
        FtsRankObservation,
        FtsRankProfile,
    )

_BUSY_TIMEOUT_MS = 5000


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
        query_policy: RetrievalQueryPolicy = DEFAULT_RETRIEVAL_QUERY_POLICY,
        search_observer: Callable[[int], None] | None = None,
    ) -> None:
        self.db_path = db_path
        self._query_policy: RetrievalQueryPolicy = require_retrieval_query_policy(
            query_policy
        )
        self._search_observer = search_observer
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
            self._connection.execute(
                "UPDATE runs SET state = ? WHERE run_id = ?", (RunState.FAILED.value, run_id)
            )
            self._append_event(run_id, RunEventType.RUN_FAILED)

    def mark_run_running(self, run_id: str) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE runs SET state = ? WHERE run_id = ?", (RunState.RUNNING.value, run_id)
            )
            self._append_event(run_id, RunEventType.RUN_STARTED)

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
                self._append_event(run_id, RunEventType.RUN_INTERRUPTED)

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
            self._append_event(run_id, RunEventType.CANDIDATE_VALIDATED)

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
                self._connection.execute(
                    "UPDATE runs SET state = ? WHERE run_id = ?",
                    (RunState.SUPERSEDED.value, run_id),
                )
                self._append_event(run_id, RunEventType.RUN_SUPERSEDED)
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
            self._connection.execute(
                "UPDATE runs SET state = ? WHERE run_id = ?", (RunState.PUBLISHED.value, run_id)
            )
            self._append_event(run_id, RunEventType.PUBLICATION_ACTIVATED)
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
        if not match_query:
            return []
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
