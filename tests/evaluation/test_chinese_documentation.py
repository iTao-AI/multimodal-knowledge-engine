import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
FIRST_RUN = """uv sync --locked &&
uv run mke eval retrieval-chinese \\
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json"""


def test_first_run_block_is_synchronized() -> None:
    for relative in (
        "README.md",
        "README_CN.md",
        "docs/tutorials/getting-started.md",
        "docs/how-to/run-chinese-retrieval-evaluation.md",
    ):
        assert FIRST_RUN in (ROOT / relative).read_text()


def test_documented_metrics_match_canonical_artifact() -> None:
    artifact = json.loads(
        (
            ROOT
            / "benchmarks/retrieval/retrieval-chinese-v1-baseline.json"
        ).read_text()
    )
    guide = (
        ROOT / "docs/how-to/run-chinese-retrieval-evaluation.md"
    ).read_text()

    for key in ("recall_at_1", "recall_at_5", "mrr_at_5", "ndcg_at_10"):
        value = artifact["metrics"][key]["value"]
        assert f"`{value:.6f}`" in guide
    assert artifact["miss_symptom_counts"] == {
        "compiled_clauses_absent_from_direct_page": 2,
        "compiled_query_empty": 25,
        "distractor_ranked_ahead": 1,
        "matching_direct_page_not_returned": 2,
    }
    assert "25 `compiled_query_empty`" in guide


def test_public_docs_keep_e3a_boundary_explicit() -> None:
    text = "\n".join(
        (ROOT / relative).read_text()
        for relative in (
            "README.md",
            "README_CN.md",
            "docs/how-to/run-chinese-retrieval-evaluation.md",
            "docs/reference/cli.md",
            "docs/reference/contracts.md",
            "docs/explanation/architecture.md",
        )
    )

    assert "FTS5 lexical" in text
    assert "ASCII-oriented" in text
    assert "sqlite_fts5_default_bm25" in text
    assert "E3-B through E3-F remain unimplemented" in text
    assert "does not establish CJK support" in " ".join(text.split())
