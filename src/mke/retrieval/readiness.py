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
    projection_check = RetrievalReadinessCheck(
        "persistent_cjk_projection",
        "not_required" if not descriptor.required_projections else "ready",
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
                projection_check,
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
                RetrievalReadinessCheck("active_publication", "not_ready"),
                projection_check,
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
            RetrievalReadinessCheck("active_publication", "ready"),
            projection_check,
        ),
    )
