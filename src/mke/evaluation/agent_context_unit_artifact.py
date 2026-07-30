"""Pure development-artifact construction and retained validation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, cast

from mke.evaluation.agent_context_unit_grading import (
    CaseMetrics,
    DevelopmentGradingResult,
    MechanismAggregateMetrics,
    MechanismCaseObservation,
    ObservedRange,
    ObservedRankedCandidate,
    ResidualGateSet,
    SealedMechanismObservation,
    build_development_grading_result,
    derive_residual_gates,
    grade_context_mechanisms,
    seal_mechanism_observation,
)
from mke.evaluation.agent_context_unit_grading_protocol import (
    AgentContextDevelopmentGradingPayload,
    parse_agent_context_unit_development_grading_payload,
    portable_agent_context_unit_development_grading_payload,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
_TOP_FIELDS = {
    "authority",
    "baseline_observation",
    "classifications",
    "content_digest",
    "holdout_status",
    "grading",
    "grading_authority",
    "integrity_status",
    "limitations",
    "mechanism_statuses",
    "nonclaims",
    "residual_gates",
    "runtime_promotion_status",
    "schema_version",
    "stage_outcome",
    "status",
    "workspace_equality",
    "workspace_observations",
}
_AUTHORITY_FIELDS = {
    "baseline_artifact_sha256",
    "baseline_content_digest",
    "evaluator_source_sha256",
    "fixture_sha256",
    "protocol_sha256",
    "runtime_profile_sha256",
}
_MECHANISM_STATUSES = {
    "candidate_failed",
    "candidate_qualified",
    "mechanism_ambiguous",
    "not_evaluated",
    "not_observed_under_protocol",
}


@dataclass(frozen=True)
class DevelopmentArtifactAuthority:
    protocol_sha256: str
    evaluator_source_sha256: str
    fixture_sha256: str
    baseline_artifact_sha256: str
    baseline_content_digest: str
    runtime_profile_sha256: str

    def __post_init__(self) -> None:
        if any(_SHA256.fullmatch(value) is None for value in asdict(self).values()):
            raise ValueError("development artifact authority is invalid")


def build_agent_context_unit_development_artifact(
    *,
    authority: DevelopmentArtifactAuthority,
    grading_payload: AgentContextDevelopmentGradingPayload,
    baseline_observation: SealedMechanismObservation,
    workspace_a: tuple[SealedMechanismObservation, ...],
    workspace_b: tuple[SealedMechanismObservation, ...],
    gates: ResidualGateSet,
    grading: DevelopmentGradingResult,
    limitations: tuple[str, ...],
    nonclaims: tuple[str, ...],
) -> bytes:
    if type(authority) is not DevelopmentArtifactAuthority:
        raise ValueError("development artifact authority is invalid")
    observations_a = _portable_observation_inventory(workspace_a)
    observations_b = _portable_observation_inventory(workspace_b)
    if observations_a != observations_b:
        raise ValueError("development artifact workspace equality is invalid")
    grading_authority = portable_agent_context_unit_development_grading_payload(
        grading_payload
    )
    baseline = _portable_observation_inventory((baseline_observation,))[0]
    by_mechanism = {item.mechanism_id: item for item in workspace_a}
    try:
        rebuilt_gates = derive_residual_gates(
            grading_payload,
            o0_artifact_sha256=authority.baseline_artifact_sha256,
            o0=baseline_observation,
            o1=by_mechanism[grading_payload.mechanism_ids["o1"]],
            o2=by_mechanism[grading_payload.mechanism_ids["o2"]],
        )
        rebuilt_grading = grade_context_mechanisms(
            grading_payload,
            rebuilt_gates,
            baseline_observation=baseline_observation,
            o0_artifact_sha256=authority.baseline_artifact_sha256,
            workspace_a=workspace_a,
            workspace_b=workspace_b,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("development artifact grading is invalid") from error
    if gates != rebuilt_gates:
        raise ValueError("development artifact residual gates are invalid")
    if grading != rebuilt_grading:
        raise ValueError("development artifact grading is invalid")
    if (
        type(grading) is not DevelopmentGradingResult
        or _SHA256.fullmatch(grading.grading_digest) is None
        or not grading.deterministic_equality
        or type(limitations) is not tuple
        or not limitations
        or type(nonclaims) is not tuple
        or not nonclaims
        or any(type(item) is not str or not item for item in (*limitations, *nonclaims))
        or len(set(limitations)) != len(limitations)
        or len(set(nonclaims)) != len(nonclaims)
        or "no_runtime_promotion" not in nonclaims
    ):
        raise ValueError("development artifact grading is invalid")
    workspace_sha = _digest(observations_a)
    record: dict[str, Any] = {
        "authority": asdict(authority),
        "baseline_observation": baseline,
        "classifications": list(grading.classifications),
        "holdout_status": "not_evaluated",
        "grading": _portable_grading(grading),
        "grading_authority": grading_authority,
        "integrity_status": "passed",
        "limitations": list(limitations),
        "mechanism_statuses": dict(grading.mechanism_statuses),
        "nonclaims": list(nonclaims),
        "residual_gates": _portable_gates(gates),
        "runtime_promotion_status": "not_evaluated",
        "schema_version": "mke.agent_context_unit_development.v2",
        "stage_outcome": _stage_outcome(grading.mechanism_statuses),
        "status": "passed",
        "workspace_equality": {
            "equal": True,
            "grading_digest": grading.grading_digest,
            "workspace_a_sha256": workspace_sha,
            "workspace_b_sha256": workspace_sha,
        },
        "workspace_observations": {
            "workspace_a": observations_a,
            "workspace_b": observations_b,
        },
    }
    record["content_digest"] = development_artifact_content_digest(record)
    content = _canonical_bytes(record)
    if len(content) > _MAX_ARTIFACT_BYTES:
        raise ValueError("development artifact capacity is invalid")
    validate_agent_context_unit_development_artifact(content)
    return content


def validate_agent_context_unit_development_artifact(
    content: bytes,
) -> dict[str, Any]:
    if type(content) is not bytes or len(content) > _MAX_ARTIFACT_BYTES:
        raise ValueError("development artifact capacity is invalid")
    if not content.endswith(b"\n") or content.count(b"\n") != 1:
        raise ValueError("development artifact encoding is invalid")
    try:
        value: object = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("development artifact encoding is invalid") from error
    if not isinstance(value, dict):
        raise ValueError("development artifact field set is invalid")
    record = cast(dict[str, Any], value)
    if set(record) != _TOP_FIELDS:
        raise ValueError("development artifact field set is invalid")
    if (
        record["schema_version"] != "mke.agent_context_unit_development.v2"
        or record["status"] != "passed"
        or record["integrity_status"] != "passed"
        or record["holdout_status"] != "not_evaluated"
        or record["runtime_promotion_status"] != "not_evaluated"
    ):
        raise ValueError("development artifact status is invalid")
    authority = _mapping(record["authority"], _AUTHORITY_FIELDS, "authority")
    if any(
        not isinstance(value, str) or _SHA256.fullmatch(value) is None
        for value in authority.values()
    ):
        raise ValueError("development artifact authority is invalid")
    try:
        grading_payload = parse_agent_context_unit_development_grading_payload(
            record["grading_authority"]
        )
    except ValueError as error:
        raise ValueError("development artifact grading authority is invalid") from error
    baseline_records, baseline_observations = _validate_portable_observation_inventory(
        [record["baseline_observation"]]
    )
    baseline_observation = baseline_observations[0]
    if baseline_observation.mechanism_id != grading_payload.mechanism_ids["o0"]:
        raise ValueError("development artifact baseline observation is invalid")
    observations = _mapping(
        record["workspace_observations"],
        {"workspace_a", "workspace_b"},
        "workspace observations",
    )
    a, typed_a = _validate_portable_observation_inventory(
        observations["workspace_a"]
    )
    b, typed_b = _validate_portable_observation_inventory(
        observations["workspace_b"]
    )
    equality = _mapping(
        record["workspace_equality"],
        {
            "equal",
            "grading_digest",
            "workspace_a_sha256",
            "workspace_b_sha256",
        },
        "workspace equality",
    )
    a_digest = _digest(a)
    b_digest = _digest(b)
    if (
        equality["equal"] is not True
        or a != b
        or equality["workspace_a_sha256"] != a_digest
        or equality["workspace_b_sha256"] != b_digest
        or a_digest != b_digest
        or not isinstance(equality["grading_digest"], str)
        or _SHA256.fullmatch(equality["grading_digest"]) is None
    ):
        raise ValueError("development artifact workspace equality is invalid")
    by_mechanism = {item.mechanism_id: item for item in typed_a}
    try:
        rebuilt_gates = derive_residual_gates(
            grading_payload,
            o0_artifact_sha256=cast(str, authority["baseline_artifact_sha256"]),
            o0=baseline_observation,
            o1=by_mechanism[grading_payload.mechanism_ids["o1"]],
            o2=by_mechanism[grading_payload.mechanism_ids["o2"]],
        )
        rebuilt_grading = grade_context_mechanisms(
            grading_payload,
            rebuilt_gates,
            baseline_observation=baseline_observation,
            o0_artifact_sha256=cast(str, authority["baseline_artifact_sha256"]),
            workspace_a=typed_a,
            workspace_b=typed_b,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("development artifact grading is invalid") from error
    gates = _validate_portable_gates(record["residual_gates"], rebuilt_gates)
    grading = _validate_portable_grading(record["grading"])
    if grading != rebuilt_grading:
        raise ValueError("development artifact grading is invalid")
    statuses = _mapping(
        record["mechanism_statuses"],
        {"o1", "o2", "o3", "o4", "o5"},
        "mechanism statuses",
    )
    if any(
        not isinstance(item, str) or item not in _MECHANISM_STATUSES for item in statuses.values()
    ):
        raise ValueError("development artifact mechanism statuses are invalid")
    classifications = _string_list(record["classifications"], "classifications")
    if (
        dict(grading.mechanism_statuses) != statuses
        or tuple(grading.classifications) != classifications
        or equality["grading_digest"] != grading.grading_digest
    ):
        raise ValueError("development artifact grading is invalid")
    for gate_name in ("o3", "o4", "o5"):
        enabled = getattr(gates, gate_name).enabled
        if not enabled and statuses[gate_name] != "not_evaluated":
            raise ValueError("development artifact mechanism statuses are invalid")
    limitations = _string_list(record["limitations"], "limitations")
    nonclaims = _string_list(record["nonclaims"], "nonclaims")
    if (
        not limitations
        or "no_runtime_promotion" not in nonclaims
        or not classifications
        or record["stage_outcome"] != _stage_outcome(statuses)
        or record["content_digest"] != development_artifact_content_digest(record)
        or _canonical_bytes(record) != content
        or baseline_records[0] != record["baseline_observation"]
    ):
        raise ValueError("development artifact semantic authority is invalid")
    return record


def validate_agent_context_unit_development_artifact_live(
    content: bytes,
    *,
    authority: DevelopmentArtifactAuthority,
) -> dict[str, Any]:
    record = validate_agent_context_unit_development_artifact(content)
    if type(authority) is not DevelopmentArtifactAuthority or record["authority"] != asdict(
        authority
    ):
        raise ValueError("development artifact strict-live authority is invalid")
    return record


def development_artifact_content_digest(record: dict[str, Any]) -> str:
    payload = dict(record)
    payload.pop("content_digest", None)
    return _digest(payload)


def _portable_observation_inventory(
    observations: tuple[SealedMechanismObservation, ...],
) -> list[dict[str, Any]]:
    if (
        type(observations) is not tuple
        or not observations
        or any(type(item) is not SealedMechanismObservation for item in observations)
    ):
        raise ValueError("development artifact observation inventory is invalid")
    mechanisms = tuple(item.mechanism_id for item in observations)
    if len(set(mechanisms)) != len(mechanisms):
        raise ValueError("development artifact observation inventory is invalid")
    result: list[dict[str, Any]] = []
    for item in sorted(observations, key=lambda entry: entry.mechanism_id.encode()):
        if (
            _SHA256.fullmatch(item.portable_sha256) is None
            or item.portable_sha256 != hashlib.sha256(item.portable_bytes).hexdigest()
        ):
            raise ValueError("development artifact observation inventory is invalid")
        portable: object = json.loads(item.portable_bytes)
        result.append(
            {
                "mechanism_id": item.mechanism_id,
                "portable": portable,
                "portable_sha256": item.portable_sha256,
            }
        )
    return result


def _validate_portable_observation_inventory(
    value: object,
) -> tuple[list[dict[str, Any]], tuple[SealedMechanismObservation, ...]]:
    if not isinstance(value, list) or not value:
        raise ValueError("development artifact observation inventory is invalid")
    items = cast(list[object], value)
    result: list[dict[str, Any]] = []
    typed_result: list[SealedMechanismObservation] = []
    for value_item in items:
        item = _mapping(
            value_item,
            {"mechanism_id", "portable", "portable_sha256"},
            "observation",
        )
        if (
            not isinstance(item["mechanism_id"], str)
            or not item["mechanism_id"]
            or not isinstance(item["portable"], dict)
            or not isinstance(item["portable_sha256"], str)
            or item["portable_sha256"] != _digest(cast(dict[str, Any], item["portable"]))
        ):
            raise ValueError("development artifact observation inventory is invalid")
        sealed = _parse_portable_observation(cast(dict[str, Any], item["portable"]))
        if (
            sealed.mechanism_id != item["mechanism_id"]
            or sealed.portable_sha256 != item["portable_sha256"]
        ):
            raise ValueError("development artifact observation inventory is invalid")
        result.append(item)
        typed_result.append(sealed)
    mechanism_ids = tuple(item["mechanism_id"] for item in result)
    if len(set(mechanism_ids)) != len(mechanism_ids) or mechanism_ids != tuple(
        sorted(mechanism_ids, key=str.encode)
    ):
        raise ValueError("development artifact observation inventory is invalid")
    return result, tuple(typed_result)


def _parse_portable_observation(
    portable: dict[str, Any],
) -> SealedMechanismObservation:
    if (
        set(portable) != {"cases", "mechanism_id", "schema_version"}
        or portable["schema_version"] != "mke.agent_context_unit_mechanism_observation.v1"
    ):
        raise ValueError("development artifact observation inventory is invalid")
    mechanism_id = portable["mechanism_id"]
    cases_value = portable["cases"]
    if not isinstance(mechanism_id, str) or not mechanism_id or not isinstance(cases_value, list):
        raise ValueError("development artifact observation inventory is invalid")
    cases: list[MechanismCaseObservation] = []
    case_fields = {
        "candidate_count",
        "context_attribution_unique",
        "context_ranges",
        "delivered_ranges",
        "delivered_utf8_bytes",
        "exact_read_complete",
        "mechanism_id",
        "output_complete",
        "provenance_exact",
        "query_id",
        "query_terms",
        "rank_profile_id",
        "ranked",
        "retrieval_text",
        "route",
        "selected_stable_identities",
        "unique_parent_count",
    }
    for case_value in cast(list[object], cases_value):
        case = _mapping(case_value, case_fields, "observation case")
        query_terms = _string_tuple_nonempty(case["query_terms"], "query terms")
        selected = _string_tuple_allow_empty(
            case["selected_stable_identities"], "selected identities"
        )
        ranked_value = case["ranked"]
        if not isinstance(ranked_value, list):
            raise ValueError("development artifact observation inventory is invalid")
        ranked: list[ObservedRankedCandidate] = []
        for ranked_item in cast(list[object], ranked_value):
            row = _mapping(
                ranked_item,
                {
                    "authority_range",
                    "parent_collapsed_rank",
                    "rank",
                    "stable_identity",
                },
                "ranked candidate",
            )
            ranked.append(
                ObservedRankedCandidate(
                    stable_identity=row["stable_identity"],
                    rank=row["rank"],
                    parent_collapsed_rank=row["parent_collapsed_rank"],
                    authority_range=_parse_observed_range(row["authority_range"]),
                )
            )
        delivered = _parse_observed_ranges(case["delivered_ranges"])
        context = _parse_observed_ranges(case["context_ranges"])
        try:
            cases.append(
                MechanismCaseObservation(
                    query_id=case["query_id"],
                    mechanism_id=case["mechanism_id"],
                    route=case["route"],
                    rank_profile_id=case["rank_profile_id"],
                    query_terms=query_terms,
                    retrieval_text=case["retrieval_text"],
                    candidate_count=case["candidate_count"],
                    unique_parent_count=case["unique_parent_count"],
                    ranked=tuple(ranked),
                    selected_stable_identities=selected,
                    delivered_ranges=delivered,
                    context_ranges=context,
                    delivered_utf8_bytes=case["delivered_utf8_bytes"],
                    context_attribution_unique=case["context_attribution_unique"],
                    exact_read_complete=case["exact_read_complete"],
                    output_complete=case["output_complete"],
                    provenance_exact=case["provenance_exact"],
                )
            )
        except (TypeError, ValueError) as error:
            raise ValueError("development artifact observation inventory is invalid") from error
    return seal_mechanism_observation(mechanism_id, tuple(cases))


def _parse_observed_ranges(value: object) -> tuple[ObservedRange, ...]:
    if not isinstance(value, list):
        raise ValueError("development artifact observation inventory is invalid")
    return tuple(_parse_observed_range(item) for item in cast(list[object], value))


def _parse_observed_range(value: object) -> ObservedRange:
    record = _mapping(
        value,
        {
            "component_kind",
            "end_utf8_byte",
            "locator_end",
            "locator_kind",
            "locator_start",
            "origin_evidence_ref",
            "source_content_fingerprint",
            "start_utf8_byte",
        },
        "observed range",
    )
    try:
        return ObservedRange(**record)
    except (TypeError, ValueError) as error:
        raise ValueError("development artifact observation inventory is invalid") from error


def _portable_gates(gates: ResidualGateSet) -> dict[str, Any]:
    return {
        "evidence": asdict(gates.evidence),
        "gate_digest": gates.gate_digest,
        "o3": asdict(gates.o3),
        "o4": asdict(gates.o4),
        "o5": asdict(gates.o5),
    }


def _portable_grading(
    grading: DevelopmentGradingResult,
) -> dict[str, Any]:
    return {
        "aggregate_metrics": [asdict(item) for item in grading.aggregate_metrics],
        "case_metrics": [asdict(item) for item in grading.case_metrics],
        "classifications": list(grading.classifications),
        "deterministic_equality": grading.deterministic_equality,
        "grading_digest": grading.grading_digest,
        "mechanism_statuses": dict(grading.mechanism_statuses),
    }


def _validate_portable_grading(value: object) -> DevelopmentGradingResult:
    record = _mapping(
        value,
        {
            "aggregate_metrics",
            "case_metrics",
            "classifications",
            "deterministic_equality",
            "grading_digest",
            "mechanism_statuses",
        },
        "grading",
    )
    metrics_value = record["case_metrics"]
    aggregate_value = record["aggregate_metrics"]
    if not isinstance(metrics_value, list) or not isinstance(aggregate_value, list):
        raise ValueError("development artifact grading is invalid")
    metrics: list[CaseMetrics] = []
    metric_fields = {
        "candidate_expansion_ratio_hex",
        "component_attribution",
        "context_attribution_unique",
        "context_only_match_count",
        "current_success_regression",
        "delivery_recall",
        "exact_read_recovery",
        "hard_negative_regression",
        "mechanism_id",
        "output_completeness",
        "parent_collapsed_rank",
        "provenance_exactness",
        "query_id",
        "rank_at_1",
        "rank_at_10",
        "rank_at_3",
        "rank_at_5",
        "raw_rank",
        "required_role_coverage",
        "required_span_count",
        "route_exact",
        "selection_recall",
        "token_presence",
        "useful_span_density_hex",
    }
    for item in cast(list[object], metrics_value):
        metric = _mapping(item, metric_fields, "case metric")
        roles = _string_tuple_allow_empty(metric["required_role_coverage"], "required roles")
        components = _string_tuple_allow_empty(
            metric["component_attribution"], "component attribution"
        )
        typed = dict(metric)
        typed["required_role_coverage"] = roles
        typed["component_attribution"] = components
        try:
            metrics.append(CaseMetrics(**typed))
        except (TypeError, ValueError) as error:
            raise ValueError("development artifact grading is invalid") from error
    aggregate_fields = {
        "comparable_query_count",
        "mechanism_id",
        "mrr_at_5_hex",
        "ndcg_at_10_hex",
        "recall_at_1_hex",
        "recall_at_3_hex",
        "recall_at_5_hex",
    }
    recorded_aggregates: list[MechanismAggregateMetrics] = []
    for item in cast(list[object], aggregate_value):
        aggregate = _mapping(item, aggregate_fields, "aggregate metric")
        try:
            recorded_aggregates.append(MechanismAggregateMetrics(**aggregate))
        except (TypeError, ValueError) as error:
            raise ValueError("development artifact grading is invalid") from error
    classifications = _string_list(record["classifications"], "grading classifications")
    statuses = _mapping(
        record["mechanism_statuses"],
        {"o1", "o2", "o3", "o4", "o5"},
        "grading mechanism statuses",
    )
    if (
        type(record["deterministic_equality"]) is not bool
        or record["deterministic_equality"] is not True
        or not isinstance(record["grading_digest"], str)
    ):
        raise ValueError("development artifact grading is invalid")
    try:
        result = build_development_grading_result(
            case_metrics=tuple(metrics),
            classifications=classifications,
            mechanism_statuses={key: cast(str, item) for key, item in statuses.items()},
            deterministic_equality=True,
        )
    except (TypeError, ValueError) as error:
        raise ValueError("development artifact grading is invalid") from error
    if result.grading_digest != record["grading_digest"]:
        raise ValueError("development artifact grading is invalid")
    if result.aggregate_metrics != tuple(recorded_aggregates):
        raise ValueError("development artifact grading is invalid")
    return result


def _validate_portable_gates(
    value: object,
    expected: ResidualGateSet,
) -> ResidualGateSet:
    record = _mapping(
        value,
        {"evidence", "gate_digest", "o3", "o4", "o5"},
        "residual gates",
    )
    if (
        type(expected) is not ResidualGateSet
        or _digest(_portable_gates(expected)) != _digest(record)
    ):
        raise ValueError("development artifact residual gates are invalid")
    return expected


def _stage_outcome(statuses: dict[str, str]) -> str:
    values = set(statuses.values())
    if "mechanism_ambiguous" in values:
        return "mechanism_ambiguous"
    if "candidate_qualified" in values:
        return "candidate_qualified"
    if values <= {"not_evaluated", "not_observed_under_protocol"}:
        return "not_observed_under_protocol"
    return "candidate_failed"


def _mapping(value: object, fields: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"development artifact {name} is invalid")
    mapping = cast(dict[object, object], value)
    if set(mapping) != fields:
        raise ValueError(f"development artifact {name} is invalid")
    return cast(dict[str, Any], value)


def _string_list(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"development artifact {name} is invalid")
    items = cast(list[object], value)
    if not items or any(not isinstance(item, str) or not item for item in items):
        raise ValueError(f"development artifact {name} is invalid")
    strings = tuple(cast(str, item) for item in items)
    if len(set(strings)) != len(strings):
        raise ValueError(f"development artifact {name} is invalid")
    return strings


def _string_tuple_allow_empty(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"development artifact {name} is invalid")
    items = cast(list[object], value)
    if any(not isinstance(item, str) or not item for item in items):
        raise ValueError(f"development artifact {name} is invalid")
    strings = tuple(cast(str, item) for item in items)
    if len(set(strings)) != len(strings):
        raise ValueError(f"development artifact {name} is invalid")
    return strings


def _string_tuple_nonempty(value: object, name: str) -> tuple[str, ...]:
    result = _string_tuple_allow_empty(value, name)
    if not result:
        raise ValueError(f"development artifact {name} is invalid")
    return result


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()
