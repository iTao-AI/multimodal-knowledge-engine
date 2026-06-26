from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from mke.evaluation.diagnostic_ports import EvaluationEvidenceSnapshot
from mke.retrieval.query_policy import (
    CompiledQueryClause,
    compile_fts5_query_diagnostic,
)


@dataclass(frozen=True)
class CjkLexicalCandidateContract:
    candidate_id: str
    revision: int
    minimum_overlap_count: int
    minimum_overlap_ratio: float
    max_results: int


@dataclass(frozen=True)
class SQLiteTrigramSupport:
    tokenizer: str
    sqlite_version: str


@dataclass(frozen=True)
class CjkEvidenceIdentity:
    row_count: int
    text_digest: str
    locator_inventory_digest: str


@dataclass(frozen=True)
class CjkTrigramProjection:
    table_name: str
    tokenizer: str
    row_count: int
    text_digest: str
    locator_inventory_digest: str


@dataclass(frozen=True)
class CjkCompiledQueryTerms:
    terms: tuple[str, ...]
    omitted_below_minimum: tuple[str, ...]
    current_compiled_query: str
    current_clauses: tuple[CompiledQueryClause, ...]
    ascii_token_count: int
    current_compiled_query_empty: bool
    match_query: str


class CjkLexicalCandidateError(ValueError):
    """The requested CJK lexical evaluation candidate is unsupported."""


class CjkLexicalProjectionError(CjkLexicalCandidateError):
    """The evaluation-only CJK lexical projection failed an integrity check."""


class CjkLexicalCandidateUnsupported(CjkLexicalCandidateError):
    problem = "cjk_lexical_unsupported_runtime"
    cause = "SQLite FTS5 trigram tokenizer is unavailable"
    next_step = "use_python_sqlite_with_fts5_trigram"

    def __init__(self, error: BaseException | None = None) -> None:
        super().__init__(self.cause)
        self.__cause__ = error


class _SQLiteConnection(Protocol):
    def __enter__(self) -> Any: ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> object: ...

    def execute(self, statement: str) -> Any: ...


_PROJECTION_TABLE = "temp.mke_cjk_trigram_projection"

CJK_LEXICAL_CANDIDATE = CjkLexicalCandidateContract(
    candidate_id="cjk-trigram-overlap-v1",
    revision=1,
    minimum_overlap_count=2,
    minimum_overlap_ratio=0.30,
    max_results=10,
)


def require_cjk_lexical_candidate(candidate_id: str) -> CjkLexicalCandidateContract:
    if candidate_id != CJK_LEXICAL_CANDIDATE.candidate_id:
        raise CjkLexicalCandidateError("candidate is unsupported")
    return CJK_LEXICAL_CANDIDATE


def candidate_identity_digest(contract: CjkLexicalCandidateContract) -> str:
    payload = asdict(contract)
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def probe_sqlite_trigram_support(
    *,
    connect: Any = sqlite3.connect,
) -> SQLiteTrigramSupport:
    try:
        connection = connect(":memory:")
        try:
            with connection as active:
                active.execute(
                    "CREATE VIRTUAL TABLE temp.mke_cjk_trigram_probe "
                    "USING fts5(value, tokenize='trigram')"
                )
                active.execute("DROP TABLE temp.mke_cjk_trigram_probe")
        finally:
            close = getattr(connection, "close", None)
            if callable(close):
                close()
    except sqlite3.Error as error:
        raise CjkLexicalCandidateUnsupported(error) from error
    return SQLiteTrigramSupport(
        tokenizer="trigram",
        sqlite_version=sqlite3.sqlite_version,
    )


def render_cjk_lexical_error(
    error: CjkLexicalCandidateError,
) -> dict[str, str]:
    if isinstance(error, CjkLexicalCandidateUnsupported):
        return {
            "problem": error.problem,
            "cause": error.cause,
            "next_step": error.next_step,
        }
    return {
        "problem": "cjk_lexical_candidate_invalid",
        "cause": "CJK lexical candidate evaluation failed",
        "next_step": "rerun_cjk_lexical_evaluation",
    }


def cjk_evidence_identity(
    evidence: tuple[EvaluationEvidenceSnapshot, ...],
) -> CjkEvidenceIdentity:
    by_evidence_id = tuple(sorted(evidence, key=lambda item: item.evidence_id))
    return CjkEvidenceIdentity(
        row_count=len(evidence),
        text_digest=_digest(
            tuple(
                {
                    "evidence_id": item.evidence_id,
                    "text_sha256": hashlib.sha256(
                        item.text.encode("utf-8")
                    ).hexdigest(),
                }
                for item in by_evidence_id
            )
        ),
        locator_inventory_digest=_digest(
            tuple(
                {
                    "evidence_id": item.evidence_id,
                    "publication_id": item.publication_id,
                    "source_id": item.source_id,
                    "locator_kind": item.locator_kind,
                    "locator_start": item.locator_start,
                    "locator_end": item.locator_end,
                }
                for item in by_evidence_id
            )
        ),
    )


def build_cjk_trigram_projection(
    connection: sqlite3.Connection,
    evidence: tuple[EvaluationEvidenceSnapshot, ...],
    *,
    expected_identity: CjkEvidenceIdentity | None = None,
) -> CjkTrigramProjection:
    try:
        connection.execute(f"DROP TABLE IF EXISTS {_PROJECTION_TABLE}")
        connection.execute(
            f"""
            CREATE VIRTUAL TABLE {_PROJECTION_TABLE} USING fts5(
              evidence_id UNINDEXED,
              publication_id UNINDEXED,
              source_id UNINDEXED,
              locator_kind UNINDEXED,
              locator_start UNINDEXED,
              locator_end UNINDEXED,
              text,
              tokenize='trigram'
            )
            """
        )
        connection.executemany(
            f"""
            INSERT INTO {_PROJECTION_TABLE}(
              evidence_id, publication_id, source_id, locator_kind,
              locator_start, locator_end, text
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    item.evidence_id,
                    item.publication_id,
                    item.source_id,
                    item.locator_kind,
                    item.locator_start,
                    item.locator_end,
                    item.text,
                )
                for item in evidence
            ),
        )
    except sqlite3.Error as error:
        raise CjkLexicalCandidateUnsupported(error) from error

    observed = cjk_evidence_identity(_projection_evidence(connection))
    if expected_identity is not None:
        if observed.row_count != expected_identity.row_count:
            raise CjkLexicalProjectionError("row count mismatch")
        if observed.text_digest != expected_identity.text_digest:
            raise CjkLexicalProjectionError("text digest mismatch")
        if (
            observed.locator_inventory_digest
            != expected_identity.locator_inventory_digest
        ):
            raise CjkLexicalProjectionError("locator inventory mismatch")
    return CjkTrigramProjection(
        table_name=_PROJECTION_TABLE,
        tokenizer="trigram",
        row_count=observed.row_count,
        text_digest=observed.text_digest,
        locator_inventory_digest=observed.locator_inventory_digest,
    )


def compile_cjk_query_terms(query: str) -> CjkCompiledQueryTerms:
    current = compile_fts5_query_diagnostic(query, policy="numeric-grouping-v1")
    runs = _cjk_runs(query.casefold())
    terms: list[str] = []
    seen_terms: set[str] = set()
    omitted: list[str] = []
    for run in runs:
        if len(run) < 3:
            omitted.append(run)
            continue
        for index in range(0, len(run) - 2):
            term = run[index : index + 3]
            if term not in seen_terms:
                seen_terms.add(term)
                terms.append(term)
    return CjkCompiledQueryTerms(
        terms=tuple(terms),
        omitted_below_minimum=tuple(omitted),
        current_compiled_query=current.compiled_query,
        current_clauses=current.clauses,
        ascii_token_count=current.ascii_token_count,
        current_compiled_query_empty=current.compiled_query_empty,
        match_query=" OR ".join(_quote_fts5_term(term) for term in terms),
    )


def should_use_cjk_fallback(compiled: CjkCompiledQueryTerms) -> bool:
    return compiled.current_compiled_query_empty and bool(compiled.terms)


def _projection_evidence(
    connection: sqlite3.Connection,
) -> tuple[EvaluationEvidenceSnapshot, ...]:
    rows = connection.execute(
        f"""
        SELECT evidence_id, publication_id, source_id, locator_kind,
               locator_start, locator_end, text
        FROM {_PROJECTION_TABLE}
        ORDER BY source_id, locator_kind,
                 CAST(locator_start AS INTEGER),
                 CAST(locator_end AS INTEGER),
                 evidence_id
        """
    ).fetchall()
    return tuple(
        EvaluationEvidenceSnapshot(
            evidence_id=str(row[0]),
            publication_id=str(row[1]),
            source_id=str(row[2]),
            locator_kind=str(row[3]),
            locator_start=int(row[4]),
            locator_end=int(row[5]),
            text=str(row[6]),
        )
        for row in rows
    )


def _cjk_runs(query: str) -> tuple[str, ...]:
    runs: list[str] = []
    current: list[str] = []
    for character in query:
        if _is_cjk_character(character):
            current.append(character)
        elif character.isspace():
            continue
        elif current:
            runs.append("".join(current))
            current = []
    if current:
        runs.append("".join(current))
    return tuple(runs)


def _is_cjk_character(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x3040 <= codepoint <= 0x30FF
        or 0x31F0 <= codepoint <= 0x31FF
        or 0xAC00 <= codepoint <= 0xD7AF
    )


def _quote_fts5_term(term: str) -> str:
    escaped = term.replace('"', '""')
    return f'"{escaped}"'


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
