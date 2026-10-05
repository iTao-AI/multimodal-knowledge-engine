from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


@pytest.mark.parametrize("parent_name", ["checkout", ".codex"])
def test_sdist_excludes_local_execution_records_in_managed_checkout(
    tmp_path: Path, parent_name: str,
) -> None:
    root = tmp_path / parent_name / "project"
    root.mkdir(parents=True)
    for name in ("pyproject.toml", "README.md", ".gitignore"):
        shutil.copyfile(Path(name), root / name)
    package = root / "src/mke"
    package.mkdir(parents=True)
    shutil.copyfile(Path("src/mke/__init__.py"), package / "__init__.py")
    public = root / "docs/how-to/public-guide.md"
    public.parent.mkdir(parents=True)
    public.write_text("Public guide\n", encoding="utf-8")
    for name in ("artifacts/native-case/receipt.json", ".superpowers/sdd/progress.md"):
        marker = root / name
        marker.parent.mkdir(parents=True)
        marker.write_text("local execution record\n", encoding="utf-8")

    output = tmp_path / "sdist"
    built = subprocess.run(
        ["uv", "build", "--sdist", "--python", sys.executable, "--out-dir", str(output)],
        cwd=root, capture_output=True, text=True, check=False, timeout=60,
        env={**os.environ, "UV_PYTHON_DOWNLOADS": "never"},
    )
    assert built.returncode == 0, built.stdout + built.stderr
    archives = list(output.glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0]) as archive:
        members = {Path(*Path(item.name).parts[1:]).as_posix() for item in archive.getmembers()}
    assert "src/mke/__init__.py" in members
    assert "docs/how-to/public-guide.md" in members
    assert not any(name.startswith(("artifacts/", ".superpowers/")) for name in members)
