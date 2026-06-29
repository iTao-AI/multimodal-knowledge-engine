"""Qrel-free model-cache compatibility proof for local dense prerequisites."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import resource
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import cast

from mke.adapters.embedding.sentence_transformers import (
    create_sentence_transformers_embedding,
)
from mke.adapters.pdf import PyMuPDFPdfExtractor
from mke.adapters.vector.exact_cosine import (
    EXACT_COSINE_ADAPTER_ID,
    ExactCosineProjection,
)
from mke.adapters.vector.sqlite_vec import (
    SQLITE_VEC_ADAPTER_ID,
    SqliteVecProjection,
)
from mke.embeddings.contracts import (
    CANDIDATE_ID,
    CANDIDATE_REVISION,
    EMBEDDING_DIMENSION,
    MAX_MODEL_LENGTH,
    MODEL_ID,
    MODEL_REVISION,
    EmbeddedEvidence,
    EmbeddingBatch,
    EmbeddingEvidenceInput,
)
from mke.embeddings.readiness import load_cached_embedding_snapshot
from mke.vector.contracts import (
    ProjectionIdentity,
    RankedEvidence,
    VectorProjectionError,
    build_projection_identity,
)

_SCHEMA = "mke.dense_compatibility.v2"
_LOCK_SCHEMA = "mke.dense_corpus_lock.v1"
_CORPUS_ID = "retrieval-dense-v1-compatibility"
_FIXED_PROBE = "本地证据兼容性固定探针"
_PROTOCOL_PATH = "tests/fixtures/retrieval-chinese-v1/protocol.json"
_DOCUMENT_INVENTORY = (
    (
        "ub-service-core",
        "development",
        "tests/fixtures/retrieval-chinese-v1/development/ub-service-core-2.0-zh.pdf",
    ),
    (
        "development-adversarial",
        "development",
        "tests/fixtures/retrieval-chinese-v1/development/adversarial.pdf",
    ),
    (
        "copyright-law",
        "holdout",
        "tests/fixtures/retrieval-chinese-v1/holdout/copyright-law-2020.pdf",
    ),
    (
        "administrative-compulsion-law",
        "holdout",
        "tests/fixtures/retrieval-chinese-v1/holdout/administrative-compulsion-law-2011.pdf",
    ),
    (
        "holdout-adversarial",
        "holdout",
        "tests/fixtures/retrieval-chinese-v1/holdout/adversarial.pdf",
    ),
)
_REQUIRED_SNAPSHOT_FILES = {
    "modules.json",
    "tokenizer_config.json",
    "config.json",
    "model.safetensors",
}
_SNAPSHOT_LIMIT = 1_610_612_736
_MIN_PHYSICAL_MEMORY = 17_179_869_184
_STRESS_RSS_LIMIT = 6_442_450_944
_STRESS_RSS_RATIO_LIMIT = 0.40
_PROJECTION_LIMIT = 1_048_576
_QUERY_LIMIT_MS = 5_000
_SCORE_TOLERANCE = 1e-5
_SQLITE_REJECTIONS = {
    "extension_unavailable_or_incompatible",
    "projection_equivalence_failed",
    "projection_size_limit_exceeded",
}


class CompatibilityValidationError(ValueError):
    """Compatibility input or report failed a frozen integrity gate."""


@dataclass(frozen=True)
class DenseCorpusDocument:
    document_id: str
    split: str
    path: str
    byte_size: int
    sha256: str
    page_count: int


@dataclass(frozen=True)
class DenseCorpusPage:
    document_id: str
    split: str
    page: int
    text: str
    text_sha256: str


@dataclass(frozen=True)
class DenseCorpusLock:
    schema_version: str
    corpus_id: str
    protocol_sha256: str
    lock_sha256: str
    documents: tuple[DenseCorpusDocument, ...]
    pages: tuple[DenseCorpusPage, ...]


def load_dense_corpus_lock(path: Path, *, repository_root: Path) -> DenseCorpusLock:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise CompatibilityValidationError("dense corpus lock is invalid") from error
    root = repository_root.resolve()
    data = _object(payload)
    _keys(
        data,
        {
            "schema_version",
            "corpus_id",
            "protocol",
            "documents",
            "evidence_count",
            "aggregate_sha256",
        },
    )
    if (
        _string(data["schema_version"]) != _LOCK_SCHEMA
        or _string(data["corpus_id"]) != _CORPUS_ID
    ):
        raise CompatibilityValidationError("dense corpus lock is invalid")
    protocol = _object(data["protocol"])
    _keys(protocol, {"path", "sha256"})
    if _string(protocol["path"]) != _PROTOCOL_PATH:
        raise CompatibilityValidationError("dense corpus protocol identity mismatch")
    protocol_path = _repository_path(root, _PROTOCOL_PATH)
    protocol_digest = _sha256_file(protocol_path)
    if protocol_digest != _sha256_value(protocol["sha256"]):
        raise CompatibilityValidationError("dense corpus protocol identity mismatch")

    raw_documents = _list(data["documents"])
    if len(raw_documents) != len(_DOCUMENT_INVENTORY):
        raise CompatibilityValidationError("dense corpus document inventory mismatch")
    documents: list[DenseCorpusDocument] = []
    pages: list[DenseCorpusPage] = []
    extractor = PyMuPDFPdfExtractor()
    for raw_document, expected in zip(
        raw_documents,
        _DOCUMENT_INVENTORY,
        strict=True,
    ):
        record = _object(raw_document)
        _keys(
            record,
            {"document_id", "split", "path", "bytes", "sha256", "pages"},
        )
        document_id = _string(record["document_id"])
        split = _split(record["split"])
        relative_path = _string(record["path"])
        if (document_id, split, relative_path) != expected:
            raise CompatibilityValidationError("dense corpus document inventory mismatch")
        document_path = _repository_path(root, relative_path)
        byte_size = _positive_integer(record["bytes"])
        document_digest = _sha256_value(record["sha256"])
        if (
            document_path.stat().st_size != byte_size
            or _sha256_file(document_path) != document_digest
        ):
            raise CompatibilityValidationError("dense corpus document identity mismatch")
        extracted = extractor.extract(document_path)
        raw_pages = _list(record["pages"])
        if not raw_pages or len(raw_pages) != len(extracted.pages):
            raise CompatibilityValidationError("dense corpus page inventory mismatch")
        for raw_page, extracted_page in zip(
            raw_pages,
            extracted.pages,
            strict=True,
        ):
            page_record = _object(raw_page)
            _keys(page_record, {"page", "text_sha256"})
            page_number = _positive_integer(page_record["page"])
            text_digest = _sha256_value(page_record["text_sha256"])
            if page_number != extracted_page.page_number:
                raise CompatibilityValidationError("dense corpus page inventory mismatch")
            if sha256(extracted_page.text.encode("utf-8")).hexdigest() != text_digest:
                raise CompatibilityValidationError("dense corpus page text identity mismatch")
            pages.append(
                DenseCorpusPage(
                    document_id=document_id,
                    split=split,
                    page=page_number,
                    text=extracted_page.text,
                    text_sha256=text_digest,
                )
            )
        documents.append(
            DenseCorpusDocument(
                document_id=document_id,
                split=split,
                path=relative_path,
                byte_size=byte_size,
                sha256=document_digest,
                page_count=len(raw_pages),
            )
        )
    if _positive_integer(data["evidence_count"]) != len(pages):
        raise CompatibilityValidationError("dense corpus page inventory mismatch")
    aggregate = _page_aggregate(tuple(pages))
    if aggregate != _sha256_value(data["aggregate_sha256"]):
        raise CompatibilityValidationError("dense corpus aggregate identity mismatch")
    return DenseCorpusLock(
        schema_version=_LOCK_SCHEMA,
        corpus_id=_CORPUS_ID,
        protocol_sha256=protocol_digest,
        lock_sha256=sha256(raw).hexdigest(),
        documents=tuple(documents),
        pages=tuple(pages),
    )


def snapshot_measurement(
    cache_dir: Path,
) -> tuple[str, int, tuple[dict[str, object], ...]]:
    _snapshot, manifest = load_cached_embedding_snapshot(cache_dir)
    return (
        manifest.snapshot_fingerprint,
        manifest.total_bytes,
        tuple(
            {
                "relative_path": item.relative_path,
                "byte_size": item.byte_size,
                "sha256": item.sha256,
            }
            for item in manifest.files
        ),
    )


def run_single_query_smoke(
    *,
    model_cache: Path,
    repository_root: Path,
) -> dict[str, object]:
    load_started = time.monotonic()
    adapter = create_sentence_transformers_embedding(cache_dir=model_cache)
    model_load_ms = _elapsed_ms(load_started)
    snapshot_fingerprint, _snapshot_bytes, _snapshot_files = snapshot_measurement(
        model_cache
    )
    query_started = time.monotonic()
    query_vector = adapter.embed_query(_FIXED_PROBE)
    query_embedding_ms = _elapsed_ms(query_started)
    return {
        "status": "passed",
        "python": platform.python_version(),
        "interpreter": "installed",
        "cache_only": True,
        "network": False,
        "source_tree_import": _mke_import_is_under_repository(repository_root),
        "model_fingerprint": snapshot_fingerprint,
        "query_vector_digest": _vector_digest(query_vector),
        "peak_rss_bytes": _peak_rss_bytes(),
        "model_load_ms": model_load_ms,
        "query_embedding_ms": query_embedding_ms,
    }


def run_dense_compatibility(
    corpus: DenseCorpusLock,
    *,
    model_cache: Path,
    projection_path: Path,
    repository_root: Path | None = None,
    single_query_smoke: dict[str, object] | None = None,
) -> dict[str, object]:
    if single_query_smoke is None:
        raise CompatibilityValidationError(
            "dense compatibility single-query smoke report is required"
        )
    load_started = time.monotonic()
    adapter = create_sentence_transformers_embedding(cache_dir=model_cache)
    model_load_ms = _elapsed_ms(load_started)
    snapshot_fingerprint, snapshot_bytes, snapshot_files = snapshot_measurement(model_cache)
    inputs = _embedding_inputs(corpus)
    token_lengths = adapter.tokenize_lengths(tuple(item.text for item in inputs))
    zero_truncation = len(token_lengths) == len(inputs) and all(
        type(length) is int and 0 < length <= MAX_MODEL_LENGTH
        for length in token_lengths
    )
    if not zero_truncation:
        raise CompatibilityValidationError("dense corpus input would be truncated")

    first = adapter.embed_documents(inputs)
    second = adapter.embed_documents(inputs)
    first_digest = _embedding_digest(first.evidence)
    second_digest = _embedding_digest(second.evidence)
    max_component_delta = max(
        abs(left - right)
        for first_item, second_item in zip(
            first.evidence,
            second.evidence,
            strict=True,
        )
        for left, right in zip(
            first_item.vector,
            second_item.vector,
            strict=True,
        )
    )
    norm_delta = max(
        abs(_vector_norm(first_item.vector) - _vector_norm(second_item.vector))
        for first_item, second_item in zip(
            first.evidence,
            second.evidence,
            strict=True,
        )
    )
    query_started = time.monotonic()
    query_first = adapter.embed_query(_FIXED_PROBE)
    query_embedding_ms = _elapsed_ms(query_started)
    query_second = adapter.embed_query(_FIXED_PROBE)
    query_first_digest = _vector_digest(query_first)
    query_second_digest = _vector_digest(query_second)

    exact = ExactCosineProjection()
    try:
        build_started = time.monotonic()
        exact_identity = exact.replace(first)
        projection_build_ms = _elapsed_ms(build_started)
        exact.validate(exact_identity)
        repeated_exact_identity = build_projection_identity(
            second,
            adapter_id=EXACT_COSINE_ADAPTER_ID,
        )
        knn_started = time.monotonic()
        exact_results = exact.search(query_first, top_k=10)
        query_knn_ms = query_embedding_ms + _elapsed_ms(knn_started)
        repeated_exact_results = exact.search(query_second, top_k=10)
        rank_order_delta = _rank_order_delta(
            exact_results,
            repeated_exact_results,
        )
        exact_projection_bytes = (
            exact_identity.row_count * exact_identity.dimension * 4
        )
        sqlite_status = _run_sqlite_compatibility(
            first,
            query_first,
            exact_results=exact_results,
            projection_path=projection_path,
            repository_root=repository_root,
        )
    finally:
        exact.close()

    deterministic = (
        first_digest == second_digest
        and query_first_digest == query_second_digest
        and max_component_delta <= _SCORE_TOLERANCE
        and norm_delta <= _SCORE_TOLERANCE
        and rank_order_delta == 0
        and exact_identity == repeated_exact_identity
    )
    peak_rss_bytes = _peak_rss_bytes()
    physical_memory_bytes = _physical_memory_bytes()
    peak_rss_ratio = peak_rss_bytes / physical_memory_bytes
    resource_passed = (
        physical_memory_bytes >= _MIN_PHYSICAL_MEMORY
        and snapshot_bytes <= _SNAPSHOT_LIMIT
        and peak_rss_bytes <= _STRESS_RSS_LIMIT
        and peak_rss_ratio <= _STRESS_RSS_RATIO_LIMIT
        and exact_projection_bytes <= _PROJECTION_LIMIT
        and query_knn_ms <= _QUERY_LIMIT_MS
    )
    exact_reference_passed = (
        exact_identity.adapter_id == EXACT_COSINE_ADAPTER_ID
        and exact_identity.row_count == len(inputs)
    )
    gates = {
        "model_identity": (
            snapshot_fingerprint
            == first.model_fingerprint
            == second.model_fingerprint
        ),
        "cpu_float32": True,
        "remote_code_disabled": True,
        "cache_only": True,
        "zero_truncation": zero_truncation,
        "determinism": deterministic,
        "exact_reference": exact_reference_passed,
        "resources": resource_passed,
    }
    sqlite_passed = sqlite_status["status"] == "passed"
    selected_adapter = (
        SQLITE_VEC_ADAPTER_ID if sqlite_passed else EXACT_COSINE_ADAPTER_ID
    )
    report: dict[str, object] = {
        "schema_version": _SCHEMA,
        "compatibility_status": "passed" if all(gates.values()) else "failed",
        "candidate_id": CANDIDATE_ID,
        "candidate_revision": CANDIDATE_REVISION,
        "model": {
            "id": MODEL_ID,
            "revision": MODEL_REVISION,
            "snapshot_fingerprint": snapshot_fingerprint,
            "snapshot_files": list(snapshot_files),
            "dimension": EMBEDDING_DIMENSION,
        },
        "packages": {
            "sentence-transformers": version("sentence-transformers"),
            "sqlite-vec": version("sqlite-vec"),
            "huggingface-hub": version("huggingface-hub"),
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "device": "cpu",
            "dtype": "float32",
            "remote_code": False,
            "network": False,
        },
        "corpus": {
            "lock_sha256": corpus.lock_sha256,
            "evidence_count": len(corpus.pages),
            "token_lengths": list(token_lengths),
            "zero_truncation": zero_truncation,
        },
        "determinism": {
            "document_vector_digest": first_digest,
            "repeated_document_vector_digest": second_digest,
            "query_vector_digest": query_first_digest,
            "repeated_query_vector_digest": query_second_digest,
            "max_component_delta": max_component_delta,
            "norm_delta": norm_delta,
            "rank_order_delta": rank_order_delta,
            "score_tolerance": _SCORE_TOLERANCE,
            "passed": deterministic,
        },
        "projection": {
            "row_count": len(inputs),
            "selected_adapter": selected_adapter,
            "exact_reference": {
                "status": "passed" if exact_reference_passed else "failed",
                "identity": asdict(exact_identity),
                "projection_bytes": exact_projection_bytes,
            },
            "sqlite_vec": sqlite_status,
        },
        "resources": {
            "snapshot_bytes": snapshot_bytes,
            "physical_memory_bytes": physical_memory_bytes,
            "compatibility_stress_peak_rss_bytes": peak_rss_bytes,
            "compatibility_stress_peak_rss_ratio": peak_rss_ratio,
            "projection_bytes": exact_projection_bytes,
            "model_load_ms": model_load_ms,
            "projection_build_ms": projection_build_ms,
            "query_knn_ms": query_knn_ms,
            "single_query_smoke": single_query_smoke,
            "ceilings": {
                "required_physical_memory_bytes": _MIN_PHYSICAL_MEMORY,
                "snapshot_bytes": _SNAPSHOT_LIMIT,
                "compatibility_stress_peak_rss_bytes": _STRESS_RSS_LIMIT,
                "compatibility_stress_peak_rss_ratio": _STRESS_RSS_RATIO_LIMIT,
                "projection_bytes": _PROJECTION_LIMIT,
                "query_knn_ms": _QUERY_LIMIT_MS,
            },
            "passed": resource_passed,
        },
        "gates": gates,
    }
    validate_dense_compatibility_report(report, corpus)
    return report


def validate_dense_compatibility_report(
    report: dict[str, object],
    corpus: DenseCorpusLock,
) -> None:
    _keys(
        report,
        {
            "schema_version",
            "compatibility_status",
            "candidate_id",
            "candidate_revision",
            "model",
            "packages",
            "runtime",
            "corpus",
            "determinism",
            "projection",
            "resources",
            "gates",
        },
    )
    if _string(report["schema_version"]) != _SCHEMA:
        raise CompatibilityValidationError("dense compatibility report is invalid")
    if _string(report["candidate_id"]) != CANDIDATE_ID:
        raise CompatibilityValidationError(
            "dense compatibility candidate identity mismatch"
        )
    if _positive_integer(report["candidate_revision"]) != CANDIDATE_REVISION:
        raise CompatibilityValidationError(
            "dense compatibility candidate identity mismatch"
        )

    model = _object(report["model"])
    _keys(
        model,
        {"id", "revision", "snapshot_fingerprint", "snapshot_files", "dimension"},
    )
    snapshot_files = _validate_snapshot_files(model["snapshot_files"])
    snapshot_fingerprint = _snapshot_fingerprint(snapshot_files)
    if (
        _string(model["id"]) != MODEL_ID
        or _string(model["revision"]) != MODEL_REVISION
        or _positive_integer(model["dimension"]) != EMBEDDING_DIMENSION
        or _string(model["snapshot_fingerprint"]) != snapshot_fingerprint
    ):
        raise CompatibilityValidationError(
            "dense compatibility model identity mismatch"
        )

    packages = _object(report["packages"])
    _keys(packages, {"sentence-transformers", "sqlite-vec", "huggingface-hub"})
    if (
        _string(packages["sentence-transformers"]) != "5.6.0"
        or _string(packages["sqlite-vec"]) != "0.1.9"
        or not _supported_huggingface_version(
            _string(packages["huggingface-hub"])
        )
    ):
        raise CompatibilityValidationError(
            "dense compatibility package identity mismatch"
        )

    runtime = _object(report["runtime"])
    _keys(
        runtime,
        {"python", "platform", "device", "dtype", "remote_code", "network"},
    )
    python_version = _string(runtime["python"])
    runtime_passed = (
        python_version.startswith(("3.12.", "3.13."))
        and bool(_string(runtime["platform"]))
        and _string(runtime["device"]) == "cpu"
        and _string(runtime["dtype"]) == "float32"
        and not _boolean(runtime["remote_code"])
        and not _boolean(runtime["network"])
    )
    if not runtime_passed:
        raise CompatibilityValidationError(
            "dense compatibility runtime identity mismatch"
        )

    corpus_report = _object(report["corpus"])
    _keys(
        corpus_report,
        {"lock_sha256", "evidence_count", "token_lengths", "zero_truncation"},
    )
    token_lengths = _list(corpus_report["token_lengths"])
    zero_truncation = (
        _string(corpus_report["lock_sha256"]) == corpus.lock_sha256
        and _positive_integer(corpus_report["evidence_count"])
        == len(corpus.pages)
        and len(token_lengths) == len(corpus.pages)
        and all(
            0 < _positive_integer(value) <= MAX_MODEL_LENGTH
            for value in token_lengths
        )
        and _boolean(corpus_report["zero_truncation"])
    )
    if not zero_truncation:
        raise CompatibilityValidationError(
            "dense compatibility corpus identity mismatch"
        )

    determinism = _object(report["determinism"])
    _keys(
        determinism,
        {
            "document_vector_digest",
            "repeated_document_vector_digest",
            "query_vector_digest",
            "repeated_query_vector_digest",
            "max_component_delta",
            "norm_delta",
            "rank_order_delta",
            "score_tolerance",
            "passed",
        },
    )
    deterministic = (
        _fingerprint(determinism["document_vector_digest"])
        and determinism["document_vector_digest"]
        == determinism["repeated_document_vector_digest"]
        and _fingerprint(determinism["query_vector_digest"])
        and determinism["query_vector_digest"]
        == determinism["repeated_query_vector_digest"]
        and _nonnegative_number(determinism["max_component_delta"])
        <= _SCORE_TOLERANCE
        and _nonnegative_number(determinism["norm_delta"])
        <= _SCORE_TOLERANCE
        and _nonnegative_integer(determinism["rank_order_delta"]) == 0
        and _number(determinism["score_tolerance"]) == _SCORE_TOLERANCE
    )
    if _boolean(determinism["passed"]) != deterministic:
        raise CompatibilityValidationError(
            "dense compatibility determinism verdict mismatch"
        )

    projection = _object(report["projection"])
    _keys(
        projection,
        {"row_count", "selected_adapter", "exact_reference", "sqlite_vec"},
    )
    if _positive_integer(projection["row_count"]) != len(corpus.pages):
        raise CompatibilityValidationError(
            "dense compatibility projection identity mismatch"
        )
    exact_reference = _object(projection["exact_reference"])
    _keys(exact_reference, {"status", "identity", "projection_bytes"})
    exact_identity = _validate_projection_identity(
        exact_reference["identity"],
        adapter_id=EXACT_COSINE_ADAPTER_ID,
        corpus=corpus,
        snapshot_fingerprint=snapshot_fingerprint,
    )
    expected_projection_bytes = len(corpus.pages) * EMBEDDING_DIMENSION * 4
    exact_reference_passed = (
        _string(exact_reference["status"]) == "passed"
        and exact_identity.row_count == len(corpus.pages)
        and _nonnegative_integer(exact_reference["projection_bytes"])
        == expected_projection_bytes
    )
    if not exact_reference_passed:
        raise CompatibilityValidationError(
            "dense compatibility projection identity mismatch"
        )
    sqlite_passed = _validate_sqlite_status(
        projection["sqlite_vec"],
        corpus=corpus,
        snapshot_fingerprint=snapshot_fingerprint,
        exact_identity=exact_identity,
    )
    selected = _string(projection["selected_adapter"])
    expected_selected = (
        SQLITE_VEC_ADAPTER_ID if sqlite_passed else EXACT_COSINE_ADAPTER_ID
    )
    if selected != expected_selected:
        raise CompatibilityValidationError(
            "dense compatibility projection verdict mismatch"
        )

    resources = _object(report["resources"])
    _keys(
        resources,
        {
            "snapshot_bytes",
            "physical_memory_bytes",
            "compatibility_stress_peak_rss_bytes",
            "compatibility_stress_peak_rss_ratio",
            "projection_bytes",
            "model_load_ms",
            "projection_build_ms",
            "query_knn_ms",
            "single_query_smoke",
            "ceilings",
            "passed",
        },
    )
    ceilings = _object(resources["ceilings"])
    expected_ceilings = {
        "required_physical_memory_bytes": _MIN_PHYSICAL_MEMORY,
        "snapshot_bytes": _SNAPSHOT_LIMIT,
        "compatibility_stress_peak_rss_bytes": _STRESS_RSS_LIMIT,
        "compatibility_stress_peak_rss_ratio": _STRESS_RSS_RATIO_LIMIT,
        "projection_bytes": _PROJECTION_LIMIT,
        "query_knn_ms": _QUERY_LIMIT_MS,
    }
    if ceilings != expected_ceilings:
        raise CompatibilityValidationError(
            "dense compatibility resource ceilings mismatch"
        )
    snapshot_bytes = sum(
        _positive_integer(file["byte_size"])
        for file in snapshot_files
    )
    physical_memory_bytes = _positive_integer(resources["physical_memory_bytes"])
    stress_peak_rss = _nonnegative_integer(
        resources["compatibility_stress_peak_rss_bytes"]
    )
    stress_ratio = _nonnegative_number(
        resources["compatibility_stress_peak_rss_ratio"]
    )
    expected_ratio = stress_peak_rss / physical_memory_bytes
    if not math.isclose(stress_ratio, expected_ratio, rel_tol=0.0, abs_tol=1e-12):
        raise CompatibilityValidationError(
            "dense compatibility resource ratio mismatch"
        )
    _validate_single_query_smoke(
        resources["single_query_smoke"],
        snapshot_fingerprint=snapshot_fingerprint,
        runtime_python=python_version,
    )
    resource_passed = (
        _nonnegative_integer(resources["snapshot_bytes"]) == snapshot_bytes
        and physical_memory_bytes >= _MIN_PHYSICAL_MEMORY
        and snapshot_bytes <= _SNAPSHOT_LIMIT
        and stress_peak_rss <= _STRESS_RSS_LIMIT
        and stress_ratio <= _STRESS_RSS_RATIO_LIMIT
        and _nonnegative_integer(resources["projection_bytes"])
        == expected_projection_bytes
        and expected_projection_bytes <= _PROJECTION_LIMIT
        and _nonnegative_integer(resources["query_knn_ms"])
        <= _QUERY_LIMIT_MS
    )
    for timing in ("model_load_ms", "projection_build_ms"):
        _nonnegative_integer(resources[timing])
    if _boolean(resources["passed"]) != resource_passed:
        raise CompatibilityValidationError(
            "dense compatibility resource verdict mismatch"
        )

    gates = _object(report["gates"])
    expected_gates = {
        "model_identity": exact_identity.model_fingerprint
        == snapshot_fingerprint,
        "cpu_float32": runtime_passed,
        "remote_code_disabled": not _boolean(runtime["remote_code"]),
        "cache_only": not _boolean(runtime["network"]),
        "zero_truncation": zero_truncation,
        "determinism": deterministic,
        "exact_reference": exact_reference_passed,
        "resources": resource_passed,
    }
    _keys(gates, set(expected_gates))
    for name, expected in expected_gates.items():
        if _boolean(gates[name]) != expected:
            raise CompatibilityValidationError(
                "dense compatibility gate verdict mismatch"
            )
    gate_passed = all(expected_gates.values())
    status = _string(report["compatibility_status"])
    if status not in {"passed", "failed"} or (status == "passed") != gate_passed:
        raise CompatibilityValidationError(
            "dense compatibility verdict mismatch"
        )


def _validate_single_query_smoke(
    value: object,
    *,
    snapshot_fingerprint: str,
    runtime_python: str,
) -> None:
    smoke = _object(value)
    _keys(
        smoke,
        {
            "status",
            "python",
            "interpreter",
            "cache_only",
            "network",
            "source_tree_import",
            "model_fingerprint",
            "query_vector_digest",
            "peak_rss_bytes",
            "model_load_ms",
            "query_embedding_ms",
        },
    )
    if (
        _string(smoke["status"]) != "passed"
        or _string(smoke["python"]) != runtime_python
        or not _string(smoke["interpreter"])
        or not _boolean(smoke["cache_only"])
        or _boolean(smoke["network"])
        or _boolean(smoke["source_tree_import"])
        or _string(smoke["model_fingerprint"]) != snapshot_fingerprint
        or not _fingerprint(smoke["query_vector_digest"])
    ):
        raise CompatibilityValidationError(
            "dense compatibility single-query smoke mismatch"
        )
    for key in ("peak_rss_bytes", "model_load_ms", "query_embedding_ms"):
        _nonnegative_integer(smoke[key])


def _run_sqlite_compatibility(
    batch: EmbeddingBatch,
    query_vector: tuple[float, ...],
    *,
    exact_results: tuple[RankedEvidence, ...],
    projection_path: Path,
    repository_root: Path | None,
) -> dict[str, object]:
    try:
        sqlite_projection = SqliteVecProjection(
            projection_path,
            repository_root=repository_root,
        )
    except VectorProjectionError:
        return {
            "status": "rejected",
            "rejection_reason": "extension_unavailable_or_incompatible",
            "order_equal": False,
            "score_delta": None,
            "projection_bytes": 0,
            "identity": None,
        }
    try:
        sqlite_identity = sqlite_projection.replace(batch)
        sqlite_projection.validate(sqlite_identity)
        sqlite_results = sqlite_projection.search(query_vector, top_k=10)
        order_equal = tuple(
            item.stable_locator_id for item in sqlite_results
        ) == tuple(
            item.stable_locator_id for item in exact_results
        )
        score_delta = max(
            (
                abs(left.score - right.score)
                for left, right in zip(
                    sqlite_results,
                    exact_results,
                    strict=True,
                )
            ),
            default=0.0,
        )
        projection_bytes = _projection_bytes(projection_path)
        rejection_reason: str | None = None
        if not order_equal or score_delta > _SCORE_TOLERANCE:
            rejection_reason = "projection_equivalence_failed"
        elif projection_bytes > _PROJECTION_LIMIT:
            rejection_reason = "projection_size_limit_exceeded"
        return {
            "status": "passed" if rejection_reason is None else "rejected",
            "rejection_reason": rejection_reason,
            "order_equal": order_equal,
            "score_delta": score_delta,
            "projection_bytes": projection_bytes,
            "identity": asdict(sqlite_identity),
        }
    except VectorProjectionError:
        return {
            "status": "rejected",
            "rejection_reason": "extension_unavailable_or_incompatible",
            "order_equal": False,
            "score_delta": None,
            "projection_bytes": 0,
            "identity": None,
        }
    finally:
        sqlite_projection.close()


def _validate_sqlite_status(
    value: object,
    *,
    corpus: DenseCorpusLock,
    snapshot_fingerprint: str,
    exact_identity: ProjectionIdentity,
) -> bool:
    sqlite = _object(value)
    _keys(
        sqlite,
        {
            "status",
            "rejection_reason",
            "order_equal",
            "score_delta",
            "projection_bytes",
            "identity",
        },
    )
    status = _string(sqlite["status"])
    if status not in {"passed", "rejected"}:
        raise CompatibilityValidationError(
            "dense compatibility projection verdict mismatch"
        )
    projection_bytes = _nonnegative_integer(sqlite["projection_bytes"])
    order_equal = _boolean(sqlite["order_equal"])
    reason = sqlite["rejection_reason"]
    identity_value = sqlite["identity"]
    score_value = sqlite["score_delta"]
    if status == "passed":
        if reason is not None or identity_value is None or score_value is None:
            raise CompatibilityValidationError(
                "dense compatibility projection verdict mismatch"
            )
        identity = _validate_projection_identity(
            identity_value,
            adapter_id=SQLITE_VEC_ADAPTER_ID,
            corpus=corpus,
            snapshot_fingerprint=snapshot_fingerprint,
        )
        if (
            not order_equal
            or _nonnegative_number(score_value) > _SCORE_TOLERANCE
            or projection_bytes > _PROJECTION_LIMIT
            or not _equivalent_projection_identity(identity, exact_identity)
        ):
            raise CompatibilityValidationError(
                "dense compatibility projection verdict mismatch"
            )
        return True
    if type(reason) is not str or reason not in _SQLITE_REJECTIONS:
        raise CompatibilityValidationError(
            "dense compatibility projection verdict mismatch"
        )
    if reason == "extension_unavailable_or_incompatible":
        if (
            identity_value is not None
            or score_value is not None
            or order_equal
            or projection_bytes != 0
        ):
            raise CompatibilityValidationError(
                "dense compatibility projection verdict mismatch"
            )
        return False
    if identity_value is None or score_value is None:
        raise CompatibilityValidationError(
            "dense compatibility projection verdict mismatch"
        )
    identity = _validate_projection_identity(
        identity_value,
        adapter_id=SQLITE_VEC_ADAPTER_ID,
        corpus=corpus,
        snapshot_fingerprint=snapshot_fingerprint,
    )
    if not _equivalent_projection_identity(identity, exact_identity):
        raise CompatibilityValidationError(
            "dense compatibility projection verdict mismatch"
        )
    score_delta = _nonnegative_number(score_value)
    valid_rejection = (
        reason == "projection_size_limit_exceeded"
        and order_equal
        and score_delta <= _SCORE_TOLERANCE
        and projection_bytes > _PROJECTION_LIMIT
    ) or (
        reason == "projection_equivalence_failed"
        and (not order_equal or score_delta > _SCORE_TOLERANCE)
    )
    if not valid_rejection:
        raise CompatibilityValidationError(
            "dense compatibility projection verdict mismatch"
        )
    return False


def _validate_projection_identity(
    value: object,
    *,
    adapter_id: str,
    corpus: DenseCorpusLock,
    snapshot_fingerprint: str,
) -> ProjectionIdentity:
    payload = _object(value)
    _keys(
        payload,
        {
            "adapter_id",
            "model_fingerprint",
            "dimension",
            "row_count",
            "locator_digest",
            "source_text_digest",
            "vector_digest",
        },
    )
    identity = ProjectionIdentity(
        adapter_id=_string(payload["adapter_id"]),
        model_fingerprint=_string(payload["model_fingerprint"]),
        dimension=_positive_integer(payload["dimension"]),
        row_count=_positive_integer(payload["row_count"]),
        locator_digest=_string(payload["locator_digest"]),
        source_text_digest=_string(payload["source_text_digest"]),
        vector_digest=_string(payload["vector_digest"]),
    )
    locators = sorted(item.stable_locator_id for item in _embedding_inputs(corpus))
    source_digests = [locator.rsplit("|", 1)[-1] for locator in locators]
    if (
        identity.adapter_id != adapter_id
        or identity.model_fingerprint != snapshot_fingerprint
        or identity.dimension != EMBEDDING_DIMENSION
        or identity.row_count != len(corpus.pages)
        or identity.locator_digest != _json_digest(locators)
        or identity.source_text_digest != _json_digest(source_digests)
        or not _fingerprint(identity.vector_digest)
    ):
        raise CompatibilityValidationError(
            "dense compatibility projection identity mismatch"
        )
    return identity


def _equivalent_projection_identity(
    left: ProjectionIdentity,
    right: ProjectionIdentity,
) -> bool:
    return (
        left.model_fingerprint == right.model_fingerprint
        and left.dimension == right.dimension
        and left.row_count == right.row_count
        and left.locator_digest == right.locator_digest
        and left.source_text_digest == right.source_text_digest
        and left.vector_digest == right.vector_digest
    )


def _embedding_inputs(
    corpus: DenseCorpusLock,
) -> tuple[EmbeddingEvidenceInput, ...]:
    return tuple(
        EmbeddingEvidenceInput(
            document_id=page.document_id,
            locator_kind="page",
            locator_start=page.page,
            locator_end=page.page,
            text=page.text,
            text_sha256=page.text_sha256,
            runtime_evidence_id=f"compat:{page.document_id}:{page.page}",
            runtime_publication_id=f"compat:{page.split}",
        )
        for page in corpus.pages
    )


def _embedding_digest(evidence: tuple[EmbeddedEvidence, ...]) -> str:
    payload = [
        {"locator": item.stable_locator_id, "vector": list(item.vector)}
        for item in evidence
    ]
    return "sha256:" + sha256(_canonical(payload)).hexdigest()


def _vector_digest(vector: tuple[float, ...]) -> str:
    return "sha256:" + sha256(_canonical(list(vector))).hexdigest()


def _vector_norm(vector: tuple[float, ...]) -> float:
    return math.sqrt(math.fsum(value * value for value in vector))


def _rank_order_delta(
    first: tuple[RankedEvidence, ...],
    second: tuple[RankedEvidence, ...],
) -> int:
    first_order = tuple(item.stable_locator_id for item in first)
    second_order = tuple(item.stable_locator_id for item in second)
    return sum(
        left != right
        for left, right in zip(first_order, second_order, strict=True)
    )


def _page_aggregate(pages: tuple[DenseCorpusPage, ...]) -> str:
    payload = [
        {
            "document_id": page.document_id,
            "split": page.split,
            "page": page.page,
            "text_sha256": page.text_sha256,
        }
        for page in pages
    ]
    return sha256(_canonical(payload)).hexdigest()


def _json_digest(value: object) -> str:
    return "sha256:" + sha256(_canonical(value)).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _snapshot_fingerprint(files: list[dict[str, object]]) -> str:
    return "sha256:" + sha256(_canonical(files)).hexdigest()


def _validate_snapshot_files(value: object) -> list[dict[str, object]]:
    raw_files = _list(value)
    if not raw_files:
        raise CompatibilityValidationError(
            "dense compatibility model identity mismatch"
        )
    files: list[dict[str, object]] = []
    paths: set[str] = set()
    for raw_file in raw_files:
        file = _object(raw_file)
        _keys(file, {"relative_path", "byte_size", "sha256"})
        relative_path = _string(file["relative_path"])
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts or relative_path in paths:
            raise CompatibilityValidationError(
                "dense compatibility model identity mismatch"
            )
        paths.add(relative_path)
        files.append(
            {
                "relative_path": relative_path,
                "byte_size": _positive_integer(file["byte_size"]),
                "sha256": _sha256_value(file["sha256"]),
            }
        )
    if not _REQUIRED_SNAPSHOT_FILES.issubset(paths):
        raise CompatibilityValidationError(
            "dense compatibility model identity mismatch"
        )
    if files != sorted(files, key=lambda item: cast(str, item["relative_path"])):
        raise CompatibilityValidationError(
            "dense compatibility model identity mismatch"
        )
    return files


def _projection_bytes(path: Path) -> int:
    return sum(
        candidate.stat().st_size
        for candidate in (
            path,
            path.with_name(path.name + "-wal"),
            path.with_name(path.name + "-shm"),
        )
        if candidate.exists()
    )


def _peak_rss_bytes() -> int:
    maximum = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(maximum if sys.platform == "darwin" else maximum * 1024)


def _physical_memory_bytes() -> int:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, OSError, ValueError) as error:
        raise CompatibilityValidationError(
            "dense compatibility physical memory is unavailable"
        ) from error
    if type(pages) is not int or type(page_size) is not int or pages <= 0 or page_size <= 0:
        raise CompatibilityValidationError(
            "dense compatibility physical memory is unavailable"
        )
    return pages * page_size


def _mke_import_is_under_repository(repository_root: Path) -> bool:
    import mke

    module_path = Path(mke.__file__ or "").resolve()
    repository = repository_root.resolve()
    return module_path == repository or module_path.is_relative_to(repository)


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))


def _repository_path(root: Path, relative: str) -> Path:
    try:
        candidate = (root / relative).resolve(strict=True)
    except OSError as error:
        raise CompatibilityValidationError("dense corpus path is invalid") from error
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise CompatibilityValidationError("dense corpus path is invalid")
    return candidate


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CompatibilityValidationError(
            "dense compatibility value must be an object"
        )
    return cast(dict[str, object], value)


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise CompatibilityValidationError(
            "dense compatibility value must be an array"
        )
    return cast(list[object], value)


def _keys(value: dict[str, object], expected: set[str]) -> None:
    if set(value) != expected:
        raise CompatibilityValidationError(
            "dense compatibility fields are invalid"
        )


def _string(value: object) -> str:
    if type(value) is not str or not value:
        raise CompatibilityValidationError(
            "dense compatibility string is invalid"
        )
    return value


def _split(value: object) -> str:
    split = _string(value)
    if split not in {"development", "holdout"}:
        raise CompatibilityValidationError("dense corpus split is invalid")
    return split


def _positive_integer(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise CompatibilityValidationError(
            "dense compatibility integer is invalid"
        )
    return value


def _nonnegative_integer(value: object) -> int:
    if type(value) is not int or value < 0:
        raise CompatibilityValidationError(
            "dense compatibility integer is invalid"
        )
    return value


def _number(value: object) -> float:
    if type(value) is int:
        number = float(value)
    elif type(value) is float:
        number = value
    else:
        raise CompatibilityValidationError(
            "dense compatibility number is invalid"
        )
    if not math.isfinite(number):
        raise CompatibilityValidationError(
            "dense compatibility number is invalid"
        )
    return number


def _nonnegative_number(value: object) -> float:
    number = _number(value)
    if number < 0:
        raise CompatibilityValidationError(
            "dense compatibility number is invalid"
        )
    return number


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise CompatibilityValidationError(
            "dense compatibility boolean is invalid"
        )
    return value


def _sha256_value(value: object) -> str:
    digest = _string(value)
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise CompatibilityValidationError(
            "dense compatibility digest is invalid"
        )
    return digest


def _fingerprint(value: object) -> bool:
    if type(value) is not str or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )


def _supported_huggingface_version(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        return False
    major, minor, _patch = (int(part) for part in parts)
    return major == 1 and minor >= 21


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mke.evaluation.dense_compatibility"
    )
    parser.add_argument("--corpus-lock", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--single-query-smoke", action="store_true")
    parser.add_argument("--single-query-smoke-report", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repository = args.repository.resolve()
    try:
        if args.single_query_smoke:
            report = run_single_query_smoke(
                model_cache=args.model_cache,
                repository_root=repository,
            )
            print(json.dumps(report, sort_keys=True, separators=(",", ":")))
            return 0
        single_query_smoke: dict[str, object] | None = None
        if args.single_query_smoke_report is not None:
            single_query_smoke = cast(
                dict[str, object],
                json.loads(args.single_query_smoke_report.read_text(encoding="utf-8")),
            )
        corpus = load_dense_corpus_lock(
            args.corpus_lock,
            repository_root=repository,
        )
        with tempfile.TemporaryDirectory(
            prefix="mke-dense-compatibility-"
        ) as temp:
            temp_root = Path(temp).resolve()
            if temp_root.is_relative_to(repository):
                raise CompatibilityValidationError(
                    "dense compatibility projection path is invalid"
                )
            report = run_dense_compatibility(
                corpus,
                model_cache=args.model_cache,
                projection_path=temp_root / "projection.sqlite",
                repository_root=repository,
                single_query_smoke=single_query_smoke,
            )
    except Exception:
        print(
            json.dumps(
                {
                    "schema_version": _SCHEMA,
                    "compatibility_status": "failed",
                }
            )
        )
        return 1
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
