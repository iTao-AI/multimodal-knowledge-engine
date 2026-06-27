from pathlib import Path
from typing import cast

from mke.application import AskValidationError, KnowledgeEngine
from mke.domain import RunState
from mke.evaluation.chinese_protocol import (
    ChineseEvaluationQuery,
    load_chinese_retrieval_protocol,
)
from mke.evaluation.graded_metrics import (
    AskObservationStatus,
    GradedQueryMetricInput,
    calculate_graded_metrics,
)
from mke.evaluation.manifest import StableLocator
from mke.retrieval.query_policy import compile_fts5_query_diagnostic

_PROTOCOL = Path("tests/fixtures/retrieval-chinese-v1/protocol.json")


def test_active_scan_runtime_preserves_task_0_5_quality_gates(
    tmp_path: Path,
) -> None:
    protocol = load_chinese_retrieval_protocol(_PROTOCOL)
    observations: list[GradedQueryMetricInput] = []

    for split in ("development", "holdout"):
        engine = KnowledgeEngine(
            tmp_path / f"{split}.sqlite",
            retrieval_strategy="cjk-active-scan-overlap-v1",
        )
        try:
            source_documents: dict[str, str] = {}
            for document in protocol.documents:
                if document.split != split:
                    continue
                ingested = engine.ingest_pdf(protocol.resolve(document.primary_file))
                assert ingested.run_state is RunState.PUBLISHED
                source_id = engine.get_run(ingested.run_id).source_id
                source_documents[source_id] = document.document_id

            for query in protocol.queries:
                if query.split != split:
                    continue
                diagnostic = compile_fts5_query_diagnostic(
                    query.text,
                    policy="numeric-grouping-v1",
                )
                matches = engine.search(query.text, limit=10)
                retrieved = tuple(
                    StableLocator(
                        document_id=source_documents[item.source_id],
                        locator_kind="page",
                        locator_start=item.locator_start,
                        locator_end=item.locator_end,
                    )
                    for item in matches
                )
                observations.append(
                    GradedQueryMetricInput(
                        query_id=query.query_id,
                        category=query.category,
                        qrels=query.qrels,
                        retrieved=retrieved,
                        ask_status=_ask_status(engine, query),
                        compiled_query_empty=diagnostic.compiled_query_empty,
                        ascii_token_count=diagnostic.ascii_token_count,
                    )
                )
        finally:
            engine.close()

    metrics = calculate_graded_metrics(tuple(observations))

    assert metrics.recall_at_5.value == 0.659091
    assert metrics.ndcg_at_10.value == 0.619152
    assert metrics.unanswerable_no_hit_rate.value == 0.5
    assert metrics.hard_negative_failure_rate.value == 0.235294


def _ask_status(
    engine: KnowledgeEngine,
    query: ChineseEvaluationQuery,
) -> AskObservationStatus:
    try:
        result = engine.ask(query.text, limit=10)
    except AskValidationError:
        return "invalid_question"
    return cast(AskObservationStatus, result.answer_status)
