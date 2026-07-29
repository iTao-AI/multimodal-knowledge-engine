from __future__ import annotations

import hashlib
import json
from typing import cast

import pytest

from mke.application.evidence_access import EvidenceExcerpt
from mke.evaluation.agent_context_unit_baseline_artifact import (
    build_agent_context_unit_baseline_artifact,
    render_agent_context_unit_baseline_artifact,
    validate_agent_context_unit_baseline_artifact,
    validate_agent_context_unit_baseline_artifact_live,
)
from mke.evaluation.agent_context_unit_grading_protocol import (
    AgentContextBaselineGradingPayload,
    AgentContextRequiredSpan,
)
from mke.evaluation.agent_context_unit_observation import (
    PortableObservation,
    PortableObservationItem,
    PortableScoreToken,
    seal_portable_observations,
)


def _span() -> AgentContextRequiredSpan:
    return AgentContextRequiredSpan(
        span_id="span-one",
        query_id="q-target",
        source_content_fingerprint="sha256:" + "1" * 64,
        locator_kind="page",
        locator_start=1,
        locator_end=1,
        start_utf8_byte=5,
        end_utf8_byte=10,
        text_sha256="2" * 64,
        role="answer",
        hypothesis="page_internal",
        control="current_success",
    )


def _observation(*, covered: bool) -> bytes:
    item = PortableObservationItem(
        content_fingerprint="sha256:" + "1" * 64,
        locator_kind="page",
        locator_start=1,
        locator_end=1,
        text_sha256="sha256:" + "2" * 64,
        route="fts5",
        rank=1,
        score=PortableScoreToken("fts5_rank", (-1.0).hex(), (-1.0).hex()),
        hints=("target",),
        excerpt=EvidenceExcerpt(
            "query_window",
            "0123456789abcdef",
            0 if covered else 10,
            16 if covered else 26,
            False,
            False,
            True,
            16,
        ),
        exact_read_sha256="sha256:" + "2" * 64,
        original_utf8_bytes=16,
        excerpt_utf8_bytes=16,
        exact_read_utf8_bytes=16,
    )
    observation = PortableObservation(
        query_id="q-target",
        query_text="target",
        expected_route="fts5",
        profile_identity="current-runtime-baseline-v1",
        statuses=(
            "query_policy_hit",
            "candidate_hit",
            "rank_hit",
            "delivery_hit",
            "output_complete",
            "exact_read_complete",
            "provenance_complete",
        ),
        items=(item,),
        candidate_count=1,
        selected_count=1,
        delivered_utf8_bytes=16,
    )
    return seal_portable_observations((observation,)).bytes


def _build(*, covered: bool) -> dict[str, object]:
    return build_agent_context_unit_baseline_artifact(
        sealed_observation_bytes=_observation(covered=covered),
        grading_payload=AgentContextBaselineGradingPayload((_span(),)),
        candidate_target_query_ids=("q-target",),
        protocol_sha256="3" * 64,
        evaluator_source_sha256="4" * 64,
        runtime_profile={"python": "3.13"},
        fixture_sha256="5" * 64,
    )


@pytest.mark.parametrize(
    ("covered", "outcome"),
    ((False, "baseline_red_observed"), (True, "docs_regression_only")),
)
def test_pure_builder_recomputes_targeted_failure(
    covered: bool, outcome: str
) -> None:
    artifact = _build(covered=covered)
    rendered = render_agent_context_unit_baseline_artifact(artifact)

    assert artifact["stage_outcome"] == outcome
    assert artifact["mechanism_statuses"] == {
        "adjacent-page-assembly-v1": "not_evaluated",
        "deterministic-unit-rank-v1": "not_evaluated",
        "fixed-rank-delivery-v1": "not_evaluated",
        "source-context-delivery-v1": "not_evaluated",
        "source-context-index-v1": "not_evaluated",
    }
    assert artifact["holdout_status"] == "not_evaluated"
    assert artifact["runtime_promotion_status"] == "not_evaluated"
    assert artifact["role_coverage"] == [
        {
            "complete": covered,
            "covered": int(covered),
            "query_id": "q-target",
            "required": 1,
            "role": "answer",
        }
    ]
    assert b"duration" not in rendered
    validate_agent_context_unit_baseline_artifact(
        json.loads(rendered),
        AgentContextBaselineGradingPayload((_span(),)),
    )


def test_retained_validator_rejects_tamper_without_live_source_access() -> None:
    artifact = _build(covered=False)
    artifact["stage_outcome"] = "docs_regression_only"
    with pytest.raises(ValueError, match="artifact"):
        validate_agent_context_unit_baseline_artifact(
            artifact, AgentContextBaselineGradingPayload((_span(),))
        )


def test_retained_validator_rejects_unknown_sealed_observation_fields() -> None:
    artifact = _build(covered=False)
    observation_value = artifact["observation"]
    assert isinstance(observation_value, dict)
    observation = cast(dict[str, object], observation_value)
    rows_value = observation["observations"]
    assert isinstance(rows_value, list)
    rows = cast(list[object], rows_value)
    row = rows[0]
    assert isinstance(row, dict)
    cast(dict[str, object], row)["unknown"] = "not-closed"
    artifact["observation_sha256"] = hashlib.sha256(
        (
            json.dumps(
                observation,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()
    ).hexdigest()
    body = dict(artifact)
    del body["content_digest"]
    artifact["content_digest"] = hashlib.sha256(
        json.dumps(
            body, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode()
    ).hexdigest()

    with pytest.raises(ValueError, match="sealed observation"):
        validate_agent_context_unit_baseline_artifact(
            artifact, AgentContextBaselineGradingPayload((_span(),))
        )


def test_strict_live_validator_is_separate() -> None:
    artifact = _build(covered=False)
    validate_agent_context_unit_baseline_artifact_live(
        artifact,
        AgentContextBaselineGradingPayload((_span(),)),
        protocol_sha256="3" * 64,
        evaluator_source_sha256="4" * 64,
        fixture_sha256="5" * 64,
    )
    with pytest.raises(ValueError, match="live"):
        validate_agent_context_unit_baseline_artifact_live(
            artifact,
            AgentContextBaselineGradingPayload((_span(),)),
            protocol_sha256="6" * 64,
            evaluator_source_sha256="4" * 64,
            fixture_sha256="5" * 64,
        )
