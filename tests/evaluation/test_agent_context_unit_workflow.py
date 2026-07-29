from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from mke.application.evidence_access import EvidenceExcerpt
from mke.evaluation import _atomic_json_publication
from mke.evaluation import agent_context_unit_workflow as workflow
from mke.evaluation.agent_context_unit_diagnostics import (
    AgentContextStageError,
    AgentContextStageSuccess,
    AgentContextSubstage,
)
from mke.evaluation.agent_context_unit_observation import (
    AuthorityObservation,
    PortableObservation,
    PortableObservationItem,
    PortableScoreToken,
)
from mke.evaluation.agent_context_unit_protocol import (
    AgentContextObserverAuthority,
    AgentContextProtocolAuthority,
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


def _copy_fixture_repository(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    shutil.copytree(ROOT / "src", repository / "src")
    shutil.copy2(ROOT / "pyproject.toml", repository / "pyproject.toml")
    target = repository / "tests/fixtures/agent-context-unit-v2"
    shutil.copytree(PROTOCOL.parent, target)
    return repository, target / "protocol.json"


def test_cli_exposes_only_o0_commands() -> None:
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
    assert "development" not in completed.stdout
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
