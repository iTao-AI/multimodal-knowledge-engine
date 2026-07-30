from __future__ import annotations

import hashlib
import json

import pytest

from mke.evaluation.agent_context_unit_diagnostics import (
    AgentContextStageError,
    AgentContextStageSuccess,
    AgentContextSubstage,
    build_agent_context_diagnostic_receipt,
    execute_diagnostic_stages,
    render_agent_context_diagnostic_receipt,
    validate_agent_context_diagnostic_receipt,
)


def test_public_substage_order_seals_residual_gate_before_residual_mechanisms() -> None:
    assert tuple(stage.value for stage in AgentContextSubstage) == (
        "authority_preflight",
        "runtime_baseline",
        "source_snapshot",
        "unit_projection",
        "unit_rank",
        "fixed_rank_delivery",
        "residual_gate",
        "adjacent_page_assembly",
        "source_context_index",
        "source_context_delivery",
        "complete_observation_seal",
        "grading",
        "artifact_validation",
        "publication",
    )


def test_receipt_accepts_residual_gate_before_adjacent_page_failure() -> None:
    stage_order = (
        AgentContextSubstage.AUTHORITY_PREFLIGHT,
        AgentContextSubstage.RUNTIME_BASELINE,
        AgentContextSubstage.SOURCE_SNAPSHOT,
        AgentContextSubstage.UNIT_PROJECTION,
        AgentContextSubstage.UNIT_RANK,
        AgentContextSubstage.FIXED_RANK_DELIVERY,
        AgentContextSubstage.RESIDUAL_GATE,
    )
    completed = tuple(
        AgentContextStageSuccess(stage, hashlib.sha256(stage.value.encode()).hexdigest())
        for stage in stage_order
    )
    error = AgentContextStageError(
        AgentContextSubstage.ADJACENT_PAGE_ASSEMBLY,
        "adjacent_page_assembly_invalid",
        "integrity",
        completed=completed,
    )
    receipt = build_agent_context_diagnostic_receipt(
        protocol_sha256="1" * 64,
        profile_sha256="2" * 64,
        evaluator_source_sha256="3" * 64,
        observation_sha256=None,
        phase="development",
        attempt_kind="development",
        observation_started=True,
        completed=completed,
        error=error,
        output_state="absent",
        publication_outcome="not_attempted",
        stderr_bytes=0,
        stderr_sha256=hashlib.sha256(b"").hexdigest(),
    )

    validate_agent_context_diagnostic_receipt(receipt)


@pytest.mark.parametrize("failed_index", range(14))
def test_fault_matrix_stops_at_exact_substage(failed_index: int) -> None:
    calls: list[AgentContextSubstage] = []
    stages = list(AgentContextSubstage)

    def operation(stage: AgentContextSubstage):
        def run() -> bytes:
            calls.append(stage)
            if stage is stages[failed_index]:
                raise AgentContextStageError(stage, "synthetic_failure", "integrity")
            return stage.value.encode()

        return run

    with pytest.raises(AgentContextStageError) as raised:
        execute_diagnostic_stages([(stage, operation(stage)) for stage in stages])

    assert raised.value.substage is stages[failed_index]
    assert raised.value.first_failed_gate == stages[failed_index].value
    assert [item.substage for item in raised.value.completed] == stages[:failed_index]
    assert calls == stages[: failed_index + 1]


def test_unexpected_failure_retains_active_substage() -> None:
    stage = AgentContextSubstage.SOURCE_SNAPSHOT

    def fail() -> bytes:
        raise RuntimeError("private traceback")

    with pytest.raises(AgentContextStageError) as raised:
        execute_diagnostic_stages([(stage, fail)])

    assert raised.value.substage is stage
    assert raised.value.error_code == "unexpected_stage_failure"
    assert raised.value.error_family == "unexpected"
    assert "private traceback" not in str(raised.value)


def test_receipt_is_closed_canonical_private_safe_and_tamper_evident() -> None:
    stages = list(AgentContextSubstage)
    completed = execute_diagnostic_stages(
        [(stage, lambda value=stage.value: value.encode()) for stage in stages[:2]]
    )
    error = AgentContextStageError(
        stages[2],
        "source_snapshot_invalid",
        "integrity",
        completed=completed,
    )
    receipt = build_agent_context_diagnostic_receipt(
        protocol_sha256="1" * 64,
        profile_sha256="2" * 64,
        evaluator_source_sha256="3" * 64,
        observation_sha256=None,
        phase="baseline",
        attempt_kind="o0",
        observation_started=True,
        completed=completed,
        error=error,
        output_state="absent",
        publication_outcome="not_attempted",
        stderr_bytes=7,
        stderr_sha256=hashlib.sha256(b"private").hexdigest(),
    )
    rendered = render_agent_context_diagnostic_receipt(receipt)

    assert rendered.endswith(b"\n")
    assert rendered == (
        json.dumps(
            receipt,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    assert b"/Users/" not in rendered
    assert b"private traceback" not in rendered
    validate_agent_context_diagnostic_receipt(json.loads(rendered))

    tampered = json.loads(rendered)
    tampered["failed_substage"] = "grading"
    with pytest.raises(ValueError, match="invalid"):
        validate_agent_context_diagnostic_receipt(tampered)


def test_complete_stage_sequence_emits_no_receipt() -> None:
    stages = list(AgentContextSubstage)
    result = execute_diagnostic_stages(
        [(stage, lambda value=stage.value: value.encode()) for stage in stages]
    )
    assert [item.substage for item in result] == stages
