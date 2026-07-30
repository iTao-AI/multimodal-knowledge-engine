from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from mke.application.evidence_access import EvidenceExcerpt
from mke.evaluation import _atomic_json_publication
from mke.evaluation import agent_context_unit_grading as grading
from mke.evaluation import agent_context_unit_grading_protocol as grading_protocol
from mke.evaluation import agent_context_unit_workflow as workflow
from mke.evaluation.agent_context_unit_diagnostics import (
    AgentContextStageError,
    AgentContextStageSuccess,
    AgentContextSubstage,
    build_agent_context_diagnostic_receipt,
    render_agent_context_diagnostic_receipt,
)
from mke.evaluation.agent_context_unit_observation import (
    AuthorityObservation,
    PortableObservation,
    PortableObservationItem,
    PortableScoreToken,
)
from mke.evaluation.agent_context_unit_observer_protocol import (
    AgentContextObserverContract,
    load_agent_context_unit_observer_contract,
)
from mke.evaluation.agent_context_unit_protocol import (
    AgentContextObserverAuthority,
    AgentContextProtocolAuthority,
    build_agent_context_unit_observer_authority,
    load_agent_context_unit_protocol_authority,
)
from mke.evaluation.agent_context_unit_workflow import (
    PUBLIC_RESULT_FIELDS,
    execute_baseline,
    main,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/agent-context-unit-v2/protocol.json"
BASELINE = ROOT / "benchmarks/retrieval/agent-context-unit-v2-baseline.json"
_CANDIDATE_MODULES = (
    "agent_context_unit_segmentation.py",
    "agent_context_unit_ranking.py",
    "agent_context_unit_assembly.py",
    "agent_context_unit_grading.py",
    "agent_context_unit_artifact.py",
)
_UNEVALUATED_MECHANISMS = {
    "adjacent-page-assembly-v1": "not_evaluated",
    "deterministic-unit-rank-v1": "not_evaluated",
    "fixed-rank-delivery-v1": "not_evaluated",
    "source-context-delivery-v1": "not_evaluated",
    "source-context-index-v1": "not_evaluated",
}
_BASELINE_FIELDS = {
    "candidate_target_query_ids",
    "content_digest",
    "coverage",
    "evaluator_source_sha256",
    "fixture_sha256",
    "holdout_status",
    "integrity_status",
    "limitations",
    "mechanism_statuses",
    "observation",
    "observation_sha256",
    "phase",
    "protocol_sha256",
    "role_coverage",
    "runtime_profile",
    "runtime_profile_sha256",
    "runtime_promotion_status",
    "schema_version",
    "stage_outcome",
    "status",
    "targeted_failure_observed",
}


def _closed_diagnostic_receipt_bytes() -> bytes:
    error = AgentContextStageError(
        AgentContextSubstage.AUTHORITY_PREFLIGHT,
        "synthetic_authority_failure",
        "integrity",
    )
    receipt = build_agent_context_diagnostic_receipt(
        protocol_sha256="1" * 64,
        profile_sha256="2" * 64,
        evaluator_source_sha256="3" * 64,
        observation_sha256=None,
        phase="baseline",
        attempt_kind="o0",
        observation_started=False,
        completed=(),
        error=error,
        output_state="absent",
        publication_outcome="not_attempted",
        stderr_bytes=0,
        stderr_sha256=hashlib.sha256(b"").hexdigest(),
    )
    return render_agent_context_diagnostic_receipt(receipt)


def _copy_fixture_repository(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    shutil.copytree(ROOT / "src", repository / "src")
    shutil.copy2(ROOT / "pyproject.toml", repository / "pyproject.toml")
    target = repository / "tests/fixtures/agent-context-unit-v2"
    shutil.copytree(PROTOCOL.parent, target)
    return repository, target / "protocol.json"


def test_cli_exposes_development_and_no_holdout_command() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "mke.evaluation.agent_context_unit_workflow",
            "--help",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0
    assert "diagnose" in completed.stdout
    assert "baseline" in completed.stdout
    assert "validate-baseline" in completed.stdout
    assert "validate-receipt" in completed.stdout
    assert "development" in completed.stdout
    assert "validate-development" in completed.stdout
    assert "holdout" not in completed.stdout


def test_argparse_misuse_exits_two() -> None:
    assert main(["baseline"]) == 2


def test_validate_baseline_is_pure_and_emits_one_closed_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.json"
    exit_code = main(
        [
            "validate-baseline",
            "--protocol",
            str(PROTOCOL),
            "--artifact",
            str(missing),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert exit_code == 1
    assert captured.out.endswith("\n")
    assert captured.err == ""
    assert set(result) == PUBLIC_RESULT_FIELDS
    assert result["first_failed_gate"] == "authority_preflight"


@pytest.mark.parametrize("link_kind", ("final", "parent"))
def test_validate_baseline_rejects_symlinked_retained_authority(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    link_kind: str,
) -> None:
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    retained = real_parent / "baseline.json"
    retained.write_bytes(BASELINE.read_bytes())
    if link_kind == "final":
        artifact = tmp_path / "baseline.json"
        artifact.symlink_to(retained)
    else:
        alias = tmp_path / "alias"
        alias.symlink_to(real_parent, target_is_directory=True)
        artifact = alias / "baseline.json"

    exit_code = main(
        [
            "validate-baseline",
            "--protocol",
            str(PROTOCOL),
            "--artifact",
            str(artifact),
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert result["status"] == "failed"
    assert result["cause"] == "baseline_artifact_invalid"
    assert result["first_failed_gate"] == "authority_preflight"


@pytest.mark.parametrize("link_kind", ("final", "parent"))
def test_validate_receipt_rejects_symlinked_retained_authority(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    link_kind: str,
) -> None:
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    retained = real_parent / "receipt.json"
    retained.write_bytes(_closed_diagnostic_receipt_bytes())
    if link_kind == "final":
        receipt = tmp_path / "receipt.json"
        receipt.symlink_to(retained)
    else:
        alias = tmp_path / "alias"
        alias.symlink_to(real_parent, target_is_directory=True)
        receipt = alias / "receipt.json"

    exit_code = main(
        [
            "validate-receipt",
            "--receipt",
            str(receipt),
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert result["status"] == "failed"
    assert result["cause"] == "diagnostic_receipt_invalid"
    assert result["first_failed_gate"] == "authority_preflight"


def test_validate_baseline_uses_one_retained_snapshot_after_path_replacement(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "baseline.json"
    artifact.write_bytes(BASELINE.read_bytes())
    original_reader = workflow._read_no_follow_absolute  # pyright: ignore[reportPrivateUsage]
    read_count = 0

    def replace_after_read(path: Path) -> bytes:
        nonlocal read_count
        read_count += 1
        retained = original_reader(path)
        path.unlink()
        path.write_bytes(b"{}\n")
        return retained

    monkeypatch.setattr(
        workflow, "_read_no_follow_absolute", replace_after_read
    )
    exit_code = main(
        [
            "validate-baseline",
            "--protocol",
            str(PROTOCOL),
            "--artifact",
            str(artifact),
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert read_count == 1
    assert exit_code == 0
    assert result["status"] == "passed"
    assert result["stage_outcome"] == "baseline_red_observed"


def test_validate_receipt_uses_one_snapshot_for_validation_and_digest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = tmp_path / "receipt.json"
    retained = _closed_diagnostic_receipt_bytes()
    receipt.write_bytes(retained)
    original_reader = workflow._read_no_follow_absolute  # pyright: ignore[reportPrivateUsage]
    read_count = 0

    def replace_after_read(path: Path) -> bytes:
        nonlocal read_count
        read_count += 1
        content = original_reader(path)
        path.unlink()
        path.write_bytes(b"{}\n")
        return content

    monkeypatch.setattr(
        workflow, "_read_no_follow_absolute", replace_after_read
    )
    exit_code = main(
        [
            "validate-receipt",
            "--receipt",
            str(receipt),
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert read_count == 1
    assert exit_code == 0
    assert result["status"] == "passed"
    assert result["diagnostic_receipt_sha256"] == hashlib.sha256(
        retained
    ).hexdigest()


@pytest.mark.parametrize("command", ("validate-baseline", "validate-receipt"))
def test_retained_pure_validators_do_not_enter_observation_or_publication(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("pure retained validation entered execution")

    monkeypatch.setattr(workflow, "execute_baseline", forbidden)
    monkeypatch.setattr(workflow, "execute_development", forbidden)
    monkeypatch.setattr(
        workflow, "load_agent_context_unit_observer_contract", forbidden
    )
    monkeypatch.setattr(
        workflow, "_default_development_driver_factory", forbidden
    )
    monkeypatch.setattr(grading, "grade_context_mechanisms", forbidden)
    monkeypatch.setattr(
        grading_protocol,
        "load_agent_context_unit_development_grading_payload",
        forbidden,
    )
    monkeypatch.setattr(
        _atomic_json_publication, "publish_json_no_replace", forbidden
    )
    if command == "validate-baseline":
        arguments = [
            command,
            "--protocol",
            str(PROTOCOL),
            "--artifact",
            str(BASELINE),
            "--json",
        ]
    else:
        receipt = tmp_path / "receipt.json"
        receipt.write_bytes(_closed_diagnostic_receipt_bytes())
        arguments = [
            command,
            "--receipt",
            str(receipt),
            "--json",
        ]

    exit_code = main(arguments)
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result["status"] == "passed"


def _candidate_modules_allowed(baseline_path: Path) -> bool:
    try:
        if baseline_path.is_symlink() or not baseline_path.is_file():
            return False
        encoded = baseline_path.read_bytes()
        decoded = cast(object, json.loads(encoded))
        if not isinstance(decoded, dict):
            return False
        artifact = cast(dict[str, object], decoded)
        if (
            set(artifact) != _BASELINE_FIELDS
            or encoded
            != (
                json.dumps(
                    artifact,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode()
        ):
            return False
        digest = artifact.get("content_digest")
        without_digest = dict(artifact)
        without_digest.pop("content_digest", None)
        if (
            not isinstance(digest, str)
            or hashlib.sha256(
                json.dumps(
                    without_digest,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            != digest
        ):
            return False
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return (
        artifact.get("schema_version") == "mke.agent_context_unit_baseline.v2"
        and artifact.get("phase") == "baseline"
        and artifact.get("status") == "passed"
        and artifact.get("integrity_status") == "passed"
        and artifact.get("stage_outcome") == "baseline_red_observed"
        and artifact.get("targeted_failure_observed") is True
        and artifact.get("holdout_status") == "not_evaluated"
        and artifact.get("runtime_promotion_status") == "not_evaluated"
        and artifact.get("mechanism_statuses") == _UNEVALUATED_MECHANISMS
    )


def _assert_candidate_modules_follow_baseline(
    repository_root: Path, baseline_path: Path
) -> None:
    if _candidate_modules_allowed(baseline_path):
        return
    for name in _CANDIDATE_MODULES:
        assert not (repository_root / "src/mke/evaluation" / name).exists()


def _write_closed_baseline(path: Path, artifact: dict[str, object]) -> None:
    record = dict(artifact)
    record.pop("content_digest", None)
    record["content_digest"] = hashlib.sha256(
        json.dumps(
            record, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode()
    ).hexdigest()
    path.write_bytes(
        (
            json.dumps(
                record,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()
    )


def _candidate_gate_repository(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    module_root = repository / "src/mke/evaluation"
    module_root.mkdir(parents=True)
    (module_root / "agent_context_unit_segmentation.py").write_text(
        "# candidate\n", encoding="utf-8"
    )
    return repository, tmp_path / "baseline.json"


def test_candidate_modules_remain_absent_without_canonical_baseline(
    tmp_path: Path,
) -> None:
    repository, missing = _candidate_gate_repository(tmp_path)

    with pytest.raises(AssertionError):
        _assert_candidate_modules_follow_baseline(repository, missing)

    (repository / "src/mke/evaluation/agent_context_unit_segmentation.py").unlink()
    _assert_candidate_modules_follow_baseline(repository, missing)


def test_docs_regression_only_baseline_keeps_candidate_modules_absent(
    tmp_path: Path,
) -> None:
    repository, baseline = _candidate_gate_repository(tmp_path)
    artifact = cast(dict[str, object], json.loads(BASELINE.read_bytes()))
    artifact["stage_outcome"] = "docs_regression_only"
    artifact["targeted_failure_observed"] = False
    _write_closed_baseline(baseline, artifact)

    with pytest.raises(AssertionError):
        _assert_candidate_modules_follow_baseline(repository, baseline)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("status", "failed"),
        ("integrity_status", "failed"),
        ("stage_outcome", "evaluation_inconclusive"),
        ("targeted_failure_observed", False),
        ("holdout_status", "passed"),
        ("runtime_promotion_status", "promoted"),
        ("mechanism_statuses", {}),
        ("unknown_field", True),
    ),
)
def test_invalid_baseline_state_fails_candidate_modules_closed(
    tmp_path: Path, field: str, value: object
) -> None:
    repository, baseline = _candidate_gate_repository(tmp_path)
    artifact = cast(dict[str, object], json.loads(BASELINE.read_bytes()))
    artifact[field] = value
    _write_closed_baseline(baseline, artifact)

    with pytest.raises(AssertionError):
        _assert_candidate_modules_follow_baseline(repository, baseline)


def test_candidate_modules_remain_absent() -> None:
    assert _candidate_modules_allowed(BASELINE)
    _assert_candidate_modules_follow_baseline(ROOT, BASELINE)


def _synthetic_authority() -> AuthorityObservation:
    item = PortableObservationItem(
        content_fingerprint="sha256:" + "1" * 64,
        locator_kind="page",
        locator_start=1,
        locator_end=1,
        text_sha256="sha256:" + "2" * 64,
        route="fts5",
        rank=1,
        score=PortableScoreToken("fts5_rank", (-1.0).hex(), (-1.0).hex()),
        hints=("volcano",),
        excerpt=EvidenceExcerpt(
            "query_window", "volcano", 0, 7, False, False, True, 7
        ),
        exact_read_sha256="sha256:" + "2" * 64,
        original_utf8_bytes=7,
        excerpt_utf8_bytes=7,
        exact_read_utf8_bytes=7,
    )
    portable = PortableObservation(
        query_id="q-synthetic",
        query_text="volcano",
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
        delivered_utf8_bytes=7,
    )
    return AuthorityObservation(
        portable,
        ("src_" + "1" * 32,),
        ("pub_" + "2" * 32,),
        ("run_" + "3" * 32,),
        ("ev_" + "4" * 32,),
    )


def test_synthetic_baseline_publishes_noncanonical_artifact_without_receipt(
    tmp_path: Path,
) -> None:
    record = tmp_path / "baseline.json"
    receipt = tmp_path / "receipt.json"

    def observe(
        _contract: object,
        _root: Path,
        workspace: Path,
        start_observation: Callable[[], None],
    ) -> tuple[AuthorityObservation, ...]:
        assert not workspace.exists()
        start_observation()
        return (_synthetic_authority(),)

    exit_code, result = execute_baseline(
        protocol_path=PROTOCOL,
        record_path=record,
        diagnostic_receipt_path=receipt,
        baseline_runner=observe,
    )

    assert exit_code == 0
    assert result["status"] == "passed"
    assert record.is_file()
    assert not receipt.exists()


def test_started_synthetic_failure_publishes_receipt_and_no_artifact(
    tmp_path: Path,
) -> None:
    record = tmp_path / "baseline.json"
    receipt = tmp_path / "receipt.json"

    def fail(
        _contract: object,
        _root: Path,
        _workspace: Path,
        start_observation: Callable[[], None],
    ) -> tuple[AuthorityObservation, ...]:
        start_observation()
        raise AgentContextStageError(
            AgentContextSubstage.RUNTIME_BASELINE,
            "synthetic_runtime_failure",
            "integrity",
        )

    exit_code, result = execute_baseline(
        protocol_path=PROTOCOL,
        record_path=record,
        diagnostic_receipt_path=receipt,
        baseline_runner=fail,
    )

    assert exit_code == 1
    assert result["first_failed_gate"] == "runtime_baseline"
    assert result["diagnostic_receipt_status"] == "complete_visible"
    assert receipt.is_file()
    assert not record.exists()


def test_started_failure_receipt_uses_retained_preflight_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = tmp_path / "baseline.json"
    receipt = tmp_path / "receipt.json"
    preflight_evaluator = "a" * 64
    preflight_profile = workflow._runtime_profile()  # pyright: ignore[reportPrivateUsage]
    protocol_digest = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    later_evaluator = "b" * 64
    later_profile = {**preflight_profile, "python": "later"}
    source_calls = 0
    profile_calls = 0

    def source_identity(
        _root: Path, _paths: object
    ) -> dict[str, object]:
        nonlocal source_calls
        source_calls += 1
        digest = (
            preflight_evaluator
            if source_calls == 1
            else ("e" * 64 if source_calls == 2 else later_evaluator)
        )
        return {
            "schema_version": "test",
            "files": [],
            "sha256": digest,
        }

    def runtime_profile() -> dict[str, object]:
        nonlocal profile_calls
        profile_calls += 1
        return (
            dict(preflight_profile)
            if profile_calls == 1
            else dict(later_profile)
        )

    monkeypatch.setattr(workflow, "build_source_identity", source_identity)
    monkeypatch.setattr(workflow, "_runtime_profile", runtime_profile)

    def fail(
        _contract: object,
        _root: Path,
        _workspace: Path,
        start_observation: Callable[[], None],
    ) -> tuple[AuthorityObservation, ...]:
        start_observation()
        raise AgentContextStageError(
            AgentContextSubstage.RUNTIME_BASELINE,
            "synthetic_runtime_failure",
            "integrity",
        )

    exit_code, result = execute_baseline(
        protocol_path=PROTOCOL,
        record_path=record,
        diagnostic_receipt_path=receipt,
        baseline_runner=fail,
    )

    retained = json.loads(receipt.read_bytes())
    assert exit_code == 1
    assert result["diagnostic_receipt_status"] == "complete_visible"
    assert retained["protocol_sha256"] == protocol_digest
    assert retained["evaluator_source_sha256"] == preflight_evaluator
    assert retained["profile_sha256"] == workflow.hashlib.sha256(
        workflow._canonical(preflight_profile)  # pyright: ignore[reportPrivateUsage]
    ).hexdigest()
    assert source_calls == 2
    assert profile_calls == 1


def test_protocol_swap_during_preflight_cannot_change_retained_receipt_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, protocol = _copy_fixture_repository(tmp_path)
    record = tmp_path / "baseline.json"
    receipt = tmp_path / "receipt.json"
    original_bytes = protocol.read_bytes()
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()
    replacement = json.loads(original_bytes)
    replacement["candidate_profile"]["hard_page_boundary"] = False
    replacement_bytes = (
        json.dumps(
            replacement,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    observer_loader = workflow.load_agent_context_unit_observer_contract
    swapped = False

    def swap_before_observer(authority: AgentContextObserverAuthority):
        nonlocal swapped
        if not swapped:
            protocol.write_bytes(replacement_bytes)
            swapped = True
        return observer_loader(authority)

    monkeypatch.setattr(
        workflow,
        "load_agent_context_unit_observer_contract",
        swap_before_observer,
    )
    protocol_authority, _contract, retained = workflow._preflight(  # pyright: ignore[reportPrivateUsage]
        protocol,
        record,
        receipt,
        repository,
    )
    error = AgentContextStageError(
        AgentContextSubstage.RUNTIME_BASELINE,
        "synthetic_runtime_failure",
        "integrity",
        completed=(
            AgentContextStageSuccess(
                AgentContextSubstage.AUTHORITY_PREFLIGHT,
                "f" * 64,
            ),
        ),
    )
    _exit_code, result = workflow._failure_result(  # pyright: ignore[reportPrivateUsage]
        error=error,
        observation_started=True,
        diagnostic_receipt_path=receipt,
        retained_authority=retained,
        observation_sha256=None,
        output_state="absent",
        publication_outcome="not_attempted",
    )

    retained_receipt = json.loads(receipt.read_bytes())
    assert swapped is True
    assert protocol_authority.protocol_read.content == original_bytes
    assert retained["protocol_sha256"] == original_sha256
    assert retained_receipt["protocol_sha256"] == original_sha256
    assert result["diagnostic_receipt_status"] == "complete_visible"


def test_preflight_passes_only_label_blind_observer_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, protocol = _copy_fixture_repository(tmp_path)
    observer_loader = workflow.load_agent_context_unit_observer_contract
    delivered: list[object] = []

    def capture_observer_authority(authority: AgentContextObserverAuthority):
        delivered.append(authority)
        return observer_loader(authority)

    monkeypatch.setattr(
        workflow,
        "load_agent_context_unit_observer_contract",
        capture_observer_authority,
    )
    protocol_authority, contract, _retained = workflow._preflight(  # pyright: ignore[reportPrivateUsage]
        protocol,
        tmp_path / "baseline.json",
        tmp_path / "receipt.json",
        repository,
    )

    assert len(delivered) == 1
    observer_authority = delivered[0]
    assert type(observer_authority).__name__ == "AgentContextObserverAuthority"
    assert set(vars(observer_authority)) == {
        "repository_root",
        "source_ids",
        "query_ids",
        "source_receipts",
        "observer_cases",
        "source_projection_sha256",
        "case_projection_sha256",
    }
    serialized = repr(observer_authority).lower()
    for forbidden in (
        "scientific_lock",
        "required_span",
        "labels",
        "holdout",
        "grading",
        "protocol_read",
        "metadata",
    ):
        assert forbidden not in serialized
    assert protocol_authority.scientific_lock_read.content
    assert len(contract.sources) == 7
    assert len(contract.cases) == 11


def test_post_seal_grading_uses_retained_protocol_after_path_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _repository, protocol = _copy_fixture_repository(tmp_path)
    record = tmp_path / "baseline.json"
    receipt = tmp_path / "receipt.json"
    original_protocol = protocol.read_bytes()
    replacement = json.loads(original_protocol)
    replacement["candidate_profile"]["hard_page_boundary"] = False
    replacement_bytes = (
        json.dumps(
            replacement,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    observer_loader = workflow.load_agent_context_unit_observer_contract
    original_seal = workflow.seal_portable_observations
    observation_sealed = False

    def replace_after_observer(authority: AgentContextObserverAuthority):
        contract = observer_loader(authority)
        protocol.write_bytes(replacement_bytes)
        return contract

    def record_seal(observations: tuple[PortableObservation, ...]):
        nonlocal observation_sealed
        sealed = original_seal(observations)
        observation_sealed = True
        return sealed

    grading_module = importlib.import_module(
        "mke.evaluation.agent_context_unit_grading_protocol"
    )
    grading_loader = grading_module.load_agent_context_unit_baseline_grading_payload
    grading_authorities: list[AgentContextProtocolAuthority] = []

    def capture_grading_authority(authority: AgentContextProtocolAuthority):
        assert observation_sealed is True
        grading_authorities.append(authority)
        return grading_loader(authority)

    monkeypatch.setattr(
        workflow,
        "load_agent_context_unit_observer_contract",
        replace_after_observer,
    )
    monkeypatch.setattr(workflow, "seal_portable_observations", record_seal)
    monkeypatch.setattr(
        grading_module,
        "load_agent_context_unit_baseline_grading_payload",
        capture_grading_authority,
    )

    def observe(
        _contract: object,
        _root: Path,
        _workspace: Path,
        start_observation: Callable[[], None],
    ) -> tuple[AuthorityObservation, ...]:
        start_observation()
        return (_synthetic_authority(),)

    exit_code, result = execute_baseline(
        protocol_path=protocol,
        record_path=record,
        diagnostic_receipt_path=receipt,
        baseline_runner=observe,
    )

    assert exit_code == 0
    assert result["status"] == "passed"
    assert len(grading_authorities) == 1
    retained = grading_authorities[0]
    assert isinstance(retained, AgentContextProtocolAuthority)
    assert retained.protocol_read.content == original_protocol
    assert record.is_file()
    assert not receipt.exists()


def test_mkdtemp_failure_before_source_open_has_no_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = tmp_path / "baseline.json"
    receipt = tmp_path / "receipt.json"

    def fail_workspace(*_args: object, **_kwargs: object) -> Path:
        raise OSError("private")

    monkeypatch.setattr(
        "mke.evaluation.agent_context_unit_workflow.tempfile.mkdtemp",
        fail_workspace,
    )

    exit_code, result = execute_baseline(
        protocol_path=PROTOCOL,
        record_path=record,
        diagnostic_receipt_path=receipt,
    )

    assert exit_code == 1
    assert result["stage_outcome"] == "pre_observation_blocked"
    assert result["diagnostic_receipt_status"] == "absent"
    assert not receipt.exists()
    assert not record.exists()


def test_runner_setup_failure_before_source_open_has_no_receipt(
    tmp_path: Path,
) -> None:
    record = tmp_path / "baseline.json"
    receipt = tmp_path / "receipt.json"

    def fail_before_open(
        _contract: object,
        _root: Path,
        _workspace: Path,
        _start_observation: Callable[[], None],
    ) -> tuple[AuthorityObservation, ...]:
        raise OSError("private")

    exit_code, result = execute_baseline(
        protocol_path=PROTOCOL,
        record_path=record,
        diagnostic_receipt_path=receipt,
        baseline_runner=fail_before_open,
    )

    assert exit_code == 1
    assert result["stage_outcome"] == "pre_observation_blocked"
    assert result["diagnostic_receipt_status"] == "absent"
    assert not receipt.exists()
    assert not record.exists()


def test_visible_publication_failure_is_retained_and_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = tmp_path / "baseline.json"
    receipt = tmp_path / "receipt.json"
    calls = 0
    fsync = _atomic_json_publication._fsync_directory  # pyright: ignore[reportPrivateUsage]

    def fail_first_directory_sync(path: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError
        fsync(path)

    monkeypatch.setattr(
        _atomic_json_publication, "_fsync_directory", fail_first_directory_sync
    )

    def observe(
        _contract: object,
        _root: Path,
        _workspace: Path,
        start_observation: Callable[[], None],
    ) -> tuple[AuthorityObservation, ...]:
        start_observation()
        return (_synthetic_authority(),)

    exit_code, result = execute_baseline(
        protocol_path=PROTOCOL,
        record_path=record,
        diagnostic_receipt_path=receipt,
        baseline_runner=observe,
    )

    assert exit_code == 1
    assert result["first_failed_gate"] == "publication"
    assert result["output_state"] == "complete_visible"
    assert result["publication_outcome"] == "durability_unconfirmed"
    assert record.is_file()
    assert receipt.is_file()


def test_observer_import_graph_does_not_open_grading_authority() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys;"
                "import mke.evaluation.agent_context_unit_observation;"
                "import mke.evaluation.agent_context_unit_baseline;"
                "import mke.evaluation.agent_context_unit_diagnostics;"
                "assert 'mke.evaluation.agent_context_unit_grading_protocol' "
                "not in sys.modules"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def _empty_mechanism_case(
    case: Any,
    mechanism_id: str,
    rank_profile_id: str,
) -> grading.MechanismCaseObservation:
    return grading.MechanismCaseObservation(
        query_id=case.query_id,
        mechanism_id=mechanism_id,
        route=("fts" if case.runtime_route_profile == "fts5" else "cjk"),
        rank_profile_id=rank_profile_id,
        query_terms=tuple(case.query_text.casefold().split()),
        retrieval_text="",
        candidate_count=0,
        unique_parent_count=0,
        ranked=(),
        selected_stable_identities=(),
        delivered_ranges=(),
        context_ranges=(),
        delivered_utf8_bytes=0,
        context_attribution_unique=True,
        output_complete=True,
        exact_read_complete=True,
        provenance_exact=True,
    )


def _seal_cases(
    contract: Any,
    mechanism_id: str,
    query_ids: tuple[str, ...],
) -> grading.SealedMechanismObservation:
    profiles = {
        "deterministic-unit-rank-v1": "deterministic-unit-rank-v1",
        "fixed-rank-delivery-v1": "deterministic-unit-rank-v1",
        "source-context-index-v1": "source-context-index-v1:heading:rank",
        "source-context-delivery-v1": "deterministic-unit-rank-v1",
        "adjacent-page-assembly-v1": "deterministic-unit-rank-v1",
    }
    by_query = {case.query_id: case for case in contract.cases}
    return grading.seal_mechanism_observation(
        mechanism_id,
        tuple(
            _empty_mechanism_case(
                by_query[query_id],
                mechanism_id,
                profiles[mechanism_id],
            )
            for query_id in query_ids
        ),
    )


class _SyntheticDevelopmentDriver:
    def __init__(
        self,
        *,
        contract: Any,
        workspace: Path,
        start_observation: Callable[[], None],
        events: list[object],
        mutate_intermediate: bool = False,
        mutate_complete: bool = False,
        forge_gate_digest: bool = False,
    ) -> None:
        self._contract = contract
        self._workspace = workspace
        self._start_observation = start_observation
        self._events = events
        self._mutate_intermediate = mutate_intermediate
        self._mutate_complete = mutate_complete
        self._forge_gate_digest = forge_gate_digest

    def observe_o1_o2(self) -> Any:
        assert not self._workspace.exists()
        self._workspace.mkdir(parents=True)
        self._start_observation()
        self._events.append(("base", self._workspace))
        query_ids = tuple(case.query_id for case in self._contract.cases)
        o1 = _seal_cases(
            self._contract,
            "deterministic-unit-rank-v1",
            query_ids,
        )
        o2 = _seal_cases(
            self._contract,
            "fixed-rank-delivery-v1",
            query_ids,
        )
        if self._mutate_intermediate:
            first, *rest = o2.cases
            o2 = grading.seal_mechanism_observation(
                o2.mechanism_id,
                (
                    replace(first, retrieval_text="workspace drift"),
                    *rest,
                ),
            )
        return workflow.CandidateIntermediateObservation(
            observations=(o1, o2),
            source_snapshot_bytes=b"source-snapshot-v1",
            unit_projection_bytes=b"unit-projection-v1",
            unit_rank_bytes=o1.portable_bytes,
            fixed_rank_delivery_bytes=o2.portable_bytes,
        )

    def observe_residual(
        self,
        dispatches: tuple[Any, ...],
    ) -> Any:
        self._events.append(("residual", self._workspace, dispatches))
        forbidden = {
            "grading_payload",
            "required_spans",
            "labels",
            "qrels",
            "expected_locators",
            "hypothesis",
            "verdict",
        }
        assert all(
            forbidden.isdisjoint(
                cast(dict[str, object], vars(dispatch))
            )
            for dispatch in dispatches
        )
        observations: tuple[grading.SealedMechanismObservation, ...] = tuple(
            _seal_cases(
                self._contract,
                dispatch.mechanism_id,
                dispatch.query_ids,
            )
            for dispatch in dispatches
            if dispatch.enabled
        )
        if self._mutate_complete and not observations:
            dispatch = dispatches[0]
            observations = (
                _seal_cases(
                    self._contract,
                    dispatch.mechanism_id,
                    dispatch.query_ids,
                ),
            )
        if self._mutate_complete and observations:
            first_observation, *rest_observations = observations
            first_case, *rest_cases = first_observation.cases
            observations = (
                grading.seal_mechanism_observation(
                    first_observation.mechanism_id,
                    (
                        replace(first_case, retrieval_text="workspace drift"),
                        *rest_cases,
                    ),
                ),
                *rest_observations,
            )
        gate_digest = (
            "f" * 64
            if self._forge_gate_digest
            else dispatches[0].gate_digest
        )
        by_mechanism = {item.mechanism_id: item for item in observations}
        stage_override = b"not-evaluated" if self._mutate_complete else None

        def stage_bytes(mechanism_id: str) -> bytes:
            item = by_mechanism.get(mechanism_id)
            return (
                stage_override
                if stage_override is not None
                else (
                    b"not-evaluated"
                    if item is None
                    else item.portable_bytes
                )
            )

        return workflow.CandidateResidualObservation(
            observations=observations,
            gate_digest=gate_digest,
            adjacent_page_assembly_bytes=stage_bytes(
                "adjacent-page-assembly-v1"
            ),
            source_context_index_bytes=stage_bytes(
                "source-context-index-v1"
            ),
            source_context_delivery_bytes=stage_bytes(
                "source-context-delivery-v1"
            ),
        )


def _development_driver_factory(
    events: list[object],
    *,
    mutate_intermediate_b: bool = False,
    mutate_complete_b: bool = False,
    forge_gate_b: bool = False,
) -> Callable[..., _SyntheticDevelopmentDriver]:
    created = 0

    def factory(
        contract: Any,
        _repository_root: Path,
        workspace: Path,
        start_observation: Callable[[], None],
    ) -> _SyntheticDevelopmentDriver:
        nonlocal created
        created += 1
        return _SyntheticDevelopmentDriver(
            contract=contract,
            workspace=workspace,
            start_observation=start_observation,
            events=events,
            mutate_intermediate=mutate_intermediate_b and created == 2,
            mutate_complete=mutate_complete_b and created == 2,
            forge_gate_digest=forge_gate_b and created == 2,
        )

    return factory


def _execute_synthetic_development(
    tmp_path: Path,
    *,
    events: list[object] | None = None,
    factory: Callable[..., Any] | None = None,
    stage_faults: dict[AgentContextSubstage, Callable[[], None]] | None = None,
) -> tuple[int, dict[str, object], Path, Path]:
    record = tmp_path / "development.json"
    receipt = tmp_path / "receipt.json"
    event_log = events if events is not None else []
    exit_code, result = workflow.execute_development(
        protocol_path=PROTOCOL,
        baseline_path=BASELINE,
        record_path=record,
        diagnostic_receipt_path=receipt,
        development_driver_factory=(
            factory or _development_driver_factory(event_log)
        ),
        stage_faults=stage_faults,
        synthetic_noncanonical=True,
    )
    return exit_code, result, record, receipt


def test_development_orders_intermediate_seal_before_single_label_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []
    original = grading_protocol.load_agent_context_unit_development_grading_payload
    label_calls = 0

    def load_once(authority: AgentContextProtocolAuthority):
        nonlocal label_calls
        label_calls += 1
        events.append("labels")
        return original(authority)

    monkeypatch.setattr(
        grading_protocol,
        "load_agent_context_unit_development_grading_payload",
        load_once,
    )

    exit_code, result, record, receipt = _execute_synthetic_development(
        tmp_path,
        events=events,
    )

    assert exit_code == 0
    assert result["phase"] == "development"
    assert result["integrity_status"] == "passed"
    assert record.is_file()
    assert not receipt.exists()
    assert label_calls == 1
    assert [
        cast(tuple[object, ...], event)[0] for event in events[:2]
    ] == ["base", "base"]
    assert events[2] == "labels"
    assert [
        cast(tuple[object, ...], event)[0] for event in events[3:]
    ] == ["residual", "residual"]
    workspace_paths = [cast(tuple[object, Path], event)[1] for event in events[:2]]
    assert workspace_paths[0] != workspace_paths[1]
    residual_dispatches = cast(tuple[object, Path, tuple[Any, ...]], events[3])[2]
    assert residual_dispatches
    assert all(
        type(dispatch) is workflow.CandidateGateDispatch
        for dispatch in residual_dispatches
    )
    assert len({dispatch.gate_digest for dispatch in residual_dispatches}) == 1


def test_development_rejects_non_red_retained_baseline_before_candidate_start(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.json"
    artifact = cast(dict[str, object], json.loads(BASELINE.read_bytes()))
    artifact["stage_outcome"] = "docs_regression_only"
    artifact["targeted_failure_observed"] = False
    _write_closed_baseline(baseline, artifact)
    events: list[object] = []

    exit_code, result = workflow.execute_development(
        protocol_path=PROTOCOL,
        baseline_path=baseline,
        record_path=tmp_path / "development.json",
        diagnostic_receipt_path=tmp_path / "receipt.json",
        development_driver_factory=_development_driver_factory(events),
        synthetic_noncanonical=True,
    )

    assert exit_code == 1
    assert result["stage_outcome"] == "pre_observation_blocked"
    assert result["first_failed_gate"] == "runtime_baseline"
    assert events == []
    assert not (tmp_path / "development.json").exists()
    assert not (tmp_path / "receipt.json").exists()


def test_development_rejects_symlinked_retained_baseline_before_candidate_start(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.symlink_to(BASELINE)
    events: list[object] = []

    exit_code, result = workflow.execute_development(
        protocol_path=PROTOCOL,
        baseline_path=baseline,
        record_path=tmp_path / "development.json",
        diagnostic_receipt_path=tmp_path / "receipt.json",
        development_driver_factory=_development_driver_factory(events),
        synthetic_noncanonical=True,
    )

    assert exit_code == 1
    assert result["stage_outcome"] == "pre_observation_blocked"
    assert result["first_failed_gate"] == "runtime_baseline"
    assert events == []
    assert not (tmp_path / "development.json").exists()
    assert not (tmp_path / "receipt.json").exists()


def test_development_rejects_intermediate_workspace_mismatch_before_label_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []
    label_calls = 0

    def forbidden_label_open(_authority: object) -> object:
        nonlocal label_calls
        label_calls += 1
        raise AssertionError("labels opened before intermediate equality")

    monkeypatch.setattr(
        grading_protocol,
        "load_agent_context_unit_development_grading_payload",
        forbidden_label_open,
    )

    exit_code, result, record, receipt = _execute_synthetic_development(
        tmp_path,
        events=events,
        factory=_development_driver_factory(
            events,
            mutate_intermediate_b=True,
        ),
    )

    assert exit_code == 1
    assert result["first_failed_gate"] == "unit_rank"
    assert result["cause"] == "workspace_intermediate_portable_mismatch"
    assert label_calls == 0
    assert not record.exists()
    assert receipt.is_file()


def test_development_rejects_complete_workspace_mismatch(
    tmp_path: Path,
) -> None:
    events: list[object] = []

    exit_code, result, record, receipt = _execute_synthetic_development(
        tmp_path,
        events=events,
        factory=_development_driver_factory(events, mutate_complete_b=True),
    )

    assert exit_code == 1
    assert result["first_failed_gate"] == "complete_observation_seal"
    assert result["cause"] == "workspace_complete_portable_mismatch"
    assert not record.exists()
    assert receipt.is_file()


def test_development_rejects_forged_candidate_gate_digest(
    tmp_path: Path,
) -> None:
    events: list[object] = []

    exit_code, result, record, receipt = _execute_synthetic_development(
        tmp_path,
        events=events,
        factory=_development_driver_factory(events, forge_gate_b=True),
    )

    assert exit_code == 1
    assert result["first_failed_gate"] == "adjacent_page_assembly"
    assert result["cause"] == "residual_gate_dispatch_mismatch"
    assert not record.exists()
    assert receipt.is_file()


@pytest.mark.parametrize("failure", ("grading_payload", "gate_derivation"))
def test_development_reports_pre_dispatch_gate_failures_at_residual_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    events: list[object] = []

    def fail(*_args: object, **_kwargs: object) -> object:
        raise AgentContextStageError(
            AgentContextSubstage.RESIDUAL_GATE,
            f"synthetic_{failure}_failure",
            "authority",
        )

    if failure == "grading_payload":
        monkeypatch.setattr(
            grading_protocol,
            "load_agent_context_unit_development_grading_payload",
            fail,
        )
    else:
        monkeypatch.setattr(grading, "derive_residual_gates", fail)

    exit_code, result, record, receipt = _execute_synthetic_development(
        tmp_path,
        events=events,
    )

    assert exit_code == 1
    assert result["first_failed_gate"] == "residual_gate"
    assert result["cause"] == f"synthetic_{failure}_failure"
    assert [
        cast(tuple[object, ...], event)[0] for event in events
    ] == ["base", "base"]
    assert not record.exists()
    assert receipt.is_file()


def test_development_residual_gate_fault_prevents_candidate_dispatch(
    tmp_path: Path,
) -> None:
    events: list[object] = []

    def fail() -> None:
        raise AgentContextStageError(
            AgentContextSubstage.RESIDUAL_GATE,
            "synthetic_residual_gate_failure",
            "integrity",
        )

    exit_code, result, record, receipt = _execute_synthetic_development(
        tmp_path,
        events=events,
        stage_faults={AgentContextSubstage.RESIDUAL_GATE: fail},
    )

    assert exit_code == 1
    assert result["first_failed_gate"] == "residual_gate"
    assert result["cause"] == "synthetic_residual_gate_failure"
    assert [
        cast(tuple[object, ...], event)[0] for event in events
    ] == ["base", "base"]
    assert not record.exists()
    assert receipt.is_file()


@pytest.mark.parametrize("substage", tuple(AgentContextSubstage))
def test_development_fault_matrix_preserves_each_public_substage(
    tmp_path: Path,
    substage: AgentContextSubstage,
) -> None:
    def fail() -> None:
        raise AgentContextStageError(
            substage,
            f"synthetic_{substage.value}_failure",
            (
                "capacity"
                if substage
                in {
                    AgentContextSubstage.SOURCE_SNAPSHOT,
                    AgentContextSubstage.UNIT_PROJECTION,
                }
                else "integrity"
            ),
        )

    exit_code, result, record, receipt = _execute_synthetic_development(
        tmp_path,
        stage_faults={substage: fail},
    )

    assert exit_code == 1
    assert result["first_failed_gate"] == substage.value
    assert result["cause"] == f"synthetic_{substage.value}_failure"
    assert not record.exists()
    if substage in {
        AgentContextSubstage.AUTHORITY_PREFLIGHT,
        AgentContextSubstage.RUNTIME_BASELINE,
    }:
        assert result["stage_outcome"] == "pre_observation_blocked"
        assert not receipt.exists()
    else:
        assert result["stage_outcome"] == "evaluation_inconclusive"
        assert receipt.is_file()


@pytest.mark.parametrize(
    ("substage", "error_code", "error_family"),
    (
        (
            AgentContextSubstage.SOURCE_SNAPSHOT,
            "candidate_source_capacity_exceeded",
            "capacity",
        ),
        (
            AgentContextSubstage.UNIT_PROJECTION,
            "candidate_projection_capacity_exceeded",
            "capacity",
        ),
        (
            AgentContextSubstage.UNIT_RANK,
            "candidate_observation_integrity_failed",
            "integrity",
        ),
        (
            AgentContextSubstage.SOURCE_CONTEXT_DELIVERY,
            "source_context_attribution_mismatch",
            "authority",
        ),
        (
            AgentContextSubstage.PUBLICATION,
            "output_visibility_state_invalid",
            "publication",
        ),
    ),
)
def test_development_historical_fault_classes_keep_distinct_taxonomy(
    tmp_path: Path,
    substage: AgentContextSubstage,
    error_code: str,
    error_family: str,
) -> None:
    def fail() -> None:
        raise AgentContextStageError(
            substage,
            error_code,
            error_family,
        )

    exit_code, result, record, receipt = _execute_synthetic_development(
        tmp_path,
        stage_faults={substage: fail},
    )

    assert exit_code == 1
    assert result["first_failed_gate"] == substage.value
    assert result["cause"] == error_code
    assert not record.exists()
    assert receipt.is_file()


def test_validate_development_is_pure_and_does_not_create_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exit_code, _result, record, receipt = _execute_synthetic_development(
        tmp_path
    )
    assert exit_code == 0
    before = record.read_bytes()
    assert not receipt.exists()

    def forbidden_factory(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("pure validation entered candidate observation")

    monkeypatch.setattr(
        workflow,
        "_default_development_driver_factory",
        forbidden_factory,
        raising=False,
    )
    validate_exit = main(
        [
            "validate-development",
            "--protocol",
            str(PROTOCOL),
            "--baseline",
            str(BASELINE),
            "--artifact",
            str(record),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert validate_exit == 0
    assert result["phase"] == "development"
    assert result["output_state"] == "complete_preexisting"
    assert captured.out.endswith("\n")
    assert captured.err == ""
    assert record.read_bytes() == before
    assert not receipt.exists()


def test_default_candidate_controller_uses_fresh_synthetic_workspaces_only(
    tmp_path: Path,
) -> None:
    authority = load_agent_context_unit_protocol_authority(PROTOCOL)
    contract = load_agent_context_unit_observer_contract(
        build_agent_context_unit_observer_authority(authority)
    )
    synthetic_contract = AgentContextObserverContract(
        sources=tuple(
            source
            for source in contract.sources
            if source.source_id == "dev-synthetic-boundaries"
        ),
        cases=tuple(
            case
            for case in contract.cases
            if case.query_id == "q-misleading-name"
        ),
    )
    starts = 0

    def mark_started() -> None:
        nonlocal starts
        starts += 1

    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    driver_a = workflow._default_development_driver_factory(  # pyright: ignore[reportPrivateUsage]
        synthetic_contract,
        ROOT,
        workspace_a,
        mark_started,
    )
    driver_b = workflow._default_development_driver_factory(  # pyright: ignore[reportPrivateUsage]
        synthetic_contract,
        ROOT,
        workspace_b,
        mark_started,
    )

    result_a = driver_a.observe_o1_o2()
    result_b = driver_b.observe_o1_o2()

    assert starts == 2
    assert workspace_a.is_dir()
    assert workspace_b.is_dir()
    assert workspace_a != workspace_b
    assert result_a.stage_bytes == result_b.stage_bytes
    assert tuple(
        cast(grading.SealedMechanismObservation, item).portable_bytes
        for item in result_a.observations
    ) == tuple(
        cast(grading.SealedMechanismObservation, item).portable_bytes
        for item in result_b.observations
    )
    gate_digest = "a" * 64
    dispatches = tuple(
        workflow.CandidateGateDispatch(
            mechanism_id=mechanism_id,
            enabled=True,
            reason="synthetic_controller_self_test",
            query_ids=("q-misleading-name",),
            gate_digest=gate_digest,
        )
        for mechanism_id in (
            "source-context-index-v1",
            "source-context-delivery-v1",
            "adjacent-page-assembly-v1",
        )
    )
    residual_a = driver_a.observe_residual(dispatches)
    residual_b = driver_b.observe_residual(dispatches)
    assert residual_a.stage_bytes == residual_b.stage_bytes
    assert tuple(
        cast(grading.SealedMechanismObservation, item).portable_bytes
        for item in residual_a.observations
    ) == tuple(
        cast(grading.SealedMechanismObservation, item).portable_bytes
        for item in residual_b.observations
    )


def _o3_context_driver() -> tuple[Any, tuple[Any, ...]]:
    from mke.evaluation.agent_context_unit_ranking import (
        build_unit_projection,
    )
    from mke.evaluation.agent_context_unit_segmentation import (
        DEFAULT_SEGMENTATION_PROFILE,
        ParentPageEvidence,
        SegmentationProfile,
        segment_page_context_units,
    )

    text = (
        b"COMMON HEADING\n"
        b"alpha filler sentence.\n\n"
        b"sharedneedle middle text.\n\n"
        b"omega filler sentence.\n\n"
        b"final filler sentence."
    )
    source_fingerprint = "sha256:" + "1" * 64
    parent = ParentPageEvidence(
        source_id="opaque-source",
        source_content_fingerprint=source_fingerprint,
        publication_id="opaque-publication",
        evidence_id="opaque-evidence",
        locator_kind="page",
        locator_start=1,
        locator_end=1,
        text_bytes=text,
    )
    profile = SegmentationProfile(
        target_utf8_bytes=28,
        minimum_utf8_bytes=5,
        maximum_utf8_bytes=40,
        overlap_utf8_bytes=0,
        hard_page_boundary=True,
        original_whitespace_retained=True,
        heading_patterns=DEFAULT_SEGMENTATION_PROFILE.heading_patterns,
    )
    rows = build_unit_projection(
        segment_page_context_units(parent, profile=profile)
    )
    driver = object.__new__(workflow._CandidateWorkspaceDriver)  # pyright: ignore[reportPrivateUsage]
    driver._rows = rows  # pyright: ignore[reportPrivateUsage]
    driver._parent_text = {  # pyright: ignore[reportPrivateUsage]
        (source_fingerprint, 1): text
    }
    return driver, rows


def _o3_result(driver: Any, query_text: str) -> Any:
    return driver._rank_o3(  # pyright: ignore[reportPrivateUsage]
        SimpleNamespace(
            query_id=f"q-{query_text}",
            query_text=query_text,
            runtime_route_profile="fts5",
        ),
        None,
    )[0]


def test_o3_reuses_same_heading_for_each_page_local_unit_document() -> None:
    driver, rows = _o3_context_driver()

    result = _o3_result(driver, "COMMON HEADING")
    attributions = {
        item.stable_context_unit_id: item
        for item in result.attributions
    }

    assert (
        "heading"
        in attributions[rows[1].stable_context_unit_id].component_kinds
    )
    assert (
        "heading"
        in attributions[rows[2].stable_context_unit_id].component_kinds
    )


def test_o3_reuses_one_unit_as_context_for_two_independent_documents() -> None:
    driver, rows = _o3_context_driver()

    result = _o3_result(driver, "sharedneedle")
    attributions = {
        item.stable_context_unit_id: item
        for item in result.attributions
    }

    assert attributions[rows[0].stable_context_unit_id].component_kinds == (
        "next_unit",
    )
    assert attributions[rows[2].stable_context_unit_id].component_kinds == (
        "previous_unit",
    )


def test_o3_portable_result_is_independent_of_projection_enumeration_order() -> None:
    driver, rows = _o3_context_driver()
    canonical = _o3_result(driver, "COMMON HEADING").portable_bytes()

    driver._rows = tuple(reversed(rows))  # pyright: ignore[reportPrivateUsage]
    reordered = _o3_result(driver, "COMMON HEADING").portable_bytes()

    assert reordered == canonical
