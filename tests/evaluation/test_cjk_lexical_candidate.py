from dataclasses import replace

import pytest

from mke.evaluation.cjk_lexical_candidate import (
    CJK_LEXICAL_CANDIDATE,
    CjkLexicalCandidateError,
    candidate_identity_digest,
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
