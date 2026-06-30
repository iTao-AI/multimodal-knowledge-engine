import pytest

from mke.evaluation.rrf_fusion import (
    ArmRankedResult,
    RrfCandidateConfig,
    RrfFusionError,
    fuse_ranked_results,
)


def result(locator: str, rank: int, arm: str = "lexical") -> ArmRankedResult:
    return ArmRankedResult(
        arm_id=arm,
        stable_locator_id=locator,
        document_id=locator.split("|")[0],
        locator_kind="page",
        locator_start=1,
        locator_end=1,
        source_text_digest="sha256:" + "1" * 64,
        rank=rank,
    )


def test_rrf_uses_rank_not_raw_score() -> None:
    config = RrfCandidateConfig.default()
    fused = fuse_ranked_results(
        query_id="q1",
        lexical=(result("doc-a|page|1|1|x", 10),),
        dense=(result("doc-b|page|1|1|y", 1, arm="dense"),),
        config=config,
    )
    assert [row.stable_locator_id for row in fused[:2]] == [
        "doc-b|page|1|1|y",
        "doc-a|page|1|1|x",
    ]


def test_duplicate_locator_merges_arm_contributions() -> None:
    config = RrfCandidateConfig.default()
    fused = fuse_ranked_results(
        query_id="q1",
        lexical=(result("doc-a|page|1|1|x", 1),),
        dense=(result("doc-a|page|1|1|x", 3, arm="dense"),),
        config=config,
    )
    assert len(fused) == 1
    assert fused[0].arms == ("dense", "lexical")
    assert fused[0].lexical_rank == 1
    assert fused[0].dense_rank == 3


def test_invalid_rank_bool_fails() -> None:
    config = RrfCandidateConfig.default()
    bad = ArmRankedResult(
        arm_id="lexical",
        stable_locator_id="doc|page|1|1|x",
        document_id="doc",
        locator_kind="page",
        locator_start=1,
        locator_end=1,
        source_text_digest="sha256:" + "1" * 64,
        rank=True,  # type: ignore[arg-type]
    )
    with pytest.raises(RrfFusionError, match="rank"):
        fuse_ranked_results(query_id="q1", lexical=(bad,), dense=(), config=config)


def test_duplicate_locator_inside_one_arm_fails() -> None:
    config = RrfCandidateConfig.default()
    row = result("doc-a|page|1|1|x", 1)

    with pytest.raises(RrfFusionError, match="duplicate"):
        fuse_ranked_results(query_id="q1", lexical=(row, row), dense=(), config=config)


def test_tie_break_order_is_deterministic() -> None:
    config = RrfCandidateConfig.default()
    fused = fuse_ranked_results(
        query_id="q1",
        lexical=(
            result("doc-c|page|1|1|x", 2),
            result("doc-a|page|1|1|x", 1),
        ),
        dense=(
            result("doc-b|page|1|1|x", 1, arm="dense"),
            result("doc-c|page|1|1|x", 2, arm="dense"),
        ),
        config=config,
    )

    assert [row.stable_locator_id for row in fused] == [
        "doc-c|page|1|1|x",
        "doc-a|page|1|1|x",
        "doc-b|page|1|1|x",
    ]
