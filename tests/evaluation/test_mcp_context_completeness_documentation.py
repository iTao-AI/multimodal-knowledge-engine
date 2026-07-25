from __future__ import annotations

from pathlib import Path

REFERENCE = Path("docs/reference/mcp-contract.md")
HOW_TO = Path("docs/how-to/use-mke-mcp.md")
PROOF = Path("docs/how-to/run-mcp-context-completeness-proof.md")


def test_canonical_reference_documents_complete_ten_tool_contract() -> None:
    text = REFERENCE.read_text(encoding="utf-8")
    for literal in (
        "search_library_v2",
        "read_evidence_v1",
        "two-dimensional completeness",
        "terminal but not exhaustive",
        "MKE tool-contract suffix",
        "active-Publication",
        "untrusted",
        "mke.search_library_response.v2",
        "mke.read_evidence_response.v1",
        "response_too_large",
        "next_step",
        "32,768",
        "96 KiB",
    ):
        assert literal in text


def test_user_how_to_has_absolute_quickstart_and_contract_boundaries() -> None:
    text = HOW_TO.read_text(encoding="utf-8")
    for literal in (
        "/ABSOLUTE/PATH/TO/INSTALLED/mke",
        "/ABSOLUTE/PATH/TO/mke.sqlite",
        "/ABSOLUTE/PATH/TO/library",
        "opaque",
        "read_evidence_v1",
        "deterministic Evidence convenience",
        "separate bounded delivery contract",
        "eight-tool",
        "ten-tool",
    ):
        assert literal in text


def test_proof_how_to_is_safe_and_public_neutral() -> None:
    text = PROOF.read_text(encoding="utf-8")
    for literal in (
        "mcp_context_completeness_proof.py",
        "Python 3.12",
        "Python 3.13",
        "UV_OFFLINE=1",
        "--constraints /ABSOLUTE/PATH/TO/mke-core-requirements.txt",
        "arbitrary external working directory",
        "installed_wheel",
        "Evidence or query text",
        "cursor",
        "database path",
        "username",
        "local filename",
        "private configuration",
        "production",
        "deployment",
        "adoption",
        "performance",
    ):
        assert literal in text
