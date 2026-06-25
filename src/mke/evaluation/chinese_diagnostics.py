from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from mke.evaluation.chinese_protocol import GradedQrel
from mke.evaluation.manifest import StableLocator
from mke.retrieval.query_policy import CompiledQueryDiagnostic

MissSymptom = Literal[
    "compiled_query_empty",
    "distractor_ranked_ahead",
    "compiled_clauses_absent_from_direct_page",
    "compiled_clauses_overconstrained",
    "matching_direct_page_not_returned",
    "other_observed_miss",
]


@dataclass(frozen=True)
class MissClassification:
    symptom: MissSymptom
    compiled_query: str
    ascii_token_count: int
    compiled_query_empty: bool
    direct_locators: tuple[StableLocator, ...]
    returned_direct_ranks: tuple[int, ...]
    returned_distractor_ranks: tuple[int, ...]
    direct_page_clause_coverage: tuple[tuple[bool, ...], ...]
    observation: str


def classify_miss(
    diagnostic: CompiledQueryDiagnostic,
    *,
    qrels: tuple[GradedQrel, ...],
    retrieved: tuple[StableLocator, ...],
    direct_page_text: Mapping[StableLocator, str],
) -> MissClassification:
    direct = tuple(qrel.locator for qrel in qrels if qrel.grade == 2)
    distractors = {qrel.locator for qrel in qrels if qrel.grade == 0}
    if not direct:
        raise ValueError("classification requires grade-2 qrels")
    direct_ranks = tuple(
        rank
        for rank, locator in enumerate(retrieved, start=1)
        if locator in set(direct)
    )
    distractor_ranks = tuple(
        rank
        for rank, locator in enumerate(retrieved, start=1)
        if locator in distractors
    )
    if direct_ranks and min(direct_ranks) == 1:
        raise ValueError("classification requires a direct-Evidence miss")
    if set(direct_page_text) != set(direct):
        raise ValueError("classification requires every direct page text")
    coverage = tuple(
        tuple(_clause_matches(text, clause.alternatives) for clause in diagnostic.clauses)
        for text in (direct_page_text[locator] for locator in direct)
    )

    if distractor_ranks and (
        not direct_ranks or min(distractor_ranks) < min(direct_ranks)
    ):
        symptom: MissSymptom = "distractor_ranked_ahead"
        observation = "A designated distractor ranked ahead of direct Evidence."
    elif diagnostic.compiled_query_empty:
        symptom = "compiled_query_empty"
        observation = "The current query compiler produced no FTS5 MATCH expression."
    elif coverage and all(not any(page) for page in coverage):
        symptom = "compiled_clauses_absent_from_direct_page"
        observation = "No direct page satisfied any required compiled clause."
    elif coverage and not any(all(page) for page in coverage) and any(
        any(page) for page in coverage
    ):
        symptom = "compiled_clauses_overconstrained"
        observation = "Direct pages satisfied some but not all compiled clauses."
    elif coverage and any(all(page) for page in coverage) and not direct_ranks:
        symptom = "matching_direct_page_not_returned"
        observation = "A direct page matched every clause but was not returned."
    else:
        symptom = "other_observed_miss"
        observation = "The observed miss did not match another mechanical symptom."

    return MissClassification(
        symptom=symptom,
        compiled_query=diagnostic.compiled_query,
        ascii_token_count=diagnostic.ascii_token_count,
        compiled_query_empty=diagnostic.compiled_query_empty,
        direct_locators=direct,
        returned_direct_ranks=direct_ranks,
        returned_distractor_ranks=distractor_ranks,
        direct_page_clause_coverage=coverage,
        observation=observation,
    )


def _clause_matches(text: str, alternatives: tuple[str, ...]) -> bool:
    document_tokens = tuple(re.findall(r"[A-Za-z0-9_]+", text.casefold()))
    return any(
        _contains_sequence(
            document_tokens,
            tuple(re.findall(r"[A-Za-z0-9_]+", alternative.casefold())),
        )
        for alternative in alternatives
    )


def _contains_sequence(
    document_tokens: tuple[str, ...], expected: tuple[str, ...]
) -> bool:
    if not expected:
        return False
    return any(
        document_tokens[index : index + len(expected)] == expected
        for index in range(len(document_tokens) - len(expected) + 1)
    )
