"""Public feature extraction for the E3-E relevance gate candidate."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Literal

ArmContribution = Literal["lexical", "dense"]

_CJK_RE = re.compile(r"[\u3400-\u9fff]+")
_ASCII_RE = re.compile(r"[a-z]+")
_MIXED_RE = re.compile(r"[a-z]+(?:[-_]\d+)+(?:[-_][a-z0-9]+)*")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_UNIT_RE = re.compile(r"\d+(?:\.\d+)?\s*(gb|mb|kb|tb|ms|s|%|元|天|页)")
_FORBIDDEN_EXTRA_FIELDS = frozenset(
    {
        "qrel",
        "qrels",
        "qrel_grade",
        "qrel_grades",
        "grade",
        "grades",
        "category",
        "query_category",
        "query_category_label",
        "split",
        "split_label",
        "expected_locator",
        "expected_locators",
    }
)


class RelevanceGateFeatureError(ValueError):
    """Raised when relevance-gate feature input is unsafe or invalid."""


def _empty_extra_fields() -> Mapping[str, object]:
    return {}


@dataclass(frozen=True)
class EvidenceCandidateInput:
    query_id: str
    query_text: str
    stable_locator_id: str
    document_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    evidence_text: str
    arm_contributions: tuple[ArmContribution, ...]
    lexical_rank: int | None
    dense_rank: int | None
    rrf_rank: int | None
    extra_fields: Mapping[str, object] = field(default_factory=_empty_extra_fields)


@dataclass(frozen=True)
class TermFeatures:
    cjk: tuple[str, ...]
    ascii: tuple[str, ...]
    mixed: tuple[str, ...]
    numbers: tuple[str, ...]
    dates: tuple[str, ...]
    units: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "cjk": list(self.cjk),
            "ascii": list(self.ascii),
            "mixed": list(self.mixed),
            "numbers": list(self.numbers),
            "dates": list(self.dates),
            "units": list(self.units),
        }


@dataclass(frozen=True)
class RequiredConstraints:
    numbers: tuple[str, ...]
    dates: tuple[str, ...]
    units: tuple[str, ...]
    mixed: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "numbers": list(self.numbers),
            "dates": list(self.dates),
            "units": list(self.units),
            "mixed": list(self.mixed),
        }


@dataclass(frozen=True)
class CoverageFeatures:
    cjk_overlap_count: int
    ascii_overlap_count: int
    mixed_overlap_count: int
    missing_numbers: tuple[str, ...]
    missing_dates: tuple[str, ...]
    missing_units: tuple[str, ...]
    missing_mixed: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "cjk_overlap_count": self.cjk_overlap_count,
            "ascii_overlap_count": self.ascii_overlap_count,
            "mixed_overlap_count": self.mixed_overlap_count,
            "missing_numbers": list(self.missing_numbers),
            "missing_dates": list(self.missing_dates),
            "missing_units": list(self.missing_units),
            "missing_mixed": list(self.missing_mixed),
        }


@dataclass(frozen=True)
class RelevanceFeatures:
    query_id: str
    stable_locator_id: str
    document_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    source_text_digest: str
    arm_contributions: tuple[ArmContribution, ...]
    lexical_rank: int | None
    dense_rank: int | None
    rrf_rank: int | None
    query_terms: TermFeatures
    evidence_terms: TermFeatures
    required_constraints: RequiredConstraints
    coverage: CoverageFeatures

    def to_json(self) -> dict[str, object]:
        return {
            "query_id": self.query_id,
            "stable_locator_id": self.stable_locator_id,
            "document_id": self.document_id,
            "locator_kind": self.locator_kind,
            "locator_start": self.locator_start,
            "locator_end": self.locator_end,
            "source_text_digest": self.source_text_digest,
            "arm_contributions": list(self.arm_contributions),
            "lexical_rank": self.lexical_rank,
            "dense_rank": self.dense_rank,
            "rrf_rank": self.rrf_rank,
            "query_terms": self.query_terms.to_json(),
            "evidence_terms": self.evidence_terms.to_json(),
            "required_constraints": self.required_constraints.to_json(),
            "coverage": self.coverage.to_json(),
        }


def build_relevance_features(candidate: EvidenceCandidateInput) -> RelevanceFeatures:
    _validate_candidate(candidate)
    query_terms = extract_terms(candidate.query_text)
    evidence_terms = extract_terms(candidate.evidence_text)
    required = RequiredConstraints(
        numbers=query_terms.numbers,
        dates=query_terms.dates,
        units=query_terms.units,
        mixed=query_terms.mixed,
    )
    coverage = CoverageFeatures(
        cjk_overlap_count=_overlap_count(query_terms.cjk, evidence_terms.cjk),
        ascii_overlap_count=_overlap_count(query_terms.ascii, evidence_terms.ascii),
        mixed_overlap_count=_overlap_count(query_terms.mixed, evidence_terms.mixed),
        missing_numbers=_missing(required.numbers, evidence_terms.numbers),
        missing_dates=_missing(required.dates, evidence_terms.dates),
        missing_units=_missing(required.units, evidence_terms.units),
        missing_mixed=_missing(required.mixed, evidence_terms.mixed),
    )
    return RelevanceFeatures(
        query_id=candidate.query_id,
        stable_locator_id=candidate.stable_locator_id,
        document_id=candidate.document_id,
        locator_kind=candidate.locator_kind,
        locator_start=candidate.locator_start,
        locator_end=candidate.locator_end,
        source_text_digest=_text_digest(candidate.evidence_text),
        arm_contributions=tuple(candidate.arm_contributions),
        lexical_rank=candidate.lexical_rank,
        dense_rank=candidate.dense_rank,
        rrf_rank=candidate.rrf_rank,
        query_terms=query_terms,
        evidence_terms=evidence_terms,
        required_constraints=required,
        coverage=coverage,
    )


def extract_terms(text: str) -> TermFeatures:
    normalized = _normalize_text(text)
    numbers = _dedupe(_NUMBER_RE.findall(normalized))
    units = _dedupe(match.group(1) for match in _UNIT_RE.finditer(normalized))
    mixed = _dedupe(_MIXED_RE.findall(normalized))
    ascii_terms = _dedupe(_ASCII_RE.findall(normalized))
    return TermFeatures(
        cjk=_dedupe(_CJK_RE.findall(normalized)),
        ascii=ascii_terms,
        mixed=mixed,
        numbers=numbers,
        dates=tuple(number for number in numbers if len(number) == 4),
        units=units,
    )


def load_repository_text(repository_root: Path, relative_path: str) -> str:
    path = _repository_path(repository_root.resolve(), relative_path)
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise RelevanceGateFeatureError("source text is missing") from error
    except OSError as error:
        raise RelevanceGateFeatureError("source text is unreadable") from error


def _validate_candidate(candidate: EvidenceCandidateInput) -> None:
    if not candidate.query_id or not candidate.stable_locator_id:
        raise RelevanceGateFeatureError("candidate identity is invalid")
    if not candidate.evidence_text:
        raise RelevanceGateFeatureError("source text is missing")
    if candidate.locator_start < 0 or candidate.locator_end < candidate.locator_start:
        raise RelevanceGateFeatureError("locator range is invalid")
    if not candidate.arm_contributions:
        raise RelevanceGateFeatureError("arm provenance is missing")
    if set(candidate.arm_contributions) - {"lexical", "dense"}:
        raise RelevanceGateFeatureError("arm provenance is invalid")
    for subject, rank in (
        ("lexical_rank", candidate.lexical_rank),
        ("dense_rank", candidate.dense_rank),
        ("rrf_rank", candidate.rrf_rank),
    ):
        if rank is not None and (type(rank) is not int or rank < 1):
            raise RelevanceGateFeatureError(f"{subject} is invalid")
    forbidden = set(candidate.extra_fields) & _FORBIDDEN_EXTRA_FIELDS
    if forbidden:
        raise RelevanceGateFeatureError(
            f"forbidden scoring inputs are not allowed: {sorted(forbidden)[0]}"
        )


def _normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


def _text_digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _overlap_count(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    return len(set(left) & set(right))


def _missing(required: tuple[str, ...], observed: tuple[str, ...]) -> tuple[str, ...]:
    observed_set = set(observed)
    return tuple(item for item in required if item not in observed_set)


def _dedupe(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw)
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return tuple(result)


def _repository_path(root: Path, relative_path: str) -> Path:
    posix_path = PurePosixPath(relative_path)
    if posix_path.is_absolute() or ".." in posix_path.parts:
        raise RelevanceGateFeatureError("repository path is invalid")
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise RelevanceGateFeatureError("repository path is invalid")
    return path
