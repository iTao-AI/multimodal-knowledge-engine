"""Cache-ready replay oracle for E3-C dense observations."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any, cast


class DenseReplayValidationError(ValueError):
    """Recorded dense observations differ from cache-ready inference."""

    def __init__(self) -> None:
        super().__init__("dense comparison cache replay is invalid")


def validate_dense_cache_replay(
    artifact: dict[str, Any],
    *,
    partition_runner: Callable[[str], dict[str, Any]],
) -> None:
    """Replay every recorded partition without permitting a download fallback."""
    try:
        for partition in ("development", "holdout"):
            recorded_value = artifact.get(f"{partition}_candidate")
            if recorded_value is None:
                if partition == "holdout":
                    continue
                raise DenseReplayValidationError
            recorded = _object(recorded_value)
            replayed = _canonical_replay(partition_runner(partition))
            _compare_candidate(recorded, replayed)
    except DenseReplayValidationError:
        raise
    except Exception as error:
        raise DenseReplayValidationError from error


def _canonical_replay(report: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(report)
    canonical.pop("duration_ms", None)
    raw_observations = canonical.get("observations")
    if not isinstance(raw_observations, list):
        raise DenseReplayValidationError
    observations: list[dict[str, Any]] = []
    for raw in cast(list[object], raw_observations):
        item = dict(_object(raw))
        item.pop("latency_ms", None)
        observations.append(item)
    canonical["observations"] = observations
    return canonical


def _compare_candidate(recorded: dict[str, Any], replayed: dict[str, Any]) -> None:
    for field in (
        "schema_version",
        "candidate_id",
        "candidate_revision",
        "partition",
        "snapshot",
        "projection",
    ):
        if recorded.get(field) != replayed.get(field):
            raise DenseReplayValidationError
    recorded_observations = recorded.get("observations")
    replayed_observations = replayed.get("observations")
    if not isinstance(recorded_observations, list) or not isinstance(
        replayed_observations, list
    ):
        raise DenseReplayValidationError
    recorded_values = cast(list[object], recorded_observations)
    replayed_values = cast(list[object], replayed_observations)
    if len(recorded_values) != len(replayed_values):
        raise DenseReplayValidationError
    for recorded_raw, replayed_raw in zip(
        recorded_values,
        replayed_values,
        strict=True,
    ):
        left = _object(recorded_raw)
        right = _object(replayed_raw)
        for field in ("query_id", "split", "category", "threshold"):
            if left.get(field) != right.get(field):
                raise DenseReplayValidationError
        _compare_results(left.get("results"), right.get("results"))


def _compare_results(recorded: object, replayed: object) -> None:
    if not isinstance(recorded, list) or not isinstance(replayed, list):
        raise DenseReplayValidationError
    recorded_values = cast(list[object], recorded)
    replayed_values = cast(list[object], replayed)
    if len(recorded_values) != len(replayed_values):
        raise DenseReplayValidationError
    for left_raw, right_raw in zip(
        recorded_values, replayed_values, strict=True
    ):
        left = _object(left_raw)
        right = _object(right_raw)
        for field in ("stable_locator_id", "rank", "adapter_id", "locator"):
            if left.get(field) != right.get(field):
                raise DenseReplayValidationError
        for field in ("portable_score", "raw_score"):
            left_score = left.get(field)
            right_score = right.get(field)
            if (
                type(left_score) is not float
                or type(right_score) is not float
                or not math.isfinite(left_score)
                or not math.isfinite(right_score)
                or abs(left_score - right_score) > 1e-5
            ):
                raise DenseReplayValidationError


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DenseReplayValidationError
    return cast(dict[str, Any], value)
