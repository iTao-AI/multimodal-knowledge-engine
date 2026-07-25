from __future__ import annotations

import asyncio
from pathlib import Path

from mke.application import KnowledgeEngine
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    CandidateEvidence,
    RunManifest,
)
from mke.interfaces.mcp_contract import McpRuntimeConfig, search_library_v1
from mke.interfaces.mcp_schemas import (
    SearchLibrarySuccessV2,
    SearchSelectionCappedV2,
    SearchSelectionMoreV2,
)
from mke.interfaces.mcp_server import build_mcp_server
from mke.runtime import RuntimeConfig


def test_search_exposes_selection_completeness(tmp_path: Path) -> None:
    server = build_mcp_server(
        McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path)
    )

    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}

    assert "search_library_v2" in tools


def test_oversized_v1_has_typed_exact_read_recovery(tmp_path: Path) -> None:
    config = McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path)
    engine = KnowledgeEngine(config.db_path)
    try:
        _publish_text(engine, ("prefix " + "x" * 1_000_001 + " late marker",))
    finally:
        engine.close()

    search = search_library_v1(config, "late marker", limit=1)

    assert search.root.problem == "response_too_large"  # type: ignore[union-attr]
    assert search.root.next_step == "use_search_library_v2"  # type: ignore[union-attr]


def test_cjk_cap_is_observable(tmp_path: Path) -> None:
    from mke.interfaces.mcp_completeness_contract import search_library_v2
    from mke.interfaces.mcp_schemas import SearchLibraryV2Request

    config = McpRuntimeConfig(
        RuntimeConfig(
            tmp_path / "mke.sqlite",
            retrieval_strategy="cjk-active-scan-overlap-v1",
        ),
        tmp_path,
    )
    engine = KnowledgeEngine(
        config.db_path,
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    try:
        _publish_text(
            engine,
            tuple(f"完整性上下文预算 第 {index} 条证据" for index in range(1, 12)),
        )
    finally:
        engine.close()

    response = search_library_v2(
        config,
        SearchLibraryV2Request(root={"query": "完整性上下文预算", "limit": 5}),
    )
    assert isinstance(response.root, SearchLibrarySuccessV2)
    while isinstance(response.root.selection, SearchSelectionMoreV2):
        response = search_library_v2(
            config,
            SearchLibraryV2Request(
                root={"cursor": response.root.selection.next_cursor}
            ),
        )
        assert isinstance(response.root, SearchLibrarySuccessV2)

    assert isinstance(response.root.selection, SearchSelectionCappedV2)
    assert response.root.selection.limit_reason == "retrieval_strategy_cap"


def _publish_text(engine: KnowledgeEngine, pages: tuple[str, ...]) -> None:
    source = engine.ensure_source(display_name="context.pdf", asset_sha256="a" * 64)
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
