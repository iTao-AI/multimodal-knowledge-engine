"""Development-only audit of residual current-runtime Chinese retrieval misses."""

from __future__ import annotations

import json
import re
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import cast

from mke.adapters.pdf import PyMuPDFPdfExtractor
from mke.application import KnowledgeEngine
from mke.domain import RunState
from mke.evaluation.chinese_protocol import (
    ChineseEvaluationQuery,
    ChineseRetrievalProtocol,
    GradedQrel,
    load_chinese_retrieval_protocol,
)
from mke.evaluation.manifest import StableLocator
from mke.retrieval.cjk_active_scan import compile_cjk_overlap_terms
from mke.retrieval.query_policy import compile_fts5_query_diagnostic

_SCHEMA = "mke.dense_development_miss_audit.v1"
_RUNTIME_STRATEGY = "cjk-active-scan-overlap-v1"
_TARGET_CLASSES = (
    "multi_condition",
    "ranking_hard_negative",
    "semantic_paraphrase",
)
_EXPECTED_TARGET_MISSES = frozenset(
    {
        "zh-dev-semantic-04",
        "zh-dev-multi-01",
        "zh-dev-multi-02",
        "zh-dev-hard-01",
    }
)
_PRIVATE_BOUNDARY_RE = re.compile(
    r"(/Users/|[A-Za-z]:\\|\.gstack|token|api[_-]?key|secret|password)",
    flags=re.IGNORECASE,
)
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+-]{1,}")
_NUMBER_OR_DATE_RE = re.compile(r"\d")


class DenseMissAuditValidationError(ValueError):
    """Raised when the development miss audit violates the frozen boundary."""


def run_development_miss_audit(
    protocol_path: Path,
    *,
    repository_root: Path,
) -> dict[str, object]:
    protocol = load_chinese_retrieval_protocol(protocol_path)
    page_text = _load_page_text(protocol)
    observations = _current_runtime_observations(protocol)
    misses: list[dict[str, object]] = []
    for query in protocol.queries:
        if (
            query.split != "development"
            or query.category not in _TARGET_CLASSES
            or not _grade_two_qrels(query)
        ):
            continue
        retrieved = observations[query.query_id]
        if any(locator in _grade_two_locators(query) for locator in retrieved):
            continue
        diagnostic = compile_fts5_query_diagnostic(
            query.text,
            policy="numeric-grouping-v1",
        )
        active_terms = compile_cjk_overlap_terms(query.text).terms
        misses.append(
            {
                "query_id": query.query_id,
                "split": query.split,
                "category": query.category,
                "query_text_sha256": sha256(query.text.encode("utf-8")).hexdigest(),
                "compiled_query": diagnostic.compiled_query,
                "compiled_query_empty": diagnostic.compiled_query_empty,
                "ascii_token_count": diagnostic.ascii_token_count,
                "active_scan_terms": list(active_terms),
                "retrieved_locators": [_locator_payload(item) for item in retrieved],
                "constraints": _constraints(query),
                "grade_2_pages": [
                    _grade_two_page_payload(
                        qrel,
                        page_text[qrel.locator],
                        active_terms,
                    )
                    for qrel in _grade_two_qrels(query)
                ],
                "hypotheses": _hypotheses(query, active_terms),
            }
        )
    return {
        "schema_version": _SCHEMA,
        "protocol_id": protocol.protocol_id,
        "split": "development",
        "runtime_strategy": _RUNTIME_STRATEGY,
        "target_classes": sorted(_TARGET_CLASSES),
        "misses": misses,
        "limitations": [
            "development_only_residual_miss_audit",
            "hypotheses_are_not_causal_labels",
            "holdout_not_read",
        ],
        "source_identities": {
            "protocol_sha256": sha256(protocol_path.read_bytes()).hexdigest(),
            "repository_relative_protocol": str(
                protocol_path.resolve().relative_to(repository_root.resolve())
            ),
        },
    }


def validate_development_miss_audit_report(
    report: dict[str, object],
    protocol: ChineseRetrievalProtocol,
    *,
    repository_root: Path,
) -> None:
    _reject_private_or_subjective(report)
    expected = run_development_miss_audit(
        protocol.root / "protocol.json",
        repository_root=repository_root,
    )
    if report.get("schema_version") != _SCHEMA:
        raise DenseMissAuditValidationError("audit schema is invalid")
    if report.get("split") != "development":
        raise DenseMissAuditValidationError("holdout input is not allowed")
    if report.get("runtime_strategy") != _RUNTIME_STRATEGY:
        raise DenseMissAuditValidationError("runtime strategy is invalid")
    if report.get("target_classes") != sorted(_TARGET_CLASSES):
        raise DenseMissAuditValidationError("target classes are invalid")
    misses = report.get("misses")
    if not isinstance(misses, list):
        raise DenseMissAuditValidationError("target misses are invalid")
    miss_items = cast(list[object], misses)
    query_ids: set[str] = set()
    for item in miss_items:
        if not isinstance(item, dict):
            raise DenseMissAuditValidationError("target misses are invalid")
        record = cast(dict[str, object], item)
        query_id = record.get("query_id")
        if type(query_id) is not str:
            raise DenseMissAuditValidationError("target misses are invalid")
        query_ids.add(query_id)
    if query_ids != set(_EXPECTED_TARGET_MISSES):
        raise DenseMissAuditValidationError("target misses are invalid")
    expected_by_id = {
        item["query_id"]: item
        for item in cast(list[dict[str, object]], expected["misses"])
    }
    for item in miss_items:
        record = cast(dict[str, object], item)
        query_id = record.get("query_id")
        if type(query_id) is not str:
            raise DenseMissAuditValidationError("target misses are invalid")
        expected_item = expected_by_id.get(query_id)
        if expected_item is None:
            raise DenseMissAuditValidationError("target misses are invalid")
        if record.get("category") != expected_item["category"]:
            raise DenseMissAuditValidationError("audit reclassifies a query")
        if record.get("grade_2_pages") != expected_item["grade_2_pages"]:
            raise DenseMissAuditValidationError("qrel locator identity drift")
    if report != expected:
        raise DenseMissAuditValidationError("development miss audit content drift")


def _current_runtime_observations(
    protocol: ChineseRetrievalProtocol,
) -> dict[str, tuple[StableLocator, ...]]:
    with tempfile.TemporaryDirectory(prefix="mke-dense-miss-audit-") as workspace:
        engine = KnowledgeEngine(
            Path(workspace) / "development.sqlite",
            retrieval_strategy=_RUNTIME_STRATEGY,
        )
        try:
            source_documents: dict[str, str] = {}
            for document in protocol.documents:
                if document.split != "development":
                    continue
                ingested = engine.ingest_pdf(protocol.resolve(document.primary_file))
                if ingested.run_state is not RunState.PUBLISHED:
                    raise DenseMissAuditValidationError("development ingest failed")
                source_id = engine.get_run(ingested.run_id).source_id
                source_documents[source_id] = document.document_id
            observations: dict[str, tuple[StableLocator, ...]] = {}
            for query in protocol.queries:
                if query.split != "development":
                    continue
                locators: list[StableLocator] = []
                for item in engine.search(query.text, limit=10):
                    if item.locator_kind != "page":
                        raise DenseMissAuditValidationError("runtime locator is invalid")
                    locators.append(
                        StableLocator(
                            document_id=source_documents[item.source_id],
                            locator_kind="page",
                            locator_start=item.locator_start,
                            locator_end=item.locator_end,
                        )
                    )
                observations[query.query_id] = tuple(locators)
            return observations
        finally:
            engine.close()


def _load_page_text(
    protocol: ChineseRetrievalProtocol,
) -> dict[StableLocator, str]:
    extractor = PyMuPDFPdfExtractor()
    pages: dict[StableLocator, str] = {}
    for document in protocol.documents:
        if document.split != "development":
            continue
        extracted = extractor.extract(protocol.resolve(document.primary_file))
        for page in extracted.pages:
            locator = StableLocator(
                document_id=document.document_id,
                locator_kind="page",
                locator_start=page.page_number,
                locator_end=page.page_number,
            )
            pages[locator] = page.text
    return pages


def _grade_two_qrels(query: ChineseEvaluationQuery) -> tuple[GradedQrel, ...]:
    return tuple(item for item in query.qrels if item.grade == 2)


def _grade_two_locators(query: ChineseEvaluationQuery) -> frozenset[StableLocator]:
    return frozenset(item.locator for item in _grade_two_qrels(query))


def _grade_two_page_payload(
    qrel: GradedQrel,
    text: str,
    active_terms: tuple[str, ...],
) -> dict[str, object]:
    normalized_text = "".join(character for character in text.casefold() if not character.isspace())
    matched_terms = tuple(term for term in active_terms if term in normalized_text)
    overlap_ratio = (
        round(len(matched_terms) / len(active_terms), 6)
        if active_terms
        else 0.0
    )
    return {
        "locator": _locator_payload(qrel.locator),
        "page_text_sha256": sha256(text.encode("utf-8")).hexdigest(),
        "page_text_chars": len(text),
        "lexical_overlap": {
            "matched_active_scan_terms": list(matched_terms),
            "matched_count": len(matched_terms),
            "overlap_ratio": overlap_ratio,
        },
        "answer_span_locality": "not_mechanically_observable",
    }


def _constraints(query: ChineseEvaluationQuery) -> dict[str, bool]:
    ascii_tokens = _ASCII_TOKEN_RE.findall(query.text)
    return {
        "has_numeric_or_date": bool(_NUMBER_OR_DATE_RE.search(query.text)),
        "has_entity_like_ascii": bool(ascii_tokens),
        "has_multi_condition": query.category == "multi_condition"
        or any(token in query.text for token in ("同时", "以及", "且", "并且", "和")),
    }


def _hypotheses(
    query: ChineseEvaluationQuery,
    active_terms: tuple[str, ...],
) -> list[str]:
    hypotheses: list[str] = []
    if query.category in {"semantic_paraphrase", "multi_condition"}:
        hypotheses.append("dense_similarity_may_recover_related_page")
    if query.category == "multi_condition":
        hypotheses.append("constraint_preserving_decomposition_may_be_needed")
    if query.category == "ranking_hard_negative":
        hypotheses.append("ranking_or_threshold_may_be_needed")
    if not active_terms:
        hypotheses.append("query_rewrite_or_segmentation_may_be_needed")
    return hypotheses


def _locator_payload(locator: StableLocator) -> dict[str, object]:
    return {
        "document_id": locator.document_id,
        "locator_kind": locator.locator_kind,
        "locator_start": locator.locator_start,
        "locator_end": locator.locator_end,
    }


def _reject_private_or_subjective(value: object) -> None:
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        if "causal_label" in mapping:
            raise DenseMissAuditValidationError("subjective causal labels are invalid")
        for key, item in mapping.items():
            if isinstance(key, str) and key in {"debug_path", "private_path"}:
                raise DenseMissAuditValidationError("private path or secret text is invalid")
            _reject_private_or_subjective(item)
    elif isinstance(value, list):
        for item in cast(list[object], value):
            _reject_private_or_subjective(item)
    elif isinstance(value, str) and _PRIVATE_BOUNDARY_RE.search(value):
        raise DenseMissAuditValidationError("private path or secret text is invalid")


def render_development_miss_audit_json(report: dict[str, object]) -> str:
    return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
