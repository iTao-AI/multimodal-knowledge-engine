"""Allowlisted compilation policies for SQLite FTS5 queries."""

from __future__ import annotations

import re
from typing import Literal, cast

RetrievalQueryPolicy = Literal["current", "numeric-grouping-v1"]
DEFAULT_RETRIEVAL_QUERY_POLICY: RetrievalQueryPolicy = "current"
_SUPPORTED_POLICIES = frozenset({"current", "numeric-grouping-v1"})


def require_retrieval_query_policy(policy: str) -> RetrievalQueryPolicy:
    if policy not in _SUPPORTED_POLICIES:
        raise ValueError("retrieval query policy is unsupported")
    return cast(RetrievalQueryPolicy, policy)


def compile_fts5_query(
    query: str,
    *,
    policy: RetrievalQueryPolicy = DEFAULT_RETRIEVAL_QUERY_POLICY,
) -> str:
    validated = require_retrieval_query_policy(policy)
    if validated == "current":
        return _compile_current(query)
    return _compile_numeric_grouping(query)


def _compile_current(query: str) -> str:
    terms = re.findall(r"[A-Za-z0-9_]+", query.casefold())
    return " ".join(f'"{term}"' for term in terms)


def _compile_numeric_grouping(query: str) -> str:
    normalized = query.casefold()
    matches = tuple(re.finditer(r"[A-Za-z0-9_]+", normalized))
    grouped = tuple(
        _group_compact_integer(match.group())
        if _is_standalone_numeric_token(normalized, match.start(), match.end())
        else None
        for match in matches
    )
    if not any(parts is not None for parts in grouped):
        return _compile_current(query)
    clauses: list[str] = []
    for match, parts in zip(matches, grouped, strict=True):
        token = match.group()
        if parts is None:
            clauses.append(f'"{token}"')
        else:
            clauses.append(f'("{token}" OR "{" ".join(parts)}")')
    return " AND ".join(clauses)


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
