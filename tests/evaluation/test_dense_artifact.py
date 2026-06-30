from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest

from mke.evaluation.chinese_protocol import load_chinese_retrieval_protocol
from mke.evaluation.dense_artifact import (
    DenseArtifactValidationError,
    build_dense_comparison_artifact,
    derive_dense_threshold_inputs,
    validate_dense_comparison_artifact,
)
from mke.evaluation.dense_compatibility import load_dense_corpus_lock
from mke.evaluation.dense_protocol import load_dense_protocol_lock
from mke.evaluation.dense_threshold import select_dense_threshold

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "tests/fixtures/retrieval-dense-v1/protocol-lock.json"
ArtifactMutation = Callable[[dict[str, Any]], None]
_ARTIFACT_MUTATIONS: tuple[ArtifactMutation, ...] = (
    lambda payload: payload["threshold_report"].__setitem__(
        "selected_threshold", 0.7
    ),
    lambda payload: payload["comparison"].__setitem__(
        "e3d_status", "not_eligible"
    ),
    lambda payload: payload["development_candidate"]["observations"].reverse(),
    lambda payload: payload["development_candidate"]["observations"][0][
        "results"
    ][0].__setitem__("rank", True),
    lambda payload: payload["development_candidate"]["observations"][0][
        "results"
    ][0]["locator"].__setitem__("document_id", "unknown"),
    lambda payload: payload["source"]["files"][0].__setitem__(
        "sha256", "0" * 64
    ),
)


def test_dense_artifact_recomputes_threshold_metrics_and_verdict() -> None:
    artifact = synthetic_artifact()

    validate_dense_comparison_artifact(
        artifact,
        protocol_path=PROTOCOL_PATH,
        repository_root=ROOT,
        current_runtime_loader=_current_runtime_semantics,
    )

    assert artifact["schema_version"] == "mke.dense_comparison_artifact.v1"
    assert artifact["comparison"]["candidate_status"] == "completed"
    assert artifact["comparison"]["e3d_status"] == "eligible"
    assert artifact["comparison"]["runtime_promotion_status"] == "not_evaluated"
    assert artifact["threshold_report"]["selected_threshold"] == 0.8
    assert artifact["state"]["development_freeze_sha256"] == "1" * 64
    assert artifact["state"]["holdout_receipt_sha256"] == "2" * 64
    assert set(artifact["metrics"]) == {"development", "holdout"}


def test_dense_artifact_model_free_validation_uses_recorded_runtime_semantics() -> None:
    validate_dense_comparison_artifact(
        synthetic_artifact(),
        protocol_path=PROTOCOL_PATH,
        repository_root=ROOT,
    )


def test_checked_in_dense_artifact_binds_current_historical_arm_identities() -> None:
    artifact = json.loads(
        (
            ROOT
            / "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json"
        ).read_text(encoding="utf-8")
    )
    e3a_sha = sha256(
        (ROOT / "benchmarks/retrieval/retrieval-chinese-v1-baseline.json").read_bytes()
    ).hexdigest()
    e3b_sha = sha256(
        (
            ROOT / "benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json"
        ).read_bytes()
    ).hexdigest()

    assert artifact["historical_arms"]["e3a"]["sha256"] == e3a_sha
    assert artifact["historical_arms"]["e3b"]["sha256"] == e3b_sha
    assert artifact["comparison"]["arms"][:2] == [
        {
            "arm_id": "e3a-historical-fts5-baseline",
            "semantic_digest": e3a_sha,
        },
        {
            "arm_id": "cjk-trigram-overlap-v1",
            "semantic_digest": e3b_sha,
        },
    ]


@pytest.mark.parametrize(
    "mutation",
    _ARTIFACT_MUTATIONS,
)
def test_dense_artifact_rejects_identity_observation_and_verdict_tampering(
    mutation: ArtifactMutation,
) -> None:
    artifact = synthetic_artifact()
    tampered = deepcopy(artifact)
    mutation(tampered)

    with pytest.raises(DenseArtifactValidationError):
        validate_dense_comparison_artifact(
            tampered,
            protocol_path=PROTOCOL_PATH,
            repository_root=ROOT,
            current_runtime_loader=_current_runtime_semantics,
        )


def test_dense_artifact_rejects_runtime_and_compatibility_identity_drift() -> None:
    artifact = synthetic_artifact()
    changed_runtime = _current_runtime_semantics()
    changed_runtime["results"][0]["direct_ranks"] = [1]

    with pytest.raises(DenseArtifactValidationError):
        validate_dense_comparison_artifact(
            artifact,
            protocol_path=PROTOCOL_PATH,
            repository_root=ROOT,
            current_runtime_loader=lambda: changed_runtime,
        )

    tampered = deepcopy(artifact)
    tampered["compatibility"]["model_fingerprint"] = "sha256:" + "0" * 64
    with pytest.raises(DenseArtifactValidationError):
        validate_dense_comparison_artifact(
            tampered,
            protocol_path=PROTOCOL_PATH,
            repository_root=ROOT,
            current_runtime_loader=_current_runtime_semantics,
        )


def test_threshold_inputs_do_not_count_current_runtime_hits_as_dense_recovery() -> None:
    candidate = synthetic_candidate_report("development")
    runtime = _current_runtime_semantics()
    semantic_query = next(
        item
        for item in runtime["results"]
        if item["category"] == "semantic_paraphrase"
    )
    semantic_query["direct_ranks"] = [1]
    chinese = load_chinese_retrieval_protocol(
        ROOT / "tests/fixtures/retrieval-chinese-v1/protocol.json"
    )

    inputs = derive_dense_threshold_inputs(
        candidate,
        partition="development",
        chinese=chinese,
        runtime=runtime,
    )

    semantic_input = next(item for item in inputs if item.query_id == semantic_query["query_id"])
    assert semantic_input.current_runtime_missed is False
    assert semantic_input.recovery_score is None
    assert semantic_input.ranked_scores_and_grades
    report = select_dense_threshold(inputs)
    assert report["development_status"] == "passed"


def test_threshold_inputs_allow_unanswerable_ranked_no_hit_evidence() -> None:
    candidate = synthetic_candidate_report("development")
    result = deepcopy(candidate["observations"][0]["results"][0])
    result["portable_score"] = 0.75
    result["raw_score"] = 0.75
    unanswerable = next(
        item
        for item in candidate["observations"]
        if item["category"] == "unanswerable"
    )
    unanswerable["results"] = [result]
    chinese = load_chinese_retrieval_protocol(
        ROOT / "tests/fixtures/retrieval-chinese-v1/protocol.json"
    )

    inputs = derive_dense_threshold_inputs(
        candidate,
        partition="development",
        chinese=chinese,
        runtime=_current_runtime_semantics(),
    )

    unanswerable_input = next(item for item in inputs if item.category == "unanswerable")
    assert unanswerable_input.unanswerable_top_score == 0.75
    assert unanswerable_input.hard_negative_failure_score is None
    assert unanswerable_input.ideal_grades == ()
    assert unanswerable_input.ranked_scores_and_grades == ((0.75, 0),)
    report = select_dense_threshold(inputs)
    assert report["threshold_trace"]


def synthetic_artifact() -> dict[str, Any]:
    return build_dense_comparison_artifact(
        protocol_path=PROTOCOL_PATH,
        repository_root=ROOT,
        development_candidate=synthetic_candidate_report("development"),
        holdout_candidate=synthetic_candidate_report("holdout"),
        current_runtime_payload=_current_runtime_semantics(),
        development_freeze_sha256="1" * 64,
        holdout_receipt_sha256="2" * 64,
    )


def synthetic_candidate_report(partition: str) -> dict[str, Any]:
    protocol = load_dense_protocol_lock(PROTOCOL_PATH, repository_root=ROOT)
    chinese = load_chinese_retrieval_protocol(
        ROOT / "tests/fixtures/retrieval-chinese-v1/protocol.json"
    )
    corpus = load_dense_corpus_lock(
        ROOT / "tests/fixtures/retrieval-dense-v1/corpus-lock.json",
        repository_root=ROOT,
    )
    pages = tuple(item for item in corpus.pages if item.split == partition)
    by_locator = {
        (item.document_id, item.page): item
        for item in pages
    }
    stable_ids = sorted(
        f"{item.document_id}|page|{item.page}|{item.page}|{item.text_sha256}"
        for item in pages
    )
    source_digests = [item.rsplit("|", 1)[-1] for item in stable_ids]
    compatibility = json.loads(
        (ROOT / "benchmarks/retrieval/qwen3-embedding-0.6b-compatibility.json").read_text(
            encoding="utf-8"
        )
    )
    observations: list[dict[str, Any]] = []
    for query in chinese.queries:
        if query.split != partition:
            continue
        results: list[dict[str, Any]] = []
        grade_two = next((item for item in query.qrels if item.grade == 2), None)
        if grade_two is not None:
            page = by_locator[
                (grade_two.locator.document_id, grade_two.locator.locator_start)
            ]
            stable_id = (
                f"{page.document_id}|page|{page.page}|{page.page}|{page.text_sha256}"
            )
            results.append(
                {
                    "stable_locator_id": stable_id,
                    "rank": 1,
                    "portable_score": 0.8,
                    "raw_score": 0.8,
                    "adapter_id": "exact-cosine-v1",
                    "locator": {
                        "document_id": page.document_id,
                        "locator_kind": "page",
                        "locator_start": page.page,
                        "locator_end": page.page,
                    },
                }
            )
        observations.append(
            {
                "query_id": query.query_id,
                "split": partition,
                "category": query.category,
                "threshold": 0.0,
                "results": results,
                "latency_ms": 1,
            }
        )
    identity = cast(dict[str, Any], compatibility["projection"]["exact_reference"])[
        "identity"
    ]
    partition_contract = cast(dict[str, Any], protocol["partitions"])[partition]
    return {
        "schema_version": "mke.dense_candidate_observations.v1",
        "candidate_id": "qwen3-embedding-0.6b-exact-v1",
        "candidate_revision": 1,
        "partition": partition,
        "snapshot": {
            "snapshot_id": partition_contract["snapshot_id"],
            "evidence_count": len(pages),
            "source_text_digest": _digest(source_digests),
            "locator_digest": _digest(stable_ids),
        },
        "projection": {
            "projection_id": partition_contract["projection_id"],
            "adapter_id": "exact-cosine-v1",
            "identity": {
                "adapter_id": "exact-cosine-v1",
                "model_fingerprint": identity["model_fingerprint"],
                "dimension": 1024,
                "row_count": len(pages),
                "locator_digest": _digest(stable_ids),
                "source_text_digest": _digest(source_digests),
                "vector_digest": "sha256:" + ("a" if partition == "development" else "b") * 64,
            },
        },
        "observations": observations,
        "duration_ms": 1,
    }


def _current_runtime_semantics() -> dict[str, Any]:
    chinese = load_chinese_retrieval_protocol(
        ROOT / "tests/fixtures/retrieval-chinese-v1/protocol.json"
    )
    return {
        "results": [
            {
                "query_id": query.query_id,
                "split": query.split,
                "category": query.category,
                "retrieved_locators": [],
                "direct_ranks": [],
                "hard_negative_failure": False,
            }
            for query in chinese.queries
        ]
    }


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()
