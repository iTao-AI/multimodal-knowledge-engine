from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from mke.evaluation import agent_context_unit_artifact as artifact
from mke.evaluation import agent_context_unit_grading as grading
from mke.evaluation import agent_context_unit_grading_protocol as grading_protocol

SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64
LOCK = json.loads(
    Path("tests/fixtures/agent-context-unit-v2/scientific-input-lock.json").read_bytes()
)


def _payload() -> grading_protocol.AgentContextDevelopmentGradingPayload:
    return grading_protocol.AgentContextDevelopmentGradingPayload(
        required_spans=(
            grading_protocol.AgentContextRequiredSpan(
                span_id="span",
                query_id="q",
                source_content_fingerprint=SHA_A,
                locator_kind="page",
                locator_start=1,
                locator_end=1,
                start_utf8_byte=0,
                end_utf8_byte=5,
                text_sha256=DIGEST_A,
                role="answer",
                hypothesis="page_internal",
                control="target",
            ),
        ),
        query_ids=("q",),
        observation_ids_by_query={
            "q": (
                "current-runtime-baseline-v1",
                "deterministic-unit-rank-v1",
                "fixed-rank-delivery-v1",
            )
        },
        expected_routes_by_query={"q": "fts5"},
        query_text_by_query={"q": "alpha"},
        query_terms_by_query={"q": ("alpha",)},
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
                "source-context-index-heading-v1",
                "source-context-index-next-unit-v1",
                "source-context-index-previous-unit-v1",
                "source-context-index-unit-v1",
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
        scientific_nonclaims=tuple(LOCK["scientific_nonclaims"]),
    )


def _seal(
    mechanism_id: str,
    *,
    selected: bool,
    delivered: bool,
) -> grading.SealedMechanismObservation:
    stable_id = "sha256:" + "d" * 64
    span = grading.ObservedRange(
        source_content_fingerprint=SHA_A,
        locator_kind="page",
        locator_start=1,
        locator_end=1,
        start_utf8_byte=0,
        end_utf8_byte=5,
        origin_evidence_ref=SHA_B,
        component_kind="unit",
    )
    case = grading.MechanismCaseObservation(
        query_id="q",
        mechanism_id=mechanism_id,
        route="fts",
        rank_profile_id=(
            "current-runtime-baseline-v1"
            if mechanism_id == "current-runtime-baseline-v1"
            else "deterministic-unit-rank-v1"
        ),
        query_terms=("alpha",),
        retrieval_text="alpha",
        candidate_count=1,
        unique_parent_count=1,
        ranked=(
            grading.ObservedRankedCandidate(
                stable_identity=stable_id,
                rank=1,
                parent_collapsed_rank=1,
                authority_range=span,
            ),
        ),
        selected_stable_identities=((stable_id,) if selected else ()),
        delivered_ranges=((span,) if delivered else ()),
        context_ranges=(),
        delivered_utf8_bytes=(5 if delivered else 0),
        context_attribution_unique=True,
        output_complete=True,
        exact_read_complete=True,
        provenance_exact=True,
    )
    return grading.seal_mechanism_observation(mechanism_id, (case,))


def _observations() -> tuple[
    grading.SealedMechanismObservation,
    tuple[grading.SealedMechanismObservation, ...],
]:
    baseline = _seal("current-runtime-baseline-v1", selected=False, delivered=False)
    workspace = (
        _seal("deterministic-unit-rank-v1", selected=True, delivered=False),
        _seal("fixed-rank-delivery-v1", selected=True, delivered=True),
    )
    return baseline, workspace


def _gates() -> grading.ResidualGateSet:
    baseline, workspace = _observations()
    return grading.derive_residual_gates(
        _payload(),
        o0_artifact_sha256=_authority().baseline_artifact_sha256,
        o0=baseline,
        o1=workspace[0],
        o2=workspace[1],
    )


def _grading() -> grading.DevelopmentGradingResult:
    baseline, workspace = _observations()
    return grading.grade_context_mechanisms(
        _payload(),
        _gates(),
        baseline_observation=baseline,
        o0_artifact_sha256=_authority().baseline_artifact_sha256,
        workspace_a=workspace,
        workspace_b=workspace,
    )


def _authority() -> artifact.DevelopmentArtifactAuthority:
    return artifact.DevelopmentArtifactAuthority(
        protocol_sha256=DIGEST_A,
        evaluator_source_sha256=DIGEST_B,
        fixture_sha256=DIGEST_C,
        baseline_artifact_sha256="1" * 64,
        baseline_content_digest="2" * 64,
        runtime_profile_sha256="3" * 64,
    )


def _digest(value: object) -> str:
    content = (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode()
    return hashlib.sha256(content).hexdigest()


def _content() -> bytes:
    baseline, workspace = _observations()
    return artifact.build_agent_context_unit_development_artifact(
        authority=_authority(),
        grading_payload=_payload(),
        baseline_observation=baseline,
        workspace_a=workspace,
        workspace_b=workspace,
        gates=_gates(),
        grading=_grading(),
        limitations=(
            "constructed_development_corpus",
            "public_nonblind_future_holdout",
        ),
        nonclaims=("comparison_only", "no_runtime_promotion"),
    )


def test_artifact_builder_rejects_contradictory_observation_and_grading() -> None:
    baseline, workspace = _observations()
    contradictory = grading.build_development_grading_result(
        case_metrics=(),
        classifications=("not_observed_under_protocol",),
        mechanism_statuses={
            "o1": "not_evaluated",
            "o2": "not_evaluated",
            "o3": "not_evaluated",
            "o4": "not_evaluated",
            "o5": "not_evaluated",
        },
        deterministic_equality=True,
    )

    with pytest.raises(ValueError, match="development artifact grading"):
        artifact.build_agent_context_unit_development_artifact(
            authority=_authority(),
            grading_payload=_payload(),
            baseline_observation=baseline,
            workspace_a=workspace,
            workspace_b=workspace,
            gates=_gates(),
            grading=contradictory,
            limitations=("constructed_development_corpus",),
            nonclaims=("comparison_only", "no_runtime_promotion"),
        )


def test_retained_validation_regrades_coordinated_portable_forgery() -> None:
    record = json.loads(_content())
    case = record["workspace_observations"]["workspace_a"][0]["portable"]["cases"][0]
    case["retrieval_text"] = "forged"
    for workspace in ("workspace_a", "workspace_b"):
        entry = record["workspace_observations"][workspace][0]
        entry["portable"]["cases"][0]["retrieval_text"] = "forged"
        portable_bytes = (
            json.dumps(
                entry["portable"],
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()
        entry["portable_sha256"] = hashlib.sha256(portable_bytes).hexdigest()
    observations = record["workspace_observations"]["workspace_a"]
    observations_sha = _digest(observations)
    record["workspace_equality"]["workspace_a_sha256"] = observations_sha
    record["workspace_equality"]["workspace_b_sha256"] = observations_sha
    for metric in record["grading"]["case_metrics"]:
        if metric["mechanism_id"] == "deterministic-unit-rank-v1":
            metric["token_presence"] = False
    classifications = sorted(
        {*record["grading"]["classifications"], "query_policy_miss"}
    )
    statuses = dict(record["grading"]["mechanism_statuses"])
    statuses["o1"] = "candidate_failed"
    grading_digest = _digest(
        {
            "aggregate_metrics": record["grading"]["aggregate_metrics"],
            "case_metrics": record["grading"]["case_metrics"],
            "classifications": classifications,
            "deterministic_equality": True,
            "mechanism_statuses": statuses,
            "schema_version": "mke.agent_context_unit_development_grading.v1",
        }
    )
    record["grading"]["classifications"] = classifications
    record["grading"]["mechanism_statuses"] = statuses
    record["grading"]["grading_digest"] = grading_digest
    record["classifications"] = classifications
    record["mechanism_statuses"] = statuses
    record["workspace_equality"]["grading_digest"] = grading_digest
    record["stage_outcome"] = "candidate_failed"
    record["content_digest"] = artifact.development_artifact_content_digest(record)
    forged = (
        json.dumps(record, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()

    with pytest.raises(ValueError, match="development artifact"):
        artifact.validate_agent_context_unit_development_artifact(forged)


def test_development_artifact_binds_recorded_authority_and_observations() -> None:
    content = _content()
    parsed = artifact.validate_agent_context_unit_development_artifact(content)

    assert parsed["schema_version"] == "mke.agent_context_unit_development.v2"
    assert parsed["status"] == "passed"
    assert parsed["integrity_status"] == "passed"
    assert parsed["holdout_status"] == "not_evaluated"
    assert parsed["runtime_promotion_status"] == "not_evaluated"
    assert parsed["authority"]["protocol_sha256"] == DIGEST_A
    assert parsed["workspace_equality"]["equal"] is True
    assert (
        parsed["workspace_equality"]["workspace_a_sha256"]
        == (parsed["workspace_equality"]["workspace_b_sha256"])
    )
    assert content.endswith(b"\n")
    assert artifact.validate_agent_context_unit_development_artifact(content) == parsed


def test_retained_validation_is_separate_from_strict_live_authority() -> None:
    content = _content()
    artifact.validate_agent_context_unit_development_artifact(content)
    artifact.validate_agent_context_unit_development_artifact_live(
        content,
        authority=_authority(),
    )
    with pytest.raises(ValueError, match="strict-live authority"):
        artifact.validate_agent_context_unit_development_artifact_live(
            content,
            authority=dataclasses.replace(
                _authority(),
                evaluator_source_sha256="9" * 64,
            ),
        )
    artifact.validate_agent_context_unit_development_artifact(content)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("holdout_status",), "passed"),
        (("runtime_promotion_status",), "candidate"),
        (("workspace_equality", "equal"), False),
        (("mechanism_statuses", "o3"), "candidate_qualified"),
    ],
)
def test_artifact_rejects_self_consistent_semantic_forgery(
    path: tuple[str, ...],
    value: object,
) -> None:
    record = json.loads(_content())
    target = record
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    record["content_digest"] = artifact.development_artifact_content_digest(record)
    forged = (
        json.dumps(record, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()

    with pytest.raises(ValueError, match="development artifact"):
        artifact.validate_agent_context_unit_development_artifact(forged)


def test_artifact_rejects_capacity_and_shape_before_nested_parse() -> None:
    with pytest.raises(ValueError, match="development artifact capacity"):
        artifact.validate_agent_context_unit_development_artifact(
            b"{" + b"x" * (4 * 1024 * 1024) + b"}"
        )
    with pytest.raises(ValueError, match="development artifact"):
        artifact.validate_agent_context_unit_development_artifact(b"[]\n")


def test_artifact_module_has_no_observation_or_publication_capability() -> None:
    source = inspect.getsource(artifact)
    forbidden = (
        "KnowledgeEngine",
        "ingest_pdf",
        "search_evidence",
        "agent_context_unit_workflow",
        "_atomic_json_publication",
        "holdout-receipt",
        "record_",
        "replay",
    )
    assert all(token not in source for token in forbidden)
