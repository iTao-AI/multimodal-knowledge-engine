from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path("scripts/pdf_extraction_observation_wheel_proof.py").resolve()


def proof() -> ModuleType:
    return importlib.import_module("scripts.pdf_extraction_observation_wheel_proof")


def source_and_wheel(tmp_path: Path) -> tuple[Path, str, Path]:
    repository = tmp_path / "repository"
    (repository / "src/mke").mkdir(parents=True)
    (repository / "src/mke/__init__.py").write_bytes(b'"""Declared package."""\n')
    (repository / "pyproject.toml").write_text(
        '[project]\nname="multimodal-knowledge-engine"\nversion="0.1.7"\n'
        'requires-python=">=3.12,<3.14"\n'
        '[project.scripts]\nmke="mke:console_main"\n',
        encoding="utf-8",
    )
    (repository / "uv.lock").write_text("version=1\n", encoding="utf-8")
    for argv in (
        ["git", "init", "--quiet", "--initial-branch=main"],
        ["git", "add", "src/mke/__init__.py", "pyproject.toml", "uv.lock"],
        [
            "git",
            "-c",
            "user.name=Proof Test",
            "-c",
            "user.email=proof@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "declared source",
        ],
    ):
        subprocess.run(argv, cwd=repository, check=True, capture_output=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository).decode().strip()
    wheel = tmp_path / "multimodal_knowledge_engine-0.1.7-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("mke/__init__.py", b'"""Declared package."""\n')
        archive.writestr(
            "multimodal_knowledge_engine-0.1.7.dist-info/METADATA",
            "Metadata-Version: 2.3\nName: multimodal-knowledge-engine\nVersion: 0.1.7\n"
            "Requires-Python: >=3.12,<3.14\n\n",
        )
        archive.writestr(
            "multimodal_knowledge_engine-0.1.7.dist-info/entry_points.txt",
            "[console_scripts]\nmke = mke:console_main\n",
        )
    return repository, commit, wheel


def test_wheel_provenance_uses_committed_bytes_not_the_dirty_checkout(tmp_path: Path) -> None:
    repository, commit, wheel = source_and_wheel(tmp_path)
    (repository / "src/mke/__init__.py").write_text("dirty checkout\n", encoding="utf-8")
    binding = proof().verify_wheel(repository, commit, wheel)
    assert binding["wheel_sha256"] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert binding["version"] == "0.1.7"
    assert binding["module_sha256"] == {
        "mke/__init__.py": hashlib.sha256(b'"""Declared package."""\n').hexdigest()
    }


@pytest.mark.parametrize("mutation", ["missing", "extra", "changed"])
def test_equal_version_wheel_with_wrong_package_bytes_is_rejected(
    tmp_path: Path, mutation: str
) -> None:
    repository, commit, wheel = source_and_wheel(tmp_path)
    with zipfile.ZipFile(wheel) as original:
        entries = {name: original.read(name) for name in original.namelist()}
    if mutation == "missing":
        del entries["mke/__init__.py"]
    elif mutation == "extra":
        entries["mke/overlay.py"] = b"unreviewed = True\n"
    else:
        entries["mke/__init__.py"] = b"different code, same version\n"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    module = proof()
    with pytest.raises(module.ProofFailure, match="wheel_source_mismatch"):
        module.verify_wheel(repository, commit, wheel)


def test_changed_lock_cannot_supply_dependency_constraints_for_an_older_wheel(
    tmp_path: Path,
) -> None:
    repository, commit, _ = source_and_wheel(tmp_path)
    (repository / "uv.lock").write_text("version=2\n", encoding="utf-8")
    module = proof()
    with pytest.raises(module.ProofFailure, match="locked_inputs_changed"):
        module.verify_locked_inputs(repository, commit)


@pytest.mark.parametrize(
    "extra",
    [
        "unreviewed.py",
        "unreviewed_startup.pth",
        "multimodal_knowledge_engine-0.1.7.data/purelib/unreviewed.py",
        "multimodal_knowledge_engine-0.1.7.data/scripts/mke",
        "multimodal_knowledge_engine-0.1.7.dist-info/unreviewed.py",
    ],
)
def test_wheel_rejects_unbound_members_outside_the_package(tmp_path: Path, extra: str) -> None:
    repository, commit, wheel = source_and_wheel(tmp_path)
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr(extra, "import unreviewed\n")
    module = proof()
    with pytest.raises(module.ProofFailure, match="wheel_source_mismatch"):
        module.verify_wheel(repository, commit, wheel)


@pytest.mark.parametrize(
    "entry_points",
    [
        None,
        "[console_scripts]\nmke = unreviewed:main\n",
        "[console_scripts]\nmke = mke:console_main\nextra = unreviewed:main\n",
        "[console_scripts]\nmke = mke:console_main\n[gui_scripts]\nextra = unreviewed:main\n",
        "[console_scripts]\nMKE = mke:console_main\n",
        "[console_scripts]\nmke = mke:console_main\nmke = unreviewed:main\n",
        "[DEFAULT]\nmke = mke:console_main\n[console_scripts]\n",
    ],
)
def test_wheel_entry_points_must_match_the_committed_project(
    tmp_path: Path, entry_points: str | None
) -> None:
    repository, commit, wheel = source_and_wheel(tmp_path)
    entry_name = "multimodal_knowledge_engine-0.1.7.dist-info/entry_points.txt"
    with zipfile.ZipFile(wheel) as original:
        entries = {name: original.read(name) for name in original.namelist() if name != entry_name}
    if entry_points is not None:
        entries[entry_name] = entry_points.encode()
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    module = proof()
    with pytest.raises(module.ProofFailure, match="wheel_source_mismatch"):
        module.verify_wheel(repository, commit, wheel)


@pytest.mark.parametrize(("bounds", "accepted"), [("<3.14,>=3.12", True), ("<3.14,>=3.11", False)])
def test_wheel_metadata_accepts_equivalent_bounds_but_rejects_a_changed_floor(
    tmp_path: Path, bounds: str, accepted: bool
) -> None:
    repository, commit, wheel = source_and_wheel(tmp_path)
    with zipfile.ZipFile(wheel) as original:
        entries = {name: original.read(name) for name in original.namelist()}
    metadata = "multimodal_knowledge_engine-0.1.7.dist-info/METADATA"
    entries[metadata] = entries[metadata].replace(b">=3.12,<3.14", bounds.encode())
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    module = proof()
    if accepted:
        assert module.verify_wheel(repository, commit, wheel)["version"] == "0.1.7"
    else:
        with pytest.raises(module.ProofFailure, match="wheel_source_mismatch"):
            module.verify_wheel(repository, commit, wheel)


def test_child_command_clears_host_python_import_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        monkeypatch.setenv(key, "/private/hostile/source")
    result = proof().command(
        [
            sys.executable,
            "-I",
            "-c",
            "import os,json;print(json.dumps({k:v for k,v in os.environ.items() "
            "if k in {'PYTHONPATH','PYTHONHOME','VIRTUAL_ENV',"
            "'UV_OFFLINE','UV_PYTHON_DOWNLOADS'}}))",
        ],
        cwd=tmp_path,
    )
    actual = json.loads(result.stdout)
    assert {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}.isdisjoint(actual)
    assert actual["UV_OFFLINE"] == "1" and actual["UV_PYTHON_DOWNLOADS"] == "never"


@pytest.mark.parametrize("mutation", [None, "source", "executable", "python", "bytes"])
def test_installed_identity_requires_selected_environment_and_wheel_bytes(
    tmp_path: Path, mutation: str | None
) -> None:
    module = proof()
    environment = tmp_path / "environment"
    repository = tmp_path / "repository"
    package = environment / "lib/python3.12/site-packages/mke/__init__.py"
    digest = hashlib.sha256(b"declared").hexdigest()
    payload = {
        "module": str(package),
        "executable": str(environment / "bin/python"),
        "prefix": str(environment),
        "python_version": "3.12.13",
        "module_sha256": {"mke/__init__.py": digest},
    }
    if mutation == "source":
        payload["module"] = str(repository / "src/mke/__init__.py")
    elif mutation == "executable":
        payload["executable"] = str(tmp_path / "host/python")
    elif mutation == "python":
        payload["python_version"] = "3.13.13"
    elif mutation == "bytes":
        payload["module_sha256"] = {"mke/__init__.py": "0" * 64}
    if mutation is None:
        module.validate_installed_identity(
            payload, environment, repository, "3.12", {"mke/__init__.py": digest}
        )
    else:
        with pytest.raises(module.ProofFailure, match="installed_identity_failed"):
            module.validate_installed_identity(
                payload, environment, repository, "3.12", {"mke/__init__.py": digest}
            )


@pytest.mark.parametrize("mcp_version", ["1.29.1", "1.29.2"])
def test_installed_dependency_versions_are_checked_after_required_packages(
    mcp_version: str,
) -> None:
    module = proof()
    actual = {
        "mcp": mcp_version,
        "pydantic": "2.13.5",
        "pymupdf": "1.27.2.3",
        "multimodal-knowledge-engine": "0.1.7",
    }
    locked = {"mcp": {"1.29.1"}, "pydantic": {"2.13.5"}, "pymupdf": {"1.27.2.3"}}
    if mcp_version == "1.29.1":
        module.validate_dependencies(actual, locked, "0.1.7")
    else:
        with pytest.raises(module.ProofFailure, match="installed_dependencies_failed"):
            module.validate_dependencies(actual, locked, "0.1.7")


def test_identity_probe_accepts_uv_local_archive_without_optional_hashes(tmp_path: Path) -> None:
    site = tmp_path / "site-packages"
    package = site / "mke"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    metadata = site / "multimodal_knowledge_engine-0.1.7.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        "Name: multimodal-knowledge-engine\nVersion: 0.1.7\n", encoding="utf-8"
    )
    origin: dict[str, object] = {"url": (tmp_path / "declared.whl").as_uri(), "archive_info": {}}
    (metadata / "direct_url.json").write_text(json.dumps(origin), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            f"import sys;sys.path.insert(0,{str(site)!r});" + proof()._IDENTITY_PROBE,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["direct_url"] == origin


@pytest.mark.parametrize(
    ("archive", "expected"),
    [
        ({}, None),
        ({"hashes": {"sha256": "a" * 64}}, "a" * 64),
        ({"hash": "sha256=" + "a" * 64}, "a" * 64),
    ],
)
def test_install_origin_requires_the_selected_wheel_with_optional_hashes(
    tmp_path: Path, archive: dict[str, object], expected: str | None
) -> None:
    wheel = tmp_path / "declared.whl"
    payload = {"direct_url": {"url": wheel.as_uri(), "archive_info": archive}}
    assert proof().validate_install_origin(payload, wheel, "a" * 64) == expected


@pytest.mark.parametrize("mutation", ["url", "hash", "legacy_hash", "editable"])
def test_wrong_install_origin_or_recorded_digest_is_rejected(tmp_path: Path, mutation: str) -> None:
    wheel = tmp_path / "declared.whl"
    origin: dict[str, object] = {"url": wheel.as_uri(), "archive_info": {}}
    if mutation == "url":
        origin["url"] = (tmp_path / "different.whl").as_uri()
    elif mutation == "hash":
        origin["archive_info"] = {"hashes": {"sha256": "b" * 64}}
    elif mutation == "legacy_hash":
        origin["archive_info"] = {"hashes": {"sha256": "a" * 64}, "hash": "sha256=" + "b" * 64}
    else:
        origin["dir_info"] = {"editable": True}
    module = proof()
    with pytest.raises(module.ProofFailure, match="installed_origin_invalid"):
        module.validate_install_origin({"direct_url": origin}, wheel, "a" * 64)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX child-group cleanup contract")
def test_command_timeout_terminates_its_descendant_process(tmp_path: Path) -> None:
    marker = tmp_path / "unexpected-child-output"
    child = f"import time;from pathlib import Path;time.sleep(0.5);Path({str(marker)!r}).touch()"
    parent = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{child!r}]);"
        "time.sleep(5)"
    )
    module = proof()
    with pytest.raises(module.ProofFailure, match="command_failed"):
        module.command([sys.executable, "-I", "-c", parent], cwd=tmp_path, timeout=0.15)
    time.sleep(0.8)
    assert not marker.exists(), "the timed-out command left its own descendant running"


def test_reused_work_directory_has_bounded_failure_without_overwrite(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    root.mkdir()
    sentinel = root / "evidence.json"
    sentinel.write_bytes(b"preserve existing evidence")
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(SCRIPT),
            "--wheel",
            str(tmp_path / "missing.whl"),
            "--source-commit",
            "a" * 40,
            "--python",
            sys.executable,
            "--python",
            sys.executable,
            "--work-dir",
            str(root),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout.strip() == '{"code":"work_directory_exists","status":"failed"}'
    assert str(tmp_path) not in result.stdout and "Traceback" not in result.stderr
    assert sentinel.read_bytes() == b"preserve existing evidence"


def test_invalid_source_commit_exits_before_creating_work_directory(tmp_path: Path) -> None:
    root = tmp_path / "new"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(SCRIPT),
            "--wheel",
            "missing.whl",
            "--source-commit",
            "main",
            "--python",
            sys.executable,
            "--python",
            sys.executable,
            "--work-dir",
            str(root),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"code": "source_commit_invalid", "status": "failed"}
    assert not root.exists() and "Traceback" not in result.stderr
