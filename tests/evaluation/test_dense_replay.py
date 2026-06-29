from __future__ import annotations

from copy import deepcopy

import pytest

from mke.evaluation.dense_replay import (
    DenseReplayValidationError,
    validate_dense_cache_replay,
)

from .test_dense_artifact import synthetic_artifact, synthetic_candidate_report


def test_cache_replay_accepts_exact_partition_regeneration() -> None:
    validate_dense_cache_replay(
        synthetic_artifact(),
        partition_runner=synthetic_candidate_report,
    )


def test_cache_replay_rejects_order_and_true_score_delta() -> None:
    artifact = synthetic_artifact()

    def changed_score(partition: str):
        report = synthetic_candidate_report(partition)
        report["observations"][0]["results"][0]["portable_score"] += 0.000011
        return report

    with pytest.raises(DenseReplayValidationError):
        validate_dense_cache_replay(artifact, partition_runner=changed_score)

    def changed_order(partition: str):
        report = synthetic_candidate_report(partition)
        report["observations"].reverse()
        return report

    with pytest.raises(DenseReplayValidationError):
        validate_dense_cache_replay(artifact, partition_runner=changed_order)


def test_cache_replay_rejects_coordinated_observation_and_verdict_replacement() -> None:
    artifact = deepcopy(synthetic_artifact())
    artifact["development_candidate"]["observations"][0]["results"][0][
        "portable_score"
    ] = 0.7
    artifact["development_candidate"]["observations"][0]["results"][0][
        "raw_score"
    ] = 0.7

    with pytest.raises(DenseReplayValidationError):
        validate_dense_cache_replay(
            artifact,
            partition_runner=synthetic_candidate_report,
        )
