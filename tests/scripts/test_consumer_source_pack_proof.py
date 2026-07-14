from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/consumer_source_pack_proof.py"
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
CONSUMER_WORKFLOW = ROOT / ".github/workflows/consumer-source-pack-proof.yml"

STABLE_FAILURE_CODES = (
    "source_pack_manifest_invalid",
    "source_pack_identity_mismatch",
    "wheel_build_failed",
    "environment_create_failed",
    "install_failed",
    "installed_identity_failed",
    "external_isolation_failed",
    "consumer_schema_invalid",
    "consumer_payload_invalid",
    "manifest_mapping_missing",
    "manifest_mapping_ambiguous",
    "manifest_locator_mismatch",
    "observation_state_mismatch",
    "mcp_startup_timeout",
    "mcp_tool_timeout",
    "mcp_transport_failed",
    "server_exit_nonzero",
    "command_output_exceeded",
    "candidate_artifact_invalid",
    "cleanup_failed",
    "proof_failed",
)
CLIENT_FAILURE_CODES = (
    "source_pack_manifest_invalid",
    "source_pack_identity_mismatch",
    "consumer_schema_invalid",
    "consumer_payload_invalid",
    "manifest_mapping_missing",
    "manifest_mapping_ambiguous",
    "manifest_locator_mismatch",
    "observation_state_mismatch",
    "mcp_startup_timeout",
    "mcp_tool_timeout",
    "mcp_transport_failed",
    "command_output_exceeded",
    "cleanup_failed",
    "proof_failed",
)


def _consumer_proof_job(workflow: str | None = None) -> str:
    if workflow is None:
        workflow = CONSUMER_WORKFLOW.read_text(encoding="utf-8")
    jobs = workflow.split("\njobs:\n", maxsplit=1)
    assert len(jobs) == 2
    job_names = re.findall(r"(?m)^  ([a-zA-Z0-9_-]+):\n", jobs[1])
    assert job_names == ["consumer-source-pack-proof"]
    matches = list(
        re.finditer(
            r"(?ms)^  consumer-source-pack-proof:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
            jobs[1],
        )
    )
    assert len(matches) == 1
    return matches[0].group(0)


def test_consumer_source_pack_workflow_has_bounded_repository_scope() -> None:
    workflow = CONSUMER_WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in workflow
    assert "push:\n    branches: [main]" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "concurrency:" in workflow
    assert "cancel-in-progress: true" in workflow


def test_primary_ci_workflow_remains_byte_identical_to_head() -> None:
    committed = subprocess.run(
        ["git", "show", "HEAD:.github/workflows/ci.yml"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    assert CI_WORKFLOW.read_bytes() == committed


def test_consumer_source_pack_workflow_is_one_bounded_non_matrix_job() -> None:
    job = _consumer_proof_job()
    assert "runs-on: ubuntu-latest" in job
    assert "timeout-minutes: 15" in job
    assert "matrix:" not in job
    assert job.count("scripts/consumer_source_pack_proof.py") == 1
    assert "uv build" not in job
    assert job.count("actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0") == 1
    assert job.count("astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990") == 1


def test_consumer_source_pack_workflow_rejects_a_sibling_job() -> None:
    workflow = CONSUMER_WORKFLOW.read_text(encoding="utf-8")
    mutated = workflow + "\n  unexpected-sibling:\n    runs-on: ubuntu-latest\n"
    with pytest.raises(AssertionError):
        _consumer_proof_job(mutated)


def test_consumer_source_pack_workflow_uses_both_explicit_interpreters() -> None:
    job = _consumer_proof_job()
    setup_python = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
    assert job.count(setup_python) == 2
    assert re.search(
        r'id: python312\n\s+uses: .*setup-python.*\n\s+with:\n\s+python-version: "3\.12"',
        job,
    )
    assert re.search(
        r'id: python313\n\s+uses: .*setup-python.*\n\s+with:\n\s+python-version: "3\.13"',
        job,
    )
    assert job.count('${{ steps.python312.outputs.python-path }}') == 2
    assert job.count('${{ steps.python313.outputs.python-path }}') == 2
    proof_command = job[job.index("scripts/consumer_source_pack_proof.py") :]
    assert '--python "${{ steps.python312.outputs.python-path }}"' in proof_command
    assert '--python "${{ steps.python313.outputs.python-path }}"' in proof_command


def test_consumer_source_pack_workflow_provisions_online_before_offline_proof() -> None:
    job = _consumer_proof_job()
    provision_name = "name: Provision locked cache for controller and both interpreters"
    proof_name = "name: Run offline same-wheel consumer proof"
    provision_start = job.index(provision_name)
    proof_start = job.index(proof_name)
    assert provision_start < proof_start
    provision = job[provision_start:proof_start]
    proof = job[proof_start:]

    assert "UV_OFFLINE" not in provision
    assert "uv sync --locked" in provision
    assert "uv export --locked --no-dev --no-emit-project" in provision
    assert '$RUNNER_TEMP/mke-core-requirements.txt' in provision
    for minor, step_id in (("312", "python312"), ("313", "python313")):
        environment = f'$RUNNER_TEMP/mke-prewarm-{minor}'
        assert f'uv venv "{environment}"' in provision
        assert f'--python "${{{{ steps.{step_id}.outputs.python-path }}}}"' in provision
        assert f'--python "{environment}/bin/python"' in provision
    assert provision.count("uv pip install") == 2
    assert provision.count('--requirement "$RUNNER_TEMP/mke-core-requirements.txt"') == 2

    assert 'UV_OFFLINE: "1"' in proof
    assert "UV_OFFLINE" not in job[:proof_start]
    assert "uv sync" not in proof
    assert "uv export" not in proof
    assert "uv pip install" not in proof
    assert "--offline" not in proof
    assert "--no-index" not in proof


def test_public_failure_allowlist_is_exact() -> None:
    proof = _load()
    assert proof._STABLE_FAILURE_CODES == frozenset(STABLE_FAILURE_CODES)
    assert proof._CLIENT_FAILURE_CODES == frozenset(CLIENT_FAILURE_CODES)


def _load():
    spec = importlib.util.spec_from_file_location("consumer_source_pack_proof", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _process_is_terminated(pid: int) -> bool:
    if sys.platform.startswith("linux"):
        stat = Path(f"/proc/{pid}/stat")
        try:
            state = stat.read_text(encoding="utf-8").split(") ", 1)[1][0]
        except FileNotFoundError:
            return True
        except (OSError, IndexError):
            pass
        else:
            if state == "Z":
                return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def test_process_termination_probe_falls_back_when_linux_proc_is_restricted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kill_probes: list[tuple[int, int]] = []

    def restricted_stat(_path: Path, *, encoding: str) -> str:
        del encoding
        raise PermissionError

    def live_process(pid: int, signal_number: int) -> None:
        kill_probes.append((pid, signal_number))

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "read_text", restricted_stat)
    monkeypatch.setattr(os, "kill", live_process)

    assert _process_is_terminated(12345) is False
    assert kill_probes == [(12345, 0)]


def test_isolated_environment_removes_python_contamination() -> None:
    proof = _load()
    result = proof.isolated_environment(
        {
            "PATH": "/bin",
            "LANG": "C",
            "PYTHONPATH": "secret",
            "PYTHONHOME": "bad",
            "VIRTUAL_ENV": "old",
        }
    )
    assert result == {"PATH": "/bin", "LANG": "C"}


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_run_bounded_terminates_live_noisy_process_group(tmp_path: Path, stream: str) -> None:
    proof = _load()
    pid_file = tmp_path / "pid"
    program = (
        "import os,sys,time; "
        f"open({str(pid_file)!r},'w').write(str(os.getpid())); "
        f"s=sys.{stream}.buffer; "
        "[(s.write(b'x'*4096),s.flush(),time.sleep(.001)) for _ in iter(int,1)]"
    )
    started = time.monotonic()
    with pytest.raises(proof.ControllerError, match="command_output_exceeded") as exc:
        proof.run_bounded(
            [sys.executable, "-c", program],
            cwd=tmp_path,
            env=os.environ,
            timeout_seconds=10,
            max_stdout_bytes=8192,
            max_stderr_bytes=8192,
        )
    assert exc.value.code == "command_output_exceeded"
    assert time.monotonic() - started < 3
    pid = int(pid_file.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_run_bounded_timeout_wins_before_late_output(tmp_path: Path) -> None:
    proof = _load()
    with pytest.raises(proof.ControllerError) as exc:
        proof.run_bounded(
            [sys.executable, "-c", "import time,sys; time.sleep(.2); sys.stdout.write('x'*1000)"],
            cwd=tmp_path,
            env=os.environ,
            timeout_seconds=0.03,
            max_stdout_bytes=10,
            max_stderr_bytes=10,
        )
    assert exc.value.code == "command_timed_out"


def test_group_probe_treats_unowned_or_reused_group_as_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proof = _load()

    def denied(_pgid: int, _signal: int) -> None:
        raise PermissionError

    monkeypatch.setattr(proof.os, "killpg", denied)
    assert proof._group_exists(12345) is False


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group contract")
def test_run_bounded_accepts_stale_group_probe_after_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proof = _load()
    group_observations = iter((True, False, False, True))
    terminate_calls: list[int | None] = []
    real_terminate = proof._terminate

    def stale_group_probe(_pgid: int) -> bool:
        return next(group_observations)

    monkeypatch.setattr(proof, "_group_exists", stale_group_probe)

    def tracked_terminate(process: object, pgid: int | None) -> None:
        terminate_calls.append(pgid)
        real_terminate(process, pgid)

    monkeypatch.setattr(proof, "_terminate", tracked_terminate)

    result = proof.run_bounded(
        [sys.executable, "-c", "print('parent done')"],
        cwd=tmp_path,
        env=os.environ,
        timeout_seconds=2,
        max_stdout_bytes=1024,
        max_stderr_bytes=1024,
    )

    assert result.returncode == 0
    assert result.stdout == b"parent done\n"
    assert terminate_calls


def test_run_bounded_returns_bytes_and_nonzero(tmp_path: Path) -> None:
    proof = _load()
    result = proof.run_bounded(
        [
            sys.executable,
            "-c",
            "import sys; print('ok'); print('bad',file=sys.stderr); raise SystemExit(7)",
        ],
        cwd=tmp_path,
        env=os.environ,
        timeout_seconds=2,
        max_stdout_bytes=100,
        max_stderr_bytes=100,
    )
    assert (result.returncode, result.stdout, result.stderr) == (7, b"ok\n", b"bad\n")


def test_bounded_implementation_never_uses_communicate() -> None:
    source = SCRIPT.read_text()
    assert ".communicate(" not in source
    assert "shutil.which" not in source
    assert "subprocess.Popen(" in source
    assert "start_new_session=" in source


@pytest.mark.parametrize(
    ("child", "expected"),
    [
        ("nonzero", "install_failed"),
        ("timeout", "install_failed"),
        ("overflow", "command_output_exceeded"),
    ],
)
def test_command_maps_only_approved_step_codes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, child: str, expected: str
) -> None:
    proof = _load()

    def fake(*args: object, **kwargs: object) -> Any:
        if child == "timeout":
            raise proof.ControllerError("command_timed_out")
        if child == "overflow":
            raise proof.ControllerError("command_output_exceeded")
        return proof.CommandResult(9, b"secret", b"secret")

    monkeypatch.setattr(proof, "run_bounded", fake)
    config = proof.ProofConfig(tmp_path, (Path("/a"), Path("/b")), 1, 10, 10)
    with pytest.raises(proof.ControllerError) as exc:
        proof._command("install_failed", ["child"], cwd=tmp_path, env={}, config=config)
    assert exc.value.code == expected


def test_validate_identity_rejects_contamination_and_wrong_metadata(tmp_path: Path) -> None:
    proof = _load()
    environment = tmp_path / "venv"
    repository = tmp_path / "repository"
    base = {
        "mke_file": str(environment / "lib/python/site-packages/mke/__init__.py"),
        "metadata_path": str(environment / "lib/python/site-packages/mke.dist-info"),
        "sys_executable": str(environment / "bin/python"),
        "mke_executable": str(environment / "bin/mke"),
        "metadata_version": "0.1.1",
        "module_version": "0.1.1",
    }
    proof._validate_identity(base, environment, repository)
    contaminated = dict(base, mke_file=str(repository / "src/mke/__init__.py"))
    with pytest.raises(proof.ControllerError, match="installed_identity_failed"):
        proof._validate_identity(contaminated, environment, repository)
    wrong_metadata = dict(base, metadata_path=str(environment / "lib/python/site-packages/mke"))
    with pytest.raises(proof.ControllerError, match="installed_identity_failed"):
        proof._validate_identity(wrong_metadata, environment, repository)


def test_validate_identity_accepts_exact_venv_python_symlink(
    tmp_path: Path,
) -> None:
    proof = _load()
    environment = tmp_path / "venv"
    repository = tmp_path / "repository"
    python = environment / "bin/python"
    python.parent.mkdir(parents=True)
    python.symlink_to(Path(sys.executable))
    payload = {
        "mke_file": str(environment / "lib/python/site-packages/mke/__init__.py"),
        "metadata_path": str(environment / "lib/python/site-packages/mke.dist-info"),
        "sys_executable": str(python),
        "mke_executable": str(environment / "bin/mke"),
        "metadata_version": "0.1.1",
        "module_version": "0.1.1",
    }
    proof._validate_identity(payload, environment, repository)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("metadata_version", ""),
        ("module_version", "0.1.2"),
        ("sys_executable", "/usr/bin/python"),
        ("mke_executable", "/usr/local/bin/mke"),
    ],
)
def test_validate_identity_rejects_every_identity_mutation(
    tmp_path: Path, field: str, value: str
) -> None:
    proof = _load()
    environment = tmp_path / "venv"
    repository = tmp_path / "repository"
    identity = {
        "mke_file": str(environment / "lib/python/site-packages/mke/__init__.py"),
        "metadata_path": str(environment / "lib/python/site-packages/mke.dist-info"),
        "sys_executable": str(environment / "bin/python"),
        "mke_executable": str(environment / "bin/mke"),
        "metadata_version": "0.1.1",
        "module_version": "0.1.1",
    }
    identity[field] = value
    with pytest.raises(proof.ControllerError, match="installed_identity_failed"):
        proof._validate_identity(identity, environment, repository)


def test_validate_client_requires_exact_two_closed_receipts() -> None:
    proof = _load()
    payload = _success_payload(proof)
    assert proof._validate_client(payload) == payload
    exact_receipts = [dict(receipt) for receipt in proof._EXPECTED_RECEIPTS]
    for receipts in ([], exact_receipts[:1], exact_receipts * 2):
        mutated = dict(payload, receipts=receipts)
        with pytest.raises(proof.ControllerError, match="proof_failed"):
            proof._validate_client(mutated)
    mutated_receipt = dict(exact_receipts[0], source_key="incident_guide")
    with pytest.raises(proof.ControllerError, match="proof_failed"):
        proof._validate_client(dict(payload, receipts=[mutated_receipt, exact_receipts[1]]))


def _success_payload(proof: Any) -> dict[str, object]:
    return {
        "status": "passed",
        "manifest_schema": "mke.consumer_source_pack_manifest.v1",
        "evidence_schema": "mke.evidence_ref.v1",
        "pack_id": "local-knowledge-v1",
        "source_count": 2,
        "published_run_count": 2,
        "active_publication_count": 2,
        "active_evidence_count": 2,
        "observed_states": ["empty", "active"],
        "receipts": [dict(receipt) for receipt in proof._EXPECTED_RECEIPTS],
        "strict_schema_validation": True,
        "search_ask_projection_equal": True,
        "exact_manifest_mapping": True,
        "fresh_store_mapping": True,
        "redaction": True,
        "server_cleanup": True,
    }


def _candidate_repository(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "candidate-repository"
    repository.mkdir()
    (repository / "pyproject.toml").write_text(
        '[project]\nname = "multimodal-knowledge-engine"\n'
        'version = "0.1.1"\nrequires-python = ">=3.12,<3.14"\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "add", "pyproject.toml"], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=MKE Test",
            "-c",
            "user.email=mke-test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=repository,
        check=True,
    )
    wheel = repository.parent / "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"
    wheel.write_bytes(b"exact-wheel-bytes")
    return repository, wheel


def _candidate_success(wheel: Path) -> dict[str, object]:
    return {
        "status": "passed",
        "proof_input_wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
    }


def test_candidate_receipt_is_closed_canonical_and_bound_to_clean_source(
    tmp_path: Path,
) -> None:
    proof = _load()
    repository, wheel = _candidate_repository(tmp_path)

    receipt = proof.build_candidate_receipt(
        repository, wheel, "0.1.1", _candidate_success(wheel)
    )

    assert set(receipt) == {
        "schema_version",
        "repository",
        "source_commit",
        "package_name",
        "package_version",
        "wheel_filename",
        "wheel_bytes",
        "wheel_sha256",
        "requires_python",
        "consumer_proof_schema",
        "consumer_proof_status",
        "proof_input_wheel_sha256",
        "receipt_sha256",
    }
    assert receipt == {
        "schema_version": "mke.candidate_artifact_receipt.v1",
        "repository": "iTao-AI/multimodal-knowledge-engine",
        "source_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "package_name": "multimodal-knowledge-engine",
        "package_version": "0.1.1",
        "wheel_filename": wheel.name,
        "wheel_bytes": len(b"exact-wheel-bytes"),
        "wheel_sha256": hashlib.sha256(b"exact-wheel-bytes").hexdigest(),
        "requires_python": ">=3.12,<3.14",
        "consumer_proof_schema": "mke.consumer_source_pack_proof.v1",
        "consumer_proof_status": "passed",
        "proof_input_wheel_sha256": hashlib.sha256(b"exact-wheel-bytes").hexdigest(),
        "receipt_sha256": receipt["receipt_sha256"],
    }
    assert receipt["receipt_sha256"] == proof.canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    source_commit = receipt["source_commit"]
    assert isinstance(source_commit, str)
    assert len(source_commit) == 40
    assert re.fullmatch(r"[0-9a-f]{40}", source_commit)


def test_candidate_receipt_fails_closed_for_non_sha1_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proof = _load()
    repository, wheel = _candidate_repository(tmp_path)
    real_run = proof.subprocess.run

    def fake_run(command: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if list(command) == ["git", "rev-parse", "--show-object-format"]:
            return subprocess.CompletedProcess(command, 0, "sha256\n", "")
        return real_run(command, **kwargs)

    monkeypatch.setattr(proof.subprocess, "run", fake_run)

    with pytest.raises(proof.ControllerError) as exc_info:
        proof.build_candidate_receipt(
            repository, wheel, "0.1.1", _candidate_success(wheel)
        )

    assert exc_info.value.code == "candidate_artifact_invalid"


@pytest.mark.parametrize(
    "mutation",
    [
        "dirty_git",
        "missing_git",
        "wrong_package_version",
        "failed_proof",
        "zero_byte_wheel",
        "invalid_wheel_filename",
        "wheel_digest_mismatch",
    ],
)
def test_candidate_receipt_rejects_invalid_source_artifact_or_proof(
    tmp_path: Path, mutation: str
) -> None:
    proof = _load()
    repository, wheel = _candidate_repository(tmp_path)
    package_version = "0.1.1"
    proof_result = _candidate_success(wheel)
    if mutation == "dirty_git":
        (repository / "untracked.txt").write_text("dirty", encoding="utf-8")
    elif mutation == "missing_git":
        repository = tmp_path / "not-a-repository"
        repository.mkdir()
        (repository / "pyproject.toml").write_text(
            '[project]\nname = "multimodal-knowledge-engine"\n'
            'version = "0.1.1"\nrequires-python = ">=3.12,<3.14"\n',
            encoding="utf-8",
        )
    elif mutation == "wrong_package_version":
        package_version = "0.1.2"
    elif mutation == "failed_proof":
        proof_result["status"] = "failed"
    elif mutation == "zero_byte_wheel":
        wheel.write_bytes(b"")
        proof_result = _candidate_success(wheel)
    elif mutation == "invalid_wheel_filename":
        invalid = wheel.with_name("unsafe.whl")
        invalid.write_bytes(wheel.read_bytes())
        wheel = invalid
        proof_result = _candidate_success(wheel)
    elif mutation == "wheel_digest_mismatch":
        proof_result["proof_input_wheel_sha256"] = "0" * 64

    with pytest.raises(proof.ControllerError) as exc_info:
        proof.build_candidate_receipt(repository, wheel, package_version, proof_result)

    assert exc_info.value.code == "candidate_artifact_invalid"


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group contract")
def test_run_bounded_kills_descendant_when_parent_exits_during_cleanup(tmp_path: Path) -> None:
    proof = _load()
    parent_file = tmp_path / "parent.pid"
    child_file = tmp_path / "child.pid"
    program = (
        "import os,signal,subprocess,sys,time;"
        f"open({str(parent_file)!r},'w').write(str(os.getpid()));"
        "child=subprocess.Popen([sys.executable,'-c',"
        f"\"import os,signal,time;open({str(child_file)!r},'w').write(str(os.getpid()));"
        'signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)"]);'
        f'exec("while not os.path.exists({str(child_file)!r}):\\n time.sleep(.01)");'
        "signal.signal(signal.SIGTERM,lambda *_:sys.exit(0));"
        "sys.stdout.buffer.write(b'x'*20000);sys.stdout.flush();time.sleep(60)"
    )
    with pytest.raises(proof.ControllerError, match="command_output_exceeded"):
        proof.run_bounded(
            [sys.executable, "-c", program],
            cwd=tmp_path,
            env=os.environ,
            timeout_seconds=5,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
        )
    for pid_file in (parent_file, child_file):
        pid = int(pid_file.read_text())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if _process_is_terminated(pid):
                break
            time.sleep(0.02)
        else:
            os.kill(pid, signal.SIGKILL)
            pytest.fail(f"process {pid} survived cleanup")


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group contract")
def test_run_bounded_cleans_descendant_after_normal_parent_exit(tmp_path: Path) -> None:
    proof = _load()
    child_file = tmp_path / "normal-child.pid"
    child = (
        f"import os,signal,time;open({str(child_file)!r},'w').write(str(os.getpid()));"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)"
    )
    program = (
        "import os,subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{child!r}]);"
        f'exec("while not os.path.exists({str(child_file)!r}):\\n time.sleep(.01)");'
        "print('parent done')"
    )
    result = proof.run_bounded(
        [sys.executable, "-c", program],
        cwd=tmp_path,
        env=os.environ,
        timeout_seconds=5,
        max_stdout_bytes=1024,
        max_stderr_bytes=1024,
    )
    assert result.returncode == 0 and result.stdout == b"parent done\n"
    pid = int(child_file.read_text())
    assert _process_is_terminated(pid)


@pytest.mark.parametrize("wheel_count", [0, 2])
def test_run_proof_requires_exactly_one_wheel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, wheel_count: int
) -> None:
    proof = _load()

    def fake_command(
        code: str,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        config: object,
    ) -> Any:
        del code, cwd, env, config
        if command[:2] == ["uv", "build"]:
            output = Path(command[command.index("--out-dir") + 1])
            for index in range(wheel_count):
                (output / f"wheel-{index}.whl").write_bytes(b"wheel")
        return proof.CommandResult(0, b"", b"")

    monkeypatch.setattr(proof, "_command", fake_command)
    with pytest.raises(proof.ControllerError, match="wheel_build_failed"):
        proof.run_proof(proof.ProofConfig(tmp_path, (Path("/py312"), Path("/py313")), 3, 10, 10))


def test_run_proof_builds_once_and_uses_same_wheel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proof = _load()
    monkeypatch.setenv("PYTHONPATH", "host-source")
    monkeypatch.setenv("PYTHONHOME", "host-home")
    monkeypatch.setenv("VIRTUAL_ENV", "host-venv")
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "scripts").mkdir()
    (repository / "scripts/consumer_source_pack_client.py").write_text("# client")
    fixtures = repository / "tests/fixtures"
    (fixtures / "consumer-source-pack-v1").mkdir(parents=True)
    (fixtures / "local-knowledge-v1").mkdir()
    for name in ("manifest.json", "mcp-tool-schemas.json"):
        (fixtures / "consumer-source-pack-v1" / name).write_text("{}")
    for name in ("operations-guide.pdf", "incident-guide.pdf"):
        (fixtures / "local-knowledge-v1" / name).write_bytes(b"pdf")
    calls: list[tuple[list[str], Path, dict[str, str]]] = []
    copied_snapshots: list[dict[str, bytes]] = []

    success = _success_payload(proof)

    def fake(
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        **kwargs: object,
    ) -> Any:
        command = list(command)
        calls.append((command, cwd, dict(env)))
        if command[:2] == ["uv", "build"]:
            out = Path(command[command.index("--out-dir") + 1])
            (out / "mke.whl").write_bytes(b"wheel")
            return proof.CommandResult(0, b"", b"")
        if "-c" in command:
            identity = {
                "mke_file": str(
                    Path(command[0]).parents[1] / "lib/python/site-packages/mke/__init__.py"
                ),
                "metadata_path": str(
                    Path(command[0]).parents[1] / "lib/python/site-packages/mke.dist-info"
                ),
                "sys_executable": command[0],
                "mke_executable": str(Path(command[0]).with_name("mke")),
                "metadata_version": "0.1.1",
                "module_version": "0.1.1",
            }
            return proof.CommandResult(0, json.dumps(identity).encode(), b"")
        if command[0].endswith("python") and command[1].endswith("consumer_source_pack_client.py"):
            copied_snapshots.append(
                {
                    str(path.relative_to(cwd)): path.read_bytes()
                    for path in cwd.rglob("*")
                    if path.is_file()
                }
            )
            return proof.CommandResult(0, json.dumps(success).encode(), b"")
        return proof.CommandResult(0, b"", b"")

    monkeypatch.setattr(proof, "run_bounded", fake)
    result = proof.run_proof(
        proof.ProofConfig(repository, (Path("/py312"), Path("/py313")), 3, 10000, 10000)
    )
    assert result["status"] == "passed" and result["cleanup"] is True
    builds = [c for c, _, _ in calls if c[:2] == ["uv", "build"]]
    exports = [c for c, _, _ in calls if c[:2] == ["uv", "export"]]
    venvs = [c for c, _, _ in calls if c[:2] == ["uv", "venv"]]
    installs = [c for c, _, _ in calls if c[:3] == ["uv", "pip", "install"]]
    assert len(builds) == len(exports) == 1
    assert [c[c.index("--python") + 1] for c in venvs] == ["/py312", "/py313"]
    assert installs[0][-1] == installs[1][-1]
    assert (
        installs[0][installs[0].index("--constraint") + 1]
        == installs[1][installs[1].index("--constraint") + 1]
    )
    client_calls = [
        item
        for item in calls
        if item[0][0].endswith("python")
        and len(item[0]) > 1
        and item[0][1].endswith("consumer_source_pack_client.py")
    ]
    assert len(client_calls) == 2
    assert client_calls[0][1] != client_calls[1][1]
    for index, (command, cwd, env) in enumerate(client_calls):
        assert "--max-server-stderr-bytes" in command
        assert "--max-transport-bytes" not in command
        assert str(repository) not in "\0".join(command)
        assert str(repository) not in str(cwd)
        assert all(str(repository) not in value for value in env.values())
        assert not ({"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"} & env.keys())
        copied = copied_snapshots[index]
        assert copied["consumer_source_pack_client.py"] == b"# client"
        assert copied["manifest.json"] == b"{}"
        assert copied["mcp-tool-schemas.json"] == b"{}"
        assert copied["source-pack/operations-guide.pdf"] == b"pdf"
        assert copied["source-pack/incident-guide.pdf"] == b"pdf"
    assert all(not cwd.exists() for _, cwd, _ in client_calls)


@pytest.mark.parametrize(
    ("failure", "index", "expected"),
    [
        ("venv", 1, "environment_create_failed"),
        ("install", 0, "install_failed"),
        ("install", 1, "install_failed"),
        ("client", 0, "server_exit_nonzero"),
    ],
)
def test_run_proof_fails_closed_at_each_interpreter_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure: str,
    index: int,
    expected: str,
) -> None:
    proof = _load()
    repository = _repository_fixture(tmp_path)
    counts = {"venv": 0, "install": 0, "client": 0}
    roots: list[Path] = []

    def fake(command: Sequence[str], *, cwd: Path, **kwargs: object) -> Any:
        del kwargs
        command = list(command)
        if command[:2] == ["uv", "build"]:
            root = Path(command[command.index("--out-dir") + 1]).parent
            roots.append(root)
            (root / "build/mke.whl").write_bytes(b"wheel")
        kind = (
            "venv"
            if command[:2] == ["uv", "venv"]
            else "install"
            if command[:3] == ["uv", "pip", "install"]
            else "client"
            if len(command) > 1 and command[1].endswith("consumer_source_pack_client.py")
            else None
        )
        if kind is not None:
            current = counts[kind]
            counts[kind] += 1
            if failure == kind and index == current:
                return proof.CommandResult(9, b"", b"")
        if "-c" in command:
            environment = Path(command[0]).parents[1]
            identity = {
                "mke_file": str(environment / "lib/python/site-packages/mke/__init__.py"),
                "metadata_path": str(environment / "lib/python/site-packages/mke.dist-info"),
                "metadata_version": "0.1.1",
                "module_version": "0.1.1",
                "sys_executable": command[0],
                "mke_executable": str(Path(command[0]).with_name("mke")),
            }
            return proof.CommandResult(0, json.dumps(identity).encode(), b"")
        if kind == "client":
            return proof.CommandResult(0, json.dumps(_success_payload(proof)).encode(), b"")
        return proof.CommandResult(0, b"", b"")

    monkeypatch.setattr(proof, "run_bounded", fake)
    with pytest.raises(proof.ControllerError, match=expected) as exc_info:
        proof.run_proof(
            proof.ProofConfig(repository, (Path("/py312"), Path("/py313")), 3, 10_000, 10_000)
        )
    assert exc_info.value.code == expected
    assert roots and all(not root.exists() for root in roots)


@pytest.mark.parametrize("client_code", CLIENT_FAILURE_CODES)
def test_run_proof_propagates_exact_allowlisted_client_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, client_code: str
) -> None:
    proof = _load()
    repository = _repository_fixture(tmp_path)
    successful = _successful_runner(proof)

    def fake(command: Sequence[str], *, cwd: Path, **kwargs: object) -> Any:
        if len(command) > 1 and str(command[1]).endswith("consumer_source_pack_client.py"):
            payload = {"status": "failed", "code": client_code}
            return proof.CommandResult(1, json.dumps(payload, separators=(",", ":")).encode(), b"")
        return successful(command, cwd=cwd, **kwargs)

    monkeypatch.setattr(proof, "run_bounded", fake)

    with pytest.raises(proof.ControllerError) as exc_info:
        proof.run_proof(
            proof.ProofConfig(repository, (Path("/py312"), Path("/py313")), 3, 10_000, 10_000)
        )

    assert exc_info.value.code == client_code


@pytest.mark.parametrize(
    "stdout",
    [
        b"not-json",
        b'{"status":"failed","code":"consumer_schema_invalid"}trailing',
        b'{"status":"failed","code":"consumer_schema_invalid","detail":"unsafe"}',
        b'{"status":"failed"}',
        b'{"code":"consumer_schema_invalid"}',
        b'{"status":"passed","code":"consumer_schema_invalid"}',
        b'{"status":"failed","code":"unknown_code"}',
        b'{"status":"failed","code":"wheel_build_failed"}',
        b'{"status":"failed","code":"server_exit_nonzero"}',
    ],
)
def test_run_proof_maps_untrusted_nonzero_client_output_to_server_exit_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stdout: bytes
) -> None:
    proof = _load()
    repository = _repository_fixture(tmp_path)
    successful = _successful_runner(proof)

    def fake(command: Sequence[str], *, cwd: Path, **kwargs: object) -> Any:
        if len(command) > 1 and str(command[1]).endswith("consumer_source_pack_client.py"):
            return proof.CommandResult(1, stdout, b"")
        return successful(command, cwd=cwd, **kwargs)

    monkeypatch.setattr(proof, "run_bounded", fake)

    with pytest.raises(proof.ControllerError) as exc_info:
        proof.run_proof(
            proof.ProofConfig(repository, (Path("/py312"), Path("/py313")), 3, 10_000, 10_000)
        )

    assert exc_info.value.code == "server_exit_nonzero"


def _repository_fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    (repository / "scripts").mkdir(parents=True)
    (repository / "scripts/consumer_source_pack_client.py").write_text("# client")
    consumer = repository / "tests/fixtures/consumer-source-pack-v1"
    local = repository / "tests/fixtures/local-knowledge-v1"
    consumer.mkdir(parents=True)
    local.mkdir()
    for name in ("manifest.json", "mcp-tool-schemas.json"):
        (consumer / name).write_text("{}")
    for name in ("operations-guide.pdf", "incident-guide.pdf"):
        (local / name).write_bytes(b"pdf")
    return repository


def test_cleanup_failure_overrides_functional_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proof = _load()
    repository = _repository_fixture(tmp_path)
    monkeypatch.setattr(proof, "run_bounded", _successful_runner(proof))
    real_rmtree = proof.shutil.rmtree

    def remove_then_fail(path: Path) -> None:
        real_rmtree(path)
        raise OSError("simulated cleanup report")

    monkeypatch.setattr(proof.shutil, "rmtree", remove_then_fail)
    with pytest.raises(proof.ControllerError, match="cleanup_failed"):
        proof.run_proof(
            proof.ProofConfig(repository, (Path("/py312"), Path("/py313")), 3, 10_000, 10_000)
        )


def _successful_runner(proof: Any):
    def fake(command: Sequence[str], *, cwd: Path, **kwargs: object) -> Any:
        del kwargs
        command = list(command)
        if command[:2] == ["uv", "build"]:
            out = Path(command[command.index("--out-dir") + 1])
            (out / "mke.whl").write_bytes(b"wheel")
        if "-c" in command:
            environment = Path(command[0]).parents[1]
            identity = {
                "mke_file": str(environment / "lib/python/site-packages/mke/__init__.py"),
                "metadata_path": str(environment / "lib/python/site-packages/mke.dist-info"),
                "metadata_version": "0.1.1",
                "module_version": "0.1.1",
                "sys_executable": command[0],
                "mke_executable": str(Path(command[0]).with_name("mke")),
            }
            return proof.CommandResult(0, json.dumps(identity).encode(), b"")
        if len(command) > 1 and command[1].endswith("consumer_source_pack_client.py"):
            return proof.CommandResult(0, json.dumps(_success_payload(proof)).encode(), b"")
        return proof.CommandResult(0, b"", b"")

    return fake


def test_main_redacts_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    proof = _load()

    def fail(_config: object) -> dict[str, object]:
        raise proof.ControllerError("install_failed")

    monkeypatch.setattr(proof, "run_proof", fail)
    assert proof.main(["--python", sys.executable, "--python", sys.executable, "--json"]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "failed", "code": "install_failed"}


@pytest.mark.parametrize("code", STABLE_FAILURE_CODES)
def test_main_failure_matrix_is_exact_closed_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    code: str,
) -> None:
    proof = _load()

    def fail(_config: object) -> dict[str, object]:
        raise proof.ControllerError(code)

    monkeypatch.setattr(proof, "run_proof", fail)
    exit_code = proof.main(
        ["--python", sys.executable, "--python", sys.executable, "--json"]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload == {"status": "failed", "code": code}
    assert set(payload) == {"status", "code"}
    assert captured.err == ""
    forbidden = (
        "Traceback",
        "injected-secret",
        "/private/source/repository",
        "opaque_123456789",
        "operations-guide.pdf",
        "uv pip install",
        "PYTHONPATH",
        "server stderr",
        "Evidence private text",
        "exception detail",
    )
    assert not any(value in captured.out for value in forbidden)


def test_main_maps_unapproved_error_code_to_proof_failed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    proof = _load()

    def fail(_config: object) -> dict[str, object]:
        raise proof.ControllerError("injected-secret:/private/source/repository")

    monkeypatch.setattr(proof, "run_proof", fail)
    assert proof.main(["--python", sys.executable, "--python", sys.executable, "--json"]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "failed", "code": "proof_failed"}
