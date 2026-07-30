from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from mke.adapters.sqlite import SQLiteStore
from mke.application import KnowledgeEngine
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    CandidateEvidence,
    RunManifest,
)
from mke.evaluation.agent_context_unit_baseline import (
    observe_prepared_agent_context_runtime,
    run_agent_context_unit_baseline,
)
from mke.evaluation.agent_context_unit_observer_protocol import (
    AgentContextObserverCase,
    AgentContextObserverContract,
    AgentContextSourceReceipt,
)


def _publish(engine: KnowledgeEngine, pages: tuple[str, ...]) -> None:
    source = engine.ensure_source("misleading-volcano-filename.pdf", "1" * 64)
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
            asset_sha256="1" * 64,
        ),
    )
    engine.activate_publication(run.run_id)


def _case(query: str = "volcano evidence") -> AgentContextObserverCase:
    return AgentContextObserverCase(
        query_id="q-volcano",
        query_text=query,
        source_content_fingerprints=("sha256:" + "1" * 64,),
        runtime_route_profile="fts5",
        observation_ids=("current-runtime-baseline-v1",),
    )


def _cjk_case() -> AgentContextObserverCase:
    return AgentContextObserverCase(
        query_id="q-cjk",
        query_text="发布证据检索",
        source_content_fingerprints=("sha256:" + "1" * 64,),
        runtime_route_profile="cjk-active-scan-overlap-v1",
        observation_ids=("current-runtime-baseline-v1",),
    )


def _source_contract(path: str, content: bytes) -> AgentContextObserverContract:
    return AgentContextObserverContract(
        sources=(
            AgentContextSourceReceipt(
                source_id="source-one",
                path=path,
                content_fingerprint=f"sha256:{hashlib.sha256(content).hexdigest()}",
                bytes=len(content),
                pages=1,
                nonempty_text_pages=1,
                extracted_text_utf8_bytes=1,
                pymupdf_version="test",
            ),
        ),
        cases=(),
    )


def _empty_observation(**_kwargs: object) -> tuple[()]:
    return ()


def test_baseline_ingests_descriptor_bound_source_bytes_after_path_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    source = root / "source.pdf"
    original = b"stable source bytes"
    replacement = b"replacement content"
    assert len(original) == len(replacement)
    source.write_bytes(original)
    ingested: list[bytes] = []

    def ingest_stable(_engine: KnowledgeEngine, path: Path) -> object:
        source.write_bytes(replacement)
        ingested.append(path.read_bytes())
        return object()

    monkeypatch.setattr(KnowledgeEngine, "ingest_pdf", ingest_stable)
    monkeypatch.setattr(
        "mke.evaluation.agent_context_unit_baseline."
        "observe_prepared_agent_context_runtime",
        _empty_observation,
    )

    run_agent_context_unit_baseline(
        contract=_source_contract("source.pdf", original),
        repository_root=root,
        workspace=tmp_path / "workspace",
    )

    assert ingested == [original]


def test_baseline_rejects_symlink_source_before_ingest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    content = b"stable source bytes"
    real = root / "real.pdf"
    real.write_bytes(content)
    (root / "source.pdf").symlink_to(real)
    calls = 0

    def reject_ingest(_engine: KnowledgeEngine, _path: Path) -> object:
        nonlocal calls
        calls += 1
        return object()

    monkeypatch.setattr(KnowledgeEngine, "ingest_pdf", reject_ingest)
    monkeypatch.setattr(
        "mke.evaluation.agent_context_unit_baseline."
        "observe_prepared_agent_context_runtime",
        _empty_observation,
    )

    with pytest.raises(ValueError, match="source identity path is invalid"):
        run_agent_context_unit_baseline(
            contract=_source_contract("source.pdf", content),
            repository_root=root,
            workspace=tmp_path / "workspace",
        )

    assert calls == 0


def test_baseline_marks_observation_started_once_at_first_source_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    first = b"first source"
    second = b"second source"
    (root / "first.pdf").write_bytes(first)
    (root / "second.pdf").write_bytes(second)
    contracts = tuple(
        _source_contract(name, content).sources[0]
        for name, content in (("first.pdf", first), ("second.pdf", second))
    )
    starts = 0

    def start() -> None:
        nonlocal starts
        starts += 1

    def ingest(_engine: KnowledgeEngine, _path: Path) -> object:
        return object()

    monkeypatch.setattr(KnowledgeEngine, "ingest_pdf", ingest)
    monkeypatch.setattr(
        "mke.evaluation.agent_context_unit_baseline."
        "observe_prepared_agent_context_runtime",
        _empty_observation,
    )

    run_agent_context_unit_baseline(
        contract=AgentContextObserverContract(sources=contracts, cases=()),
        repository_root=root,
        workspace=tmp_path / "workspace",
        on_source_open=start,
    )

    assert starts == 1


def test_real_runtime_uses_public_search_read_and_independent_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "mke.sqlite"
    engine = KnowledgeEngine(db_path)
    _publish(engine, ("volcano evidence alpha", "volcano evidence beta"))
    calls = {"search": 0, "read": 0, "open": 0, "rank": 0}
    search = KnowledgeEngine.search_evidence_page
    read = KnowledgeEngine.read_active_evidence
    open_export = SQLiteStore.open_read_only_export.__func__
    rank = SQLiteStore.observe_fts5_rank

    def record_search(self: KnowledgeEngine, *args: Any, **kwargs: Any):
        calls["search"] += 1
        return search(self, *args, **kwargs)

    def record_read(self: KnowledgeEngine, *args: Any, **kwargs: Any):
        calls["read"] += 1
        return read(self, *args, **kwargs)

    def record_open(cls: type[SQLiteStore], path: Path) -> SQLiteStore:
        calls["open"] += 1
        return open_export(cls, path)

    def record_rank(self: SQLiteStore, compiled_query: str):
        calls["rank"] += 1
        return rank(self, compiled_query)

    monkeypatch.setattr(KnowledgeEngine, "search_evidence_page", record_search)
    monkeypatch.setattr(KnowledgeEngine, "read_active_evidence", record_read)
    monkeypatch.setattr(SQLiteStore, "open_read_only_export", classmethod(record_open))
    monkeypatch.setattr(SQLiteStore, "observe_fts5_rank", record_rank)
    try:
        authority = observe_prepared_agent_context_runtime(
            engine=engine,
            db_path=db_path,
            cases=(_case(),),
        )
    finally:
        engine.close()

    portable = authority[0].portable
    assert calls == {"search": 1, "read": len(portable.items), "open": 1, "rank": 1}
    assert portable.items
    assert all(item.route == "fts5" for item in portable.items)
    assert tuple(item.rank for item in portable.items) == tuple(
        range(1, len(portable.items) + 1)
    )
    assert "misleading-volcano-filename.pdf" not in repr(portable)


def test_selected_locator_must_match_independent_rank_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "mke.sqlite"
    engine = KnowledgeEngine(db_path)
    _publish(engine, ("volcano evidence alpha", "volcano evidence beta"))
    original = SQLiteStore.observe_fts5_rank

    def reverse_rank(self: SQLiteStore, compiled_query: str):
        profile = original(self, compiled_query)
        return type(profile)(
            rank_order=tuple(reversed(profile.rank_order)),
            bm25_order=profile.bm25_order,
            rank_override_present=profile.rank_override_present,
            sql_trace=profile.sql_trace,
        )

    monkeypatch.setattr(SQLiteStore, "observe_fts5_rank", reverse_rank)
    try:
        observed = observe_prepared_agent_context_runtime(
            engine=engine,
            db_path=db_path,
            cases=(_case(),),
        )
    finally:
        engine.close()
    assert observed[0].portable.statuses[2] == "rank_miss"


def test_candidate_capacity_rejects_before_exact_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "mke.sqlite"
    engine = KnowledgeEngine(db_path)
    _publish(engine, tuple(f"volcano evidence {index}" for index in range(6)))
    reads = 0

    def reject_read(*_args: object, **_kwargs: object) -> None:
        nonlocal reads
        reads += 1
        raise AssertionError("read must not start")

    monkeypatch.setattr(engine, "read_active_evidence", reject_read)
    try:
        with pytest.raises(ValueError, match="observation capacity exceeded"):
            observe_prepared_agent_context_runtime(
                engine=engine,
                db_path=db_path,
                cases=(_case(),),
                max_candidate_pool=1,
            )
    finally:
        engine.close()
    assert reads == 0


@pytest.mark.parametrize("eligible_count", (10, 11))
def test_fts_candidate_count_retains_full_eligible_inventory(
    tmp_path: Path,
    eligible_count: int,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    engine = KnowledgeEngine(db_path)
    _publish(
        engine,
        tuple(
            f"volcano evidence eligible page {index}"
            for index in range(eligible_count)
        ),
    )
    try:
        observed = observe_prepared_agent_context_runtime(
            engine=engine,
            db_path=db_path,
            cases=(_case(),),
        )
    finally:
        engine.close()

    portable = observed[0].portable
    assert portable.candidate_count == eligible_count
    assert portable.selected_count == 5


@pytest.mark.parametrize("eligible_count", (10, 11))
def test_cjk_candidate_count_retains_full_eligible_inventory(
    tmp_path: Path,
    eligible_count: int,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    engine = KnowledgeEngine(
        db_path, retrieval_strategy="cjk-active-scan-overlap-v1"
    )
    _publish(
        engine,
        tuple(f"发布证据检索完整页面{index}" for index in range(eligible_count)),
    )
    try:
        observed = observe_prepared_agent_context_runtime(
            engine=engine,
            db_path=db_path,
            cases=(_cjk_case(),),
        )
    finally:
        engine.close()

    portable = observed[0].portable
    assert portable.candidate_count == eligible_count
    assert portable.selected_count == 5


def test_cjk_runtime_uses_public_selector_projection(tmp_path: Path) -> None:
    db_path = tmp_path / "mke.sqlite"
    engine = KnowledgeEngine(
        db_path, retrieval_strategy="cjk-active-scan-overlap-v1"
    )
    _publish(engine, ("发布证据检索完整页面", "不相关页面"))
    try:
        observed = observe_prepared_agent_context_runtime(
            engine=engine,
            db_path=db_path,
            cases=(_cjk_case(),),
        )
    finally:
        engine.close()

    portable = observed[0].portable
    assert portable.statuses[2] == "rank_hit"
    assert tuple(item.route for item in portable.items) == (
        "cjk-active-scan-overlap-v1",
    )
    assert portable.items[0].score.kind == "cjk_overlap"


def test_current_fts_runtime_records_compiled_empty_cjk_as_policy_miss(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    engine = KnowledgeEngine(db_path, retrieval_strategy="numeric-grouping-v1")
    _publish(engine, ("发布证据检索完整页面",))
    case = AgentContextObserverCase(
        query_id="q-cjk-policy-miss",
        query_text="发布证据检索",
        source_content_fingerprints=("sha256:" + "1" * 64,),
        runtime_route_profile="fts5",
        observation_ids=("current-runtime-baseline-v1",),
    )
    try:
        observed = observe_prepared_agent_context_runtime(
            engine=engine,
            db_path=db_path,
            cases=(case,),
        )
    finally:
        engine.close()

    portable = observed[0].portable
    assert portable.expected_route == "fts5"
    assert portable.statuses[0] == "query_policy_miss"
    assert portable.statuses[6] == "provenance_complete"
