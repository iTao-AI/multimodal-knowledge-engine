from __future__ import annotations

import copy
import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tests/fixtures/consumer-source-pack-v1/manifest.json"
SCHEMAS = ROOT / "tests/fixtures/consumer-source-pack-v1/mcp-tool-schemas.json"
LOCAL_FIXTURE_ROOT = ROOT / "tests/fixtures/local-knowledge-v1"
CLIENT_PATH = ROOT / "scripts/consumer_source_pack_client.py"


def _load_client() -> ModuleType:
    spec = importlib.util.spec_from_file_location("consumer_source_pack_client", CLIENT_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load standalone client: {CLIENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


client = _load_client()


def _manifest_payload() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _write_manifest(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _is_frozen_dataclass(value: object) -> bool:
    value_type = cast(Any, type(value))
    return bool(value_type.__dataclass_params__.frozen)


def _delete_top_level(payload: dict[str, object]) -> None:
    del payload["pack_id"]


def _add_top_level(payload: dict[str, object]) -> None:
    payload["unexpected"] = True


def _unknown_schema(payload: dict[str, object]) -> None:
    payload["schema_version"] = "mke.consumer_source_pack_manifest.v2"


def _missing_source_field(payload: dict[str, object]) -> None:
    del payload["sources"][0]["media_type"]  # type: ignore[index]


def _extra_source_field(payload: dict[str, object]) -> None:
    payload["sources"][0]["unexpected"] = True  # type: ignore[index]


def _duplicate_source_key(payload: dict[str, object]) -> None:
    payload["sources"][1]["source_key"] = payload["sources"][0]["source_key"]  # type: ignore[index]


def _duplicate_filename(payload: dict[str, object]) -> None:
    payload["sources"][1]["relative_filename"] = payload["sources"][0][  # type: ignore[index]
        "relative_filename"
    ]


def _bool_bytes(payload: dict[str, object]) -> None:
    payload["sources"][0]["bytes"] = True  # type: ignore[index]


def _uppercase_digest(payload: dict[str, object]) -> None:
    payload["sources"][0]["sha256"] = str(  # type: ignore[index]
        payload["sources"][0]["sha256"]  # type: ignore[index]
    ).upper()


def _malformed_digest(payload: dict[str, object]) -> None:
    payload["sources"][0]["sha256"] = "abc"  # type: ignore[index]


def _absolute_path(payload: dict[str, object]) -> None:
    payload["sources"][0]["relative_filename"] = "/operations-guide.pdf"  # type: ignore[index]


def _parent_traversal(payload: dict[str, object]) -> None:
    payload["sources"][0]["relative_filename"] = "../operations-guide.pdf"  # type: ignore[index]


def _non_normalized_path(payload: dict[str, object]) -> None:
    payload["sources"][0]["relative_filename"] = "guides/../operations-guide.pdf"  # type: ignore[index]


def _duplicate_query_role(payload: dict[str, object]) -> None:
    payload["queries"][1]["role"] = payload["queries"][0]["role"]  # type: ignore[index]


def _invalid_locator_range(payload: dict[str, object]) -> None:
    payload["queries"][0]["allowed_locator_range"] = [2, 1]  # type: ignore[index]


def _positive_query_shape_mismatch(payload: dict[str, object]) -> None:
    del payload["queries"][0]["expected_source_key"]  # type: ignore[index]


def _unsupported_query_shape_mismatch(payload: dict[str, object]) -> None:
    payload["queries"][2]["locator_kind"] = "page"  # type: ignore[index]


MANIFEST_MUTATIONS: tuple[tuple[str, Callable[[dict[str, object]], None]], ...] = (
    ("missing top-level field", _delete_top_level),
    ("extra top-level field", _add_top_level),
    ("unknown schema", _unknown_schema),
    ("missing source field", _missing_source_field),
    ("extra source field", _extra_source_field),
    ("duplicate source key", _duplicate_source_key),
    ("duplicate filename", _duplicate_filename),
    ("bool byte count", _bool_bytes),
    ("uppercase digest", _uppercase_digest),
    ("malformed digest", _malformed_digest),
    ("absolute path", _absolute_path),
    ("parent traversal", _parent_traversal),
    ("non-normalized relative path", _non_normalized_path),
    ("duplicate query role", _duplicate_query_role),
    ("invalid locator range", _invalid_locator_range),
    ("positive query shape mismatch", _positive_query_shape_mismatch),
    ("unsupported query shape mismatch", _unsupported_query_shape_mismatch),
)


def test_load_source_pack_manifest() -> None:
    pack = client.load_source_pack(MANIFEST)

    assert pack.schema_version == "mke.consumer_source_pack_manifest.v1"
    assert pack.pack_id == "local-knowledge-v1"
    assert {source.source_key for source in pack.sources} == {
        "operations_guide",
        "incident_guide",
    }
    assert {query.query for query in pack.queries} == {
        "Cedar Relay maintenance window",
        "Cedar Relay telemetry amber",
        "lunar payroll retention policy",
    }
    values = (client.ProofError("example"), pack, *pack.sources, *pack.queries)
    assert all(_is_frozen_dataclass(item) for item in values)


@pytest.mark.parametrize(("case", "mutate"), MANIFEST_MUTATIONS, ids=lambda value: str(value))
def test_load_source_pack_rejects_invalid_manifest(
    tmp_path: Path,
    case: str,
    mutate: Callable[[dict[str, object]], None],
) -> None:
    payload = copy.deepcopy(_manifest_payload())
    mutate(payload)

    with pytest.raises(client.ProofError) as exc_info:
        client.load_source_pack(_write_manifest(tmp_path, payload))

    assert exc_info.value.code == "source_pack_manifest_invalid", case


def test_verify_source_files_matches_manifest() -> None:
    pack = client.load_source_pack(MANIFEST)

    resolved = client.verify_source_files(pack, LOCAL_FIXTURE_ROOT)

    assert resolved.keys() == {"operations_guide", "incident_guide"}
    assert resolved == {
        "operations_guide": LOCAL_FIXTURE_ROOT / "operations-guide.pdf",
        "incident_guide": LOCAL_FIXTURE_ROOT / "incident-guide.pdf",
    }


@pytest.mark.parametrize("mismatch", ["missing", "extra", "bytes", "sha256"])
def test_verify_source_files_rejects_identity_mismatch(tmp_path: Path, mismatch: str) -> None:
    pack = client.load_source_pack(MANIFEST)
    for source in pack.sources:
        source_path = LOCAL_FIXTURE_ROOT / source.relative_filename
        (tmp_path / source.relative_filename).write_bytes(source_path.read_bytes())
    if mismatch == "missing":
        (tmp_path / "incident-guide.pdf").unlink()
    elif mismatch == "extra":
        (tmp_path / "extra.pdf").write_bytes(b"extra")
    elif mismatch == "bytes":
        (tmp_path / "operations-guide.pdf").write_bytes(b"wrong length")
    else:
        data = bytearray((tmp_path / "operations-guide.pdf").read_bytes())
        data[0] ^= 1
        (tmp_path / "operations-guide.pdf").write_bytes(data)

    with pytest.raises(client.ProofError) as exc_info:
        client.verify_source_files(pack, tmp_path)

    assert exc_info.value.code == "source_pack_identity_mismatch"


def test_load_schema_expectations_returns_closed_fixture() -> None:
    expected = client.load_schema_expectations(SCHEMAS)

    assert set(expected) == {"schema_version", "public_error_contract", "tools"}
    assert expected["schema_version"] == "mke.consumer_mcp_tool_expectations.v1"
    assert set(expected["tools"]) == {
        "ask_library",
        "ask_library_v1",
        "get_run",
        "ingest_file",
        "list_libraries",
        "list_libraries_v1",
        "search_library",
        "search_library_v1",
    }
