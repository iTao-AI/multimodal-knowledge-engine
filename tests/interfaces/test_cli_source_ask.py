from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.source_discovery_support import native_cli, publish_pages


def packet(database: Path, source: str, publication: str, question: str, limit: int = 5):
    result = native_cli(
        database,
        "ask",
        question,
        "--source-id",
        source,
        "--publication-id",
        publication,
        "--limit",
        str(limit),
        "--json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_scoped_ask_excludes_stronger_other_source_and_discloses_first_page(tmp_path: Path) -> None:
    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(
        database, ("needle target" + " padding" * 30,) * 13, fingerprint="f"
    )
    publish_pages(database, ("needle outsideonly",) * 20, fingerprint="a")
    legacy = native_cli(database, "ask", "needle")
    assert legacy.returncode == 0 and "outsideonly" in legacy.stdout
    response = packet(database, source, publication, "needle", 3)
    assert response["schema_version"] == "mke.source_ask_response.v1"
    assert response["question"] == "needle" and response["answer_status"] == "evidence_found"
    assert response["scope"]["source_id"] == source
    assert response["scope"]["publication_id"] == publication
    assert len(response["evidence"]) == 3
    assert [item["evidence"]["locator"]["start"] for item in response["evidence"]] == [1, 2, 3]
    assert all(item["evidence"]["source_id"] == source for item in response["evidence"])
    assert all("outsideonly" not in item["excerpt"]["text"] for item in response["evidence"])
    assert response["selection"] == {
        "mode": "bounded_first_page",
        "status": "more_available",
        "returned": 3,
        "next_step": "run_scoped_search_for_all_matches",
    }
    assert "cursor" not in json.dumps(response)
    assert "do not verify an answer" in response["limitations"]


def test_scoped_ask_complete_and_zero_match_preserve_scope(tmp_path: Path) -> None:
    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, ("needle selected",) * 2, fingerprint="f")
    publish_pages(database, ("outsideonly needle",), fingerprint="a")
    response = packet(database, source, publication, "needle")
    assert response["selection"] == {
        "mode": "bounded_first_page",
        "status": "complete",
        "returned": 2,
        "next_step": "read_selected_evidence",
    }
    empty = packet(database, source, publication, "outsideonly")
    assert empty["answer_status"] == "insufficient_evidence" and empty["evidence"] == []
    assert empty["scope"] == response["scope"]
    assert empty["selection"] == {
        "mode": "bounded_first_page",
        "status": "complete",
        "returned": 0,
        "next_step": "refine_question_in_selected_source",
    }


@pytest.mark.parametrize(
    "options",
    [
        ("--source-id", "src_only"),
        ("--publication-id", "pub_only"),
        ("--limit", "3"),
        ("--json",),
    ],
)
def test_ask_opt_in_options_require_identity_pair(tmp_path: Path, options: tuple[str, ...]) -> None:
    result = native_cli(tmp_path / "mke.sqlite", "ask", "needle", *options)
    assert result.returncode == 2 and "Traceback" not in result.stderr


@pytest.mark.parametrize("limit", [0, 21])
def test_scoped_ask_invalid_limit_preserves_typed_failure(tmp_path: Path, limit: int) -> None:
    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, ("needle",))
    result = native_cli(
        database,
        "ask",
        "needle",
        "--source-id",
        source,
        "--publication-id",
        publication,
        "--limit",
        str(limit),
        "--json",
    )
    assert result.returncode == 1, result.stderr
    error = json.loads(result.stdout)
    assert error["schema_version"] == "mke.source_ask_response.v1"
    assert error["ok"] is False and error["problem"] == "invalid_request"
    assert error["active_publication_impact"] == "unchanged"


def test_scoped_ask_rejects_mixed_and_replaced_publication(tmp_path: Path) -> None:
    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, ("needle old",), fingerprint="f")
    _, other = publish_pages(database, ("needle other",), fingerprint="a")
    for selected in (other, "pub_missing"):
        result = native_cli(
            database, "ask", "needle", "--source-id", source, "--publication-id", selected, "--json"
        )
        assert result.returncode == 1, result.stderr
        assert json.loads(result.stdout)["problem"] == "evidence_not_found"
    same_source, replacement = publish_pages(
        database,
        ("needle old",),
        fingerprint="f",
        evidence_prefix="b",
    )
    assert same_source == source and replacement != publication
    stale = native_cli(
        database, "ask", "needle", "--source-id", source, "--publication-id", publication, "--json"
    )
    assert stale.returncode == 1 and json.loads(stale.stdout)["ok"] is False
    response = packet(database, source, replacement, "needle")
    assert response["scope"]["publication_revision"] == 2
    assert response["evidence"][0]["evidence"]["publication_id"] == replacement


@pytest.mark.parametrize(
    "strategy,query,text",
    [
        ("current", "needle", "needle"),
        ("numeric-grouping-v1", "needle 410000", "needle 410,000"),
        ("cjk-active-scan-overlap-v1", "知识检索范围", "知识检索"),
        ("mixed-cjk-fts-intent-v1", "needle 知识检索范围", "needle 知识检索"),
    ],
)
def test_scoped_ask_reuses_each_strategy_before_selection(
    tmp_path: Path,
    strategy: str,
    query: str,
    text: str,
) -> None:
    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, (text + " padding" * 30,) * 13, fingerprint="f")
    publish_pages(database, (query + " outsideonly",) * 20, fingerprint="a")
    result = native_cli(
        database,
        "--retrieval-strategy",
        strategy,
        "ask",
        query,
        "--source-id",
        source,
        "--publication-id",
        publication,
        "--limit",
        "3",
        "--json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    response = json.loads(result.stdout)
    assert len(response["evidence"]) == 3 and response["selection"]["status"] == "more_available"
    assert all(item["evidence"]["source_id"] == source for item in response["evidence"])


def test_scoped_ask_unicode_and_escaping_are_bounded_including_question(tmp_path: Path) -> None:
    database = tmp_path / "mke.sqlite"
    text = "needle " + '知识😀\\"\n' * 1200
    source, publication = publish_pages(database, (text,) * 20)
    response = packet(database, source, publication, 'needle "😀"', 20)
    encoded = json.dumps(
        response, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    assert len(encoded) <= 32768
    assert response["question"] == 'needle "😀"'
    assert response["selection"]["status"] == "more_available"
    excerpts = [item["excerpt"]["text"].encode() for item in response["evidence"]]
    assert all(len(excerpt) <= 2048 for excerpt in excerpts)
    assert sum(map(len, excerpts)) <= 16384
    human = native_cli(
        database,
        "ask",
        "needle",
        "--source-id",
        source,
        "--publication-id",
        publication,
        "--limit",
        "3",
    )
    assert human.returncode == 0 and "selection=more_available" in human.stdout
    assert "Evidence selection only" in human.stdout
