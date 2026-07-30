"""Thin command workflow for diagnostic-first O0 observation and pure validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import sqlite3
import stat
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol, cast

import pymupdf

from mke.evaluation._atomic_json_publication import publish_json_no_replace
from mke.evaluation.agent_context_unit_baseline import (
    run_agent_context_unit_baseline,
)
from mke.evaluation.agent_context_unit_diagnostics import (
    AgentContextStageError,
    AgentContextStageSuccess,
    AgentContextSubstage,
    build_agent_context_diagnostic_receipt,
    render_agent_context_diagnostic_receipt,
    run_diagnostic_stage,
    validate_agent_context_diagnostic_receipt,
)
from mke.evaluation.agent_context_unit_observation import (
    AuthorityObservation,
    seal_portable_observations,
)
from mke.evaluation.agent_context_unit_observer_protocol import (
    AgentContextObserverContract,
    load_agent_context_unit_observer_contract,
)
from mke.evaluation.agent_context_unit_protocol import (
    AgentContextProtocolAuthority,
    build_agent_context_unit_observer_authority,
    load_agent_context_unit_protocol_authority,
)
from mke.evaluation.source_identity import build_source_identity

_BARE_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
PUBLIC_RESULT_FIELDS = {
    "cause",
    "diagnostic_receipt_sha256",
    "diagnostic_receipt_status",
    "first_failed_gate",
    "holdout_status",
    "integrity_status",
    "mechanism_statuses",
    "next_step",
    "output_state",
    "phase",
    "problem",
    "publication_outcome",
    "runtime_promotion_status",
    "schema_version",
    "stage_outcome",
    "status",
}
_MECHANISMS = {
    "adjacent-page-assembly-v1": "not_evaluated",
    "deterministic-unit-rank-v1": "not_evaluated",
    "fixed-rank-delivery-v1": "not_evaluated",
    "source-context-delivery-v1": "not_evaluated",
    "source-context-index-v1": "not_evaluated",
}
_RUNTIME_SOURCE_PATHS = (
    "src/mke/adapters/sqlite/__init__.py",
    "src/mke/application/__init__.py",
    "src/mke/application/evidence_access.py",
    "src/mke/domain/library_export.py",
    "src/mke/retrieval/cjk_active_scan.py",
    "src/mke/retrieval/query_policy.py",
    "src/mke/retrieval/strategy.py",
)


@dataclass(frozen=True)
class CandidateIntermediateObservation:
    observations: tuple[object, ...]
    source_snapshot_bytes: bytes
    unit_projection_bytes: bytes
    unit_rank_bytes: bytes
    fixed_rank_delivery_bytes: bytes

    def __post_init__(self) -> None:
        if (
            type(self.observations) is not tuple
            or len(self.observations) != 2
            or any(type(item) is not bytes for item in self.stage_bytes)
        ):
            raise ValueError("candidate intermediate observation is invalid")

    @property
    def stage_bytes(self) -> tuple[bytes, ...]:
        return (
            self.source_snapshot_bytes,
            self.unit_projection_bytes,
            self.unit_rank_bytes,
            self.fixed_rank_delivery_bytes,
        )


@dataclass(frozen=True)
class CandidateGateDispatch:
    mechanism_id: str
    enabled: bool
    reason: str
    query_ids: tuple[str, ...]
    gate_digest: str

    def __post_init__(self) -> None:
        if (
            type(self.mechanism_id) is not str
            or not self.mechanism_id
            or type(self.enabled) is not bool
            or type(self.reason) is not str
            or not self.reason
            or type(self.query_ids) is not tuple
            or tuple(sorted(self.query_ids, key=str.encode)) != self.query_ids
            or len(set(self.query_ids)) != len(self.query_ids)
            or any(type(item) is not str or not item for item in self.query_ids)
            or _BARE_SHA256.fullmatch(self.gate_digest) is None
        ):
            raise ValueError("candidate gate dispatch is invalid")


@dataclass(frozen=True)
class CandidateResidualObservation:
    observations: tuple[object, ...]
    gate_digest: str
    adjacent_page_assembly_bytes: bytes
    source_context_index_bytes: bytes
    source_context_delivery_bytes: bytes

    def __post_init__(self) -> None:
        if (
            type(self.observations) is not tuple
            or _BARE_SHA256.fullmatch(self.gate_digest) is None
            or any(type(item) is not bytes for item in self.stage_bytes)
        ):
            raise ValueError("candidate residual observation is invalid")

    @property
    def stage_bytes(self) -> tuple[bytes, ...]:
        return (
            self.adjacent_page_assembly_bytes,
            self.source_context_index_bytes,
            self.source_context_delivery_bytes,
        )


class DevelopmentWorkspaceDriver(Protocol):
    def observe_o1_o2(self) -> CandidateIntermediateObservation: ...

    def observe_residual(
        self,
        dispatches: tuple[CandidateGateDispatch, ...],
    ) -> CandidateResidualObservation: ...


DevelopmentDriverFactory = Callable[
    [
        AgentContextObserverContract,
        Path,
        Path,
        Callable[[], None],
    ],
    DevelopmentWorkspaceDriver,
]


def _result(
    *,
    status: str,
    integrity_status: str,
    stage_outcome: str,
    output_state: str,
    publication_outcome: str,
    problem: str = "none",
    cause: str = "none",
    next_step: str = "none",
    first_failed_gate: str = "none",
    diagnostic_receipt_status: str = "absent",
    diagnostic_receipt_sha256: str | None = None,
    phase: str = "baseline",
    mechanism_statuses: Mapping[str, str] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "schema_version": "mke.agent_context_unit_result.v2",
        "status": status,
        "phase": phase,
        "integrity_status": integrity_status,
        "stage_outcome": stage_outcome,
        "mechanism_statuses": dict(
            _MECHANISMS if mechanism_statuses is None else mechanism_statuses
        ),
        "holdout_status": "not_evaluated",
        "runtime_promotion_status": "not_evaluated",
        "output_state": output_state,
        "publication_outcome": publication_outcome,
        "problem": problem,
        "cause": cause,
        "next_step": next_step,
        "first_failed_gate": first_failed_gate,
        "diagnostic_receipt_status": diagnostic_receipt_status,
        "diagnostic_receipt_sha256": diagnostic_receipt_sha256,
    }
    if set(result) != PUBLIC_RESULT_FIELDS:
        raise AssertionError("public result field inventory drifted")
    return result


def _render_result(value: dict[str, object]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def execute_baseline(
    *,
    protocol_path: Path,
    record_path: Path,
    diagnostic_receipt_path: Path,
    baseline_runner: Callable[
        [AgentContextObserverContract, Path, Path, Callable[[], None]],
        tuple[AuthorityObservation, ...],
    ]
    | None = None,
) -> tuple[int, dict[str, object]]:
    observation_started = False
    observation_sha256: str | None = None
    output_state = "absent"
    publication_outcome = "not_attempted"
    completed: list[AgentContextStageSuccess] = []
    retained_authority: dict[str, object] | None = None
    try:
        protocol_authority, contract, authority = _preflight(
            protocol_path,
            record_path,
            diagnostic_receipt_path,
        )
        repository_root = protocol_authority.repository_root
        retained_authority = authority
        completed.append(
            run_diagnostic_stage(
                AgentContextSubstage.AUTHORITY_PREFLIGHT,
                lambda: _canonical(authority),
            )
        )
        workspace_root = Path(
            tempfile.mkdtemp(prefix="mke-agent-context-v2-baseline-")
        )
        workspace = workspace_root / "workspace"
        runner = baseline_runner or _default_baseline_runner

        def mark_observation_started() -> None:
            nonlocal observation_started
            observation_started = True

        observations = _run_stage(
            AgentContextSubstage.RUNTIME_BASELINE,
            lambda: runner(
                contract,
                repository_root,
                workspace,
                mark_observation_started,
            ),
            completed,
        )
        sealed = seal_portable_observations(
            tuple(item.portable for item in observations)
        )
        observation_sha256 = sealed.sha256.removeprefix("sha256:")
        completed.append(
            AgentContextStageSuccess(
                AgentContextSubstage.RUNTIME_BASELINE, observation_sha256
            )
        )
        for stage in (
            AgentContextSubstage.SOURCE_SNAPSHOT,
            AgentContextSubstage.UNIT_PROJECTION,
            AgentContextSubstage.UNIT_RANK,
            AgentContextSubstage.FIXED_RANK_DELIVERY,
            AgentContextSubstage.ADJACENT_PAGE_ASSEMBLY,
            AgentContextSubstage.SOURCE_CONTEXT_INDEX,
            AgentContextSubstage.SOURCE_CONTEXT_DELIVERY,
            AgentContextSubstage.RESIDUAL_GATE,
        ):
            completed.append(run_diagnostic_stage(stage, lambda value=stage: value.value.encode()))
        completed.append(
            run_diagnostic_stage(
                AgentContextSubstage.COMPLETE_OBSERVATION_SEAL,
                lambda: sealed.bytes,
            )
        )
        from mke.evaluation.agent_context_unit_baseline_artifact import (
            build_agent_context_unit_baseline_artifact,
            render_agent_context_unit_baseline_artifact,
            validate_agent_context_unit_baseline_artifact,
        )
        from mke.evaluation.agent_context_unit_grading_protocol import (
            load_agent_context_unit_baseline_grading_payload,
        )

        grading_payload = load_agent_context_unit_baseline_grading_payload(
            protocol_authority
        )
        targets = tuple(
            case.query_id
            for case in contract.cases
            if len(case.observation_ids) > 1
        )
        artifact = build_agent_context_unit_baseline_artifact(
            sealed_observation_bytes=sealed.bytes,
            grading_payload=grading_payload,
            candidate_target_query_ids=targets,
            protocol_sha256=cast(str, authority["protocol_sha256"]),
            evaluator_source_sha256=cast(
                str, authority["evaluator_source_sha256"]
            ),
            runtime_profile=cast(dict[str, object], authority["runtime_profile"]),
            fixture_sha256=cast(str, authority["fixture_sha256"]),
        )
        artifact_bytes = render_agent_context_unit_baseline_artifact(artifact)
        completed.append(
            run_diagnostic_stage(
                AgentContextSubstage.GRADING, lambda: _canonical(artifact["coverage"])
            )
        )
        validate_agent_context_unit_baseline_artifact(artifact, grading_payload)
        completed.append(
            run_diagnostic_stage(
                AgentContextSubstage.ARTIFACT_VALIDATION,
                lambda: artifact_bytes,
            )
        )
        publication = publish_json_no_replace(
            record_path,
            artifact_bytes,
            validate=lambda value: validate_agent_context_unit_baseline_artifact(
                value, grading_payload
            ),
        )
        output_state = publication.output_state
        publication_outcome = publication.publication_outcome
        if (
            publication.output_state != "complete_visible"
            or publication.publication_outcome != "published"
        ):
            raise AgentContextStageError(
                AgentContextSubstage.PUBLICATION,
                publication.cause or "publication_failed",
                "publication",
                completed=tuple(completed),
            )
        completed.append(
            run_diagnostic_stage(
                AgentContextSubstage.PUBLICATION, lambda: artifact_bytes
            )
        )
        return 0, _result(
            status="passed",
            integrity_status="passed",
            stage_outcome=cast(str, artifact["stage_outcome"]),
            output_state=publication.output_state,
            publication_outcome=publication.publication_outcome,
        )
    except AgentContextStageError as error:
        return _failure_result(
            error=error,
            observation_started=observation_started,
            diagnostic_receipt_path=diagnostic_receipt_path,
            retained_authority=retained_authority,
            observation_sha256=observation_sha256,
            output_state=output_state,
            publication_outcome=publication_outcome,
        )
    except Exception:
        error = AgentContextStageError(
            (
                AgentContextSubstage.RUNTIME_BASELINE
                if observation_started
                else AgentContextSubstage.AUTHORITY_PREFLIGHT
            ),
            "unexpected_stage_failure",
            "unexpected",
            completed=tuple(completed),
        )
        return _failure_result(
            error=error,
            observation_started=observation_started,
            diagnostic_receipt_path=diagnostic_receipt_path,
            retained_authority=retained_authority,
            observation_sha256=observation_sha256,
            output_state=output_state,
            publication_outcome=publication_outcome,
        )


def execute_development(
    *,
    protocol_path: Path,
    baseline_path: Path,
    record_path: Path,
    diagnostic_receipt_path: Path,
    development_driver_factory: DevelopmentDriverFactory | None = None,
    stage_faults: Mapping[
        AgentContextSubstage, Callable[[], None]
    ] | None = None,
    synthetic_noncanonical: bool = False,
) -> tuple[int, dict[str, object]]:
    observation_started = False
    observation_sha256: str | None = None
    output_state = "absent"
    publication_outcome = "not_attempted"
    completed: list[AgentContextStageSuccess] = []
    retained_authority: dict[str, object] | None = None
    faults = dict(stage_faults or {})
    try:
        protocol_authority, contract, authority = _preflight(
            protocol_path,
            record_path,
            diagnostic_receipt_path,
        )
        repository_root = protocol_authority.repository_root
        if not synthetic_noncanonical and record_path.absolute() != (
            repository_root
            / "benchmarks/retrieval/agent-context-unit-v2-development.json"
        ):
            raise AgentContextStageError(
                AgentContextSubstage.AUTHORITY_PREFLIGHT,
                "development_output_path_invalid",
                "authority",
            )
        metadata = protocol_authority.metadata
        candidate_source = build_source_identity(
            repository_root,
            metadata.development_evaluator_paths,
        )
        retained_authority = {
            **authority,
            "evaluator_source_sha256": candidate_source["sha256"],
        }
        _complete_development_stage(
            AgentContextSubstage.AUTHORITY_PREFLIGHT,
            _canonical(retained_authority),
            completed,
            faults,
        )

        from mke.evaluation.agent_context_unit_baseline_artifact import (
            load_retained_agent_context_unit_baseline_authority,
        )

        baseline_read = _read_no_follow_absolute(baseline_path)
        retained_baseline = load_retained_agent_context_unit_baseline_authority(
            baseline_read
        )
        if (
            retained_baseline.protocol_sha256
            != retained_authority["protocol_sha256"]
            or retained_baseline.fixture_sha256
            != retained_authority["fixture_sha256"]
        ):
            raise AgentContextStageError(
                AgentContextSubstage.RUNTIME_BASELINE,
                "retained_baseline_authority_invalid",
                "authority",
                completed=tuple(completed),
            )
        _complete_development_stage(
            AgentContextSubstage.RUNTIME_BASELINE,
            retained_baseline.content,
            completed,
            faults,
        )

        workspace_root = Path(
            tempfile.mkdtemp(prefix="mke-agent-context-v2-development-")
        )
        factory = (
            development_driver_factory
            or _default_development_driver_factory
        )

        def mark_observation_started() -> None:
            nonlocal observation_started
            observation_started = True

        drivers = (
            factory(
                contract,
                repository_root,
                workspace_root / "workspace-a",
                mark_observation_started,
            ),
            factory(
                contract,
                repository_root,
                workspace_root / "workspace-b",
                mark_observation_started,
            ),
        )
        intermediate = tuple(driver.observe_o1_o2() for driver in drivers)
        if any(
            type(item) is not CandidateIntermediateObservation
            for item in intermediate
        ):
            raise AgentContextStageError(
                AgentContextSubstage.SOURCE_SNAPSHOT,
                "candidate_intermediate_observation_invalid",
                "integrity",
                completed=tuple(completed),
            )
        intermediate = cast(
            tuple[
                CandidateIntermediateObservation,
                CandidateIntermediateObservation,
            ],
            intermediate,
        )
        for stage, index in (
            (AgentContextSubstage.SOURCE_SNAPSHOT, 0),
            (AgentContextSubstage.UNIT_PROJECTION, 1),
        ):
            _require_workspace_stage_equality(
                intermediate[0].stage_bytes[index],
                intermediate[1].stage_bytes[index],
                stage,
                "workspace_intermediate_portable_mismatch",
                completed,
            )
            _complete_development_stage(
                stage,
                intermediate[0].stage_bytes[index],
                completed,
                faults,
            )
        base_a = _sealed_observation_inventory(
            intermediate[0].observations,
            expected_count=2,
        )
        base_b = _sealed_observation_inventory(
            intermediate[1].observations,
            expected_count=2,
        )
        if _sealed_inventory_bytes(base_a) != _sealed_inventory_bytes(base_b):
            raise AgentContextStageError(
                AgentContextSubstage.UNIT_RANK,
                "workspace_intermediate_portable_mismatch",
                "integrity",
                completed=tuple(completed),
            )
        for stage, index in (
            (AgentContextSubstage.UNIT_RANK, 2),
            (AgentContextSubstage.FIXED_RANK_DELIVERY, 3),
        ):
            _require_workspace_stage_equality(
                intermediate[0].stage_bytes[index],
                intermediate[1].stage_bytes[index],
                stage,
                "workspace_intermediate_portable_mismatch",
                completed,
            )
            _complete_development_stage(
                stage,
                intermediate[0].stage_bytes[index],
                completed,
                faults,
            )

        from mke.evaluation import agent_context_unit_grading_protocol
        from mke.evaluation.agent_context_unit_baseline_artifact import (
            build_retained_agent_context_baseline_observation,
        )
        from mke.evaluation.agent_context_unit_grading import (
            derive_residual_gates,
        )

        grading_payload = (
            agent_context_unit_grading_protocol
            .load_agent_context_unit_development_grading_payload(
                protocol_authority
            )
        )
        baseline_observation: Any = (
            build_retained_agent_context_baseline_observation(
                retained_baseline,
                grading_payload,
            )
        )
        by_mechanism = {
            item.mechanism_id: item for item in base_a
        }
        gates = derive_residual_gates(
            grading_payload,
            o0_artifact_sha256=retained_baseline.artifact_sha256,
            o0=baseline_observation,
            o1=by_mechanism[grading_payload.mechanism_ids["o1"]],
            o2=by_mechanism[grading_payload.mechanism_ids["o2"]],
        )
        dispatches = _gate_dispatches(grading_payload, gates)
        residual = tuple(
            driver.observe_residual(dispatches) for driver in drivers
        )
        if any(
            type(item) is not CandidateResidualObservation
            for item in residual
        ):
            raise AgentContextStageError(
                AgentContextSubstage.ADJACENT_PAGE_ASSEMBLY,
                "candidate_residual_observation_invalid",
                "integrity",
                completed=tuple(completed),
            )
        residual = cast(
            tuple[
                CandidateResidualObservation,
                CandidateResidualObservation,
            ],
            residual,
        )
        for stage, index in (
            (AgentContextSubstage.ADJACENT_PAGE_ASSEMBLY, 0),
            (AgentContextSubstage.SOURCE_CONTEXT_INDEX, 1),
            (AgentContextSubstage.SOURCE_CONTEXT_DELIVERY, 2),
        ):
            _require_workspace_stage_equality(
                residual[0].stage_bytes[index],
                residual[1].stage_bytes[index],
                stage,
                (
                    "source_context_attribution_mismatch"
                    if stage
                    in {
                        AgentContextSubstage.SOURCE_CONTEXT_INDEX,
                        AgentContextSubstage.SOURCE_CONTEXT_DELIVERY,
                    }
                    else "workspace_complete_portable_mismatch"
                ),
                completed,
            )
            _complete_development_stage(
                stage,
                residual[0].stage_bytes[index],
                completed,
                faults,
            )
        if any(item.gate_digest != gates.gate_digest for item in residual):
            raise AgentContextStageError(
                AgentContextSubstage.RESIDUAL_GATE,
                "residual_gate_dispatch_mismatch",
                "authority",
                completed=tuple(completed),
            )
        _complete_development_stage(
            AgentContextSubstage.RESIDUAL_GATE,
            _canonical(
                {
                    "dispatches": [
                        {
                            "enabled": item.enabled,
                            "gate_digest": item.gate_digest,
                            "mechanism_id": item.mechanism_id,
                            "query_ids": item.query_ids,
                            "reason": item.reason,
                        }
                        for item in dispatches
                    ]
                }
            ),
            completed,
            faults,
        )
        residual_a = _sealed_observation_inventory(
            residual[0].observations
        )
        residual_b = _sealed_observation_inventory(
            residual[1].observations
        )
        complete_a = tuple(
            sorted(
                (*base_a, *residual_a),
                key=lambda item: item.mechanism_id.encode(),
            )
        )
        complete_b = tuple(
            sorted(
                (*base_b, *residual_b),
                key=lambda item: item.mechanism_id.encode(),
            )
        )
        complete_bytes = _sealed_inventory_bytes(complete_a)
        if complete_bytes != _sealed_inventory_bytes(complete_b):
            raise AgentContextStageError(
                AgentContextSubstage.COMPLETE_OBSERVATION_SEAL,
                "workspace_complete_portable_mismatch",
                "integrity",
                completed=tuple(completed),
            )
        observation_sha256 = hashlib.sha256(complete_bytes).hexdigest()
        _complete_development_stage(
            AgentContextSubstage.COMPLETE_OBSERVATION_SEAL,
            complete_bytes,
            completed,
            faults,
        )

        from mke.evaluation.agent_context_unit_artifact import (
            DevelopmentArtifactAuthority,
            build_agent_context_unit_development_artifact,
            validate_agent_context_unit_development_artifact,
        )
        from mke.evaluation.agent_context_unit_grading import (
            grade_context_mechanisms,
        )

        grading = grade_context_mechanisms(
            grading_payload,
            gates,
            baseline_observation=baseline_observation,
            o0_artifact_sha256=retained_baseline.artifact_sha256,
            workspace_a=complete_a,
            workspace_b=complete_b,
        )
        _complete_development_stage(
            AgentContextSubstage.GRADING,
            _canonical(
                {
                    "classifications": grading.classifications,
                    "digest": grading.grading_digest,
                    "statuses": dict(grading.mechanism_statuses),
                }
            ),
            completed,
            faults,
        )
        artifact_authority = DevelopmentArtifactAuthority(
            protocol_sha256=cast(
                str, retained_authority["protocol_sha256"]
            ),
            evaluator_source_sha256=cast(
                str, retained_authority["evaluator_source_sha256"]
            ),
            fixture_sha256=cast(
                str, retained_authority["fixture_sha256"]
            ),
            baseline_artifact_sha256=retained_baseline.artifact_sha256,
            baseline_content_digest=retained_baseline.content_digest,
            runtime_profile_sha256=hashlib.sha256(
                _canonical(retained_authority["runtime_profile"])
            ).hexdigest(),
        )
        artifact_bytes = build_agent_context_unit_development_artifact(
            authority=artifact_authority,
            grading_payload=grading_payload,
            baseline_observation=baseline_observation,
            workspace_a=complete_a,
            workspace_b=complete_b,
            gates=gates,
            grading=grading,
            limitations=(
                "constructed_development_corpus",
                "public_nonblind_future_holdout",
            ),
            nonclaims=grading_payload.scientific_nonclaims,
        )
        artifact = validate_agent_context_unit_development_artifact(
            artifact_bytes
        )
        _complete_development_stage(
            AgentContextSubstage.ARTIFACT_VALIDATION,
            artifact_bytes,
            completed,
            faults,
        )
        _invoke_development_fault(
            AgentContextSubstage.PUBLICATION,
            faults,
            completed,
        )
        publication = publish_json_no_replace(
            record_path,
            artifact_bytes,
            validate=lambda value: _validate_development_publication(
                value,
                validate_agent_context_unit_development_artifact,
            ),
        )
        output_state = publication.output_state
        publication_outcome = publication.publication_outcome
        if (
            output_state != "complete_visible"
            or publication_outcome != "published"
        ):
            raise AgentContextStageError(
                AgentContextSubstage.PUBLICATION,
                publication.cause or "publication_failed",
                "publication",
                completed=tuple(completed),
            )
        completed.append(
            run_diagnostic_stage(
                AgentContextSubstage.PUBLICATION,
                lambda: artifact_bytes,
            )
        )
        public_statuses = {
            grading_payload.mechanism_ids[key]: value
            for key, value in grading.mechanism_statuses.items()
        }
        return 0, _result(
            status="passed",
            integrity_status="passed",
            stage_outcome=cast(str, artifact["stage_outcome"]),
            output_state=output_state,
            publication_outcome=publication_outcome,
            phase="development",
            mechanism_statuses=public_statuses,
        )
    except AgentContextStageError as error:
        expected = tuple(AgentContextSubstage)[len(completed)]
        if (
            error.substage is not expected
            or error.completed != tuple(completed)
        ):
            error = AgentContextStageError(
                expected,
                error.error_code,
                error.error_family,
                completed=tuple(completed),
            )
        return _failure_result(
            error=error,
            observation_started=observation_started,
            diagnostic_receipt_path=diagnostic_receipt_path,
            retained_authority=retained_authority,
            observation_sha256=observation_sha256,
            output_state=output_state,
            publication_outcome=publication_outcome,
            phase="development",
            attempt_kind="development",
        )
    except Exception:
        stage = tuple(AgentContextSubstage)[len(completed)]
        error = AgentContextStageError(
            stage,
            "unexpected_stage_failure",
            "unexpected",
            completed=tuple(completed),
        )
        return _failure_result(
            error=error,
            observation_started=observation_started,
            diagnostic_receipt_path=diagnostic_receipt_path,
            retained_authority=retained_authority,
            observation_sha256=observation_sha256,
            output_state=output_state,
            publication_outcome=publication_outcome,
            phase="development",
            attempt_kind="development",
        )


def _complete_development_stage(
    substage: AgentContextSubstage,
    content: bytes,
    completed: list[AgentContextStageSuccess],
    faults: Mapping[AgentContextSubstage, Callable[[], None]],
) -> None:
    _invoke_development_fault(substage, faults, completed)
    completed.append(run_diagnostic_stage(substage, lambda: content))


def _invoke_development_fault(
    substage: AgentContextSubstage,
    faults: Mapping[AgentContextSubstage, Callable[[], None]],
    completed: list[AgentContextStageSuccess],
) -> None:
    operation = faults.get(substage)
    if operation is None:
        return
    try:
        operation()
    except AgentContextStageError as error:
        raise AgentContextStageError(
            error.substage,
            error.error_code,
            error.error_family,
            completed=tuple(completed),
        ) from None
    except Exception:
        raise AgentContextStageError(
            substage,
            "unexpected_stage_failure",
            "unexpected",
            completed=tuple(completed),
        ) from None


def _require_workspace_stage_equality(
    workspace_a: bytes,
    workspace_b: bytes,
    substage: AgentContextSubstage,
    error_code: str,
    completed: list[AgentContextStageSuccess],
) -> None:
    if workspace_a != workspace_b:
        raise AgentContextStageError(
            substage,
            error_code,
            "integrity",
            completed=tuple(completed),
        )


def _sealed_observation_inventory(
    value: tuple[object, ...],
    *,
    expected_count: int | None = None,
) -> tuple[Any, ...]:
    from mke.evaluation.agent_context_unit_grading import (
        SealedMechanismObservation,
    )

    if (
        type(value) is not tuple
        or (expected_count is not None and len(value) != expected_count)
        or any(type(item) is not SealedMechanismObservation for item in value)
    ):
        raise ValueError("candidate observation inventory is invalid")
    result = tuple(
        sorted(
            cast(tuple[SealedMechanismObservation, ...], value),
            key=lambda item: item.mechanism_id.encode(),
        )
    )
    if len({item.mechanism_id for item in result}) != len(result):
        raise ValueError("candidate observation inventory is invalid")
    return result


def _sealed_inventory_bytes(observations: tuple[Any, ...]) -> bytes:
    parts: list[bytes] = []
    for item in observations:
        mechanism = item.mechanism_id.encode("utf-8")
        portable = item.portable_bytes
        if (
            type(portable) is not bytes
            or item.portable_sha256
            != hashlib.sha256(portable).hexdigest()
        ):
            raise ValueError("candidate observation seal is invalid")
        parts.extend(
            (
                len(mechanism).to_bytes(4, "big"),
                mechanism,
                len(portable).to_bytes(8, "big"),
                portable,
            )
        )
    return b"".join(parts)


def _gate_dispatches(
    payload: Any,
    gates: Any,
) -> tuple[CandidateGateDispatch, ...]:
    candidate_targets = {
        query_id
        for query_id, mechanism_ids in payload.observation_ids_by_query.items()
        if any(
            item != payload.mechanism_ids["o0"]
            for item in mechanism_ids
        )
    }
    controls = set(payload.query_ids) - candidate_targets
    queries = {
        "o3": set(gates.evidence.o3_residual_query_ids) | controls,
        "o4": set(gates.evidence.o4_residual_query_ids) | controls,
        "o5": set(gates.evidence.o5_preregistered_query_ids) | controls,
    }
    return tuple(
        CandidateGateDispatch(
            mechanism_id=getattr(gates, gate_name).mechanism_id,
            enabled=getattr(gates, gate_name).enabled,
            reason=getattr(gates, gate_name).reason,
            query_ids=tuple(sorted(queries[gate_name], key=str.encode)),
            gate_digest=gates.gate_digest,
        )
        for gate_name in ("o3", "o4", "o5")
    )


def _read_no_follow_absolute(path: Path) -> bytes:
    absolute = path.absolute()
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory_flag = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory_flag is None:
        raise ValueError("retained artifact authority is unavailable")
    descriptors = [
        os.open(absolute.anchor, os.O_RDONLY | directory_flag | nofollow)
    ]
    try:
        parent_descriptor = descriptors[0]
        for component in absolute.parent.parts[1:]:
            parent_descriptor = os.open(
                component,
                os.O_RDONLY | directory_flag | nofollow,
                dir_fd=parent_descriptor,
            )
            descriptors.append(parent_descriptor)
        file_descriptor = os.open(
            absolute.name,
            os.O_RDONLY | nofollow,
            dir_fd=parent_descriptor,
        )
        descriptors.append(file_descriptor)
        before = os.fstat(file_descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("retained artifact authority is invalid")
        chunks: list[bytes] = []
        while chunk := os.read(file_descriptor, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(file_descriptor)
        lexical = os.stat(
            absolute.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            )
            or (lexical.st_dev, lexical.st_ino)
            != (before.st_dev, before.st_ino)
        ):
            raise ValueError("retained artifact authority changed")
        content = b"".join(chunks)
        if len(content) != before.st_size:
            raise ValueError("retained artifact authority changed")
        return content
    except OSError as error:
        raise ValueError("retained artifact authority is invalid") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _validate_development_publication(
    value: object,
    validator: Callable[[bytes], object],
) -> None:
    validator(_canonical(value) + b"\n")


def _default_development_driver_factory(
    contract: AgentContextObserverContract,
    repository_root: Path,
    workspace: Path,
    start_observation: Callable[[], None],
) -> DevelopmentWorkspaceDriver:
    return _CandidateWorkspaceDriver(
        contract=contract,
        repository_root=repository_root,
        workspace=workspace,
        start_observation=start_observation,
    )


class _CandidateWorkspaceDriver:
    def __init__(
        self,
        *,
        contract: AgentContextObserverContract,
        repository_root: Path,
        workspace: Path,
        start_observation: Callable[[], None],
    ) -> None:
        self._contract = contract
        self._repository_root = repository_root
        self._workspace = workspace
        self._start_observation = start_observation
        self._units: tuple[Any, ...] = ()
        self._rows: tuple[Any, ...] = ()
        self._rank_by_query: dict[str, Any] = {}
        self._delivery_by_query: dict[str, Any | None] = {}
        self._parent_text: dict[tuple[str, int], bytes] = {}

    def observe_o1_o2(self) -> CandidateIntermediateObservation:
        if self._workspace.exists():
            raise ValueError("candidate workspace must be fresh")
        self._workspace.mkdir(parents=True)
        parents = self._read_parent_pages()
        from mke.evaluation.agent_context_unit_ranking import (
            build_unit_projection,
            rank_cjk_units,
            rank_fts_units,
        )
        from mke.evaluation.agent_context_unit_segmentation import (
            segment_parent_pages,
        )

        units = segment_parent_pages(parents)
        rows = build_unit_projection(units)
        self._units = units
        self._rows = rows
        o1_cases: list[Any] = []
        o2_cases: list[Any] = []
        rank_bytes: list[object] = []
        delivery_bytes: list[object] = []
        for case in self._contract.cases:
            rank = (
                rank_fts_units(
                    rows,
                    query_id=case.query_id,
                    query_text=case.query_text,
                )
                if case.runtime_route_profile == "fts5"
                else rank_cjk_units(
                    rows,
                    query_id=case.query_id,
                    query_text=case.query_text,
                )
            )
            self._rank_by_query[case.query_id] = rank
            delivery = self._assemble_o2(rank)
            self._delivery_by_query[case.query_id] = delivery
            o1_cases.append(
                self._mechanism_case(
                    case,
                    "deterministic-unit-rank-v1",
                    rank,
                    delivery=None,
                    context_ranges=(),
                )
            )
            o2_cases.append(
                self._mechanism_case(
                    case,
                    "fixed-rank-delivery-v1",
                    rank,
                    delivery=delivery,
                    context_ranges=(),
                )
            )
            rank_bytes.append(json.loads(rank.portable_bytes()))
            delivery_bytes.append(
                None
                if delivery is None
                else json.loads(delivery.portable_bytes())
            )
        from mke.evaluation.agent_context_unit_grading import (
            seal_mechanism_observation,
        )

        o1 = seal_mechanism_observation(
            "deterministic-unit-rank-v1", tuple(o1_cases)
        )
        o2 = seal_mechanism_observation(
            "fixed-rank-delivery-v1", tuple(o2_cases)
        )
        return CandidateIntermediateObservation(
            observations=(o1, o2),
            source_snapshot_bytes=_canonical(
                [
                    {
                        "locator": (
                            parent.locator_kind,
                            parent.locator_start,
                            parent.locator_end,
                        ),
                        "source_content_fingerprint": (
                            parent.source_content_fingerprint
                        ),
                        "text_sha256": hashlib.sha256(
                            parent.text_bytes
                        ).hexdigest(),
                    }
                    for parent in parents
                ]
            ),
            unit_projection_bytes=_canonical(
                [_portable_projection_row(row) for row in rows]
            ),
            unit_rank_bytes=_canonical(rank_bytes),
            fixed_rank_delivery_bytes=_canonical(delivery_bytes),
        )

    def observe_residual(
        self,
        dispatches: tuple[CandidateGateDispatch, ...],
    ) -> CandidateResidualObservation:
        if not self._rows or not self._rank_by_query:
            raise ValueError("candidate intermediate seal is absent")
        observations: list[Any] = []
        stage_bytes: dict[str, list[object]] = {
            "adjacent-page-assembly-v1": [],
            "source-context-index-v1": [],
            "source-context-delivery-v1": [],
        }
        by_query = {case.query_id: case for case in self._contract.cases}
        for dispatch in dispatches:
            if not dispatch.enabled:
                continue
            cases: list[Any] = []
            for query_id in dispatch.query_ids:
                case = by_query[query_id]
                rank = self._rank_by_query[query_id]
                if dispatch.mechanism_id == "source-context-index-v1":
                    result, context_ranges, retrieval_text = (
                        self._rank_o3(case, rank)
                    )
                    cases.append(
                        self._mechanism_case(
                            case,
                            dispatch.mechanism_id,
                            result.rank,
                            delivery=None,
                            context_ranges=context_ranges,
                            retrieval_text=retrieval_text,
                        )
                    )
                    stage_bytes[dispatch.mechanism_id].append(
                        json.loads(result.portable_bytes())
                    )
                elif dispatch.mechanism_id == "source-context-delivery-v1":
                    context = self._source_context_inventory(rank)
                    result = self._assemble_context_delivery(
                        rank, context, adjacent=False
                    )
                    cases.append(
                        self._mechanism_case(
                            case,
                            dispatch.mechanism_id,
                            rank,
                            delivery=result,
                            context_ranges=_delivery_context_ranges(result),
                        )
                    )
                    stage_bytes[dispatch.mechanism_id].append(
                        None
                        if result is None
                        else json.loads(result.portable_bytes())
                    )
                elif dispatch.mechanism_id == "adjacent-page-assembly-v1":
                    context = self._adjacent_context_inventory(rank)
                    result = self._assemble_context_delivery(
                        rank, context, adjacent=True
                    )
                    cases.append(
                        self._mechanism_case(
                            case,
                            dispatch.mechanism_id,
                            rank,
                            delivery=result,
                            context_ranges=_delivery_context_ranges(result),
                        )
                    )
                    stage_bytes[dispatch.mechanism_id].append(
                        None
                        if result is None
                        else json.loads(result.portable_bytes())
                    )
                else:
                    raise ValueError("candidate gate mechanism is invalid")
            from mke.evaluation.agent_context_unit_grading import (
                seal_mechanism_observation,
            )

            observations.append(
                seal_mechanism_observation(
                    dispatch.mechanism_id, tuple(cases)
                )
            )
        return CandidateResidualObservation(
            observations=tuple(observations),
            gate_digest=dispatches[0].gate_digest,
            adjacent_page_assembly_bytes=_canonical(
                stage_bytes["adjacent-page-assembly-v1"]
            ),
            source_context_index_bytes=_canonical(
                stage_bytes["source-context-index-v1"]
            ),
            source_context_delivery_bytes=_canonical(
                stage_bytes["source-context-delivery-v1"]
            ),
        )

    def _read_parent_pages(self) -> tuple[Any, ...]:
        from mke.evaluation.agent_context_unit_segmentation import (
            ParentPageEvidence,
        )
        from mke.evaluation.source_identity import (
            read_no_follow_regular_file,
        )

        parents: list[ParentPageEvidence] = []
        first = True
        for receipt in self._contract.sources:
            source = read_no_follow_regular_file(
                self._repository_root,
                receipt.path,
                on_open=(self._start_observation if first else None),
            )
            first = False
            if (
                source.identity["bytes"] != receipt.bytes
                or f"sha256:{source.identity['sha256']}"
                != receipt.content_fingerprint
            ):
                raise ValueError("candidate source identity is invalid")
            document = pymupdf.open(
                stream=source.content,
                filetype="pdf",
            )
            try:
                page_texts: list[tuple[int, bytes]] = []
                for page in document:
                    page_handle: Any = page
                    text = page_handle.get_text("text")
                    if text:
                        page_texts.append(
                            (
                                cast(int, page_handle.number) + 1,
                                cast(str, text).encode("utf-8"),
                            )
                        )
            finally:
                document.close()
            if (
                len(page_texts) != receipt.nonempty_text_pages
                or sum(len(item[1]) for item in page_texts)
                != receipt.extracted_text_utf8_bytes
            ):
                raise ValueError("candidate source projection is invalid")
            publication_identity = _stable_prefixed_digest(
                {
                    "kind": "publication",
                    "source_content_fingerprint": (
                        receipt.content_fingerprint
                    ),
                }
            )
            for page_number, text_bytes in page_texts:
                self._parent_text[
                    (receipt.content_fingerprint, page_number)
                ] = text_bytes
                parents.append(
                    ParentPageEvidence(
                        source_id=receipt.source_id,
                        source_content_fingerprint=(
                            receipt.content_fingerprint
                        ),
                        publication_id=publication_identity,
                        evidence_id=(
                            f"{self._workspace.name}:"
                            f"{receipt.source_id}:{page_number}"
                        ),
                        locator_kind="page",
                        locator_start=page_number,
                        locator_end=page_number,
                        text_bytes=text_bytes,
                    )
                )
        return tuple(parents)

    def _assemble_o2(self, rank: Any) -> Any | None:
        from mke.evaluation.agent_context_unit_assembly import (
            assemble_o2_delivery,
            seal_selected_identities,
        )

        if not rank.primary_stable_context_unit_ids:
            return None
        selection = seal_selected_identities(
            rank.primary_stable_context_unit_ids
        )
        return assemble_o2_delivery(
            selection,
            self._delivery_inventory(
                rank.primary_stable_context_unit_ids,
                rank.rank_profile_id,
            ),
        )

    def _assemble_context_delivery(
        self,
        rank: Any,
        context: tuple[Any, ...],
        *,
        adjacent: bool,
    ) -> Any | None:
        from mke.evaluation.agent_context_unit_assembly import (
            assemble_o4_delivery,
            assemble_o5_delivery,
            seal_selected_identities,
        )

        if not rank.primary_stable_context_unit_ids:
            return None
        selection = seal_selected_identities(
            rank.primary_stable_context_unit_ids
        )
        inventory = self._delivery_inventory(
            rank.primary_stable_context_unit_ids,
            rank.rank_profile_id,
        )
        return (
            assemble_o5_delivery(selection, inventory, context)
            if adjacent
            else assemble_o4_delivery(selection, inventory, context)
        )

    def _delivery_inventory(
        self,
        selected_ids: tuple[str, ...],
        rank_profile_id: str,
    ) -> tuple[Any, ...]:
        from mke.evaluation.agent_context_unit_assembly import (
            FrozenDeliveryInput,
        )

        by_id = {
            row.stable_context_unit_id: row for row in self._rows
        }
        return tuple(
            FrozenDeliveryInput(
                stable_context_unit_id=row.stable_context_unit_id,
                source_content_fingerprint=(
                    row.source_content_fingerprint
                ),
                publication_identity=_stable_prefixed_digest(
                    {
                        "kind": "publication",
                        "source_content_fingerprint": (
                            row.source_content_fingerprint
                        ),
                    }
                ),
                origin_evidence_ref=_origin_evidence_ref(row),
                parent_locator=row.parent_locator,
                origin_start_utf8_byte=row.start_utf8_byte,
                origin_end_utf8_byte=row.end_utf8_byte,
                text_bytes=row.text_bytes,
                text_sha256=row.text_sha256,
                rank_profile_id=rank_profile_id,
                active=True,
                runtime_evidence_handle=(
                    f"{self._workspace.name}:"
                    f"{row.stable_context_unit_id}"
                ),
            )
            for row in (by_id[item] for item in selected_ids)
        )

    def _source_context_inventory(
        self, rank: Any
    ) -> tuple[Any, ...]:
        return self._context_inventory(
            rank.primary_stable_context_unit_ids,
            adjacent=False,
        )

    def _adjacent_context_inventory(
        self, rank: Any
    ) -> tuple[Any, ...]:
        return self._context_inventory(
            rank.primary_stable_context_unit_ids,
            adjacent=True,
        )

    def _context_inventory(
        self,
        selected_ids: tuple[str, ...],
        *,
        adjacent: bool,
    ) -> tuple[Any, ...]:
        from mke.evaluation.agent_context_unit_assembly import (
            ContextComponentInput,
        )

        by_id = {
            row.stable_context_unit_id: row for row in self._rows
        }
        stable_rows = tuple(self._rows)
        positions = {
            row.stable_context_unit_id: index
            for index, row in enumerate(stable_rows)
        }
        result: list[ContextComponentInput] = []
        seen_context: set[tuple[str, tuple[str, int, int], int, int]] = set()
        for selected_id in selected_ids:
            selected = by_id[selected_id]
            if adjacent:
                candidates = (
                    (
                        "previous_page_tail",
                        selected.parent_locator[1] - 1,
                    ),
                    (
                        "next_page_head",
                        selected.parent_locator[1] + 1,
                    ),
                )
                for kind, page in candidates:
                    component = _page_context_component(
                            selected,
                            selected_id,
                            kind,
                            page,
                            self._parent_text,
                        )
                    result.append(
                        _deduplicated_context_component(
                            component,
                            seen_context,
                        )
                    )
                continue
            position = positions[selected_id]
            previous = (
                stable_rows[position - 1] if position > 0 else None
            )
            following = (
                stable_rows[position + 1]
                if position + 1 < len(stable_rows)
                else None
            )
            parent_bytes = self._parent_text[
                (
                    selected.source_content_fingerprint,
                    selected.parent_locator[1],
                )
            ]
            heading_end = parent_bytes.find(b"\n")
            heading_end = (
                len(parent_bytes) if heading_end < 0 else heading_end
            )
            components = (
                (
                    _unit_context_component(
                        selected,
                        selected_id,
                        "heading",
                        parent_bytes[:heading_end],
                        0,
                        heading_end,
                    ),
                    _neighbor_context_component(
                        selected,
                        selected_id,
                        "previous_unit",
                        previous,
                    ),
                    _neighbor_context_component(
                        selected,
                        selected_id,
                        "next_unit",
                        following,
                    ),
                )
            )
            if heading_end > selected.start_utf8_byte:
                components = (
                    _empty_context_component(
                        selected,
                        selected_id,
                        "heading",
                        status="missing",
                    ),
                    components[1],
                    components[2],
                )
            result.extend(
                _deduplicated_context_component(
                    component,
                    seen_context,
                )
                for component in components
            )
        return tuple(result)

    def _rank_o3(
        self,
        case: Any,
        base_rank: Any,
    ) -> tuple[Any, tuple[Any, ...], str]:
        from mke.evaluation.agent_context_unit_ranking import (
            SourceContextProjectionComponent,
            build_source_context_projection,
            rank_source_context_cjk,
            rank_source_context_fts,
        )

        context = self._context_inventory(
            tuple(row.stable_context_unit_id for row in self._rows),
            adjacent=False,
        )
        components = tuple(
            SourceContextProjectionComponent(
                stable_context_unit_id=(
                    item.selected_stable_context_unit_id
                ),
                kind=item.kind,
                status=item.status,
                source_content_fingerprint=(
                    item.source_content_fingerprint
                ),
                publication_identity=item.publication_identity,
                origin_evidence_ref=item.origin_evidence_ref,
                parent_locator=item.parent_locator,
                origin_start_utf8_byte=item.origin_start_utf8_byte,
                origin_end_utf8_byte=item.origin_end_utf8_byte,
                text_bytes=item.text_bytes,
                text_sha256=item.text_sha256,
            )
            for item in context
        )
        projection = build_source_context_projection(
            self._rows, components, variant="combined"
        )
        result = (
            rank_source_context_fts(
                projection,
                query_id=case.query_id,
                query_text=case.query_text,
            )
            if case.runtime_route_profile == "fts5"
            else rank_source_context_cjk(
                projection,
                query_id=case.query_id,
                query_text=case.query_text,
            )
        )
        by_component = {
            (
                item.selected_stable_context_unit_id,
                item.kind,
            ): item
            for item in context
        }
        selected = set(result.rank.primary_stable_context_unit_ids)
        ranges = tuple(
            _observed_range_from_component(
                by_component[
                    (
                        attribution.stable_context_unit_id,
                        kind,
                    )
                ]
            )
            for attribution in result.attributions
            if attribution.stable_context_unit_id in selected
            for kind in attribution.component_kinds
        )
        retrieval_text = "".join(
            row.retrieval_text_bytes.decode("utf-8")
            for row in projection
            if row.unit.stable_context_unit_id in selected
        )
        return result, ranges, retrieval_text

    def _mechanism_case(
        self,
        case: Any,
        mechanism_id: str,
        rank: Any,
        *,
        delivery: Any | None,
        context_ranges: tuple[Any, ...],
        retrieval_text: str | None = None,
    ) -> Any:
        from mke.evaluation.agent_context_unit_grading import (
            MechanismCaseObservation,
            ObservedRankedCandidate,
        )

        by_id = {
            row.stable_context_unit_id: row for row in self._rows
        }
        ranked = tuple(
            ObservedRankedCandidate(
                stable_identity=item.stable_context_unit_id,
                rank=item.diagnostic_rank,
                parent_collapsed_rank=item.parent_collapsed_rank,
                authority_range=_observed_range_from_row(
                    by_id[item.stable_context_unit_id]
                ),
            )
            for item in rank.diagnostic
        )
        selected = rank.primary_stable_context_unit_ids
        delivered_ranges = (
            ()
            if delivery is None
            else tuple(
                _observed_range_from_delivery(item)
                for item in delivery.items
            )
        )
        if retrieval_text is None:
            retrieval_text = (
                "".join(
                    by_id[item].text_bytes.decode("utf-8")
                    for item in selected
                )
                if delivery is None
                else "".join(
                    item.delivered_text_bytes.decode("utf-8")
                    for item in delivery.items
                )
            )
        return MechanismCaseObservation(
            query_id=case.query_id,
            mechanism_id=mechanism_id,
            route=rank.route,
            rank_profile_id=rank.rank_profile_id,
            query_terms=tuple(case.query_text.casefold().split()),
            retrieval_text=retrieval_text,
            candidate_count=rank.candidate_count,
            unique_parent_count=rank.unique_parent_count,
            ranked=ranked,
            selected_stable_identities=selected,
            delivered_ranges=delivered_ranges,
            context_ranges=context_ranges,
            delivered_utf8_bytes=(
                sum(
                    item.end_utf8_byte - item.start_utf8_byte
                    for item in (*delivered_ranges, *context_ranges)
                )
            ),
            context_attribution_unique=True,
            output_complete=True,
            exact_read_complete=True,
            provenance_exact=True,
        )


def _portable_projection_row(row: Any) -> dict[str, object]:
    return {
        "end_utf8_byte": row.end_utf8_byte,
        "parent_locator": row.parent_locator,
        "parent_text_sha256": row.parent_text_sha256,
        "rank_profile_id": row.rank_profile_id,
        "source_content_fingerprint": row.source_content_fingerprint,
        "stable_context_unit_id": row.stable_context_unit_id,
        "start_utf8_byte": row.start_utf8_byte,
        "text_sha256": row.text_sha256,
    }


def _stable_prefixed_digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _origin_evidence_ref(row: Any) -> str:
    return _stable_prefixed_digest(
        {
            "parent_locator": row.parent_locator,
            "parent_text_sha256": row.parent_text_sha256,
            "source_content_fingerprint": (
                row.source_content_fingerprint
            ),
        }
    )


def _observed_range_from_row(row: Any) -> Any:
    from mke.evaluation.agent_context_unit_grading import ObservedRange

    return ObservedRange(
        source_content_fingerprint=row.source_content_fingerprint,
        locator_kind="page",
        locator_start=row.parent_locator[1],
        locator_end=row.parent_locator[2],
        start_utf8_byte=row.start_utf8_byte,
        end_utf8_byte=row.end_utf8_byte,
        origin_evidence_ref=_origin_evidence_ref(row),
        component_kind="unit",
    )


def _observed_range_from_delivery(item: Any) -> Any:
    from mke.evaluation.agent_context_unit_grading import ObservedRange

    delivered_unit_bytes = (
        item.excerpt_text_bytes
        if item.excerpt_text_bytes
        else item.unit_text_bytes
    )
    return ObservedRange(
        source_content_fingerprint=item.source_content_fingerprint,
        locator_kind="page",
        locator_start=item.parent_locator[1],
        locator_end=item.parent_locator[2],
        start_utf8_byte=item.origin_start_utf8_byte,
        end_utf8_byte=(
            item.origin_start_utf8_byte + len(delivered_unit_bytes)
        ),
        origin_evidence_ref=item.origin_evidence_ref,
        component_kind="unit",
    )


def _observed_range_from_component(item: Any) -> Any:
    from mke.evaluation.agent_context_unit_grading import ObservedRange

    start = getattr(
        item,
        "returned_origin_start_utf8_byte",
        item.origin_start_utf8_byte,
    )
    end = getattr(
        item,
        "returned_origin_end_utf8_byte",
        item.origin_end_utf8_byte,
    )
    return ObservedRange(
        source_content_fingerprint=item.source_content_fingerprint,
        locator_kind="page",
        locator_start=item.parent_locator[1],
        locator_end=item.parent_locator[2],
        start_utf8_byte=start,
        end_utf8_byte=end,
        origin_evidence_ref=item.origin_evidence_ref,
        component_kind=item.kind,
    )


def _empty_context_component(
    selected: Any,
    selected_id: str,
    kind: Any,
    *,
    status: Any,
    page: int | None = None,
) -> Any:
    from mke.evaluation.agent_context_unit_assembly import (
        ContextComponentInput,
    )

    locator = selected.parent_locator[1] if page is None else page
    offset = selected.start_utf8_byte
    return ContextComponentInput(
        selected_stable_context_unit_id=selected_id,
        kind=kind,
        status=status,
        source_content_fingerprint=selected.source_content_fingerprint,
        publication_identity=_stable_prefixed_digest(
            {
                "kind": "publication",
                "source_content_fingerprint": (
                    selected.source_content_fingerprint
                ),
            }
        ),
        origin_evidence_ref=_origin_evidence_ref(selected),
        parent_locator=("page", locator, locator),
        origin_start_utf8_byte=offset,
        origin_end_utf8_byte=offset,
        text_bytes=b"",
        text_sha256=hashlib.sha256(b"").hexdigest(),
    )


def _unit_context_component(
    selected: Any,
    selected_id: str,
    kind: Any,
    text_bytes: bytes,
    start: int,
    end: int,
) -> Any:
    from mke.evaluation.agent_context_unit_assembly import (
        ContextComponentInput,
    )

    if not text_bytes:
        return _empty_context_component(
            selected, selected_id, kind, status="missing"
        )
    return ContextComponentInput(
        selected_stable_context_unit_id=selected_id,
        kind=kind,
        status="available",
        source_content_fingerprint=selected.source_content_fingerprint,
        publication_identity=_stable_prefixed_digest(
            {
                "kind": "publication",
                "source_content_fingerprint": (
                    selected.source_content_fingerprint
                ),
            }
        ),
        origin_evidence_ref=_origin_evidence_ref(selected),
        parent_locator=selected.parent_locator,
        origin_start_utf8_byte=start,
        origin_end_utf8_byte=end,
        text_bytes=text_bytes,
        text_sha256=hashlib.sha256(text_bytes).hexdigest(),
    )


def _neighbor_context_component(
    selected: Any,
    selected_id: str,
    kind: Any,
    neighbor: Any | None,
) -> Any:
    if (
        neighbor is None
        or neighbor.source_content_fingerprint
        != selected.source_content_fingerprint
        or neighbor.parent_locator != selected.parent_locator
    ):
        return _empty_context_component(
            selected, selected_id, kind, status="missing"
        )
    return _unit_context_component(
        neighbor,
        selected_id,
        kind,
        neighbor.text_bytes,
        neighbor.start_utf8_byte,
        neighbor.end_utf8_byte,
    )


def _page_context_component(
    selected: Any,
    selected_id: str,
    kind: Any,
    page: int,
    parent_text: Mapping[tuple[str, int], bytes],
) -> Any:
    text = parent_text.get(
        (selected.source_content_fingerprint, page)
    )
    if page < 1 or text is None:
        return _empty_context_component(
            selected,
            selected_id,
            kind,
            status="missing",
            page=max(page, 1),
        )
    from mke.evaluation.agent_context_unit_assembly import (
        ContextComponentInput,
    )

    return ContextComponentInput(
        selected_stable_context_unit_id=selected_id,
        kind=kind,
        status="available",
        source_content_fingerprint=selected.source_content_fingerprint,
        publication_identity=_stable_prefixed_digest(
            {
                "kind": "publication",
                "source_content_fingerprint": (
                    selected.source_content_fingerprint
                ),
            }
        ),
        origin_evidence_ref=_stable_prefixed_digest(
            {
                "locator": ("page", page, page),
                "source_content_fingerprint": (
                    selected.source_content_fingerprint
                ),
            }
        ),
        parent_locator=("page", page, page),
        origin_start_utf8_byte=0,
        origin_end_utf8_byte=len(text),
        text_bytes=text,
        text_sha256=hashlib.sha256(text).hexdigest(),
    )


def _deduplicated_context_component(
    component: Any,
    seen: set[tuple[str, tuple[str, int, int], int, int]],
) -> Any:
    if component.status != "available":
        return component
    identity = (
        component.source_content_fingerprint,
        component.parent_locator,
        component.origin_start_utf8_byte,
        component.origin_end_utf8_byte,
    )
    if identity in seen:
        return replace(
            component,
            status="ambiguous",
            origin_end_utf8_byte=component.origin_start_utf8_byte,
            text_bytes=b"",
            text_sha256=hashlib.sha256(b"").hexdigest(),
        )
    seen.add(identity)
    return component


def _delivery_context_ranges(delivery: Any | None) -> tuple[Any, ...]:
    if delivery is None:
        return ()
    return tuple(
        _observed_range_from_component(component)
        for item in delivery.items
        for component in item.components
        if component.returned_utf8_bytes
    )


def _default_baseline_runner(
    contract: AgentContextObserverContract,
    repository_root: Path,
    workspace: Path,
    start_observation: Callable[[], None],
) -> tuple[AuthorityObservation, ...]:
    return run_agent_context_unit_baseline(
        contract=contract,
        repository_root=repository_root,
        workspace=workspace,
        on_source_open=start_observation,
    )


def _run_stage(
    substage: AgentContextSubstage,
    operation: Callable[[], tuple[AuthorityObservation, ...]],
    completed: list[AgentContextStageSuccess],
) -> tuple[AuthorityObservation, ...]:
    try:
        return operation()
    except AgentContextStageError as error:
        raise AgentContextStageError(
            error.substage,
            error.error_code,
            error.error_family,
            completed=tuple(completed),
        ) from None
    except Exception:
        raise AgentContextStageError(
            substage,
            "unexpected_stage_failure",
            "unexpected",
            completed=tuple(completed),
        ) from None


def _failure_result(
    *,
    error: AgentContextStageError,
    observation_started: bool,
    diagnostic_receipt_path: Path,
    retained_authority: dict[str, object] | None,
    observation_sha256: str | None,
    output_state: str,
    publication_outcome: str,
    phase: str = "baseline",
    attempt_kind: str = "o0",
) -> tuple[int, dict[str, object]]:
    if not observation_started or retained_authority is None:
        return 1, _result(
            status="failed",
            integrity_status="failed",
            stage_outcome="pre_observation_blocked",
            output_state="absent",
            publication_outcome="not_attempted",
            problem="agent_context_authority_preflight_failed",
            cause=error.error_code,
            next_step="correct_preflight_under_separate_authority",
            first_failed_gate=error.first_failed_gate,
            phase=phase,
        )
    profile = cast(dict[str, object], retained_authority["runtime_profile"])
    receipt = build_agent_context_diagnostic_receipt(
        protocol_sha256=cast(str, retained_authority["protocol_sha256"]),
        profile_sha256=hashlib.sha256(_canonical(profile)).hexdigest(),
        evaluator_source_sha256=cast(
            str, retained_authority["evaluator_source_sha256"]
        ),
        observation_sha256=observation_sha256,
        phase=phase,
        attempt_kind=attempt_kind,
        observation_started=True,
        completed=error.completed,
        error=error,
        output_state=output_state,
        publication_outcome=publication_outcome,
        stderr_bytes=0,
        stderr_sha256=hashlib.sha256(b"").hexdigest(),
    )
    receipt_bytes = render_agent_context_diagnostic_receipt(receipt)
    publication = publish_json_no_replace(
        diagnostic_receipt_path,
        receipt_bytes,
        validate=validate_agent_context_diagnostic_receipt,
    )
    if (
        publication.output_state != "complete_visible"
        or publication.publication_outcome != "published"
        or publication.sha256 is None
    ):
        return 1, _result(
            status="failed",
            integrity_status="failed",
            stage_outcome="evaluation_inconclusive",
            output_state="absent",
            publication_outcome="not_attempted",
            problem="agent_context_diagnostic_receipt_unavailable",
            cause="operator_receipt_not_complete_visible",
            next_step="repair_diagnostic_harness_before_new_protocol",
            first_failed_gate=error.first_failed_gate,
            diagnostic_receipt_status="unavailable",
            phase=phase,
        )
    publication_failed = error.substage is AgentContextSubstage.PUBLICATION
    return 1, _result(
        status="failed",
        integrity_status="failed",
        stage_outcome="evaluation_inconclusive",
        output_state=output_state,
        publication_outcome=publication_outcome,
        problem=(
            "agent_context_publication_failed"
            if publication_failed
            else "agent_context_observation_incomplete"
        ),
        cause=error.error_code,
        next_step=(
            "retain_visible_bytes_and_do_not_retry"
            if publication_failed and output_state == "complete_visible"
            else "close_protocol_and_review_retained_receipt"
        ),
        first_failed_gate=error.first_failed_gate,
        diagnostic_receipt_status="complete_visible",
        diagnostic_receipt_sha256=publication.sha256,
        phase=phase,
    )


def _preflight(
    protocol_path: Path,
    record_path: Path,
    receipt_path: Path,
    repository_root: Path | None = None,
) -> tuple[
    AgentContextProtocolAuthority,
    AgentContextObserverContract,
    dict[str, object],
]:
    if not _absent_regular_destination(record_path) or not _absent_regular_destination(
        receipt_path
    ):
        raise ValueError("output path authority is invalid")
    protocol_authority = load_agent_context_unit_protocol_authority(protocol_path)
    if (
        repository_root is not None
        and repository_root != protocol_authority.repository_root
    ):
        raise ValueError("protocol repository root is invalid")
    repository_root = protocol_authority.repository_root
    metadata = protocol_authority.metadata
    observer_authority = build_agent_context_unit_observer_authority(
        protocol_authority
    )
    contract = load_agent_context_unit_observer_contract(observer_authority)
    evaluator = build_source_identity(repository_root, metadata.o0_evaluator_paths)
    runtime_source = build_source_identity(repository_root, _RUNTIME_SOURCE_PATHS)
    runtime_profile = _runtime_profile()
    if set(runtime_profile) != set(metadata.runtime_profile_fields):
        raise ValueError("runtime profile field inventory is invalid")
    authority: dict[str, object] = {
        "protocol_sha256": protocol_authority.protocol_read.identity["sha256"],
        "evaluator_source_sha256": evaluator["sha256"],
        "runtime_source_sha256": runtime_source["sha256"],
        "runtime_profile": runtime_profile,
        "fixture_sha256": protocol_authority.scientific_lock_read.identity[
            "sha256"
        ],
    }
    return protocol_authority, contract, authority


def _runtime_profile() -> dict[str, object]:
    connection = sqlite3.connect(":memory:")
    try:
        source_id = connection.execute("SELECT sqlite_source_id()").fetchone()
        compile_options = tuple(
            sorted(
                str(row[0])
                for row in connection.execute("PRAGMA compile_options").fetchall()
            )
        )
    finally:
        connection.close()
    if source_id is None or not isinstance(source_id[0], str) or not source_id[0]:
        raise ValueError("SQLite runtime profile is invalid")
    return {
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "sqlite_source_id": source_id[0],
        "sqlite_compile_options": list(compile_options),
        "pymupdf": pymupdf.VersionBind,
        "fts5_rank_configuration": "rank",
        "strategy_id": "numeric-grouping-v1",
        "strategy_revision": 2,
        "query_policy_id": "numeric-grouping-v1",
        "query_policy_revision": 1,
    }


def _absent_regular_destination(path: Path) -> bool:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parent.parts[1:]:
        current /= component
        try:
            metadata = current.lstat()
        except OSError:
            return False
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            return False
    try:
        path.lstat()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return False


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-context-unit-workflow")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("diagnose", "baseline"):
        command = commands.add_parser(name)
        command.add_argument("--protocol", type=Path, required=True)
        command.add_argument("--record", type=Path, required=True)
        command.add_argument("--diagnostic-receipt", type=Path, required=True)
        command.add_argument("--json", action="store_true", required=True)
    development = commands.add_parser("development")
    development.add_argument("--protocol", type=Path, required=True)
    development.add_argument("--baseline", type=Path, required=True)
    development.add_argument("--record", type=Path, required=True)
    development.add_argument(
        "--diagnostic-receipt", type=Path, required=True
    )
    development.add_argument("--json", action="store_true", required=True)
    validate = commands.add_parser("validate-baseline")
    validate.add_argument("--protocol", type=Path, required=True)
    validate.add_argument("--artifact", type=Path, required=True)
    validate.add_argument("--json", action="store_true", required=True)
    validate_development = commands.add_parser("validate-development")
    validate_development.add_argument(
        "--protocol", type=Path, required=True
    )
    validate_development.add_argument(
        "--baseline", type=Path, required=True
    )
    validate_development.add_argument("--artifact", type=Path, required=True)
    validate_development.add_argument(
        "--json", action="store_true", required=True
    )
    receipt = commands.add_parser("validate-receipt")
    receipt.add_argument("--receipt", type=Path, required=True)
    receipt.add_argument("--json", action="store_true", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
    except SystemExit as error:
        return cast(int, error.code)
    if arguments.command in {"diagnose", "baseline"}:
        exit_code, result = execute_baseline(
            protocol_path=arguments.protocol,
            record_path=arguments.record,
            diagnostic_receipt_path=arguments.diagnostic_receipt,
        )
    elif arguments.command == "development":
        exit_code, result = execute_development(
            protocol_path=arguments.protocol,
            baseline_path=arguments.baseline,
            record_path=arguments.record,
            diagnostic_receipt_path=arguments.diagnostic_receipt,
        )
    elif arguments.command == "validate-baseline":
        exit_code, result = _validate_baseline_command(
            arguments.protocol, arguments.artifact
        )
    elif arguments.command == "validate-development":
        exit_code, result = _validate_development_command(
            arguments.protocol,
            arguments.baseline,
            arguments.artifact
        )
    else:
        exit_code, result = _validate_receipt_command(arguments.receipt)
    sys.stdout.buffer.write(_render_result(result))
    return exit_code


def _validate_baseline_command(
    protocol_path: Path, artifact_path: Path
) -> tuple[int, dict[str, object]]:
    try:
        from mke.evaluation.agent_context_unit_baseline_artifact import (
            validate_agent_context_unit_baseline_artifact,
        )
        from mke.evaluation.agent_context_unit_grading_protocol import (
            load_agent_context_unit_baseline_grading_payload,
        )

        payload = load_agent_context_unit_baseline_grading_payload(protocol_path)
        artifact = json.loads(artifact_path.read_bytes())
        validate_agent_context_unit_baseline_artifact(artifact, payload)
    except Exception:
        return 1, _result(
            status="failed",
            integrity_status="failed",
            stage_outcome="pre_observation_blocked",
            output_state="absent",
            publication_outcome="not_attempted",
            problem="agent_context_authority_preflight_failed",
            cause="baseline_artifact_invalid",
            next_step="correct_preflight_under_separate_authority",
            first_failed_gate="authority_preflight",
        )
    return 0, _result(
        status="passed",
        integrity_status="passed",
        stage_outcome=cast(str, artifact["stage_outcome"]),
        output_state="complete_preexisting",
        publication_outcome="not_attempted",
    )


def _validate_receipt_command(
    receipt_path: Path,
) -> tuple[int, dict[str, object]]:
    try:
        receipt = json.loads(receipt_path.read_bytes())
        validate_agent_context_diagnostic_receipt(receipt)
    except Exception:
        return 1, _result(
            status="failed",
            integrity_status="failed",
            stage_outcome="pre_observation_blocked",
            output_state="absent",
            publication_outcome="not_attempted",
            problem="agent_context_authority_preflight_failed",
            cause="diagnostic_receipt_invalid",
            next_step="correct_preflight_under_separate_authority",
            first_failed_gate="authority_preflight",
        )
    return 0, _result(
        status="passed",
        integrity_status="passed",
        stage_outcome="receipt_validated",
        output_state="complete_preexisting",
        publication_outcome="not_attempted",
        diagnostic_receipt_status="complete_visible",
        diagnostic_receipt_sha256=hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest(),
    )


def _validate_development_command(
    protocol_path: Path,
    baseline_path: Path,
    artifact_path: Path,
) -> tuple[int, dict[str, object]]:
    try:
        from mke.evaluation.agent_context_unit_artifact import (
            validate_agent_context_unit_development_artifact,
        )
        from mke.evaluation.agent_context_unit_baseline_artifact import (
            load_retained_agent_context_unit_baseline_authority,
        )

        content = _read_no_follow_absolute(artifact_path)
        artifact = validate_agent_context_unit_development_artifact(content)
        protocol = load_agent_context_unit_protocol_authority(protocol_path)
        baseline = load_retained_agent_context_unit_baseline_authority(
            _read_no_follow_absolute(baseline_path)
        )
        artifact_authority = cast(
            dict[str, str], artifact["authority"]
        )
        if (
            artifact_authority["protocol_sha256"]
            != protocol.protocol_read.identity["sha256"]
            or artifact_authority["fixture_sha256"]
            != protocol.scientific_lock_read.identity["sha256"]
            or artifact_authority["baseline_artifact_sha256"]
            != baseline.artifact_sha256
            or artifact_authority["baseline_content_digest"]
            != baseline.content_digest
        ):
            raise ValueError("development artifact retained authority differs")
        statuses = cast(dict[str, str], artifact["mechanism_statuses"])
        payload = cast(dict[str, Any], artifact["grading_authority"])
        mechanism_ids = cast(dict[str, str], payload["mechanism_ids"])
        public_statuses = {
            mechanism_ids[key]: value
            for key, value in statuses.items()
        }
    except Exception:
        return 1, _result(
            status="failed",
            integrity_status="failed",
            stage_outcome="pre_observation_blocked",
            output_state="absent",
            publication_outcome="not_attempted",
            problem="agent_context_authority_preflight_failed",
            cause="development_artifact_invalid",
            next_step="correct_preflight_under_separate_authority",
            first_failed_gate="artifact_validation",
            phase="development",
        )
    return 0, _result(
        status="passed",
        integrity_status="passed",
        stage_outcome=cast(str, artifact["stage_outcome"]),
        output_state="complete_preexisting",
        publication_outcome="not_attempted",
        phase="development",
        mechanism_statuses=public_statuses,
    )


if __name__ == "__main__":
    raise SystemExit(main())
