from __future__ import annotations

import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from mke.application import KnowledgeEngine
from mke.domain import ActiveEvidenceRef, RunState, SearchResult
from mke.evaluation.manifest import (
    EvaluationDocument,
    EvaluationQuery,
    FixtureValidationError,
    LocatorKind,
    ManifestValidationError,
    RetrievalEvaluationManifest,
    StableLocator,
    load_retrieval_manifest,
    snapshot_retrieval_fixtures,
)
from mke.evaluation.metrics import (
    AskStatus,
    QueryMetricInput,
    RetrievalMetrics,
    calculate_metrics,
)
from mke.evaluation.report import (
    IntegrityFailure,
    QueryEvaluationResult,
    RetrievalEvaluationReport,
)
from mke.retrieval import RetrievalQueryPolicy
from mke.retrieval.query_policy import require_retrieval_query_policy


class EvaluationIntegrityError(RuntimeError):
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
    results: tuple[QueryEvaluationResult, ...]
    metrics: RetrievalMetrics


def run_retrieval_evaluation(manifest_path: Path) -> RetrievalEvaluationReport:
    return _run_retrieval_evaluation(manifest_path, query_policy="current")


def _run_retrieval_evaluation(
    manifest_path: Path,
    *,
    query_policy: RetrievalQueryPolicy,
) -> RetrievalEvaluationReport:
    started = time.monotonic()
    manifest_id = "unknown"
    document_count = 0
    try:
        validated_policy = require_retrieval_query_policy(query_policy)
    except ValueError:
        return _failed_report(
            manifest_id=manifest_id,
            document_count=document_count,
            problem="retrieval_eval_incomplete",
            cause="retrieval query policy is unsupported",
            next_step="inspect_retrieval_eval_inputs",
            subject_id=None,
            started=started,
        )
    try:
        manifest = load_retrieval_manifest(manifest_path)
        manifest_id = manifest.manifest_id
        document_count = len(manifest.documents)
        with tempfile.TemporaryDirectory(
            prefix="mke-retrieval-eval-snapshot-"
        ) as snapshot_root:
            staged = snapshot_retrieval_fixtures(
                manifest, Path(snapshot_root) / "fixtures"
            )
            first = _run_workspace(staged, query_policy=validated_policy)
            second = _run_workspace(staged, query_policy=validated_policy)
            _require_deterministic(first, second)
            return RetrievalEvaluationReport(
                manifest_id=manifest.manifest_id,
                benchmark_scope="small_english_page_timestamp_corpus",
                quality_gate="none",
                status="passed",
                quality_status="baseline_recorded",
                document_count=len(manifest.documents),
                results=first.results,
                metrics=first.metrics,
                integrity_failures=(),
                duration_ms=_elapsed_ms(started),
            )
    except FixtureValidationError as error:
        return _failed_report(
            manifest_id=manifest_id,
            document_count=document_count,
            problem="retrieval_eval_fixture_invalid",
            cause=error.cause,
            next_step="restore_retrieval_eval_fixture",
            subject_id=error.subject_id,
            started=started,
        )
    except ManifestValidationError as error:
        return _failed_report(
            manifest_id=manifest_id,
            document_count=document_count,
            problem="retrieval_eval_manifest_invalid",
            cause=error.cause,
            next_step="fix_retrieval_eval_manifest",
            subject_id=error.subject_id,
            started=started,
        )
    except EvaluationIntegrityError as error:
        return _failed_report(
            manifest_id=manifest_id,
            document_count=document_count,
            problem=error.problem,
            cause=error.cause,
            next_step=error.next_step,
            subject_id=error.subject_id,
            started=started,
        )
    except Exception:
        return _failed_report(
            manifest_id=manifest_id,
            document_count=document_count,
            problem="retrieval_eval_incomplete",
            cause="retrieval evaluation failed",
            next_step="inspect_retrieval_eval_inputs",
            subject_id=None,
            started=started,
        )


def _run_workspace(
    manifest: RetrievalEvaluationManifest,
    *,
    query_policy: RetrievalQueryPolicy,
) -> _WorkspaceResult:
    with tempfile.TemporaryDirectory(prefix="mke-retrieval-eval-") as workspace:
        engine = KnowledgeEngine(
            Path(workspace) / "mke.sqlite",
            query_policy=query_policy,
        )
        try:
            source_documents: dict[str, str] = {}
            for document in manifest.documents:
                source_id = _ingest_document(engine, manifest, document)
                if source_id in source_documents:
                    raise EvaluationIntegrityError(
                        "retrieval_eval_incomplete",
                        "manifest documents did not produce distinct Sources",
                        "inspect_retrieval_eval_inputs",
                        subject_id=document.document_id,
                    )
                source_documents[source_id] = document.document_id
            active = tuple(
                _active_locator(item, source_documents)
                for item in engine.list_active_evidence()
            )
            _validate_active_locators(manifest, active)
            results = tuple(
                _evaluate_query(engine, query, source_documents)
                for query in manifest.queries
            )
            if len(results) != len(manifest.queries) or tuple(
                item.query_id for item in results
            ) != tuple(item.query_id for item in manifest.queries):
                raise EvaluationIntegrityError(
                    "retrieval_eval_incomplete",
                    "retrieval evaluation did not execute every query",
                    "inspect_retrieval_eval_inputs",
                )
            metrics = calculate_metrics(
                tuple(
                    QueryMetricInput(
                        category=result.category,
                        relevant=query.relevant_locators,
                        retrieved=result.retrieved_locators,
                        ask_status=result.ask_status,
                    )
                    for query, result in zip(manifest.queries, results, strict=True)
                )
            )
            return _WorkspaceResult(results=results, metrics=metrics)
        except EvaluationIntegrityError:
            raise
        except Exception as error:
            raise EvaluationIntegrityError(
                "retrieval_eval_incomplete",
                "retrieval evaluation failed",
                "inspect_retrieval_eval_inputs",
            ) from error
        finally:
            engine.close()


def _ingest_document(
    engine: KnowledgeEngine,
    manifest: RetrievalEvaluationManifest,
    document: EvaluationDocument,
) -> str:
    try:
        path = manifest.resolve(document.primary_file)
        result = (
            engine.ingest_pdf(path)
            if document.media_type == "application/pdf"
            else engine.ingest_video(path)
        )
    except Exception as error:
        raise EvaluationIntegrityError(
            "retrieval_eval_ingest_failed",
            "document ingest did not publish",
            "inspect_retrieval_eval_inputs",
            subject_id=document.document_id,
        ) from error
    if result.run_state != RunState.PUBLISHED:
        raise EvaluationIntegrityError(
            "retrieval_eval_ingest_failed",
            "document ingest did not publish",
            "inspect_retrieval_eval_inputs",
            subject_id=document.document_id,
        )
    return engine.get_run(result.run_id).source_id


def _active_locator(
    item: ActiveEvidenceRef,
    source_documents: dict[str, str],
) -> StableLocator:
    document_id = source_documents.get(item.source_id)
    if document_id is None:
        raise EvaluationIntegrityError(
            "retrieval_eval_incomplete",
            "active Evidence belongs to an unknown document",
            "inspect_retrieval_eval_inputs",
        )
    kind = _locator_kind(item.locator_kind)
    return StableLocator(
        document_id=document_id,
        locator_kind=kind,
        locator_start=item.locator_start,
        locator_end=item.locator_end,
    )


def _validate_active_locators(
    manifest: RetrievalEvaluationManifest,
    active: tuple[StableLocator, ...],
) -> None:
    counts = Counter(active)
    duplicates = [locator for locator, count in counts.items() if count != 1]
    if duplicates:
        raise EvaluationIntegrityError(
            "retrieval_eval_qrel_invalid",
            "active Evidence locator is not unique",
            "inspect_retrieval_eval_inputs",
            subject_id=duplicates[0].document_id,
        )
    available = set(active)
    for query in manifest.queries:
        for locator in query.relevant_locators:
            if locator not in available:
                raise EvaluationIntegrityError(
                    "retrieval_eval_qrel_invalid",
                    "qrel does not resolve to active Evidence",
                    "fix_retrieval_eval_manifest",
                    subject_id=query.query_id,
                )


def _evaluate_query(
    engine: KnowledgeEngine,
    query: EvaluationQuery,
    source_documents: dict[str, str],
) -> QueryEvaluationResult:
    retrieved = _search_locators(engine, query, source_documents)
    ask_status = _ask_status(engine, query)
    if bool(retrieved) != (ask_status == "evidence_found"):
        raise EvaluationIntegrityError(
            "retrieval_eval_incomplete",
            "Search and Ask results disagree",
            "inspect_retrieval_eval_inputs",
            subject_id=query.query_id,
        )
    relevant = set(query.relevant_locators)
    return QueryEvaluationResult(
        query_id=query.query_id,
        category=query.category,
        relevant_locator_count=len(relevant),
        retrieved_locators=retrieved,
        relevant_retrieved_at_1=len(relevant.intersection(retrieved[:1])),
        relevant_retrieved_at_3=len(relevant.intersection(retrieved[:3])),
        relevant_retrieved_at_5=len(relevant.intersection(retrieved[:5])),
        first_relevant_rank=_first_relevant_rank(relevant, retrieved),
        ask_status=ask_status,
    )


def _search_locators(
    engine: KnowledgeEngine,
    query: EvaluationQuery,
    source_documents: dict[str, str],
) -> tuple[StableLocator, ...]:
    return tuple(
        _stable_locator(match, source_documents)
        for match in engine.search(query.text, limit=5)
    )


def _ask_status(engine: KnowledgeEngine, query: EvaluationQuery) -> AskStatus:
    status = engine.ask(query.text, limit=5).answer_status
    if status not in {"evidence_found", "insufficient_evidence"}:
        raise EvaluationIntegrityError(
            "retrieval_eval_incomplete",
            "Ask returned an unsupported status",
            "inspect_retrieval_eval_inputs",
            subject_id=query.query_id,
        )
    return cast(AskStatus, status)


def _stable_locator(
    match: SearchResult,
    source_documents: dict[str, str],
) -> StableLocator:
    try:
        document_id = source_documents[match.source_id]
    except KeyError as error:
        raise EvaluationIntegrityError(
            "retrieval_eval_incomplete",
            "retrieved Evidence belongs to an unknown document",
            "inspect_retrieval_eval_inputs",
        ) from error
    return StableLocator(
        document_id=document_id,
        locator_kind=_locator_kind(match.locator_kind),
        locator_start=match.locator_start,
        locator_end=match.locator_end,
    )


def _locator_kind(value: str) -> LocatorKind:
    if value not in {"page", "timestamp_ms"}:
        raise EvaluationIntegrityError(
            "retrieval_eval_incomplete",
            "Evidence locator kind is unsupported",
            "inspect_retrieval_eval_inputs",
        )
    return cast(LocatorKind, value)


def _first_relevant_rank(
    relevant: set[StableLocator],
    retrieved: tuple[StableLocator, ...],
) -> int | None:
    for rank, locator in enumerate(retrieved[:5], start=1):
        if locator in relevant:
            return rank
    return None


def _require_deterministic(
    first: _WorkspaceResult,
    second: _WorkspaceResult,
) -> None:
    if first != second:
        raise EvaluationIntegrityError(
            "retrieval_eval_nondeterministic",
            "retrieval evaluation results are nondeterministic",
            "inspect_retrieval_eval_inputs",
        )


def _failed_report(
    *,
    manifest_id: str,
    document_count: int,
    problem: str,
    cause: str,
    next_step: str,
    subject_id: str | None,
    started: float,
) -> RetrievalEvaluationReport:
    return RetrievalEvaluationReport(
        manifest_id=manifest_id,
        benchmark_scope="small_english_page_timestamp_corpus",
        quality_gate="none",
        status="failed",
        quality_status="not_recorded",
        document_count=document_count,
        results=(),
        metrics=None,
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


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))
