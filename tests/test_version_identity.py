from __future__ import annotations

import tomllib
from pathlib import Path

import mke


def test_package_version_identity_is_v0_1_0() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == "0.1.0"
    assert mke.__version__ == "0.1.0"
    assert pyproject["project"]["version"] == mke.__version__
