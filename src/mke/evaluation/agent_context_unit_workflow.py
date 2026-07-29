"""Thin command workflow for diagnostic-first O0 observation and pure validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sqlite3
import stat
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

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
    AgentContextProtocolMetadata,
    load_agent_context_unit_protocol_metadata,
)
from mke.evaluation.source_identity import build_source_identity

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
) -> dict[str, object]:
    result: dict[str, object] = {
        "schema_version": "mke.agent_context_unit_result.v2",
        "status": status,
        "phase": "baseline",
        "integrity_status": integrity_status,
        "stage_outcome": stage_outcome,
        "mechanism_statuses": dict(_MECHANISMS),
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
        [AgentContextObserverContract, Path, Path], tuple[AuthorityObservation, ...]
    ]
    | None = None,
) -> tuple[int, dict[str, object]]:
    repository_root = _repository_root(protocol_path)
    observation_started = False
    observation_sha256: str | None = None
    output_state = "absent"
    publication_outcome = "not_attempted"
    completed: list[AgentContextStageSuccess] = []
    try:
        _metadata, contract, authority = _preflight(
            protocol_path,
            record_path,
            diagnostic_receipt_path,
            repository_root,
        )
        completed.append(
            run_diagnostic_stage(
                AgentContextSubstage.AUTHORITY_PREFLIGHT,
                lambda: _canonical(authority),
            )
        )
        observation_started = True
        workspace_root = Path(
            tempfile.mkdtemp(prefix="mke-agent-context-v2-baseline-")
        )
        workspace = workspace_root / "workspace"
        runner = baseline_runner or _default_baseline_runner
        observations = _run_stage(
            AgentContextSubstage.RUNTIME_BASELINE,
            lambda: runner(contract, repository_root, workspace),
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
            protocol_path
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
            protocol_path=protocol_path,
            diagnostic_receipt_path=diagnostic_receipt_path,
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
            protocol_path=protocol_path,
            diagnostic_receipt_path=diagnostic_receipt_path,
            observation_sha256=observation_sha256,
            output_state=output_state,
            publication_outcome=publication_outcome,
        )


def _default_baseline_runner(
    contract: AgentContextObserverContract,
    repository_root: Path,
    workspace: Path,
) -> tuple[AuthorityObservation, ...]:
    return run_agent_context_unit_baseline(
        contract=contract,
        repository_root=repository_root,
        workspace=workspace,
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
    protocol_path: Path,
    diagnostic_receipt_path: Path,
    observation_sha256: str | None,
    output_state: str,
    publication_outcome: str,
) -> tuple[int, dict[str, object]]:
    if not observation_started:
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
        )
    root = _repository_root(protocol_path)
    metadata = load_agent_context_unit_protocol_metadata(protocol_path)
    source = build_source_identity(root, metadata.o0_evaluator_paths)
    profile = _runtime_profile()
    receipt = build_agent_context_diagnostic_receipt(
        protocol_sha256=_sha256_file(protocol_path),
        profile_sha256=hashlib.sha256(_canonical(profile)).hexdigest(),
        evaluator_source_sha256=cast(str, source["sha256"]),
        observation_sha256=observation_sha256,
        phase="baseline",
        attempt_kind="o0",
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
    )


def _preflight(
    protocol_path: Path,
    record_path: Path,
    receipt_path: Path,
    repository_root: Path,
) -> tuple[
    AgentContextProtocolMetadata,
    AgentContextObserverContract,
    dict[str, object],
]:
    if not _absent_regular_destination(record_path) or not _absent_regular_destination(
        receipt_path
    ):
        raise ValueError("output path authority is invalid")
    metadata = load_agent_context_unit_protocol_metadata(protocol_path)
    contract = load_agent_context_unit_observer_contract(protocol_path)
    evaluator = build_source_identity(repository_root, metadata.o0_evaluator_paths)
    runtime_source = build_source_identity(repository_root, _RUNTIME_SOURCE_PATHS)
    runtime_profile = _runtime_profile()
    if set(runtime_profile) != set(metadata.runtime_profile_fields):
        raise ValueError("runtime profile field inventory is invalid")
    scientific_lock = (
        repository_root
        / "tests/fixtures/agent-context-unit-v2/scientific-input-lock.json"
    )
    authority: dict[str, object] = {
        "protocol_sha256": _sha256_file(protocol_path),
        "evaluator_source_sha256": evaluator["sha256"],
        "runtime_source_sha256": runtime_source["sha256"],
        "runtime_profile": runtime_profile,
        "fixture_sha256": _sha256_file(scientific_lock),
    }
    return metadata, contract, authority


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


def _repository_root(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    for parent in resolved.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src/mke").is_dir():
            return parent
    raise ValueError("protocol repository root is invalid")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    validate = commands.add_parser("validate-baseline")
    validate.add_argument("--protocol", type=Path, required=True)
    validate.add_argument("--artifact", type=Path, required=True)
    validate.add_argument("--json", action="store_true", required=True)
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
    elif arguments.command == "validate-baseline":
        exit_code, result = _validate_baseline_command(
            arguments.protocol, arguments.artifact
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


if __name__ == "__main__":
    raise SystemExit(main())
