from __future__ import annotations

import copy
import importlib.util
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from scripts.consumer_source_pack_client import DiscoveredTool

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


def _write_schema_expectations(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "mcp-tool-schemas.json"
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


def _drift_source_key(payload: dict[str, object]) -> None:
    payload["sources"][0]["source_key"] = "operations_manual"  # type: ignore[index]
    payload["queries"][0]["expected_source_key"] = "operations_manual"  # type: ignore[index]


def _drift_source_filename(payload: dict[str, object]) -> None:
    payload["sources"][0]["relative_filename"] = "operations-manual.pdf"  # type: ignore[index]


def _drift_source_media_type(payload: dict[str, object]) -> None:
    payload["sources"][0]["media_type"] = "application/x-pdf"  # type: ignore[index]


def _drift_source_bytes(payload: dict[str, object]) -> None:
    payload["sources"][0]["bytes"] = 1001  # type: ignore[index]


def _drift_source_sha256(payload: dict[str, object]) -> None:
    payload["sources"][0]["sha256"] = "1" * 64  # type: ignore[index]


def _drift_source_redistribution_class(payload: dict[str, object]) -> None:
    payload["sources"][0]["redistribution_class"] = "redistributable"  # type: ignore[index]


def _drift_source_generator_identity(payload: dict[str, object]) -> None:
    payload["sources"][0]["generator"] = "scripts/other_generator.py"  # type: ignore[index]


def _drift_query_role(payload: dict[str, object]) -> None:
    payload["queries"][0]["role"] = "operations_manual"  # type: ignore[index]


def _drift_query_text(payload: dict[str, object]) -> None:
    payload["queries"][0]["query"] = "Cedar Relay service window"  # type: ignore[index]


def _drift_query_expected_source_key(payload: dict[str, object]) -> None:
    payload["queries"][0]["expected_source_key"] = "incident_guide"  # type: ignore[index]


def _drift_query_locator_kind(payload: dict[str, object]) -> None:
    payload["queries"][0]["locator_kind"] = "timestamp"  # type: ignore[index]


def _drift_query_locator_range(payload: dict[str, object]) -> None:
    payload["queries"][0]["allowed_locator_range"] = [2, 2]  # type: ignore[index]


def _drift_unsupported_query(payload: dict[str, object]) -> None:
    payload["queries"][2]["role"] = "out_of_scope"  # type: ignore[index]
    payload["queries"][2]["query"] = "lunar payroll archive policy"  # type: ignore[index]


def _drift_unsupported_search_state(payload: dict[str, object]) -> None:
    payload["queries"][2]["expected_search_status"] = "match"  # type: ignore[index]


def _drift_unsupported_ask_state(payload: dict[str, object]) -> None:
    payload["queries"][2]["expected_ask_status"] = "answered"  # type: ignore[index]


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


IDENTITY_DRIFT_MUTATIONS: tuple[tuple[str, Callable[[dict[str, object]], None]], ...] = (
    ("source key", _drift_source_key),
    ("source relative filename", _drift_source_filename),
    ("source media type", _drift_source_media_type),
    ("source bytes", _drift_source_bytes),
    ("source sha256", _drift_source_sha256),
    ("source redistribution class", _drift_source_redistribution_class),
    ("source generator identity", _drift_source_generator_identity),
    ("query role", _drift_query_role),
    ("query text", _drift_query_text),
    ("query expected source key", _drift_query_expected_source_key),
    ("query locator kind", _drift_query_locator_kind),
    ("query locator range", _drift_query_locator_range),
    ("unsupported query role and text", _drift_unsupported_query),
    ("unsupported search state", _drift_unsupported_search_state),
    ("unsupported ask state", _drift_unsupported_ask_state),
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


@pytest.mark.parametrize(("case", "mutate"), IDENTITY_DRIFT_MUTATIONS, ids=lambda value: str(value))
def test_load_source_pack_rejects_approved_identity_drift(
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("safe_causes", ["private provider detail"]),
        ("safe_causes", []),
        ("safe_causes", {}),
        ("machine_token_pattern", "^.*$"),
        ("active_publication_impact", "changed"),
    ],
)
def test_load_schema_expectations_rejects_error_contract_drift_atomically(
    tmp_path: Path, field: str, value: object
) -> None:
    fresh_client = _load_client()
    valid_error = {
        "schema_version": "mke.search_library_response.v1",
        "ok": False,
        "problem": "search_failed",
        "cause": "unknown run",
        "active_publication_impact": "unchanged",
        "next_step": "retry_search",
    }
    assert fresh_client.validate_search_response(valid_error) == valid_error
    payload = json.loads(SCHEMAS.read_text(encoding="utf-8"))
    payload["public_error_contract"][field] = value

    with pytest.raises(fresh_client.ProofError) as exc_info:
        fresh_client.load_schema_expectations(_write_schema_expectations(tmp_path, payload))

    assert exc_info.value.code == "tool_schema_expectations_invalid"
    assert fresh_client.validate_search_response(valid_error) == valid_error


def test_payload_safe_cause_validation_is_independent_of_expectations_load_order() -> None:
    fresh_client = _load_client()
    payload = {
        "schema_version": "mke.search_library_response.v1",
        "ok": False,
        "problem": "search_failed",
        "cause": "unknown run",
        "active_publication_impact": "unchanged",
        "next_step": "retry_search",
    }

    before = fresh_client.validate_search_response(payload)
    fresh_client.load_schema_expectations(SCHEMAS)
    after = fresh_client.validate_search_response(payload)

    assert before == after == payload


class FakeTool:
    def __init__(self, name: str, input_schema: Any, output_schema: Any) -> None:
        self.name = name
        self.inputSchema = input_schema
        self.outputSchema = output_schema


def _fixture_tools() -> list[FakeTool]:
    tools = cast(dict[str, dict[str, object]], client.load_schema_expectations(SCHEMAS)["tools"])
    return [
        FakeTool(name, schema["inputSchema"], schema["outputSchema"])
        for name, schema in tools.items()
    ]


def test_tool_schema_protocol_and_exact_fixture_validation() -> None:
    tools = _fixture_tools()
    typed: Sequence[DiscoveredTool] = tools
    expected = client.load_schema_expectations(SCHEMAS)

    assert client.normalize_discovered_tools(typed) == expected["tools"]
    client.validate_tool_schemas(typed, expected)


@pytest.mark.parametrize(
    "mutation", ["missing", "non_mapping", "duplicate", "unknown", "non_string_name"]
)
def test_normalize_discovered_tools_rejects_invalid_discovery(mutation: str) -> None:
    tools = _fixture_tools()
    if mutation == "missing":
        del tools[0].inputSchema
    elif mutation == "non_mapping":
        tools[0].inputSchema = []
    elif mutation == "duplicate":
        tools.append(tools[0])
    elif mutation == "non_string_name":
        tools[0].name = cast(Any, 42)
    else:
        tools[0].name = "replacement_tool"

    with pytest.raises(client.ProofError):
        if mutation == "unknown":
            client.validate_tool_schemas(tools, client.load_schema_expectations(SCHEMAS))
        else:
            client.normalize_discovered_tools(tools)


def test_tool_schema_validation_requires_all_v1_tools_and_legacy_exactness() -> None:
    expected = client.load_schema_expectations(SCHEMAS)
    tools = _fixture_tools()
    tools[:] = [tool for tool in tools if tool.name != "ask_library_v1"]
    with pytest.raises(client.ProofError):
        client.validate_tool_schemas(tools, expected)
    tools = _fixture_tools()
    cast(dict[str, object], tools[0].inputSchema)["extra"] = True
    with pytest.raises(client.ProofError):
        client.validate_tool_schemas(tools, expected)


def test_search_and_ask_evidence_schema_definitions_are_identical() -> None:
    tools = cast(dict[str, dict[str, object]], client.load_schema_expectations(SCHEMAS)["tools"])
    search = cast(dict[str, object], tools["search_library_v1"]["outputSchema"])
    ask = cast(dict[str, object], tools["ask_library_v1"]["outputSchema"])
    assert (
        cast(dict[str, object], search["$defs"])["EvidenceRefV1"]
        == cast(dict[str, object], ask["$defs"])["EvidenceRefV1"]
    )


def _observation() -> dict[str, object]:
    return {
        "schema_version": "mke.active_publication_observation.v1",
        "library_id": "local",
        "state": "active",
        "source_count": 1,
        "active_publication_count": 1,
        "active_evidence_count": 1,
    }


def _evidence() -> dict[str, object]:
    return {
        "schema_version": "mke.evidence_ref.v1",
        "evidence_id": "ev_" + "a" * 32,
        "source_id": "src_" + "b" * 32,
        "content_fingerprint": "sha256:" + "c" * 64,
        "publication_id": "pub_" + "d" * 32,
        "publication_revision": 1,
        "run_id": "run_" + "e" * 32,
        "locator": {"kind": "page", "start": 1, "end": 1},
        "text": "evidence",
    }


def _search() -> dict[str, object]:
    return {
        "schema_version": "mke.search_library_response.v1",
        "ok": True,
        "query": "q",
        "observation": _observation(),
        "results": [_evidence()],
    }


def _ask() -> dict[str, object]:
    return {
        "schema_version": "mke.ask_library_response.v1",
        "ok": True,
        "question": "q",
        "answer_status": "evidence_found",
        "summary": "s",
        "observation": _observation(),
        "evidence": [_evidence()],
        "limitations": [],
    }


def _list() -> dict[str, object]:
    return {
        "schema_version": "mke.list_libraries_response.v1",
        "ok": True,
        "observation": _observation(),
    }


@pytest.mark.parametrize("kind", ["list", "search", "ask"])
def test_payload_validators_accept_success_and_machine_token_errors(kind: str) -> None:
    validator = getattr(client, f"validate_{kind}_response")
    payload = {"list": _list, "search": _search, "ask": _ask}[kind]()
    assert validator(payload) == payload
    error = {
        "schema_version": f"mke.{kind}_libraries_response.v1"
        if kind == "list"
        else f"mke.{kind}_library_response.v1",
        "ok": False,
        "problem": "provider_failure_2",
        "cause": "query must not be empty",
        "active_publication_impact": "unchanged",
        "next_step": "retry_with_query_2",
    }
    if kind == "list":
        error["schema_version"] = "mke.list_libraries_response.v1"
    assert validator(error) == error


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "version",
        "bool_count",
        "bad_id",
        "bad_fingerprint",
        "revision",
        "locator",
        "state",
        "limit",
        "mixed",
    ],
)
def test_search_payload_mutations_are_rejected(mutation: str) -> None:
    payload = _search()
    if mutation == "missing":
        del payload["query"]
    elif mutation == "extra":
        payload["private_path"] = "/tmp/x"
    elif mutation == "version":
        payload["schema_version"] = "mke.search_library_response.v2"
    elif mutation == "bool_count":
        cast(dict[str, object], payload["observation"])["source_count"] = True
    elif mutation == "bad_id":
        cast(dict[str, object], cast(list[object], payload["results"])[0])["source_id"] = "src_no"
    elif mutation == "bad_fingerprint":
        cast(dict[str, object], cast(list[object], payload["results"])[0])[
            "content_fingerprint"
        ] = "sha256:" + "A" * 64
    elif mutation == "revision":
        cast(dict[str, object], cast(list[object], payload["results"])[0])[
            "publication_revision"
        ] = 0
    elif mutation == "locator":
        cast(dict[str, object], cast(list[object], payload["results"])[0])["locator"] = {
            "kind": "timestamp_ms",
            "start": -1,
            "end": 2,
        }
    elif mutation == "state":
        cast(dict[str, object], payload["observation"])["state"] = "empty"
    elif mutation == "limit":
        payload["results"] = [_evidence()] * 21
    else:
        payload["problem"] = "also_error"
    with pytest.raises(client.ProofError):
        client.validate_search_response(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("problem", "Bad token"),
        ("next_step", "_bad"),
        ("active_publication_impact", "changed"),
        ("cause", "secret provider error"),
    ],
)
def test_payload_error_contract_is_exact(field: str, value: str) -> None:
    payload = {
        "schema_version": "mke.search_library_response.v1",
        "ok": False,
        "problem": "search_failed",
        "cause": "query must not be empty",
        "active_publication_impact": "unchanged",
        "next_step": "retry_search",
    }
    payload[field] = value
    with pytest.raises(client.ProofError):
        client.validate_search_response(payload)


@pytest.mark.parametrize("cause", [[], {}, None, 7, True])
def test_payload_error_contract_rejects_non_string_cause_as_proof_error(cause: object) -> None:
    payload = {
        "schema_version": "mke.search_library_response.v1",
        "ok": False,
        "problem": "search_failed",
        "cause": cause,
        "active_publication_impact": "unchanged",
        "next_step": "retry_search",
    }

    with pytest.raises(client.ProofError) as exc_info:
        client.validate_search_response(payload)

    assert exc_info.value.code == "consumer_mcp_contract_invalid"


def test_list_and_ask_cross_field_invariants_and_projection() -> None:
    listing = _list()
    cast(dict[str, object], listing["observation"])["active_publication_count"] = 0
    with pytest.raises(client.ProofError):
        client.validate_list_response(listing)
    ask = _ask()
    ask["answer_status"] = "insufficient_evidence"
    with pytest.raises(client.ProofError):
        client.validate_ask_response(ask)
    search = _search()
    valid_ask = _ask()
    assert client.evidence_projection(search) == client.evidence_projection(valid_ask)
    cast(dict[str, object], cast(list[object], valid_ask["evidence"])[0])["text"] = "different"
    assert client.evidence_projection(search) != client.evidence_projection(valid_ask)
