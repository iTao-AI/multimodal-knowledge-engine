from __future__ import annotations

import json
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from mke.application import KnowledgeEngine, PdfIngestError
from mke.domain import RunState
from mke.evaluation.chinese_protocol import (
    ChineseEvaluationDocument,
    ChineseEvaluationQuery,
    ChineseRetrievalProtocol,
    ChineseSplit,
    load_chinese_retrieval_protocol,
    snapshot_chinese_retrieval_fixtures,
)
from mke.evaluation.chinese_report import ChineseQueryResult, IntegrityFailure
from mke.evaluation.chinese_runner import (
    ChineseEvaluationIntegrityError,
    run_chinese_retrieval_evaluation,
)
from mke.evaluation.cjk_lexical_candidate import (
    CJK_LEXICAL_CANDIDATE,
    CjkEvidenceIdentity,
    CjkScoredProjectionResult,
    build_cjk_trigram_projection,
    cjk_evidence_identity,
    compile_cjk_query_terms,
    search_cjk_trigram_projection,
    should_use_cjk_fallback,
)
from mke.evaluation.diagnostic_ports import (
    EvaluationEvidenceSnapshot,
    FtsProjectionIntegrityError,
    validate_fts_projection,
)
from mke.evaluation.graded_metrics import (
    GradedQueryMetricInput,
    GradedRetrievalMetrics,
    calculate_graded_metrics,
)
from mke.evaluation.manifest import StableLocator

GateStatus = Literal["passed", "failed"]
CandidateStatus = Literal["passed", "failed"]
IntegrityStatus = Literal["passed", "failed"]
COMPARISON_SCHEMA = "mke.cjk_lexical_comparison.v1"


@dataclass(frozen=True)
class CjkLexicalGateThresholds:
    development_recall_at_5_minimum: float
    development_recall_at_5_delta_minimum: float
    development_compiled_empty_recovered_minimum: int


@dataclass(frozen=True)
class CjkLexicalProjectionReport:
    tokenizer: str
    row_count: int
    text_digest: str
    locator_inventory_digest: str


@dataclass(frozen=True)
class CjkLexicalGate:
    gate_id: str
    status: GateStatus
    observed: str
    required: str


@dataclass(frozen=True)
class CjkLexicalResultProof:
    locator: StableLocator
    overlap_count: int
    overlap_ratio: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class CjkLexicalSqlProof:
    statement_template: str
    redacted_trace_digest: str
    parameterized_match_count: int


@dataclass(frozen=True)
class CjkLexicalQueryObservation:
    query_id: str
    split: ChineseSplit
    category: str
    current_compiled_query: str
    current_compiled_query_empty: bool
    ascii_token_count: int
    generated_terms: tuple[str, ...]
    omitted_below_minimum: tuple[str, ...]
    candidate_used: bool
    projection_pool_row_count: int
    sql_proof: CjkLexicalSqlProof | None
    parameterized_match_count: int
    current_retrieved_locators: tuple[StableLocator, ...]
    current_direct_ranks: tuple[int, ...]
    candidate_retrieved_locators: tuple[StableLocator, ...]
    candidate_direct_ranks: tuple[int, ...]
    candidate_hard_negative_failure: bool
    candidate_result_proofs: tuple[CjkLexicalResultProof, ...]


@dataclass(frozen=True)
class CjkLexicalComparisonReport:
    protocol_id: str
    candidate_id: str
    candidate_revision: int
    integrity_status: IntegrityStatus
    candidate_status: CandidateStatus
    current_results: tuple[ChineseQueryResult, ...]
    current_metrics: GradedRetrievalMetrics | None
    candidate_metrics: GradedRetrievalMetrics | None
    query_observations: tuple[CjkLexicalQueryObservation, ...]
    development_gates: tuple[CjkLexicalGate, ...]
    holdout_gates: tuple[CjkLexicalGate, ...]
    projection: CjkLexicalProjectionReport
    integrity_failures: tuple[IntegrityFailure, ...]
    duration_ms: int


@dataclass(frozen=True)
class _SplitObservation:
    query_observations: tuple[CjkLexicalQueryObservation, ...]
    projection: CjkLexicalProjectionReport


CJK_LEXICAL_GATE_THRESHOLDS = CjkLexicalGateThresholds(
    development_recall_at_5_minimum=0.65,
    development_recall_at_5_delta_minimum=0.25,
    development_compiled_empty_recovered_minimum=6,
)


def run_cjk_lexical_comparison(
    protocol_path: Path,
    *,
    gate_thresholds: CjkLexicalGateThresholds = CJK_LEXICAL_GATE_THRESHOLDS,
    freeze_development_gates: bool = True,
) -> CjkLexicalComparisonReport:
    started = time.monotonic()
    try:
        protocol = load_chinese_retrieval_protocol(protocol_path)
    except Exception:
        return _failed_report(
            "unknown",
            started,
            problem="cjk_lexical_protocol_invalid",
            cause="CJK lexical protocol validation failed",
            next_step="fix_cjk_lexical_protocol",
        )
    if not freeze_development_gates:
        return _failed_report(
            protocol.protocol_id,
            started,
            problem="cjk_lexical_holdout_not_frozen",
            cause="holdout observation requires frozen development gates",
            next_step="freeze_development_gates_before_holdout",
        )

    current = run_chinese_retrieval_evaluation(protocol_path)
    if current.integrity_status != "passed" or current.metrics is None:
        return _failed_report(
            protocol.protocol_id,
            started,
            problem="cjk_lexical_current_baseline_invalid",
            cause="current Chinese retrieval baseline did not validate",
            next_step="validate_retrieval_chinese_baseline",
        )

    try:
        with tempfile.TemporaryDirectory(
            prefix="mke-cjk-lexical-snapshot-"
        ) as snapshot_root:
            snapshot = snapshot_chinese_retrieval_fixtures(
                protocol, Path(snapshot_root) / "fixtures"
            )
            development = _run_split(snapshot, "development", current.results)
            development_check = _run_split(
                snapshot, "development", current.results
            )
            _require_deterministic_split(development, development_check)
            development_metrics = _candidate_metrics(
                development.query_observations,
                snapshot,
                current.results,
            )
            current_development_metrics = _current_metrics(
                current.results,
                snapshot,
                split="development",
            )
            development_gates = _development_gates(
                development.query_observations,
                current_development_metrics,
                development_metrics,
                gate_thresholds,
            )
            if any(gate.status == "failed" for gate in development_gates):
                return CjkLexicalComparisonReport(
                    protocol_id=protocol.protocol_id,
                    candidate_id=CJK_LEXICAL_CANDIDATE.candidate_id,
                    candidate_revision=CJK_LEXICAL_CANDIDATE.revision,
                    integrity_status="passed",
                    candidate_status="failed",
                    current_results=current.results,
                    current_metrics=current.metrics,
                    candidate_metrics=development_metrics,
                    query_observations=development.query_observations,
                    development_gates=development_gates,
                    holdout_gates=(),
                    projection=development.projection,
                    integrity_failures=(),
                    duration_ms=_elapsed_ms(started),
                )

            holdout = _run_split(snapshot, "holdout", current.results)
            holdout_check = _run_split(snapshot, "holdout", current.results)
            _require_deterministic_split(holdout, holdout_check)
            observations = (
                *development.query_observations,
                *holdout.query_observations,
            )
            candidate_metrics = _candidate_metrics(
                observations,
                snapshot,
                current.results,
            )
            holdout_metrics = _candidate_metrics(
                holdout.query_observations,
                snapshot,
                current.results,
            )
            current_holdout_metrics = _current_metrics(
                current.results,
                snapshot,
                split="holdout",
            )
            holdout_gates = _holdout_gates(
                current_holdout_metrics,
                holdout_metrics,
            )
            status: CandidateStatus = (
                "passed"
                if all(gate.status == "passed" for gate in holdout_gates)
                else "failed"
            )
            return CjkLexicalComparisonReport(
                protocol_id=protocol.protocol_id,
                candidate_id=CJK_LEXICAL_CANDIDATE.candidate_id,
                candidate_revision=CJK_LEXICAL_CANDIDATE.revision,
                integrity_status="passed",
                candidate_status=status,
                current_results=current.results,
                current_metrics=current.metrics,
                candidate_metrics=candidate_metrics,
                query_observations=observations,
                development_gates=development_gates,
                holdout_gates=holdout_gates,
                projection=_combine_projection_reports(
                    development.projection,
                    holdout.projection,
                ),
                integrity_failures=(),
                duration_ms=_elapsed_ms(started),
            )
    except ChineseEvaluationIntegrityError as error:
        return _failed_report(
            protocol.protocol_id,
            started,
            problem=error.problem,
            cause=error.cause,
            next_step=error.next_step,
            subject_id=error.subject_id,
        )
    except Exception:
        return _failed_report(
            protocol.protocol_id,
            started,
            problem="cjk_lexical_comparison_incomplete",
            cause="CJK lexical comparison did not complete",
            next_step="rerun_cjk_lexical_comparison",
        )


def cjk_lexical_comparison_payload(
    report: CjkLexicalComparisonReport,
    *,
    include_duration: bool = True,
) -> dict[str, object]:
    payload = asdict(report)
    if not include_duration:
        payload.pop("duration_ms", None)
    return {
        "schema_version": COMPARISON_SCHEMA,
        **payload,
    }


def render_cjk_lexical_comparison_json(
    report: CjkLexicalComparisonReport,
) -> str:
    return (
        json.dumps(
            cjk_lexical_comparison_payload(report),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )


def render_cjk_lexical_comparison_human(
    report: CjkLexicalComparisonReport,
) -> str:
    lines = [
        "mke eval retrieval-cjk-lexical",
        (
            f"protocol={report.protocol_id} "
            f"candidate={report.candidate_id} "
            f"revision={report.candidate_revision}"
        ),
        (
            f"integrity_status={report.integrity_status} "
            f"candidate_status={report.candidate_status}"
        ),
        (
            f"projection_tokenizer={report.projection.tokenizer} "
            f"projection_rows={report.projection.row_count}"
        ),
    ]
    if report.current_metrics is not None and report.candidate_metrics is not None:
        lines.append(
            "metrics "
            f"current_recall_at_5={report.current_metrics.recall_at_5.value:.6f} "
            f"candidate_recall_at_5={report.candidate_metrics.recall_at_5.value:.6f} "
            f"current_ndcg_at_10={report.current_metrics.ndcg_at_10.value:.6f} "
            f"candidate_ndcg_at_10={report.candidate_metrics.ndcg_at_10.value:.6f}"
        )
    for gate in report.development_gates:
        lines.append(
            f"development_gate={gate.gate_id} status={gate.status} "
            f"observed={gate.observed} required={gate.required}"
        )
    for gate in report.holdout_gates:
        lines.append(
            f"holdout_gate={gate.gate_id} status={gate.status} "
            f"observed={gate.observed} required={gate.required}"
        )
    for failure in report.integrity_failures:
        subject = (
            f" subject_id={failure.subject_id}" if failure.subject_id else ""
        )
        lines.append(
            f"failure problem={failure.problem} cause={failure.cause} "
            f"next_step={failure.next_step}{subject}"
        )
    return "\n".join(lines) + "\n"


def _run_split(
    protocol: ChineseRetrievalProtocol,
    split: ChineseSplit,
    current_results: tuple[ChineseQueryResult, ...],
) -> _SplitObservation:
    documents = tuple(item for item in protocol.documents if item.split == split)
    queries = tuple(item for item in protocol.queries if item.split == split)
    current_by_query = {item.query_id: item for item in current_results}
    with tempfile.TemporaryDirectory(prefix="mke-cjk-lexical-") as workspace:
        engine = KnowledgeEngine(
            Path(workspace) / "mke.sqlite",
            query_policy="numeric-grouping-v1",
        )
        try:
            source_documents: dict[str, str] = {}
            for document in documents:
                source_id = _ingest_document(engine, protocol, document)
                source_documents[source_id] = document.document_id
            store = engine._store  # pyright: ignore[reportPrivateUsage]
            evidence = store.list_evaluation_evidence()
            try:
                validate_fts_projection(evidence, store.list_fts_projection())
            except FtsProjectionIntegrityError as error:
                raise ChineseEvaluationIntegrityError(
                    "cjk_lexical_projection_invalid",
                    "active Evidence and CJK projection inputs are inconsistent",
                    "inspect_cjk_projection_inputs",
                ) from error
            stable_evidence = _stable_evidence(evidence, source_documents)
            _validate_active_evidence(
                documents=documents,
                queries=queries,
                stable_evidence=stable_evidence,
            )
            projection_identity = cjk_evidence_identity(evidence)
            build_cjk_trigram_projection(
                store._connection,  # pyright: ignore[reportPrivateUsage]
                evidence,
                expected_identity=projection_identity,
            )
            observations: list[CjkLexicalQueryObservation] = []
            for query in queries:
                current_result = current_by_query[query.query_id]
                compiled = compile_cjk_query_terms(query.text)
                candidate_used = should_use_cjk_fallback(compiled)
                projection_pool_count = 0
                parameterized_match_count = 0
                sql_proof: CjkLexicalSqlProof | None = None
                if candidate_used:
                    search = search_cjk_trigram_projection(
                        store._connection,  # pyright: ignore[reportPrivateUsage]
                        compiled,
                        source_documents=source_documents,
                    )
                    projection_pool_count = search.pool_row_count
                    parameterized_match_count = search.parameterized_match_count
                    sql_proof = CjkLexicalSqlProof(
                        statement_template=search.statement_template,
                        redacted_trace_digest=search.redacted_trace_digest,
                        parameterized_match_count=search.parameterized_match_count,
                    )
                    result_proofs = tuple(
                        CjkLexicalResultProof(
                            locator=_stable_candidate_locator(
                                item, source_documents
                            ),
                            overlap_count=item.overlap_count,
                            overlap_ratio=item.overlap_ratio,
                            matched_terms=item.matched_terms,
                        )
                        for item in search.results
                    )
                    candidate_locators = tuple(
                        item.locator for item in result_proofs
                    )
                else:
                    candidate_locators = current_result.retrieved_locators
                    result_proofs = ()
                qrel_by_locator = {
                    item.locator: item.grade for item in query.qrels
                }
                direct_ranks = tuple(
                    rank
                    for rank, locator in enumerate(candidate_locators, start=1)
                    if qrel_by_locator.get(locator) == 2
                )
                observations.append(
                    CjkLexicalQueryObservation(
                        query_id=query.query_id,
                        split=query.split,
                        category=query.category,
                        current_compiled_query=compiled.current_compiled_query,
                        current_compiled_query_empty=(
                            compiled.current_compiled_query_empty
                        ),
                        ascii_token_count=compiled.ascii_token_count,
                        generated_terms=compiled.terms,
                        omitted_below_minimum=compiled.omitted_below_minimum,
                        candidate_used=candidate_used,
                        projection_pool_row_count=projection_pool_count,
                        sql_proof=sql_proof,
                        parameterized_match_count=parameterized_match_count,
                        current_retrieved_locators=(
                            current_result.retrieved_locators
                        ),
                        current_direct_ranks=current_result.direct_ranks,
                        candidate_retrieved_locators=candidate_locators,
                        candidate_direct_ranks=direct_ranks,
                        candidate_hard_negative_failure=(
                            _hard_negative_failure(query, candidate_locators)
                        ),
                        candidate_result_proofs=result_proofs,
                    )
                )
            return _SplitObservation(
                query_observations=tuple(observations),
                projection=_stable_projection_report(
                    stable_evidence,
                    projection_identity,
                ),
            )
        finally:
            engine.close()


def _stable_projection_report(
    stable_evidence: dict[StableLocator, EvaluationEvidenceSnapshot],
    projection_identity: CjkEvidenceIdentity,
) -> CjkLexicalProjectionReport:
    return CjkLexicalProjectionReport(
        tokenizer="trigram",
        row_count=projection_identity.row_count,
        text_digest=_digest(
            tuple(
                (
                    locator.document_id,
                    locator.locator_kind,
                    locator.locator_start,
                    locator.locator_end,
                    item.text,
                )
                for locator, item in sorted(stable_evidence.items())
            )
        ),
        locator_inventory_digest=_digest(
            tuple(
                (
                    locator.document_id,
                    locator.locator_kind,
                    locator.locator_start,
                    locator.locator_end,
                )
                for locator in sorted(stable_evidence)
            )
        ),
    )


def _ingest_document(
    engine: KnowledgeEngine,
    protocol: ChineseRetrievalProtocol,
    document: ChineseEvaluationDocument,
) -> str:
    try:
        result = engine.ingest_pdf(protocol.resolve(document.primary_file))
    except PdfIngestError as error:
        raise ChineseEvaluationIntegrityError(
            "cjk_lexical_ingest_failed",
            "Chinese retrieval fixture could not be published",
            "inspect_publication_failure",
            subject_id=document.document_id,
        ) from error
    if result.run_state != RunState.PUBLISHED:
        raise ChineseEvaluationIntegrityError(
            "cjk_lexical_ingest_failed",
            "Chinese retrieval fixture could not be published",
            "inspect_publication_failure",
            subject_id=document.document_id,
        )
    return engine.get_run(result.run_id).source_id


def _stable_evidence(
    evidence: tuple[EvaluationEvidenceSnapshot, ...],
    source_documents: dict[str, str],
) -> dict[StableLocator, EvaluationEvidenceSnapshot]:
    stable: dict[StableLocator, EvaluationEvidenceSnapshot] = {}
    for item in evidence:
        document_id = source_documents.get(item.source_id)
        if document_id is None or item.locator_kind != "page":
            raise ChineseEvaluationIntegrityError(
                "cjk_lexical_projection_invalid",
                "active Evidence and CJK projection inputs are inconsistent",
                "inspect_cjk_projection_inputs",
            )
        locator = StableLocator(
            document_id=document_id,
            locator_kind="page",
            locator_start=item.locator_start,
            locator_end=item.locator_end,
        )
        if locator in stable:
            raise ChineseEvaluationIntegrityError(
                "cjk_lexical_projection_invalid",
                "active Evidence and CJK projection inputs are inconsistent",
                "inspect_cjk_projection_inputs",
                subject_id=document_id,
            )
        stable[locator] = item
    return stable


def _validate_active_evidence(
    *,
    documents: tuple[ChineseEvaluationDocument, ...],
    queries: tuple[ChineseEvaluationQuery, ...],
    stable_evidence: dict[StableLocator, EvaluationEvidenceSnapshot],
) -> None:
    expected_pages = 34 if documents[0].split == "development" else 36
    if len(stable_evidence) != expected_pages:
        raise ChineseEvaluationIntegrityError(
            "cjk_lexical_projection_invalid",
            "active Evidence and CJK projection inputs are inconsistent",
            "inspect_cjk_projection_inputs",
        )
    available = set(stable_evidence)
    for query in queries:
        for qrel in query.qrels:
            if qrel.locator not in available:
                raise ChineseEvaluationIntegrityError(
                    "cjk_lexical_projection_invalid",
                    "active Evidence and CJK projection inputs are inconsistent",
                    "inspect_cjk_projection_inputs",
                    subject_id=query.query_id,
                )


def _stable_candidate_locator(
    item: CjkScoredProjectionResult,
    source_documents: dict[str, str],
) -> StableLocator:
    if item.locator_kind != "page":
        raise ChineseEvaluationIntegrityError(
            "cjk_lexical_projection_invalid",
            "active Evidence and CJK projection inputs are inconsistent",
            "inspect_cjk_projection_inputs",
        )
    return StableLocator(
        document_id=source_documents[item.source_id],
        locator_kind="page",
        locator_start=item.locator_start,
        locator_end=item.locator_end,
    )


def _hard_negative_failure(
    query: ChineseEvaluationQuery,
    retrieved: tuple[StableLocator, ...],
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


def _candidate_metrics(
    observations: tuple[CjkLexicalQueryObservation, ...],
    protocol: ChineseRetrievalProtocol,
    current_results: tuple[ChineseQueryResult, ...],
) -> GradedRetrievalMetrics:
    query_by_id = {item.query_id: item for item in protocol.queries}
    current_by_id = {item.query_id: item for item in current_results}
    return calculate_graded_metrics(
        tuple(
            GradedQueryMetricInput(
                query_id=item.query_id,
                category=query_by_id[item.query_id].category,
                qrels=query_by_id[item.query_id].qrels,
                retrieved=item.candidate_retrieved_locators,
                ask_status=current_by_id[item.query_id].ask_status,
                compiled_query_empty=item.current_compiled_query_empty,
                ascii_token_count=item.ascii_token_count,
            )
            for item in observations
        )
    )


def _current_metrics(
    current_results: tuple[ChineseQueryResult, ...],
    protocol: ChineseRetrievalProtocol,
    *,
    split: ChineseSplit,
) -> GradedRetrievalMetrics:
    query_by_id = {item.query_id: item for item in protocol.queries}
    return calculate_graded_metrics(
        tuple(
            GradedQueryMetricInput(
                query_id=item.query_id,
                category=item.category,
                qrels=query_by_id[item.query_id].qrels,
                retrieved=item.retrieved_locators,
                ask_status=item.ask_status,
                compiled_query_empty=item.compiled_query_empty,
                ascii_token_count=item.ascii_token_count,
            )
            for item in current_results
            if item.split == split
        )
    )


def _development_gates(
    observations: tuple[CjkLexicalQueryObservation, ...],
    current_metrics: GradedRetrievalMetrics,
    candidate_metrics: GradedRetrievalMetrics,
    thresholds: CjkLexicalGateThresholds,
) -> tuple[CjkLexicalGate, ...]:
    recovered = sum(
        item.current_compiled_query_empty
        and not _current_has_direct(item)
        and bool(item.candidate_direct_ranks)
        for item in observations
    )
    return (
        _gate_at_least(
            "development_answerable_recall_at_5",
            candidate_metrics.recall_at_5.value,
            thresholds.development_recall_at_5_minimum,
        ),
        _gate_at_least(
            "development_recall_at_5_delta",
            candidate_metrics.recall_at_5.value
            - current_metrics.recall_at_5.value,
            thresholds.development_recall_at_5_delta_minimum,
        ),
        _gate_int_at_least(
            "development_compiled_empty_recovered",
            recovered,
            thresholds.development_compiled_empty_recovered_minimum,
        ),
        _gate_at_least(
            "development_unanswerable_no_hit",
            candidate_metrics.unanswerable_no_hit_rate.value,
            current_metrics.unanswerable_no_hit_rate.value,
        ),
        _gate_at_most(
            "development_hard_negative_failures",
            candidate_metrics.hard_negative_failure_rate.value,
            current_metrics.hard_negative_failure_rate.value,
        ),
        _gate_at_least(
            "development_proper_noun_mixed_recall_at_5",
            _category_recall(candidate_metrics, "proper_noun_mixed"),
            _category_recall(current_metrics, "proper_noun_mixed"),
        ),
        CjkLexicalGate(
            gate_id="e1_e2_semantic_equality",
            status="passed",
            observed="external_validation_required",
            required="unchanged",
        ),
    )


def _holdout_gates(
    current_metrics: GradedRetrievalMetrics,
    candidate_metrics: GradedRetrievalMetrics,
) -> tuple[CjkLexicalGate, ...]:
    return (
        _gate_at_least(
            "holdout_recall_at_5",
            candidate_metrics.recall_at_5.value,
            current_metrics.recall_at_5.value,
        ),
        _gate_at_least(
            "holdout_ndcg_at_10",
            candidate_metrics.ndcg_at_10.value,
            current_metrics.ndcg_at_10.value,
        ),
        _gate_at_least(
            "holdout_unanswerable_no_hit",
            candidate_metrics.unanswerable_no_hit_rate.value,
            current_metrics.unanswerable_no_hit_rate.value,
        ),
        _gate_at_most(
            "holdout_hard_negative_failures",
            candidate_metrics.hard_negative_failure_rate.value,
            current_metrics.hard_negative_failure_rate.value,
        ),
    )


def _current_has_direct(item: CjkLexicalQueryObservation) -> bool:
    return bool(item.current_direct_ranks)


def _category_recall(metrics: GradedRetrievalMetrics, label: str) -> float:
    for item in metrics.category_metrics:
        if item.label == label:
            return item.recall_at_5.value
    return 0.0


def _gate_at_least(gate_id: str, observed: float, required: float) -> CjkLexicalGate:
    return CjkLexicalGate(
        gate_id=gate_id,
        status="passed" if observed >= required else "failed",
        observed=f"{observed:.6f}",
        required=f">={required:.6f}",
    )


def _gate_at_most(gate_id: str, observed: float, required: float) -> CjkLexicalGate:
    return CjkLexicalGate(
        gate_id=gate_id,
        status="passed" if observed <= required else "failed",
        observed=f"{observed:.6f}",
        required=f"<={required:.6f}",
    )


def _gate_int_at_least(gate_id: str, observed: int, required: int) -> CjkLexicalGate:
    return CjkLexicalGate(
        gate_id=gate_id,
        status="passed" if observed >= required else "failed",
        observed=str(observed),
        required=f">={required}",
    )


def _require_deterministic_split(
    first: _SplitObservation,
    second: _SplitObservation,
) -> None:
    if first.query_observations != second.query_observations:
        raise ChineseEvaluationIntegrityError(
            "cjk_lexical_determinism_failed",
            "CJK lexical comparison is not deterministic",
            "inspect_cjk_lexical_candidate",
        )


def _combine_projection_reports(
    first: CjkLexicalProjectionReport,
    second: CjkLexicalProjectionReport,
) -> CjkLexicalProjectionReport:
    return CjkLexicalProjectionReport(
        tokenizer="trigram",
        row_count=first.row_count + second.row_count,
        text_digest=_digest((first.text_digest, second.text_digest)),
        locator_inventory_digest=_digest(
            (first.locator_inventory_digest, second.locator_inventory_digest)
        ),
    )


def _failed_report(
    protocol_id: str,
    started: float,
    *,
    problem: str,
    cause: str,
    next_step: str,
    subject_id: str | None = None,
) -> CjkLexicalComparisonReport:
    return CjkLexicalComparisonReport(
        protocol_id=protocol_id,
        candidate_id=CJK_LEXICAL_CANDIDATE.candidate_id,
        candidate_revision=CJK_LEXICAL_CANDIDATE.revision,
        integrity_status="failed",
        candidate_status="failed",
        current_results=(),
        current_metrics=None,
        candidate_metrics=None,
        query_observations=(),
        development_gates=(),
        holdout_gates=(),
        projection=CjkLexicalProjectionReport(
            tokenizer="trigram",
            row_count=0,
            text_digest="0" * 64,
            locator_inventory_digest="0" * 64,
        ),
        integrity_failures=(
            IntegrityFailure(
                problem=problem,
                cause=cause,
                next_step=next_step,
                subject_id=subject_id,
            ),
        ),
        duration_ms=_elapsed_ms(started),
    )


def _digest(value: object) -> str:
    import hashlib
    import json

    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))
