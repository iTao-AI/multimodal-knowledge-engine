"""Four-arm E3-C comparison state without runtime promotion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, cast

from mke.adapters.vector.exact_cosine import EXACT_COSINE_ADAPTER_ID
from mke.embeddings.contracts import CANDIDATE_ID, MODEL_ID, MODEL_REVISION
from mke.evaluation.chinese_protocol import EXPECTED_CATEGORY_COUNTS
from mke.evaluation.dense_threshold import validate_threshold_report

_TARGET_CLASSES = frozenset(
    {"semantic_paraphrase", "multi_condition", "ranking_hard_negative"}
)
_E3A_ARM = "e3a-historical-fts5-baseline"
_E3B_ARM = "cjk-trigram-overlap-v1"
_RUNTIME_ARM = "cjk-active-scan-overlap-v1"


class DenseComparisonError(RuntimeError):
    """Dense comparison integrity or state transition failed."""


@dataclass(frozen=True)
class DenseArmEvidence:
    arm_id: str
    semantic_digest: str


@dataclass(frozen=True)
class DenseComparisonIdentity:
    candidate_id: str
    model_id: str
    model_revision: str
    adapter_id: str


@dataclass(frozen=True)
class DensePartitionObservation:
    query_id: str
    category: str
    current_runtime_missed: bool
    recovered_grade2: bool
    unanswerable_no_hit: bool | None
    hard_negative_failure: bool | None


@dataclass(frozen=True)
class DenseHoldoutEvidence:
    identity: DenseComparisonIdentity
    snapshot_id: str
    projection_id: str
    selected_threshold: float
    observations: tuple[DensePartitionObservation, ...]


@dataclass(frozen=True)
class DenseDevelopmentFreeze:
    development_status: str
    selected_threshold: float | None
    recovered_target_grade2_count: int
    unanswerable_no_hit: float
    hard_negative_failure: float
    arms: tuple[DenseArmEvidence, ...]
    identity: DenseComparisonIdentity
    snapshot_id: str
    projection_id: str


def freeze_dense_development(
    *,
    e3a: DenseArmEvidence,
    e3b: DenseArmEvidence,
    current_runtime_expected_digest: str,
    current_runtime_observed_digest: str,
    threshold_report: dict[str, Any],
    identity: DenseComparisonIdentity,
    snapshot_id: str,
    projection_id: str,
) -> DenseDevelopmentFreeze:
    """Freeze development evidence before any holdout API is reachable."""
    _validate_arm(e3a, expected_id=_E3A_ARM)
    _validate_arm(e3b, expected_id=_E3B_ARM)
    if (
        not current_runtime_expected_digest
        or current_runtime_observed_digest != current_runtime_expected_digest
    ):
        raise DenseComparisonError("current runtime semantics drift")
    _validate_identity(identity)
    _validate_partition_identity(snapshot_id, projection_id)
    try:
        validate_threshold_report(threshold_report)
    except ValueError as error:
        raise DenseComparisonError("development threshold report is invalid") from error

    development_status = threshold_report.get("development_status")
    if development_status not in {"passed", "valid_negative"}:
        raise DenseComparisonError("development threshold status is invalid")
    selected_value = threshold_report.get("selected_threshold")
    if selected_value is not None and type(selected_value) is not float:
        raise DenseComparisonError("development threshold is invalid")
    selected = threshold_report.get("selected")
    if selected is None:
        recovered = 0
        no_hit = 0.0
        hard_failure = 0.0
    elif isinstance(selected, dict):
        selected_data = cast(dict[str, object], selected)
        recovered = _required_int(
            selected_data.get("recovered_target_grade2_count"),
            "development recovery count",
        )
        no_hit = _required_float(
            selected_data.get("unanswerable_no_hit"),
            "development unanswerable no-hit",
        )
        hard_failure = _required_float(
            selected_data.get("hard_negative_failure"),
            "development hard-negative failure",
        )
    else:
        raise DenseComparisonError("development threshold selection is invalid")
    if development_status == "passed" and (
        selected_value is None
        or recovered < 2
        or no_hit < 0.5
        or hard_failure > 0.3
    ):
        raise DenseComparisonError("development gate verdict is invalid")

    return DenseDevelopmentFreeze(
        development_status=development_status,
        selected_threshold=selected_value,
        recovered_target_grade2_count=recovered,
        unanswerable_no_hit=no_hit,
        hard_negative_failure=hard_failure,
        arms=(
            e3a,
            e3b,
            DenseArmEvidence(_RUNTIME_ARM, current_runtime_observed_digest),
            DenseArmEvidence(CANDIDATE_ID, projection_id),
        ),
        identity=identity,
        snapshot_id=snapshot_id,
        projection_id=projection_id,
    )


class DenseComparisonState:
    """One-process latch for the single authorized holdout observation."""

    def __init__(self, *, completion_record_exists: bool = False) -> None:
        self._completion_record_exists = completion_record_exists
        self._holdout_observed = False

    def complete(
        self,
        development: DenseDevelopmentFreeze,
        *,
        holdout_loader: Callable[[], DenseHoldoutEvidence],
    ) -> dict[str, Any]:
        if self._completion_record_exists:
            raise DenseComparisonError("completion record already exists")
        if self._holdout_observed:
            raise DenseComparisonError("holdout already observed")
        if development.development_status != "passed":
            return _completed_negative(development)

        holdout = holdout_loader()
        self._holdout_observed = True
        _validate_holdout_identity(development, holdout)
        summary = _summarize_holdout(holdout.observations)
        eligible = (
            summary["recovered_target_grade2_count"] >= 2
            and summary["unanswerable_no_hit"] >= 0.5
            and summary["hard_negative_failure"] <= 0.142857
        )
        return {
            "schema_version": "mke.dense_comparison_state.v1",
            "arms": [asdict(item) for item in development.arms],
            "development": _development_payload(development),
            "holdout_status": "observed",
            "holdout": summary,
            "candidate_status": "completed",
            "e3d_status": "eligible" if eligible else "not_eligible",
            "runtime_promotion_status": "not_evaluated",
        }


def _completed_negative(development: DenseDevelopmentFreeze) -> dict[str, Any]:
    return {
        "schema_version": "mke.dense_comparison_state.v1",
        "arms": [asdict(item) for item in development.arms],
        "development": _development_payload(development),
        "holdout_status": "not_observed",
        "holdout": None,
        "candidate_status": "completed",
        "e3d_status": "not_eligible",
        "runtime_promotion_status": "not_evaluated",
    }


def _development_payload(development: DenseDevelopmentFreeze) -> dict[str, object]:
    return {
        "development_status": development.development_status,
        "selected_threshold": development.selected_threshold,
        "recovered_target_grade2_count": (
            development.recovered_target_grade2_count
        ),
        "unanswerable_no_hit": development.unanswerable_no_hit,
        "hard_negative_failure": development.hard_negative_failure,
        "snapshot_id": development.snapshot_id,
        "projection_id": development.projection_id,
    }


def _summarize_holdout(
    observations: tuple[DensePartitionObservation, ...],
) -> dict[str, Any]:
    if not observations:
        raise DenseComparisonError("holdout observations are empty")
    seen: set[str] = set()
    recoveries: list[str] = []
    report_only: list[str] = []
    no_hits: list[bool] = []
    hard_failures: list[bool] = []
    for item in observations:
        _validate_observation(item)
        if item.query_id in seen:
            raise DenseComparisonError("holdout query identity is duplicated")
        seen.add(item.query_id)
        if item.recovered_grade2 and item.current_runtime_missed:
            if item.category in _TARGET_CLASSES:
                recoveries.append(item.query_id)
            elif item.category != "unanswerable":
                report_only.append(item.query_id)
        if item.unanswerable_no_hit is not None:
            no_hits.append(item.unanswerable_no_hit)
        if item.hard_negative_failure is not None:
            hard_failures.append(item.hard_negative_failure)
    return {
        "recovered_target_grade2_count": len(recoveries),
        "recovery_ids": sorted(recoveries),
        "report_only_recovery_ids": sorted(report_only),
        "unanswerable_no_hit": _mean_bools(no_hits, empty=1.0),
        "hard_negative_failure": _mean_bools(hard_failures, empty=0.0),
    }


def _validate_observation(item: DensePartitionObservation) -> None:
    if not item.query_id or item.category not in EXPECTED_CATEGORY_COUNTS:
        raise DenseComparisonError("holdout observation identity is invalid")
    if (
        type(item.current_runtime_missed) is not bool
        or type(item.recovered_grade2) is not bool
    ):
        raise DenseComparisonError("holdout observation flags are invalid")
    if item.unanswerable_no_hit is not None and type(item.unanswerable_no_hit) is not bool:
        raise DenseComparisonError("holdout no-hit flag is invalid")
    if (
        item.hard_negative_failure is not None
        and type(item.hard_negative_failure) is not bool
    ):
        raise DenseComparisonError("holdout hard-negative flag is invalid")
    if item.category == "unanswerable" and item.unanswerable_no_hit is None:
        raise DenseComparisonError("unanswerable holdout evidence is incomplete")


def _validate_holdout_identity(
    development: DenseDevelopmentFreeze,
    holdout: DenseHoldoutEvidence,
) -> None:
    if (
        holdout.identity != development.identity
        or holdout.selected_threshold != development.selected_threshold
        or holdout.snapshot_id == development.snapshot_id
        or holdout.projection_id == development.projection_id
    ):
        raise DenseComparisonError("holdout identity drift")
    _validate_identity(holdout.identity)
    _validate_partition_identity(holdout.snapshot_id, holdout.projection_id)


def _validate_identity(identity: DenseComparisonIdentity) -> None:
    if identity != DenseComparisonIdentity(
        candidate_id=CANDIDATE_ID,
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
        adapter_id=EXACT_COSINE_ADAPTER_ID,
    ):
        raise DenseComparisonError("dense comparison identity is invalid")


def _validate_arm(arm: DenseArmEvidence, *, expected_id: str) -> None:
    if arm.arm_id != expected_id or not arm.semantic_digest:
        raise DenseComparisonError("historical arm identity is invalid")


def _validate_partition_identity(snapshot_id: str, projection_id: str) -> None:
    if not snapshot_id or not projection_id or snapshot_id == projection_id:
        raise DenseComparisonError("partition identity is invalid")


def _required_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise DenseComparisonError(f"{label} is invalid")
    return value


def _required_float(value: object, label: str) -> float:
    if type(value) is not float or not 0.0 <= value <= 1.0:
        raise DenseComparisonError(f"{label} is invalid")
    return value


def _mean_bools(values: list[bool], *, empty: float) -> float:
    if not values:
        return empty
    return round(sum(values) / len(values), 6)
