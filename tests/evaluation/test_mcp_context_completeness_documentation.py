from __future__ import annotations

import asyncio
import re
from pathlib import Path

from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import build_mcp_server
from mke.runtime import RuntimeConfig

REFERENCE = Path("docs/reference/mcp-contract.md")
CONTRACTS = Path("docs/reference/contracts.md")
HOW_TO = Path("docs/how-to/use-mke-mcp.md")
PROOF = Path("docs/how-to/run-mcp-context-completeness-proof.md")
CLI = Path("docs/reference/cli.md")
VERIFY = Path("docs/how-to/verify-release.md")
RELEASE = Path("docs/releases/v0.1.6.md")

STABLE_PROOF_CODES = (
    "candidate_artifact_invalid",
    "cleanup_failed",
    "cli_ask_failed",
    "cli_ingest_failed",
    "cli_search_failed",
    "command_could_not_start",
    "command_failed",
    "command_output_exceeded",
    "command_timed_out",
    "consumer_failed",
    "consumer_payload_invalid",
    "consumer_proof_failed",
    "consumer_schema_invalid",
    "consumer_smoke_failed",
    "demo_failed",
    "environment_create_failed",
    "external_isolation_failed",
    "fixture_setup_failed",
    "fixture_unavailable",
    "install_failed",
    "installed_identity_failed",
    "locked_constraints_mismatch",
    "locked_constraints_unavailable",
    "manifest_locator_mismatch",
    "manifest_mapping_ambiguous",
    "manifest_mapping_missing",
    "mcp_contract_failed",
    "mcp_startup_timeout",
    "mcp_tool_timeout",
    "mcp_transport_failed",
    "observation_state_mismatch",
    "producer_failed",
    "proof_failed",
    "python_interpreter_unavailable",
    "retrieval_order_publication_durability_unconfirmed",
    "retrieval_order_publication_failed_before_visibility",
    "retrieval_order_source_pack_already_started",
    "retrieval_order_source_pack_attempt_terminal",
    "retrieval_order_source_pack_claim_invalid",
    "runtime_root_inside_repository",
    "server_exit_nonzero",
    "source_pack_identity_mismatch",
    "source_pack_manifest_invalid",
    "venv_failed",
    "wheel_build_failed",
    "wheel_invalid",
    "wheel_unavailable",
)

EXPECTED_MCP_TOOL_NAMES = (
    "ask_library",
    "ask_library_v1",
    "get_run",
    "ingest_file",
    "list_libraries",
    "list_libraries_v1",
    "read_evidence_v1",
    "search_library",
    "search_library_v1",
    "search_library_v2",
)


def _documented_mcp_inventory(text: str) -> tuple[str, ...]:
    marker = "MKE exposes exactly ten tools:\n\n"
    section = text.split(marker, maxsplit=1)[1]
    block = section.split("\n\n", maxsplit=1)[0]
    return tuple(re.findall(r"^- `([^`]+)`$", block, flags=re.MULTILINE))


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


def test_public_contracts_mcp_summary_matches_live_canonical_ten_tool_inventory(
    tmp_path: Path,
) -> None:
    server = build_mcp_server(
        McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path)
    )
    live_inventory = tuple(sorted(tool.name for tool in asyncio.run(server.list_tools())))
    canonical = _documented_mcp_inventory(REFERENCE.read_text(encoding="utf-8"))
    summary = _documented_mcp_inventory(CONTRACTS.read_text(encoding="utf-8"))

    assert live_inventory == EXPECTED_MCP_TOOL_NAMES
    assert tuple(sorted(canonical)) == live_inventory
    assert tuple(sorted(summary)) == live_inventory
    stale = CONTRACTS.read_text(encoding="utf-8").casefold()
    assert "status: partially implemented" not in stale
    assert "implemented tools:" not in stale
    assert "five-tool" not in stale
    assert "five tools" not in stale
    assert "[mcp contract reference](./mcp-contract.md)" in stale


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
    for tool in (
        "list_libraries", "ingest_file", "get_run", "search_library", "ask_library",
        "list_libraries_v1", "search_library_v1", "ask_library_v1",
        "search_library_v2", "read_evidence_v1",
    ):
        assert tool in cli
    assert "mke --db <library.sqlite3> mcp --allowed-root <directory>" in cli
    assert "mke --db <path> mcp" in cli
    assert "mke mcp --db <path>" not in cli


def test_stable_proof_code_table_has_exact_inventory_and_bounded_actions() -> None:
    text = VERIFY.read_text(encoding="utf-8")
    section = text.split("## Stable proof code recovery", maxsplit=1)[1].split(
        "## Stage 1", maxsplit=1
    )[0]
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.startswith("| `")
    ]

    assert rows
    assert all(len(row) == 4 for row in rows)
    assert tuple(row[0].strip("`") for row in rows) == STABLE_PROOF_CODES
    assert all(all(cell for cell in row[1:]) for row in rows)
    assert "| code | problem | likely cause | bounded next action |" in section
    assert "proof JSON remains exactly `{\"status\",\"code\"}` on failure" in section

    actions = {row[0].strip("`"): row[3] for row in rows}
    assert "Restore the documented fixture" in actions["fixture_setup_failed"]
    assert "Recreate the isolated environment" in actions["venv_failed"]
    for code in STABLE_PROOF_CODES:
        if code.startswith("retrieval_order_source_pack_") or code.startswith(
            "retrieval_order_publication_"
        ):
            assert "Historical maintenance only" in actions[code]


def test_current_release_workflow_precedes_immutable_history_and_is_v016_exact() -> None:
    text = VERIFY.read_text(encoding="utf-8")
    stage_1 = text.index("## Stage 1 Release Candidate Readiness")
    stage_4 = text.index("## Stage 4 Tag, GitHub Release, And Archive Smoke")
    history = text.index("## Completed v0.1.5 Release Record")
    current = text[stage_1:history]

    assert stage_1 < stage_4 < history
    assert 'candidate_output="${candidate_parent}/mke-v0.1.6-candidate"' in current
    assert 'receipt["package_version"] == project["version"] == "0.1.6"' in current
    assert "installed `mke.__version__` and package metadata both equal `0.1.6`" in current
    assert "gh release download v0.1.6" in current
    assert "multimodal-knowledge-engine-v0.1.6.tar.gz" in current
    assert "cd multimodal-knowledge-engine-0.1.6" in current


def test_current_candidate_proofs_bind_both_lanes_exact_wheel_and_offline_commands() -> None:
    text = VERIFY.read_text(encoding="utf-8")
    current = text[
        text.index("## Stage 1 Release Candidate Readiness") :
        text.index("## Completed v0.1.5 Release Record")
    ]

    assert current.count("scripts/release_consumer_smoke.py") >= 3
    assert '--python "${PYTHON312}"' in current
    assert '--python "${PYTHON313}"' in current
    assert '--mke-wheel "${candidate_wheel}"' in current
    assert (
        "UV_OFFLINE=1 uv run python scripts/release_consumer_smoke.py \\\n"
        "  --wheel dist/multimodal_knowledge_engine-0.1.6-py3-none-any.whl --json"
        in current
    )
    for line in current.splitlines():
        if line.startswith(("uv run ", "uv build", "uv sync ")):
            raise AssertionError(f"cache-warmed proof command lacks UV_OFFLINE=1: {line}")

    release = RELEASE.read_text(encoding="utf-8")
    try_it = release.split("## Try it", maxsplit=1)[1].split(
        "## Upgrade from v0.1.4", maxsplit=1
    )[0]
    for line in try_it.splitlines():
        if line.startswith(("uv run ", "uv build", "uv sync ")):
            raise AssertionError(f"release Try-it command lacks UV_OFFLINE=1: {line}")


def test_all_primary_mcp_documentation_surfaces_route_the_current_contract() -> None:
    requirements = {
        Path("README.md"): ("v0.1.6", "search_library_v2", "read_evidence_v1"),
        Path("README_CN.md"): ("v0.1.6", "search_library_v2", "read_evidence_v1"),
        Path("docs/README.md"): ("v0.1.6", "MCP", "exact active Evidence"),
        Path("docs/tutorials/getting-started.md"): (
            "search_library_v2",
            "read_evidence_v1",
            "evidence_text_sha256",
        ),
        HOW_TO: ("search_library_v2", "read_evidence_v1", "more_available"),
        PROOF: ("ten-tool", "Python 3.12", "Python 3.13", "UV_OFFLINE=1"),
        CLI: ("ten-tool", "search_library_v2", "read_evidence_v1"),
        VERIFY: ("v0.1.6", "Stable proof code recovery", "Stage 4"),
        RELEASE: ("v0.1.6", "search_library_v2", "read_evidence_v1"),
        REFERENCE: ("exactly ten tools", "search_library_v2", "read_evidence_v1"),
    }
    for path, literals in requirements.items():
        text = path.read_text(encoding="utf-8")
        for literal in literals:
            assert literal in text, f"{path} is missing {literal!r}"


def test_current_presentation_links_and_runtime_boundary_are_v016_authoritative() -> None:
    assert "- [Release notes](./docs/releases/v0.1.6.md)" in Path("README.md").read_text(
        encoding="utf-8"
    )
    assert "- [Release notes](./docs/releases/v0.1.6.md)" in Path(
        "README_CN.md"
    ).read_text(encoding="utf-8")
    docs_index = Path("docs/README.md").read_text(encoding="utf-8")
    assert "v0.1.6 retains the historical v0.1.4 runtime boundary" in docs_index

    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    current = changelog.split("## [0.1.6]", maxsplit=1)[1].split(
        "## [0.1.5]", maxsplit=1
    )[0]
    assert current.count("### Added") == 1
    assert "No release" not in current


def test_v016_release_note_documents_atomic_pdf_publication_repair() -> None:
    assert RELEASE.is_file()
    text = RELEASE.read_text(encoding="utf-8")
    for literal in (
        "atomic",
        "PdfIntakeReport",
        "failed extraction",
        "FAILED",
        "active Publication",
        "unchanged",
        "no schema",
        "no dependency",
    ):
        assert literal in text
