"""Owner-selected retrieval strategy descriptors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mke.retrieval.query_policy import RetrievalQueryPolicy

RetrievalStrategy = Literal[
    "current",
    "numeric-grouping-v1",
    "cjk-active-scan-overlap-v1",
]

DEFAULT_RETRIEVAL_STRATEGY: RetrievalStrategy = "cjk-active-scan-overlap-v1"
SUPPORTED_RETRIEVAL_STRATEGIES: tuple[RetrievalStrategy, ...] = (
    "current",
    "numeric-grouping-v1",
    "cjk-active-scan-overlap-v1",
)
_SUPPORTED_STRATEGIES = frozenset(SUPPORTED_RETRIEVAL_STRATEGIES)


@dataclass(frozen=True)
class RetrievalStrategyDescriptor:
    strategy_id: str
    revision: int
    base_query_policy: RetrievalQueryPolicy
    required_projections: tuple[str, ...]
    term_derivation_mode: str
    readiness_checker: str
    rollback_capability: tuple[RetrievalStrategy, ...]
    fallback_semantics: str
    dense: str
    hybrid: str
    rerank: str


_DESCRIPTORS: dict[RetrievalStrategy, RetrievalStrategyDescriptor] = {
    "current": RetrievalStrategyDescriptor(
        strategy_id="current",
        revision=1,
        base_query_policy="current",
        required_projections=("active_evidence_fts",),
        term_derivation_mode="ascii-token-fts5",
        readiness_checker="active-publication-fts",
        rollback_capability=("current",),
        fallback_semantics="legacy FTS5 query policy only",
        dense="none",
        hybrid="none",
        rerank="none",
    ),
    "numeric-grouping-v1": RetrievalStrategyDescriptor(
        strategy_id="numeric-grouping-v1",
        revision=1,
        base_query_policy="numeric-grouping-v1",
        required_projections=("active_evidence_fts",),
        term_derivation_mode="ascii-token-fts5-with-numeric-grouping",
        readiness_checker="active-publication-fts",
        rollback_capability=("current",),
        fallback_semantics="default FTS5 query policy only",
        dense="none",
        hybrid="none",
        rerank="none",
    ),
    "cjk-active-scan-overlap-v1": RetrievalStrategyDescriptor(
        strategy_id="cjk-active-scan-overlap-v1",
        revision=1,
        base_query_policy="numeric-grouping-v1",
        required_projections=(),
        term_derivation_mode="cjk-overlap-trigrams",
        readiness_checker="active-publication-domain-evidence",
        rollback_capability=("numeric-grouping-v1", "current"),
        fallback_semantics=(
            "use active_evidence_fts for non-empty numeric-grouping queries; "
            "use bounded active Evidence scan for eligible compiled-empty CJK queries"
        ),
        dense="none",
        hybrid="none",
        rerank="none",
    ),
}


def require_retrieval_strategy(strategy: str) -> RetrievalStrategy:
    if type(strategy) is not str:
        raise TypeError("retrieval strategy must be a string")
    if strategy not in _SUPPORTED_STRATEGIES:
        raise ValueError("retrieval strategy is unsupported")
    return strategy


def get_retrieval_strategy_descriptor(
    strategy: str,
) -> RetrievalStrategyDescriptor:
    validated = require_retrieval_strategy(strategy)
    return _DESCRIPTORS[validated]
