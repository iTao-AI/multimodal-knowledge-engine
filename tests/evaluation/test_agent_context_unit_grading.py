from __future__ import annotations

import dataclasses
import inspect
import json
from pathlib import Path

import pytest

from mke.evaluation import agent_context_unit_grading as grading
from mke.evaluation.agent_context_unit_grading_protocol import (
    AgentContextDevelopmentGradingPayload,
    AgentContextRequiredSpan,
)

SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
ROOT = Path(__file__).resolve().parents[2]
LOCK = json.loads(
    (ROOT / "tests/fixtures/agent-context-unit-v2/scientific-input-lock.json").read_bytes()
)


def _span(
    *,
    span_id: str = "span-answer",
    query_id: str = "q-rank",
    start: int = 2,
    end: int = 5,
    role: str = "answer",
    hypothesis: str = "page_internal",
    control: str = "target",
) -> AgentContextRequiredSpan:
    return AgentContextRequiredSpan(
        span_id=span_id,
        query_id=query_id,
        source_content_fingerprint=SHA_A,
        locator_kind="page",
        locator_start=1,
        locator_end=1,
        start_utf8_byte=start,
        end_utf8_byte=end,
        text_sha256="c" * 64,
        role=role,
        hypothesis=hypothesis,
        control=control,
    )


def _payload(
    spans: tuple[AgentContextRequiredSpan, ...] | None = None,
) -> AgentContextDevelopmentGradingPayload:
    selected_spans = spans or (_span(),)
    return AgentContextDevelopmentGradingPayload(
        required_spans=selected_spans,
        query_ids=tuple(sorted({span.query_id for span in selected_spans})),
        observation_ids_by_query={
            "q-rank": (
                "current-runtime-baseline-v1",
                "deterministic-unit-rank-v1",
                "fixed-rank-delivery-v1",
                "source-context-index-v1",
            )
        },
        expected_routes_by_query={"q-rank": "fts5"},
        query_text_by_query={"q-rank": "needle"},
        query_terms_by_query={"q-rank": ("needle",)},
        control_query_kinds={},
        mechanism_ids={
            "o0": "current-runtime-baseline-v1",
            "o1": "deterministic-unit-rank-v1",
            "o2": "fixed-rank-delivery-v1",
            "o3": "source-context-index-v1",
            "o4": "source-context-delivery-v1",
            "o5": "adjacent-page-assembly-v1",
        },
        rank_profiles_by_mechanism={
            "current-runtime-baseline-v1": ("current-runtime-baseline-v1",),
            "deterministic-unit-rank-v1": ("deterministic-unit-rank-v1",),
            "fixed-rank-delivery-v1": ("deterministic-unit-rank-v1",),
            "source-context-index-v1": (
                "source-context-index-v1:heading:rank",
                "source-context-index-v1:previous_unit:rank",
                "source-context-index-v1:next_unit:rank",
                "source-context-index-v1:combined:rank",
            ),
            "source-context-delivery-v1": ("deterministic-unit-rank-v1",),
            "adjacent-page-assembly-v1": (
                "current-runtime-baseline-v1",
                "deterministic-unit-rank-v1",
            ),
        },
        residual_gate_rules=LOCK["residual_gate_rules"],
        mechanism_verdict_rules=LOCK["mechanism_verdict_rules"],
        mechanism_verdict_revision=LOCK["mechanism_verdict_revision"],
        stage_verdict_revision=LOCK["stage_verdict_revision"],
        scientific_nonclaims=(
            "development_only_until_separate_holdout_authority",
            "comparison_only",
            "no_retrieval_quality_claim",
            "no_performance_claim",
            "no_runtime_promotion",
        ),
    )


def _range(
    *,
    start: int = 0,
    end: int = 10,
    component_kind: str = "unit",
) -> grading.ObservedRange:
    return grading.ObservedRange(
        source_content_fingerprint=SHA_A,
        locator_kind="page",
        locator_start=1,
        locator_end=1,
        start_utf8_byte=start,
        end_utf8_byte=end,
        origin_evidence_ref=SHA_B,
        component_kind=component_kind,
    )


def _case(
    mechanism_id: str,
    *,
    query_id: str = "q-rank",
    selected: bool = True,
    delivered: tuple[grading.ObservedRange, ...] | None = None,
    context: tuple[grading.ObservedRange, ...] = (),
    rank_profile_id: str | None = None,
    query_terms: tuple[str, ...] = ("needle",),
    retrieval_text: str = "needle in unit",
) -> grading.MechanismCaseObservation:
    stable_id = "sha256:" + "d" * 64
    actual_delivered = (_range(),) if delivered is None else delivered
    return grading.MechanismCaseObservation(
        query_id=query_id,
        mechanism_id=mechanism_id,
        route="fts",
        rank_profile_id=rank_profile_id or _rank_profile(mechanism_id),
        query_terms=query_terms,
        retrieval_text=retrieval_text,
        candidate_count=2,
        unique_parent_count=1,
        ranked=(
            grading.ObservedRankedCandidate(
                stable_identity=stable_id,
                rank=1,
                parent_collapsed_rank=1,
                authority_range=_range(),
            ),
        ),
        selected_stable_identities=(stable_id,) if selected else (),
        delivered_ranges=actual_delivered,
        context_ranges=context,
        delivered_utf8_bytes=sum(
            item.end_utf8_byte - item.start_utf8_byte for item in (*actual_delivered, *context)
        ),
        context_attribution_unique=True,
        output_complete=True,
        exact_read_complete=True,
        provenance_exact=True,
    )


def _seal(
    mechanism_id: str,
    case: grading.MechanismCaseObservation | None = None,
) -> grading.SealedMechanismObservation:
    return grading.seal_mechanism_observation(
        mechanism_id,
        (case or _case(mechanism_id),),
    )


def _case_at_relevant_rank(
    mechanism_id: str,
    *,
    rank: int,
    delivered: tuple[grading.ObservedRange, ...],
) -> grading.MechanismCaseObservation:
    relevant_id = "sha256:" + "f" * 64
    ranked: list[grading.ObservedRankedCandidate] = []
    for index in range(1, rank + 1):
        relevant = index == rank
        ranked.append(
            grading.ObservedRankedCandidate(
                stable_identity=(
                    relevant_id if relevant else "sha256:" + str(index) * 64
                ),
                rank=index,
                parent_collapsed_rank=index,
                authority_range=(
                    _range()
                    if relevant
                    else dataclasses.replace(
                        _range(),
                        source_content_fingerprint="sha256:" + str(index) * 64,
                    )
                ),
            )
        )
    return dataclasses.replace(
        _case(mechanism_id, delivered=delivered),
        candidate_count=rank,
        unique_parent_count=rank,
        ranked=tuple(ranked),
        selected_stable_identities=(relevant_id,),
    )


def _rank_profile(mechanism_id: str) -> str:
    return {
        "current-runtime-baseline-v1": "current-runtime-baseline-v1",
        "deterministic-unit-rank-v1": "deterministic-unit-rank-v1",
        "fixed-rank-delivery-v1": "deterministic-unit-rank-v1",
        "source-context-index-v1": "source-context-index-v1:combined:rank",
        "source-context-delivery-v1": "deterministic-unit-rank-v1",
        "adjacent-page-assembly-v1": "current-runtime-baseline-v1",
    }[mechanism_id]


def _derive(
    payload: AgentContextDevelopmentGradingPayload,
    *,
    o0: grading.SealedMechanismObservation | None = None,
    o1: grading.SealedMechanismObservation | None = None,
    o2: grading.SealedMechanismObservation | None = None,
) -> grading.ResidualGateSet:
    return grading.derive_residual_gates(
        payload,
        o0_artifact_sha256=DIGEST_A,
        o0=o0 or _seal("current-runtime-baseline-v1"),
        o1=o1 or _seal("deterministic-unit-rank-v1"),
        o2=o2 or _seal("fixed-rank-delivery-v1"),
    )


def _grade(
    payload: AgentContextDevelopmentGradingPayload,
    gates: grading.ResidualGateSet,
    *,
    o0: grading.SealedMechanismObservation,
    observations: tuple[grading.SealedMechanismObservation, ...],
    workspace_b: tuple[grading.SealedMechanismObservation, ...] | None = None,
) -> grading.DevelopmentGradingResult:
    return grading.grade_context_mechanisms(
        payload,
        gates,
        baseline_observation=o0,
        o0_artifact_sha256=DIGEST_A,
        workspace_a=observations,
        workspace_b=workspace_b or observations,
    )


def test_residual_gates_are_closed_and_derived_without_labels() -> None:
    payload = _payload()
    o0 = _seal("current-runtime-baseline-v1")
    o1 = _seal(
        "deterministic-unit-rank-v1",
        _case(
            "deterministic-unit-rank-v1",
            selected=False,
            delivered=(),
        ),
    )
    o2 = _seal("fixed-rank-delivery-v1")
    gates = _derive(payload, o0=o0, o1=o1, o2=o2)

    assert gates.o3.enabled is True
    assert gates.o3.reason == "residual_indexing_ranking_failure"
    assert gates.o4.enabled is False
    assert gates.o4.reason == "no_residual_delivery_failure"
    assert gates.o5.enabled is False
    assert gates.o5.reason == "no_preregistered_cross_page_case"
    assert not hasattr(gates.evidence, "o1_page_internal_unqualified")
    assert _derive(payload, o0=o0, o1=o1, o2=o2) == gates


def test_residual_gate_rejects_forgery_from_same_sealed_inputs() -> None:
    payload = _payload()
    o0 = _seal("current-runtime-baseline-v1")
    o1 = _seal("deterministic-unit-rank-v1")
    o2 = _seal("fixed-rank-delivery-v1")
    gates = _derive(payload, o0=o0, o1=o1, o2=o2)
    forged = dataclasses.replace(
        gates,
        o3=dataclasses.replace(gates.o3, enabled=not gates.o3.enabled),
    )
    with pytest.raises(ValueError, match="residual gate authority is invalid"):
        grading.validate_residual_gate_for_dispatch(
            payload,
            forged,
            "o3",
            o0_artifact_sha256=DIGEST_A,
            o0=o0,
            o1=o1,
            o2=o2,
        )


@pytest.mark.parametrize(
    "forged_case",
    [
        _case(
            "deterministic-unit-rank-v1",
            query_terms=("forged",),
            retrieval_text="forged",
        ),
        _case(
            "deterministic-unit-rank-v1",
            rank_profile_id="forged-profile",
        ),
    ],
)
def test_gate_rejects_query_term_and_rank_profile_self_authority(
    forged_case: grading.MechanismCaseObservation,
) -> None:
    payload = _payload()
    with pytest.raises(ValueError, match="observation case authority"):
        _derive(
            payload,
            o1=_seal("deterministic-unit-rank-v1", forged_case),
        )


def test_grader_rejects_unregistered_rows_and_non_strict_effect() -> None:
    payload = _payload()
    o0 = _seal("current-runtime-baseline-v1")
    o1 = _seal("deterministic-unit-rank-v1")
    o2 = _seal("fixed-rank-delivery-v1")
    gates = _derive(payload, o0=o0, o1=o1, o2=o2)
    result = _grade(payload, gates, o0=o0, observations=(o1, o2))
    assert result.mechanism_statuses["o1"] == "candidate_failed"
    assert "segmentation_rank_effect" not in result.classifications

    unregistered = dataclasses.replace(
        payload,
        observation_ids_by_query={
            "q-rank": (
                "current-runtime-baseline-v1",
                "deterministic-unit-rank-v1",
                "fixed-rank-delivery-v1",
            )
        },
    )
    failed_o1 = _seal(
        "deterministic-unit-rank-v1",
        _case("deterministic-unit-rank-v1", selected=False, delivered=()),
    )
    closed_gates = _derive(unregistered, o0=o0, o1=failed_o1, o2=o2)
    assert closed_gates.o3.enabled is True
    with pytest.raises(ValueError, match="observation"):
        _grade(
            unregistered,
            closed_gates,
            o0=o0,
            observations=(
                failed_o1,
                o2,
                _seal("source-context-index-v1"),
                _seal("source-context-delivery-v1"),
            ),
        )


def test_partial_required_span_and_role_coverage_cannot_qualify_o1() -> None:
    payload = _payload(
        (
            _span(
                hypothesis="segmentation",
                role="answer",
                control="current_success",
                start=0,
                end=5,
            ),
            _span(
                span_id="span-disambiguator",
                hypothesis="segmentation",
                role="disambiguator",
                start=6,
                end=9,
            ),
        )
    )
    o0 = _seal(
        "current-runtime-baseline-v1",
        _case("current-runtime-baseline-v1", selected=False, delivered=()),
    )
    partial = _range(start=0, end=5)
    o1_case = dataclasses.replace(
        _case("deterministic-unit-rank-v1", delivered=(partial,)),
        ranked=(
            dataclasses.replace(
                _case("deterministic-unit-rank-v1").ranked[0],
                authority_range=partial,
            ),
        ),
    )
    o1 = _seal("deterministic-unit-rank-v1", o1_case)
    o2 = _seal("fixed-rank-delivery-v1")
    gates = _derive(payload, o0=o0, o1=o1, o2=o2)

    result = _grade(payload, gates, o0=o0, observations=(o1, o2))
    metric = next(
        item
        for item in result.case_metrics
        if item.mechanism_id == "deterministic-unit-rank-v1"
    )

    assert metric.required_span_count == 2
    assert metric.required_role_coverage == ("answer",)
    assert metric.current_success_regression is True
    assert result.mechanism_statuses["o1"] == "candidate_failed"
    assert "segmentation_rank_effect" not in result.classifications


def test_delivery_rank_regression_fails_o2_and_equal_rank_can_qualify() -> None:
    payload = _payload((_span(hypothesis="segmentation"),))
    o0 = _seal(
        "current-runtime-baseline-v1",
        _case("current-runtime-baseline-v1", selected=False, delivered=()),
    )
    o1 = _seal(
        "deterministic-unit-rank-v1",
        _case_at_relevant_rank(
            "deterministic-unit-rank-v1",
            rank=1,
            delivered=(),
        ),
    )
    regressed_o2 = _seal(
        "fixed-rank-delivery-v1",
        _case_at_relevant_rank(
            "fixed-rank-delivery-v1",
            rank=5,
            delivered=(_range(),),
        ),
    )
    gates = _derive(payload, o0=o0, o1=o1, o2=regressed_o2)

    regressed = _grade(
        payload,
        gates,
        o0=o0,
        observations=(o1, regressed_o2),
    )

    assert regressed.mechanism_statuses["o2"] == "candidate_failed"
    assert "rank_regression" in regressed.classifications
    assert "segmentation_delivery_effect" not in regressed.classifications

    equal_o2 = _seal(
        "fixed-rank-delivery-v1",
        _case_at_relevant_rank(
            "fixed-rank-delivery-v1",
            rank=1,
            delivered=(_range(),),
        ),
    )
    equal_gates = _derive(payload, o0=o0, o1=o1, o2=equal_o2)
    equal = _grade(
        payload,
        equal_gates,
        o0=o0,
        observations=(o1, equal_o2),
    )

    assert equal.mechanism_statuses["o2"] == "candidate_qualified"
    assert "rank_regression" not in equal.classifications
    assert "segmentation_delivery_effect" in equal.classifications


def test_pure_grader_recomputes_metrics_and_context_attribution() -> None:
    payload = _payload()
    o0 = _seal("current-runtime-baseline-v1")
    o1 = _seal(
        "deterministic-unit-rank-v1",
        _case("deterministic-unit-rank-v1", selected=False, delivered=()),
    )
    o2 = _seal("fixed-rank-delivery-v1")
    gates = _derive(payload, o0=o0, o1=o1, o2=o2)
    o3 = _seal(
        "source-context-index-v1",
        _case(
            "source-context-index-v1",
            delivered=(),
            context=(_range(component_kind="heading"),),
        ),
    )

    result = _grade(
        payload,
        gates,
        o0=o0,
        observations=(o1, o2, o3),
    )

    metric = next(
        item for item in result.case_metrics if item.mechanism_id == "source-context-index-v1"
    )
    assert metric.token_presence is True
    assert metric.selection_recall is True
    assert metric.delivery_recall is True
    assert metric.output_completeness is True
    assert metric.exact_read_recovery is True
    assert metric.route_exact is True
    assert metric.provenance_exactness is True
    assert metric.rank_at_1 is True
    assert metric.rank_at_3 is True
    assert metric.rank_at_5 is True
    assert metric.rank_at_10 is True
    assert metric.parent_collapsed_rank == 1
    assert metric.candidate_expansion_ratio_hex == (2.0).hex()
    assert metric.context_only_match_count == 1
    assert metric.component_attribution == ("heading",)
    assert metric.useful_span_density_hex == float(3 / 10).hex()
    aggregate = next(
        item for item in result.aggregate_metrics if item.mechanism_id == "source-context-index-v1"
    )
    assert aggregate.recall_at_1_hex == (1.0).hex()
    assert aggregate.recall_at_3_hex == (1.0).hex()
    assert aggregate.recall_at_5_hex == (1.0).hex()
    assert aggregate.mrr_at_5_hex == (1.0).hex()
    assert aggregate.ndcg_at_10_hex == (1.0).hex()
    assert result.deterministic_equality is True
    assert result.mechanism_statuses["o3"] == "candidate_qualified"
    assert "context_only_match" in result.classifications


def test_hard_negative_and_route_controls_are_recomputed() -> None:
    base = _payload()
    payload = dataclasses.replace(
        base,
        query_ids=("q-hard-negative", "q-rank"),
        observation_ids_by_query={
            "q-hard-negative": ("current-runtime-baseline-v1",),
            "q-rank": base.observation_ids_by_query["q-rank"],
        },
        expected_routes_by_query={
            "q-hard-negative": "fts5",
            "q-rank": "fts5",
        },
        query_text_by_query={
            "q-hard-negative": "needle",
            "q-rank": "needle",
        },
        query_terms_by_query={
            "q-hard-negative": ("needle",),
            "q-rank": ("needle",),
        },
        control_query_kinds={"q-hard-negative": "hard_negative"},
    )
    o0 = grading.seal_mechanism_observation(
        "current-runtime-baseline-v1",
        (
            _case(
                "current-runtime-baseline-v1",
                query_id="q-hard-negative",
                selected=False,
                delivered=(),
            ),
            _case("current-runtime-baseline-v1"),
        ),
    )
    o1 = grading.seal_mechanism_observation(
        "deterministic-unit-rank-v1",
        (
            _case("deterministic-unit-rank-v1", query_id="q-hard-negative"),
            _case("deterministic-unit-rank-v1"),
        ),
    )
    o2 = grading.seal_mechanism_observation(
        "fixed-rank-delivery-v1",
        (
            _case("fixed-rank-delivery-v1", query_id="q-hard-negative"),
            _case("fixed-rank-delivery-v1"),
        ),
    )
    gates = _derive(payload, o0=o0, o1=o1, o2=o2)

    result = _grade(
        payload,
        gates,
        o0=o0,
        observations=(o1, o2),
    )

    hard_negative = next(item for item in result.case_metrics if item.query_id == "q-hard-negative")
    assert hard_negative.hard_negative_regression is True
    assert result.mechanism_statuses["o1"] == "candidate_failed"


def test_ambiguous_context_attribution_is_recomputed_not_qualified() -> None:
    payload = _payload()
    o0 = _seal("current-runtime-baseline-v1")
    o1 = _seal(
        "deterministic-unit-rank-v1",
        _case("deterministic-unit-rank-v1", selected=False, delivered=()),
    )
    o2 = _seal("fixed-rank-delivery-v1")
    gates = _derive(payload, o0=o0, o1=o1, o2=o2)
    o3 = _seal(
        "source-context-index-v1",
        dataclasses.replace(
            _case(
                "source-context-index-v1",
                delivered=(),
                context=(_range(component_kind="heading"),),
            ),
            context_attribution_unique=False,
        ),
    )

    result = _grade(
        payload,
        gates,
        o0=o0,
        observations=(o1, o2, o3),
    )

    assert result.mechanism_statuses["o3"] == "mechanism_ambiguous"
    assert "mechanism_ambiguous" in result.classifications


def test_false_gate_is_not_evaluated_and_observation_is_rejected() -> None:
    payload = _payload()
    o0 = _seal("current-runtime-baseline-v1")
    o1 = _seal("deterministic-unit-rank-v1")
    o2 = _seal("fixed-rank-delivery-v1")
    gates = _derive(payload, o0=o0, o1=o1, o2=o2)
    o3 = _seal("source-context-index-v1")

    with pytest.raises(ValueError, match="observation"):
        _grade(
            payload,
            gates,
            o0=o0,
            observations=(o1, o2, o3),
        )

    result = _grade(
        payload,
        gates,
        o0=o0,
        observations=(o1, o2),
    )
    assert result.mechanism_statuses["o3"] == "not_evaluated"
    assert result.mechanism_statuses["o4"] == "not_evaluated"
    assert result.mechanism_statuses["o5"] == "not_evaluated"


def test_pure_grader_rejects_workspace_digest_selected_and_case_drift() -> None:
    payload = _payload()
    o0 = _seal("current-runtime-baseline-v1")
    o1 = _seal("deterministic-unit-rank-v1")
    o2 = _seal("fixed-rank-delivery-v1")
    gates = _derive(payload, o0=o0, o1=o1, o2=o2)
    drifted = _seal(
        "deterministic-unit-rank-v1",
        dataclasses.replace(
            _case("deterministic-unit-rank-v1"),
            selected_stable_identities=(),
        ),
    )
    with pytest.raises(ValueError, match="portable observation equality"):
        _grade(
            payload,
            gates,
            o0=o0,
            observations=(o1, o2),
            workspace_b=(drifted, o2),
        )
    duplicate = dataclasses.replace(
        o1,
        cases=(o1.cases[0], o1.cases[0]),
    )
    with pytest.raises(ValueError, match="observation inventory"):
        _grade(
            payload,
            gates,
            o0=o0,
            observations=(duplicate, o2),
        )


def test_grading_module_has_hard_pure_boundaries() -> None:
    source = inspect.getsource(grading)
    forbidden = (
        "KnowledgeEngine",
        "ingest_pdf",
        "search_evidence",
        "agent_context_unit_workflow",
        "_atomic_json_publication",
        "holdout",
        "record_",
        "replay",
    )
    assert all(token not in source for token in forbidden)
