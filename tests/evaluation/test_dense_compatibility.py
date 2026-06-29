from __future__ import annotations

import json
import math
import platform
from collections.abc import Callable
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from mke.adapters.vector.exact_cosine import EXACT_COSINE_ADAPTER_ID
from mke.adapters.vector.sqlite_vec import SQLITE_VEC_ADAPTER_ID
from mke.embeddings.contracts import (
    EMBEDDING_DIMENSION,
    EmbeddingBatch,
    EmbeddingEvidenceInput,
    build_embedding_batch,
)
from mke.evaluation.dense_compatibility import (
    CompatibilityValidationError,
    DenseCorpusLock,
    DenseCorpusPage,
    load_dense_corpus_lock,
    run_dense_compatibility,
    validate_dense_compatibility_report,
)
from mke.vector.contracts import RankedEvidence, build_projection_identity

ROOT = Path(__file__).resolve().parents[2]
CORPUS_LOCK = ROOT / "tests/fixtures/retrieval-dense-v1/corpus-lock.json"
_SNAPSHOT_FILES: tuple[dict[str, object], ...] = (
    {
        "relative_path": "config.json",
        "byte_size": 100,
        "sha256": "1" * 64,
    },
    {
        "relative_path": "model.safetensors",
        "byte_size": 700,
        "sha256": "2" * 64,
    },
    {
        "relative_path": "modules.json",
        "byte_size": 100,
        "sha256": "3" * 64,
    },
    {
        "relative_path": "tokenizer_config.json",
        "byte_size": 100,
        "sha256": "4" * 64,
    },
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


SNAPSHOT_FINGERPRINT = "sha256:" + sha256(
    _canonical(list(_SNAPSHOT_FILES))
).hexdigest()
_SYNTHETIC_PHYSICAL_MEMORY_BYTES = 32 * 1024**3
_SYNTHETIC_PEAK_RSS_BYTES = 2 * 1024**3
_FROZEN_PACKAGE_VERSIONS = {
    "sentence-transformers": "5.6.0",
    "sqlite-vec": "0.1.9",
    "huggingface-hub": "1.21.0",
}


def test_checked_in_corpus_lock_binds_only_frozen_document_and_page_inventory() -> None:
    lock = load_dense_corpus_lock(CORPUS_LOCK, repository_root=ROOT)
    raw = CORPUS_LOCK.read_text(encoding="utf-8")

    assert lock.corpus_id == "retrieval-dense-v1-compatibility"
    assert len(lock.documents) == 5
    assert len(lock.pages) == 70
    assert {page.split for page in lock.pages} == {"development", "holdout"}
    assert all(page.text and len(page.text_sha256) == 64 for page in lock.pages)
    assert all(
        term not in raw
        for term in ('"queries"', '"qrels"', '"category"', '"grade"')
    )


def test_corpus_lock_rejects_document_protocol_and_page_tampering(
    tmp_path: Path,
) -> None:
    payload = cast(
        dict[str, object],
        json.loads(CORPUS_LOCK.read_text(encoding="utf-8")),
    )
    for index, target in enumerate(("document", "protocol", "page", "inventory")):
        changed = cast(
            dict[str, object],
            json.loads(json.dumps(payload)),
        )
        documents = cast(list[dict[str, object]], changed["documents"])
        protocol = cast(dict[str, object], changed["protocol"])
        pages = cast(list[dict[str, object]], documents[0]["pages"])
        if target == "document":
            documents[0]["sha256"] = "0" * 64
        elif target == "protocol":
            protocol["sha256"] = "0" * 64
        elif target == "page":
            pages[0]["text_sha256"] = "0" * 64
        else:
            documents[0]["document_id"] = "replacement"
        path = tmp_path / f"lock-{index}.json"
        path.write_text(json.dumps(changed), encoding="utf-8")
        with pytest.raises(CompatibilityValidationError):
            load_dense_corpus_lock(path, repository_root=ROOT)


class _FakeAdapter:
    def __init__(self) -> None:
        self.document_calls = 0

    def tokenize_lengths(self, texts: tuple[str, ...]) -> tuple[int, ...]:
        return tuple(len(text) for text in texts)

    def embed_documents(
        self,
        evidence: tuple[EmbeddingEvidenceInput, ...],
    ) -> EmbeddingBatch:
        self.document_calls += 1
        vectors = tuple(
            tuple(
                1.0 if position == index else 0.0
                for position in range(EMBEDDING_DIMENSION)
            )
            for index, _ in enumerate(evidence)
        )
        return build_embedding_batch(
            evidence,
            vectors,
            model_fingerprint=SNAPSHOT_FINGERPRINT,
            output_dtype="float32",
        )

    def embed_query(self, query: str) -> tuple[float, ...]:
        return tuple(
            1.0 if position == 0 else 0.0
            for position in range(EMBEDDING_DIMENSION)
        )


def _synthetic_lock() -> DenseCorpusLock:
    pages = (
        DenseCorpusPage(
            "doc-a",
            "development",
            1,
            "first",
            sha256(b"first").hexdigest(),
        ),
        DenseCorpusPage(
            "doc-b",
            "holdout",
            1,
            "second",
            sha256(b"second").hexdigest(),
        ),
    )
    return DenseCorpusLock(
        schema_version="mke.dense_corpus_lock.v1",
        corpus_id="synthetic",
        protocol_sha256="a" * 64,
        lock_sha256="b" * 64,
        documents=(),
        pages=pages,
    )


def _snapshot_measurement(
    _cache: Path,
) -> tuple[str, int, tuple[dict[str, object], ...]]:
    return SNAPSHOT_FINGERPRINT, 1_000, _SNAPSHOT_FILES


def _single_query_smoke() -> dict[str, object]:
    return {
        "status": "passed",
        "python": platform.python_version(),
        "interpreter": "installed",
        "cache_only": True,
        "network": False,
        "source_tree_import": False,
        "model_fingerprint": SNAPSHOT_FINGERPRINT,
        "query_vector_digest": "sha256:" + "d" * 64,
        "peak_rss_bytes": 3_400_000_000,
        "model_load_ms": 1,
        "query_embedding_ms": 1,
    }


def _section(report: dict[str, object], name: str) -> dict[str, object]:
    return cast(dict[str, object], report[name])


def _frozen_package_version(name: str) -> str:
    return _FROZEN_PACKAGE_VERSIONS[name]


def _sqlite_compatibility_passed(
    batch: EmbeddingBatch,
    query_vector: tuple[float, ...],
    *,
    exact_results: tuple[RankedEvidence, ...],
    projection_path: Path,
    repository_root: Path | None,
) -> dict[str, object]:
    del query_vector, exact_results, projection_path, repository_root
    identity = build_projection_identity(
        batch,
        adapter_id=SQLITE_VEC_ADAPTER_ID,
    )
    return {
        "status": "passed",
        "rejection_reason": None,
        "order_equal": True,
        "score_delta": 0.0,
        "projection_bytes": 100_000,
        "identity": asdict(identity),
    }


def _sqlite_compatibility_size_rejected(
    batch: EmbeddingBatch,
    query_vector: tuple[float, ...],
    *,
    exact_results: tuple[RankedEvidence, ...],
    projection_path: Path,
    repository_root: Path | None,
) -> dict[str, object]:
    del query_vector, exact_results, projection_path, repository_root
    identity = build_projection_identity(
        batch,
        adapter_id=SQLITE_VEC_ADAPTER_ID,
    )
    return {
        "status": "rejected",
        "rejection_reason": "projection_size_limit_exceeded",
        "order_equal": True,
        "score_delta": 0.0,
        "projection_bytes": 4_251_648,
        "identity": asdict(identity),
    }


def _freeze_synthetic_runner_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sqlite_compatibility: object,
) -> None:
    def physical_memory_bytes() -> int:
        return _SYNTHETIC_PHYSICAL_MEMORY_BYTES

    def peak_rss_bytes() -> int:
        return _SYNTHETIC_PEAK_RSS_BYTES

    monkeypatch.setattr(
        "mke.evaluation.dense_compatibility._physical_memory_bytes",
        physical_memory_bytes,
    )
    monkeypatch.setattr(
        "mke.evaluation.dense_compatibility._peak_rss_bytes",
        peak_rss_bytes,
    )
    monkeypatch.setattr(
        "mke.evaluation.dense_compatibility.version",
        _frozen_package_version,
    )
    monkeypatch.setattr(
        "mke.evaluation.dense_compatibility._run_sqlite_compatibility",
        sqlite_compatibility,
    )


def _assert_frozen_synthetic_environment(report: dict[str, object]) -> None:
    assert _section(report, "packages") == _FROZEN_PACKAGE_VERSIONS
    resources = _section(report, "resources")
    assert resources["physical_memory_bytes"] == _SYNTHETIC_PHYSICAL_MEMORY_BYTES
    assert resources["compatibility_stress_peak_rss_bytes"] == _SYNTHETIC_PEAK_RSS_BYTES
    assert resources["compatibility_stress_peak_rss_ratio"] == 0.0625


def test_compatibility_runner_records_determinism_projection_and_resources_without_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _FakeAdapter()

    def create_adapter(
        *,
        cache_dir: Path,
        cancelled: Callable[[], bool] | None = None,
    ) -> _FakeAdapter:
        del cache_dir, cancelled
        return adapter

    monkeypatch.setattr(
        "mke.evaluation.dense_compatibility.create_sentence_transformers_embedding",
        create_adapter,
    )
    monkeypatch.setattr(
        "mke.evaluation.dense_compatibility.snapshot_measurement",
        _snapshot_measurement,
    )
    _freeze_synthetic_runner_environment(
        monkeypatch,
        sqlite_compatibility=_sqlite_compatibility_passed,
    )

    lock = _synthetic_lock()
    report = run_dense_compatibility(
        lock,
        model_cache=tmp_path / "cache",
        projection_path=tmp_path / "projection.sqlite",
        single_query_smoke=_single_query_smoke(),
    )

    validate_dense_compatibility_report(report, lock)
    assert report["compatibility_status"] == "passed"
    assert _section(report, "corpus")["zero_truncation"] is True
    assert _section(report, "determinism")["max_component_delta"] == 0.0
    projection = _section(report, "projection")
    assert _section(projection, "sqlite_vec")["status"] == "passed"
    assert projection["selected_adapter"] == SQLITE_VEC_ADAPTER_ID
    assert "metrics" not in report
    assert "queries" not in report
    assert adapter.document_calls == 2
    _assert_frozen_synthetic_environment(report)


def test_sqlite_projection_size_failure_is_structured_rejection_not_exact_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def create_adapter(
        *,
        cache_dir: Path,
        cancelled: Callable[[], bool] | None = None,
    ) -> _FakeAdapter:
        del cache_dir, cancelled
        return _FakeAdapter()

    monkeypatch.setattr(
        "mke.evaluation.dense_compatibility.create_sentence_transformers_embedding",
        create_adapter,
    )
    monkeypatch.setattr(
        "mke.evaluation.dense_compatibility.snapshot_measurement",
        _snapshot_measurement,
    )
    _freeze_synthetic_runner_environment(
        monkeypatch,
        sqlite_compatibility=_sqlite_compatibility_size_rejected,
    )

    lock = _synthetic_lock()
    report = run_dense_compatibility(
        lock,
        model_cache=tmp_path / "cache",
        projection_path=tmp_path / "projection.sqlite",
        single_query_smoke=_single_query_smoke(),
    )

    validate_dense_compatibility_report(report, lock)
    assert report["compatibility_status"] == "passed"
    projection = _section(report, "projection")
    assert projection["selected_adapter"] == EXACT_COSINE_ADAPTER_ID
    sqlite = _section(projection, "sqlite_vec")
    assert sqlite["status"] == "rejected"
    assert sqlite["rejection_reason"] == "projection_size_limit_exceeded"
    assert _section(report, "resources")["projection_bytes"] == 8_192
    _assert_frozen_synthetic_environment(report)


def test_compatibility_runner_rejects_missing_fresh_process_smoke_evidence(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        CompatibilityValidationError,
        match="single-query smoke report is required",
    ):
        run_dense_compatibility(
            _synthetic_lock(),
            model_cache=tmp_path / "cache",
            projection_path=tmp_path / "projection.sqlite",
        )


def _embedding_inputs(lock: DenseCorpusLock) -> tuple[EmbeddingEvidenceInput, ...]:
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
        for page in lock.pages
    )


def _valid_report() -> dict[str, object]:
    lock = _synthetic_lock()
    batch = _FakeAdapter().embed_documents(_embedding_inputs(lock))
    exact_identity = build_projection_identity(
        batch,
        adapter_id=EXACT_COSINE_ADAPTER_ID,
    )
    sqlite_identity = replace(exact_identity, adapter_id=SQLITE_VEC_ADAPTER_ID)
    return {
        "schema_version": "mke.dense_compatibility.v1",
        "compatibility_status": "passed",
        "candidate_id": "qwen3-embedding-0.6b-exact-v1",
        "candidate_revision": 1,
        "model": {
            "id": "Qwen/Qwen3-Embedding-0.6B",
            "revision": "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
            "snapshot_fingerprint": SNAPSHOT_FINGERPRINT,
            "snapshot_files": list(_SNAPSHOT_FILES),
            "dimension": 1024,
        },
        "packages": {
            "sentence-transformers": "5.6.0",
            "sqlite-vec": "0.1.9",
            "huggingface-hub": "1.21.0",
        },
        "runtime": {
            "python": "3.13.12",
            "platform": "synthetic",
            "device": "cpu",
            "dtype": "float32",
            "remote_code": False,
            "network": False,
        },
        "corpus": {
            "lock_sha256": lock.lock_sha256,
            "evidence_count": 2,
            "token_lengths": [5, 6],
            "zero_truncation": True,
        },
        "determinism": {
            "document_vector_digest": "sha256:" + "b" * 64,
            "repeated_document_vector_digest": "sha256:" + "b" * 64,
            "query_vector_digest": "sha256:" + "c" * 64,
            "repeated_query_vector_digest": "sha256:" + "c" * 64,
            "max_component_delta": 0.0,
            "norm_delta": 0.0,
            "rank_order_delta": 0,
            "score_tolerance": 1e-5,
            "passed": True,
        },
        "projection": {
            "row_count": 2,
            "selected_adapter": SQLITE_VEC_ADAPTER_ID,
            "exact_reference": {
                "status": "passed",
                "identity": asdict(exact_identity),
                "projection_bytes": 8_192,
            },
            "sqlite_vec": {
                "status": "passed",
                "rejection_reason": None,
                "order_equal": True,
                "score_delta": 0.0,
                "projection_bytes": 100_000,
                "identity": asdict(sqlite_identity),
            },
        },
        "resources": {
            "snapshot_bytes": 1_000,
            "peak_rss_bytes": 2_000,
            "projection_bytes": 8_192,
            "model_load_ms": 1,
            "projection_build_ms": 1,
            "query_knn_ms": 1,
            "ceilings": {
                "snapshot_bytes": 1_610_612_736,
                "peak_rss_bytes": 4_294_967_296,
                "projection_bytes": 1_048_576,
                "query_knn_ms": 5_000,
            },
            "passed": True,
        },
        "gates": {
            "model_identity": True,
            "cpu_float32": True,
            "remote_code_disabled": True,
            "cache_only": True,
            "zero_truncation": True,
            "determinism": True,
            "exact_reference": True,
            "resources": True,
        },
    }


def _amended_resource_report() -> dict[str, object]:
    report = _valid_report()
    resources = _section(report, "resources")
    physical_memory = 17_179_869_184
    stress_peak = 4_300_947_456
    ratio = stress_peak / physical_memory
    report["schema_version"] = "mke.dense_compatibility.v2"
    resources.pop("peak_rss_bytes")
    resources["physical_memory_bytes"] = physical_memory
    resources["compatibility_stress_peak_rss_bytes"] = stress_peak
    resources["compatibility_stress_peak_rss_ratio"] = ratio
    resources["single_query_smoke"] = {
        "status": "passed",
        "python": "3.13.12",
        "interpreter": "installed",
        "cache_only": True,
        "network": False,
        "source_tree_import": False,
        "model_fingerprint": SNAPSHOT_FINGERPRINT,
        "query_vector_digest": "sha256:" + "d" * 64,
        "peak_rss_bytes": 3_400_000_000,
        "model_load_ms": 1,
        "query_embedding_ms": 1,
    }
    resources["ceilings"] = {
        "required_physical_memory_bytes": 17_179_869_184,
        "snapshot_bytes": 1_610_612_736,
        "compatibility_stress_peak_rss_bytes": 6_442_450_944,
        "compatibility_stress_peak_rss_ratio": 0.40,
        "projection_bytes": 1_048_576,
        "query_knn_ms": 5_000,
    }
    return report


def test_amended_schema_records_host_memory_stress_ratio_and_query_smoke() -> None:
    report = _amended_resource_report()

    validate_dense_compatibility_report(report, _synthetic_lock())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("physical_memory_bytes", 17_179_869_183),
        ("compatibility_stress_peak_rss_bytes", 6_442_450_945),
        ("compatibility_stress_peak_rss_ratio", 0.4000001),
        ("compatibility_stress_peak_rss_ratio", True),
        ("compatibility_stress_peak_rss_ratio", math.inf),
    ],
)
def test_amended_validator_rejects_host_and_stress_resource_failures(
    field: str,
    value: object,
) -> None:
    report = _amended_resource_report()
    _section(report, "resources")[field] = value

    with pytest.raises(CompatibilityValidationError):
        validate_dense_compatibility_report(report, _synthetic_lock())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "failed"),
        ("network", True),
        ("cache_only", False),
        ("source_tree_import", True),
        ("model_fingerprint", "sha256:" + "0" * 64),
        ("peak_rss_bytes", math.nan),
    ],
)
def test_amended_validator_requires_complete_cache_only_query_smoke_evidence(
    field: str,
    value: object,
) -> None:
    report = _amended_resource_report()
    smoke = _section(_section(report, "resources"), "single_query_smoke")
    smoke[field] = value

    with pytest.raises(CompatibilityValidationError):
        validate_dense_compatibility_report(report, _synthetic_lock())


def test_validator_rejects_superseded_four_gib_schema_report() -> None:
    report = _valid_report()

    with pytest.raises(CompatibilityValidationError):
        validate_dense_compatibility_report(report, _synthetic_lock())


@pytest.mark.parametrize(
    ("section", "key", "replacement"),
    [
        (None, "candidate_revision", True),
        ("model", "revision", "main"),
        ("packages", "sqlite-vec", "0.2.0"),
        ("runtime", "python", "3.11.9"),
        ("corpus", "evidence_count", True),
        ("determinism", "max_component_delta", math.nan),
        ("resources", "projection_bytes", -1),
        ("resources", "passed", False),
        ("gates", "resources", False),
        ("model", "snapshot_fingerprint", "sha256:tampered"),
    ],
)
def test_validator_rejects_types_identity_impossible_values_and_false_pass(
    section: str | None,
    key: str,
    replacement: object,
) -> None:
    report = _valid_report()
    target = report if section is None else _section(report, section)
    target[key] = replacement

    with pytest.raises(CompatibilityValidationError):
        validate_dense_compatibility_report(report, _synthetic_lock())


def test_validator_rejects_snapshot_manifest_tampering_even_if_refingerprinted() -> None:
    report = _valid_report()
    model = _section(report, "model")
    files = cast(list[dict[str, object]], model["snapshot_files"])
    files[0]["sha256"] = "f" * 64
    model["snapshot_fingerprint"] = "sha256:" + sha256(_canonical(files)).hexdigest()

    with pytest.raises(CompatibilityValidationError):
        validate_dense_compatibility_report(report, _synthetic_lock())
