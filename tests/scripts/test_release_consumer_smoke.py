from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest


def _json(data: dict[str, object]) -> bytes:
    return json.dumps(data).encode()


def test_consumer_smoke_orchestrates_core_wheel_flow_outside_source_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import release_consumer_smoke as smoke

    repo = tmp_path / "repo"
    _write_public_fixtures(repo)
    wheel = repo / "dist" / "multimodal_knowledge_engine-0.1.3-py3-none-any.whl"
    wheel.parent.mkdir()
    wheel.write_bytes(b"wheel")
    runtime_root = tmp_path / "runtime"
    commands: list[tuple[str, ...]] = []
    command_cwds: list[Path | None] = []
    command_envs: list[dict[str, str] | None] = []
    limits: list[tuple[int, int]] = []
    monkeypatch.setenv("PYTHONPATH", str(repo / "src"))
    monkeypatch.setenv("PYTHONHOME", str(repo / "python-home"))
    monkeypatch.setenv("VIRTUAL_ENV", str(repo / ".venv"))

    monkeypatch.setattr(smoke, "repository_root", lambda: repo)
    monkeypatch.setattr(smoke.tempfile, "TemporaryDirectory", _tempdir(runtime_root))

    def fake_run(
        command: list[str],
        *,
        timeout_seconds: float,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        accepted_returncodes: frozenset[int] = frozenset({0}),
    ) -> smoke.CommandResult:
        commands.append(tuple(command))
        command_cwds.append(cwd)
        command_envs.append(env)
        limits.append((max_stdout_bytes, max_stderr_bytes))
        installed_python = runtime_root / "venv" / "bin" / "python"
        module = (
            runtime_root
            / "venv"
            / "lib"
            / "python3.12"
            / "site-packages"
            / "mke"
            / "__init__.py"
        )
        if command[:2] == ["uv", "venv"]:
            installed_python.parent.mkdir(parents=True, exist_ok=True)
            installed_python.write_text("")
        if command[:2] == ["uv", "pip"]:
            return smoke.CommandResult(0, b"", b"")
        if len(command) >= 3 and command[1] == "-c" and "mke.__file__" in command[2]:
            module.parent.mkdir(parents=True, exist_ok=True)
            module.write_text("")
            return smoke.CommandResult(
                0,
                _json(
                    {
                        "mke_file": str(module),
                        "mke_version": "0.1.3",
                        "metadata_version": "0.1.3",
                        "sys_executable": str(installed_python),
                    }
                ),
                b"",
            )
        if command[-2:] == ["proof", "run"]:
            return smoke.CommandResult(0, b"proof=product status=passed", b"")
        if command[-2:] == ["demo", "--verify"]:
            return smoke.CommandResult(0, b"result=passed", b"")
        if "ingest" in command:
            return smoke.CommandResult(
                0,
                _json(
                    {
                        "ok": True,
                        "run_id": "run_cli",
                        "run_state": "published",
                        "evidence_count": 2,
                    }
                ),
                b"",
            )
        if "search" in command:
            return smoke.CommandResult(
                0,
                b"page=2 text=Publication search returns only active page two.",
                b"",
            )
        if "ask" in command:
            return smoke.CommandResult(
                0,
                b"answer_status=evidence_found evidence_count=1 page=2",
                b"",
            )
        if len(command) >= 3 and command[1] == "-c" and "McpRuntimeConfig" in command[2]:
            return smoke.CommandResult(
                0,
                _json(
                    {
                        "status": "passed",
                        "run_state": "published",
                        "evidence_count": 2,
                        "search_keyword_matched": True,
                        "ask_status": "evidence_found",
                    }
                ),
                b"",
            )
        return smoke.CommandResult(0, b"", b"")

    monkeypatch.setattr(smoke, "run_command", fake_run)

    result = smoke.run_consumer_smoke(smoke.ConsumerSmokeConfig(wheel=wheel))

    assert result["status"] == "passed"
    assert result["version"] == "0.1.3"
    assert cast(dict[str, object], result["identity"]) == {
        "installed_site_packages": True,
        "venv_executable": True,
    }
    assert cast(dict[str, object], result["steps"]) == {
        "install": "passed",
        "identity": "passed",
        "proof": "passed",
        "demo": "passed",
        "cli": "passed",
        "mcp": "passed",
    }
    assert runtime_root.exists() is False
    assert any(command[:2] == ("uv", "venv") for command in commands)
    install_command = next(command for command in commands if command[:2] == ("uv", "pip"))
    rendered_install = " ".join(install_command)
    assert "[embedding]" not in rendered_install
    assert "[transcription]" not in rendered_install
    identity_command = next(
        command
        for command in commands
        if len(command) >= 3 and command[1] == "-c" and "mke.__file__" in command[2]
    )
    assert "mke.__version__" in identity_command[2]
    assert 'metadata.version("multimodal-knowledge-engine")' in identity_command[2]
    installed_indexes = [
        index
        for index, command in enumerate(commands)
        if command and command[0] != "uv"
    ]
    assert installed_indexes
    for index in installed_indexes:
        assert command_cwds[index] == runtime_root
        env = command_envs[index]
        assert env is not None
        assert "PYTHONPATH" not in env
        assert "PYTHONHOME" not in env
        assert "VIRTUAL_ENV" not in env
    assert all(stdout > 0 and stderr > 0 for stdout, stderr in limits)
    rendered_result = json.dumps(result)
    assert str(repo) not in rendered_result
    assert str(runtime_root) not in rendered_result


def test_source_checkout_import_identity_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import release_consumer_smoke as smoke

    repo, wheel, runtime_root = _repo_wheel_runtime(tmp_path)
    monkeypatch.setattr(smoke, "repository_root", lambda: repo)
    monkeypatch.setattr(smoke.tempfile, "TemporaryDirectory", _tempdir(runtime_root))

    def fake_run(command: list[str], **kwargs: object) -> smoke.CommandResult:
        installed_python = runtime_root / "venv" / "bin" / "python"
        if command[:2] == ["uv", "venv"]:
            installed_python.parent.mkdir(parents=True, exist_ok=True)
            installed_python.write_text("")
        if len(command) >= 3 and command[1] == "-c" and "mke.__file__" in command[2]:
            return smoke.CommandResult(
                0,
                _json(
                    {
                        "mke_file": str(repo / "src" / "mke" / "__init__.py"),
                        "mke_version": "0.1.3",
                        "metadata_version": "0.1.3",
                        "sys_executable": str(installed_python),
                    }
                ),
                b"",
            )
        return smoke.CommandResult(0, b"", b"")

    monkeypatch.setattr(smoke, "run_command", fake_run)

    with pytest.raises(smoke.ConsumerSmokeError) as raised:
        smoke.run_consumer_smoke(smoke.ConsumerSmokeConfig(wheel=wheel))

    assert raised.value.code == "installed_identity_failed"


@pytest.mark.parametrize(
    "identity_override",
    [
        {"mke_version": "0.1.0"},
        {"metadata_version": "0.1.0"},
    ],
    ids=["module-version-drift", "metadata-version-drift"],
)
def test_installed_version_identity_drift_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identity_override: dict[str, object],
) -> None:
    from scripts import release_consumer_smoke as smoke

    repo, wheel, runtime_root = _repo_wheel_runtime(tmp_path)
    monkeypatch.setattr(smoke, "repository_root", lambda: repo)
    monkeypatch.setattr(smoke.tempfile, "TemporaryDirectory", _tempdir(runtime_root))

    def fake_run(command: list[str], **kwargs: object) -> smoke.CommandResult:
        installed_python = runtime_root / "venv" / "bin" / "python"
        module = (
            runtime_root
            / "venv"
            / "lib"
            / "python3.12"
            / "site-packages"
            / "mke"
            / "__init__.py"
        )
        if command[:2] == ["uv", "venv"]:
            installed_python.parent.mkdir(parents=True, exist_ok=True)
            installed_python.write_text("")
        if len(command) >= 3 and command[1] == "-c" and "mke.__file__" in command[2]:
            module.parent.mkdir(parents=True, exist_ok=True)
            module.write_text("")
            identity: dict[str, object] = {
                "mke_file": str(module),
                "mke_version": "0.1.3",
                "metadata_version": "0.1.3",
                "sys_executable": str(installed_python),
            }
            identity.update(identity_override)
            return smoke.CommandResult(0, _json(identity), b"")
        return smoke.CommandResult(0, b"", b"")

    monkeypatch.setattr(smoke, "run_command", fake_run)

    with pytest.raises(smoke.ConsumerSmokeError) as raised:
        smoke.run_consumer_smoke(smoke.ConsumerSmokeConfig(wheel=wheel))

    assert raised.value.code == "installed_identity_failed"


@pytest.mark.parametrize(
    ("command_marker", "expected_code"),
    [
        ("proof", "proof_failed"),
        ("demo", "demo_failed"),
        ("search", "cli_search_failed"),
        ("McpRuntimeConfig", "mcp_contract_failed"),
    ],
)
def test_substep_failure_returns_stable_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command_marker: str,
    expected_code: str,
) -> None:
    from scripts import release_consumer_smoke as smoke

    repo, wheel, runtime_root = _repo_wheel_runtime(tmp_path)
    monkeypatch.setattr(smoke, "repository_root", lambda: repo)
    monkeypatch.setattr(smoke.tempfile, "TemporaryDirectory", _tempdir(runtime_root))
    monkeypatch.setattr(
        smoke,
        "run_command",
        _fake_run_with_failure(smoke, runtime_root, command_marker),
    )

    assert smoke.main(["--wheel", str(wheel), "--json"]) == 1
    rendered = capsys.readouterr().out
    payload = json.loads(rendered)

    assert payload == {"status": "failed", "code": expected_code}
    assert str(repo) not in rendered
    assert str(runtime_root) not in rendered
    assert "Traceback" not in rendered
    assert "secret" not in rendered


def test_missing_or_invalid_wheel_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts import release_consumer_smoke as smoke

    missing = tmp_path / "missing.whl"
    assert smoke.main(["--wheel", str(missing), "--json"]) == 1
    missing_payload = json.loads(capsys.readouterr().out)
    assert missing_payload == {"status": "failed", "code": "wheel_unavailable"}

    invalid = tmp_path / "not-a-wheel.txt"
    invalid.write_text("not a wheel")
    assert smoke.main(["--wheel", str(invalid), "--json"]) == 1
    invalid_payload = json.loads(capsys.readouterr().out)
    assert invalid_payload == {"status": "failed", "code": "wheel_invalid"}

    combined = json.dumps([missing_payload, invalid_payload])
    assert str(tmp_path) not in combined
    assert "Traceback" not in combined


def test_unexpected_errors_are_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts import release_consumer_smoke as smoke

    repo, wheel, runtime_root = _repo_wheel_runtime(tmp_path)
    monkeypatch.setattr(smoke, "repository_root", lambda: repo)
    monkeypatch.setattr(smoke.tempfile, "TemporaryDirectory", _tempdir(runtime_root))

    def fake_run(command: list[str], **kwargs: object) -> smoke.CommandResult:
        raise RuntimeError(f"Traceback private path {repo} secret=value")

    monkeypatch.setattr(smoke, "run_command", fake_run)

    assert smoke.main(["--wheel", str(wheel), "--json"]) == 1
    rendered = capsys.readouterr().out
    payload = json.loads(rendered)

    assert payload == {"status": "failed", "code": "consumer_smoke_failed"}
    assert str(repo) not in rendered
    assert "Traceback" not in rendered
    assert "secret" not in rendered


def _repo_wheel_runtime(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    _write_public_fixtures(repo)
    wheel = repo / "dist" / "multimodal_knowledge_engine-0.1.3-py3-none-any.whl"
    wheel.parent.mkdir(parents=True)
    wheel.write_bytes(b"wheel")
    return repo, wheel, tmp_path / "runtime"


def _write_public_fixtures(repo: Path) -> None:
    for relative in (
        "tests/fixtures/pdf/text-layer.pdf",
        "tests/fixtures/pdf/text-layer-revised.pdf",
        "tests/fixtures/video/short-audio.mp4",
        "tests/fixtures/video/short-audio.mp4.mke-transcript.json",
    ):
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")


def _tempdir(path: Path) -> object:
    class TempContext:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> str:
            path.mkdir(parents=True)
            return str(path)

        def __exit__(self, *args: object) -> None:
            for child in sorted(path.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            path.rmdir()

    return TempContext


def _fake_run_with_failure(
    smoke: Any,
    runtime_root: Path,
    marker: str,
) -> object:
    module = (
        runtime_root
        / "venv"
        / "lib"
        / "python3.12"
        / "site-packages"
        / "mke"
        / "__init__.py"
    )
    installed_python = runtime_root / "venv" / "bin" / "python"

    def fake_run(command: list[str], **kwargs: object) -> object:
        if command[:2] == ["uv", "venv"]:
            installed_python.parent.mkdir(parents=True, exist_ok=True)
            installed_python.write_text("")
        if marker in " ".join(command):
            raise smoke.ConsumerSmokeError("private detail", "secret=value")
        if len(command) >= 3 and command[1] == "-c" and "mke.__file__" in command[2]:
            module.parent.mkdir(parents=True, exist_ok=True)
            module.write_text("")
            return smoke.CommandResult(
                0,
                _json(
                    {
                        "mke_file": str(module),
                        "mke_version": "0.1.3",
                        "metadata_version": "0.1.3",
                        "sys_executable": str(installed_python),
                    }
                ),
                b"",
            )
        if command[-2:] == ["proof", "run"]:
            return smoke.CommandResult(0, b"proof=product status=passed", b"")
        if command[-2:] == ["demo", "--verify"]:
            return smoke.CommandResult(0, b"result=passed", b"")
        if "ingest" in command:
            return smoke.CommandResult(
                0,
                _json(
                    {
                        "ok": True,
                        "run_id": "run_cli",
                        "run_state": "published",
                        "evidence_count": 2,
                    }
                ),
                b"",
            )
        if "search" in command:
            return smoke.CommandResult(0, b"page=2", b"")
        if "ask" in command:
            return smoke.CommandResult(0, b"answer_status=evidence_found", b"")
        if len(command) >= 3 and command[1] == "-c" and "McpRuntimeConfig" in command[2]:
            return smoke.CommandResult(
                0,
                _json({"status": "passed", "ask_status": "evidence_found"}),
                b"",
            )
        return smoke.CommandResult(0, b"", b"")

    return fake_run
