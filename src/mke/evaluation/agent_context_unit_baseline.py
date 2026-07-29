"""Label-blind current-runtime observation for the diagnostic context protocol."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

from mke.adapters.sqlite import SQLiteStore
from mke.application import KnowledgeEngine
from mke.application.evidence_access import build_excerpt
from mke.evaluation.agent_context_unit_observation import (
    AuthorityObservation,
    ObservationBounds,
    PortableObservation,
    PortableObservationItem,
    PortableScoreToken,
    validate_observation_inventory,
)
from mke.evaluation.agent_context_unit_observer_protocol import (
    AgentContextObserverCase,
    AgentContextObserverContract,
)
from mke.evaluation.diagnostic_ports import (
    EvaluationEvidenceSnapshot,
    validate_fts_projection,
)
from mke.evaluation.source_identity import read_no_follow_regular_file
from mke.retrieval.cjk_active_scan import (
    CjkActiveScanCandidate,
    compile_cjk_overlap_terms,
    select_cjk_active_scan_candidates,
)
from mke.retrieval.query_policy import compile_fts5_query_diagnostic


def observe_prepared_agent_context_runtime(
    *,
    engine: KnowledgeEngine,
    db_path: Path,
    cases: tuple[AgentContextObserverCase, ...],
    max_candidate_pool: int = 1_000,
) -> tuple[AuthorityObservation, ...]:
    """Observe an already-published fresh workspace through public contracts."""
    bounds = ObservationBounds(max_candidate_pool=max_candidate_pool)
    snapshot = engine.compiled_library_snapshot(format_version="v2")
    source_fingerprints = {
        source.source_id: source.content_fingerprint for source in snapshot.sources
    }
    diagnostics = SQLiteStore.open_read_only_export(db_path)
    try:
        evidence = diagnostics.list_evaluation_evidence()
        projection = diagnostics.list_fts_projection()
        validate_observation_inventory(
            bounds,
            source_count=len(snapshot.sources),
            evidence_count=len(evidence),
            page_count=sum(item.locator_kind == "page" for item in evidence),
            source_text_utf8_bytes=sum(len(item.text.encode("utf-8")) for item in evidence),
            candidate_count=0,
            rank_count=0,
            result_count=0,
        )
        validate_fts_projection(evidence, projection)
        return tuple(
            _observe_case(
                engine=engine,
                diagnostics=diagnostics,
                case=case,
                evidence=evidence,
                source_fingerprints=source_fingerprints,
                bounds=bounds,
            )
            for case in cases
        )
    finally:
        diagnostics.close()


def run_agent_context_unit_baseline(
    *,
    contract: AgentContextObserverContract,
    repository_root: Path,
    workspace: Path,
    on_source_open: Callable[[], None] | None = None,
) -> tuple[AuthorityObservation, ...]:
    """Ingest the frozen development sources into one caller-owned fresh workspace."""
    if workspace.exists():
        raise ValueError("baseline workspace must be fresh")
    workspace.mkdir(parents=True)
    source_staging = workspace / "source-inputs"
    source_staging.mkdir()
    db_path = workspace / "mke.sqlite"
    source_opened = False

    def mark_first_source_open() -> None:
        nonlocal source_opened
        if source_opened:
            return
        source_opened = True
        if on_source_open is not None:
            on_source_open()

    engine = KnowledgeEngine(db_path, retrieval_strategy="numeric-grouping-v1")
    try:
        for index, receipt in enumerate(contract.sources):
            source = read_no_follow_regular_file(
                repository_root,
                receipt.path,
                on_open=mark_first_source_open,
            )
            if (
                source.identity["bytes"] != receipt.bytes
                or f"sha256:{source.identity['sha256']}"
                != receipt.content_fingerprint
            ):
                raise ValueError("baseline source identity is invalid")
            stable_path = source_staging / f"{index:04d}.pdf"
            stable_path.write_bytes(source.content)
            if stable_path.read_bytes() != source.content:
                raise ValueError("baseline stable source copy is invalid")
            engine.ingest_pdf(stable_path)
        return observe_prepared_agent_context_runtime(
            engine=engine,
            db_path=db_path,
            cases=contract.cases,
        )
    finally:
        engine.close()


def _observe_case(
    *,
    engine: KnowledgeEngine,
    diagnostics: SQLiteStore,
    case: AgentContextObserverCase,
    evidence: tuple[EvaluationEvidenceSnapshot, ...],
    source_fingerprints: dict[str, str],
    bounds: ObservationBounds,
) -> AuthorityObservation:
    page = engine.search_evidence_page(
        case.query_text,
        position=0,
        page_size=bounds.max_primary_results,
        authority_validator=lambda _authority: None,
    )
    compiled_fts = compile_fts5_query_diagnostic(case.query_text).compiled_query
    route = (
        "cjk-active-scan-overlap-v1"
        if not compiled_fts
        and page.strategy_id == "cjk-active-scan-overlap-v1"
        else "fts5"
    )
    if route == "fts5":
        ranked, candidate_count = _fts_rank(diagnostics, case, bounds)
    elif route == "cjk-active-scan-overlap-v1":
        ranked, candidate_count = _cjk_rank(
            evidence, source_fingerprints, case, bounds
        )
    else:
        ranked, candidate_count = {}, 0
    validate_observation_inventory(
        bounds,
        source_count=len(source_fingerprints),
        evidence_count=len(evidence),
        page_count=sum(item.locator_kind == "page" for item in evidence),
        source_text_utf8_bytes=sum(len(item.text.encode("utf-8")) for item in evidence),
        candidate_count=candidate_count,
        rank_count=len(ranked),
        result_count=len(page.results),
    )
    items: list[PortableObservationItem] = []
    source_ids: list[str] = []
    publication_ids: list[str] = []
    run_ids: list[str] = []
    evidence_ids: list[str] = []
    parity = True
    for position, selected in enumerate(page.results, start=1):
        result = selected.provenance.result
        score = ranked.get(result.evidence_id)
        if score is None or score[0] != position:
            parity = False
            continue
        exact = engine.read_active_evidence(
            result.evidence_id,
            authority_validator=lambda authority: _require_same_authority(
                page.authority, authority
            ),
        )
        if exact.text is None:
            raise ValueError("exact Evidence read is incomplete")
        exact_bytes = exact.text.encode("utf-8")
        result_bytes = result.text.encode("utf-8")
        excerpt = build_excerpt(result.text, selected.hints)
        if exact_bytes != result_bytes:
            raise ValueError("Search and Read Evidence differ")
        digest = f"sha256:{sha256(exact_bytes).hexdigest()}"
        items.append(
            PortableObservationItem(
                content_fingerprint=selected.provenance.content_fingerprint,
                locator_kind=result.locator_kind,  # type: ignore[arg-type]
                locator_start=result.locator_start,
                locator_end=result.locator_end,
                text_sha256=digest,
                route=route,
                rank=position,
                score=score[1],
                hints=tuple(hint.text for hint in selected.hints),
                excerpt=excerpt,
                exact_read_sha256=digest,
                original_utf8_bytes=len(result_bytes),
                excerpt_utf8_bytes=excerpt.returned_utf8_bytes,
                exact_read_utf8_bytes=len(exact_bytes),
            )
        )
        source_ids.append(result.source_id)
        publication_ids.append(result.publication_id)
        run_ids.append(selected.provenance.run_id)
        evidence_ids.append(result.evidence_id)
    complete = parity and len(items) == len(page.results)
    provenance_complete = route == case.runtime_route_profile and all(
        item.content_fingerprint in case.source_content_fingerprints for item in items
    )
    statuses = (
        "query_policy_hit" if compiled_fts else "query_policy_miss",
        "candidate_hit" if candidate_count else "candidate_miss",
        "rank_hit" if complete else "rank_miss",
        "delivery_hit" if items else "delivery_miss",
        "output_complete" if complete else "output_incomplete",
        "exact_read_complete" if complete else "exact_read_incomplete",
        "provenance_complete" if provenance_complete else "provenance_incomplete",
    )
    portable = PortableObservation(
        query_id=case.query_id,
        query_text=case.query_text,
        expected_route=case.runtime_route_profile,
        profile_identity=case.observation_ids[0],
        statuses=statuses,
        items=tuple(items),
        candidate_count=candidate_count,
        selected_count=len(items),
        delivered_utf8_bytes=sum(item.excerpt_utf8_bytes for item in items),
    )
    return AuthorityObservation(
        portable=portable,
        source_ids=tuple(source_ids),
        publication_ids=tuple(publication_ids),
        run_ids=tuple(run_ids),
        evidence_ids=tuple(evidence_ids),
    )


def _fts_rank(
    diagnostics: SQLiteStore,
    case: AgentContextObserverCase,
    bounds: ObservationBounds,
) -> tuple[dict[str, tuple[int, PortableScoreToken]], int]:
    query = compile_fts5_query_diagnostic(case.query_text).compiled_query
    if not query:
        return {}, 0
    profile = diagnostics.observe_fts5_rank(query)
    candidate_count = len(profile.rank_order)
    if candidate_count > bounds.max_candidate_pool:
        raise ValueError("observation capacity exceeded")
    return (
        {
            item.evidence_id: (
                position,
                PortableScoreToken(
                    "fts5_rank", item.rank_score.hex(), item.bm25_score.hex()
                ),
            )
            for position, item in enumerate(
                profile.rank_order[: bounds.max_diagnostic_rank], start=1
            )
        },
        candidate_count,
    )


def _cjk_rank(
    evidence: tuple[EvaluationEvidenceSnapshot, ...],
    source_fingerprints: dict[str, str],
    case: AgentContextObserverCase,
    bounds: ObservationBounds,
) -> tuple[dict[str, tuple[int, PortableScoreToken]], int]:
    candidates = tuple(
        CjkActiveScanCandidate(
            evidence_id=item.evidence_id,
            publication_id=item.publication_id,
            source_id=item.source_id,
            locator_kind=item.locator_kind,
            locator_start=item.locator_start,
            locator_end=item.locator_end,
            text=item.text,
            document_id=source_fingerprints[item.source_id],
        )
        for item in evidence
    )
    terms = compile_cjk_overlap_terms(case.query_text, require_terms=True)
    selected = select_cjk_active_scan_candidates(candidates, terms.terms)
    if selected.eligible_count > bounds.max_candidate_pool:
        raise ValueError("observation capacity exceeded")
    return (
        {
            item.evidence_id: (
                position,
                PortableScoreToken(
                    "cjk_overlap",
                    float(item.overlap_count).hex(),
                    item.overlap_ratio.hex(),
                ),
            )
            for position, item in enumerate(
                selected.results[: bounds.max_diagnostic_rank], start=1
            )
        },
        selected.eligible_count,
    )


def _require_same_authority(expected: object, actual: object) -> None:
    if expected != actual:
        raise ValueError("Search and Read authority differ")
