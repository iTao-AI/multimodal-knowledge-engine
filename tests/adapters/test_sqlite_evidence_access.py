import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Literal, cast

import pytest

from mke.adapters.sqlite import EvidenceNotFoundError, EvidenceResponseTooLargeError
from mke.application import KnowledgeEngine
from mke.application.evidence_access import build_excerpt
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    ActiveAuthoritySnapshot,
    CandidateEvidence,
    RunManifest,
    RunState,
)

ROOT = Path(__file__).resolve().parents[2]
FTS_QUERY_PLAN = (
    ROOT / "tests/fixtures/retrieval-order-v1/fts-query-plan.json"
)
FTS_QUERY_PLAN_SHA256 = (
    "1f6a70a69edb9a3b182e21a9b125a37d81ed4dca869c16d1f5d5b807554ffdc1"
)
FTS_QUERY_PLAN_LIMITATIONS = (
    "fixed_profile_structural_evidence_only",
    "not_wall_clock_performance_evidence",
    "not_relevance_quality_evidence",
    "not_segmentation_or_contextual_retrieval_evidence",
    "not_runtime_promotion_evidence",
    "not_cross_sqlite_portability_guarantee",
    "not_production_performance_guarantee",
    "not_future_sqlite_planner_stability_guarantee",
)
FTS_QUERY_PLAN_PROFILE_FIELDS = (
    "active_evidence_fts_sql",
    "automatic_index",
    "compile_options",
    "fts5_rank_configuration",
    "fts5_source_id",
    "journal_mode",
    "sqlite_source_id",
    "sqlite_version",
    "temp_store",
)


def test_search_page_and_read_share_active_authority(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        evidence_id = _publish(engine, ("publication authority one", "publication authority two"))
        observed: list[ActiveAuthoritySnapshot] = []
        page = engine.search_evidence_page(
            "publication authority",
            position=0,
            page_size=1,
            authority_validator=observed.append,
        )
        read = engine.read_active_evidence(
            evidence_id,
            authority_validator=lambda authority: observed.append(authority),
        )
        assert page.more_in_selected_pool is True
        assert page.authority == read.authority == observed[0] == observed[1]
        assert read.text == "publication authority one"
    finally:
        engine.close()


def test_read_rejects_unknown_evidence(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        with pytest.raises(EvidenceNotFoundError):
            engine.read_active_evidence(
                "ev_missing",
                authority_validator=lambda _authority: None,
            )
    finally:
        engine.close()


def test_read_continuation_uses_bounded_blob_range_without_full_text(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        evidence_id = _publish(engine, ("prefix " + "x" * 50_000 + " suffix",))
        statements: list[str] = []
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.set_trace_callback(statements.append)
        snapshot = engine.read_active_evidence(
            evidence_id,
            offset_bytes=4096,
            range_bytes=1024,
            authority_validator=lambda _authority: None,
        )
        connection.set_trace_callback(None)

        assert snapshot.text is None
        assert len(snapshot.range_bytes) <= 1027
        evidence_queries = [
            statement
            for statement in statements
            if "WHERE evidence.evidence_id" in statement
        ]
        assert len(evidence_queries) == 2
        assert "length(CAST(evidence.text AS BLOB))" in evidence_queries[0]
        assert "evidence.text," not in evidence_queries[0]
        assert "substr(CAST(evidence.text AS BLOB)" in evidence_queries[1]
        assert "evidence.text," not in evidence_queries[1]
    finally:
        engine.close()


def test_oversized_initial_read_rejects_before_materializing_text(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        evidence_id = _publish(engine, ("bounded",))
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.execute(
            "UPDATE evidence SET text = ? WHERE evidence_id = ?",
            ("x" * (16 * 1024 * 1024 + 1), evidence_id),
        )
        connection.commit()
        statements: list[str] = []
        connection.set_trace_callback(statements.append)
        with pytest.raises(EvidenceResponseTooLargeError):
            engine.read_active_evidence(
                evidence_id,
                authority_validator=lambda _authority: None,
            )
        connection.set_trace_callback(None)

        evidence_queries = [
            statement
            for statement in statements
            if "WHERE evidence.evidence_id" in statement
        ]
        assert len(evidence_queries) == 1
        assert "length(CAST(evidence.text AS BLOB))" in evidence_queries[0]
        assert "evidence.text," not in evidence_queries[0]
    finally:
        engine.close()


@pytest.mark.parametrize("position", (0, 1, 7))
def test_fts_page_uses_metadata_limit_offset_without_gaps(
    tmp_path: Path, position: int
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        _publish(engine, tuple(f"authority match {index}" for index in range(12)))
        statements: list[str] = []
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.set_trace_callback(statements.append)
        page = engine.search_evidence_page(
            "authority",
            position=position,
            page_size=3,
            authority_validator=lambda _authority: None,
        )
        connection.set_trace_callback(None)

        assert [item.provenance.result.locator_start for item in page.results] == list(
            range(position + 1, position + 4)
        )
        metadata = [
            statement
            for statement in statements
            if "active_evidence_fts MATCH" in statement and "LIMIT" in statement
        ]
        assert len(metadata) == 1
        assert "active_evidence_fts.text" not in metadata[0]
        assert "LIMIT 4 OFFSET" in metadata[0]
        page_order = metadata[0].split("LIMIT 4 OFFSET", maxsplit=1)[0].rsplit(
            "ORDER BY", maxsplit=1
        )[1]
        assert "evidence_id" not in page_order
        for stable_key in (
            "score",
            "locator_start",
            "locator_kind",
            "locator_end",
            "source_sha256",
        ):
            assert stable_key in page_order
    finally:
        engine.close()


def test_fts_page_fixed_profile_plan_matches_frozen_record(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        _publish(
            engine,
            tuple(
                f"authority active page {index}"
                for index in range(12)
            ),
        )
        engine.ensure_source("inactive.pdf", "b" * 64)

        candidate_source = engine.ensure_source(
            "candidate.pdf",
            "c" * 64,
        )
        candidate = engine.create_run(candidate_source.source_id)
        _persist_candidate(
            engine,
            run_id=candidate.run_id,
            asset_sha256="c" * 64,
            evidence_id="ev_candidate",
            text="authority candidate must remain inactive",
        )

        failed_source = engine.ensure_source("failed.pdf", "d" * 64)
        failed = engine.create_run(failed_source.source_id)
        engine._store.mark_run_failed(  # pyright: ignore[reportPrivateUsage]
            failed.run_id
        )

        superseded_source = engine.ensure_source(
            "superseded.pdf",
            "e" * 64,
        )
        superseded = engine.create_run(superseded_source.source_id)
        newer = engine.create_run(superseded_source.source_id)
        _persist_candidate(
            engine,
            run_id=superseded.run_id,
            asset_sha256="e" * 64,
            evidence_id="ev_superseded",
            text="authority superseded must remain inactive",
        )
        activation = engine.activate_publication(superseded.run_id)
        assert activation.published is False
        assert activation.run_state is RunState.SUPERSEDED
        assert engine.get_run(newer.run_id).state is RunState.QUEUED

        connection = (
            engine._store._connection  # pyright: ignore[reportPrivateUsage]
        )
        fts_ids = {
            str(row["evidence_id"])
            for row in connection.execute(
                "SELECT evidence_id FROM active_evidence_fts"
            ).fetchall()
        }
        active_ids = {
            f"ev_{index:032x}" for index in range(1, 13)
        }
        assert fts_ids == active_ids
        assert "ev_candidate" not in fts_ids
        assert "ev_superseded" not in fts_ids

        statements: list[str] = []
        connection.set_trace_callback(statements.append)
        page = engine.search_evidence_page(
            "authority",
            position=0,
            page_size=3,
            authority_validator=lambda _authority: None,
        )
        connection.set_trace_callback(None)

        assert [
            item.provenance.result.evidence_id
            for item in page.results
        ] == [
            f"ev_{index:032x}" for index in range(1, 4)
        ]
        page_queries = [
            statement
            for statement in statements
            if "WITH matched AS MATERIALIZED" in statement
            and "page AS (" in statement
        ]
        assert len(page_queries) == 1
        page_query = page_queries[0]
        assert page_query.count(" MATCH ") == 1
        assert "active_evidence_fts.text" not in page_query
        assert "evidence.text," not in page_query
        page_order = (
            page_query.split("page AS (", maxsplit=1)[1]
            .split("LIMIT", maxsplit=1)[0]
            .rsplit("ORDER BY", maxsplit=1)[1]
        )
        final_order = page_query.rsplit("ORDER BY", maxsplit=1)[1]
        assert all(
            ".text" not in order
            for order in (page_order, final_order)
        )
        top_level_statements = [
            statement
            for statement in statements
            if not statement.lstrip().startswith("--")
            and statement.lstrip().upper().startswith(
                ("SELECT", "WITH")
            )
        ]
        assert len(top_level_statements) == 6
        assert sum(
            "FROM libraries" in statement
            for statement in top_level_statements
        ) == 1
        assert sum(
            "COUNT(*) AS source_count" in statement
            for statement in top_level_statements
        ) == 1
        assert sum(
            "run_manifests.extractor_fingerprint" in statement
            and "GROUP BY sources.source_id" in statement
            for statement in top_level_statements
        ) == 1
        assert sum(
            "WITH matched AS MATERIALIZED" in statement
            for statement in top_level_statements
        ) == 1
        assert len(
            [
                statement
                for statement in top_level_statements
                if "SELECT evidence_id, text" in statement
                and "WHERE evidence_id IN (" in statement
            ]
        ) == 1
        assert len(
            [
                statement
                for statement in top_level_statements
                if "WHERE evidence.evidence_id IN (" in statement
            ]
        ) == 1

        plan_rows = connection.execute(
            "EXPLAIN QUERY PLAN " + page_query
        ).fetchall()
        normalized_nodes = [
            {
                "operator": str(row["detail"]).split(maxsplit=1)[0],
                "detail": str(row["detail"]),
            }
            for row in plan_rows
        ]
        details = [node["detail"] for node in normalized_nodes]
        assert "MATERIALIZE matched" in details
        assert any(
            detail.startswith(
                "SCAN active_evidence_fts VIRTUAL TABLE INDEX"
            )
            for detail in details
        )
        assert any("SCAN matched" in detail for detail in details)
        assert any(
            detail == "USE TEMP B-TREE FOR ORDER BY"
            for detail in details
        )

        compile_options = {
            str(row[0])
            for row in connection.execute(
                "PRAGMA compile_options"
            ).fetchall()
        }
        table_sql_row = connection.execute(
            """
            SELECT sql
            FROM sqlite_schema
            WHERE type = 'table' AND name = 'active_evidence_fts'
            """
        ).fetchone()
        assert table_sql_row is not None
        live_record = {
            "schema_version": (
                "mke.retrieval_order_fts_query_plan.v1"
            ),
            "sqlite_profile": {
                "sqlite_version": sqlite3.sqlite_version,
                "sqlite_source_id": str(
                    connection.execute(
                        "SELECT sqlite_source_id()"
                    ).fetchone()[0]
                ),
                "fts5_source_id": str(
                    connection.execute(
                        "SELECT fts5_source_id()"
                    ).fetchone()[0]
                ),
                "compile_options": sorted(
                    option
                    for option in compile_options
                    if option == "ENABLE_FTS5"
                    or option.startswith("TEMP_STORE=")
                    or option.startswith("THREADSAFE=")
                ),
                "journal_mode": str(
                    connection.execute(
                        "PRAGMA journal_mode"
                    ).fetchone()[0]
                ),
                "temp_store": int(
                    connection.execute(
                        "PRAGMA temp_store"
                    ).fetchone()[0]
                ),
                "automatic_index": int(
                    connection.execute(
                        "PRAGMA automatic_index"
                    ).fetchone()[0]
                ),
                "fts5_rank_configuration": (
                    "sqlite_fts5_default_bm25"
                ),
                "active_evidence_fts_sql": " ".join(
                    str(table_sql_row["sql"]).split()
                ),
            },
            "strategy_revision": 2,
            "query_policy_revision": 1,
            "fixture_authority": {
                "active_only": True,
                "active_fts_row_count": len(fts_ids),
                "inactive_source_count": 1,
                "validated_candidate_count": 1,
                "failed_run_count": 1,
                "superseded_evidence_count": 1,
            },
            "query": {
                "parameters": ['"authority"', 4, 0],
                "expanded_sql_sha256": hashlib.sha256(
                    page_query.encode()
                ).hexdigest(),
                "statement_count": len(top_level_statements),
                "fts_match_count": page_query.count(" MATCH "),
                "metadata_only_page_selection": True,
                "bulk_text_load_count": 1,
                "bulk_provenance_load_count": 1,
            },
            "normalized_nodes": normalized_nodes,
            "limitations": list(FTS_QUERY_PLAN_LIMITATIONS),
        }
        comparison = _fixed_profile_comparison(
            live_record=live_record,
            frozen_bytes=FTS_QUERY_PLAN.read_bytes(),
        )
        if comparison == "not_applicable":
            pytest.skip(
                "exact fixed-profile equality not applicable: "
                "complete live SQLite/FTS profile differs from "
                "the sealed profile"
            )
        assert comparison == "exact"
    finally:
        engine.close()


def test_fixed_profile_comparison_accepts_exact_sealed_profile() -> None:
    frozen_bytes = FTS_QUERY_PLAN.read_bytes()
    frozen_record = json.loads(frozen_bytes)

    assert _fixed_profile_comparison(
        live_record=frozen_record,
        frozen_bytes=frozen_bytes,
    ) == "exact"


@pytest.mark.parametrize(
    "profile_field",
    FTS_QUERY_PLAN_PROFILE_FIELDS,
)
def test_fixed_profile_comparison_routes_every_profile_mismatch(
    profile_field: str,
) -> None:
    frozen_bytes = FTS_QUERY_PLAN.read_bytes()
    live_record = copy.deepcopy(json.loads(frozen_bytes))
    profile = live_record["sqlite_profile"]
    original = profile[profile_field]
    if isinstance(original, list):
        profile[profile_field] = [*original, "DIFFERENT_PROFILE"]
    elif isinstance(original, int):
        profile[profile_field] = original + 1
    else:
        profile[profile_field] = f"different:{original}"

    assert _fixed_profile_comparison(
        live_record=live_record,
        frozen_bytes=frozen_bytes,
    ) == "not_applicable"


def test_fixed_profile_comparison_rejects_tampered_fixture_before_routing(
) -> None:
    frozen_bytes = FTS_QUERY_PLAN.read_bytes()
    live_record = copy.deepcopy(json.loads(frozen_bytes))
    live_record["sqlite_profile"]["sqlite_version"] = "different"
    tampered_bytes = frozen_bytes.replace(
        b"not_wall_clock_performance_evidence",
        b"not_wall_clock_performance_claim",
    )

    with pytest.raises(
        AssertionError,
        match="L6_FTS_QUERY_PLAN_FIXTURE_BYTES_INVALID",
    ):
        _fixed_profile_comparison(
            live_record=live_record,
            frozen_bytes=tampered_bytes,
        )


def test_fts_page_text_budget_always_progresses_first_candidate(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        _publish(
            engine,
            (
                "authority " + "x" * (9 * 1024 * 1024),
                "authority " + "y" * (9 * 1024 * 1024),
                "authority tail",
            ),
        )
        first = engine.search_evidence_page(
            "authority",
            position=0,
            page_size=3,
            authority_validator=lambda _authority: None,
        )
        second = engine.search_evidence_page(
            "authority",
            position=1,
            page_size=3,
            authority_validator=lambda _authority: None,
        )

        assert len(first.results) == 1
        assert first.more_in_selected_pool is True
        assert first.results[0].provenance.result.locator_start == 1
        assert [item.provenance.result.locator_start for item in second.results] == [2, 3]
    finally:
        engine.close()


def test_search_preserves_numeric_and_cjk_match_hints(tmp_path: Path) -> None:
    numeric = KnowledgeEngine(tmp_path / "numeric.sqlite")
    cjk = KnowledgeEngine(
        tmp_path / "cjk.sqlite",
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    try:
        _publish(numeric, ("前缀" * 1000 + " 560 033 202 243 late",))
        numeric_page = numeric.search_evidence_page(
            "560033202243",
            position=0,
            page_size=1,
            authority_validator=lambda _authority: None,
        )
        assert [hint.text for hint in numeric_page.results[0].hints] == [
            "560033202243",
            "560 033 202 243",
        ]
        numeric_excerpt = build_excerpt(
            numeric_page.results[0].provenance.result.text,
            numeric_page.results[0].hints,
        )
        assert numeric_excerpt.kind == "query_window"
        assert "560 033 202 243" in numeric_excerpt.text

        _publish(cjk, ("前缀" * 1000 + " 发布证据检索 late",))
        cjk_page = cjk.search_evidence_page(
            "发布证据检索额外内容",
            position=0,
            page_size=1,
            authority_validator=lambda _authority: None,
        )
        matched = cjk_page.results[0].hints
        assert matched
        assert all(hint.text in "发布证据检索" for hint in matched)
        cjk_excerpt = build_excerpt(
            cjk_page.results[0].provenance.result.text,
            matched,
        )
        assert cjk_excerpt.kind == "query_window"
        assert any(hint.text in cjk_excerpt.text for hint in matched)
    finally:
        numeric.close()
        cjk.close()


@pytest.mark.parametrize("eligible", (9, 10, 11))
@pytest.mark.parametrize("page_size", (5, 10))
def test_cjk_page_cap_uses_actual_strategy_discard(
    tmp_path: Path, eligible: int, page_size: int
) -> None:
    engine = KnowledgeEngine(
        tmp_path / f"cjk-{eligible}-{page_size}.sqlite",
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    try:
        _publish(
            engine,
            tuple(f"发布证据检索 完整页面 {index}" for index in range(eligible)),
        )
        position = 0
        terminal: Any = None
        while True:
            terminal = engine.search_evidence_page(
                "发布证据检索",
                position=position,
                page_size=page_size,
                authority_validator=lambda _authority: None,
            )
            position += len(terminal.results)
            if not terminal.more_in_selected_pool:
                break
        assert terminal.eligible_discarded_by_cap is (eligible == 11)
        assert position == min(eligible, 10)
    finally:
        engine.close()


def _publish(engine: KnowledgeEngine, pages: tuple[str, ...]) -> str:
    source = engine.ensure_source("fixture.pdf", "a" * 64)
    run = engine.create_run(source.source_id)
    evidence = [
        CandidateEvidence(
            evidence_id=f"ev_{index:032x}",
            locator_kind="page",
            locator_start=index,
            locator_end=index,
            text=text,
        )
        for index, text in enumerate(pages, start=1)
    ]
    engine.persist_validated_candidate(
        run.run_id,
        evidence,
        RunManifest(
            run_id=run.run_id,
            evidence_count=len(evidence),
            required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
            extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
            asset_sha256="a" * 64,
        ),
    )
    engine.activate_publication(run.run_id)
    return evidence[0].evidence_id


def _persist_candidate(
    engine: KnowledgeEngine,
    *,
    run_id: str,
    asset_sha256: str,
    evidence_id: str,
    text: str,
) -> None:
    engine.persist_validated_candidate(
        run_id,
        [
            CandidateEvidence(
                evidence_id=evidence_id,
                locator_kind="page",
                locator_start=1,
                locator_end=1,
                text=text,
            )
        ],
        RunManifest(
            run_id=run_id,
            evidence_count=1,
            required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
            extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
            asset_sha256=asset_sha256,
        ),
    )


def _fixed_profile_comparison(
    *,
    live_record: dict[str, Any],
    frozen_bytes: bytes,
) -> Literal["exact", "not_applicable"]:
    assert (
        hashlib.sha256(frozen_bytes).hexdigest()
        == FTS_QUERY_PLAN_SHA256
    ), "L6_FTS_QUERY_PLAN_FIXTURE_BYTES_INVALID"
    frozen_value: object = json.loads(frozen_bytes)
    frozen_record = _string_keyed_dict(frozen_value)
    assert set(frozen_record) == {
        "fixture_authority",
        "limitations",
        "normalized_nodes",
        "query",
        "query_policy_revision",
        "schema_version",
        "sqlite_profile",
        "strategy_revision",
    }
    assert (
        frozen_record["schema_version"]
        == "mke.retrieval_order_fts_query_plan.v1"
    )
    assert frozen_record["strategy_revision"] == 2
    assert frozen_record["query_policy_revision"] == 1
    assert frozen_record["limitations"] == list(
        FTS_QUERY_PLAN_LIMITATIONS
    )
    assert frozen_record["fixture_authority"] == {
        "active_fts_row_count": 12,
        "active_only": True,
        "failed_run_count": 1,
        "inactive_source_count": 1,
        "superseded_evidence_count": 1,
        "validated_candidate_count": 1,
    }
    query = _string_keyed_dict(frozen_record["query"])
    assert set(query) == {
        "bulk_provenance_load_count",
        "bulk_text_load_count",
        "expanded_sql_sha256",
        "fts_match_count",
        "metadata_only_page_selection",
        "parameters",
        "statement_count",
    }
    assert query["parameters"] == ['"authority"', 4, 0]
    assert query["statement_count"] == 6
    assert query["fts_match_count"] == 1
    assert query["metadata_only_page_selection"] is True
    assert query["bulk_text_load_count"] == 1
    assert query["bulk_provenance_load_count"] == 1
    expanded_sql_sha256 = query["expanded_sql_sha256"]
    assert isinstance(expanded_sql_sha256, str)
    assert len(expanded_sql_sha256) == 64
    assert set(expanded_sql_sha256) <= set("0123456789abcdef")
    normalized_nodes_value = frozen_record["normalized_nodes"]
    assert isinstance(normalized_nodes_value, list)
    normalized_nodes = cast(list[object], normalized_nodes_value)
    assert normalized_nodes
    for node_value in normalized_nodes:
        node = _string_keyed_dict(node_value)
        assert set(node) == {"detail", "operator"}
        assert isinstance(node["detail"], str)
        assert isinstance(node["operator"], str)
    frozen_profile = _string_keyed_dict(
        frozen_record["sqlite_profile"]
    )
    assert set(frozen_profile) == set(
        FTS_QUERY_PLAN_PROFILE_FIELDS
    )
    compile_options_value = frozen_profile["compile_options"]
    assert isinstance(compile_options_value, list)
    compile_option_objects = cast(
        list[object],
        compile_options_value,
    )
    assert all(
        isinstance(option, str)
        for option in compile_option_objects
    )
    compile_options = cast(list[str], compile_option_objects)
    assert compile_options == sorted(set(compile_options))
    assert "ENABLE_FTS5" in compile_options
    live_profile = live_record.get("sqlite_profile")
    assert isinstance(live_profile, dict)
    if live_profile != frozen_profile:
        return "not_applicable"
    assert live_record == frozen_record, (
        "L6_FTS_QUERY_PLAN_RECORD_MISSING_OR_DRIFT\n"
        + json.dumps(
            live_record,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
    )
    return "exact"


def _string_keyed_dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    object_dict = cast(dict[object, object], value)
    assert all(isinstance(key, str) for key in object_dict)
    return cast(dict[str, object], object_dict)
