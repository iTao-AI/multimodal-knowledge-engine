from __future__ import annotations

import importlib.util
import json
import os
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
    }
    proof._validate_identity(base, environment, repository)
    contaminated = dict(base, mke_file=str(repository / "src/mke/__init__.py"))
    with pytest.raises(proof.ControllerError, match="installed_identity_failed"):
        proof._validate_identity(contaminated, environment, repository)
    wrong_metadata = dict(base, metadata_path=str(environment / "lib/python/site-packages/mke"))
    with pytest.raises(proof.ControllerError, match="installed_identity_failed"):
        proof._validate_identity(wrong_metadata, environment, repository)


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

    success = {
        "status": "passed",
        "manifest_schema": "mke.consumer_source_pack_manifest.v1",
        "evidence_schema": "mke.evidence_ref.v1",
        "pack_id": "local-knowledge-v1",
        "source_count": 2,
        "published_run_count": 2,
        "active_publication_count": 2,
        "active_evidence_count": 2,
        "observed_states": ["empty", "active"],
        "receipts": [],
        "strict_schema_validation": True,
        "search_ask_projection_equal": True,
        "exact_manifest_mapping": True,
        "fresh_store_mapping": True,
        "redaction": True,
        "server_cleanup": True,
    }

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
            }
            return proof.CommandResult(0, json.dumps(identity).encode(), b"")
        if command[0].endswith("python") and command[1].endswith("consumer_source_pack_client.py"):
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
    client_calls = [
        item
        for item in calls
        if item[0][0].endswith("python")
        and len(item[0]) > 1
        and item[0][1].endswith("consumer_source_pack_client.py")
    ]
    assert len(client_calls) == 2
    for command, cwd, env in client_calls:
        assert str(repository) not in "\0".join(command)
        assert str(repository) not in str(cwd)
        assert all(str(repository) not in value for value in env.values())


def test_main_redacts_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    proof = _load()

    def fail(_config: object) -> dict[str, object]:
        raise proof.ControllerError("install_failed")

    monkeypatch.setattr(proof, "run_proof", fail)
    assert proof.main(["--python", sys.executable, "--python", sys.executable, "--json"]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "failed", "code": "install_failed"}
