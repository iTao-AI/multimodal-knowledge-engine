"""Allowlisted compilation policies for SQLite FTS5 queries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

RetrievalQueryPolicy = Literal["current", "numeric-grouping-v1"]
DEFAULT_RETRIEVAL_QUERY_POLICY: RetrievalQueryPolicy = "numeric-grouping-v1"
SUPPORTED_RETRIEVAL_QUERY_POLICIES: tuple[RetrievalQueryPolicy, ...] = (
    "current",
    "numeric-grouping-v1",
)
_SUPPORTED_POLICIES = frozenset(SUPPORTED_RETRIEVAL_QUERY_POLICIES)


@dataclass(frozen=True)
class CompiledQueryClause:
    alternatives: tuple[str, ...]


@dataclass(frozen=True)
class CompiledQueryDiagnostic:
    compiled_query: str
    clauses: tuple[CompiledQueryClause, ...]
    ascii_token_count: int
    compiled_query_empty: bool


def require_retrieval_query_policy(policy: str) -> RetrievalQueryPolicy:
    if policy not in _SUPPORTED_POLICIES:
        raise ValueError("retrieval query policy is unsupported")
    return policy


def compile_fts5_query(
    query: str,
    *,
    policy: RetrievalQueryPolicy = DEFAULT_RETRIEVAL_QUERY_POLICY,
) -> str:
    return compile_fts5_query_diagnostic(query, policy=policy).compiled_query


def compile_fts5_query_diagnostic(
    query: str,
    *,
    policy: RetrievalQueryPolicy = DEFAULT_RETRIEVAL_QUERY_POLICY,
) -> CompiledQueryDiagnostic:
    validated = require_retrieval_query_policy(policy)
    if validated == "current":
        return _compile_current_diagnostic(query)
    return _compile_numeric_grouping_diagnostic(query)


def _compile_current_diagnostic(query: str) -> CompiledQueryDiagnostic:
    terms = tuple(re.findall(r"[A-Za-z0-9_]+", query.casefold()))
    compiled = " ".join(f'"{term}"' for term in terms)
    return CompiledQueryDiagnostic(
        compiled_query=compiled,
        clauses=tuple(CompiledQueryClause((term,)) for term in terms),
        ascii_token_count=len(terms),
        compiled_query_empty=not compiled,
    )


def _compile_numeric_grouping_diagnostic(query: str) -> CompiledQueryDiagnostic:
    normalized = query.casefold()
    matches = tuple(re.finditer(r"[A-Za-z0-9_]+", normalized))
    grouped = tuple(
        _group_compact_integer(match.group())
        if _is_standalone_numeric_token(normalized, match.start(), match.end())
        else None
        for match in matches
    )
    if not any(parts is not None for parts in grouped):
        return _compile_current_diagnostic(query)
    clauses: list[str] = []
    diagnostics: list[CompiledQueryClause] = []
    for match, parts in zip(matches, grouped, strict=True):
        token = match.group()
        if parts is None:
            clauses.append(f'"{token}"')
            diagnostics.append(CompiledQueryClause((token,)))
        else:
            grouped_phrase = " ".join(parts)
            clauses.append(f'("{token}" OR "{grouped_phrase}")')
            diagnostics.append(CompiledQueryClause((token, grouped_phrase)))
    compiled = " AND ".join(clauses)
    return CompiledQueryDiagnostic(
        compiled_query=compiled,
        clauses=tuple(diagnostics),
        ascii_token_count=len(matches),
        compiled_query_empty=not compiled,
    )


def numeric_grouping_eligible_tokens(query: str) -> tuple[str, ...]:
    normalized = query.casefold()
    return tuple(
        match.group()
        for match in re.finditer(r"[A-Za-z0-9_]+", normalized)
        if _is_standalone_numeric_token(normalized, match.start(), match.end())
        and _group_compact_integer(match.group()) is not None
    )


def _group_compact_integer(token: str) -> tuple[str, ...] | None:
    if (
        not token.isascii()
        or not token.isdigit()
        or len(token) < 5
        or token.startswith("0")
    ):
        return None
    first = len(token) % 3 or 3
    return (
        token[:first],
        *(token[index : index + 3] for index in range(first, len(token), 3)),
    )


def _is_standalone_numeric_token(query: str, start: int, end: int) -> bool:
    before = query[start - 1] if start else ""
    after = query[end] if end < len(query) else ""
    return (not before or before not in "+-./") and (
        not after or after not in "+-./"
    )
