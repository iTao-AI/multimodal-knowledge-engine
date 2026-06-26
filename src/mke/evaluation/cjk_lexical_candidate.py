from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from typing import Any, Protocol


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


class CjkLexicalCandidateError(ValueError):
    """The requested CJK lexical evaluation candidate is unsupported."""


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
