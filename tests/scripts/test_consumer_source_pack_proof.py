from __future__ import annotations

import importlib.util
import json
import os
import signal
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/consumer_source_pack_proof.py"


def _load():
    spec = importlib.util.spec_from_file_location("consumer_source_pack_proof", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
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
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


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
