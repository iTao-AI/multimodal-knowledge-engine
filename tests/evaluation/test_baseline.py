import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.baseline import (
    BaselineValidationError,
    validate_retrieval_baseline,
)

ARTIFACT = Path("benchmarks/retrieval/retrieval-eval-v1-baseline.json")
MANIFEST = Path("tests/fixtures/retrieval-eval-v1.json")
REPOSITORY = Path(".")


def _artifact_payload() -> dict[str, object]:
    return cast(dict[str, object], json.loads(ARTIFACT.read_text()))


def _write_artifact(tmp_path: Path, payload: dict[str, object]) -> Path:
    artifact = tmp_path / "baseline.json"
    artifact.write_text(json.dumps(payload))
    return artifact


def _validate(path: Path) -> None:
    validate_retrieval_baseline(
        artifact_path=path,
        manifest_path=MANIFEST,
        repository_root=REPOSITORY,
    )


def _wrong_manifest_checksum(payload: dict[str, object]) -> None:
    payload["manifest_sha256"] = "0" * 64


def _wrong_fixture_checksum(payload: dict[str, object]) -> None:
    fixtures = cast(list[dict[str, object]], payload["fixtures"])
    fixtures[0]["sha256"] = "0" * 64


def _wrong_metric_count(metric: dict[str, object]) -> None:
    metric["count"] = 15


def _wrong_metric_sum(metric: dict[str, object]) -> None:
    metric["sum"] = 13.0


def _wrong_metric_value(metric: dict[str, object]) -> None:
    metric["value"] = 0.5


def _unknown_metric_field(metric: dict[str, object]) -> None:
    metric["unexpected"] = True


def _wrong_query_id(result: dict[str, object]) -> None:
    result["query_id"] = "wrong-query"


def _wrong_category(result: dict[str, object]) -> None:
    result["category"] = "out_of_corpus"


def _wrong_retrieved_count(result: dict[str, object]) -> None:
    result["retrieved_locator_count"] = 99


def _unknown_result_field(result: dict[str, object]) -> None:
    result["unexpected"] = True


def test_checked_in_canonical_baseline_is_self_consistent() -> None:
    _validate(ARTIFACT)


def test_validator_rejects_wrong_main_merge_base(tmp_path: Path) -> None:
    payload = _artifact_payload()
    code = cast(dict[str, object], payload["code"])
    code["main_merge_base"] = code["implementation_start"]

    with pytest.raises(
        BaselineValidationError,
        match="code main merge base is not the implementation fork point",
    ):
        _validate(_write_artifact(tmp_path, payload))


def test_validator_rejects_wrong_evaluation_commit_identity(tmp_path: Path) -> None:
    payload = _artifact_payload()
    code = cast(dict[str, object], payload["code"])
    code["evaluation_commit"] = code["main_merge_base"]

    with pytest.raises(
        BaselineValidationError,
        match="evaluation commit does not descend from implementation start",
    ):
        _validate(_write_artifact(tmp_path, payload))


def test_validator_rejects_malformed_environment(tmp_path: Path) -> None:
    payload = _artifact_payload()
    environment = cast(dict[str, object], payload["environment"])
    environment["python"] = "unknown"

    with pytest.raises(BaselineValidationError, match="baseline environment is invalid"):
        _validate(_write_artifact(tmp_path, payload))


def test_validator_rejects_unknown_top_level_fields(tmp_path: Path) -> None:
    payload = _artifact_payload()
    payload["unexpected"] = True

    with pytest.raises(
        BaselineValidationError, match="baseline artifact fields are invalid"
    ):
        _validate(_write_artifact(tmp_path, payload))


@pytest.mark.parametrize(
    ("mutation", "cause"),
    [
        (_wrong_manifest_checksum, "manifest checksum does not match"),
        (
            _wrong_fixture_checksum,
            "fixture provenance does not match manifest and files",
        ),
    ],
)
def test_validator_derives_manifest_and_fixture_provenance(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
    cause: str,
) -> None:
    payload = _artifact_payload()
    mutation(payload)

    with pytest.raises(BaselineValidationError, match=cause):
        _validate(_write_artifact(tmp_path, payload))


@pytest.mark.parametrize(
    "mutation",
    [
        _wrong_metric_count,
        _wrong_metric_sum,
        _wrong_metric_value,
        _unknown_metric_field,
    ],
)
def test_validator_rejects_malformed_metrics(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
) -> None:
    payload = _artifact_payload()
    metrics = cast(dict[str, dict[str, object]], payload["metrics"])
    mutation(metrics["locator_recall_at_1"])

    with pytest.raises(BaselineValidationError, match="baseline metrics are inconsistent"):
        _validate(_write_artifact(tmp_path, payload))


@pytest.mark.parametrize(
    "mutation",
    [
        _wrong_query_id,
        _wrong_category,
        _wrong_retrieved_count,
        _unknown_result_field,
    ],
)
def test_validator_rejects_malformed_results_or_query_identity(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
) -> None:
    payload = _artifact_payload()
    results = cast(list[dict[str, object]], payload["results"])
    mutation(results[0])

    with pytest.raises(
        BaselineValidationError,
        match="baseline results do not match manifest query identity",
    ):
        _validate(_write_artifact(tmp_path, payload))


def test_validator_does_not_compare_current_scores_to_historical_baseline(
    tmp_path: Path,
) -> None:
    payload = _artifact_payload()
    results = cast(list[dict[str, object]], payload["results"])
    result = results[0]
    result.update(
        {
            "retrieved_locator_count": 0,
            "relevant_retrieved_at_1": 0,
            "relevant_retrieved_at_3": 0,
            "relevant_retrieved_at_5": 0,
            "first_relevant_rank": None,
            "ask_status": "insufficient_evidence",
            "retrieved_locators": [],
        }
    )
    metrics = cast(dict[str, dict[str, object]], payload["metrics"])
    metrics["locator_recall_at_1"].update({"value": 0.8125, "sum": 13.0})
    metrics["locator_recall_at_3"].update({"value": 0.875, "sum": 14.0})
    metrics["locator_recall_at_5"].update({"value": 0.875, "sum": 14.0})
    metrics["mrr_at_5"].update({"value": 0.875, "sum": 14.0})
    metrics["answerable_zero_hit_rate"].update({"value": 0.125, "sum": 2.0})
    payload["answerable_misses_at_5"] = [
        "volcano-answerable-01",
        "water-answerable-01",
    ]

    _validate(_write_artifact(tmp_path, payload))
