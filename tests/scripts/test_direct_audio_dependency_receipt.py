# Dynamic monkeypatch targets come from the stdlib-only script module loaded at runtime.
# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
import subprocess
import sys
import sysconfig
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest


def _module() -> Any:
    from scripts import direct_audio_dependency_receipt

    return direct_audio_dependency_receipt


def _wheel(root: Path, name: str, payload: bytes | None = None) -> Path:
    path = root / name
    path.write_bytes(payload or name.encode("ascii"))
    return path


def _cells():
    receipt = _module()
    return (
        receipt.Cell("python3.12", "3.12", "cp312", "macosx_11_0_arm64"),
        receipt.Cell("python3.13", "3.13", "cp313", "macosx_11_0_arm64"),
    )


def _requirements():
    receipt = _module()
    return (
        receipt.Requirement("native-demo", "1.0"),
        receipt.Requirement("shared-demo", "2.0"),
    )


def _write_single_package_lock(
    tmp_path: Path, *, name: str, version: str, sha256: str
) -> tuple[Path, Path]:
    lock = tmp_path / "uv.lock"
    filename = name.replace("-", "_") + f"-{version}-py3-none-any.whl"
    lock.write_text(
        "version = 1\n"
        'requires-python = ">=3.12, <3.14"\n'
        "[[package]]\n"
        f'name = "{name}"\n'
        f'version = "{version}"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        f'wheels = [{{ url = "https://example.invalid/{filename}", '
        f'hash = "sha256:{sha256}", size = 1 }}]\n'
        "[[package]]\n"
        'name = "multimodal-knowledge-engine"\n'
        'version = "0.1.3"\n'
        'source = { editable = "." }\n'
        "[package.optional-dependencies]\n"
        f'transcription = [{{ name = "{name}" }}]\n',
        encoding="utf-8",
    )
    constraints = tmp_path / "constraints.txt"
    projection = _module().derive_transcription_projection(lock, _cells())
    constraints.write_bytes(projection.constraints)
    return lock, constraints


def test_manifest_keeps_disjoint_wheels_and_reuses_one_universal_entry(
    tmp_path: Path,
) -> None:
    receipt = _module()
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _wheel(wheelhouse, "native_demo-1.0-cp312-cp312-macosx_11_0_arm64.whl")
    _wheel(wheelhouse, "native_demo-1.0-cp313-cp313-macosx_11_0_arm64.whl")
    _wheel(wheelhouse, "shared_demo-2.0-py3-none-any.whl")

    manifest = receipt.build_wheelhouse_manifest(wheelhouse)
    resolution = receipt.resolve_wheels(manifest, _requirements(), _cells())

    assert [entry.filename for entry in manifest] == sorted(entry.filename for entry in manifest)
    assert len(manifest) == 3
    assert resolution["3.12"]["shared-demo"].filename == "shared_demo-2.0-py3-none-any.whl"
    assert resolution["3.13"]["shared-demo"] is resolution["3.12"]["shared-demo"]


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("missing", "wheel_missing"),
        ("ambiguous", "wheel_ambiguous"),
        ("wrong_version", "wheel_missing"),
        ("wrong_tag", "wheel_missing"),
        ("surplus", "wheel_surplus"),
    ],
)
def test_resolution_fails_closed_for_candidate_drift(
    tmp_path: Path, mutation: str, code: str
) -> None:
    receipt = _module()
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    if mutation != "missing":
        version = "9.0" if mutation == "wrong_version" else "1.0"
        tag = "cp311-cp311-macosx_11_0_arm64" if mutation == "wrong_tag" else "py3-none-any"
        _wheel(wheelhouse, f"native_demo-{version}-{tag}.whl")
    if mutation == "ambiguous":
        _wheel(wheelhouse, "native_demo-1.0-cp311-abi3-macosx_11_0_arm64.whl")
    if mutation == "surplus":
        _wheel(wheelhouse, "unused_demo-1.0-py3-none-any.whl")

    manifest = receipt.build_wheelhouse_manifest(wheelhouse)
    with pytest.raises(receipt.ReceiptError, match=code):
        receipt.resolve_wheels(
            manifest,
            (receipt.Requirement("native-demo", "1.0"),),
            _cells(),
        )


@pytest.mark.parametrize(
    "name",
    [
        "not-a-wheel.txt",
        "Bad.Name-1.0-py3-none-any.whl",
        "demo-1.0-py3-any.whl",
        "demo-1.0--py3-none-any.whl",
    ],
)
def test_manifest_rejects_unrelated_or_invalid_canonical_filename(
    tmp_path: Path, name: str
) -> None:
    receipt = _module()
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _wheel(wheelhouse, name)

    with pytest.raises(receipt.ReceiptError, match="wheel_input_invalid"):
        receipt.build_wheelhouse_manifest(wheelhouse)


def test_manifest_rejects_duplicate_symlink_nested_and_non_regular_inputs(
    tmp_path: Path,
) -> None:
    receipt = _module()
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = _wheel(wheelhouse, "demo-1.0-py3-none-any.whl")

    with pytest.raises(receipt.ReceiptError, match="wheel_duplicate"):
        receipt.build_manifest_from_paths((wheel, wheel))

    link_root = tmp_path / "links"
    link_root.mkdir()
    (link_root / wheel.name).symlink_to(wheel)
    with pytest.raises(receipt.ReceiptError, match="wheel_input_invalid"):
        receipt.build_wheelhouse_manifest(link_root)

    nested_root = tmp_path / "nested"
    nested_root.mkdir()
    (nested_root / "child").mkdir()
    with pytest.raises(receipt.ReceiptError, match="wheel_input_invalid"):
        receipt.build_wheelhouse_manifest(nested_root)

    fifo_root = tmp_path / "fifo"
    fifo_root.mkdir()
    os.mkfifo(fifo_root / "demo-1.0-py3-none-any.whl")
    with pytest.raises(receipt.ReceiptError, match="wheel_input_invalid"):
        receipt.build_wheelhouse_manifest(fifo_root)


def test_manifest_detects_before_after_identity_and_tag_drift(tmp_path: Path) -> None:
    receipt = _module()
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = _wheel(wheelhouse, "demo-1.0-py3-none-any.whl", b"before")
    manifest = receipt.build_wheelhouse_manifest(wheelhouse)
    wheel.write_bytes(b"after")

    with pytest.raises(receipt.ReceiptError, match="wheel_identity_drift"):
        receipt.validate_manifest_identity(wheelhouse, manifest)

    wheel.unlink()
    _wheel(wheelhouse, "demo-1.0-cp312-cp312-macosx_11_0_arm64.whl", b"before")
    with pytest.raises(receipt.ReceiptError, match="wheel_identity_drift"):
        receipt.validate_manifest_identity(wheelhouse, manifest)


def test_regular_file_read_rechecks_path_identity_after_descriptor_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    target = tmp_path / "bound.txt"
    target.write_bytes(b"bound")
    original_lstat = Path.lstat
    target_calls = 0

    def drifting_lstat(path: Path):
        nonlocal target_calls
        observed = original_lstat(path)
        if path == target:
            target_calls += 1
            if target_calls == 2:
                values = list(observed)
                values[1] += 1
                return os.stat_result(values)
        return observed

    monkeypatch.setattr(Path, "lstat", drifting_lstat)

    with pytest.raises(receipt.ReceiptError, match="input_identity_drift"):
        receipt._read_regular(target)  # pyright: ignore[reportPrivateUsage]


def test_lock_projection_excludes_project_and_freezes_hashed_external_roots(
    tmp_path: Path,
) -> None:
    receipt = _module()
    lock = tmp_path / "uv.lock"
    digest_a = "a" * 64
    digest_b = "b" * 64
    lock_text = """
version = 1
requires-python = ">=3.12, <3.14"
[[package]]
name = "av"
version = "17.1.0"
source = { registry = "https://pypi.org/simple" }
wheels = [WHEEL_A]
[[package]]
name = "faster-whisper"
version = "1.2.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [{ name = "av" }]
wheels = [WHEEL_B]
[[package]]
name = "multimodal-knowledge-engine"
version = "0.1.3"
source = { editable = "." }
[package.optional-dependencies]
transcription = [{ name = "faster-whisper" }, { name = "av" }]
""".strip()
    wheel_a = (
        '{ url = "https://example.invalid/av-17.1.0-py3-none-any.whl", '
        f'hash = "sha256:{digest_a}", size = 1 }}'
    )
    wheel_b = (
        '{ url = "https://example.invalid/faster_whisper-1.2.1-py3-none-any.whl", '
        f'hash = "sha256:{digest_b}", size = 1 }}'
    )
    lock.write_text(
        lock_text.replace("WHEEL_A", wheel_a).replace("WHEEL_B", wheel_b) + "\n",
        encoding="utf-8",
    )

    projection = receipt.derive_transcription_projection(lock, _cells())

    assert [(item.name, item.version) for item in projection.requirements] == [
        ("av", "17.1.0"),
        ("faster-whisper", "1.2.1"),
    ]
    rendered = projection.constraints.decode("ascii")
    assert "multimodal" not in rendered
    assert "--hash=sha256:" in rendered
    assert projection.root_requirements.decode("ascii").splitlines() == [
        "av==17.1.0 --hash=sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "faster-whisper==1.2.1 --hash=sha256:"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    ]


def test_lock_projection_and_resolution_are_exact_per_python_cell(tmp_path: Path) -> None:
    receipt = _module()
    lock = tmp_path / "uv.lock"
    digest = "a" * 64
    wheel = (
        '{ url = "https://example.invalid/demo-1.0-py3-none-any.whl", '
        f'hash = "sha256:{digest}", size = 1 }}'
    )
    lock.write_text(
        """
version = 1
requires-python = ">=3.12, <3.14"
[[package]]
name = "root-demo"
version = "1.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
  { name = "only-312", marker = "python_version < '3.13'" },
]
wheels = [WHEEL]
[[package]]
name = "only-312"
version = "1.0"
source = { registry = "https://pypi.org/simple" }
wheels = [WHEEL]
[[package]]
name = "multimodal-knowledge-engine"
version = "0.1.3"
source = { editable = "." }
[package.optional-dependencies]
transcription = [{ name = "root-demo" }]
""".strip().replace("WHEEL", wheel)
        + "\n",
        encoding="utf-8",
    )
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _wheel(wheelhouse, "root_demo-1.0-py3-none-any.whl")
    _wheel(wheelhouse, "only_312-1.0-cp312-cp312-macosx_11_0_arm64.whl")

    projection = receipt.derive_transcription_projection(lock, _cells())
    by_cell = dict(projection.requirements_by_cell)
    resolution = receipt.resolve_projected_wheels(
        receipt.build_wheelhouse_manifest(wheelhouse), projection
    )

    assert [(item.name, item.version) for item in by_cell["3.12"]] == [
        ("only-312", "1.0"),
        ("root-demo", "1.0"),
    ]
    assert [(item.name, item.version) for item in by_cell["3.13"]] == [("root-demo", "1.0")]
    assert b"only-312==1.0" in projection.constraints
    assert set(resolution["3.13"]) == {"root-demo"}


def test_arm64_cells_accept_macos_universal2_abi3_wheel(tmp_path: Path) -> None:
    receipt = _module()
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _wheel(wheelhouse, "protobuf-7.35.1-cp310-abi3-macosx_10_9_universal2.whl")

    resolution = receipt.resolve_wheels(
        receipt.build_wheelhouse_manifest(wheelhouse),
        (receipt.Requirement("protobuf", "7.35.1"),),
        _cells(),
    )

    assert set(resolution) == {"3.12", "3.13"}


def test_check_inputs_uses_canonical_per_cell_constraint_authority(tmp_path: Path) -> None:
    receipt = _module()
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    root = _wheel(wheelhouse, "root_demo-1.0-py3-none-any.whl")
    only = _wheel(wheelhouse, "only_312-1.0-cp312-cp312-macosx_11_0_arm64.whl")
    root_digest = hashlib.sha256(root.read_bytes()).hexdigest()
    only_digest = hashlib.sha256(only.read_bytes()).hexdigest()
    lock = tmp_path / "uv.lock"
    lock.write_text(
        "version = 1\n"
        'requires-python = ">=3.12, <3.14"\n'
        '[[package]]\nname = "root-demo"\nversion = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://example.invalid/root.whl", '
        f'hash = "sha256:{root_digest}", size = 1 }}]\n'
        '[[package]]\nname = "only-312"\nversion = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://example.invalid/only.whl", '
        f'hash = "sha256:{only_digest}", size = 1 }}]\n'
        '[[package]]\nname = "multimodal-knowledge-engine"\nversion = "0.1.3"\n'
        'source = { editable = "." }\n[package.optional-dependencies]\n'
        'transcription = [{ name = "root-demo" }, '
        '{ name = "only-312", marker = "python_version < \'3.13\'" }]\n',
        encoding="utf-8",
    )
    constraints = tmp_path / "constraints.txt"
    constraints.write_bytes(receipt.derive_transcription_projection(lock, _cells()).constraints)
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()

    result = receipt.check_inputs(
        pythons=(Path(sys.executable), Path(sys.executable)),
        wheelhouse=wheelhouse,
        lock_path=lock,
        constraints=constraints,
        fixture_root=fixtures,
    )

    issues = cast(list[dict[str, str]], result["issues"])
    assert "constraints_invalid" not in {issue["code"] for issue in issues}
    assert "wheel_missing" not in {issue["code"] for issue in issues}
    manifest = cast(list[dict[str, object]], result["wheelhouse"])
    assert all(item["build"] is None for item in manifest)


def test_nested_pip_boundary_uses_exact_argv_and_empty_allowlisted_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    python = tmp_path / "python"
    python.write_bytes(b"python")
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _wheel(wheelhouse, "demo-1.0-py3-none-any.whl")
    constraints = tmp_path / "constraints.txt"
    requirements = tmp_path / "requirements.txt"
    constraints.write_bytes(b"demo==1 --hash=sha256:" + b"a" * 64 + b"\n")
    requirements.write_bytes(constraints.read_bytes())
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    home = runtime_root / "home"
    temp = runtime_root / "tmp"
    cwd = runtime_root / "cwd"
    home.mkdir()
    temp.mkdir()
    cwd.mkdir()
    manifest = receipt.build_wheelhouse_manifest(wheelhouse)
    captured: dict[str, object] = {}
    preflight_public = {
        "label": "python-3.12",
        "python_version": "3.12.9",
        "executable_sha256": hashlib.sha256(python.read_bytes()).hexdigest(),
    }
    preflight_file_identity = (1, 2, 3)
    probe_calls: list[tuple[Path, object]] = []

    def intercept(argv: list[str], **kwargs: object) -> SimpleNamespace:
        captured["argv"] = argv
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"", supervision=None)

    monkeypatch.setattr(receipt, "_run_bounded", intercept)
    monkeypatch.setattr(
        receipt,
        "_probe_target_interpreter",
        lambda path, cell: (
            probe_calls.append((path, cell)) or preflight_public,
            preflight_file_identity,
            python.resolve(),
        ),
    )
    monkeypatch.setenv("PIP_INDEX_URL", "https://credential.invalid/simple")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid")
    receipt.run_nested_pip_install(
        python=python,
        wheelhouse=wheelhouse,
        constraints=constraints,
        root_requirements=requirements,
        expected_manifest=manifest,
        constraints_sha256=hashlib.sha256(constraints.read_bytes()).hexdigest(),
        root_requirements_sha256=hashlib.sha256(requirements.read_bytes()).hexdigest(),
        runtime_root=runtime_root,
        home=home,
        temp=temp,
        cwd=cwd,
        cell=_cells()[0],
        preflight_interpreter=preflight_public,
        preflight_file_identity=preflight_file_identity,
    )

    expected = [
        str(python.resolve()),
        "-I",
        "-m",
        "pip",
        "--isolated",
        "--disable-pip-version-check",
        "--no-input",
        "install",
        "--no-index",
        "--find-links",
        wheelhouse.resolve().as_uri(),
        "--only-binary=:all:",
        "--no-cache-dir",
        "--require-hashes",
        "--constraint",
        str(constraints.resolve()),
        "--requirement",
        str(requirements.resolve()),
    ]
    assert captured["argv"] == expected
    assert captured["cwd"] == cwd.resolve()
    assert captured["env"] == {
        "HOME": str(home.resolve()),
        "TMPDIR": str(temp.resolve()),
        "PIP_CONFIG_FILE": os.devnull,
    }
    assert probe_calls == [(python, _cells()[0])]
    rendered = json.dumps(captured, default=str)
    for forbidden in ("PIP_INDEX_URL", "HTTPS_PROXY", "credential.invalid", "proxy.invalid"):
        assert forbidden not in rendered
    profile = cast(Any, captured["profile"])
    assert profile.wall_seconds == 300.0
    assert profile.stdout_bytes == 64 * 1024
    assert profile.stderr_bytes == 64 * 1024


def test_nested_pip_uses_probe_bound_target_after_declared_alias_retarget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    first = tmp_path / "python-first"
    second = tmp_path / "python-second"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    first.chmod(0o700)
    second.chmod(0o700)
    python = tmp_path / "python"
    python.symlink_to(first)
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _wheel(wheelhouse, "demo-1.0-py3-none-any.whl")
    constraints = tmp_path / "constraints.txt"
    constraints.write_bytes(b"demo==1 --hash=sha256:" + b"a" * 64 + b"\n")
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    home = runtime_root / "home"
    temp = runtime_root / "tmp"
    cwd = runtime_root / "cwd"
    home.mkdir()
    temp.mkdir()
    cwd.mkdir()
    manifest = receipt.build_wheelhouse_manifest(wheelhouse)
    public = {"label": "python-3.12", "executable_sha256": "a" * 64}
    identity = (1, 2, 3)
    captured: dict[str, object] = {}

    def probe(_path: Path, _cell: object):
        python.unlink()
        python.symlink_to(second)
        return public, identity, first.resolve()

    def intercept(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        captured["argv"] = argv
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"", supervision=None)

    monkeypatch.setattr(receipt, "_probe_target_interpreter", probe)
    monkeypatch.setattr(receipt, "_run_bounded", intercept)

    receipt.run_nested_pip_install(
        python=python,
        wheelhouse=wheelhouse,
        constraints=constraints,
        root_requirements=constraints,
        expected_manifest=manifest,
        constraints_sha256=hashlib.sha256(constraints.read_bytes()).hexdigest(),
        root_requirements_sha256=hashlib.sha256(constraints.read_bytes()).hexdigest(),
        runtime_root=runtime_root,
        home=home,
        temp=temp,
        cwd=cwd,
        cell=_cells()[0],
        preflight_interpreter=public,
        preflight_file_identity=identity,
    )

    argv = cast(list[str], captured["argv"])
    assert argv[0] == str(first.resolve())
    assert argv[0] != str(python)


def test_nested_pip_rejects_symlink_wheelhouse_and_non_call_owned_cwd(
    tmp_path: Path,
) -> None:
    receipt = _module()
    python = _wheel(tmp_path, "python")
    real_wheelhouse = tmp_path / "real-wheelhouse"
    real_wheelhouse.mkdir()
    _wheel(real_wheelhouse, "demo-1.0-py3-none-any.whl")
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.symlink_to(real_wheelhouse, target_is_directory=True)
    constraints = tmp_path / "constraints.txt"
    constraints.write_bytes(b"demo==1.0 --hash=sha256:" + b"a" * 64 + b"\n")
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    home = runtime_root / "home"
    temp = runtime_root / "tmp"
    home.mkdir()
    temp.mkdir()
    outside_cwd = tmp_path / "outside-cwd"
    outside_cwd.mkdir()

    with pytest.raises(receipt.ReceiptError, match="wheel_input_invalid"):
        receipt.run_nested_pip_install(
            python=python,
            wheelhouse=wheelhouse,
            constraints=constraints,
            root_requirements=constraints,
            expected_manifest=receipt.build_wheelhouse_manifest(real_wheelhouse),
            constraints_sha256=hashlib.sha256(constraints.read_bytes()).hexdigest(),
            root_requirements_sha256=hashlib.sha256(constraints.read_bytes()).hexdigest(),
            runtime_root=runtime_root,
            home=home,
            temp=temp,
            cwd=outside_cwd,
            cell=_cells()[0],
            preflight_interpreter={},
            preflight_file_identity=(),
        )

    with pytest.raises(receipt.ReceiptError, match="runtime_path_invalid"):
        receipt.run_nested_pip_install(
            python=python,
            wheelhouse=real_wheelhouse,
            constraints=constraints,
            root_requirements=constraints,
            expected_manifest=receipt.build_wheelhouse_manifest(real_wheelhouse),
            constraints_sha256=hashlib.sha256(constraints.read_bytes()).hexdigest(),
            root_requirements_sha256=hashlib.sha256(constraints.read_bytes()).hexdigest(),
            runtime_root=runtime_root,
            home=home,
            temp=temp,
            cwd=outside_cwd,
            cell=_cells()[0],
            preflight_interpreter={},
            preflight_file_identity=(),
        )

    owned_cwd = runtime_root / "cwd"
    owned_cwd.mkdir()
    with pytest.raises(receipt.ReceiptError, match="pip_input_identity_drift"):
        receipt.run_nested_pip_install(
            python=python,
            wheelhouse=real_wheelhouse,
            constraints=constraints,
            root_requirements=constraints,
            expected_manifest=receipt.build_wheelhouse_manifest(real_wheelhouse),
            constraints_sha256="0" * 64,
            root_requirements_sha256=hashlib.sha256(constraints.read_bytes()).hexdigest(),
            runtime_root=runtime_root,
            home=home,
            temp=temp,
            cwd=owned_cwd,
            cell=_cells()[0],
            preflight_interpreter={},
            preflight_file_identity=(),
        )


def test_check_inputs_is_closed_sorted_public_safe_and_does_not_write(
    tmp_path: Path,
) -> None:
    receipt = _module()
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _wheel(wheelhouse, "unexpected-1.0-py3-none-any.whl")
    constraints = tmp_path / "constraints.txt"
    constraints.write_text("broken\n", encoding="ascii")
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    before = sorted(
        (path.relative_to(tmp_path), path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    )

    result = receipt.check_inputs(
        pythons=(Path(sys.executable), Path(sys.executable)),
        wheelhouse=wheelhouse,
        lock_path=Path(__file__).parents[2] / "uv.lock",
        constraints=constraints,
        fixture_root=fixtures,
    )
    after = sorted(
        (path.relative_to(tmp_path), path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    )

    assert result["status"] == "failed"
    assert result["gate"] == "input_validation_failed"
    assert result["distribution"] == {
        "external_binary_redistribution": "not_performed",
        "redistribution_authority": "not_claimed",
    }
    controller = cast(dict[str, str], result["controller"])
    assert controller["implementation"] == "cpython"
    assert controller["python_version"] == ".".join(map(str, sys.version_info[:3]))
    assert controller["platform"] == sysconfig.get_platform()
    assert controller["executable_type"] == "regular"
    assert (
        controller["executable_mode"]
        == f"{stat.S_IMODE(Path(sys.executable).resolve().stat().st_mode):04o}"
    )
    assert (
        controller["executable_sha256"]
        == hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()
    )
    assert "sha256" not in controller
    script = cast(dict[str, str], result["script"])
    assert (
        script["sha256"]
        == hashlib.sha256(
            (
                Path(__file__).parents[2] / "scripts" / "direct_audio_dependency_receipt.py"
            ).read_bytes()
        ).hexdigest()
    )
    issues = cast(list[dict[str, str]], result["issues"])
    assert issues == sorted(issues, key=lambda item: json.dumps(item, sort_keys=True))
    assert before == after
    rendered = json.dumps(result, sort_keys=True)
    for forbidden in (
        str(tmp_path),
        os.uname().nodename,
        "PATH",
        "secret-token-value",
        "timestamp",
    ):
        assert forbidden not in rendered


def test_check_inputs_fails_closed_when_controller_executable_is_not_executable(
    tmp_path: Path,
) -> None:
    receipt = _module()
    controller = tmp_path / "controller-python"
    controller.write_bytes(b"not executable")
    controller.chmod(0o600)
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    constraints = tmp_path / "constraints.txt"
    constraints.write_text("broken\n", encoding="ascii")
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()

    result = receipt.check_inputs(
        pythons=(Path(sys.executable), Path(sys.executable)),
        wheelhouse=wheelhouse,
        lock_path=Path(__file__).parents[2] / "uv.lock",
        constraints=constraints,
        fixture_root=fixtures,
        controller_executable=controller,
    )

    issues = cast(list[dict[str, str]], result["issues"])
    assert {issue["code"] for issue in issues} >= {"controller_executable_invalid"}
    assert result["controller"] is None


@pytest.mark.parametrize(
    ("input_kind", "expected_code"),
    [
        ("missing", "wheel_missing"),
        ("substituted", "wheel_substituted"),
        ("extra", "wheel_surplus"),
    ],
)
def test_check_inputs_reports_missing_substituted_and_extra_wheels(
    tmp_path: Path, input_kind: str, expected_code: str
) -> None:
    receipt = _module()
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    expected_payload = b"approved-wheel"
    expected_digest = hashlib.sha256(expected_payload).hexdigest()
    if input_kind != "missing":
        payload = b"substituted" if input_kind == "substituted" else expected_payload
        _wheel(wheelhouse, "demo-1.0-py3-none-any.whl", payload)
    if input_kind == "extra":
        _wheel(wheelhouse, "extra-1.0-py3-none-any.whl")
    lock, constraints = _write_single_package_lock(
        tmp_path, name="demo", version="1.0", sha256=expected_digest
    )
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()

    result = receipt.check_inputs(
        pythons=(Path(sys.executable), Path(sys.executable)),
        wheelhouse=wheelhouse,
        lock_path=lock,
        constraints=constraints,
        fixture_root=fixtures,
    )

    issues = cast(list[dict[str, str]], result["issues"])
    assert expected_code in {issue["code"] for issue in issues}


@pytest.mark.parametrize(
    ("input_kind", "expected_code"),
    [
        ("ambiguous", "wheel_ambiguous"),
        ("wrong_version", "wheel_wrong_version"),
        ("wrong_tag", "wheel_wrong_tag"),
    ],
)
def test_check_inputs_reports_cell_specific_candidate_failures(
    tmp_path: Path, input_kind: str, expected_code: str
) -> None:
    receipt = _module()
    payload = b"approved-wheel"
    lock, constraints = _write_single_package_lock(
        tmp_path,
        name="demo",
        version="1.0",
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    if input_kind == "ambiguous":
        _wheel(wheelhouse, "demo-1.0-py3-none-any.whl", payload)
        _wheel(wheelhouse, "demo-1.0-cp310-abi3-macosx_10_9_universal2.whl", payload)
    elif input_kind == "wrong_version":
        _wheel(wheelhouse, "demo-9.0-py3-none-any.whl", payload)
    else:
        _wheel(wheelhouse, "demo-1.0-cp311-cp311-macosx_11_0_arm64.whl", payload)
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()

    result = receipt.check_inputs(
        pythons=(Path(sys.executable), Path(sys.executable)),
        wheelhouse=wheelhouse,
        lock_path=lock,
        constraints=constraints,
        fixture_root=fixtures,
    )

    issues = cast(list[dict[str, str]], result["issues"])
    matching = [issue for issue in issues if issue["code"] == expected_code]
    assert {issue["subject"] for issue in matching} == {
        "3.12:demo==1.0",
        "3.13:demo==1.0",
    }


def test_check_inputs_accumulates_all_missing_cells_and_distributions(
    tmp_path: Path,
) -> None:
    receipt = _module()
    first_digest = "a" * 64
    second_digest = "b" * 64
    lock = tmp_path / "uv.lock"
    lock.write_text(
        "version = 1\n"
        'requires-python = ">=3.12, <3.14"\n'
        '[[package]]\nname = "first"\nversion = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://example.invalid/first.whl", '
        f'hash = "sha256:{first_digest}", size = 1 }}]\n'
        '[[package]]\nname = "second"\nversion = "2.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://example.invalid/second.whl", '
        f'hash = "sha256:{second_digest}", size = 1 }}]\n'
        '[[package]]\nname = "multimodal-knowledge-engine"\nversion = "0.1.3"\n'
        'source = { editable = "." }\n[package.optional-dependencies]\n'
        'transcription = [{ name = "first" }, { name = "second" }]\n',
        encoding="utf-8",
    )
    constraints = tmp_path / "constraints.txt"
    constraints.write_bytes(receipt.derive_transcription_projection(lock, _cells()).constraints)
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()

    result = receipt.check_inputs(
        pythons=(Path(sys.executable), Path(sys.executable)),
        wheelhouse=wheelhouse,
        lock_path=lock,
        constraints=constraints,
        fixture_root=fixtures,
    )

    issues = cast(list[dict[str, str]], result["issues"])
    missing = [issue for issue in issues if issue["code"] == "wheel_missing"]
    assert {issue["subject"] for issue in missing} == {
        "3.12:first==1.0",
        "3.12:second==2.0",
        "3.13:first==1.0",
        "3.13:second==2.0",
    }


def test_missing_declared_paths_still_emit_full_lock_derived_matrix(
    tmp_path: Path,
) -> None:
    receipt = _module()
    lock = tmp_path / "uv.lock"
    first_digest = "a" * 64
    second_digest = "b" * 64
    lock.write_text(
        "version = 1\n"
        'requires-python = ">=3.12, <3.14"\n'
        '[[package]]\nname = "first"\nversion = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://example.invalid/first.whl", '
        f'hash = "sha256:{first_digest}", size = 1 }}]\n'
        '[[package]]\nname = "second"\nversion = "2.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://example.invalid/second.whl", '
        f'hash = "sha256:{second_digest}", size = 1 }}]\n'
        '[[package]]\nname = "multimodal-knowledge-engine"\nversion = "0.1.3"\n'
        'source = { editable = "." }\n[package.optional-dependencies]\n'
        'transcription = [{ name = "first" }, { name = "second" }]\n',
        encoding="utf-8",
    )
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()

    result = receipt.check_inputs(
        pythons=(Path(sys.executable), Path(sys.executable)),
        wheelhouse=tmp_path / "missing-wheelhouse",
        lock_path=lock,
        constraints=tmp_path / "missing-constraints.txt",
        fixture_root=fixtures,
    )

    issues = cast(list[dict[str, str]], result["issues"])
    assert {issue["code"] for issue in issues} >= {
        "constraints_missing",
        "wheelhouse_missing",
    }
    assert {issue["subject"] for issue in issues if issue["code"] == "wheel_missing"} == {
        "3.12:first==1.0",
        "3.12:second==2.0",
        "3.13:first==1.0",
        "3.13:second==2.0",
    }
    assert not (tmp_path / "missing-wheelhouse").exists()
    assert not (tmp_path / "missing-constraints.txt").exists()


def test_interpreter_targets_have_explicit_labels_and_distinct_file_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _module()
    lock, constraints = _write_single_package_lock(
        tmp_path, name="demo", version="1.0", sha256="a" * 64
    )
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    snapshot = receipt._snapshot_executable(Path(sys.executable))  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(
        receipt,
        "_probe_target_interpreter",
        lambda _path, cell: (
            {
                "label": f"python-{cell.version}",
                "python_version": f"{cell.version}.0",
                "executable_sha256": snapshot.sha256,
            },
            snapshot.identity,
            snapshot.resolved,
        ),
    )

    result = receipt.check_inputs(
        pythons=(Path(sys.executable), Path(sys.executable)),
        wheelhouse=wheelhouse,
        lock_path=lock,
        constraints=constraints,
        fixture_root=fixtures,
    )

    interpreters = cast(list[dict[str, str]], result["interpreters"])
    assert [item["label"] for item in interpreters] == ["python-3.12", "python-3.13"]
    issues = cast(list[dict[str, str]], result["issues"])
    assert {
        "code": "interpreter_identity_duplicate",
        "subject": "python-3.12,python-3.13",
    } in issues


def test_interpreter_aliases_to_one_target_cannot_masquerade_as_two_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    first = tmp_path / "python3.12"
    second = tmp_path / "python3.13"
    first.symlink_to(Path(sys.executable))
    second.symlink_to(Path(sys.executable))
    lock, constraints = _write_single_package_lock(
        tmp_path, name="demo", version="1.0", sha256="a" * 64
    )
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()

    def probe(path: Path, cell: Any) -> tuple[dict[str, object], tuple[int, ...], Path]:
        snapshot = receipt._snapshot_executable(path)  # pyright: ignore[reportPrivateUsage]
        return {"label": f"python-{cell.version}"}, snapshot.identity, snapshot.resolved

    monkeypatch.setattr(receipt, "_probe_target_interpreter", probe)

    result = receipt.check_inputs(
        pythons=(first, second),
        wheelhouse=wheelhouse,
        lock_path=lock,
        constraints=constraints,
        fixture_root=fixtures,
    )

    assert {
        "code": "interpreter_identity_duplicate",
        "subject": "python-3.12,python-3.13",
    } in cast(list[dict[str, str]], result["issues"])


def test_check_inputs_rejects_constraints_not_bound_to_declared_lock(tmp_path: Path) -> None:
    receipt = _module()
    payload = b"wheel"
    lock, constraints = _write_single_package_lock(
        tmp_path,
        name="demo",
        version="1.0",
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    constraints.write_bytes(constraints.read_bytes() + b"# arbitrary\n")
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _wheel(wheelhouse, "demo-1.0-py3-none-any.whl", payload)
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()

    result = receipt.check_inputs(
        pythons=(Path(sys.executable), Path(sys.executable)),
        wheelhouse=wheelhouse,
        lock_path=lock,
        constraints=constraints,
        fixture_root=fixtures,
    )

    issues = cast(list[dict[str, str]], result["issues"])
    assert "constraints_projection_drift" in {issue["code"] for issue in issues}
    assert result["lock_sha256"] == hashlib.sha256(lock.read_bytes()).hexdigest()
    assert result["constraints_sha256"] == hashlib.sha256(constraints.read_bytes()).hexdigest()


def test_public_manifest_serializes_parsed_build_tag(tmp_path: Path) -> None:
    receipt = _module()
    payload = b"build-wheel"
    lock, constraints = _write_single_package_lock(
        tmp_path,
        name="demo",
        version="1.0",
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _wheel(wheelhouse, "demo-1.0-2-py3-none-any.whl", payload)
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()

    result = receipt.check_inputs(
        pythons=(Path(sys.executable), Path(sys.executable)),
        wheelhouse=wheelhouse,
        lock_path=lock,
        constraints=constraints,
        fixture_root=fixtures,
    )

    manifest = cast(list[dict[str, object]], result["wheelhouse"])
    assert manifest[0]["build"] == "2"


def test_real_check_inputs_cli_requires_isolated_no_bytecode_controller(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parents[2] / "scripts" / "direct_audio_dependency_receipt.py"
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    constraints = tmp_path / "constraints.txt"
    constraints.write_text("broken\n", encoding="ascii")
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    argv = [
        str(script),
        "--check-inputs",
        "--python",
        sys.executable,
        "--python",
        sys.executable,
        "--wheelhouse",
        str(wheelhouse),
        "--lock",
        str(Path(__file__).parents[2] / "uv.lock"),
        "--constraints",
        str(constraints),
        "--fixture-root",
        str(fixtures),
        "--json",
    ]

    rejected = subprocess.run([sys.executable, *argv], capture_output=True, check=False)
    accepted = subprocess.run([sys.executable, "-I", "-B", *argv], capture_output=True, check=False)

    assert rejected.returncode == 2
    assert json.loads(rejected.stdout)["failure"] == "controller_not_isolated"
    assert accepted.returncode == 1
    payload = json.loads(accepted.stdout)
    assert payload["status"] == "failed"
    assert payload["gate"] == "input_validation_failed"


def test_receipt_generation_fails_closed_without_complete_authorized_evidence() -> None:
    receipt = _module()

    result = receipt.validate_generation_evidence({})

    assert result == {
        "failure": "generation_evidence_incomplete",
        "status": "failed",
    }


def test_receipt_generation_rejects_unvalidated_truthy_placeholders() -> None:
    receipt = _module()
    placeholders = {
        "external_constraints": {"status": "claimed"},
        "wheelhouse_manifest": {"status": "claimed"},
        "cells": {"status": "claimed"},
        "pyav_runtime": {"status": "claimed"},
        "binary_components": {"status": "claimed"},
        "licenses": {"status": "claimed"},
        "notices": {"status": "claimed"},
        "fixtures": {"status": "claimed"},
        "child_containment": {"status": "claimed"},
    }

    result = receipt.validate_generation_evidence(placeholders)

    assert result == {
        "failure": "generation_evidence_incomplete",
        "status": "failed",
    }


def _target_probe_payload(
    version: str, *, sysconfig_platform: str = "macosx-11.0-arm64"
) -> dict[str, object]:
    compact = version.replace(".", "")
    return {
        "schema": "mke.target_interpreter_identity.v1",
        "implementation": "cpython",
        "python_version": [int(version.split(".")[0]), int(version.split(".")[1]), 9],
        "system": "Darwin",
        "machine": "arm64",
        "sysconfig_platform": sysconfig_platform,
        "soabi": f"cpython-{compact}-darwin",
        "ext_suffix": f".cpython-{compact}-darwin.so",
        "cache_tag": f"cpython-{compact}",
        "abiflags": "",
        "pointer_bits": 64,
        "byteorder": "little",
    }


def _canonical_probe_output(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"


def test_target_interpreter_probe_uses_only_fixed_isolated_bounded_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    target = tmp_path / "python3.12"
    target.write_bytes(b"fixed target bytes")
    target.chmod(0o700)
    captured: dict[str, object] = {}

    def intercept(argv: list[str], **kwargs: object) -> SimpleNamespace:
        captured["argv"] = argv
        captured.update(kwargs)
        return SimpleNamespace(
            returncode=0,
            stdout=_canonical_probe_output(_target_probe_payload("3.12")),
            stderr=b"",
            supervision=None,
        )

    monkeypatch.setattr(receipt, "_run_bounded", intercept)

    public, file_identity, resolved = receipt._probe_target_interpreter(  # pyright: ignore[reportPrivateUsage]
        target, _cells()[0]
    )

    assert captured["argv"] == [
        str(target.resolve()),
        "-I",
        "-B",
        "-c",
        receipt._INTERPRETER_PROBE_SOURCE,  # pyright: ignore[reportPrivateUsage]
    ]
    assert captured["env"] == {}
    assert captured["cwd"] is None
    profile = cast(Any, captured["profile"])
    assert profile.wall_seconds == 5.0
    assert profile.stdout_bytes == 4096
    assert profile.stderr_bytes == 4096
    assert public["label"] == "python-3.12"
    assert public["python_version"] == "3.12.9"
    assert public["executable_sha256"] == hashlib.sha256(b"fixed target bytes").hexdigest()
    assert file_identity
    assert resolved == target.resolve()
    rendered = json.dumps(public, sort_keys=True)
    assert str(tmp_path) not in rendered
    assert "st_dev" not in rendered
    assert "st_ino" not in rendered
    assert "ctime" not in rendered


def test_target_interpreter_probe_accepts_executable_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    target = tmp_path / "python-target"
    target.write_bytes(b"fixed target bytes")
    target.chmod(0o700)
    declared = tmp_path / "python3.12"
    declared.symlink_to(target)
    captured: dict[str, object] = {}

    def intercept(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        captured["argv"] = argv
        return SimpleNamespace(
            returncode=0,
            stdout=_canonical_probe_output(_target_probe_payload("3.12")),
            stderr=b"",
            supervision=None,
        )

    monkeypatch.setattr(receipt, "_run_bounded", intercept)

    public, identity, resolved = receipt._probe_target_interpreter(  # pyright: ignore[reportPrivateUsage]
        declared, _cells()[0]
    )

    assert cast(list[str], captured["argv"])[0] == str(target.resolve())
    assert resolved == target.resolve()
    assert identity
    assert public["executable_sha256"] == hashlib.sha256(b"fixed target bytes").hexdigest()


@pytest.mark.parametrize("drifted_path", ["declared", "target"])
def test_target_interpreter_snapshot_detects_ctime_only_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drifted_path: str
) -> None:
    receipt = _module()
    target = tmp_path / "python-target"
    target.write_bytes(b"python")
    target.chmod(0o700)
    declared = tmp_path / "python3.12"
    declared.symlink_to(target)
    original_lstat = Path.lstat
    calls = {declared: 0, target: 0}

    def drifting_lstat(path: Path):
        observed = original_lstat(path)
        if path in calls:
            calls[path] += 1
            selected = declared if drifted_path == "declared" else target
            if path == selected and calls[path] == 2:
                values = {
                    name: getattr(observed, name)
                    for name in (
                        "st_dev",
                        "st_ino",
                        "st_mode",
                        "st_size",
                        "st_mtime_ns",
                        "st_ctime_ns",
                    )
                }
                values["st_ctime_ns"] += 1
                return SimpleNamespace(**values)
        return observed

    monkeypatch.setattr(receipt, "_read_regular", lambda _path: b"python")
    monkeypatch.setattr(Path, "lstat", drifting_lstat)

    with pytest.raises(receipt.ReceiptError, match="interpreter_identity_drift"):
        receipt._snapshot_interpreter_executable(declared)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("kind", ["dangling", "directory", "non_executable"])
def test_target_interpreter_probe_rejects_invalid_file_kinds(tmp_path: Path, kind: str) -> None:
    receipt = _module()
    target = tmp_path / "python3.12"
    if kind == "dangling":
        target.symlink_to(tmp_path / "missing")
    elif kind == "directory":
        target.mkdir()
    else:
        target.write_bytes(b"not executable")
        target.chmod(0o600)

    with pytest.raises(receipt.ReceiptError, match="interpreter_invalid"):
        receipt._probe_target_interpreter(target, _cells()[0])  # pyright: ignore[reportPrivateUsage]


def test_target_interpreter_probe_rejects_non_python_executable() -> None:
    receipt = _module()

    with pytest.raises(receipt.ReceiptError, match="interpreter_probe_failed"):
        receipt._probe_target_interpreter(Path("/bin/ls"), _cells()[0])  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("implementation", "pypy"),
        ("python_version", [3, 13, 0]),
        ("system", "Linux"),
        ("machine", "x86_64"),
        ("sysconfig_platform", "macosx-11.0-x86_64"),
        ("soabi", "cpython-313-darwin"),
        ("ext_suffix", ".cpython-313-darwin.so"),
        ("cache_tag", "cpython-313"),
        ("abiflags", "d"),
        ("pointer_bits", 32),
        ("byteorder", "big"),
    ],
)
def test_target_interpreter_probe_rejects_cell_and_abi_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    receipt = _module()
    target = tmp_path / "python3.12"
    target.write_bytes(b"python")
    target.chmod(0o700)
    payload = _target_probe_payload("3.12")
    payload[field] = value
    monkeypatch.setattr(
        receipt,
        "_run_bounded",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=_canonical_probe_output(payload),
            stderr=b"",
            supervision=None,
        ),
    )

    with pytest.raises(receipt.ReceiptError, match="interpreter_identity_mismatch"):
        receipt._probe_target_interpreter(target, _cells()[0])  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    ("result", "code"),
    [
        (
            SimpleNamespace(returncode=0, stdout=b"{}\n", stderr=b"", supervision=None),
            "interpreter_output_invalid",
        ),
        ("bounded_stdout_exceeded", "bounded_stdout_exceeded"),
        ("bounded_timeout", "bounded_timeout"),
    ],
)
def test_target_interpreter_probe_rejects_malformed_oversized_and_timeout_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    result: object,
    code: str,
) -> None:
    receipt = _module()
    target = tmp_path / "python3.12"
    target.write_bytes(b"python")
    target.chmod(0o700)

    def intercept(*_args: object, **_kwargs: object) -> object:
        if isinstance(result, str):
            raise receipt.ReceiptError(result)
        return result

    monkeypatch.setattr(receipt, "_run_bounded", intercept)
    with pytest.raises(receipt.ReceiptError, match=code):
        receipt._probe_target_interpreter(target, _cells()[0])  # pyright: ignore[reportPrivateUsage]


def test_target_interpreter_probe_rejects_before_after_executable_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    target = tmp_path / "python3.12"
    target.write_bytes(b"python")
    target.chmod(0o700)
    snapshots = iter(
        [
            SimpleNamespace(resolved=target, identity=(1,), sha256="a" * 64),
            SimpleNamespace(resolved=target, identity=(2,), sha256="b" * 64),
        ]
    )
    monkeypatch.setattr(receipt, "_snapshot_executable", lambda _path: next(snapshots))
    monkeypatch.setattr(
        receipt,
        "_run_bounded",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=_canonical_probe_output(_target_probe_payload("3.12")),
            stderr=b"",
            supervision=None,
        ),
    )

    with pytest.raises(receipt.ReceiptError, match="interpreter_identity_drift"):
        receipt._probe_target_interpreter(target, _cells()[0])  # pyright: ignore[reportPrivateUsage]


def test_bounded_runner_records_darwin_footprint_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _module()

    class Sampler:
        identity = "leader-identity"

        def sample(self) -> int:
            return 4096

    monkeypatch.setattr(receipt, "_DarwinFootprintSampler", lambda _pid: Sampler())
    profile = receipt.BoundedProfile(
        wall_seconds=5.0,
        stdout_bytes=4096,
        stderr_bytes=4096,
        footprint_bytes=64 * 1024 * 1024,
        poll_seconds=0.01,
        term_grace_seconds=0.2,
        controlled_allocator="stdlib-bytearray-v1",
    )

    result = receipt._run_bounded(  # pyright: ignore[reportPrivateUsage]
        [sys.executable, "-I", "-B", "-c", "print('bounded')"],
        env={},
        cwd=None,
        profile=profile,
    )

    assert result.stdout == b"bounded\n"
    assert result.supervision == {
        "api": "proc_pid_rusage",
        "api_version": "RUSAGE_INFO_V4",
        "tool": "stdlib-ctypes",
        "metric": "ri_phys_footprint",
        "leader_scope": "process_group_leader",
        "leader_identity_binding": "pid+ri_proc_start_abstime",
        "descendants_scope": "ordinary_cooperative_descendants",
        "budget_mode": "absolute",
        "baseline_bytes": 4096,
        "budget_bytes": 64 * 1024 * 1024,
        "poll_seconds": 0.01,
        "controlled_allocator": "stdlib-bytearray-v1",
        "observed_max_bytes": 4096,
        "overshoot_bytes": 0,
        "budget_outcome": "within_budget",
        "transient_overshoot_possible": True,
        "cleanup": {
            "sigterm_sent": False,
            "sigkill_sent": False,
            "waited": True,
            "process_group_absent": True,
        },
        "hard_kernel_enforced": False,
        "bounds": {
            "wall_seconds": 5.0,
            "stdout_bytes": 4096,
            "stderr_bytes": 4096,
            "input_bytes": 0,
            "temp_bytes": 0,
            "output_bytes": 4096,
        },
    }


def test_target_interpreter_accepts_compatible_arm64_sysconfig_floor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    target = tmp_path / "python3.13"
    target.write_bytes(b"python")
    target.chmod(0o700)
    payload = _target_probe_payload("3.13", sysconfig_platform="macosx-12.1-arm64")
    monkeypatch.setattr(
        receipt,
        "_run_bounded",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=_canonical_probe_output(payload),
            stderr=b"",
            supervision=None,
        ),
    )

    public, _, _ = receipt._probe_target_interpreter(target, _cells()[1])  # pyright: ignore[reportPrivateUsage]

    assert public["sysconfig_platform"] == "macosx-12.1-arm64"
    assert public["pointer_bits"] == 64


def test_target_interpreter_rejects_noncanonical_or_trailing_probe_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    target = tmp_path / "python3.12"
    target.write_bytes(b"python")
    target.chmod(0o700)
    payload = _target_probe_payload("3.12")
    monkeypatch.setattr(
        receipt,
        "_run_bounded",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=_canonical_probe_output(payload) + b"{}\n",
            stderr=b"",
            supervision=None,
        ),
    )

    with pytest.raises(receipt.ReceiptError, match="interpreter_output_invalid"):
        receipt._probe_target_interpreter(target, _cells()[0])  # pyright: ignore[reportPrivateUsage]


def test_public_rusage_v4_layout_matches_darwin_authority() -> None:
    receipt = _module()

    assert receipt.ctypes.sizeof(receipt._DarwinRusageInfoV4) == 296  # pyright: ignore[reportPrivateUsage]
    assert receipt._DarwinRusageInfoV4.ri_phys_footprint.offset == 72  # pyright: ignore[reportPrivateUsage]
    assert receipt._DarwinRusageInfoV4.ri_proc_start_abstime.offset == 80  # pyright: ignore[reportPrivateUsage]


def test_controlled_allocator_over_budget_returns_kill_and_wait_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _module()

    class Sampler:
        identity = "leader-identity"
        calls = 0

        def sample(self) -> int:
            self.calls += 1
            return 0 if self.calls <= 10 else 8192

    processes: list[subprocess.Popen[bytes]] = []
    original_popen = receipt.subprocess.Popen

    def intercept_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        process = original_popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(receipt, "_DarwinFootprintSampler", lambda _pid: Sampler())
    monkeypatch.setattr(receipt.subprocess, "Popen", intercept_popen)
    profile = receipt.BoundedProfile(
        wall_seconds=5.0,
        stdout_bytes=4096,
        stderr_bytes=4096,
        footprint_bytes=4096,
        poll_seconds=0.01,
        term_grace_seconds=0.05,
        controlled_allocator="stdlib-bytearray-v1",
    )
    source = (
        "import signal,time;"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
        "value=bytearray(8*1024*1024);"
        "time.sleep(5)"
    )

    result = receipt._run_bounded(  # pyright: ignore[reportPrivateUsage]
        [sys.executable, "-I", "-B", "-c", source],
        env={},
        cwd=None,
        profile=profile,
    )

    assert processes and processes[0].poll() is not None
    supervision = cast(dict[str, object], result.supervision)
    assert supervision["budget_outcome"] == "exceeded_terminated"
    assert supervision["observed_max_bytes"] == 8192
    assert supervision["overshoot_bytes"] == 4096
    assert supervision["cleanup"] == {
        "sigterm_sent": True,
        "sigkill_sent": True,
        "waited": True,
        "process_group_absent": True,
    }


def test_cleanup_waits_for_leader_exited_cooperative_descendant_before_sigkill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _module()
    probe_calls = 0
    signals: list[int] = []
    process = SimpleNamespace(pid=43210, poll=lambda: 0, wait=lambda timeout: 0)

    def process_group_absent(_pid: int) -> bool:
        nonlocal probe_calls
        probe_calls += 1
        return probe_calls >= 4

    monkeypatch.setattr(receipt, "_process_group_absent", process_group_absent)
    monkeypatch.setattr(receipt.os, "killpg", lambda _pid, sig: signals.append(sig))
    monkeypatch.setattr(receipt.time, "sleep", lambda _seconds: None)

    cleanup = receipt._cleanup_process_group(  # pyright: ignore[reportPrivateUsage]
        process,
        grace_seconds=0.2,
        terminate=True,
    )

    assert signals == [receipt.signal.SIGTERM]
    assert cleanup["sigkill_sent"] is False
    assert cleanup["process_group_absent"] is True


def test_signal_failure_retries_cleanup_and_preserves_supervision_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _module()

    class Sampler:
        identity = "leader-identity"
        calls = 0

        def sample(self) -> int:
            self.calls += 1
            if self.calls > 1:
                raise receipt.ReceiptError("footprint_sampling_failed")
            return 1024

    original_killpg = receipt.os.killpg
    term_calls = 0

    def flaky_killpg(pid: int, sig: int) -> None:
        nonlocal term_calls
        if sig == receipt.signal.SIGTERM:
            term_calls += 1
            if term_calls == 1:
                raise PermissionError("denied")
        original_killpg(pid, sig)

    monkeypatch.setattr(receipt, "_DarwinFootprintSampler", lambda _pid: Sampler())
    monkeypatch.setattr(receipt.os, "killpg", flaky_killpg)
    profile = receipt.BoundedProfile(
        wall_seconds=5.0,
        stdout_bytes=4096,
        stderr_bytes=4096,
        footprint_bytes=64 * 1024 * 1024,
        poll_seconds=0.01,
        term_grace_seconds=0.2,
    )

    with pytest.raises(receipt.ReceiptError, match="footprint_sampling_failed") as raised:
        receipt._run_bounded(  # pyright: ignore[reportPrivateUsage]
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(5)"],
            env={},
            cwd=None,
            profile=profile,
        )

    assert term_calls == 2
    details = cast(dict[str, object], raised.value.details)
    assert details["budget_outcome"] == "supervision_failed"
    assert cast(dict[str, bool], details["cleanup"])["process_group_absent"] is True


@pytest.mark.parametrize("operation", ["poll", "wait"])
def test_process_reap_failure_retries_cleanup_and_preserves_supervision_receipt(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    receipt = _module()

    class Sampler:
        identity = "leader-identity"
        calls = 0

        def sample(self) -> int:
            self.calls += 1
            if self.calls > 1:
                raise receipt.ReceiptError("footprint_sampling_failed")
            return 1024

    original = getattr(receipt.subprocess.Popen, operation)
    calls = 0

    def fail_once(process: object, *args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        fail_at = 2 if operation == "poll" else 1
        if calls == fail_at:
            raise ChildProcessError("reap failed")
        return original(process, *args, **kwargs)

    monkeypatch.setattr(receipt, "_DarwinFootprintSampler", lambda _pid: Sampler())
    monkeypatch.setattr(receipt.subprocess.Popen, operation, fail_once)
    group_probes = iter([False, True, True, True])
    monkeypatch.setattr(receipt, "_process_group_absent", lambda _pid: next(group_probes))
    profile = receipt.BoundedProfile(
        wall_seconds=5.0,
        stdout_bytes=4096,
        stderr_bytes=4096,
        footprint_bytes=64 * 1024 * 1024,
        poll_seconds=0.01,
        term_grace_seconds=0.2,
    )

    with pytest.raises(receipt.ReceiptError, match="footprint_sampling_failed") as raised:
        receipt._run_bounded(  # pyright: ignore[reportPrivateUsage]
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(5)"],
            env={},
            cwd=None,
            profile=profile,
        )

    details = cast(dict[str, object], raised.value.details)
    assert details["budget_outcome"] == "supervision_failed"
    assert cast(dict[str, bool], details["cleanup"])["process_group_absent"] is True


def test_selector_registration_failure_has_supervision_and_cleanup_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _module()

    class Sampler:
        identity = "leader-identity"

        def sample(self) -> int:
            return 1024

    class FailingSelector:
        def register(self, *_args: object) -> None:
            raise OSError("registration failed")

        def close(self) -> None:
            pass

    monkeypatch.setattr(receipt, "_DarwinFootprintSampler", lambda _pid: Sampler())
    monkeypatch.setattr(receipt.selectors, "DefaultSelector", FailingSelector)
    profile = receipt.BoundedProfile(
        wall_seconds=5.0,
        stdout_bytes=4096,
        stderr_bytes=4096,
        footprint_bytes=64 * 1024 * 1024,
        term_grace_seconds=0.2,
    )

    with pytest.raises(receipt.ReceiptError, match="bounded_supervision_failed") as raised:
        receipt._run_bounded(  # pyright: ignore[reportPrivateUsage]
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(5)"],
            env={},
            cwd=None,
            profile=profile,
        )

    details = cast(dict[str, object], raised.value.details)
    assert details["budget_outcome"] == "supervision_failed"
    assert cast(dict[str, bool], details["cleanup"])["process_group_absent"] is True


def test_sampler_initialization_failure_has_supervision_and_cleanup_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _module()

    def fail_sampler(_pid: int) -> None:
        raise receipt.ReceiptError("footprint_sampling_failed")

    monkeypatch.setattr(receipt, "_DarwinFootprintSampler", fail_sampler)
    profile = receipt.BoundedProfile(
        wall_seconds=5.0,
        stdout_bytes=4096,
        stderr_bytes=4096,
        footprint_bytes=64 * 1024 * 1024,
        term_grace_seconds=0.2,
    )

    with pytest.raises(receipt.ReceiptError, match="footprint_sampling_failed") as raised:
        receipt._run_bounded(  # pyright: ignore[reportPrivateUsage]
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(5)"],
            env={},
            cwd=None,
            profile=profile,
        )

    details = cast(dict[str, object], raised.value.details)
    assert details["budget_outcome"] == "supervision_failed"
    assert cast(dict[str, bool], details["cleanup"])["process_group_absent"] is True


@pytest.mark.parametrize("failure", [PermissionError("denied"), OSError("lookup failed")])
def test_process_group_identity_lookup_errors_fail_closed_with_cleanup_receipt(
    monkeypatch: pytest.MonkeyPatch, failure: OSError
) -> None:
    receipt = _module()
    monkeypatch.setattr(
        receipt.os,
        "getpgid",
        lambda _pid: (_ for _ in ()).throw(failure),
    )
    profile = receipt.BoundedProfile(
        wall_seconds=5.0,
        stdout_bytes=4096,
        stderr_bytes=4096,
        footprint_bytes=64 * 1024 * 1024,
        term_grace_seconds=0.2,
    )

    with pytest.raises(receipt.ReceiptError, match="bounded_supervision_failed") as raised:
        receipt._run_bounded(  # pyright: ignore[reportPrivateUsage]
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(5)"],
            env={},
            cwd=None,
            profile=profile,
        )

    details = cast(dict[str, object], raised.value.details)
    assert details["budget_outcome"] == "supervision_failed"
    assert cast(dict[str, bool], details["cleanup"])["process_group_absent"] is True


@pytest.mark.parametrize("failure", [PermissionError("denied"), OSError("probe failed")])
def test_process_group_probe_errors_fail_closed(
    monkeypatch: pytest.MonkeyPatch, failure: OSError
) -> None:
    receipt = _module()
    monkeypatch.setattr(receipt.os, "killpg", lambda _pid, _sig: (_ for _ in ()).throw(failure))

    with pytest.raises(receipt.ReceiptError, match="bounded_cleanup_incomplete"):
        receipt._process_group_absent(43210)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.skipif(platform.system() != "Darwin", reason="Darwin proc_pid_rusage authority")
def test_real_darwin_controlled_allocator_proves_footprint_and_cleanup() -> None:
    receipt = _module()
    profile = receipt.BoundedProfile(
        wall_seconds=5.0,
        stdout_bytes=4096,
        stderr_bytes=4096,
        footprint_bytes=24 * 1024 * 1024,
        footprint_budget_mode="baseline_plus",
        poll_seconds=0.01,
        term_grace_seconds=0.25,
        controlled_allocator="stdlib-dirty-bytearray-4mib-v1",
    )
    source = (
        "import time;chunks=[];"
        "exec(\"for _ in range(10):\\n chunks.append(bytearray(b'x'*(4*1024*1024)))\\n"
        " time.sleep(0.05)\\nwhile True:\\n time.sleep(1)\")"
    )

    result = receipt._run_bounded(  # pyright: ignore[reportPrivateUsage]
        [sys.executable, "-I", "-B", "-c", source],
        env={},
        cwd=None,
        profile=profile,
    )

    supervision = cast(dict[str, object], result.supervision)
    assert supervision["budget_mode"] == "baseline_plus"
    assert cast(int, supervision["observed_max_bytes"]) > cast(int, supervision["budget_bytes"])
    assert cast(int, supervision["overshoot_bytes"]) >= 0
    cleanup = cast(dict[str, bool], supervision["cleanup"])
    assert cleanup["sigterm_sent"] is True
    assert cleanup["waited"] is True
    assert cleanup["process_group_absent"] is True


@pytest.mark.parametrize(
    "failure_code", ["footprint_sampling_failed", "footprint_leader_identity_drift"]
)
def test_supervision_failure_is_closed_with_cleanup_receipt(
    monkeypatch: pytest.MonkeyPatch, failure_code: str
) -> None:
    receipt = _module()

    class Sampler:
        identity_calls = 0
        sample_calls = 0

        @property
        def identity(self) -> str:
            self.identity_calls += 1
            if failure_code == "footprint_leader_identity_drift" and self.identity_calls > 1:
                return "drifted-leader"
            return "bound-leader"

        def sample(self) -> int:
            self.sample_calls += 1
            if failure_code == "footprint_sampling_failed" and self.sample_calls > 1:
                raise receipt.ReceiptError(failure_code)
            return 1024

    monkeypatch.setattr(receipt, "_DarwinFootprintSampler", lambda _pid: Sampler())
    profile = receipt.BoundedProfile(
        wall_seconds=5.0,
        stdout_bytes=4096,
        stderr_bytes=4096,
        footprint_bytes=64 * 1024 * 1024,
        poll_seconds=0.01,
        term_grace_seconds=0.2,
    )

    with pytest.raises(receipt.ReceiptError, match=failure_code) as raised:
        receipt._run_bounded(  # pyright: ignore[reportPrivateUsage]
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(5)"],
            env={},
            cwd=None,
            profile=profile,
        )

    details = cast(dict[str, object], raised.value.details)
    assert details["budget_outcome"] == "supervision_failed"
    cleanup = cast(dict[str, bool], details["cleanup"])
    assert cleanup["waited"] is True
    assert cleanup["process_group_absent"] is True


_FIXTURE_AUTHORITY_DOCUMENT_SHA256 = (
    "533bc8a47ba89aeb86de0e7b944da2f1a3f1de8a5ba062b861a3aef854a87ccb"
)
_FIXTURE_SOURCE_SHA256 = "2e62303fbc08223d326b6faa3699bbbfdf0e0fca335101bdb7265b4988d11cb4"
_FIXTURE_IDENTITIES = {
    "direct-audio.m4a": (
        24_880,
        "cd7307b22b74de4fef8bda87582be791528c65d6546e4abdf42128070980e260",
        {
            "codec": "aac",
            "compatible_brands": "M4A isomiso2",
            "container_tokens": ["3g2", "3gp", "m4a", "mj2", "mov", "mp4"],
            "duration_us": 3_630_000,
            "layout": "mono",
            "major_brand": "M4A ",
            "media_type": "audio/mp4",
            "profile": "LC",
            "sample_rate": 16_000,
            "stream_count": 1,
        },
    ),
    "direct-audio.mp3": (
        22_509,
        "cc10ce7b07ae0ea8434b690383bb7ef0a43f7af66aec474d410e5a9612158631",
        {
            "codec": "mp3float",
            "container_tokens": ["mp3"],
            "duration_us": 3_630_000,
            "layout": "mono",
            "media_type": "audio/mpeg",
            "profile": "normalized-mpeg-layer-iii",
            "sample_rate": 16_000,
            "stream_count": 1,
        },
    ),
    "direct-audio.wav": (
        116_238,
        "ec82eefefc5a6ccbbfc757864fc94bffd250bf185b03fc0404568063c8f993ac",
        {
            "codec": "pcm_s16le",
            "container_tokens": ["wav"],
            "duration_us": 3_630_000,
            "layout": "mono",
            "media_type": "audio/wav",
            "profile": "pcm-s16le",
            "sample_rate": 16_000,
            "stream_count": 1,
        },
    ),
}


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def _generation_preflight_digest(evidence: dict[str, object]) -> str:
    projection = {
        "fixtures": sorted(
            cast(list[dict[str, object]], evidence["fixtures"]),
            key=lambda item: cast(str, item["filename"]),
        ),
        "wheel_inventory": sorted(
            cast(list[dict[str, object]], evidence["wheel_inventory"]),
            key=lambda item: cast(str, item["filename"]),
        ),
    }
    return _canonical_digest(projection)


def _refresh_preflight_digest(payload: dict[str, object]) -> None:
    observed = {
        key: value
        for key, value in payload.items()
        if key not in {"issues", "status", "gate", "observed_digest"}
    }
    payload["observed_digest"] = _canonical_digest(observed)


def _complete_preflight_payload(evidence: dict[str, object]) -> dict[str, object]:
    wheel_rows = cast(list[dict[str, object]], evidence["wheel_inventory"])
    fixture_rows = cast(list[dict[str, object]], evidence["fixtures"])
    digest = "9" * 64
    payload: dict[str, object] = {
        "schema": "mke.direct_audio_dependency_input_check.v1",
        "status": "passed",
        "gate": "inputs_valid",
        "distribution": {
            "external_binary_redistribution": "not_performed",
            "redistribution_authority": "not_claimed",
        },
        "controller": {
            "implementation": "cpython",
            "python_version": "3.13.9",
            "platform": "macosx-15.0-arm64",
            "executable_type": "regular",
            "executable_mode": "0755",
            "executable_sha256": digest,
        },
        "script": {"sha256": "8" * 64},
        "interpreters": [
            {
                "label": f"python-{version}",
                "implementation": "cpython",
                "python_version": f"{version}.9",
                "system": "Darwin",
                "machine": "arm64",
                "sysconfig_platform": "macosx-15.0-arm64",
                "soabi": f"cpython-{version.replace('.', '')}-darwin",
                "ext_suffix": f".cpython-{version.replace('.', '')}-darwin.so",
                "cache_tag": f"cpython-{version.replace('.', '')}",
                "abiflags": "",
                "pointer_bits": 64,
                "byteorder": "little",
                "executable_sha256": character * 64,
            }
            for version, character in (("3.12", "6"), ("3.13", "7"))
        ],
        "lock_sha256": "5" * 64,
        "constraints_sha256": "4" * 64,
        "wheelhouse": [
            {
                **item,
                "bytes": index + 100,
                "build": None,
                "python_tags": ["cp312" if index == 0 else "cp313"],
                "abi_tags": ["cp312" if index == 0 else "cp313"],
                "platform_tags": ["macosx_11_0_arm64"],
            }
            for index, item in enumerate(wheel_rows)
        ],
        "fixtures": [
            {
                "filename": item["filename"],
                "bytes": item["bytes"],
                "sha256": item["sha256"],
                "artifact_scope": item["artifact_scope"],
            }
            for item in fixture_rows
        ],
        "issues": [],
        "observed_digest": "",
    }
    _refresh_preflight_digest(payload)
    return payload


def _complete_generation_bundle() -> tuple[
    dict[str, object], dict[str, object], dict[str, object]
]:
    evidence = _complete_generation_evidence()
    preflight = _complete_preflight_payload(evidence)
    generation_preflight = _complete_preflight_payload(evidence)
    evidence["preflight_observed_digest"] = preflight["observed_digest"]
    evidence["generation_preflight_observed_digest"] = generation_preflight["observed_digest"]
    return evidence, preflight, generation_preflight


def _complete_generation_evidence() -> dict[str, object]:
    digest = "a" * 64
    digest_313 = "c" * 64
    evidence: dict[str, object] = {
        "preflight_observed_digest": "",
        "generation_preflight_observed_digest": "",
        "external_binary_redistribution": "not_performed",
        "redistribution_authority": "not_claimed",
        "wheel_inventory": [
            {
                "filename": "av-17.0-cp312.whl",
                "distribution": "av",
                "version": "17.0",
                "sha256": digest,
                "artifact_scope": "local_runtime_only",
            },
            {
                "filename": "av-17.0-cp313.whl",
                "distribution": "av",
                "version": "17.0",
                "sha256": digest_313,
                "artifact_scope": "local_runtime_only",
            },
        ],
        "installed_distributions": [
            {
                "distribution": "av",
                "version": "17.0",
                "source_wheel_sha256": digest,
                "cell": "3.12",
                "artifact_scope": "local_runtime_only",
            },
            {
                "distribution": "av",
                "version": "17.0",
                "source_wheel_sha256": digest_313,
                "cell": "3.13",
                "artifact_scope": "local_runtime_only",
            },
        ],
        "pyav": {
            "distribution": "av",
            "version": "17.0",
            "artifact_scope": "local_runtime_only",
            "extensions": [{"filename": "av/_core.so", "sha256": digest}],
            "linked_components": ["libavcodec"],
            "bundled_components": [],
        },
        "ffmpeg_runtime": {
            "license": "LGPL version 2.1 or later",
            "configuration": "--enable-shared",
            "configuration_sha256": digest,
            "sha256": digest,
            "source_reference": "ffmpeg-runtime-version-output",
            "license_text_sha256": digest,
            "artifact_scope": "local_runtime_only",
        },
        "direct_components": [
            {
                "name": "libavcodec",
                "version": "61",
                "license": "LGPL-2.1-or-later",
                "evidence_sha256": digest,
                "source_reference": "pyav-linked-library-inventory",
                "license_text_sha256": digest,
                "artifact_scope": "local_runtime_only",
                "local_use_restriction": "none_observed",
            }
        ],
        "fixtures": [
            {
                "filename": name,
                "sha256": fixture_sha256,
                "redistribution": "permitted",
                "artifact_scope": "repository_distributed",
                "bytes": fixture_bytes,
                "source": "repository-authored-synthetic-speech",
                "recipe_sha256": _FIXTURE_AUTHORITY_DOCUMENT_SHA256,
                "license": "Flite",
                "license_evidence_sha256": _FIXTURE_AUTHORITY_DOCUMENT_SHA256,
                "source_sha256": _FIXTURE_SOURCE_SHA256,
                "required_notice": "included",
                "notice_evidence_sha256": _FIXTURE_AUTHORITY_DOCUMENT_SHA256,
                "redistribution_basis": "documented_source_license_and_recipe",
                "redistribution_evidence_sha256": _FIXTURE_AUTHORITY_DOCUMENT_SHA256,
                "profile_sha256": _canonical_digest(profile),
                "authority_document_sha256": _FIXTURE_AUTHORITY_DOCUMENT_SHA256,
            }
            for name, (fixture_bytes, fixture_sha256, profile) in _FIXTURE_IDENTITIES.items()
        ],
        "unresolved_transitive_binary_items": [
            {
                "name": "system-runtime",
                "version": "1",
                "identity_sha256": digest,
                "redistribution_clearance": "unresolved",
                "local_use_restriction": "none_observed",
                "artifact_scope": "local_runtime_only",
            }
        ],
    }
    preflight_digest = _generation_preflight_digest(evidence)
    evidence["preflight_observed_digest"] = preflight_digest
    evidence["generation_preflight_observed_digest"] = preflight_digest
    return evidence


def test_generation_rejects_partial_projection_as_preflight_authority() -> None:
    receipt = _module()
    evidence = _complete_generation_evidence()

    assert receipt.validate_generation_evidence(evidence) == {
        "failure": "generation_evidence_invalid",
        "status": "failed",
    }


def test_local_optional_use_allows_recorded_unresolved_transitive_items() -> None:
    receipt = _module()
    evidence, preflight, generation_preflight = _complete_generation_bundle()

    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {
        "external_binary_redistribution": "not_performed",
        "redistribution_authority": "not_claimed",
        "status": "passed",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "failed_status",
        "nonempty_issues",
        "observed_digest_tamper",
        "controller_drift_without_rehash",
        "unknown_preflight_field",
        "wheel_projection_drift",
        "fixture_projection_drift",
        "generation_full_preflight_drift",
    ],
)
def test_generation_evidence_requires_full_passed_preflight_authority(mutation: str) -> None:
    receipt = _module()
    evidence, preflight, generation_preflight = _complete_generation_bundle()
    if mutation == "failed_status":
        preflight["status"] = "failed"
    elif mutation == "nonempty_issues":
        preflight["gate"] = "input_validation_failed"
        preflight["issues"] = [{"code": "wheel_missing", "subject": "external-wheelhouse"}]
    elif mutation == "observed_digest_tamper":
        preflight["observed_digest"] = "f" * 64
    elif mutation == "controller_drift_without_rehash":
        cast(dict[str, object], preflight["controller"])["python_version"] = "3.12.0"
    elif mutation == "unknown_preflight_field":
        preflight["private_path"] = "/Users/operator/private"
        _refresh_preflight_digest(preflight)
        evidence["preflight_observed_digest"] = preflight["observed_digest"]
    elif mutation == "wheel_projection_drift":
        for payload in (preflight, generation_preflight):
            cast(list[dict[str, object]], payload["wheelhouse"])[0]["sha256"] = "d" * 64
            _refresh_preflight_digest(payload)
        evidence["preflight_observed_digest"] = preflight["observed_digest"]
        evidence["generation_preflight_observed_digest"] = generation_preflight[
            "observed_digest"
        ]
    elif mutation == "fixture_projection_drift":
        for payload in (preflight, generation_preflight):
            cast(list[dict[str, object]], payload["fixtures"])[0]["bytes"] = 1
            _refresh_preflight_digest(payload)
        evidence["preflight_observed_digest"] = preflight["observed_digest"]
        evidence["generation_preflight_observed_digest"] = generation_preflight[
            "observed_digest"
        ]
    else:
        cast(dict[str, object], generation_preflight["controller"])["python_version"] = "3.13.10"
        _refresh_preflight_digest(generation_preflight)
        evidence["generation_preflight_observed_digest"] = generation_preflight[
            "observed_digest"
        ]

    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {
        "failure": "generation_evidence_invalid",
        "status": "failed",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "private_component_name",
        "private_unresolved_name",
        "hostname_unresolved_version",
        "private_ffmpeg_configuration",
        "private_ffmpeg_license",
        "hostname_ffmpeg_license",
        "invalid_ffmpeg_configuration_digest",
        "duplicate_ffmpeg_configuration_token",
        "noncanonical_ffmpeg_configuration_order",
        "private_direct_license",
        "absolute_extension_filename",
        "parent_extension_filename",
    ],
)
def test_generation_evidence_rejects_private_or_noncanonical_field_grammar(
    mutation: str,
) -> None:
    receipt = _module()
    evidence, preflight, generation_preflight = _complete_generation_bundle()
    pyav = cast(dict[str, object], evidence["pyav"])
    direct = cast(list[dict[str, object]], evidence["direct_components"])
    unresolved = cast(list[dict[str, object]], evidence["unresolved_transitive_binary_items"])
    ffmpeg = cast(dict[str, object], evidence["ffmpeg_runtime"])
    if mutation == "private_component_name":
        private_name = "/Users/operator/private/libavcodec.dylib"
        pyav["linked_components"] = [private_name]
        direct[0]["name"] = private_name
    elif mutation == "private_unresolved_name":
        unresolved[0]["name"] = "/Users/operator/private/libfoo.dylib"
    elif mutation == "hostname_unresolved_version":
        unresolved[0]["version"] = "build-host.internal"
    elif mutation == "private_ffmpeg_configuration":
        ffmpeg["configuration"] = "--prefix=/Users/operator/private/build"
    elif mutation == "private_ffmpeg_license":
        ffmpeg["license"] = "/Users/operator/private/LICENSE"
    elif mutation == "hostname_ffmpeg_license":
        ffmpeg["license"] = "build-host.internal"
    elif mutation == "invalid_ffmpeg_configuration_digest":
        ffmpeg["configuration_sha256"] = "invalid"
    elif mutation == "duplicate_ffmpeg_configuration_token":
        ffmpeg["configuration"] = "--enable-shared --enable-shared"
    elif mutation == "noncanonical_ffmpeg_configuration_order":
        ffmpeg["configuration"] = "--enable-shared --enable-gpl"
    elif mutation == "private_direct_license":
        direct[0]["license"] = "/Users/operator/private/LICENSE"
    elif mutation == "absolute_extension_filename":
        cast(list[dict[str, object]], pyav["extensions"])[0]["filename"] = (
            "/Users/operator/private/av/_core.so"
        )
    else:
        cast(list[dict[str, object]], pyav["extensions"])[0]["filename"] = "av/../_core.so"

    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {
        "failure": "generation_evidence_invalid",
        "status": "failed",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_fixture",
        "duplicate_direct_component",
        "duplicate_direct_component_name",
        "duplicate_unresolved_transitive",
        "duplicate_unresolved_transitive_name",
        "duplicate_linked_component",
        "linked_bundled_overlap",
        "absolute_direct_source_reference",
        "hostname_ffmpeg_source_reference",
        "absolute_fixture_source_reference",
        "fixture_bytes_drift",
        "fixture_sha256_drift",
        "fixture_profile_drift",
        "fixture_license_evidence_drift",
        "fixture_notice_evidence_drift",
        "fixture_authority_document_drift",
        "arbitrary_preflight_digest",
    ],
)
def test_generation_evidence_rejects_noncanonical_inventory_mutations(mutation: str) -> None:
    receipt = _module()
    evidence, preflight, generation_preflight = _complete_generation_bundle()
    fixtures = cast(list[dict[str, object]], evidence["fixtures"])
    direct = cast(list[dict[str, object]], evidence["direct_components"])
    unresolved = cast(list[dict[str, object]], evidence["unresolved_transitive_binary_items"])
    pyav = cast(dict[str, object], evidence["pyav"])
    ffmpeg = cast(dict[str, object], evidence["ffmpeg_runtime"])
    if mutation == "duplicate_fixture":
        fixtures.append(dict(fixtures[0]))
    elif mutation == "duplicate_direct_component":
        direct.append(dict(direct[0]))
    elif mutation == "duplicate_direct_component_name":
        duplicate = dict(direct[0])
        duplicate["version"] = "62"
        direct.append(duplicate)
    elif mutation == "duplicate_unresolved_transitive":
        unresolved.append(dict(unresolved[0]))
    elif mutation == "duplicate_unresolved_transitive_name":
        duplicate = dict(unresolved[0])
        duplicate["version"] = "2"
        duplicate["identity_sha256"] = "d" * 64
        unresolved.append(duplicate)
    elif mutation == "duplicate_linked_component":
        cast(list[str], pyav["linked_components"]).append("libavcodec")
    elif mutation == "linked_bundled_overlap":
        cast(list[str], pyav["bundled_components"]).append("libavcodec")
    elif mutation == "absolute_direct_source_reference":
        direct[0]["source_reference"] = "/Users/operator/private-evidence"
    elif mutation == "hostname_ffmpeg_source_reference":
        ffmpeg["source_reference"] = "build-host.internal"
    elif mutation == "absolute_fixture_source_reference":
        fixtures[0]["source"] = "/private/local/generated-audio"
    elif mutation == "fixture_bytes_drift":
        fixtures[0]["bytes"] = cast(int, fixtures[0]["bytes"]) + 1
    elif mutation == "fixture_sha256_drift":
        fixtures[0]["sha256"] = "d" * 64
    elif mutation == "fixture_profile_drift":
        fixtures[0]["profile_sha256"] = "e" * 64
    elif mutation == "fixture_license_evidence_drift":
        fixtures[0]["license_evidence_sha256"] = "e" * 64
    elif mutation == "fixture_notice_evidence_drift":
        fixtures[0]["notice_evidence_sha256"] = "e" * 64
    elif mutation == "fixture_authority_document_drift":
        fixtures[0]["authority_document_sha256"] = "e" * 64
    else:
        evidence["preflight_observed_digest"] = "f" * 64
        evidence["generation_preflight_observed_digest"] = "f" * 64
    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {
        "failure": "generation_evidence_invalid",
        "status": "failed",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "distribution_claim",
        "fixture",
        "inventory",
        "direct_evidence",
        "preflight_drift",
        "boundary_escape",
        "unknown_field",
        "unresolved_identity",
        "local_use_restriction",
        "ffmpeg_unknown_license",
        "ffmpeg_unobservable_configuration",
        "direct_unresolved_version",
        "direct_source_reference",
        "direct_license_reference",
        "fixture_redistribution_basis",
        "fixture_redistribution_evidence",
        "fixture_profile",
    ],
)
def test_generation_evidence_fails_closed_for_authority_drift(mutation: str) -> None:
    receipt = _module()
    evidence, preflight, generation_preflight = _complete_generation_bundle()
    if mutation == "distribution_claim":
        evidence["external_binary_redistribution"] = "performed"
    elif mutation == "fixture":
        cast(list[dict[str, object]], evidence["fixtures"])[0]["redistribution"] = "unknown"
    elif mutation == "inventory":
        cast(list[dict[str, object]], evidence["installed_distributions"])[0]["version"] = "18.0"
    elif mutation == "direct_evidence":
        cast(list[dict[str, object]], evidence["direct_components"])[0]["evidence_sha256"] = "bad"
    elif mutation == "preflight_drift":
        evidence["generation_preflight_observed_digest"] = "c" * 64
    elif mutation == "boundary_escape":
        cast(list[dict[str, object]], evidence["wheel_inventory"])[0]["artifact_scope"] = (
            "repository_distributed"
        )
    elif mutation == "unknown_field":
        cast(dict[str, object], evidence["pyav"])["claim"] = "inferred redistribution"
    elif mutation == "unresolved_identity":
        cast(list[dict[str, object]], evidence["unresolved_transitive_binary_items"])[0][
            "identity_sha256"
        ] = "unknown"
    elif mutation == "local_use_restriction":
        cast(list[dict[str, object]], evidence["direct_components"])[0]["local_use_restriction"] = (
            "restricted"
        )
    elif mutation == "ffmpeg_unknown_license":
        cast(dict[str, object], evidence["ffmpeg_runtime"])["license"] = "unknown"
    elif mutation == "ffmpeg_unobservable_configuration":
        cast(dict[str, object], evidence["ffmpeg_runtime"])["configuration"] = "unobservable"
    elif mutation == "direct_unresolved_version":
        cast(list[dict[str, object]], evidence["direct_components"])[0]["version"] = "unresolved"
    elif mutation == "direct_source_reference":
        cast(list[dict[str, object]], evidence["direct_components"])[0]["source_reference"] = (
            "unknown"
        )
    elif mutation == "direct_license_reference":
        cast(list[dict[str, object]], evidence["direct_components"])[0]["license_text_sha256"] = (
            "invalid"
        )
    elif mutation == "fixture_redistribution_basis":
        cast(list[dict[str, object]], evidence["fixtures"])[0]["redistribution_basis"] = "unknown"
    elif mutation == "fixture_redistribution_evidence":
        cast(list[dict[str, object]], evidence["fixtures"])[0]["redistribution_evidence_sha256"] = (
            "invalid"
        )
    else:
        cast(list[dict[str, object]], evidence["fixtures"])[0]["profile_sha256"] = "invalid"

    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {
        "failure": "generation_evidence_invalid",
        "status": "failed",
    }


def test_generation_cli_without_authorized_inputs_keeps_acquisition_gate(
    capsys: pytest.CaptureFixture[str],
) -> None:
    receipt = _module()

    assert (
        receipt.main(
            [
                "--python",
                sys.executable,
                "--python",
                sys.executable,
                "--wheelhouse",
                "missing",
                "--lock",
                "uv.lock",
                "--constraints",
                "missing",
                "--fixture-root",
                "missing",
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out) == {
        "failure": "acquisition_authorization_required",
        "status": "failed",
    }
