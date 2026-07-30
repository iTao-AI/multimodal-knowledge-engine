"""Pure residual-gate derivation and grading for context mechanism contrasts."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from typing import Literal

from mke.evaluation.agent_context_unit_grading_protocol import (
    AgentContextDevelopmentGradingPayload,
    AgentContextRequiredSpan,
)

_PREFIXED_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_BARE_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MECHANISM_BY_GATE = {
    "o3": "source-context-index-v1",
    "o4": "source-context-delivery-v1",
    "o5": "adjacent-page-assembly-v1",
}
_STATUS_INVENTORY = {
    "candidate_failed",
    "candidate_qualified",
    "mechanism_ambiguous",
    "not_observed_under_protocol",
}


@dataclass(frozen=True)
class ResidualGateEvidence:
    o0_artifact_sha256: str
    o0_observation_sha256: str
    o1_observation_sha256: str
    o2_observation_sha256: str
    failed_control_query_ids: tuple[str, ...]
    o3_residual_query_ids: tuple[str, ...]
    o4_residual_query_ids: tuple[str, ...]
    o5_preregistered_query_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if any(
            _BARE_SHA256.fullmatch(value) is None
            for value in (
                self.o0_artifact_sha256,
                self.o0_observation_sha256,
                self.o1_observation_sha256,
                self.o2_observation_sha256,
            )
        ) or any(
            type(value) is not tuple
            or tuple(sorted(value, key=str.encode)) != value
            or len(set(value)) != len(value)
            or any(type(item) is not str or not item for item in value)
            for value in (
                self.failed_control_query_ids,
                self.o3_residual_query_ids,
                self.o4_residual_query_ids,
                self.o5_preregistered_query_ids,
            )
        ):
            raise ValueError("residual gate evidence is invalid")


@dataclass(frozen=True)
class ResidualGateDecision:
    mechanism_id: str
    enabled: bool
    reason: str


@dataclass(frozen=True)
class ResidualGateSet:
    evidence: ResidualGateEvidence
    o3: ResidualGateDecision
    o4: ResidualGateDecision
    o5: ResidualGateDecision
    gate_digest: str


@dataclass(frozen=True)
class ObservedRange:
    source_content_fingerprint: str
    locator_kind: Literal["page"]
    locator_start: int
    locator_end: int
    start_utf8_byte: int
    end_utf8_byte: int
    origin_evidence_ref: str
    component_kind: str

    def __post_init__(self) -> None:
        if (
            _PREFIXED_SHA256.fullmatch(self.source_content_fingerprint) is None
            or self.locator_kind != "page"
            or type(self.locator_start) is not int
            or self.locator_start < 1
            or type(self.locator_end) is not int
            or self.locator_end != self.locator_start
            or type(self.start_utf8_byte) is not int
            or self.start_utf8_byte < 0
            or type(self.end_utf8_byte) is not int
            or self.end_utf8_byte <= self.start_utf8_byte
            or _PREFIXED_SHA256.fullmatch(self.origin_evidence_ref) is None
            or type(self.component_kind) is not str
            or not self.component_kind
        ):
            raise ValueError("observed range authority is invalid")


@dataclass(frozen=True)
class ObservedRankedCandidate:
    stable_identity: str
    rank: int
    parent_collapsed_rank: int
    authority_range: ObservedRange

    def __post_init__(self) -> None:
        if (
            _PREFIXED_SHA256.fullmatch(self.stable_identity) is None
            or type(self.rank) is not int
            or self.rank < 1
            or type(self.parent_collapsed_rank) is not int
            or self.parent_collapsed_rank < 1
            or type(self.authority_range) is not ObservedRange
        ):
            raise ValueError("ranked candidate authority is invalid")


@dataclass(frozen=True)
class MechanismCaseObservation:
    query_id: str
    mechanism_id: str
    route: Literal["fts", "cjk"]
    rank_profile_id: str
    query_terms: tuple[str, ...]
    retrieval_text: str
    candidate_count: int
    unique_parent_count: int
    ranked: tuple[ObservedRankedCandidate, ...]
    selected_stable_identities: tuple[str, ...]
    delivered_ranges: tuple[ObservedRange, ...]
    context_ranges: tuple[ObservedRange, ...]
    delivered_utf8_bytes: int
    context_attribution_unique: bool
    output_complete: bool
    exact_read_complete: bool
    provenance_exact: bool

    def __post_init__(self) -> None:
        ranked_ids = tuple(item.stable_identity for item in self.ranked)
        ranks = tuple(item.rank for item in self.ranked)
        if (
            not self.query_id
            or not self.mechanism_id
            or self.route not in {"fts", "cjk"}
            or not self.rank_profile_id
            or type(self.query_terms) is not tuple
            or not self.query_terms
            or any(type(term) is not str or not term for term in self.query_terms)
            or type(self.retrieval_text) is not str
            or type(self.candidate_count) is not int
            or self.candidate_count < len(self.ranked)
            or type(self.unique_parent_count) is not int
            or not 0 <= self.unique_parent_count <= self.candidate_count
            or type(self.ranked) is not tuple
            or any(type(item) is not ObservedRankedCandidate for item in self.ranked)
            or ranks != tuple(range(1, len(ranks) + 1))
            or len(set(ranked_ids)) != len(ranked_ids)
            or type(self.selected_stable_identities) is not tuple
            or any(
                _PREFIXED_SHA256.fullmatch(item) is None for item in self.selected_stable_identities
            )
            or len(set(self.selected_stable_identities)) != len(self.selected_stable_identities)
            or not set(self.selected_stable_identities) <= set(ranked_ids)
            or type(self.delivered_ranges) is not tuple
            or type(self.context_ranges) is not tuple
            or any(
                type(item) is not ObservedRange
                for item in (*self.delivered_ranges, *self.context_ranges)
            )
            or type(self.delivered_utf8_bytes) is not int
            or self.delivered_utf8_bytes < 0
            or self.delivered_utf8_bytes
            != sum(
                item.end_utf8_byte - item.start_utf8_byte
                for item in (*self.delivered_ranges, *self.context_ranges)
            )
            or type(self.context_attribution_unique) is not bool
            or type(self.output_complete) is not bool
            or type(self.exact_read_complete) is not bool
            or type(self.provenance_exact) is not bool
        ):
            raise ValueError("mechanism case observation is invalid")


@dataclass(frozen=True)
class SealedMechanismObservation:
    mechanism_id: str
    cases: tuple[MechanismCaseObservation, ...]
    portable_bytes: bytes
    portable_sha256: str


@dataclass(frozen=True)
class CaseMetrics:
    query_id: str
    mechanism_id: str
    token_presence: bool
    selection_recall: bool
    delivery_recall: bool
    output_completeness: bool
    exact_read_recovery: bool
    provenance_exactness: bool
    route_exact: bool
    rank_at_1: bool
    rank_at_3: bool
    rank_at_5: bool
    rank_at_10: bool
    raw_rank: int | None
    parent_collapsed_rank: int | None
    candidate_expansion_ratio_hex: str
    useful_span_density_hex: str
    required_role_coverage: tuple[str, ...]
    context_only_match_count: int
    component_attribution: tuple[str, ...]
    context_attribution_unique: bool
    hard_negative_regression: bool
    current_success_regression: bool
    required_span_count: int

    def __post_init__(self) -> None:
        boolean_values = (
            self.token_presence,
            self.selection_recall,
            self.delivery_recall,
            self.output_completeness,
            self.exact_read_recovery,
            self.provenance_exactness,
            self.route_exact,
            self.context_attribution_unique,
            self.rank_at_1,
            self.rank_at_3,
            self.rank_at_5,
            self.rank_at_10,
            self.hard_negative_regression,
            self.current_success_regression,
        )
        if (
            not self.query_id
            or not self.mechanism_id
            or any(type(item) is not bool for item in boolean_values)
            or (self.raw_rank is not None and (type(self.raw_rank) is not int or self.raw_rank < 1))
            or (
                self.parent_collapsed_rank is not None
                and (type(self.parent_collapsed_rank) is not int or self.parent_collapsed_rank < 1)
            )
            or not _finite_hex(self.candidate_expansion_ratio_hex)
            or not _finite_hex(self.useful_span_density_hex)
            or not 0.0 <= float.fromhex(self.useful_span_density_hex) <= 1.0
            or type(self.required_role_coverage) is not tuple
            or type(self.component_attribution) is not tuple
            or any(
                type(item) is not str or not item
                for item in (
                    *self.required_role_coverage,
                    *self.component_attribution,
                )
            )
            or type(self.context_only_match_count) is not int
            or self.context_only_match_count < 0
            or type(self.required_span_count) is not int
            or self.required_span_count < 0
        ):
            raise ValueError("case metrics are invalid")


@dataclass(frozen=True)
class MechanismAggregateMetrics:
    mechanism_id: str
    comparable_query_count: int
    recall_at_1_hex: str
    recall_at_3_hex: str
    recall_at_5_hex: str
    mrr_at_5_hex: str
    ndcg_at_10_hex: str

    def __post_init__(self) -> None:
        if (
            not self.mechanism_id
            or type(self.comparable_query_count) is not int
            or self.comparable_query_count < 1
            or any(
                not _finite_hex(item) or not 0.0 <= float.fromhex(item) <= 1.0
                for item in (
                    self.recall_at_1_hex,
                    self.recall_at_3_hex,
                    self.recall_at_5_hex,
                    self.mrr_at_5_hex,
                    self.ndcg_at_10_hex,
                )
            )
        ):
            raise ValueError("aggregate metrics are invalid")


@dataclass(frozen=True)
class DevelopmentGradingResult:
    case_metrics: tuple[CaseMetrics, ...]
    aggregate_metrics: tuple[MechanismAggregateMetrics, ...]
    classifications: tuple[str, ...]
    mechanism_statuses: dict[str, str]
    deterministic_equality: bool
    grading_digest: str

    def __post_init__(self) -> None:
        if (
            type(self.case_metrics) is not tuple
            or any(type(item) is not CaseMetrics for item in self.case_metrics)
            or type(self.aggregate_metrics) is not tuple
            or any(type(item) is not MechanismAggregateMetrics for item in self.aggregate_metrics)
            or type(self.classifications) is not tuple
            or not self.classifications
            or any(type(item) is not str or not item for item in self.classifications)
            or set(self.mechanism_statuses)
            != {
                "o1",
                "o2",
                "o3",
                "o4",
                "o5",
            }
            or not set(self.mechanism_statuses.values()) <= _STATUS_INVENTORY | {"not_evaluated"}
            or type(self.deterministic_equality) is not bool
            or self.grading_digest
            != development_grading_digest(
                case_metrics=self.case_metrics,
                aggregate_metrics=self.aggregate_metrics,
                classifications=self.classifications,
                mechanism_statuses=self.mechanism_statuses,
                deterministic_equality=self.deterministic_equality,
            )
        ):
            raise ValueError("grading digest is invalid")


def _validate_case_authority(
    payload: AgentContextDevelopmentGradingPayload,
    case: MechanismCaseObservation,
) -> None:
    expected_route = payload.expected_routes_by_query.get(case.query_id)
    expected_terms = payload.query_terms_by_query.get(case.query_id)
    allowed_profiles = payload.rank_profiles_by_mechanism.get(case.mechanism_id)
    if (
        expected_route is None
        or expected_terms is None
        or allowed_profiles is None
        or case.route != ("fts" if expected_route == "fts5" else "cjk")
        or case.query_terms != expected_terms
        or case.rank_profile_id not in allowed_profiles
    ):
        raise ValueError("observation case authority is invalid")


def _case_guardrails_pass(
    case: MechanismCaseObservation,
    payload: AgentContextDevelopmentGradingPayload,
) -> bool:
    _validate_case_authority(payload, case)
    visible = bool(
        case.selected_stable_identities
        or case.delivered_ranges
        or case.context_ranges
    )
    control_kind = payload.control_query_kinds.get(case.query_id)
    common = (
        case.output_complete
        and case.exact_read_complete
        and case.provenance_exact
        and all(
            term in case.retrieval_text.casefold()
            for term in payload.query_terms_by_query[case.query_id]
        )
    )
    if control_kind in {"hard_negative", "misleading_source_name"}:
        return common and not visible
    if control_kind in {"current_success", "exact_read"}:
        return common and visible
    return common


def _selection_success(
    payload: AgentContextDevelopmentGradingPayload,
    case: MechanismCaseObservation,
) -> bool:
    metric = _grade_case(payload, case)
    return (
        metric.selection_recall
        and not metric.hard_negative_regression
        and not metric.current_success_regression
        and metric.output_completeness
        and metric.exact_read_recovery
        and metric.provenance_exactness
        and metric.route_exact
        and metric.token_presence
    )


def _delivery_success(
    payload: AgentContextDevelopmentGradingPayload,
    case: MechanismCaseObservation,
) -> bool:
    metric = _grade_case(payload, case)
    return (
        metric.delivery_recall
        and not metric.hard_negative_regression
        and not metric.current_success_regression
        and metric.output_completeness
        and metric.exact_read_recovery
        and metric.provenance_exactness
        and metric.route_exact
        and metric.token_presence
    )


def derive_residual_gates(
    payload: AgentContextDevelopmentGradingPayload,
    *,
    o0_artifact_sha256: str,
    o0: SealedMechanismObservation,
    o1: SealedMechanismObservation,
    o2: SealedMechanismObservation,
) -> ResidualGateSet:
    if (
        type(payload) is not AgentContextDevelopmentGradingPayload
        or _BARE_SHA256.fullmatch(o0_artifact_sha256) is None
    ):
        raise ValueError("residual gate evidence is invalid")
    observations = _validated_observation_inventory((o0, o1, o2))
    expected_mechanisms = tuple(
        payload.mechanism_ids[key] for key in ("o0", "o1", "o2")
    )
    if tuple(item.mechanism_id for item in observations) != tuple(
        sorted(expected_mechanisms, key=str.encode)
    ):
        raise ValueError("residual gate evidence is invalid")
    by_mechanism = {item.mechanism_id: item for item in observations}
    expected_queries = set(payload.query_ids)
    if any(
        {case.query_id for case in observation.cases} != expected_queries
        for observation in observations
    ):
        raise ValueError("residual gate evidence is invalid")
    for observation in observations:
        for case in observation.cases:
            _validate_case_authority(payload, case)
    cases = {
        mechanism_id: {case.query_id: case for case in observation.cases}
        for mechanism_id, observation in by_mechanism.items()
    }
    candidate_targets = {
        query_id
        for query_id, mechanism_ids in payload.observation_ids_by_query.items()
        if any(item != payload.mechanism_ids["o0"] for item in mechanism_ids)
    }
    control_queries = expected_queries - candidate_targets
    failed_controls = tuple(
        sorted(
            (
                query_id
                for query_id in control_queries
                if any(
                    not _case_guardrails_pass(cases[mechanism_id][query_id], payload)
                    for mechanism_id in (
                        payload.mechanism_ids["o0"],
                        payload.mechanism_ids["o1"],
                        payload.mechanism_ids["o2"],
                    )
                )
            ),
            key=str.encode,
        )
    )
    o3_targets = {
        query_id
        for query_id in candidate_targets
        if payload.mechanism_ids["o1"]
        in payload.observation_ids_by_query[query_id]
        and any(
            span.query_id == query_id and span.hypothesis == "page_internal"
            for span in payload.required_spans
        )
    }
    o4_targets = {
        query_id
        for query_id in candidate_targets
        if payload.mechanism_ids["o4"]
        in payload.observation_ids_by_query[query_id]
        and any(
            span.query_id == query_id and span.hypothesis == "delivery_context"
            for span in payload.required_spans
        )
    }
    o5_targets = {
        query_id
        for query_id in candidate_targets
        if payload.mechanism_ids["o5"] in payload.observation_ids_by_query[query_id]
    }
    o1_cases = cases[payload.mechanism_ids["o1"]]
    o2_cases = cases[payload.mechanism_ids["o2"]]
    o3_residual = tuple(
        sorted(
            (
                query_id
                for query_id in o3_targets
                if not _selection_success(payload, o1_cases[query_id])
            ),
            key=str.encode,
        )
    )
    o4_residual = tuple(
        sorted(
            (
                query_id
                for query_id in o4_targets
                if not _delivery_success(payload, o2_cases[query_id])
            ),
            key=str.encode,
        )
    )
    evidence = ResidualGateEvidence(
        o0_artifact_sha256=o0_artifact_sha256,
        o0_observation_sha256=o0.portable_sha256,
        o1_observation_sha256=o1.portable_sha256,
        o2_observation_sha256=o2.portable_sha256,
        failed_control_query_ids=failed_controls,
        o3_residual_query_ids=o3_residual,
        o4_residual_query_ids=o4_residual,
        o5_preregistered_query_ids=tuple(sorted(o5_targets, key=str.encode)),
    )
    if evidence.failed_control_query_ids:
        decisions = (
            ResidualGateDecision("source-context-index-v1", False, "control_guardrail_failed"),
            ResidualGateDecision("source-context-delivery-v1", False, "control_guardrail_failed"),
            ResidualGateDecision("adjacent-page-assembly-v1", False, "control_guardrail_failed"),
        )
    else:
        decisions = (
            ResidualGateDecision(
                "source-context-index-v1",
                bool(evidence.o3_residual_query_ids),
                (
                    "residual_indexing_ranking_failure"
                    if evidence.o3_residual_query_ids
                    else "no_residual_indexing_ranking_failure"
                ),
            ),
            ResidualGateDecision(
                "source-context-delivery-v1",
                bool(evidence.o4_residual_query_ids),
                (
                    "residual_delivery_failure"
                    if evidence.o4_residual_query_ids
                    else "no_residual_delivery_failure"
                ),
            ),
            ResidualGateDecision(
                "adjacent-page-assembly-v1",
                bool(evidence.o5_preregistered_query_ids),
                (
                    "preregistered_cross_page_case"
                    if evidence.o5_preregistered_query_ids
                    else "no_preregistered_cross_page_case"
                ),
            ),
        )
    gate_record = {
        "evidence": asdict(evidence),
        "o3": asdict(decisions[0]),
        "o4": asdict(decisions[1]),
        "o5": asdict(decisions[2]),
        "schema_version": "mke.agent_context_unit_residual_gate.v1",
    }
    return ResidualGateSet(
        evidence=evidence,
        o3=decisions[0],
        o4=decisions[1],
        o5=decisions[2],
        gate_digest=_digest(gate_record),
    )


def validate_residual_gate_for_dispatch(
    payload: AgentContextDevelopmentGradingPayload,
    gates: ResidualGateSet,
    mechanism: Literal["o3", "o4", "o5"],
    *,
    o0_artifact_sha256: str,
    o0: SealedMechanismObservation,
    o1: SealedMechanismObservation,
    o2: SealedMechanismObservation,
) -> bool:
    if type(gates) is not ResidualGateSet or mechanism not in _MECHANISM_BY_GATE:
        raise ValueError("residual gate authority is invalid")
    rebuilt = derive_residual_gates(
        payload,
        o0_artifact_sha256=o0_artifact_sha256,
        o0=o0,
        o1=o1,
        o2=o2,
    )
    if gates != rebuilt:
        raise ValueError("residual gate authority is invalid")
    decision = getattr(gates, mechanism)
    if decision.mechanism_id != _MECHANISM_BY_GATE[mechanism]:
        raise ValueError("residual gate authority is invalid")
    return decision.enabled


def seal_mechanism_observation(
    mechanism_id: str,
    cases: tuple[MechanismCaseObservation, ...],
) -> SealedMechanismObservation:
    if (
        type(mechanism_id) is not str
        or not mechanism_id
        or type(cases) is not tuple
        or not cases
        or any(
            type(case) is not MechanismCaseObservation or case.mechanism_id != mechanism_id
            for case in cases
        )
    ):
        raise ValueError("observation inventory is invalid")
    query_ids = tuple(case.query_id for case in cases)
    if len(set(query_ids)) != len(query_ids):
        raise ValueError("observation inventory is invalid")
    ordered = tuple(sorted(cases, key=lambda item: item.query_id.encode()))
    content = _canonical_bytes(
        {
            "cases": [asdict(case) for case in ordered],
            "mechanism_id": mechanism_id,
            "schema_version": "mke.agent_context_unit_mechanism_observation.v1",
        }
    )
    return SealedMechanismObservation(
        mechanism_id=mechanism_id,
        cases=ordered,
        portable_bytes=content,
        portable_sha256=hashlib.sha256(content).hexdigest(),
    )


def grade_context_mechanisms(
    payload: AgentContextDevelopmentGradingPayload,
    gates: ResidualGateSet,
    *,
    baseline_observation: SealedMechanismObservation,
    o0_artifact_sha256: str,
    workspace_a: tuple[SealedMechanismObservation, ...],
    workspace_b: tuple[SealedMechanismObservation, ...],
) -> DevelopmentGradingResult:
    if type(payload) is not AgentContextDevelopmentGradingPayload:
        raise ValueError("grading payload is invalid")
    a = _validated_observation_inventory(workspace_a)
    b = _validated_observation_inventory(workspace_b)
    if tuple(item.portable_bytes for item in a) != tuple(item.portable_bytes for item in b):
        raise ValueError("portable observation equality is invalid")
    by_mechanism = {item.mechanism_id: item for item in a}
    o1 = by_mechanism.get(payload.mechanism_ids["o1"])
    o2 = by_mechanism.get(payload.mechanism_ids["o2"])
    if o1 is None or o2 is None:
        raise ValueError("observation inventory is invalid")
    rebuilt_gates = derive_residual_gates(
        payload,
        o0_artifact_sha256=o0_artifact_sha256,
        o0=baseline_observation,
        o1=o1,
        o2=o2,
    )
    if gates != rebuilt_gates:
        raise ValueError("residual gate authority is invalid")
    required = {
        payload.mechanism_ids["o1"],
        payload.mechanism_ids["o2"],
    }
    if not required <= set(by_mechanism):
        raise ValueError("observation inventory is invalid")
    target_queries = {
        query_id
        for query_id, mechanism_ids in payload.observation_ids_by_query.items()
        if any(item != payload.mechanism_ids["o0"] for item in mechanism_ids)
    }
    control_queries = set(payload.query_ids) - target_queries
    expected_by_gate = {
        "o1": set(payload.query_ids),
        "o2": set(payload.query_ids),
        "o3": set(gates.evidence.o3_residual_query_ids) | control_queries,
        "o4": set(gates.evidence.o4_residual_query_ids) | control_queries,
        "o5": set(gates.evidence.o5_preregistered_query_ids) | control_queries,
    }
    for gate_name in ("o1", "o2", "o3", "o4", "o5"):
        observation = by_mechanism.get(payload.mechanism_ids[gate_name])
        expected = expected_by_gate[gate_name]
        if observation is not None and {
            case.query_id for case in observation.cases
        } != expected:
            raise ValueError("observation inventory is invalid")
        if observation is not None:
            for case in observation.cases:
                _validate_case_authority(payload, case)
    for gate_name in ("o3", "o4", "o5"):
        mechanism_id = payload.mechanism_ids[gate_name]
        enabled = validate_residual_gate_for_dispatch(
            payload,
            gates,
            gate_name,
            o0_artifact_sha256=o0_artifact_sha256,
            o0=baseline_observation,
            o1=o1,
            o2=o2,
        )
        if enabled != (mechanism_id in by_mechanism):
            if not enabled and mechanism_id in by_mechanism:
                raise ValueError("disabled mechanism observation is invalid")
            raise ValueError("observation inventory is invalid")

    metrics: list[CaseMetrics] = []
    classifications: set[str] = set()
    statuses: dict[str, str] = {}
    baseline_cases = {case.query_id: case for case in baseline_observation.cases}
    case_inventory = {
        mechanism_id: {case.query_id: case for case in observation.cases}
        for mechanism_id, observation in by_mechanism.items()
    }
    targets_by_gate = {
        "o1": {
            query_id
            for query_id, mechanism_ids in payload.observation_ids_by_query.items()
            if payload.mechanism_ids["o1"] in mechanism_ids
        },
        "o2": {
            query_id
            for query_id, mechanism_ids in payload.observation_ids_by_query.items()
            if payload.mechanism_ids["o2"] in mechanism_ids
        },
        "o3": set(gates.evidence.o3_residual_query_ids),
        "o4": set(gates.evidence.o4_residual_query_ids),
        "o5": set(gates.evidence.o5_preregistered_query_ids),
    }
    for gate_name in ("o1", "o2", "o3", "o4", "o5"):
        mechanism_id = payload.mechanism_ids[gate_name]
        observation = by_mechanism.get(mechanism_id)
        if observation is None:
            statuses[gate_name] = "not_evaluated"
            continue
        mechanism_metrics = tuple(_grade_case(payload, case) for case in observation.cases)
        metrics.extend(mechanism_metrics)
        for metric in mechanism_metrics:
            classifications.update(_classifications(metric, gate_name))
        predecessor_id = {
            "o1": payload.mechanism_ids["o0"],
            "o2": payload.mechanism_ids["o1"],
            "o3": payload.mechanism_ids["o1"],
            "o4": payload.mechanism_ids["o2"],
            "o5": payload.mechanism_ids["o0"],
        }[gate_name]
        predecessor_cases = (
            baseline_cases
            if predecessor_id == payload.mechanism_ids["o0"]
            else case_inventory[predecessor_id]
        )
        statuses[gate_name] = _contrast_status(
            payload,
            gate_name,
            candidate_cases=case_inventory[mechanism_id],
            predecessor_cases=predecessor_cases,
            target_queries=targets_by_gate[gate_name],
            control_queries=control_queries,
        )
        if gate_name in {"o2", "o4", "o5"} and any(
            _rank_regressed(
                payload,
                case_inventory[mechanism_id][query_id],
                predecessor_cases[query_id],
            )
            for query_id in targets_by_gate[gate_name] | control_queries
        ):
            classifications.add("rank_regression")
        if statuses[gate_name] == "candidate_qualified":
            classifications.add(
                {
                    "o1": "segmentation_rank_effect",
                    "o2": "segmentation_delivery_effect",
                    "o3": "context_index_effect",
                    "o4": "context_delivery_effect",
                    "o5": "cross_page_assembly_effect",
                }[gate_name]
            )
    if "mechanism_ambiguous" in statuses.values():
        classifications.add("mechanism_ambiguous")
    if not classifications:
        classifications.add("not_observed_under_protocol")
    status_inventory = set(payload.mechanism_verdict_rules["status_inventory"])
    if (
        not set(statuses.values()) <= _STATUS_INVENTORY | {"not_evaluated"}
        or status_inventory != _STATUS_INVENTORY
    ):
        raise ValueError("grading status inventory is invalid")
    ordered_metrics = tuple(
        sorted(
            metrics,
            key=lambda item: (
                item.mechanism_id.encode(),
                item.query_id.encode(),
            ),
        )
    )
    return build_development_grading_result(
        case_metrics=ordered_metrics,
        classifications=tuple(sorted(classifications)),
        mechanism_statuses=statuses,
        deterministic_equality=True,
    )


def build_development_grading_result(
    *,
    case_metrics: tuple[CaseMetrics, ...],
    classifications: tuple[str, ...],
    mechanism_statuses: dict[str, str],
    deterministic_equality: bool,
) -> DevelopmentGradingResult:
    if (
        type(classifications) is not tuple
        or not classifications
        or tuple(sorted(classifications)) != classifications
        or len(set(classifications)) != len(classifications)
        or type(mechanism_statuses) is not dict
    ):
        raise ValueError("grading result authority is invalid")
    aggregate_metrics = _aggregate_metrics(case_metrics)
    digest = development_grading_digest(
        case_metrics=case_metrics,
        aggregate_metrics=aggregate_metrics,
        classifications=classifications,
        mechanism_statuses=mechanism_statuses,
        deterministic_equality=deterministic_equality,
    )
    return DevelopmentGradingResult(
        case_metrics=case_metrics,
        aggregate_metrics=aggregate_metrics,
        classifications=classifications,
        mechanism_statuses=mechanism_statuses,
        deterministic_equality=deterministic_equality,
        grading_digest=digest,
    )


def development_grading_digest(
    *,
    case_metrics: tuple[CaseMetrics, ...],
    aggregate_metrics: tuple[MechanismAggregateMetrics, ...],
    classifications: tuple[str, ...],
    mechanism_statuses: dict[str, str],
    deterministic_equality: bool,
) -> str:
    return _digest(
        {
            "case_metrics": [asdict(item) for item in case_metrics],
            "aggregate_metrics": [asdict(item) for item in aggregate_metrics],
            "classifications": list(classifications),
            "deterministic_equality": deterministic_equality,
            "mechanism_statuses": mechanism_statuses,
            "schema_version": "mke.agent_context_unit_development_grading.v1",
        }
    )


def _validated_observation_inventory(
    observations: tuple[SealedMechanismObservation, ...],
) -> tuple[SealedMechanismObservation, ...]:
    if (
        type(observations) is not tuple
        or not observations
        or any(type(item) is not SealedMechanismObservation for item in observations)
    ):
        raise ValueError("observation inventory is invalid")
    mechanisms = tuple(item.mechanism_id for item in observations)
    if len(set(mechanisms)) != len(mechanisms):
        raise ValueError("observation inventory is invalid")
    for item in observations:
        rebuilt = seal_mechanism_observation(item.mechanism_id, item.cases)
        if item != rebuilt:
            raise ValueError("observation inventory is invalid")
    return tuple(sorted(observations, key=lambda item: item.mechanism_id.encode()))


def _grade_case(
    payload: AgentContextDevelopmentGradingPayload,
    case: MechanismCaseObservation,
) -> CaseMetrics:
    spans = payload.required_spans
    required = tuple(span for span in spans if span.query_id == case.query_id)
    ranked_matches = tuple(
        candidate
        for candidate in case.ranked
        if any(_contains(candidate.authority_range, span) for span in required)
    )
    selected = set(case.selected_stable_identities)
    selection_covered = {
        span.span_id
        for span in required
        if any(
            candidate.stable_identity in selected
            and _contains(candidate.authority_range, span)
            for candidate in case.ranked
        )
    }
    delivery_ranges = (*case.delivered_ranges, *case.context_ranges)
    covered = tuple(
        span
        for span in required
        if any(_contains(delivered_range, span) for delivered_range in delivery_ranges)
    )
    unit_covered = {
        span.span_id
        for span in required
        if any(_contains(item, span) for item in case.delivered_ranges)
    }
    context_covered = tuple(
        span
        for span in covered
        if span.span_id not in unit_covered
        and any(_contains(item, span) for item in case.context_ranges)
    )
    matched_components = tuple(
        sorted(
            {
                item.component_kind
                for item in case.context_ranges
                for span in context_covered
                if _contains(item, span)
            }
        )
    )
    first_rank = min((item.rank for item in ranked_matches), default=None)
    parent_rank = min((item.parent_collapsed_rank for item in ranked_matches), default=None)
    useful_bytes = sum(span.end_utf8_byte - span.start_utf8_byte for span in covered)
    density = useful_bytes / case.delivered_utf8_bytes if case.delivered_utf8_bytes else 0.0
    expansion = case.candidate_count / case.unique_parent_count if case.unique_parent_count else 0.0
    controls = {span.control for span in required}
    expected_route = payload.expected_routes_by_query[case.query_id]
    route_exact = case.route == ("fts" if expected_route == "fts5" else "cjk")
    control_kind = payload.control_query_kinds.get(case.query_id)
    has_visible_result = bool(
        case.selected_stable_identities or case.delivered_ranges or case.context_ranges
    )
    return CaseMetrics(
        query_id=case.query_id,
        mechanism_id=case.mechanism_id,
        token_presence=all(
            term.casefold() in case.retrieval_text.casefold() for term in case.query_terms
        ),
        selection_recall=(
            len(selection_covered) == len(required) if required else True
        ),
        delivery_recall=len(covered) == len(required),
        output_completeness=case.output_complete,
        exact_read_recovery=case.exact_read_complete,
        provenance_exactness=case.provenance_exact,
        route_exact=route_exact,
        rank_at_1=first_rank is not None and first_rank <= 1,
        rank_at_3=first_rank is not None and first_rank <= 3,
        rank_at_5=first_rank is not None and first_rank <= 5,
        rank_at_10=first_rank is not None and first_rank <= 10,
        raw_rank=first_rank,
        parent_collapsed_rank=parent_rank,
        candidate_expansion_ratio_hex=expansion.hex(),
        useful_span_density_hex=density.hex(),
        required_role_coverage=tuple(sorted({span.role for span in covered})),
        context_only_match_count=len(context_covered),
        component_attribution=matched_components,
        context_attribution_unique=case.context_attribution_unique,
        hard_negative_regression=(
            control_kind in {"hard_negative", "misleading_source_name"} and has_visible_result
        ),
        current_success_regression=(
            (
                control_kind in {"current_success", "exact_read"}
                and (
                    not has_visible_result
                    or not case.output_complete
                    or not case.exact_read_complete
                )
            )
            or ("current_success" in controls and len(covered) != len(required))
        ),
        required_span_count=len(required),
    )


def _aggregate_metrics(
    metrics: tuple[CaseMetrics, ...],
) -> tuple[MechanismAggregateMetrics, ...]:
    result: list[MechanismAggregateMetrics] = []
    for mechanism_id in sorted({item.mechanism_id for item in metrics}, key=str.encode):
        comparable = tuple(
            item
            for item in metrics
            if item.mechanism_id == mechanism_id and item.required_span_count > 0
        )
        if not comparable:
            continue
        count = len(comparable)
        recall_1 = sum(item.rank_at_1 for item in comparable) / count
        recall_3 = sum(item.rank_at_3 for item in comparable) / count
        recall_5 = sum(item.rank_at_5 for item in comparable) / count
        reciprocal = (
            sum(
                1.0 / item.raw_rank
                for item in comparable
                if item.raw_rank is not None and item.raw_rank <= 5
            )
            / count
        )
        ndcg = (
            sum(
                1.0 / math.log2(item.raw_rank + 1)
                for item in comparable
                if item.raw_rank is not None and item.raw_rank <= 10
            )
            / count
        )
        result.append(
            MechanismAggregateMetrics(
                mechanism_id=mechanism_id,
                comparable_query_count=count,
                recall_at_1_hex=recall_1.hex(),
                recall_at_3_hex=recall_3.hex(),
                recall_at_5_hex=recall_5.hex(),
                mrr_at_5_hex=reciprocal.hex(),
                ndcg_at_10_hex=ndcg.hex(),
            )
        )
    return tuple(result)


def _contains(observed: ObservedRange, span: AgentContextRequiredSpan) -> bool:
    return (
        observed.source_content_fingerprint == span.source_content_fingerprint
        and observed.locator_kind == span.locator_kind
        and observed.locator_start == span.locator_start
        and observed.locator_end == span.locator_end
        and observed.start_utf8_byte <= span.start_utf8_byte
        and observed.end_utf8_byte >= span.end_utf8_byte
    )


def _classifications(metric: CaseMetrics, gate_name: str) -> set[str]:
    result: set[str] = set()
    if not metric.route_exact or not metric.token_presence:
        result.add("query_policy_miss")
    elif metric.raw_rank is None:
        result.add("candidate_eligibility_miss")
    elif not metric.selection_recall:
        result.add("rank_miss")
    elif not metric.delivery_recall:
        result.add("delivery_completeness_miss")
    if metric.context_only_match_count:
        result.add("context_only_match")
    return result


def _contrast_status(
    payload: AgentContextDevelopmentGradingPayload,
    gate_name: str,
    *,
    candidate_cases: dict[str, MechanismCaseObservation],
    predecessor_cases: dict[str, MechanismCaseObservation],
    target_queries: set[str],
    control_queries: set[str],
) -> str:
    if not target_queries:
        return "candidate_failed"
    if any(
        query_id not in candidate_cases or query_id not in predecessor_cases
        for query_id in (*target_queries, *control_queries)
    ):
        return "candidate_failed"
    if any(
        not _case_guardrails_pass(candidate_cases[query_id], payload)
        for query_id in control_queries
    ):
        return "candidate_failed"
    if gate_name in {"o2", "o4", "o5"} and any(
        _rank_regressed(
            payload,
            candidate_cases[query_id],
            predecessor_cases[query_id],
        )
        for query_id in target_queries | control_queries
    ):
        return "candidate_failed"
    strict_repairs: list[bool] = []
    for query_id in target_queries:
        candidate = candidate_cases[query_id]
        predecessor = predecessor_cases[query_id]
        if not _case_guardrails_pass(candidate, payload):
            return "candidate_failed"
        if gate_name in {"o1", "o3"}:
            strict_repairs.append(
                _selection_success(payload, candidate)
                and not _selection_success(payload, predecessor)
            )
        else:
            strict_repairs.append(
                _delivery_success(payload, candidate)
                and not _delivery_success(payload, predecessor)
            )
    if not all(strict_repairs):
        return "candidate_failed"
    if gate_name in {"o3", "o4", "o5"} and any(
        case.context_ranges and not case.context_attribution_unique
        for case in candidate_cases.values()
    ):
        return "mechanism_ambiguous"
    return "candidate_qualified"


def _rank_regressed(
    payload: AgentContextDevelopmentGradingPayload,
    candidate: MechanismCaseObservation,
    predecessor: MechanismCaseObservation,
) -> bool:
    for span in (
        item
        for item in payload.required_spans
        if item.query_id == candidate.query_id
    ):
        predecessor_matches = tuple(
            item for item in predecessor.ranked if _contains(item.authority_range, span)
        )
        candidate_matches = tuple(
            item for item in candidate.ranked if _contains(item.authority_range, span)
        )
        predecessor_rank = min(
            (item.rank for item in predecessor_matches),
            default=None,
        )
        candidate_rank = min(
            (item.rank for item in candidate_matches),
            default=None,
        )
        predecessor_parent_rank = min(
            (item.parent_collapsed_rank for item in predecessor_matches),
            default=None,
        )
        candidate_parent_rank = min(
            (item.parent_collapsed_rank for item in candidate_matches),
            default=None,
        )
        if (
            predecessor_rank is not None
            and (candidate_rank is None or candidate_rank > predecessor_rank)
        ) or (
            predecessor_parent_rank is not None
            and (
                candidate_parent_rank is None
                or candidate_parent_rank > predecessor_parent_rank
            )
        ):
            return True
    return False


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _finite_hex(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = float.fromhex(value)
    except ValueError:
        return False
    return math.isfinite(parsed) and parsed.hex() == value
