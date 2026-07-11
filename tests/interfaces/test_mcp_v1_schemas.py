import asyncio
import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from mke.interfaces.mcp_contract import (
    McpRuntimeConfig,
    ask_library_v1,
    ingest_file,
    list_libraries_v1,
    search_library_v1,
)
from mke.interfaces.mcp_schemas import SearchLibraryResponseV1
from mke.interfaces.mcp_server import build_mcp_server
from mke.runtime import RuntimeConfig
from tests.conftest import PDF_FIXTURES


def _valid_search() -> dict[str, object]:
    return {
        "schema_version": "mke.search_library_response.v1",
        "ok": True,
        "query": "q",
        "observation": {
            "schema_version": "mke.active_publication_observation.v1",
            "library_id": "local",
            "state": "active",
            "source_count": 1,
            "active_publication_count": 1,
            "active_evidence_count": 1,
        },
        "results": [
            {
                "schema_version": "mke.evidence_ref.v1",
                "evidence_id": "ev_" + "a" * 32,
                "source_id": "src_" + "b" * 32,
                "content_fingerprint": "sha256:" + "c" * 64,
                "publication_id": "pub_" + "d" * 32,
                "publication_revision": 1,
                "run_id": "run_" + "e" * 32,
                "locator": {"kind": "page", "start": 1, "end": 1},
                "text": "x",
            }
        ],
    }


@pytest.mark.parametrize("mutation", ["extra", "version", "bool_count", "bad_locator"])
def test_search_response_rejects_malformed_payload(mutation: str) -> None:
    payload = _valid_search()
    if mutation == "extra":
        payload["path"] = "/tmp/private"
    elif mutation == "version":
        payload["schema_version"] = "mke.search_library_response.v2"
    elif mutation == "bool_count":
        payload["observation"]["source_count"] = True  # type: ignore[index]
    else:
        payload["results"][0]["locator"] = {"kind": "page", "start": 1, "end": 2}  # type: ignore[index]
    with pytest.raises(ValidationError):
        TypeAdapter(SearchLibraryResponseV1).validate_python(payload)


def test_v1_tools_have_closed_discriminated_output_schemas(tmp_path: Path) -> None:
    server = build_mcp_server(McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path))
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    assert set(tools) >= {"list_libraries_v1", "search_library_v1", "ask_library_v1"}
    for name in ("list_libraries_v1", "search_library_v1", "ask_library_v1"):
        schema = tools[name].outputSchema
        assert schema is not None
        assert "oneOf" in schema
        rendered = json.dumps(schema, sort_keys=True)
        assert '"additionalProperties": false' in rendered
        assert '"const": true' in rendered and '"const": false' in rendered


def test_v1_search_and_ask_return_same_evidence_projection(tmp_path: Path) -> None:
    config = McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), PDF_FIXTURES)
    assert list_libraries_v1(config).root.observation.state == "empty"  # type: ignore[union-attr]
    assert ingest_file(config, "text-layer.pdf")["ok"] is True
    search = search_library_v1(config, "publication active")
    ask = ask_library_v1(config, "publication active")
    assert search.root.ok is True and ask.root.ok is True
    assert search.root.results == ask.root.evidence  # type: ignore[union-attr]
