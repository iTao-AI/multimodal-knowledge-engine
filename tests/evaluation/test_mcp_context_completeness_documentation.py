from __future__ import annotations

from pathlib import Path

REFERENCE = Path("docs/reference/mcp-contract.md")
HOW_TO = Path("docs/how-to/use-mke-mcp.md")
PROOF = Path("docs/how-to/run-mcp-context-completeness-proof.md")
CLI = Path("docs/reference/cli.md")
VERIFY = Path("docs/how-to/verify-release.md")


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


def test_mcp_reference_documents_stable_locator_recovery_and_id_boundary() -> None:
    text = REFERENCE.read_text(encoding="utf-8")
    prose = " ".join(text.split())

    for literal in (
        "`stable_locator_identity`",
        "`retrieval_authority_invalid`",
        "active retrieval candidates contain duplicate stable "
        "Evidence locators",
        "`restore_valid_database_or_reingest_into_new_database`",
        "`unchanged`",
    ):
        assert literal in text
    assert (
        "Opaque Evidence IDs are addressing identity, not ranking "
        "authority and not a cross-strategy display-order promise."
        in prose
    )


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


def test_current_cli_inventory_and_release_proof_codes_are_complete() -> None:
    cli = CLI.read_text(encoding="utf-8")
    verify = VERIFY.read_text(encoding="utf-8")
    for tool in (
        "list_libraries", "ingest_file", "get_run", "search_library", "ask_library",
        "list_libraries_v1", "search_library_v1", "ask_library_v1",
        "search_library_v2", "read_evidence_v1",
    ):
        assert tool in cli
    for code in (
        "candidate_artifact_invalid",
        "fixture_setup_failed",
        "venv_failed",
        "wheel_unavailable",
    ):
        assert code in verify
    assert "mke --db <library.sqlite3> mcp --allowed-root <directory>" in cli
