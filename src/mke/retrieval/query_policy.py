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
    return _compile_current(query)
