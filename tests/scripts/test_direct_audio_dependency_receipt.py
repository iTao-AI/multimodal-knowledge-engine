# Dynamic monkeypatch targets come from the stdlib-only script module loaded at runtime.
# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

import hashlib
import importlib.metadata
import io
import json
import os
import platform
import stat
import subprocess
import sys
import sysconfig
import types
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


def _freeze_synthetic_darwin_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_module(), "_supported_cells", _cells)


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


def test_projection_includes_candidate_core_and_requested_dependency_extras(
    tmp_path: Path,
) -> None:
    receipt = _module()
    lock = tmp_path / "uv.lock"
    digest = "a" * 64
    lock.write_text(
        "version = 1\n"
        'requires-python = ">=3.12, <3.14"\n'
        "[[package]]\n"
        'name = "cryptography"\n'
        'version = "49.0.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://files.pythonhosted.org/cryptography-49.0.0-'
        'cp311-abi3-macosx_11_0_arm64.whl", hash = "sha256:'
        f'{digest}", size = 1 }}]\n'
        "[[package]]\n"
        'name = "demo"\n'
        'version = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://files.pythonhosted.org/demo-1.0-py3-none-any.whl", '
        f'hash = "sha256:{digest}", size = 1 }}]\n'
        "[[package]]\n"
        'name = "mcp"\n'
        'version = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'dependencies = [{ name = "pyjwt", extra = ["crypto"] }]\n'
        'wheels = [{ url = "https://files.pythonhosted.org/mcp-1.0-py3-none-any.whl", '
        f'hash = "sha256:{digest}", size = 1 }}]\n'
        "[[package]]\n"
        'name = "multimodal-knowledge-engine"\n'
        'version = "0.1.3"\n'
        'source = { editable = "." }\n'
        'dependencies = [{ name = "mcp" }]\n'
        "[package.optional-dependencies]\n"
        'transcription = [{ name = "demo" }]\n'
        "[[package]]\n"
        'name = "pyjwt"\n'
        'version = "2.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://files.pythonhosted.org/pyjwt-2.0-py3-none-any.whl", '
        f'hash = "sha256:{digest}", size = 1 }}]\n'
        "[package.optional-dependencies]\n"
        'crypto = [{ name = "cryptography" }]\n',
        encoding="utf-8",
    )

    projection = receipt.derive_transcription_projection(lock, _cells())

    assert {item.name for item in projection.requirements} == {
        "cryptography",
        "demo",
        "mcp",
        "pyjwt",
    }


def test_projection_selects_one_highest_priority_abi3_wheel_per_cell(
    tmp_path: Path,
) -> None:
    receipt = _module()
    lock = tmp_path / "uv.lock"
    lock.write_text(
        "version = 1\n"
        'requires-python = ">=3.12, <3.14"\n'
        "[[package]]\n"
        'name = "cryptography"\n'
        'version = "49.0.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        "wheels = [\n"
        '  { url = "https://files.pythonhosted.org/cryptography-49.0.0-'
        'cp311-abi3-macosx_11_0_arm64.whl", hash = "sha256:'
        + "a" * 64
        + '", size = 11 },\n'
        '  { url = "https://files.pythonhosted.org/cryptography-49.0.0-'
        'cp39-abi3-macosx_11_0_arm64.whl", hash = "sha256:'
        + "b" * 64
        + '", size = 9 },\n'
        "]\n"
        "[[package]]\n"
        'name = "multimodal-knowledge-engine"\n'
        'version = "0.1.3"\n'
        'source = { editable = "." }\n'
        "[package.optional-dependencies]\n"
        'transcription = [{ name = "cryptography" }]\n',
        encoding="utf-8",
    )

    projection = receipt.derive_transcription_projection(lock, _cells())

    assert [item.filename for item in projection.locked_wheels] == [
        "cryptography-49.0.0-cp311-abi3-macosx_11_0_arm64.whl"
    ]


def test_projection_renders_prefix_distribution_names_in_canonical_line_order(
    tmp_path: Path,
) -> None:
    receipt = _module()
    lock = tmp_path / "uv.lock"
    digest = "a" * 64
    lock.write_text(
        "version = 1\n"
        'requires-python = ">=3.12, <3.14"\n'
        "[[package]]\n"
        'name = "httpx"\nversion = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://example.invalid/httpx-1.0-py3-none-any.whl", '
        f'hash = "sha256:{digest}", size = 1 }}]\n'
        "[[package]]\n"
        'name = "httpx-sse"\nversion = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://example.invalid/httpx_sse-1.0-py3-none-any.whl", '
        f'hash = "sha256:{digest}", size = 1 }}]\n'
        "[[package]]\n"
        'name = "multimodal-knowledge-engine"\nversion = "0.1.3"\n'
        'source = { editable = "." }\n'
        'dependencies = [{ name = "httpx" }]\n'
        "[package.optional-dependencies]\n"
        'transcription = [{ name = "httpx-sse" }]\n',
        encoding="utf-8",
    )

    projection = receipt.derive_transcription_projection(lock, _cells())

    parsed, _, by_cell = receipt._parse_constraints(  # pyright: ignore[reportPrivateUsage]
        projection.constraints
    )
    assert parsed == projection.requirements
    assert by_cell == projection.requirements_by_cell


def _copy_audio_fixture_root(tmp_path: Path) -> Path:
    source = Path(__file__).parents[1] / "fixtures" / "audio"
    target = tmp_path / "audio-fixtures"
    target.mkdir()
    for name in ("README.md", "direct-audio.m4a", "direct-audio.mp3", "direct-audio.wav"):
        (target / name).write_bytes((source / name).read_bytes())
    return target


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
transcription = [{ name = "faster-whisper" }]
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


def test_lock_projection_supports_platform_python_implementation_marker(
    tmp_path: Path,
) -> None:
    receipt = _module()
    digest = "a" * 64
    lock = tmp_path / "uv.lock"
    lock.write_text(
        "version = 1\n"
        'requires-python = ">=3.12, <3.14"\n'
        "[[package]]\n"
        'name = "demo"\n'
        'version = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://example.invalid/demo-1.0-py3-none-any.whl", '
        f'hash = "sha256:{digest}", size = 1 }}]\n'
        "[[package]]\n"
        'name = "multimodal-knowledge-engine"\n'
        'version = "0.1.3"\n'
        'source = { editable = "." }\n'
        "[package.optional-dependencies]\n"
        'transcription = [{ name = "demo", '
        "marker = \"platform_python_implementation == 'CPython'\" }]\n",
        encoding="utf-8",
    )

    projection = receipt.derive_transcription_projection(lock, _cells())

    assert [(item.name, item.version) for item in projection.requirements] == [("demo", "1.0")]


def test_lock_projection_rejects_unknown_marker_variable_with_closed_error(
    tmp_path: Path,
) -> None:
    receipt = _module()
    digest = "a" * 64
    lock = tmp_path / "uv.lock"
    lock.write_text(
        "version = 1\n"
        'requires-python = ">=3.12, <3.14"\n'
        "[[package]]\n"
        'name = "demo"\n'
        'version = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://example.invalid/demo-1.0-py3-none-any.whl", '
        f'hash = "sha256:{digest}", size = 1 }}]\n'
        "[[package]]\n"
        'name = "multimodal-knowledge-engine"\n'
        'version = "0.1.3"\n'
        'source = { editable = "." }\n'
        "[package.optional-dependencies]\n"
        'transcription = [{ name = "demo", marker = "os_name == \'posix\'" }]\n',
        encoding="utf-8",
    )

    with pytest.raises(receipt.ReceiptError, match="^lock_projection_invalid$"):
        receipt.derive_transcription_projection(lock, _cells())


@pytest.mark.parametrize(
    "lock_text",
    [
        'version = 1\npackage = ["not-a-mapping"]\n',
        "version = 1\n[[package]]\nname = []\n",
        (
            'version = 1\n[[package]]\nname = "multimodal-knowledge-engine"\n'
            'source = { editable = "." }\n[package.optional-dependencies]\n'
            'transcription = "not-a-list"\n'
        ),
    ],
)
def test_malformed_lock_types_have_one_closed_projection_error(
    tmp_path: Path, lock_text: str
) -> None:
    receipt = _module()
    lock = tmp_path / "uv.lock"
    lock.write_text(lock_text, encoding="utf-8")

    with pytest.raises(receipt.ReceiptError, match="^lock_projection_invalid$"):
        receipt.derive_transcription_projection(lock, _cells())


def test_lock_wheel_authority_rejects_incompatible_hash_renamed_as_darwin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _module()
    _freeze_synthetic_darwin_cells(monkeypatch)
    linux_bytes = b"linux-wheel"
    darwin_bytes = b"darwin-wheel"
    linux_digest = hashlib.sha256(linux_bytes).hexdigest()
    darwin_digest = hashlib.sha256(darwin_bytes).hexdigest()
    lock = tmp_path / "uv.lock"
    lock.write_text(
        "version = 1\n"
        'requires-python = ">=3.12, <3.14"\n'
        "[[package]]\n"
        'name = "demo"\n'
        'version = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        "wheels = [\n"
        '  { url = "https://example.invalid/demo-1.0-cp311-abi3-macosx_11_0_arm64.whl", '
        f'hash = "sha256:{darwin_digest}", size = {len(darwin_bytes)} }},\n'
        '  { url = "https://example.invalid/demo-1.0-cp311-abi3-manylinux_2_28_aarch64.whl", '
        f'hash = "sha256:{linux_digest}", size = {len(linux_bytes)} }},\n'
        "]\n"
        "[[package]]\n"
        'name = "multimodal-knowledge-engine"\n'
        'version = "0.1.3"\n'
        'source = { editable = "." }\n'
        "[package.optional-dependencies]\n"
        'transcription = [{ name = "demo" }]\n',
        encoding="utf-8",
    )
    constraints = tmp_path / "constraints.txt"
    constraints.write_bytes(receipt.derive_transcription_projection(lock, _cells()).constraints)
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _wheel(
        wheelhouse,
        "demo-1.0-cp311-abi3-macosx_11_0_arm64.whl",
        linux_bytes,
    )
    fixtures = _copy_audio_fixture_root(tmp_path)

    result = receipt.check_inputs(
        pythons=(),
        wheelhouse=wheelhouse,
        lock_path=lock,
        constraints=constraints,
        fixture_root=fixtures,
    )

    assert "wheel_substituted" in {
        item["code"] for item in cast(list[dict[str, str]], result["issues"])
    }


def test_lock_projection_and_resolution_are_exact_per_python_cell(tmp_path: Path) -> None:
    receipt = _module()
    lock = tmp_path / "uv.lock"
    digest = "a" * 64
    root_wheel = (
        '{ url = "https://example.invalid/root_demo-1.0-py3-none-any.whl", '
        f'hash = "sha256:{digest}", size = 1 }}'
    )
    only_wheel = (
        '{ url = "https://example.invalid/only_312-1.0-cp312-cp312-macosx_11_0_arm64.whl", '
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
    wheels = [ROOT_WHEEL]
[[package]]
name = "only-312"
version = "1.0"
source = { registry = "https://pypi.org/simple" }
    wheels = [ONLY_WHEEL]
[[package]]
name = "multimodal-knowledge-engine"
version = "0.1.3"
source = { editable = "." }
[package.optional-dependencies]
transcription = [{ name = "root-demo" }]
    """.strip()
        .replace("ROOT_WHEEL", root_wheel)
        .replace("ONLY_WHEEL", only_wheel)
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
        'wheels = [{ url = "https://example.invalid/root_demo-1.0-py3-none-any.whl", '
        f'hash = "sha256:{root_digest}", size = {root.stat().st_size} }}]\n'
        '[[package]]\nname = "only-312"\nversion = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://example.invalid/'
        'only_312-1.0-cp312-cp312-macosx_11_0_arm64.whl", '
        f'hash = "sha256:{only_digest}", size = {only.stat().st_size} }}]\n'
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


def _nested_pip_case(tmp_path: Path) -> dict[str, object]:
    receipt = _module()
    python = tmp_path / "operator-python"
    python.write_bytes(b"approved-python")
    python.chmod(0o700)
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _wheel(wheelhouse, "demo-1.0-py3-none-any.whl", b"wheel-bytes")
    constraints = tmp_path / "constraints.txt"
    requirements = tmp_path / "requirements.txt"
    constraints.write_bytes(b"demo==1.0 --hash=sha256:" + b"a" * 64 + b"\n")
    requirements.write_bytes(constraints.read_bytes())
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    snapshot = receipt._snapshot_executable(python)  # pyright: ignore[reportPrivateUsage]
    public = {
        "label": "python-3.12",
        "python_version": "3.12.9",
        "executable_sha256": snapshot.sha256,
    }
    return {
        "python": python,
        "wheelhouse": wheelhouse,
        "constraints": constraints,
        "requirements": requirements,
        "runtime_root": runtime_root,
        "manifest": receipt.build_wheelhouse_manifest(wheelhouse),
        "public": public,
        "identity": snapshot.identity,
    }


def _install_fake_nested_pip_runtime(
    monkeypatch: pytest.MonkeyPatch,
    case: dict[str, object],
    *,
    venv_alias: bool = False,
    venv_hardlink: bool = False,
    site_packages_alias: Path | None = None,
    install_mutation: object | None = None,
) -> list[dict[str, object]]:
    receipt = _module()
    python = cast(Path, case["python"])
    public = cast(dict[str, object], case["public"])
    calls: list[dict[str, object]] = []

    def probe(path: Path, _cell: object):
        snapshot = receipt._snapshot_executable(path)  # pyright: ignore[reportPrivateUsage]
        return dict(public), snapshot.identity, snapshot.resolved

    def runner(argv: list[str], **kwargs: object):
        calls.append({"argv": list(argv), **kwargs})
        if argv[1:5] == ["-I", "-B", "-m", "venv"]:
            venv = Path(argv[-1])
            target = venv / "bin" / "python3.12"
            target.parent.mkdir(parents=True)
            if venv_alias:
                target.symlink_to(python)
            elif venv_hardlink:
                os.link(python, target)
            else:
                target.write_bytes(python.read_bytes())
                target.chmod(0o700)
            python_lib = venv / "lib" / "python3.12"
            python_lib.mkdir(parents=True)
            site_packages = python_lib / "site-packages"
            if site_packages_alias is None:
                site_packages.mkdir()
            else:
                site_packages.symlink_to(site_packages_alias, target_is_directory=True)
            (venv / "pyvenv.cfg").write_text(
                "include-system-site-packages = false\nversion = 3.12.9\n",
                encoding="utf-8",
            )
        elif "install" in argv and callable(install_mutation):
            install_mutation(argv)
        return receipt.BoundedRunResult(0, b"", b"", None)

    monkeypatch.setattr(receipt, "_probe_target_interpreter", probe)
    monkeypatch.setattr(receipt, "_run_bounded", runner)
    return calls


def _run_nested_case(case: dict[str, object]) -> dict[str, object]:
    receipt = _module()
    constraints = cast(Path, case["constraints"])
    requirements = cast(Path, case["requirements"])
    return receipt.run_nested_pip_install(
        python=cast(Path, case["python"]),
        wheelhouse=cast(Path, case["wheelhouse"]),
        constraints=constraints,
        root_requirements=requirements,
        expected_manifest=cast(tuple[Any, ...], case["manifest"]),
        constraints_sha256=hashlib.sha256(constraints.read_bytes()).hexdigest(),
        root_requirements_sha256=hashlib.sha256(requirements.read_bytes()).hexdigest(),
        runtime_root=cast(Path, case["runtime_root"]),
        cell=_cells()[0],
        preflight_interpreter=cast(dict[str, object], case["public"]),
        preflight_file_identity=cast(tuple[int, ...], case["identity"]),
    )


def test_nested_pip_uses_exclusive_staging_and_call_owned_venv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _nested_pip_case(tmp_path)
    calls = _install_fake_nested_pip_runtime(monkeypatch, case)
    monkeypatch.setenv("PIP_INDEX_URL", "https://credential.invalid/simple")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid")

    result = _run_nested_case(case)

    assert result["cell"] == "3.12"
    assert result["pip_install"] == "passed"
    assert result["pip_check"] == "passed"
    assert result["cleanup"] == "passed"
    assert result["argv"] == [
        "call-owned-venv-python",
        "-I",
        "-m",
        "pip",
        "--isolated",
        "--disable-pip-version-check",
        "--no-input",
        "install",
        "--no-index",
        "--find-links",
        "call-owned-wheelhouse-uri",
        "--only-binary=:all:",
        "--no-cache-dir",
        "--require-hashes",
        "--constraint",
        "call-owned-constraints",
        "--requirement",
        "call-owned-root-requirements",
    ]
    assert result["environment"] == {
        "HOME": "call-owned-home",
        "PIP_CONFIG_FILE": "platform-null",
        "TMPDIR": "call-owned-temp",
    }
    assert len(calls) == 4
    creator = cast(list[str], calls[0]["argv"])
    assert creator[:5] == [
        str(cast(Path, case["python"]).resolve()),
        "-I",
        "-B",
        "-m",
        "venv",
    ]
    assert creator[-2] == "--copies"
    assert "--without-pip" in creator
    ensurepip = cast(list[str], calls[1]["argv"])
    assert ensurepip[1:] == [
        "-I",
        "-B",
        "-m",
        "ensurepip",
        "--upgrade",
        "--default-pip",
    ]
    install = cast(list[str], calls[2]["argv"])
    check = cast(list[str], calls[3]["argv"])
    runtime_root = cast(Path, case["runtime_root"])
    call_root = Path(creator[-1]).parent
    assert call_root.parent == runtime_root.resolve()
    assert install[0].startswith(str(call_root / "venv" / "bin"))
    assert install[0] != str(cast(Path, case["python"]).resolve())
    assert check[-1] == "check"
    assert check[0] == install[0]
    assert str(cast(Path, case["wheelhouse"]).resolve()) not in json.dumps(calls, default=str)
    assert str(cast(Path, case["constraints"]).resolve()) not in json.dumps(calls, default=str)
    assert list(runtime_root.iterdir()) == []
    assert cast(Path, case["python"]).read_bytes() == b"approved-python"
    rendered = json.dumps(calls, default=str)
    for forbidden in ("PIP_INDEX_URL", "HTTPS_PROXY", "credential.invalid", "proxy.invalid"):
        assert forbidden not in rendered


def test_nested_pip_collects_runtime_evidence_before_call_owned_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    case = _nested_pip_case(tmp_path)
    _install_fake_nested_pip_runtime(monkeypatch, case)
    fixtures = _copy_audio_fixture_root(tmp_path)
    observed: dict[str, object] = {}

    def collect(**kwargs: object) -> dict[str, object]:
        python = cast(Path, kwargs["python"])
        observed.update(kwargs)
        observed["venv_exists_during_probe"] = python.exists()
        return {"schema": "mke.direct_audio_runtime_evidence.v1"}

    monkeypatch.setattr(receipt, "_collect_runtime_evidence", collect)
    constraints = cast(Path, case["constraints"])
    requirements = cast(Path, case["requirements"])
    result = receipt.run_nested_pip_install(
        python=cast(Path, case["python"]),
        wheelhouse=cast(Path, case["wheelhouse"]),
        constraints=constraints,
        root_requirements=requirements,
        expected_manifest=cast(tuple[Any, ...], case["manifest"]),
        constraints_sha256=hashlib.sha256(constraints.read_bytes()).hexdigest(),
        root_requirements_sha256=hashlib.sha256(requirements.read_bytes()).hexdigest(),
        runtime_root=cast(Path, case["runtime_root"]),
        cell=_cells()[0],
        preflight_interpreter=cast(dict[str, object], case["public"]),
        preflight_file_identity=cast(tuple[int, ...], case["identity"]),
        fixture_root=fixtures,
        requirements=(receipt.Requirement("demo", "1.0"),),
    )

    assert result["runtime_evidence"] == {
        "schema": "mke.direct_audio_runtime_evidence.v1"
    }
    assert observed["venv_exists_during_probe"] is True
    assert observed["fixture_root"] == fixtures
    assert list(cast(Path, case["runtime_root"]).iterdir()) == []


def test_nested_pip_rejects_venv_alias_to_operator_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _nested_pip_case(tmp_path)
    calls = _install_fake_nested_pip_runtime(monkeypatch, case, venv_alias=True)

    with pytest.raises(_module().ReceiptError, match="^pip_venv_invalid$"):
        _run_nested_case(case)

    assert len(calls) == 1
    assert list(cast(Path, case["runtime_root"]).iterdir()) == []
    assert cast(Path, case["python"]).read_bytes() == b"approved-python"


def test_nested_pip_rejects_venv_hardlink_to_operator_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _nested_pip_case(tmp_path)
    calls = _install_fake_nested_pip_runtime(monkeypatch, case, venv_hardlink=True)

    with pytest.raises(_module().ReceiptError, match="^pip_venv_invalid$"):
        _run_nested_case(case)

    assert len(calls) == 1
    assert list(cast(Path, case["runtime_root"]).iterdir()) == []
    assert cast(Path, case["python"]).read_bytes() == b"approved-python"


def test_nested_pip_rejects_site_packages_alias_before_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _nested_pip_case(tmp_path)
    operator_site = tmp_path / "operator-site-packages"
    operator_site.mkdir()
    marker = operator_site / "operator-owned.txt"
    marker.write_text("unchanged", encoding="utf-8")
    calls = _install_fake_nested_pip_runtime(
        monkeypatch,
        case,
        site_packages_alias=operator_site,
    )

    with pytest.raises(_module().ReceiptError, match="^pip_venv_invalid$"):
        _run_nested_case(case)

    assert len(calls) == 1
    assert marker.read_text(encoding="utf-8") == "unchanged"
    assert list(cast(Path, case["runtime_root"]).iterdir()) == []


def test_nested_pip_rejects_site_packages_retarget_after_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _nested_pip_case(tmp_path)
    operator_site = tmp_path / "operator-site-packages"
    operator_site.mkdir()
    marker = operator_site / "operator-owned.txt"
    marker.write_text("unchanged", encoding="utf-8")

    def retarget_site_packages(argv: list[str]) -> None:
        venv = Path(argv[0]).parent.parent
        site_packages = venv / "lib" / "python3.12" / "site-packages"
        site_packages.rmdir()
        site_packages.symlink_to(operator_site, target_is_directory=True)

    _install_fake_nested_pip_runtime(
        monkeypatch,
        case,
        install_mutation=retarget_site_packages,
    )

    with pytest.raises(_module().ReceiptError, match="^pip_venv_identity_drift$"):
        _run_nested_case(case)

    assert marker.read_text(encoding="utf-8") == "unchanged"
    assert list(cast(Path, case["runtime_root"]).iterdir()) == []


def test_nested_pip_rejects_venv_retarget_after_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _nested_pip_case(tmp_path)

    def retarget_venv(argv: list[str]) -> None:
        executable = Path(argv[0])
        value = executable.read_bytes()
        executable.unlink()
        executable.write_bytes(value)
        executable.chmod(0o700)

    _install_fake_nested_pip_runtime(monkeypatch, case, install_mutation=retarget_venv)

    with pytest.raises(_module().ReceiptError, match="^pip_venv_identity_drift$"):
        _run_nested_case(case)

    assert list(cast(Path, case["runtime_root"]).iterdir()) == []
    assert cast(Path, case["python"]).read_bytes() == b"approved-python"


@pytest.mark.parametrize("mutation", ["replacement", "same_size_digest_drift"])
def test_nested_pip_rejects_source_replacement_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    receipt = _module()
    case = _nested_pip_case(tmp_path)
    calls = _install_fake_nested_pip_runtime(monkeypatch, case)
    original_write = getattr(receipt, "_write_exclusive_file", None)
    writes = 0

    def drifting_write(path: Path, value: bytes) -> None:
        nonlocal writes
        writes += 1
        if original_write is not None:
            original_write(path, value)
        if writes == 1:
            source = cast(Path, case["constraints"])
            if mutation == "replacement":
                source.unlink()
                source.write_bytes(b"replaced")
            else:
                source.write_bytes(b"x" * len(source.read_bytes()))

    monkeypatch.setattr(receipt, "_write_exclusive_file", drifting_write, raising=False)

    with pytest.raises(receipt.ReceiptError, match="^pip_input_identity_drift$"):
        _run_nested_case(case)

    assert calls == []
    assert list(cast(Path, case["runtime_root"]).iterdir()) == []


def test_nested_pip_rejects_source_post_run_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _nested_pip_case(tmp_path)

    def mutate_source(_argv: list[str]) -> None:
        source = cast(Path, case["requirements"])
        source.write_bytes(b"x" * len(source.read_bytes()))

    _install_fake_nested_pip_runtime(monkeypatch, case, install_mutation=mutate_source)

    with pytest.raises(_module().ReceiptError, match="^pip_input_identity_drift$"):
        _run_nested_case(case)

    assert list(cast(Path, case["runtime_root"]).iterdir()) == []


@pytest.mark.parametrize("mutation", ["replacement", "symlink", "extra", "missing"])
def test_nested_pip_rejects_staging_inventory_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    case = _nested_pip_case(tmp_path)

    def mutate_stage(argv: list[str]) -> None:
        uri = argv[argv.index("--find-links") + 1]
        staged_wheelhouse = Path(uri.removeprefix("file://"))
        wheel = staged_wheelhouse / "demo-1.0-py3-none-any.whl"
        if mutation == "replacement":
            wheel.unlink()
            wheel.write_bytes(b"other-bytes")
        elif mutation == "symlink":
            wheel.unlink()
            wheel.symlink_to(cast(Path, case["wheelhouse"]) / wheel.name)
        elif mutation == "extra":
            (staged_wheelhouse / "extra-1.0-py3-none-any.whl").write_bytes(b"extra")
        else:
            wheel.unlink()

    _install_fake_nested_pip_runtime(monkeypatch, case, install_mutation=mutate_stage)

    with pytest.raises(_module().ReceiptError, match="^pip_staging_identity_drift$"):
        _run_nested_case(case)

    assert list(cast(Path, case["runtime_root"]).iterdir()) == []


def test_nested_pip_cleanup_failure_is_terminal_and_preserves_operator_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    case = _nested_pip_case(tmp_path)
    _install_fake_nested_pip_runtime(monkeypatch, case)

    def fail_cleanup(_path: Path, _identity: tuple[int, ...]) -> None:
        raise receipt.ReceiptError("pip_cleanup_failed")

    monkeypatch.setattr(receipt, "_cleanup_owned_tree", fail_cleanup, raising=False)

    with pytest.raises(receipt.ReceiptError, match="^pip_cleanup_failed$"):
        _run_nested_case(case)

    assert cast(Path, case["python"]).read_bytes() == b"approved-python"


@pytest.mark.skipif(sys.platform != "darwin", reason="Darwin inode-addressed cleanup contract")
def test_nested_pip_cleanup_opens_and_removes_original_inode_after_path_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    call_root = tmp_path / "direct-audio-pip-owned"
    call_root.mkdir()
    call_root.chmod(0o700)
    (call_root / "venv").mkdir()
    (call_root / "venv" / "owned-python").write_text("owned", encoding="utf-8")
    (call_root / "stage").mkdir()
    (call_root / "stage" / "owned-wheel").write_bytes(b"owned")
    identity = receipt._owned_directory_identity(call_root)  # pyright: ignore[reportPrivateUsage]
    displaced = tmp_path / "displaced-owned-root"
    real_open = os.open
    raced = False

    def racing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal raced
        rendered = os.fsdecode(path)
        if not raced and (rendered == os.fspath(call_root) or rendered.startswith("/.vol/")):
            os.replace(call_root, displaced)
            call_root.mkdir()
            (call_root / "operator-owned-sentinel").write_text("preserve", encoding="utf-8")
            raced = True
        if dir_fd is None:
            return real_open(path, flags, mode)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(receipt.os, "open", racing_open)

    with pytest.raises(receipt.ReceiptError, match="^pip_cleanup_failed$"):
        receipt._cleanup_owned_tree(  # pyright: ignore[reportPrivateUsage]
            call_root,
            identity,
        )

    assert raced is True
    assert (call_root / "operator-owned-sentinel").read_text(encoding="utf-8") == "preserve"
    assert not displaced.exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="Darwin inode-addressed cleanup contract")
def test_nested_pip_cleanup_removes_owned_inode_and_preserves_path_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    call_root = tmp_path / "direct-audio-pip-owned"
    call_root.mkdir()
    call_root.chmod(0o700)
    (call_root / "owned-state").write_text("owned", encoding="utf-8")
    identity = receipt._owned_directory_identity(call_root)  # pyright: ignore[reportPrivateUsage]
    displaced = tmp_path / "displaced-owned-root"
    real_rmdir = os.rmdir
    raced = False

    def racing_rmdir(path: str | bytes | Path, *args: object, **kwargs: object) -> None:
        nonlocal raced
        rendered = os.fsdecode(path)
        if not raced and rendered.startswith("/.vol/"):
            os.replace(call_root, displaced)
            call_root.mkdir()
            (call_root / "operator-owned-sentinel").write_text("preserve", encoding="utf-8")
            raced = True
        real_rmdir(path, *args, **kwargs)

    monkeypatch.setattr(receipt.os, "rmdir", racing_rmdir)

    with pytest.raises(receipt.ReceiptError, match="^pip_cleanup_failed$"):
        receipt._cleanup_owned_tree(  # pyright: ignore[reportPrivateUsage]
            call_root,
            identity,
        )

    assert raced is True
    assert (call_root / "operator-owned-sentinel").read_text(encoding="utf-8") == "preserve"
    assert not displaced.exists()


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
    script_path = Path(__file__).parents[2] / "scripts" / "direct_audio_dependency_receipt.py"
    script_bytes = script_path.read_bytes()
    script = cast(dict[str, object], result["script"])
    assert script == {
        "bootstrap_contract": "not_performed",
        "bootstrap_contract_sha256": None,
        "schema": "mke.direct_audio_controller_execution.v1",
        "script_bytes": len(script_bytes),
        "script_sha256": hashlib.sha256(script_bytes).hexdigest(),
        "source_binding": "unbound_module_import",
    }
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


def test_check_inputs_binds_exact_readme_and_binary_fixture_inventory(tmp_path: Path) -> None:
    receipt = _module()
    fixtures = _copy_audio_fixture_root(tmp_path)
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()

    result = receipt.check_inputs(
        pythons=(),
        wheelhouse=wheelhouse,
        lock_path=tmp_path / "missing.lock",
        constraints=tmp_path / "missing-constraints.txt",
        fixture_root=fixtures,
    )

    inventory = cast(list[dict[str, object]], result["fixtures"])
    assert [item["filename"] for item in inventory] == [
        "README.md",
        "direct-audio.m4a",
        "direct-audio.mp3",
        "direct-audio.wav",
    ]
    readme = inventory[0]
    assert readme["bytes"] == 7256
    assert readme["sha256"] == _FIXTURE_AUTHORITY_DOCUMENT_SHA256


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("missing_readme", "fixture_inventory_invalid"),
        ("readme_symlink", "fixture_inventory_invalid"),
        ("extra", "fixture_inventory_invalid"),
        ("same_size_replacement", "fixture_identity_invalid"),
        ("root_symlink", "fixture_inventory_invalid"),
    ],
)
def test_check_inputs_fixture_root_mutations_fail_closed(
    tmp_path: Path, mutation: str, expected_code: str
) -> None:
    receipt = _module()
    fixtures = _copy_audio_fixture_root(tmp_path)
    fixture_argument = fixtures
    if mutation == "missing_readme":
        (fixtures / "README.md").unlink()
    elif mutation == "readme_symlink":
        readme = fixtures / "README.md"
        value = readme.read_bytes()
        readme.unlink()
        outside = tmp_path / "outside-readme"
        outside.write_bytes(value)
        readme.symlink_to(outside)
    elif mutation == "extra":
        (fixtures / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    elif mutation == "same_size_replacement":
        fixture = fixtures / "direct-audio.mp3"
        fixture.write_bytes(b"x" * fixture.stat().st_size)
    else:
        alias = tmp_path / "fixture-alias"
        alias.symlink_to(fixtures, target_is_directory=True)
        fixture_argument = alias
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()

    result = receipt.check_inputs(
        pythons=(),
        wheelhouse=wheelhouse,
        lock_path=tmp_path / "missing.lock",
        constraints=tmp_path / "missing-constraints.txt",
        fixture_root=fixture_argument,
    )

    assert expected_code in {item["code"] for item in cast(list[dict[str, str]], result["issues"])}


def test_fixture_root_replacement_during_descriptor_reads_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    fixtures = _copy_audio_fixture_root(tmp_path)
    replacement = tmp_path / "replacement-fixtures"
    replacement.mkdir()
    for entry in fixtures.iterdir():
        (replacement / entry.name).write_bytes(entry.read_bytes())
    displaced = tmp_path / "displaced-fixtures"
    original_read = receipt._read_regular
    replaced = False

    def replacing_read(path: Path) -> bytes:
        nonlocal replaced
        value = original_read(path)
        if path.parent == fixtures and path.name == "README.md" and not replaced:
            fixtures.rename(displaced)
            replacement.rename(fixtures)
            replaced = True
        return value

    monkeypatch.setattr(receipt, "_read_regular", replacing_read)

    with pytest.raises(receipt.ReceiptError, match="^fixture_identity_invalid$"):
        receipt.build_fixture_manifest(fixtures)


@pytest.mark.parametrize(
    ("input_name", "mutation", "expected_code"),
    [
        ("lock", "same_inode", "lock_identity_drift"),
        ("lock", "replacement", "lock_identity_drift"),
        ("constraints", "same_inode", "constraints_identity_drift"),
        ("constraints", "replacement", "constraints_identity_drift"),
        ("wheel", "same_inode", "wheel_identity_drift"),
        ("wheel", "replacement", "wheel_identity_drift"),
        ("README.md", "same_inode", "fixture_identity_invalid"),
        ("README.md", "replacement", "fixture_identity_invalid"),
        ("direct-audio.m4a", "same_inode", "fixture_identity_invalid"),
        ("direct-audio.m4a", "replacement", "fixture_identity_invalid"),
    ],
)
def test_check_inputs_revalidates_complete_authority_after_all_initial_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    input_name: str,
    mutation: str,
    expected_code: str,
) -> None:
    receipt = _module()
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = _wheel(wheelhouse, "demo-1.0-py3-none-any.whl", b"w")
    lock, constraints = _write_single_package_lock(
        tmp_path,
        name="demo",
        version="1.0",
        sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
    )
    fixtures = _copy_audio_fixture_root(tmp_path)
    targets = {
        "lock": lock,
        "constraints": constraints,
        "wheel": wheel,
        "README.md": fixtures / "README.md",
        "direct-audio.m4a": fixtures / "direct-audio.m4a",
    }
    target = targets[input_name]
    original_controller_identity = receipt._public_controller_identity
    mutated = False

    def mutate_after_initial_reads(executable: Path) -> dict[str, object]:
        nonlocal mutated
        if not mutated:
            value = target.read_bytes()
            if mutation == "same_inode":
                target.write_bytes(bytes([value[0] ^ 1]) + value[1:])
            else:
                target.unlink()
                target.write_bytes(value)
            mutated = True
        return original_controller_identity(executable)

    monkeypatch.setattr(receipt, "_public_controller_identity", mutate_after_initial_reads)

    result = receipt.check_inputs(
        pythons=(),
        wheelhouse=wheelhouse,
        lock_path=lock,
        constraints=constraints,
        fixture_root=fixtures,
    )

    assert mutated is True
    assert result["status"] == "failed"
    assert result["gate"] == "input_validation_failed"
    assert expected_code in {
        issue["code"] for issue in cast(list[dict[str, str]], result["issues"])
    }


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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    input_kind: str,
    expected_code: str,
) -> None:
    receipt = _module()
    _freeze_synthetic_darwin_cells(monkeypatch)
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
        pythons=(),
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
        'wheels = [{ url = "https://example.invalid/first-1.0-py3-none-any.whl", '
        f'hash = "sha256:{first_digest}", size = 1 }}]\n'
        '[[package]]\nname = "second"\nversion = "2.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://example.invalid/second-2.0-py3-none-any.whl", '
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
        'wheels = [{ url = "https://example.invalid/first-1.0-py3-none-any.whl", '
        f'hash = "sha256:{first_digest}", size = 1 }}]\n'
        '[[package]]\nname = "second"\nversion = "2.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://example.invalid/second-2.0-py3-none-any.whl", '
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
    unbound = subprocess.run(
        [sys.executable, "-I", "-B", *argv], capture_output=True, check=False
    )
    receipt = _module()
    accepted = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            receipt._CONTROLLER_BOOTSTRAP_SOURCE,  # pyright: ignore[reportPrivateUsage]
            "--",
            *argv,
        ],
        capture_output=True,
        check=False,
        env={},
    )

    assert rejected.returncode == 2
    assert json.loads(rejected.stdout)["failure"] == "controller_not_isolated"
    assert unbound.returncode == 2
    assert json.loads(unbound.stdout) == {
        "failure": "controller_bootstrap_required",
        "status": "failed",
    }
    assert accepted.returncode == 1
    payload = json.loads(accepted.stdout)
    assert payload["status"] == "failed"
    assert payload["gate"] == "input_validation_failed"
    script_authority = cast(dict[str, object], payload["script"])
    assert script_authority["schema"] == "mke.direct_audio_controller_execution.v1"
    assert script_authority["bootstrap_contract"] == (
        "mke.fixed_stdlib_descriptor_bootstrap.v1"
    )
    assert script_authority["source_binding"] == (
        "descriptor-sha256-compile-exec-same-bytes"
    )
    assert script_authority["script_sha256"] == hashlib.sha256(script.read_bytes()).hexdigest()
    assert script_authority["script_bytes"] == script.stat().st_size


def test_descriptor_bootstrap_executes_and_hashes_the_same_bytes_after_path_replacement(
    tmp_path: Path,
) -> None:
    receipt = _module()
    controller = tmp_path / "controller.py"
    replacement = tmp_path / "replacement.py"
    replacement_bytes = b"raise RuntimeError('replacement must not execute')\n"
    replacement.write_bytes(replacement_bytes)
    source = (
        "import hashlib,json,os\n"
        f"os.replace({str(replacement)!r},{str(controller)!r})\n"
        "authority=globals()['__MKE_DIRECT_AUDIO_CONTROLLER_AUTHORITY__']\n"
        f"current=open({str(controller)!r},'rb').read()\n"
        "print(json.dumps({'authority':authority,'current_sha256':"
        "hashlib.sha256(current).hexdigest()},sort_keys=True,separators=(',',':')))\n"
    ).encode()
    controller.write_bytes(source)

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            receipt._CONTROLLER_BOOTSTRAP_SOURCE,  # pyright: ignore[reportPrivateUsage]
            "--",
            str(controller),
        ],
        capture_output=True,
        check=False,
        env={},
    )

    assert result.returncode == 0
    assert result.stderr == b""
    payload = json.loads(result.stdout)
    authority = cast(dict[str, object], payload["authority"])
    assert authority["script_sha256"] == hashlib.sha256(source).hexdigest()
    assert authority["script_bytes"] == len(source)
    assert payload["current_sha256"] == hashlib.sha256(replacement_bytes).hexdigest()
    assert authority["script_sha256"] != payload["current_sha256"]
    assert authority["source_binding"] == "descriptor-sha256-compile-exec-same-bytes"


def test_running_controller_cannot_validate_receipt_for_post_gate_replacement(
    tmp_path: Path,
) -> None:
    receipt = _module()
    production_script = (
        Path(__file__).parents[2] / "scripts" / "direct_audio_dependency_receipt.py"
    )
    replacement = tmp_path / "replacement-controller.py"
    controller = tmp_path / "controller.py"
    artifact = tmp_path / "dependency-artifacts.json"
    replacement_bytes = production_script.read_bytes()
    replacement.write_bytes(replacement_bytes)
    injection = (
        "\n_ORIGINAL_CONTROLLER_PROJECTION = _controller_execution_projection\n"
        "_CONTROLLER_REPLACED = False\n"
        "def _replace_after_first_projection(*, require_bound):\n"
        "    global _CONTROLLER_REPLACED\n"
        "    authority = _ORIGINAL_CONTROLLER_PROJECTION(require_bound=require_bound)\n"
        "    if not _CONTROLLER_REPLACED:\n"
        f"        os.replace({str(replacement)!r}, __file__)\n"
        "        _CONTROLLER_REPLACED = True\n"
        "    return authority\n"
        "_controller_execution_projection = _replace_after_first_projection\n\n"
    )
    source = replacement_bytes.decode("utf-8").replace(
        '\nif __name__ == "__main__":\n',
        injection + 'if __name__ == "__main__":\n',
    )
    controller.write_text(source, encoding="utf-8")
    evidence = _complete_generation_evidence()
    artifact.write_bytes(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            receipt._CONTROLLER_BOOTSTRAP_SOURCE,  # pyright: ignore[reportPrivateUsage]
            "--",
            str(controller),
            "--validate-receipt",
            str(artifact),
            "--json",
        ],
        capture_output=True,
        check=False,
        env={},
    )

    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "failure": "controller_bootstrap_invalid",
        "status": "failed",
    }
    assert result.stderr == b""


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


def test_bounded_runner_maps_missing_executable_to_closed_receipt_error() -> None:
    receipt = _module()

    with pytest.raises(receipt.ReceiptError, match="^bounded_supervision_failed$"):
        receipt._run_bounded(  # pyright: ignore[reportPrivateUsage]
            ["definitely-missing-receipt-executable"],
            env={},
            cwd=None,
            profile=receipt.BoundedProfile(1.0, 32, 32),
        )


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


def test_terminal_cleanup_failure_overrides_timeout_after_two_real_descendant_attempts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _module()
    marker = tmp_path / "descendant-pid"
    source = (
        "import pathlib,subprocess,sys,time;"
        "child=subprocess.Popen([sys.executable,'-I','-B','-c',"
        "'import time;time.sleep(30)']);"
        f"pathlib.Path({str(marker)!r}).write_text(str(child.pid),encoding='ascii');"
        "time.sleep(30)"
    )
    real_popen = receipt.subprocess.Popen
    real_killpg = receipt.os.killpg
    processes: list[subprocess.Popen[bytes]] = []
    cleanup_signal_failures = 0

    def capture_process(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process

    def deny_cleanup_signals(pid: int, sig: int) -> None:
        nonlocal cleanup_signal_failures
        if sig in {receipt.signal.SIGTERM, receipt.signal.SIGKILL}:
            cleanup_signal_failures += 1
            raise PermissionError("cleanup denied")
        real_killpg(pid, sig)

    monkeypatch.setattr(receipt.subprocess, "Popen", capture_process)
    monkeypatch.setattr(receipt.os, "killpg", deny_cleanup_signals)
    profile = receipt.BoundedProfile(
        wall_seconds=0.2,
        stdout_bytes=4096,
        stderr_bytes=4096,
        poll_seconds=0.01,
        term_grace_seconds=0.05,
    )

    try:
        with pytest.raises(receipt.ReceiptError) as raised:
            receipt._run_bounded(  # pyright: ignore[reportPrivateUsage]
                [sys.executable, "-I", "-B", "-c", source],
                env={},
                cwd=None,
                profile=profile,
            )

        assert str(raised.value) == "bounded_cleanup_incomplete"
        assert cleanup_signal_failures >= 2
        assert processes and processes[0].poll() is None
        descendant_pid = int(marker.read_text(encoding="ascii"))
        assert os.getpgid(descendant_pid) == processes[0].pid
        os.kill(descendant_pid, 0)
        details = cast(dict[str, object], raised.value.details)
        assert cast(dict[str, bool], details["cleanup"])["process_group_absent"] is False
    finally:
        monkeypatch.setattr(receipt.os, "killpg", real_killpg)
        if processes and not receipt._process_group_absent(  # pyright: ignore[reportPrivateUsage]
            processes[0].pid
        ):
            try:
                receipt._cleanup_process_group(  # pyright: ignore[reportPrivateUsage]
                    processes[0], grace_seconds=0.2, terminate=True
                )
            except receipt.ReceiptError:
                real_killpg(processes[0].pid, receipt.signal.SIGKILL)
                processes[0].wait(timeout=2.0)
        if processes:
            assert receipt._process_group_absent(  # pyright: ignore[reportPrivateUsage]
                processes[0].pid
            )


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
        ' time.sleep(0.05)\\nwhile True:\\n time.sleep(1)")'
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


def _refresh_preflight_digest(payload: dict[str, object]) -> None:
    observed = {
        key: value
        for key, value in payload.items()
        if key not in {"issues", "status", "gate", "observed_digest"}
    }
    payload["observed_digest"] = _canonical_digest(observed)


def _refresh_receipt_digest(evidence: dict[str, object]) -> None:
    evidence["receipt_sha256"] = _canonical_digest(
        {key: value for key, value in evidence.items() if key != "receipt_sha256"}
    )


def _interpreter_rows() -> list[dict[str, object]]:
    return [
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
    ]


def _wheel_manifest_digest(wheels: list[dict[str, object]]) -> str:
    return _canonical_digest(
        [
            {
                "filename": item["filename"],
                "distribution": item["distribution"],
                "version": item["version"],
                "build": item["build"],
                "python_tags": item["python_tags"],
                "abi_tags": item["abi_tags"],
                "platform_tags": item["platform_tags"],
                "bytes": item["bytes"],
                "sha256": item["sha256"],
            }
            for item in wheels
        ]
    )


def _complete_preflight_payload(evidence: dict[str, object]) -> dict[str, object]:
    wheel_rows = cast(list[dict[str, object]], evidence["wheel_inventory"])
    fixture_rows = cast(list[dict[str, object]], evidence["fixtures"])
    installed_rows = cast(list[dict[str, object]], evidence["installed_distributions"])
    wheel_by_filename = {item["filename"]: item for item in wheel_rows}
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
        "script": dict(cast(dict[str, object], evidence["controller_execution"])),
        "interpreters": _interpreter_rows(),
        "lock_sha256": "5" * 64,
        "constraints_sha256": "4" * 64,
        "root_requirements_sha256": "3" * 64,
        "wheelhouse": [dict(item) for item in wheel_rows],
        "wheel_resolution": [
            {
                "cell": item["cell"],
                "distribution": item["distribution"],
                "version": item["version"],
                "filename": item["source_wheel_filename"],
                "sha256": wheel_by_filename[item["source_wheel_filename"]]["sha256"],
            }
            for item in installed_rows
        ],
        "fixtures": [
            dict(cast(dict[str, object], evidence["fixture_authority_document"])),
            *[
                {
                    "filename": item["filename"],
                    "bytes": item["bytes"],
                    "sha256": item["sha256"],
                    "artifact_scope": item["artifact_scope"],
                }
                for item in fixture_rows
            ],
        ],
        "issues": [],
        "observed_digest": "",
    }
    _refresh_preflight_digest(payload)
    return payload


def _complete_generation_bundle() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    evidence = _complete_generation_evidence()
    preflight = _complete_preflight_payload(evidence)
    generation_preflight = _complete_preflight_payload(evidence)
    evidence["preflight_observed_digest"] = preflight["observed_digest"]
    evidence["generation_preflight_observed_digest"] = generation_preflight["observed_digest"]
    _refresh_receipt_digest(evidence)
    return evidence, preflight, generation_preflight


def _complete_generation_evidence() -> dict[str, object]:
    script = Path(__file__).parents[2] / "scripts" / "direct_audio_dependency_receipt.py"
    script_bytes = script.read_bytes()
    script_sha256 = hashlib.sha256(script_bytes).hexdigest()
    receipt = _module()
    controller_execution = {
        "bootstrap_contract": "mke.fixed_stdlib_descriptor_bootstrap.v1",
        "bootstrap_contract_sha256": receipt._CONTROLLER_BOOTSTRAP_CONTRACT_SHA256,  # pyright: ignore[reportPrivateUsage]
        "schema": "mke.direct_audio_controller_execution.v1",
        "script_bytes": len(script_bytes),
        "script_sha256": script_sha256,
        "source_binding": "descriptor-sha256-compile-exec-same-bytes",
    }
    wheels: list[dict[str, object]] = [
        {
            "filename": "av-17.1.0-cp312-cp312-macosx_11_0_arm64.whl",
            "distribution": "av",
            "version": "17.1.0",
            "build": None,
            "python_tags": ["cp312"],
            "abi_tags": ["cp312"],
            "platform_tags": ["macosx_11_0_arm64"],
            "bytes": 101,
            "sha256": "a" * 64,
            "artifact_scope": "local_runtime_only",
        },
        {
            "filename": "av-17.1.0-cp313-cp313-macosx_11_0_arm64.whl",
            "distribution": "av",
            "version": "17.1.0",
            "build": None,
            "python_tags": ["cp313"],
            "abi_tags": ["cp313"],
            "platform_tags": ["macosx_11_0_arm64"],
            "bytes": 102,
            "sha256": "c" * 64,
            "artifact_scope": "local_runtime_only",
        },
        {
            "filename": "faster_whisper-1.2.1-py3-none-any.whl",
            "distribution": "faster-whisper",
            "version": "1.2.1",
            "build": None,
            "python_tags": ["py3"],
            "abi_tags": ["none"],
            "platform_tags": ["any"],
            "bytes": 103,
            "sha256": "d" * 64,
            "artifact_scope": "local_runtime_only",
        },
        {
            "filename": "huggingface_hub-1.0-py3-none-any.whl",
            "distribution": "huggingface-hub",
            "version": "1.0",
            "build": None,
            "python_tags": ["py3"],
            "abi_tags": ["none"],
            "platform_tags": ["any"],
            "bytes": 104,
            "sha256": "e" * 64,
            "artifact_scope": "local_runtime_only",
        },
    ]
    wheels_by_name = {cast(str, item["filename"]): item for item in wheels}
    installed: list[dict[str, object]] = []
    for cell in ("3.12", "3.13"):
        filenames = (
            (
                "av-17.1.0-cp312-cp312-macosx_11_0_arm64.whl"
                if cell == "3.12"
                else "av-17.1.0-cp313-cp313-macosx_11_0_arm64.whl"
            ),
            "faster_whisper-1.2.1-py3-none-any.whl",
            "huggingface_hub-1.0-py3-none-any.whl",
        )
        for filename in filenames:
            wheel = wheels_by_name[filename]
            installed.append(
                {
                    "distribution": wheel["distribution"],
                    "version": wheel["version"],
                    "source_wheel_filename": filename,
                    "source_wheel_sha256": wheel["sha256"],
                    "cell": cell,
                    "artifact_scope": "local_runtime_only",
                }
            )
    interpreters = {item["label"]: item for item in _interpreter_rows()}
    manifest_sha256 = _wheel_manifest_digest(wheels)
    pip_authority = {
        "argv": [
            "call-owned-venv-python",
            "-I",
            "-m",
            "pip",
            "--isolated",
            "--disable-pip-version-check",
            "--no-input",
            "install",
            "--no-index",
            "--find-links",
            "call-owned-wheelhouse-uri",
            "--only-binary=:all:",
            "--no-cache-dir",
            "--require-hashes",
            "--constraint",
            "call-owned-constraints",
            "--requirement",
            "call-owned-root-requirements",
        ],
        "environment": {
            "HOME": "call-owned-home",
            "PIP_CONFIG_FILE": "platform-null",
            "TMPDIR": "call-owned-temp",
        },
        "pip_install": "passed",
        "pip_check": "passed",
        "cleanup": "passed",
        "staging": {
            "constraints_sha256": "4" * 64,
            "root_requirements_sha256": "3" * 64,
            "wheelhouse_manifest_sha256": manifest_sha256,
        },
    }
    cells = []
    for cell in ("3.12", "3.13"):
        cell_installed = [dict(item) for item in installed if item["cell"] == cell]
        cells.append(
            {
                "cell": cell,
                "interpreter": dict(interpreters[f"python-{cell}"]),
                "pip": json.loads(json.dumps(pip_authority)),
                "installed_distributions": cell_installed,
                "imports": [
                    {
                        "distribution": distribution,
                        "module": module,
                        "status": "passed",
                        "version": version,
                        "evidence_sha256": (
                            wheels_by_name[
                                "av-17.1.0-cp312-cp312-macosx_11_0_arm64.whl"
                                if cell == "3.12"
                                else "av-17.1.0-cp313-cp313-macosx_11_0_arm64.whl"
                            ]["sha256"]
                            if distribution == "av"
                            else digest
                        ),
                    }
                    for distribution, module, version, digest in (
                        ("av", "av", "17.1.0", "a" * 64),
                        ("faster-whisper", "faster_whisper", "1.2.1", "d" * 64),
                        ("huggingface-hub", "huggingface_hub", "1.0", "e" * 64),
                    )
                ],
                "fixture_decodes": [
                    {
                        "filename": name,
                        "sha256": fixture_sha256,
                        "decoder": "pyav",
                        "status": "passed",
                        "stream_count": 1,
                    }
                    for name, (_, fixture_sha256, _) in _FIXTURE_IDENTITIES.items()
                ],
            }
        )
    digest = "a" * 64
    evidence: dict[str, object] = {
        "schema_version": "mke.direct_audio_dependency_receipt.v1",
        "receipt_sha256": "",
        "script_sha256": script_sha256,
        "controller_execution": controller_execution,
        "preflight_observed_digest": "b" * 64,
        "generation_preflight_observed_digest": "b" * 64,
        "external_binary_redistribution": "not_performed",
        "redistribution_authority": "not_claimed",
        "binary_source_provenance": "not_claimed",
        "wheel_inventory": wheels,
        "installed_distributions": installed,
        "cells": cells,
        "darwin_supervisor": {
            "api": "proc_pid_rusage",
            "api_version": "RUSAGE_INFO_V4",
            "tool": "stdlib-ctypes",
            "metric": "ri_phys_footprint",
            "leader_scope": "process_group_leader",
            "leader_identity_binding": "pid+ri_proc_start_abstime",
            "descendants_scope": "ordinary_cooperative_descendants",
            "budget_mode": "baseline_plus",
            "baseline_bytes": 1_000_000,
            "budget_bytes": 2_000_000,
            "poll_seconds": 0.01,
            "controlled_allocator": "stdlib-bytearray-growth",
            "observed_max_bytes": 2_100_000,
            "overshoot_bytes": 100_000,
            "budget_outcome": "exceeded_terminated",
            "transient_overshoot_possible": True,
            "cleanup": {
                "sigterm_sent": True,
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
        },
        "pyav": {
            "distribution": "av",
            "version": "17.1.0",
            "artifact_scope": "local_runtime_only",
            "extensions": [{"filename": "av/_core.so", "sha256": digest}],
            "linked_components": ["libavcodec"],
            "bundled_components": ["pyav"],
        },
        "ffmpeg_runtime": {
            "version": "8.1.1",
            "runtime_license_label": "LGPL version 3 or later",
            "runtime_license_label_sha256": (
                "511f63111e9aeaf0151394415cd170c1a396c95bb3da8a63aa681cc8d978a306"
            ),
            "configuration": "--enable-shared",
            "configuration_sha256": digest,
            "binary_inventory_sha256": digest,
            "source_tag": "n8.1.1",
            "source_tag_object_sha1": "150ba6ddfabb5c433bb2fb3ee546d2a96e59066d",
            "source_commit_sha1": "239f2c733de417201d7ad3b3b8b0d9b63285b2b1",
            "source_reference": (
                "ffmpeg-source-n8_1_1-239f2c733de417201d7ad3b3b8b0d9b63285b2b1"
            ),
            "license_notice_filename": "LICENSE.md",
            "license_notice_bytes": 4346,
            "license_notice_sha256": (
                "2e1d16c72fd74e12063776371da757322f8b77589386532f4fd8634bde7de1af"
            ),
            "license_text_filename": "COPYING.LGPLv3",
            "license_text_bytes": 7651,
            "license_text_sha256": (
                "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768"
            ),
            "binary_source_provenance": "not_claimed",
            "artifact_scope": "local_runtime_only",
        },
        "direct_components": [
            {
                "name": "libavcodec",
                "version": "62.28.101",
                "license": "LGPL-3.0-or-later",
                "license_authority": "runtime_reported",
                "evidence_sha256": digest,
                "source_reference": (
                    "ffmpeg-source-n8_1_1-239f2c733de417201d7ad3b3b8b0d9b63285b2b1"
                ),
                "license_text_sha256": (
                    "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768"
                ),
                "artifact_scope": "local_runtime_only",
                "local_use_restriction": "not_assessed",
                "binary_source_provenance": "not_claimed",
            },
            {
                "name": "pyav",
                "version": "17.1.0",
                "license": "BSD-3-Clause",
                "license_authority": "installed_distribution_metadata",
                "evidence_sha256": digest,
                "source_reference": "pyav-project-17_1_0",
                "license_text_sha256": (
                    "76af0461ffb92e19f1c14449e95557d83a2dfaa1baf202d49e5f1d8746c0da19"
                ),
                "artifact_scope": "local_runtime_only",
                "local_use_restriction": "not_assessed",
                "binary_source_provenance": "not_claimed",
            },
        ],
        "fixture_authority_document": {
            "filename": "README.md",
            "bytes": 7_256,
            "sha256": _FIXTURE_AUTHORITY_DOCUMENT_SHA256,
            "artifact_scope": "repository_distributed",
        },
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
                "observed_dylib_suffix": "1",
                "upstream_version_authority": "not_established",
                "identity_sha256": digest,
                "redistribution_clearance": "unresolved",
                "local_use_restriction": "not_assessed",
                "artifact_scope": "local_runtime_only",
            }
        ],
    }
    _refresh_receipt_digest(evidence)
    return evidence


def test_generation_rejects_partial_projection_as_preflight_authority() -> None:
    receipt = _module()
    evidence = _complete_generation_evidence()

    assert receipt.validate_generation_evidence(evidence) == {
        "failure": "generation_evidence_invalid",
        "status": "failed",
    }


def test_local_optional_use_allows_recorded_unresolved_transitive_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _module()
    _freeze_synthetic_darwin_cells(monkeypatch)
    evidence, preflight, generation_preflight = _complete_generation_bundle()

    assert evidence["schema_version"] == "mke.direct_audio_dependency_receipt.v1"
    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {
        "external_binary_redistribution": "not_performed",
        "redistribution_authority": "not_claimed",
        "status": "passed",
    }


def test_synthetic_darwin_generation_authority_is_independent_of_linux_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _module()
    evidence, preflight, generation_preflight = _complete_generation_bundle()
    monkeypatch.setattr(receipt.platform, "system", lambda: "Linux")
    monkeypatch.setattr(receipt.platform, "machine", lambda: "x86_64")
    _freeze_synthetic_darwin_cells(monkeypatch)

    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {
        "external_binary_redistribution": "not_performed",
        "redistribution_authority": "not_claimed",
        "status": "passed",
    }


def test_generation_evidence_freezes_immutable_ffmpeg_license_and_source_authority() -> None:
    evidence = _complete_generation_evidence()
    ffmpeg = cast(dict[str, object], evidence["ffmpeg_runtime"])

    assert ffmpeg == {
        "version": "8.1.1",
        "runtime_license_label": "LGPL version 3 or later",
        "runtime_license_label_sha256": (
            "511f63111e9aeaf0151394415cd170c1a396c95bb3da8a63aa681cc8d978a306"
        ),
        "configuration": "--enable-shared",
        "configuration_sha256": "a" * 64,
        "binary_inventory_sha256": "a" * 64,
        "source_tag": "n8.1.1",
        "source_tag_object_sha1": "150ba6ddfabb5c433bb2fb3ee546d2a96e59066d",
        "source_commit_sha1": "239f2c733de417201d7ad3b3b8b0d9b63285b2b1",
        "source_reference": (
            "ffmpeg-source-n8_1_1-239f2c733de417201d7ad3b3b8b0d9b63285b2b1"
        ),
        "license_notice_filename": "LICENSE.md",
        "license_notice_bytes": 4346,
        "license_notice_sha256": (
            "2e1d16c72fd74e12063776371da757322f8b77589386532f4fd8634bde7de1af"
        ),
        "license_text_filename": "COPYING.LGPLv3",
        "license_text_bytes": 7651,
        "license_text_sha256": (
            "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768"
        ),
        "binary_source_provenance": "not_claimed",
        "artifact_scope": "local_runtime_only",
    }
    direct = cast(list[dict[str, object]], evidence["direct_components"])
    assert all(item["local_use_restriction"] == "not_assessed" for item in direct)
    assert all(item["binary_source_provenance"] == "not_claimed" for item in direct)
    unresolved = cast(list[dict[str, object]], evidence["unresolved_transitive_binary_items"])
    assert unresolved
    assert all("version" not in item for item in unresolved)
    assert all(item["upstream_version_authority"] == "not_established" for item in unresolved)
    assert all(item["local_use_restriction"] == "not_assessed" for item in unresolved)


def test_committed_dependency_receipt_passes_independent_static_validation() -> None:
    receipt = _module()
    path = Path(__file__).parents[2] / "benchmarks" / "audio" / "dependency-artifacts.json"
    committed_bytes = path.read_bytes()
    evidence = cast(dict[str, object], json.loads(committed_bytes.decode("ascii")))

    assert committed_bytes == (
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    )
    assert receipt.validate_committed_receipt(evidence) == {
        "authority": "canonical_static_artifact",
        "binary_source_provenance": "not_claimed",
        "external_binary_redistribution": "not_performed",
        "redistribution_authority": "not_claimed",
        "retained_runtime_replay": "not_performed",
        "status": "passed",
    }
    assert evidence["receipt_sha256"] != hashlib.sha256(committed_bytes).hexdigest()


def test_complete_generation_evidence_passes_independent_static_validation() -> None:
    receipt = _module()

    assert receipt.validate_committed_receipt(_complete_generation_evidence()) == {
        "authority": "canonical_static_artifact",
        "binary_source_provenance": "not_claimed",
        "external_binary_redistribution": "not_performed",
        "redistribution_authority": "not_claimed",
        "retained_runtime_replay": "not_performed",
        "status": "passed",
    }


def test_validate_receipt_cli_accepts_committed_artifact_without_runtime_replay() -> None:
    receipt = _module()
    script = Path(__file__).parents[2] / "scripts" / "direct_audio_dependency_receipt.py"
    artifact = Path(__file__).parents[2] / "benchmarks" / "audio" / "dependency-artifacts.json"
    artifact_bytes = artifact.read_bytes()
    evidence = cast(dict[str, object], json.loads(artifact_bytes.decode("ascii")))

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            receipt._CONTROLLER_BOOTSTRAP_SOURCE,  # pyright: ignore[reportPrivateUsage]
            "--",
            str(script),
            "--validate-receipt",
            str(artifact),
            "--json",
        ],
        capture_output=True,
        check=False,
        env={},
    )

    assert result.returncode == 0
    assert result.stderr == b""
    assert json.loads(result.stdout) == {
        "authority": "canonical_static_artifact",
        "binary_source_provenance": "not_claimed",
        "canonical_payload_sha256": evidence["receipt_sha256"],
        "committed_file_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "external_binary_redistribution": "not_performed",
        "redistribution_authority": "not_claimed",
        "retained_runtime_replay": "not_performed",
        "status": "passed",
    }


def test_validate_receipt_cli_rejects_noncanonical_artifact_public_safely(
    tmp_path: Path,
) -> None:
    receipt = _module()
    script = Path(__file__).parents[2] / "scripts" / "direct_audio_dependency_receipt.py"
    artifact = tmp_path / "private-operator-receipt.json"
    artifact.write_text(json.dumps(_complete_generation_evidence(), indent=2), encoding="ascii")

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            receipt._CONTROLLER_BOOTSTRAP_SOURCE,  # pyright: ignore[reportPrivateUsage]
            "--",
            str(script),
            "--validate-receipt",
            str(artifact),
            "--json",
        ],
        capture_output=True,
        check=False,
        env={},
    )

    assert result.returncode == 2
    assert result.stderr == b""
    assert json.loads(result.stdout) == {
        "failure": "committed_receipt_invalid",
        "status": "failed",
    }
    assert b"private-operator-receipt" not in result.stdout
    assert b"Traceback" not in result.stdout


def test_validate_receipt_mode_rejects_mixed_generation_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    receipt = _module()

    result = receipt.main(
        [
            "--validate-receipt",
            "dependency-artifacts.json",
            "--check-inputs",
            "--json",
        ]
    )

    assert result == 2
    assert json.loads(capsys.readouterr().out) == {
        "failure": "cli_arguments_invalid",
        "status": "failed",
    }


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("source_tag", "n8.1.2"),
        ("source_tag_object_sha1", "1" * 40),
        ("source_commit_sha1", "2" * 40),
        ("license_notice_sha256", "3" * 64),
        ("license_text_sha256", "4" * 64),
        ("binary_source_provenance", "established"),
    ],
)
def test_static_receipt_validator_rejects_well_formed_ffmpeg_authority_substitution(
    field: str,
    replacement: str,
) -> None:
    receipt = _module()
    evidence = _complete_generation_evidence()
    cast(dict[str, object], evidence["ffmpeg_runtime"])[field] = replacement
    _refresh_receipt_digest(evidence)

    assert receipt.validate_committed_receipt(evidence) == {
        "failure": "committed_receipt_invalid",
        "status": "failed",
    }


def test_task1_final_focused_gate_requires_real_pyav_fixture_profiles() -> None:
    plan = (
        Path(__file__).parents[2]
        / "docs"
        / "superpowers"
        / "plans"
        / "2026-07-18-bounded-direct-audio-intake-implementation.md"
    ).read_text(encoding="utf-8")
    task1 = plan.split("### Task 1 (PR A):", 1)[1].split("### Task 2 (PR B):", 1)[0]
    step7 = task1.split("**Step 7:", 1)[1]

    assert "UV_OFFLINE=1 MKE_REQUIRE_TRANSCRIPTION_EXTRA=1 uv run pytest -q" in step7
    assert "tests/adapters/test_audio_fixtures.py" in step7
    assert "tests/scripts/test_direct_audio_dependency_receipt.py" in step7


def test_generation_rejects_arbitrary_project_source_reference_substitution() -> None:
    receipt = _module()
    evidence, preflight, generation_preflight = _complete_generation_bundle()
    cast(dict[str, object], evidence["ffmpeg_runtime"])["source_reference"] = (
        "arbitrary-public-token"
    )
    for component in cast(list[dict[str, object]], evidence["direct_components"]):
        component["source_reference"] = "arbitrary-public-token"
    _refresh_receipt_digest(evidence)

    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {"failure": "generation_evidence_invalid", "status": "failed"}


@pytest.mark.skipif(platform.system() != "Darwin", reason="Darwin wheel floor authority")
def test_preflight_authority_uses_live_os_floor_with_target_interpreter_abi() -> None:
    receipt = _module()
    evidence, preflight, _ = _complete_generation_bundle()
    del evidence
    wheelhouse = cast(list[dict[str, object]], preflight["wheelhouse"])
    resolutions = cast(list[dict[str, object]], preflight["wheel_resolution"])
    for interpreter in cast(list[dict[str, object]], preflight["interpreters"]):
        interpreter["sysconfig_platform"] = "macosx-11.0-arm64"
    replacements: dict[str, str] = {}
    for wheel in wheelhouse:
        filename = cast(str, wheel["filename"])
        if cast(str, wheel["distribution"]) != "av":
            continue
        replacement = filename.replace("macosx_11_0_arm64", "macosx_14_0_arm64")
        wheel["filename"] = replacement
        wheel["platform_tags"] = ["macosx_14_0_arm64"]
        replacements[filename] = replacement
    for row in resolutions:
        filename = cast(str, row["filename"])
        if filename in replacements:
            row["filename"] = replacements[filename]
    _refresh_preflight_digest(preflight)

    assert receipt._passed_preflight_authority(preflight) is not None  # pyright: ignore[reportPrivateUsage]


def test_static_receipt_uses_target_abi_without_treating_sysconfig_floor_as_host_ceiling() -> None:
    receipt = _module()
    evidence = _complete_generation_evidence()
    wheels = cast(list[dict[str, object]], evidence["wheel_inventory"])
    replacements: dict[str, str] = {}
    for wheel in wheels:
        filename = cast(str, wheel["filename"])
        if cast(str, wheel["distribution"]) != "av":
            continue
        replacement = filename.replace("macosx_11_0_arm64", "macosx_14_0_arm64")
        wheel["filename"] = replacement
        wheel["platform_tags"] = ["macosx_14_0_arm64"]
        replacements[filename] = replacement
    for installed in cast(list[dict[str, object]], evidence["installed_distributions"]):
        filename = cast(str, installed["source_wheel_filename"])
        if filename in replacements:
            installed["source_wheel_filename"] = replacements[filename]
    manifest_sha256 = _wheel_manifest_digest(wheels)
    for cell in cast(list[dict[str, object]], evidence["cells"]):
        for installed in cast(list[dict[str, object]], cell["installed_distributions"]):
            filename = cast(str, installed["source_wheel_filename"])
            if filename in replacements:
                installed["source_wheel_filename"] = replacements[filename]
        cast(dict[str, object], cast(dict[str, object], cell["pip"])["staging"])[
            "wheelhouse_manifest_sha256"
        ] = manifest_sha256
    _refresh_receipt_digest(evidence)

    assert receipt.validate_committed_receipt(evidence)["status"] == "passed"


def test_runtime_evidence_probe_uses_fixed_isolated_command_and_closed_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _module()
    python = tmp_path / "venv" / "bin" / "python3.12"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"python")
    python.chmod(0o700)
    fixtures = _copy_audio_fixture_root(tmp_path)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    payload = {
        "schema": "mke.direct_audio_runtime_evidence.v1",
        "installed_distributions": [
            {"distribution": "av", "version": "17.1.0"},
            {"distribution": "faster-whisper", "version": "1.2.1"},
            {"distribution": "huggingface-hub", "version": "1.21.0"},
        ],
        "imports": [
            {"distribution": "av", "module": "av", "status": "passed", "version": "17.1.0"},
            {
                "distribution": "faster-whisper",
                "module": "faster_whisper",
                "status": "passed",
                "version": "1.2.1",
            },
            {
                "distribution": "huggingface-hub",
                "module": "huggingface_hub",
                "status": "passed",
                "version": "1.21.0",
            },
        ],
        "fixture_decodes": [
            {
                "filename": name,
                "sha256": fixture_sha256,
                "decoder": "pyav",
                "status": "passed",
                "stream_count": 1,
            }
            for name, (_, fixture_sha256, _) in _FIXTURE_IDENTITIES.items()
        ],
        "pyav": {
            "version": "17.1.0",
            "extensions": [{"filename": "av/_core.abi3.so", "sha256": "a" * 64}],
            "bundled_binaries": [
                {
                    "filename": "av/.dylibs/libavutil.60.26.101.dylib",
                    "sha256": "b" * 64,
                }
            ],
            "library_versions": {"libavutil": "60.26.101"},
            "license": "BSD-3-Clause",
            "license_text_sha256": "c" * 64,
            "ffmpeg_license": "LGPL version 3 or later",
            "ffmpeg_configuration": "--disable-static --enable-shared",
            "ffmpeg_configuration_sha256": "d" * 64,
            "ffmpeg_version": "8.1.1",
        },
    }
    captured: dict[str, object] = {}

    def run(argv: list[str], **kwargs: object) -> SimpleNamespace:
        captured["argv"] = argv
        captured.update(kwargs)
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
            + b"\n",
            stderr=b"",
            supervision=None,
        )

    monkeypatch.setattr(receipt, "_run_bounded", run)

    observed = receipt._collect_runtime_evidence(  # pyright: ignore[reportPrivateUsage]
        python=python,
        fixture_root=fixtures,
        requirements=(
            receipt.Requirement("av", "17.1.0"),
            receipt.Requirement("faster-whisper", "1.2.1"),
            receipt.Requirement("huggingface-hub", "1.21.0"),
        ),
        cwd=cwd,
        env={"HOME": "call-owned-home", "TMPDIR": "call-owned-temp"},
    )

    assert cast(list[str], captured["argv"])[:5] == [
        str(python),
        "-I",
        "-B",
        "-c",
        receipt._RUNTIME_EVIDENCE_SOURCE,  # pyright: ignore[reportPrivateUsage]
    ]
    assert captured["env"] == {"HOME": "call-owned-home", "TMPDIR": "call-owned-temp"}
    assert captured["cwd"] == cwd
    assert observed == payload
    assert str(tmp_path) not in json.dumps(observed, sort_keys=True)


def test_runtime_probe_decodes_the_exact_bytes_bound_to_fixture_sha_after_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    receipt = _module()
    fixture_root = tmp_path / "fixtures"
    fixture_root.mkdir()
    fixture = fixture_root / "direct-audio.wav"
    original_bytes = b"fixture-a"
    replacement_bytes = b"fixture-b"
    fixture.write_bytes(original_bytes)
    replacement = tmp_path / "replacement.wav"
    replacement.write_bytes(replacement_bytes)

    site_root = tmp_path / "site-packages"
    av_root = site_root / "av"
    dylib_root = av_root / ".dylibs"
    dylib_root.mkdir(parents=True)
    (av_root / "__init__.py").write_text("", encoding="ascii")
    (av_root / "_core.abi3.so").write_bytes(b"extension")
    (dylib_root / "libavutil.60.26.101.dylib").write_bytes(b"dylib")
    license_file = site_root / "av-17.1.0.dist-info" / "licenses" / "LICENSE.txt"
    license_file.parent.mkdir(parents=True)
    license_file.write_bytes(b"PyAV license")

    observed: dict[str, object] = {}

    class Container:
        streams = SimpleNamespace(
            audio=[SimpleNamespace(index=0)],
            video=[],
            subtitles=[],
        )

        def __enter__(self) -> Container:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def decode(self, *, audio: int):
            assert audio == 0
            return iter((object(),))

    def open_fixture(value: object, *, mode: str) -> Container:
        assert mode == "r"
        assert isinstance(value, io.BytesIO)
        observed["decoded_bytes"] = value.getvalue()
        return Container()

    av_module = types.ModuleType("av")
    av_module.__file__ = str(av_root / "__init__.py")
    av_module.library_versions = {"libavutil": (60, 26, 101)}  # type: ignore[attr-defined]
    av_module.open = open_fixture  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "av", av_module)
    monkeypatch.setitem(sys.modules, "faster_whisper", types.ModuleType("faster_whisper"))
    monkeypatch.setitem(sys.modules, "huggingface_hub", types.ModuleType("huggingface_hub"))

    versions = {
        "av": "17.1.0",
        "faster-whisper": "1.2.1",
        "huggingface-hub": "1.21.0",
    }
    monkeypatch.setattr(importlib.metadata, "version", lambda name: versions[name])

    class Distribution:
        files = [Path("av-17.1.0.dist-info/licenses/LICENSE.txt")]
        metadata = {"License-Expression": "BSD-3-Clause"}

        def locate_file(self, _path: Path) -> Path:
            return license_file

    monkeypatch.setattr(importlib.metadata, "distribution", lambda _name: Distribution())

    class RuntimeSymbol:
        restype: object = None

        def __init__(self, value: bytes) -> None:
            self.value = value

        def __call__(self) -> bytes:
            return self.value

    runtime = SimpleNamespace(
        avutil_license=RuntimeSymbol(b"LGPL version 3 or later"),
        avutil_configuration=RuntimeSymbol(b"--disable-static --enable-shared"),
        av_version_info=RuntimeSymbol(b"8.1.1"),
    )
    monkeypatch.setattr(receipt.ctypes, "CDLL", lambda _path: runtime)

    original_read_bytes = Path.read_bytes
    replaced = False

    def replacing_read_bytes(path: Path) -> bytes:
        nonlocal replaced
        value = original_read_bytes(path)
        if path == fixture and not replaced:
            os.replace(replacement, fixture)
            replaced = True
        return value

    monkeypatch.setattr(Path, "read_bytes", replacing_read_bytes)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runtime-evidence-probe",
            str(fixture_root),
            json.dumps(versions, sort_keys=True, separators=(",", ":")),
        ],
    )

    exec(receipt._RUNTIME_EVIDENCE_SOURCE, {"__name__": "__main__"})  # noqa: S102

    payload = json.loads(capsys.readouterr().out)
    decodes = cast(list[dict[str, object]], payload["fixture_decodes"])
    assert replaced is True
    assert original_read_bytes(fixture) == replacement_bytes
    assert observed["decoded_bytes"] == original_bytes
    assert decodes == [
        {
            "decoder": "pyav",
            "filename": "direct-audio.wav",
            "sha256": hashlib.sha256(original_bytes).hexdigest(),
            "status": "passed",
            "stream_count": 1,
        }
    ]


def test_generation_cli_writes_only_validator_accepted_canonical_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    receipt = _module()
    _freeze_synthetic_darwin_cells(monkeypatch)
    evidence, preflight, generation_preflight = _complete_generation_bundle()
    output = tmp_path / "dependency-artifacts.json"
    captured: dict[str, object] = {}

    def generate(
        **kwargs: object,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        captured.update(kwargs)
        return evidence, preflight, generation_preflight

    monkeypatch.setattr(receipt, "generate_dependency_receipt", generate, raising=False)
    monkeypatch.setattr(receipt, "_controller_isolated", lambda: True)
    monkeypatch.setattr(
        receipt,
        "_controller_execution_projection",
        lambda *, require_bound: evidence["controller_execution"],
    )

    result = receipt.main(
        [
            "--python",
            "synthetic-python3.12",
            "--python",
            "synthetic-python3.13",
            "--wheelhouse",
            str(tmp_path / "wheelhouse"),
            "--lock",
            str(tmp_path / "uv.lock"),
            "--constraints",
            str(tmp_path / "constraints.txt"),
            "--fixture-root",
            str(tmp_path / "fixtures"),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    assert json.loads(output.read_text(encoding="ascii")) == evidence
    assert output.read_bytes() == (
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    )
    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    )["status"] == "passed"
    assert json.loads(capsys.readouterr().out) == {
        "receipt_sha256": evidence["receipt_sha256"],
        "status": "passed",
    }
    assert captured["pythons"] == (
        Path("synthetic-python3.12"),
        Path("synthetic-python3.13"),
    )


def test_generation_receipt_requires_schema_identity() -> None:
    receipt = _module()
    evidence, preflight, generation_preflight = _complete_generation_bundle()
    del evidence["schema_version"]
    _refresh_receipt_digest(evidence)

    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {
        "failure": "generation_evidence_incomplete",
        "status": "failed",
    }


def test_generation_receipt_rejects_unknown_schema_and_binds_it_in_digest() -> None:
    receipt = _module()
    evidence, preflight, generation_preflight = _complete_generation_bundle()
    original_digest = evidence["receipt_sha256"]
    evidence["schema_version"] = "mke.direct_audio_dependency_receipt.v2"
    _refresh_receipt_digest(evidence)

    assert evidence["receipt_sha256"] != original_digest
    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {
        "failure": "generation_evidence_invalid",
        "status": "failed",
    }


@pytest.mark.parametrize(
    "inventory",
    [
        "preflight_interpreters",
        "preflight_wheelhouse",
        "preflight_wheel_resolution",
        "preflight_fixtures",
        "generation_wheel_inventory",
        "generation_installed_distributions",
        "generation_cells",
        "cell_installed_distributions",
        "cell_imports",
        "cell_fixture_decodes",
        "generation_fixtures",
    ],
)
def test_generation_receipt_rejects_permuted_inventory_with_recomputed_digest(
    inventory: str,
) -> None:
    receipt = _module()
    evidence, preflight, generation_preflight = _complete_generation_bundle()
    original_digest = evidence["receipt_sha256"]
    if inventory.startswith("preflight_"):
        field = inventory.removeprefix("preflight_")
        for payload in (preflight, generation_preflight):
            cast(list[object], payload[field]).reverse()
            _refresh_preflight_digest(payload)
        evidence["preflight_observed_digest"] = preflight["observed_digest"]
        evidence["generation_preflight_observed_digest"] = generation_preflight["observed_digest"]
    elif inventory == "generation_wheel_inventory":
        cast(list[object], evidence["wheel_inventory"]).reverse()
    elif inventory == "generation_installed_distributions":
        cast(list[object], evidence["installed_distributions"]).reverse()
    elif inventory == "generation_cells":
        cast(list[object], evidence["cells"]).reverse()
    elif inventory == "generation_fixtures":
        cast(list[object], evidence["fixtures"]).reverse()
    else:
        cell = cast(list[dict[str, object]], evidence["cells"])[0]
        field = {
            "cell_installed_distributions": "installed_distributions",
            "cell_imports": "imports",
            "cell_fixture_decodes": "fixture_decodes",
        }[inventory]
        cast(list[object], cell[field]).reverse()
    _refresh_receipt_digest(evidence)

    assert evidence["receipt_sha256"] != original_digest
    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {
        "failure": "generation_evidence_invalid",
        "status": "failed",
    }


def test_positive_generation_wheels_match_the_production_filename_parser() -> None:
    receipt = _module()
    wheels = cast(list[dict[str, object]], _complete_generation_evidence()["wheel_inventory"])

    for wheel in wheels:
        assert receipt._parse_wheel_filename(cast(str, wheel["filename"])) == (
            wheel["distribution"],
            wheel["version"],
            wheel["build"],
            tuple(cast(list[str], wheel["python_tags"])),
            tuple(cast(list[str], wheel["abi_tags"])),
            tuple(cast(list[str], wheel["platform_tags"])),
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "cell_version_abi_mismatch",
        "duplicate_interpreter_digest",
        "wrong_sysconfig_platform",
        "arbitrary_script_sha",
        "invalid_wheel_filename_and_tags",
    ],
)
def test_generation_rejects_semantically_forged_runtime_authority(mutation: str) -> None:
    receipt = _module()
    evidence, preflight, generation_preflight = _complete_generation_bundle()
    preflights = (preflight, generation_preflight)
    if mutation == "cell_version_abi_mismatch":
        for payload in preflights:
            interpreter = cast(list[dict[str, object]], payload["interpreters"])[0]
            interpreter["python_version"] = "3.13.9"
            interpreter["soabi"] = "cpython-313-darwin"
            interpreter["ext_suffix"] = ".cpython-313-darwin.so"
            interpreter["cache_tag"] = "cpython-313"
    elif mutation == "duplicate_interpreter_digest":
        for payload in preflights:
            interpreters = cast(list[dict[str, object]], payload["interpreters"])
            interpreters[1]["executable_sha256"] = interpreters[0]["executable_sha256"]
    elif mutation == "wrong_sysconfig_platform":
        for payload in preflights:
            cast(list[dict[str, object]], payload["interpreters"])[0]["sysconfig_platform"] = (
                "linux-aarch64"
            )
    elif mutation == "arbitrary_script_sha":
        for payload in preflights:
            cast(dict[str, object], payload["script"])["script_sha256"] = "f" * 64
        cast(dict[str, object], evidence["controller_execution"])["script_sha256"] = "f" * 64
        evidence["script_sha256"] = "f" * 64
    else:
        original_filename = "av-17.1.0-cp312-cp312-macosx_11_0_arm64.whl"
        invalid_filename = "av-17.1.0-invalid.whl"
        for payload in preflights:
            wheel = cast(list[dict[str, object]], payload["wheelhouse"])[0]
            wheel["filename"] = invalid_filename
            wheel["python_tags"] = ["invalid"]
            wheel["abi_tags"] = ["invalid"]
            for resolution in cast(list[dict[str, object]], payload["wheel_resolution"]):
                if resolution["filename"] == original_filename:
                    resolution["filename"] = invalid_filename
        evidence_wheel = cast(list[dict[str, object]], evidence["wheel_inventory"])[0]
        evidence_wheel["filename"] = invalid_filename
        evidence_wheel["python_tags"] = ["invalid"]
        evidence_wheel["abi_tags"] = ["invalid"]
        for installed in cast(list[dict[str, object]], evidence["installed_distributions"]):
            if installed["source_wheel_filename"] == original_filename:
                installed["source_wheel_filename"] = invalid_filename
        for cell_row in cast(list[dict[str, object]], evidence["cells"]):
            for installed in cast(list[dict[str, object]], cell_row["installed_distributions"]):
                if installed["source_wheel_filename"] == original_filename:
                    installed["source_wheel_filename"] = invalid_filename
    if mutation in {
        "cell_version_abi_mismatch",
        "duplicate_interpreter_digest",
        "wrong_sysconfig_platform",
    }:
        authority_by_label = {
            row["label"]: row for row in cast(list[dict[str, object]], preflight["interpreters"])
        }
        for cell_row in cast(list[dict[str, object]], evidence["cells"]):
            cell_row["interpreter"] = dict(authority_by_label[f"python-{cell_row['cell']}"])
    for payload in preflights:
        _refresh_preflight_digest(payload)
    evidence["preflight_observed_digest"] = preflight["observed_digest"]
    evidence["generation_preflight_observed_digest"] = generation_preflight["observed_digest"]
    _refresh_receipt_digest(evidence)

    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {"failure": "generation_evidence_invalid", "status": "failed"}


@pytest.mark.parametrize(
    "mutation",
    [
        "pip_check_missing",
        "pip_check_failed",
        "pip_argv_drift",
        "pip_environment_drift",
        "root_requirements_staging_drift",
        "missing_cp313_cell",
        "missing_installed_distribution",
        "missing_import_proof",
        "missing_fixture_decode",
        "allocator_trigger_missing",
        "supervisor_cleanup_incomplete",
        "fixture_authority_document_drift",
    ],
)
def test_generation_requires_closed_runtime_authority(mutation: str) -> None:
    receipt = _module()
    evidence, preflight, generation_preflight = _complete_generation_bundle()
    cells = cast(list[dict[str, object]], evidence["cells"])
    pip = cast(dict[str, object], cells[0]["pip"])
    if mutation == "pip_check_missing":
        del pip["pip_check"]
    elif mutation == "pip_check_failed":
        pip["pip_check"] = "failed"
    elif mutation == "pip_argv_drift":
        cast(list[str], pip["argv"]).remove("--no-index")
    elif mutation == "pip_environment_drift":
        cast(dict[str, str], pip["environment"])["HTTPS_PROXY"] = "https://proxy.invalid"
    elif mutation == "root_requirements_staging_drift":
        cast(dict[str, object], pip["staging"])["root_requirements_sha256"] = "8" * 64
    elif mutation == "missing_cp313_cell":
        cells.pop()
    elif mutation == "missing_installed_distribution":
        cast(list[dict[str, object]], cells[0]["installed_distributions"]).pop()
    elif mutation == "missing_import_proof":
        cast(list[dict[str, object]], cells[0]["imports"]).pop()
    elif mutation == "missing_fixture_decode":
        cast(list[dict[str, object]], cells[1]["fixture_decodes"]).pop()
    elif mutation == "allocator_trigger_missing":
        cast(dict[str, object], evidence["darwin_supervisor"])["controlled_allocator"] = "none"
    elif mutation == "supervisor_cleanup_incomplete":
        supervisor = cast(dict[str, object], evidence["darwin_supervisor"])
        cast(dict[str, object], supervisor["cleanup"])["process_group_absent"] = False
    else:
        cast(dict[str, object], evidence["fixture_authority_document"])["sha256"] = "8" * 64
    _refresh_receipt_digest(evidence)

    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {"failure": "generation_evidence_invalid", "status": "failed"}


@pytest.mark.parametrize("missing", ["cells", "darwin_supervisor", "fixture_authority_document"])
def test_generation_rejects_missing_top_level_runtime_evidence(missing: str) -> None:
    receipt = _module()
    evidence, preflight, generation_preflight = _complete_generation_bundle()
    del evidence[missing]

    assert receipt.validate_generation_evidence(
        evidence,
        preflight=preflight,
        generation_preflight=generation_preflight,
    ) == {"failure": "generation_evidence_incomplete", "status": "failed"}


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
        evidence["generation_preflight_observed_digest"] = generation_preflight["observed_digest"]
    elif mutation == "fixture_projection_drift":
        for payload in (preflight, generation_preflight):
            cast(list[dict[str, object]], payload["fixtures"])[0]["bytes"] = 1
            _refresh_preflight_digest(payload)
        evidence["preflight_observed_digest"] = preflight["observed_digest"]
        evidence["generation_preflight_observed_digest"] = generation_preflight["observed_digest"]
    else:
        cast(dict[str, object], generation_preflight["controller"])["python_version"] = "3.13.10"
        _refresh_preflight_digest(generation_preflight)
        evidence["generation_preflight_observed_digest"] = generation_preflight["observed_digest"]

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
        "hostname_unresolved_suffix",
        "private_ffmpeg_configuration",
        "private_ffmpeg_runtime_license_label",
        "hostname_ffmpeg_runtime_license_label",
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
    elif mutation == "hostname_unresolved_suffix":
        unresolved[0]["observed_dylib_suffix"] = "build-host.internal"
    elif mutation == "private_ffmpeg_configuration":
        ffmpeg["configuration"] = "--prefix=/Users/operator/private/build"
    elif mutation == "private_ffmpeg_runtime_license_label":
        ffmpeg["runtime_license_label"] = "/Users/operator/private/LICENSE"
    elif mutation == "hostname_ffmpeg_runtime_license_label":
        ffmpeg["runtime_license_label"] = "build-host.internal"
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
        duplicate["observed_dylib_suffix"] = "2"
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
        "ffmpeg_unknown_runtime_license_label",
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
    elif mutation == "ffmpeg_unknown_runtime_license_label":
        cast(dict[str, object], evidence["ffmpeg_runtime"])["runtime_license_label"] = "unknown"
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


def test_main_redacts_unexpected_controller_failure_to_one_closed_json_object(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    receipt = _module()
    monkeypatch.setattr(receipt, "_controller_isolated", lambda: True)
    monkeypatch.setattr(
        receipt,
        "_controller_execution_projection",
        lambda *, require_bound: {},
    )

    def fail_closed(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("private failure at /Users/operator/secret")

    monkeypatch.setattr(receipt, "check_inputs", fail_closed)

    result = receipt.main(
        [
            "--check-inputs",
            "--python",
            "python3.12",
            "--python",
            "python3.13",
            "--wheelhouse",
            "wheelhouse",
            "--lock",
            "uv.lock",
            "--constraints",
            "constraints.txt",
            "--fixture-root",
            "fixtures",
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert result == 2
    assert json.loads(captured.out) == {
        "failure": "receipt_controller_failed",
        "status": "failed",
    }
    assert captured.err == ""
    assert "Traceback" not in captured.out
    assert "/Users/" not in captured.out


def test_main_closes_argument_errors_without_usage_or_private_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    receipt = _module()

    result = receipt.main(["--check-inputs", "--python", "/Users/operator/private-python"])
    captured = capsys.readouterr()

    assert result == 2
    assert json.loads(captured.out) == {
        "failure": "cli_arguments_invalid",
        "status": "failed",
    }
    assert captured.err == ""
    assert "usage:" not in captured.out
    assert "/Users/" not in captured.out
