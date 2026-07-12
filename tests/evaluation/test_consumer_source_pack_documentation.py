from pathlib import Path

HOW_TO = Path("docs/how-to/run-consumer-source-pack-proof.md")
README = Path("README.md")
DOCS_INDEX = Path("docs/README.md")
HOW_TO_LINK = "docs/how-to/run-consumer-source-pack-proof.md"


def normalized(text: str) -> str:
    return " ".join(text.split())


def test_consumer_source_pack_how_to_documents_exact_command_and_contract() -> None:
    text = HOW_TO.read_text(encoding="utf-8")
    prose = normalized(text)

    for required in (
        "scripts/consumer_source_pack_proof.py",
        "mke.consumer_source_pack_manifest.v1",
        "mke.evidence_ref.v1",
        "content_fingerprint",
        "Python 3.12",
        "Python 3.13",
        "source-built",
        "current source checkout",
        "What This Proves",
        "What This Does Not Prove",
        "official MCP SDK",
        "fresh environments",
        "lock-derived",
        "external working directory",
        "external consumer assets",
        "stable redacted failures",
        "shared OS principal",
        "OS sandbox",
    ):
        assert required in prose

    assert "UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py" in text
    assert '--python "$(command -v python3.12)"' in text
    assert '--python "$(command -v python3.13)"' in text
    assert "--json" in text
    assert "builds the current source checkout once" in prose
    assert "same wheel" in prose
    assert "prepared uv cache" in prose
    assert "online provisioning/prewarm step" in prose
    assert "empty machine" in prose
    assert "air-gapped" in prose


def test_consumer_source_pack_how_to_documents_closed_public_output() -> None:
    text = HOW_TO.read_text(encoding="utf-8")

    for success_field in (
        "proof",
        "status",
        "manifest_schema",
        "evidence_schema",
        "pack_id",
        "source_count",
        "published_run_count",
        "active_publication_count",
        "active_evidence_count",
        "observed_states",
        "installed_identity",
        "external_isolation",
        "strict_schema_validation",
        "search_ask_projection_equal",
        "exact_manifest_mapping",
        "fresh_store_mapping",
        "redaction",
        "cleanup",
    ):
        assert f"`{success_field}`" in text

    assert '{"status":"failed","code":"<stable_code>"}' in text
    assert "paths, identifiers, Evidence text, filenames, stderr, tracebacks" in text


def test_consumer_source_pack_navigation_is_minimal_and_discoverable() -> None:
    readme = README.read_text(encoding="utf-8")
    docs_index = DOCS_INDEX.read_text(encoding="utf-8")

    assert f"[Run The Consumer Source-Pack Proof](./{HOW_TO_LINK})" in readme
    assert "source-built proof for the current source checkout" in readme
    assert (
        "[Run The Consumer Source-Pack Proof](./how-to/run-consumer-source-pack-proof.md)"
        in docs_index
    )
    assert "source-built proof for the current source checkout" in docs_index


def test_consumer_source_pack_docs_preserve_non_release_boundary() -> None:
    text = normalized(
        "\n".join(
            (
                HOW_TO.read_text(encoding="utf-8"),
                README.read_text(encoding="utf-8"),
                DOCS_INDEX.read_text(encoding="utf-8"),
            )
        )
    )

    for required_boundary in (
        "not the tagged `v0.1.1` Release wheel",
        "not a Release artifact",
        "not a release gate",
        "not a PyPI proof",
        "not a deployment",
        "not a production-readiness proof",
        "not a release verification step",
    ):
        assert required_boundary in text
