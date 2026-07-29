from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.source_identity import (
    build_source_identity,
    read_no_follow_regular_file,
)


def test_direct_read_rejects_parent_and_final_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    real = root / "real"
    real.mkdir()
    (real / "source.py").write_bytes(b"source\n")
    (root / "parent-link").symlink_to(real, target_is_directory=True)
    (root / "file-link").symlink_to(real / "source.py")

    with pytest.raises(ValueError, match="source identity path is invalid"):
        read_no_follow_regular_file(root, "parent-link/source.py")
    with pytest.raises(ValueError, match="source identity path is invalid"):
        read_no_follow_regular_file(root, "file-link")


def test_direct_read_returns_descriptor_bound_identity(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "source.py"
    target.write_bytes(b"source\n")

    result = read_no_follow_regular_file(root, "source.py")

    assert result.content == b"source\n"
    assert result.identity == {
        "path": "source.py",
        "bytes": 7,
        "sha256": "b8bb034f9b63bd0254fbc7c157cae746c75853f4643d6cea844dc48ddb57f522",
    }
    assert result.physical_identity[0] == target.stat().st_dev
    assert result.physical_identity[1] == target.stat().st_ino


def test_source_identity_rejects_aliases_and_canonicalizes_inventory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.py").write_bytes(b"a")
    os.link(root / "a.py", root / "b.py")

    with pytest.raises(ValueError, match="physical aliases"):
        build_source_identity(root, ["a.py", "b.py"])
    (root / "b.py").unlink()
    (root / "b.py").write_bytes(b"b")
    identity = build_source_identity(root, ["b.py", "a.py"])
    files = cast(list[dict[str, object]], identity["files"])
    assert [item["path"] for item in files] == ["a.py", "b.py"]
    with pytest.raises(ValueError, match="paths are invalid"):
        build_source_identity(root, [])


def test_source_identity_rejects_capacity_before_file_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = False

    def fail_open(*args: object, **kwargs: object) -> int:
        nonlocal opened
        del args, kwargs
        opened = True
        raise AssertionError("file opened")

    monkeypatch.setattr(os, "open", fail_open)
    with pytest.raises(ValueError, match="capacity"):
        build_source_identity(tmp_path, [f"{index}.py" for index in range(1025)])
    assert opened is False
