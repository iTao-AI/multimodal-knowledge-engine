from __future__ import annotations

import tomllib
from pathlib import Path

import mke


def test_package_version_identity_is_v0_1_7() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == "0.1.7"
    assert mke.__version__ == "0.1.7"
    assert pyproject["project"]["version"] == mke.__version__
