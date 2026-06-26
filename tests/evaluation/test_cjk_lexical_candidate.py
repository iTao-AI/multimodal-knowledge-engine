from dataclasses import replace
import sqlite3
from pathlib import Path

import pytest

from mke.evaluation.cjk_lexical_candidate import (
    CJK_LEXICAL_CANDIDATE,
    CjkLexicalCandidateError,
    CjkLexicalCandidateUnsupported,
    candidate_identity_digest,
    probe_sqlite_trigram_support,
    render_cjk_lexical_error,
    require_cjk_lexical_candidate,
)


def test_candidate_contract_freezes_identity_and_parameters() -> None:
    assert CJK_LEXICAL_CANDIDATE.candidate_id == "cjk-trigram-overlap-v1"
    assert type(CJK_LEXICAL_CANDIDATE.revision) is int
    assert CJK_LEXICAL_CANDIDATE.revision == 1
    assert CJK_LEXICAL_CANDIDATE.minimum_overlap_count == 2
    assert CJK_LEXICAL_CANDIDATE.minimum_overlap_ratio == 0.30
    assert CJK_LEXICAL_CANDIDATE.max_results == 10


def test_non_allowlisted_candidate_id_is_rejected() -> None:
    with pytest.raises(CjkLexicalCandidateError, match="candidate is unsupported"):
        require_cjk_lexical_candidate("raw-trigram")


def test_candidate_identity_digest_changes_when_parameters_change() -> None:
    baseline = candidate_identity_digest(CJK_LEXICAL_CANDIDATE)
    changed = candidate_identity_digest(
        replace(CJK_LEXICAL_CANDIDATE, minimum_overlap_count=3)
    )

    assert baseline != changed
    assert candidate_identity_digest(CJK_LEXICAL_CANDIDATE) == baseline


def test_sqlite_trigram_probe_returns_runtime_identity() -> None:
    support = probe_sqlite_trigram_support()

    assert support.tokenizer == "trigram"
    assert support.sqlite_version == sqlite3.sqlite_version


def test_sqlite_trigram_probe_fails_closed_when_unsupported() -> None:
    class UnsupportedConnection:
        def __enter__(self) -> "UnsupportedConnection":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def execute(self, statement: str) -> None:
            raise sqlite3.OperationalError(
                f"no such tokenizer at {Path.cwd()}"
            )

    def connect(_: str) -> UnsupportedConnection:
        return UnsupportedConnection()

    with pytest.raises(CjkLexicalCandidateUnsupported) as raised:
        probe_sqlite_trigram_support(connect=connect)

    assert raised.value.problem == "cjk_lexical_unsupported_runtime"
    assert raised.value.cause == "SQLite FTS5 trigram tokenizer is unavailable"
    assert raised.value.next_step == "use_python_sqlite_with_fts5_trigram"


def test_cjk_lexical_public_error_hides_tracebacks_and_local_paths() -> None:
    error = CjkLexicalCandidateUnsupported(
        sqlite3.OperationalError(f"boom at {Path.cwd()}")
    )

    payload = render_cjk_lexical_error(error)

    assert payload == {
        "problem": "cjk_lexical_unsupported_runtime",
        "cause": "SQLite FTS5 trigram tokenizer is unavailable",
        "next_step": "use_python_sqlite_with_fts5_trigram",
    }
    assert str(Path.cwd()) not in repr(payload)
