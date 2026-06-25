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
