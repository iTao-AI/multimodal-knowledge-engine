from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CjkLexicalCandidateContract:
    candidate_id: str
    revision: int
    minimum_overlap_count: int
    minimum_overlap_ratio: float
    max_results: int


class CjkLexicalCandidateError(ValueError):
    """The requested CJK lexical evaluation candidate is unsupported."""


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
