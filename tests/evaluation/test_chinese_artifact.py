import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.chinese_artifact import (
    ChineseArtifactValidationError,
    record_chinese_artifact,
    validate_chinese_artifact,
)
from mke.evaluation.chinese_report import render_chinese_retrieval_json
from mke.evaluation.chinese_runner import run_chinese_retrieval_evaluation

PROTOCOL = Path("tests/fixtures/retrieval-chinese-v1/protocol.json")
REPOSITORY = Path(".")


def _record(tmp_path: Path) -> tuple[Path, Path]:
    observed = tmp_path / "observed.json"
    observed.write_text(
        render_chinese_retrieval_json(
            run_chinese_retrieval_evaluation(PROTOCOL)
        ),
        encoding="utf-8",
    )
    artifact = tmp_path / "artifact.json"
    record_chinese_artifact(
        observed_path=observed,
        artifact_path=artifact,
        protocol_path=PROTOCOL,
        repository_root=REPOSITORY,
    )
    return artifact, observed


def test_recorded_chinese_artifact_validates_without_reingest(
    tmp_path: Path,
) -> None:
    artifact, observed = _record(tmp_path)

    validate_chinese_artifact(
        artifact_path=artifact,
        observed_path=observed,
        protocol_path=PROTOCOL,
        repository_root=REPOSITORY,
    )

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "mke.retrieval_chinese_baseline.v1"
    assert payload["protocol_id"] == "retrieval-chinese-v1"
    assert payload["documents"] == 5
    assert payload["queries"] == 48
    assert payload["e3b_evidence"][
        "development_answerable_compiled_query_empty_misses"
    ] >= 1
    assert payload["fts5_rank_profile"] == "sqlite_fts5_default_bm25"
    assert "duration_ms" not in payload
    assert set(payload["environment"]) == {"python", "sqlite", "pymupdf"}
    assert payload["source_identity"]["files"]


MUTATIONS: list[Callable[[dict[str, object]], object]] = [
    lambda payload: payload.update({"documents": 4}),
    lambda payload: payload["metrics"]["recall_at_1"].update({"value": 1.0}),  # type: ignore[index]
    lambda payload: payload["results"][0].update({"category": "unanswerable"}),  # type: ignore[index]
    lambda payload: payload["results"][0].update({"compiled_query": '"changed"'}),  # type: ignore[index]
    lambda payload: payload["results"][0]["retrieved"].append(  # type: ignore[index]
        payload["results"][0]["retrieved"][0]  # type: ignore[index]
    ),
    lambda payload: payload["fts5_rank_observations"][0].update(  # type: ignore[index]
        {"score_pairs_sha256": "0" * 64}
    ),
    lambda payload: payload["limitations"].append("unsupported_claim"),  # type: ignore[union-attr]
    lambda payload: payload["source_identity"]["files"][0].update(  # type: ignore[index]
        {"sha256": "0" * 64}
    ),
]


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_artifact_validation_rejects_semantic_or_identity_mutation(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], object],
) -> None:
    artifact, observed = _record(tmp_path)
    payload = cast(
        dict[str, object],
        json.loads(artifact.read_text(encoding="utf-8")),
    )
    mutation(payload)
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ChineseArtifactValidationError):
        validate_chinese_artifact(
            artifact_path=artifact,
            observed_path=observed,
            protocol_path=PROTOCOL,
            repository_root=REPOSITORY,
        )


def test_record_rejects_failed_or_malformed_observation(tmp_path: Path) -> None:
    observed = tmp_path / "observed.json"
    report = json.loads(
        render_chinese_retrieval_json(
            run_chinese_retrieval_evaluation(PROTOCOL)
        )
    )
    report["integrity_status"] = "failed"
    observed.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ChineseArtifactValidationError):
        record_chinese_artifact(
            observed_path=observed,
            artifact_path=tmp_path / "artifact.json",
            protocol_path=PROTOCOL,
            repository_root=REPOSITORY,
        )


def test_validation_accepts_recorded_environment_from_another_ci_runtime(
    tmp_path: Path,
) -> None:
    artifact, observed = _record(tmp_path)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["environment"] = {
        "python": "3.12.0",
        "sqlite": "3.45.1",
        "pymupdf": "1.26.0",
    }
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    validate_chinese_artifact(
        artifact_path=artifact,
        observed_path=observed,
        protocol_path=PROTOCOL,
        repository_root=REPOSITORY,
    )


def test_validation_rejects_malformed_recorded_environment(
    tmp_path: Path,
) -> None:
    artifact, observed = _record(tmp_path)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["environment"]["python"] = "unknown"
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ChineseArtifactValidationError):
        validate_chinese_artifact(
            artifact_path=artifact,
            observed_path=observed,
            protocol_path=PROTOCOL,
            repository_root=REPOSITORY,
        )


def _observed_payload() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(
            render_chinese_retrieval_json(
                run_chinese_retrieval_evaluation(PROTOCOL)
            )
        ),
    )


def _first_miss(payload: dict[str, object]) -> dict[str, object]:
    results = cast(list[dict[str, object]], payload["results"])
    return cast(
        dict[str, object],
        next(item["miss"] for item in results if item["miss"] is not None),
    )


def _mutate_out_of_inventory_locator(payload: dict[str, object]) -> None:
    results = cast(list[dict[str, object]], payload["results"])
    result = next(
        item
        for item in results
        if cast(list[object], item["direct_ranks"])
        and len(cast(list[object], item["retrieved"])) < 10
    )
    cast(list[object], result["retrieved"]).append(
        {
            "locator": {
                "document_id": "copyright-law",
                "locator_kind": "page",
                "locator_start": 1,
                "locator_end": 1,
            },
            "grade": None,
        }
    )


def _mutate_bool_grade(payload: dict[str, object]) -> None:
    results = cast(list[dict[str, object]], payload["results"])
    record = next(
        retrieved
        for result in results
        for retrieved in cast(list[dict[str, object]], result["retrieved"])
        if retrieved["grade"] == 1
    )
    record["grade"] = True


def _mutate_bool_qrel_count(payload: dict[str, object]) -> None:
    results = cast(list[dict[str, object]], payload["results"])
    counts = next(
        cast(dict[str, object], result["qrel_counts"])
        for result in results
        if cast(dict[str, object], result["qrel_counts"])["grade_1"] == 1
    )
    counts["grade_1"] = True


OBSERVED_RERECORD_MUTATIONS: list[
    Callable[[dict[str, object]], object]
] = [
    lambda payload: _first_miss(payload).update(
        {"symptom": "other_observed_miss"}
    ),
    lambda payload: _first_miss(payload).update(
        {"returned_distractor_ranks": [999]}
    ),
    lambda payload: _first_miss(payload).update(
        {"direct_page_clause_coverage": [[True]]}
    ),
    _mutate_out_of_inventory_locator,
    _mutate_bool_grade,
    _mutate_bool_qrel_count,
]


@pytest.mark.parametrize("mutation", OBSERVED_RERECORD_MUTATIONS)
def test_record_rejects_self_consistent_untrusted_observed_report(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], object],
) -> None:
    payload = _observed_payload()
    mutation(payload)
    observed = tmp_path / "observed.json"
    observed.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ChineseArtifactValidationError):
        record_chinese_artifact(
            observed_path=observed,
            artifact_path=tmp_path / "artifact.json",
            protocol_path=PROTOCOL,
            repository_root=REPOSITORY,
        )
