from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[2]


def _project() -> dict[str, object]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        payload = tomllib.load(handle)
    return payload["project"]  # type: ignore[return-value]


def _optional_dependencies() -> dict[str, list[str]]:
    return cast(dict[str, list[str]], _project()["optional-dependencies"])


def test_embedding_extra_has_exact_direct_dependency_boundary() -> None:
    optional = _optional_dependencies()

    assert optional["embedding"] == [
        "sentence-transformers==5.6.0",
        "sqlite-vec==0.1.9",
        "huggingface-hub>=1.21.0,<2",
    ]


def test_embedding_extra_does_not_add_provider_or_vector_service_sdks() -> None:
    serialized = "\n".join(
        dependency
        for group in _optional_dependencies().values()
        for dependency in group
    ).lower()

    assert "langchain" not in serialized
    assert "llama-index" not in serialized
    assert "qdrant" not in serialized
    assert "pymilvus" not in serialized
    assert "pgvector" not in serialized
    assert "openai" not in serialized


def test_core_and_embedding_contracts_import_with_optional_sdks_blocked() -> None:
    script = """
import builtins

blocked = ("sentence_transformers", "torch", "huggingface_hub", "sqlite_vec")
original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name in blocked or name.startswith(tuple(item + "." for item in blocked)):
        raise AssertionError(f"optional dependency imported: {name}")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
import mke
import mke.embeddings.contracts
"""

    subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
