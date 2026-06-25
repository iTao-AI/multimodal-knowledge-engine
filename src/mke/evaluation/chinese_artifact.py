from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import tempfile
import tomllib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

import fitz  # pyright: ignore[reportMissingTypeStubs]

from mke.adapters.sqlite import SQLiteStore
from mke.evaluation.chinese_diagnostics import classify_miss
from mke.evaluation.chinese_protocol import (
    ChineseEvaluationQuery,
    ChineseRetrievalProtocol,
    load_chinese_retrieval_protocol,
)
from mke.evaluation.chinese_report import CHINESE_RETRIEVAL_LIMITATIONS
from mke.evaluation.graded_metrics import (
    AskObservationStatus,
    GradedQueryMetricInput,
    calculate_graded_metrics,
)
from mke.evaluation.manifest import StableLocator
from mke.retrieval.query_policy import compile_fts5_query_diagnostic

ARTIFACT_SCHEMA = "mke.retrieval_chinese_baseline.v1"
REPORT_SCHEMA = "mke.retrieval_chinese_report.v1"
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_REPORT_FIELDS = {
    "schema_version",
    "protocol_id",
    "benchmark_scope",
    "quality_gate",
    "integrity_status",
    "quality_status",
    "documents",
    "queries",
    "split_counts",
    "results",
    "metrics",
    "qrel_adjudication",
    "e3b_decision",
    "e3b_evidence",
    "e3b_reason",
    "fts5_rank_profile",
    "fts5_rank_observations",
    "integrity_failures",
    "duration_ms",
    "limitations",
}
_ARTIFACT_FIELDS = {
    "schema_version",
    "protocol_id",
    "protocol_sha256",
    "fixtures",
    "qrel_adjudication",
    "source_identity",
    "environment",
    "report_schema_version",
    "benchmark_scope",
    "quality_gate",
    "documents",
    "queries",
    "split_counts",
    "category_counts",
    "metrics",
    "query_strata",
    "miss_symptom_counts",
    "e3b_decision",
    "e3b_evidence",
    "e3b_reason",
    "fts5_rank_profile",
    "fts5_rank_observations",
    "results",
    "limitations",
}


class ChineseArtifactValidationError(ValueError):
    """The canonical E3-A artifact or its bound evidence is invalid."""


@dataclass(frozen=True)
class _ReplayedRankEvidence:
    ordered_evidence: tuple[StableLocator, ...]
    score_pairs: tuple[tuple[StableLocator, str, str], ...]


def record_chinese_artifact(
    *,
    observed_path: Path,
    artifact_path: Path,
    protocol_path: Path,
    repository_root: Path,
) -> None:
    try:
        observed = _load_object(observed_path)
        protocol = load_chinese_retrieval_protocol(protocol_path)
        _validate_observed(observed, protocol)
        artifact = _canonical_artifact(
            observed,
            protocol=protocol,
            protocol_path=protocol_path,
            repository_root=repository_root.resolve(),
        )
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = artifact_path.with_name(f".{artifact_path.name}.tmp")
        temporary.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(artifact_path)
    except ChineseArtifactValidationError:
        raise
    except Exception as error:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        ) from error


def validate_chinese_artifact(
    *,
    artifact_path: Path,
    observed_path: Path,
    protocol_path: Path,
    repository_root: Path,
) -> None:
    try:
        artifact = _load_object(artifact_path)
        if set(artifact) != _ARTIFACT_FIELDS:
            raise ChineseArtifactValidationError(
                "Chinese retrieval baseline artifact is invalid"
            )
        observed = _load_object(observed_path)
        protocol = load_chinese_retrieval_protocol(protocol_path)
        _validate_observed(observed, protocol)
        expected = _canonical_artifact(
            observed,
            protocol=protocol,
            protocol_path=protocol_path,
            repository_root=repository_root.resolve(),
        )
        if not _same_json_value(artifact, expected):
            raise ChineseArtifactValidationError(
                "Chinese retrieval baseline artifact is invalid"
            )
    except ChineseArtifactValidationError:
        raise
    except Exception as error:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        ) from error


def _canonical_artifact(
    observed: dict[str, object],
    *,
    protocol: ChineseRetrievalProtocol,
    protocol_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    metrics = _object(observed["metrics"])
    category_metrics = _list(metrics["category_metrics"])
    empty_metrics = _list(metrics["compiled_query_empty_metrics"])
    ascii_metrics = _list(metrics["ascii_token_count_metrics"])
    results = _list(observed["results"])
    symptoms = Counter(
        cast(dict[str, object], cast(dict[str, object], item).get("miss"))[
            "symptom"
        ]
        for item in results
        if cast(dict[str, object], item).get("miss") is not None
    )
    return {
        "schema_version": ARTIFACT_SCHEMA,
        "protocol_id": protocol.protocol_id,
        "protocol_sha256": _sha256(protocol_path),
        "fixtures": [
            {
                "document_id": item.document_id,
                "split": item.split,
                "path": item.primary_file.path.as_posix(),
                "bytes": item.primary_file.bytes,
                "sha256": item.primary_file.sha256,
            }
            for item in protocol.documents
        ],
        "qrel_adjudication": {
            "path": protocol.qrel_adjudication.path.relative_to(
                protocol.root
            ).as_posix(),
            "sha256": protocol.qrel_adjudication.sha256,
            "review_status": protocol.qrel_adjudication.review_status,
            "reviewed_query_count": (
                protocol.qrel_adjudication.reviewed_query_count
            ),
            "query_page_judgment_count": (
                protocol.qrel_adjudication.query_page_judgment_count
            ),
            "integrity_claim": "adjudication_record_integrity",
        },
        "source_identity": _source_identity(repository_root),
        "environment": _repository_environment_contract(repository_root),
        "report_schema_version": REPORT_SCHEMA,
        "benchmark_scope": observed["benchmark_scope"],
        "quality_gate": observed["quality_gate"],
        "documents": observed["documents"],
        "queries": observed["queries"],
        "split_counts": observed["split_counts"],
        "category_counts": {
            category: sum(item.category == category for item in protocol.queries)
            for category in (
                "chinese_exact_lexical",
                "chinese_word_boundary",
                "proper_noun_mixed",
                "number_date_unit",
                "semantic_paraphrase",
                "multi_condition",
                "ranking_hard_negative",
                "unanswerable",
            )
        },
        "metrics": {
            key: value
            for key, value in metrics.items()
            if key
            not in {
                "category_metrics",
                "compiled_query_empty_metrics",
                "ascii_token_count_metrics",
            }
        },
        "query_strata": {
            "category": category_metrics,
            "compiled_query_empty": empty_metrics,
            "ascii_token_count": ascii_metrics,
        },
        "miss_symptom_counts": dict(sorted(symptoms.items())),
        "e3b_decision": observed["e3b_decision"],
        "e3b_evidence": observed["e3b_evidence"],
        "e3b_reason": observed["e3b_reason"],
        "fts5_rank_profile": observed["fts5_rank_profile"],
        "fts5_rank_observations": observed["fts5_rank_observations"],
        "results": results,
        "limitations": observed["limitations"],
    }


def _validate_observed(
    observed: dict[str, object], protocol: ChineseRetrievalProtocol
) -> None:
    if set(observed) != _REPORT_FIELDS:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    if (
        observed["schema_version"] != REPORT_SCHEMA
        or observed["protocol_id"] != protocol.protocol_id
        or observed["benchmark_scope"] != "small_public_chinese_page_corpus"
        or observed["quality_gate"] != "none"
        or observed["integrity_status"] != "passed"
        or observed["quality_status"] != "baseline_recorded"
        or observed["documents"] != 5
        or observed["queries"] != 48
        or observed["split_counts"] != {"development": 24, "holdout": 24}
        or observed["integrity_failures"] != []
        or observed["limitations"] != list(CHINESE_RETRIEVAL_LIMITATIONS)
        or observed["fts5_rank_profile"] != "sqlite_fts5_default_bm25"
    ):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    duration = observed["duration_ms"]
    if type(duration) is not int or duration < 0:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    qrel_record = _require_fields(
        observed["qrel_adjudication"],
        {
            "sha256",
            "review_status",
            "reviewed_query_count",
            "query_page_judgment_count",
        },
    )
    if qrel_record != {
        "sha256": protocol.qrel_adjudication.sha256,
        "review_status": "complete",
        "reviewed_query_count": 48,
        "query_page_judgment_count": 1680,
    }:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    raw_results = _list(observed["results"])
    if len(raw_results) != len(protocol.queries):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    page_text = _page_text_inventory(protocol)
    locator_inventory = {
        split: frozenset(
            locator
            for locator in page_text
            if next(
                document.split
                for document in protocol.documents
                if document.document_id == locator.document_id
            )
            == split
        )
        for split in ("development", "holdout")
    }
    metric_inputs = tuple(
        _validate_result(
            raw,
            query,
            locator_inventory=locator_inventory[query.split],
            page_text=page_text,
        )
        for raw, query in zip(raw_results, protocol.queries, strict=True)
    )
    expected_metrics = _jsonable(asdict(calculate_graded_metrics(metric_inputs)))
    if not _same_json_value(observed["metrics"], expected_metrics):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    _validate_rank_observations(
        observed["fts5_rank_observations"],
        protocol,
        metric_inputs=metric_inputs,
        locator_inventory=locator_inventory,
        replayed=_replay_rank_observations(protocol, page_text),
    )
    e3b_evidence = _require_fields(
        observed["e3b_evidence"],
        {
            "development_answerable_compiled_query_empty_misses",
            "qrel_review_status",
            "query_page_judgment_count",
        },
    )
    expected_empty_misses = sum(
        item.split == "development"
        and any(qrel.grade == 2 for qrel in item.qrels)
        and input_item.compiled_query_empty
        and not any(
            locator in {qrel.locator for qrel in item.qrels if qrel.grade == 2}
            for locator in input_item.retrieved
        )
        for item, input_item in zip(protocol.queries, metric_inputs, strict=True)
    )
    if not _same_json_value(e3b_evidence, {
        "development_answerable_compiled_query_empty_misses": (
            expected_empty_misses
        ),
        "qrel_review_status": "complete",
        "query_page_judgment_count": 1680,
    }):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    eligible = expected_empty_misses >= 1
    if (
        observed["e3b_decision"]
        != ("eligible" if eligible else "not_justified")
        or observed["e3b_reason"]
        != (
            "development_compiled_query_empty_miss_observed"
            if eligible
            else "no_development_compiled_query_empty_miss"
        )
    ):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )


def _validate_result(
    value: object,
    query: ChineseEvaluationQuery,
    *,
    locator_inventory: frozenset[StableLocator],
    page_text: Mapping[StableLocator, str],
) -> GradedQueryMetricInput:
    result = _require_fields(
        value,
        {
            "query_id",
            "split",
            "category",
            "qrel_counts",
            "retrieved",
            "direct_ranks",
            "hard_negative_failure",
            "ask_status",
            "compiled_query",
            "ascii_token_count",
            "compiled_query_empty",
            "miss",
        },
    )
    diagnostic = compile_fts5_query_diagnostic(
        query.text, policy="numeric-grouping-v1"
    )
    if (
        result["query_id"] != query.query_id
        or result["split"] != query.split
        or result["category"] != query.category
        or result["compiled_query"] != diagnostic.compiled_query
        or type(result["ascii_token_count"]) is not int
        or result["ascii_token_count"] != diagnostic.ascii_token_count
        or type(result["compiled_query_empty"]) is not bool
        or result["compiled_query_empty"] != diagnostic.compiled_query_empty
    ):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    expected_qrel_counts = {
        "grade_0": sum(item.grade == 0 for item in query.qrels),
        "grade_1": sum(item.grade == 1 for item in query.qrels),
        "grade_2": sum(item.grade == 2 for item in query.qrels),
    }
    if not _same_json_value(result["qrel_counts"], expected_qrel_counts):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    qrel_by_locator = {item.locator: item.grade for item in query.qrels}
    retrieved: list[StableLocator] = []
    raw_retrieved = _list(result["retrieved"])
    if len(raw_retrieved) > 10:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    for raw in raw_retrieved:
        record = _require_fields(raw, {"locator", "grade"})
        locator = _locator(record["locator"])
        expected_grade = qrel_by_locator.get(locator)
        if (
            locator not in locator_inventory
            or not _same_json_value(record["grade"], expected_grade)
        ):
            raise ChineseArtifactValidationError(
                "Chinese retrieval baseline artifact is invalid"
            )
        retrieved.append(locator)
    if len(retrieved) != len(set(retrieved)):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    direct = {item.locator for item in query.qrels if item.grade == 2}
    expected_direct_ranks = [
        rank
        for rank, locator in enumerate(retrieved, start=1)
        if locator in direct
    ]
    if not _same_json_value(result["direct_ranks"], expected_direct_ranks):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    expected_hard_failure = _hard_negative_failure(query, tuple(retrieved))
    if type(result["hard_negative_failure"]) is not bool or (
        result["hard_negative_failure"] != expected_hard_failure
    ):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    ask_status = result["ask_status"]
    if ask_status not in {
        "evidence_found",
        "insufficient_evidence",
        "invalid_question",
    }:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    if diagnostic.compiled_query_empty != (ask_status == "invalid_question"):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    miss = result["miss"]
    if direct and not expected_direct_ranks:
        miss_record = _require_fields(
            miss,
            {
                "symptom",
                "compiled_query",
                "ascii_token_count",
                "compiled_query_empty",
                "direct_locators",
                "returned_direct_ranks",
                "returned_distractor_ranks",
                "direct_page_clause_coverage",
                "observation",
            },
        )
        expected_miss = classify_miss(
            diagnostic,
            qrels=query.qrels,
            retrieved=tuple(retrieved),
            direct_page_text={
                item.locator: page_text[item.locator]
                for item in query.qrels
                if item.grade == 2
            },
        )
        if not _same_json_value(
            miss_record,
            _jsonable(asdict(expected_miss)),
        ):
            raise ChineseArtifactValidationError(
                "Chinese retrieval baseline artifact is invalid"
            )
    elif miss is not None:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    return GradedQueryMetricInput(
        query_id=query.query_id,
        category=query.category,
        qrels=query.qrels,
        retrieved=tuple(retrieved),
        ask_status=cast(AskObservationStatus, ask_status),
        compiled_query_empty=diagnostic.compiled_query_empty,
        ascii_token_count=diagnostic.ascii_token_count,
    )


def _validate_rank_observations(
    value: object,
    protocol: ChineseRetrievalProtocol,
    *,
    metric_inputs: tuple[GradedQueryMetricInput, ...],
    locator_inventory: Mapping[str, frozenset[StableLocator]],
    replayed: Mapping[str, _ReplayedRankEvidence],
) -> None:
    observations = _list(value)
    expected_queries = tuple(
        query
        for query in protocol.queries
        if compile_fts5_query_diagnostic(
            query.text, policy="numeric-grouping-v1"
        ).compiled_query
    )
    if len(observations) != len(expected_queries):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    inputs_by_query = {
        query.query_id: metric_input
        for query, metric_input in zip(
            protocol.queries, metric_inputs, strict=True
        )
    }
    for raw, query in zip(observations, expected_queries, strict=True):
        record = _require_fields(
            raw,
            {
                "query_id",
                "split",
                "result_count",
                "ordered_evidence_ids_sha256",
                "score_pairs_sha256",
                "rank_override_present",
                "ordered_evidence",
                "score_pairs",
            },
        )
        ordered_evidence = tuple(
            _locator(item) for item in _list(record["ordered_evidence"])
        )
        score_pairs = tuple(
            _rank_score_pair(item) for item in _list(record["score_pairs"])
        )
        expected = replayed.get(query.query_id)
        if expected is None:
            raise ChineseArtifactValidationError(
                "Chinese retrieval baseline artifact is invalid"
            )
        expected_stable_ids = tuple(
            _stable_evidence_identity(locator)
            for locator in expected.ordered_evidence
        )
        expected_score_pairs = tuple(
            (
                _stable_evidence_identity(locator),
                rank_score_hex,
                bm25_score_hex,
            )
            for locator, rank_score_hex, bm25_score_hex in expected.score_pairs
        )
        retrieved = inputs_by_query[query.query_id].retrieved
        if (
            record["query_id"] != query.query_id
            or record["split"] != query.split
            or type(record["result_count"]) is not int
            or record["result_count"] < 0
            or (
                query.query_id == protocol.rank_probe_query_id
                and record["result_count"] == 0
            )
            or record["rank_override_present"] is not False
            or record["result_count"] != len(ordered_evidence)
            or len(score_pairs) != len(ordered_evidence)
            or tuple(item[0] for item in score_pairs) != ordered_evidence
            or len(set(ordered_evidence)) != len(ordered_evidence)
            or any(
                locator not in locator_inventory[query.split]
                for locator in ordered_evidence
            )
            or ordered_evidence != expected.ordered_evidence
            or score_pairs != expected.score_pairs
            or record["result_count"] != len(expected.ordered_evidence)
            or len(retrieved) != min(10, len(expected.ordered_evidence))
            or retrieved != expected.ordered_evidence[: len(retrieved)]
            or record["ordered_evidence_ids_sha256"]
            != _digest(expected_stable_ids)
            or record["score_pairs_sha256"]
            != _digest(expected_score_pairs)
        ):
            raise ChineseArtifactValidationError(
                "Chinese retrieval baseline artifact is invalid"
            )
        _require_sha256(record["ordered_evidence_ids_sha256"])
        _require_sha256(record["score_pairs_sha256"])


def _replay_rank_observations(
    protocol: ChineseRetrievalProtocol,
    page_text: Mapping[StableLocator, str],
) -> dict[str, _ReplayedRankEvidence]:
    replayed: dict[str, _ReplayedRankEvidence] = {}
    try:
        for split in ("development", "holdout"):
            with tempfile.TemporaryDirectory(
                prefix=f"mke-retrieval-chinese-replay-{split}-"
            ) as workspace:
                store = SQLiteStore(
                    Path(workspace) / "mke.sqlite",
                    query_policy="numeric-grouping-v1",
                )
                try:
                    evidence_by_id = _seed_replay_partition(
                        store,
                        protocol,
                        page_text=page_text,
                        split=split,
                    )
                    for query in protocol.queries:
                        if query.split != split:
                            continue
                        diagnostic = compile_fts5_query_diagnostic(
                            query.text, policy="numeric-grouping-v1"
                        )
                        if not diagnostic.compiled_query:
                            continue
                        profile = store.observe_fts5_rank(
                            diagnostic.compiled_query
                        )
                        rank_ids = tuple(
                            item.evidence_id for item in profile.rank_order
                        )
                        bm25_ids = tuple(
                            item.evidence_id for item in profile.bm25_order
                        )
                        if (
                            profile.rank_override_present
                            or rank_ids != bm25_ids
                            or any(
                                not math.isfinite(item.rank_score)
                                or not math.isfinite(item.bm25_score)
                                or not math.isclose(
                                    item.rank_score,
                                    item.bm25_score,
                                    rel_tol=0.0,
                                    abs_tol=1e-12,
                                )
                                for item in profile.rank_order
                            )
                        ):
                            raise ChineseArtifactValidationError(
                                "Chinese retrieval baseline artifact is invalid"
                            )
                        ordered = tuple(
                            evidence_by_id[evidence_id]
                            for evidence_id in rank_ids
                        )
                        replayed[query.query_id] = _ReplayedRankEvidence(
                            ordered_evidence=ordered,
                            score_pairs=tuple(
                                (
                                    evidence_by_id[item.evidence_id],
                                    item.rank_score.hex(),
                                    item.bm25_score.hex(),
                                )
                                for item in profile.rank_order
                            ),
                        )
                finally:
                    store.close()
    except ChineseArtifactValidationError:
        raise
    except Exception as error:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        ) from error
    return replayed


def _seed_replay_partition(
    store: SQLiteStore,
    protocol: ChineseRetrievalProtocol,
    *,
    page_text: Mapping[StableLocator, str],
    split: str,
) -> dict[str, StableLocator]:
    connection = store._connection  # pyright: ignore[reportPrivateUsage]
    library_id = f"replay-library-{split}"
    evidence_by_id: dict[str, StableLocator] = {}
    with connection:
        connection.execute(
            "INSERT INTO libraries(library_id, name) VALUES (?, ?)",
            (library_id, f"replay-{split}"),
        )
        for document in protocol.documents:
            if document.split != split:
                continue
            asset_id = f"replay-asset-{document.document_id}"
            source_id = f"replay-source-{document.document_id}"
            run_id = f"replay-run-{document.document_id}"
            publication_id = f"replay-publication-{document.document_id}"
            connection.execute(
                """
                INSERT INTO assets(asset_id, sha256, media_type)
                VALUES (?, ?, ?)
                """,
                (
                    asset_id,
                    document.primary_file.sha256,
                    document.media_type,
                ),
            )
            connection.execute(
                """
                INSERT INTO sources(
                  source_id, library_id, asset_id, display_name,
                  active_publication_id, active_revision, requested_generation
                ) VALUES (?, ?, ?, ?, ?, 1, 1)
                """,
                (
                    source_id,
                    library_id,
                    asset_id,
                    document.document_id,
                    publication_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO runs(
                  run_id, source_id, state, source_generation,
                  based_on_active_revision
                ) VALUES (?, ?, 'published', 1, 0)
                """,
                (run_id, source_id),
            )
            connection.execute(
                """
                INSERT INTO publications(
                  publication_id, source_id, run_id, revision
                ) VALUES (?, ?, ?, 1)
                """,
                (publication_id, source_id, run_id),
            )
            locators = sorted(
                locator
                for locator in page_text
                if locator.document_id == document.document_id
            )
            for locator in locators:
                evidence_id = (
                    f"replay-evidence-{document.document_id}-"
                    f"{locator.locator_start:04d}"
                )
                text = page_text[locator]
                connection.execute(
                    """
                    INSERT INTO evidence(
                      evidence_id, run_id, source_id, locator_kind,
                      locator_start, locator_end, text
                    ) VALUES (?, ?, ?, 'page', ?, ?, ?)
                    """,
                    (
                        evidence_id,
                        run_id,
                        source_id,
                        locator.locator_start,
                        locator.locator_end,
                        text,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO active_evidence_fts(
                      library_id, source_id, publication_id, evidence_id,
                      locator_label, text
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        library_id,
                        source_id,
                        publication_id,
                        evidence_id,
                        f"page:{locator.locator_start}",
                        text,
                    ),
                )
                evidence_by_id[evidence_id] = locator
    return evidence_by_id


def _source_identity(repository_root: Path) -> dict[str, object]:
    files = [
        {
            "path": path.relative_to(repository_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(repository_root.glob("src/mke/**/*.py"))
        if path.is_file() and path.resolve().is_relative_to(repository_root)
    ]
    if not files:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    encoded = json.dumps(
        files, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "files": files,
    }


def _page_text_inventory(
    protocol: ChineseRetrievalProtocol,
) -> dict[StableLocator, str]:
    inventory: dict[StableLocator, str] = {}
    try:
        for document in protocol.documents:
            with fitz.open(protocol.resolve(document.primary_file)) as pdf:
                for index in range(1, len(pdf) + 1):
                    page = pdf[index - 1]  # pyright: ignore[reportUnknownVariableType]
                    locator = StableLocator(
                        document_id=document.document_id,
                        locator_kind="page",
                        locator_start=index,
                        locator_end=index,
                    )
                    text = cast(
                        object,
                        page.get_text(  # pyright: ignore[reportUnknownMemberType]
                            "text", sort=True
                        ),
                    )
                    if not isinstance(text, str):
                        raise ChineseArtifactValidationError(
                            "Chinese retrieval baseline artifact is invalid"
                        )
                    inventory[locator] = text
    except Exception as error:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        ) from error
    return inventory


def _repository_environment_contract(
    repository_root: Path,
) -> dict[str, object]:
    try:
        pyproject = tomllib.loads(
            (repository_root / "pyproject.toml").read_text(encoding="utf-8")
        )
        requires_python = pyproject["project"]["requires-python"]
        workflow = (
            repository_root / ".github/workflows/ci.yml"
        ).read_text(encoding="utf-8")
        matrix = re.search(
            r'python-version:\s*\[([^\]]+)\]',
            workflow,
        )
        if matrix is None:
            raise ValueError
        ci_versions = re.findall(r'"(\d+\.\d+)"', matrix.group(1))
        lock = tomllib.loads(
            (repository_root / "uv.lock").read_text(encoding="utf-8")
        )
        packages = cast(list[dict[str, object]], lock["package"])
        pymupdf = next(
            package["version"]
            for package in packages
            if package.get("name") == "pymupdf"
        )
    except (KeyError, OSError, TypeError, ValueError, StopIteration) as error:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        ) from error
    if (
        not isinstance(requires_python, str)
        or not isinstance(pymupdf, str)
        or ci_versions != ["3.12", "3.13"]
    ):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    return {
        "schema_version": "mke.retrieval_environment_contract.v1",
        "python_requires": requires_python,
        "ci_python_versions": ci_versions,
        "pymupdf_lock_version": pymupdf,
        "sqlite_profile": "sqlite_fts5_default_bm25",
    }


def _rank_score_pair(
    value: object,
) -> tuple[StableLocator, str, str]:
    record = _require_fields(
        value,
        {"locator", "rank_score_hex", "bm25_score_hex"},
    )
    locator = _locator(record["locator"])
    rank_hex = record["rank_score_hex"]
    bm25_hex = record["bm25_score_hex"]
    if not isinstance(rank_hex, str) or not isinstance(bm25_hex, str):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    try:
        rank_score = float.fromhex(rank_hex)
        bm25_score = float.fromhex(bm25_hex)
    except ValueError as error:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        ) from error
    if (
        not math.isfinite(rank_score)
        or not math.isfinite(bm25_score)
        or not math.isclose(
            rank_score, bm25_score, rel_tol=0.0, abs_tol=1e-12
        )
    ):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    return locator, rank_hex, bm25_hex


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


def _locator(value: object) -> StableLocator:
    record = _require_fields(
        value,
        {"document_id", "locator_kind", "locator_start", "locator_end"},
    )
    if (
        not isinstance(record["document_id"], str)
        or record["locator_kind"] != "page"
        or type(record["locator_start"]) is not int
        or type(record["locator_end"]) is not int
        or record["locator_start"] <= 0
        or record["locator_start"] != record["locator_end"]
    ):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    return StableLocator(
        document_id=record["document_id"],
        locator_kind="page",
        locator_start=record["locator_start"],
        locator_end=record["locator_end"],
    )


def _load_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        ) from error
    if not isinstance(payload, dict):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    return cast(dict[str, object], payload)


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    return cast(dict[str, object], value)


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    return cast(list[object], value)


def _require_fields(
    value: object, fields: set[str]
) -> dict[str, object]:
    record = _object(value)
    if set(record) != fields:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )
    return record


def _require_sha256(value: object) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ChineseArtifactValidationError(
            "Chinese retrieval baseline artifact is invalid"
        )


def _same_json_value(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        actual_record = cast(dict[str, object], actual)
        expected_record = cast(dict[str, object], expected)
        if set(actual_record) != set(expected_record):
            return False
        return all(
            _same_json_value(actual_record[key], expected_record[key])
            for key in expected_record
        )
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        actual_items = cast(list[object], actual)
        expected_items = cast(list[object], expected)
        return len(actual_items) == len(expected_items) and all(
            _same_json_value(left, right)
            for left, right in zip(
                actual_items, expected_items, strict=True
            )
        )
    return actual == expected


def _jsonable(value: object) -> object:
    return json.loads(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record or validate the Chinese retrieval baseline artifact."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("record", "validate"):
        command = commands.add_parser(name)
        command.add_argument("--artifact", type=Path, required=True)
        command.add_argument("--observed", type=Path, required=True)
        command.add_argument("--protocol", type=Path, required=True)
        command.add_argument("--repository", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            record_chinese_artifact(
                observed_path=args.observed,
                artifact_path=args.artifact,
                protocol_path=args.protocol,
                repository_root=args.repository,
            )
            print("Chinese retrieval baseline artifact recorded")
            return 0
        validate_chinese_artifact(
            artifact_path=args.artifact,
            observed_path=args.observed,
            protocol_path=args.protocol,
            repository_root=args.repository,
        )
    except ChineseArtifactValidationError:
        print(
            "problem=retrieval_chinese_artifact_invalid "
            "cause=Chinese retrieval baseline artifact is invalid "
            "next_step=regenerate_chinese_artifact"
        )
        return 1
    print("Chinese retrieval baseline artifact valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
