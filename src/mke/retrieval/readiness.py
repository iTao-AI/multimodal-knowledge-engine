"""Readiness checks for retrieval strategies."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from mke.retrieval.strategy import (
    RetrievalStrategy,
    get_retrieval_strategy_descriptor,
)

ReadinessStatus = Literal["ready", "not_ready"]
CheckStatus = Literal["ready", "not_ready", "not_required"]


@dataclass(frozen=True)
class RetrievalReadinessCheck:
    name: str
    status: CheckStatus


@dataclass(frozen=True)
class RetrievalReadiness:
    status: ReadinessStatus
    strategy: RetrievalStrategy
    problem: str | None
    cause: str | None
    next_step: str | None
    checks: tuple[RetrievalReadinessCheck, ...]


def doctor_retrieval_strategy(
    db_path: Path, strategy: RetrievalStrategy
) -> RetrievalReadiness:
    descriptor = get_retrieval_strategy_descriptor(strategy)
    additional_projection_check = RetrievalReadinessCheck(
        "additional_cjk_projection",
        "not_required" if not descriptor.additional_projections else "ready",
    )
    try:
        if not db_path.is_file():
            raise OSError
        uri = f"{db_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            active = connection.execute(
                """
                SELECT 1
                FROM sources
                JOIN publications
                  ON publications.publication_id = sources.active_publication_id
                LIMIT 1
                """
            ).fetchone()
            active_fts_ready = _active_fts_projection_is_consistent(connection)
    except (OSError, sqlite3.Error):
        return RetrievalReadiness(
            status="not_ready",
            strategy=strategy,
            problem="sqlite_unreadable",
            cause="SQLite domain truth could not be inspected",
            next_step="check_database_file",
            checks=(
                RetrievalReadinessCheck("sqlite_domain_truth", "not_ready"),
                RetrievalReadinessCheck("active_publication", "not_ready"),
                RetrievalReadinessCheck("active_fts_projection", "not_ready"),
                additional_projection_check,
            ),
        )
    active_publication_check = RetrievalReadinessCheck(
        "active_publication", "ready" if active else "not_ready"
    )
    if not active_fts_ready:
        return RetrievalReadiness(
            status="not_ready",
            strategy=strategy,
            problem="retrieval_projection_not_ready",
            cause="Active FTS5 projection is missing or inconsistent",
            next_step="republish_active_sources",
            checks=(
                RetrievalReadinessCheck("sqlite_domain_truth", "ready"),
                active_publication_check,
                RetrievalReadinessCheck("active_fts_projection", "not_ready"),
                additional_projection_check,
            ),
        )
    if not active:
        return RetrievalReadiness(
            status="not_ready",
            strategy=strategy,
            problem="no_active_publication",
            cause="No active Publication is available to scan",
            next_step="ingest_and_publish_source",
            checks=(
                RetrievalReadinessCheck("sqlite_domain_truth", "ready"),
                active_publication_check,
                RetrievalReadinessCheck("active_fts_projection", "ready"),
                additional_projection_check,
            ),
        )
    return RetrievalReadiness(
        status="ready",
        strategy=strategy,
        problem=None,
        cause=None,
        next_step=None,
        checks=(
            RetrievalReadinessCheck("sqlite_domain_truth", "ready"),
            active_publication_check,
            RetrievalReadinessCheck("active_fts_projection", "ready"),
            additional_projection_check,
        ),
    )


def _active_fts_projection_is_consistent(connection: sqlite3.Connection) -> bool:
    definition = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("active_evidence_fts",),
    ).fetchone()
    if (
        definition is None
        or not isinstance(definition[0], str)
        or "using fts5" not in definition[0].casefold()
    ):
        return False
    try:
        counts_and_differences = connection.execute(
            """
            WITH expected(
              library_id, source_id, publication_id, evidence_id, locator_label, text
            ) AS (
              SELECT sources.library_id, evidence.source_id,
                     publications.publication_id, evidence.evidence_id,
                     CASE evidence.locator_kind
                       WHEN 'page'
                         THEN 'page:' || evidence.locator_start
                       WHEN 'timestamp_ms'
                         THEN 'timestamp_ms:' || evidence.locator_start
                              || '..' || evidence.locator_end
                       ELSE evidence.locator_kind || ':' || evidence.locator_start
                            || '..' || evidence.locator_end
                     END,
                     evidence.text
              FROM sources
              JOIN publications
                ON publications.publication_id = sources.active_publication_id
              JOIN evidence
                ON evidence.run_id = publications.run_id
               AND evidence.source_id = sources.source_id
            )
            SELECT
              (SELECT COUNT(*) FROM expected),
              (SELECT COUNT(*) FROM active_evidence_fts),
              EXISTS(
                SELECT * FROM expected
                EXCEPT
                SELECT library_id, source_id, publication_id, evidence_id, locator_label, text
                FROM active_evidence_fts
              ),
              EXISTS(
                SELECT library_id, source_id, publication_id, evidence_id, locator_label, text
                FROM active_evidence_fts
                EXCEPT
                SELECT * FROM expected
              )
            """
        ).fetchone()
    except sqlite3.Error:
        return False
    return (
        counts_and_differences is not None
        and counts_and_differences[0] == counts_and_differences[1]
        and counts_and_differences[2] == 0
        and counts_and_differences[3] == 0
    )
