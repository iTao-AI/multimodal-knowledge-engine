from __future__ import annotations

import hashlib
import json
import math
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from mke.application import AskValidationError, KnowledgeEngine, PdfIngestError
from mke.domain import RunState, SearchResult
from mke.evaluation.chinese_diagnostics import classify_miss
from mke.evaluation.chinese_protocol import (
    ChineseEvaluationDocument,
    ChineseEvaluationQuery,
    ChineseProtocolValidationError,
    ChineseRetrievalProtocol,
    QrelAdjudication,
    load_chinese_retrieval_protocol,
    snapshot_chinese_retrieval_fixtures,
)
from mke.evaluation.chinese_report import (
    CHINESE_RETRIEVAL_LIMITATIONS,
    ChineseQueryResult,
    ChineseRetrievalReport,
    E3BDecisionEvidence,
    FtsRankEvidence,
    FtsRankScoreEvidence,
    IntegrityFailure,
)
from mke.evaluation.diagnostic_ports import (
    EvaluationEvidenceSnapshot,
    FtsProjectionIntegrityError,
    FtsRankProfile,
    validate_fts_projection,
)
from mke.evaluation.graded_metrics import (
    AskObservationStatus,
    GradedQueryMetricInput,
    calculate_graded_metrics,
)
from mke.evaluation.manifest import StableLocator
from mke.retrieval.query_policy import compile_fts5_query_diagnostic

ProgressCallback = Callable[[str], None]


class ChineseEvaluationIntegrityError(RuntimeError):
    def __init__(
        self,
        problem: str,
        cause: str,
        next_step: str,
        *,
        subject_id: str | None = None,
    ) -> None:
        super().__init__(cause)
        self.problem = problem
        self.cause = cause
        self.next_step = next_step
        self.subject_id = subject_id


@dataclass(frozen=True)
class _WorkspaceResult:
    results: tuple[ChineseQueryResult, ...]
    rank_evidence: tuple[FtsRankEvidence, ...]
    traces: tuple[tuple[str, int], ...]


def run_chinese_retrieval_evaluation(
    protocol_path: Path,
    *,
    progress: ProgressCallback | None = None,
) -> ChineseRetrievalReport:
    started = time.monotonic()
    protocol: ChineseRetrievalProtocol | None = None
    try:
        protocol = load_chinese_retrieval_protocol(protocol_path)
        _progress(progress, "protocol_validated")
        with tempfile.TemporaryDirectory(
            prefix="mke-retrieval-chinese-snapshot-"
        ) as snapshot_root:
            snapshot = snapshot_chinese_retrieval_fixtures(
                protocol, Path(snapshot_root) / "fixtures"
            )
            development_queries = tuple(
                item for item in protocol.queries if item.split == "development"
            )
            holdout_queries = tuple(
                item for item in protocol.queries if item.split == "holdout"
            )
            development_documents = tuple(
                item for item in snapshot.documents if item.split == "development"
            )
            holdout_documents = tuple(
                item for item in snapshot.documents if item.split == "holdout"
            )
            development_a = _run_workspace(
                snapshot, development_documents, development_queries
            )
            _progress(progress, "development_ingested")
            development_b = _run_workspace(
                snapshot, development_documents, development_queries
            )
            _require_deterministic(
                development_a, development_b, split="development"
            )
            holdout_a = _run_workspace(
                snapshot, holdout_documents, holdout_queries
            )
            _progress(progress, "holdout_ingested")
            holdout_b = _run_workspace(
                snapshot, holdout_documents, holdout_queries
            )
            _require_deterministic(holdout_a, holdout_b, split="holdout")
            _progress(progress, "determinism_verified")

        results = (*development_a.results, *holdout_a.results)
        if tuple(item.query_id for item in results) != tuple(
            item.query_id for item in protocol.queries
        ):
            raise ChineseEvaluationIntegrityError(
                "retrieval_chinese_incomplete",
                "Chinese retrieval evaluation did not complete",
                "rerun_evaluation",
            )
        query_by_id = {item.query_id: item for item in protocol.queries}
        metrics = calculate_graded_metrics(
            tuple(
                GradedQueryMetricInput(
                    query_id=result.query_id,
                    category=result.category,
                    qrels=query_by_id[result.query_id].qrels,
                    retrieved=result.retrieved_locators,
                    ask_status=result.ask_status,
                    compiled_query_empty=result.compiled_query_empty,
                    ascii_token_count=result.ascii_token_count,
                )
                for result in results
            )
        )
        empty_development_misses = sum(
            result.split == "development"
            and result.qrel_counts[2] > 0
            and not result.direct_ranks
            and result.compiled_query_empty
            for result in results
        )
        e3b_evidence = E3BDecisionEvidence(
            development_answerable_compiled_query_empty_misses=(
                empty_development_misses
            ),
            qrel_review_status=protocol.qrel_adjudication.review_status,
            query_page_judgment_count=(
                protocol.qrel_adjudication.query_page_judgment_count
            ),
        )
        eligible = (
            protocol.qrel_adjudication.review_status == "complete"
            and empty_development_misses >= 1
        )
        return ChineseRetrievalReport(
            protocol_id=protocol.protocol_id,
            benchmark_scope="small_public_chinese_page_corpus",
            quality_gate="none",
            integrity_status="passed",
            quality_status="baseline_recorded",
            documents=len(protocol.documents),
            queries=len(protocol.queries),
            split_counts={"development": 24, "holdout": 24},
            results=tuple(results),
            metrics=metrics,
            qrel_adjudication=protocol.qrel_adjudication,
            e3b_decision="eligible" if eligible else "not_justified",
            e3b_evidence=e3b_evidence,
            e3b_reason=(
                "development_compiled_query_empty_miss_observed"
                if eligible
                else "no_development_compiled_query_empty_miss"
            ),
            fts5_rank_profile="sqlite_fts5_default_bm25",
            fts5_rank_observations=(
                *development_a.rank_evidence,
                *holdout_a.rank_evidence,
            ),
            integrity_failures=(),
            duration_ms=_elapsed_ms(started),
            limitations=CHINESE_RETRIEVAL_LIMITATIONS,
        )
    except ChineseProtocolValidationError as error:
        return _failed_report(
            protocol,
            problem=_protocol_problem(error.cause),
            cause=_protocol_cause(error.cause),
            next_step=_protocol_next_step(error.cause),
            subject_id=error.subject_id,
            started=started,
        )
    except ChineseEvaluationIntegrityError as error:
        return _failed_report(
            protocol,
            problem=error.problem,
            cause=error.cause,
            next_step=error.next_step,
            subject_id=error.subject_id,
            started=started,
        )
    except Exception:
        return _failed_report(
            protocol,
            problem="retrieval_chinese_incomplete",
            cause="Chinese retrieval evaluation did not complete",
            next_step="rerun_evaluation",
            subject_id=None,
            started=started,
        )


def _run_workspace(
    protocol: ChineseRetrievalProtocol,
    documents: tuple[ChineseEvaluationDocument, ...],
    queries: tuple[ChineseEvaluationQuery, ...],
) -> _WorkspaceResult:
    with tempfile.TemporaryDirectory(prefix="mke-retrieval-chinese-") as workspace:
        current_operation = ""
        traces: list[tuple[str, int]] = []

        def observe_search(count: int) -> None:
            traces.append((current_operation, count))

        engine = KnowledgeEngine(
            Path(workspace) / "mke.sqlite",
            query_policy="numeric-grouping-v1",
            search_observer=observe_search,
        )
        try:
            source_documents: dict[str, str] = {}
            for document in documents:
                source_id = _ingest_document(engine, protocol, document)
                if source_id in source_documents:
                    raise ChineseEvaluationIntegrityError(
                        "retrieval_chinese_ingest_failed",
                        "Chinese retrieval fixture could not be published",
                        "inspect_publication_failure",
                        subject_id=document.document_id,
                    )
                source_documents[source_id] = document.document_id
            store = engine._store  # pyright: ignore[reportPrivateUsage]
            evidence = store.list_evaluation_evidence()
            projection = store.list_fts_projection()
            try:
                validate_fts_projection(evidence, projection)
            except FtsProjectionIntegrityError as error:
                raise ChineseEvaluationIntegrityError(
                    "retrieval_chinese_evidence_invalid",
                    "active Evidence and retrieval projection are inconsistent",
                    "inspect_active_evidence_projection",
                ) from error
            stable_evidence = _stable_evidence(evidence, source_documents)
            _validate_active_evidence(
                documents=documents,
                queries=queries,
                stable_evidence=stable_evidence,
            )
            results: list[ChineseQueryResult] = []
            rank_evidence: list[FtsRankEvidence] = []
            for query in queries:
                diagnostic = compile_fts5_query_diagnostic(
                    query.text, policy="numeric-grouping-v1"
                )
                before = len(traces)
                current_operation = "direct_search"
                direct_matches = engine.search(query.text, limit=10)
                if len(traces) == before:
                    traces.append(("direct_search", 0))
                before = len(traces)
                current_operation = "ask_search"
                ask_status, ask_matches = _ask(engine, query, diagnostic.compiled_query)
                if len(traces) == before:
                    traces.append(("ask_search", 0))
                if diagnostic.compiled_query:
                    _require_search_ask_identity(
                        query.query_id, direct_matches, ask_matches
                    )
                    current_operation = "rank_probe"
                    profile = store.observe_fts5_rank(diagnostic.compiled_query)
                    traces.append(("rank_probe", 2))
                    rank_evidence.append(
                        _validate_rank_profile(
                            query,
                            profile,
                            stable_evidence,
                            direct_matches=direct_matches,
                            require_non_empty=(
                                query.query_id
                                == protocol.rank_probe_query_id
                            ),
                        )
                    )
                retrieved = tuple(
                    _stable_locator(item, source_documents)
                    for item in direct_matches
                )
                qrel_by_locator = {
                    item.locator: item.grade for item in query.qrels
                }
                direct_ranks = tuple(
                    rank
                    for rank, locator in enumerate(retrieved, start=1)
                    if qrel_by_locator.get(locator) == 2
                )
                miss = None
                if any(item.grade == 2 for item in query.qrels) and not direct_ranks:
                    miss = classify_miss(
                        diagnostic,
                        qrels=query.qrels,
                        retrieved=retrieved,
                        direct_page_text={
                            item.locator: stable_evidence[item.locator].text
                            for item in query.qrels
                            if item.grade == 2
                        },
                    )
                results.append(
                    ChineseQueryResult(
                        query_id=query.query_id,
                        split=query.split,
                        category=query.category,
                        qrel_counts=(
                            sum(item.grade == 0 for item in query.qrels),
                            sum(item.grade == 1 for item in query.qrels),
                            sum(item.grade == 2 for item in query.qrels),
                        ),
                        retrieved_locators=retrieved,
                        retrieved_grades=tuple(
                            qrel_by_locator.get(locator) for locator in retrieved
                        ),
                        direct_ranks=direct_ranks,
                        hard_negative_failure=_hard_negative_failure(
                            query, retrieved
                        ),
                        ask_status=ask_status,
                        compiled_query=diagnostic.compiled_query,
                        ascii_token_count=diagnostic.ascii_token_count,
                        compiled_query_empty=diagnostic.compiled_query_empty,
                        miss=miss,
                    )
                )
            return _WorkspaceResult(
                results=tuple(results),
                rank_evidence=tuple(rank_evidence),
                traces=tuple(traces),
            )
        except ChineseEvaluationIntegrityError:
            raise
        except Exception as error:
            raise ChineseEvaluationIntegrityError(
                "retrieval_chinese_incomplete",
                "Chinese retrieval evaluation did not complete",
                "rerun_evaluation",
            ) from error
        finally:
            engine.close()


def _ingest_document(
    engine: KnowledgeEngine,
    protocol: ChineseRetrievalProtocol,
    document: ChineseEvaluationDocument,
) -> str:
    try:
        result = engine.ingest_pdf(protocol.resolve(document.primary_file))
    except PdfIngestError as error:
        raise ChineseEvaluationIntegrityError(
            "retrieval_chinese_ingest_failed",
            "Chinese retrieval fixture could not be published",
            "inspect_publication_failure",
            subject_id=document.document_id,
        ) from error
    if result.run_state != RunState.PUBLISHED:
        raise ChineseEvaluationIntegrityError(
            "retrieval_chinese_ingest_failed",
            "Chinese retrieval fixture could not be published",
            "inspect_publication_failure",
            subject_id=document.document_id,
        )
    return engine.get_run(result.run_id).source_id


def _stable_evidence(
    evidence: tuple[EvaluationEvidenceSnapshot, ...],
    source_documents: Mapping[str, str],
) -> dict[StableLocator, EvaluationEvidenceSnapshot]:
    stable: dict[StableLocator, EvaluationEvidenceSnapshot] = {}
    for item in evidence:
        try:
            document_id = source_documents[item.source_id]
        except KeyError as error:
            raise ChineseEvaluationIntegrityError(
                "retrieval_chinese_evidence_invalid",
                "active Evidence and retrieval projection are inconsistent",
                "inspect_active_evidence_projection",
            ) from error
        if item.locator_kind != "page":
            raise ChineseEvaluationIntegrityError(
                "retrieval_chinese_evidence_invalid",
                "active Evidence and retrieval projection are inconsistent",
                "inspect_active_evidence_projection",
                subject_id=document_id,
            )
        locator = StableLocator(
            document_id=document_id,
            locator_kind="page",
            locator_start=item.locator_start,
            locator_end=item.locator_end,
        )
        if locator in stable:
            raise ChineseEvaluationIntegrityError(
                "retrieval_chinese_evidence_invalid",
                "active Evidence and retrieval projection are inconsistent",
                "inspect_active_evidence_projection",
                subject_id=document_id,
            )
        stable[locator] = item
    return stable


def _validate_active_evidence(
    *,
    documents: tuple[ChineseEvaluationDocument, ...],
    queries: tuple[ChineseEvaluationQuery, ...],
    stable_evidence: Mapping[StableLocator, EvaluationEvidenceSnapshot],
) -> None:
    expected_pages = 34 if documents[0].split == "development" else 36
    if len(stable_evidence) != expected_pages:
        raise ChineseEvaluationIntegrityError(
            "retrieval_chinese_evidence_invalid",
            "active Evidence and retrieval projection are inconsistent",
            "inspect_active_evidence_projection",
        )
    available = set(stable_evidence)
    for query in queries:
        for qrel in query.qrels:
            if qrel.locator not in available:
                raise ChineseEvaluationIntegrityError(
                    "retrieval_chinese_evidence_invalid",
                    "active Evidence and retrieval projection are inconsistent",
                    "inspect_active_evidence_projection",
                    subject_id=query.query_id,
                )


def _ask(
    engine: KnowledgeEngine,
    query: ChineseEvaluationQuery,
    compiled_query: str,
) -> tuple[AskObservationStatus, tuple[SearchResult, ...]]:
    try:
        response = engine.ask(query.text, limit=10)
    except AskValidationError as error:
        if error.problem != "invalid_question" or compiled_query:
            raise ChineseEvaluationIntegrityError(
                "retrieval_chinese_incomplete",
                "Chinese retrieval evaluation did not complete",
                "rerun_evaluation",
                subject_id=query.query_id,
            ) from error
        return "invalid_question", ()
    if response.answer_status not in {
        "evidence_found",
        "insufficient_evidence",
    }:
        raise ChineseEvaluationIntegrityError(
            "retrieval_chinese_incomplete",
            "Chinese retrieval evaluation did not complete",
            "rerun_evaluation",
            subject_id=query.query_id,
        )
    return cast(AskObservationStatus, response.answer_status), response.evidence


def _require_search_ask_identity(
    query_id: str,
    direct: list[SearchResult],
    ask: tuple[SearchResult, ...],
) -> None:
    def identity(item: SearchResult) -> tuple[object, ...]:
        return (
            item.publication_id,
            item.source_id,
            item.locator_kind,
            item.locator_start,
            item.locator_end,
        )

    if tuple(identity(item) for item in direct) != tuple(
        identity(item) for item in ask
    ):
        raise ChineseEvaluationIntegrityError(
            "retrieval_chinese_incomplete",
            "Chinese retrieval evaluation did not complete",
            "rerun_evaluation",
            subject_id=query_id,
        )


def _stable_locator(
    item: SearchResult, source_documents: Mapping[str, str]
) -> StableLocator:
    try:
        document_id = source_documents[item.source_id]
    except KeyError as error:
        raise ChineseEvaluationIntegrityError(
            "retrieval_chinese_incomplete",
            "Chinese retrieval evaluation did not complete",
            "rerun_evaluation",
        ) from error
    if item.locator_kind != "page":
        raise ChineseEvaluationIntegrityError(
            "retrieval_chinese_incomplete",
            "Chinese retrieval evaluation did not complete",
            "rerun_evaluation",
        )
    return StableLocator(
        document_id=document_id,
        locator_kind="page",
        locator_start=item.locator_start,
        locator_end=item.locator_end,
    )


def _validate_rank_profile(
    query: ChineseEvaluationQuery,
    profile: FtsRankProfile,
    stable_evidence: Mapping[StableLocator, EvaluationEvidenceSnapshot],
    *,
    direct_matches: list[SearchResult],
    require_non_empty: bool,
) -> FtsRankEvidence:
    if profile.rank_override_present or not _valid_rank_sql_trace(
        profile.sql_trace
    ):
        raise ChineseEvaluationIntegrityError(
            "retrieval_chinese_rank_invalid",
            "FTS5 rank evidence is inconsistent",
            "inspect_fts5_rank_configuration",
            subject_id=query.query_id,
        )
    rank_ids = tuple(item.evidence_id for item in profile.rank_order)
    bm25_ids = tuple(item.evidence_id for item in profile.bm25_order)
    search_ids = tuple(item.evidence_id for item in direct_matches)
    if (
        (require_non_empty and not rank_ids)
        or len(search_ids) != min(10, len(rank_ids))
        or search_ids != rank_ids[: len(search_ids)]
        or rank_ids != bm25_ids
        or any(
        not math.isfinite(item.rank_score)
        or not math.isfinite(item.bm25_score)
        or not math.isclose(
            item.rank_score, item.bm25_score, rel_tol=0.0, abs_tol=1e-12
        )
        for item in profile.rank_order
        )
    ):
        raise ChineseEvaluationIntegrityError(
            "retrieval_chinese_rank_invalid",
            "FTS5 rank evidence is inconsistent",
            "inspect_fts5_rank_configuration",
            subject_id=query.query_id,
        )
    evidence_by_id = {
        item.evidence_id: locator for locator, item in stable_evidence.items()
    }
    try:
        stable_ids = tuple(
            _stable_evidence_identity(evidence_by_id[evidence_id])
            for evidence_id in rank_ids
        )
    except KeyError as error:
        raise ChineseEvaluationIntegrityError(
            "retrieval_chinese_rank_invalid",
            "FTS5 rank evidence is inconsistent",
            "inspect_fts5_rank_configuration",
            subject_id=query.query_id,
        ) from error
    score_pairs = tuple(
        (
            stable_id,
            observation.rank_score.hex(),
            observation.bm25_score.hex(),
        )
        for stable_id, observation in zip(
            stable_ids, profile.rank_order, strict=True
        )
    )
    return FtsRankEvidence(
        query_id=query.query_id,
        split=query.split,
        result_count=len(profile.rank_order),
        ordered_evidence_ids_sha256=_digest(stable_ids),
        score_pairs_sha256=_digest(score_pairs),
        rank_override_present=False,
        ordered_evidence=tuple(
            evidence_by_id[evidence_id] for evidence_id in rank_ids
        ),
        score_pairs=tuple(
            FtsRankScoreEvidence(
                locator=evidence_by_id[observation.evidence_id],
                rank_score_hex=observation.rank_score.hex(),
                bm25_score_hex=observation.bm25_score.hex(),
            )
            for observation in profile.rank_order
        ),
    )


def _valid_rank_sql_trace(statements: tuple[str, ...]) -> bool:
    match_statements = tuple(
        " ".join(statement.split())
        for statement in statements
        if "active_evidence_fts MATCH" in statement
    )
    if len(match_statements) != 2:
        return False
    lowered = tuple(statement.casefold() for statement in match_statements)
    common = (
        "join evidence on evidence.evidence_id = active_evidence_fts.evidence_id",
        "join sources on sources.source_id = evidence.source_id",
        "sources.active_publication_id = active_evidence_fts.publication_id",
    )
    if any(" limit " in statement for statement in lowered) or any(
        requirement not in statement
        for statement in lowered
        for requirement in common
    ):
        return False
    return (
        any(
            "rank as score" in statement
            and (
                "order by rank, evidence.locator_start, "
                "evidence.evidence_id"
            )
            in statement
            for statement in lowered
        )
        and any(
            "bm25(active_evidence_fts) as score" in statement
            and (
                "order by bm25(active_evidence_fts), "
                "evidence.locator_start, evidence.evidence_id"
            )
            in statement
            for statement in lowered
        )
    )


def _stable_evidence_identity(locator: StableLocator) -> str:
    return (
        f"{locator.document_id}|{locator.locator_kind}|"
        f"{locator.locator_start}|{locator.locator_end}"
    )


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    ).hexdigest()


def _hard_negative_failure(
    query: ChineseEvaluationQuery, retrieved: tuple[StableLocator, ...]
) -> bool:
    direct = {item.locator for item in query.qrels if item.grade == 2}
    distractors = {item.locator for item in query.qrels if item.grade == 0}
    direct_ranks = tuple(
        rank
        for rank, locator in enumerate(retrieved, start=1)
        if locator in direct
    )
    distractor_ranks = tuple(
        rank
        for rank, locator in enumerate(retrieved, start=1)
        if locator in distractors
    )
    return bool(
        distractor_ranks
        and (
            not direct_ranks
            or min(distractor_ranks) < min(direct_ranks)
        )
    )


def _require_deterministic(
    first: _WorkspaceResult,
    second: _WorkspaceResult,
    *,
    split: str,
) -> None:
    if first != second:
        raise ChineseEvaluationIntegrityError(
            "retrieval_chinese_incomplete",
            "Chinese retrieval evaluation did not complete",
            "rerun_evaluation",
            subject_id=split,
        )


def _failed_report(
    protocol: ChineseRetrievalProtocol | None,
    *,
    problem: str,
    cause: str,
    next_step: str,
    subject_id: str | None,
    started: float,
) -> ChineseRetrievalReport:
    adjudication = (
        protocol.qrel_adjudication
        if protocol is not None
        else QrelAdjudication(
            path=Path("."),
            sha256="0" * 64,
            review_status="complete",
            reviewed_query_count=0,
            query_page_judgment_count=0,
        )
    )
    return ChineseRetrievalReport(
        protocol_id=protocol.protocol_id if protocol is not None else "unknown",
        benchmark_scope="small_public_chinese_page_corpus",
        quality_gate="none",
        integrity_status="failed",
        quality_status="not_recorded",
        documents=len(protocol.documents) if protocol is not None else 0,
        queries=len(protocol.queries) if protocol is not None else 0,
        split_counts={
            "development": (
                sum(item.split == "development" for item in protocol.queries)
                if protocol is not None
                else 0
            ),
            "holdout": (
                sum(item.split == "holdout" for item in protocol.queries)
                if protocol is not None
                else 0
            ),
        },
        results=(),
        metrics=None,
        qrel_adjudication=adjudication,
        e3b_decision="not_justified",
        e3b_evidence=E3BDecisionEvidence(
            development_answerable_compiled_query_empty_misses=0,
            qrel_review_status="complete",
            query_page_judgment_count=adjudication.query_page_judgment_count,
        ),
        e3b_reason="evaluation_integrity_failed",
        fts5_rank_profile=None,
        fts5_rank_observations=(),
        integrity_failures=(
            IntegrityFailure(
                problem=problem,
                cause=cause,
                next_step=next_step,
                subject_id=subject_id,
            ),
        ),
        duration_ms=_elapsed_ms(started),
        limitations=CHINESE_RETRIEVAL_LIMITATIONS,
    )


def _protocol_problem(cause: str) -> str:
    if "qrel" in cause or "adjudication" in cause or "decision basis" in cause:
        return "retrieval_chinese_qrels_invalid"
    if "fixture" in cause or "PDF" in cause:
        return "retrieval_chinese_fixture_invalid"
    return "retrieval_chinese_protocol_invalid"


def _protocol_cause(cause: str) -> str:
    problem = _protocol_problem(cause)
    return {
        "retrieval_chinese_qrels_invalid": (
            "Chinese retrieval qrel review is invalid"
        ),
        "retrieval_chinese_fixture_invalid": (
            "Chinese retrieval fixture identity is invalid"
        ),
        "retrieval_chinese_protocol_invalid": (
            "Chinese retrieval protocol is invalid"
        ),
    }[problem]


def _protocol_next_step(cause: str) -> str:
    problem = _protocol_problem(cause)
    return {
        "retrieval_chinese_qrels_invalid": "restore_checked_in_qrel_review",
        "retrieval_chinese_fixture_invalid": "verify_fixture_identity",
        "retrieval_chinese_protocol_invalid": "restore_checked_in_protocol",
    }[problem]


def _progress(callback: ProgressCallback | None, phase: str) -> None:
    if callback is not None:
        callback(phase)


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))
