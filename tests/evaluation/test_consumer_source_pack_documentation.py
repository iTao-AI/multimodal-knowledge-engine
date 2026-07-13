import re
from collections.abc import Callable
from pathlib import Path

import pytest

HOW_TO = Path("docs/how-to/run-consumer-source-pack-proof.md")
README = Path("README.md")
DOCS_INDEX = Path("docs/README.md")
SPEC = Path("docs/superpowers/specs/2026-07-12-consumer-ready-source-pack-proof-design.md")
PLAN = Path("docs/superpowers/plans/2026-07-12-consumer-ready-source-pack-proof-implementation.md")
PLAN_REVIEW = Path(
    "docs/superpowers/reviews/2026-07-12-consumer-ready-source-pack-proof-plan-review.md"
)
HOW_TO_LINK = "docs/how-to/run-consumer-source-pack-proof.md"
SUCCESS_FIELDS = frozenset(
    {
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
    }
)
FAILURE_CODES = frozenset(
    {
        "source_pack_manifest_invalid",
        "source_pack_identity_mismatch",
        "wheel_build_failed",
        "environment_create_failed",
        "install_failed",
        "installed_identity_failed",
        "external_isolation_failed",
        "consumer_schema_invalid",
        "consumer_payload_invalid",
        "manifest_mapping_missing",
        "manifest_mapping_ambiguous",
        "manifest_locator_mismatch",
        "observation_state_mismatch",
        "mcp_startup_timeout",
        "mcp_tool_timeout",
        "mcp_transport_failed",
        "server_exit_nonzero",
        "command_output_exceeded",
        "cleanup_failed",
        "proof_failed",
    }
)


def normalized(text: str) -> str:
    return " ".join(text.split())


def _backtick_tokens_between(text: str, start: str, end: str) -> frozenset[str] | None:
    match = re.search(
        re.escape(start) + r"(?P<body>.*?)" + re.escape(end),
        normalized(text),
        re.DOTALL,
    )
    if match is None:
        return None
    return frozenset(re.findall(r"`([a-z][a-z0-9_]*)`", match.group("body")))


def _consumer_navigation_paragraphs(text: str) -> list[str]:
    matches = re.findall(
        r"(?:^|\n)(?:The |- )\[Run The Consumer Source-Pack Proof\]\([^)]+\)"
        r".*?(?=\n\n|\Z)",
        text,
        flags=re.DOTALL,
    )
    return matches


def documentation_violations(how_to: str, readme: str, docs_index: str) -> list[str]:
    violations: list[str] = []
    success_fields = _backtick_tokens_between(
        how_to,
        "A successful command emits one JSON object with exactly these fields:",
        "The consumer validates",
    )
    if success_fields != SUCCESS_FIELDS:
        violations.append("success_fields")

    failure_codes = _backtick_tokens_between(
        how_to,
        "The stable codes are",
        "These are stable redacted failures",
    )
    if failure_codes != FAILURE_CODES:
        violations.append("failure_codes")

    readme_navigation = _consumer_navigation_paragraphs(readme)
    docs_navigation = _consumer_navigation_paragraphs(docs_index)
    if len(readme_navigation) != 1:
        violations.append("readme_navigation")
    if len(docs_navigation) != 1:
        violations.append("docs_navigation")

    scoped_text = normalized(
        "\n".join(
            (
                how_to,
                *readme_navigation,
                *docs_navigation,
            )
        )
    ).lower()
    for allowed_negative in (
        "not the tagged `v0.1.1` release wheel",
        "not a release artifact",
        "not a release gate",
        "not a pypi proof",
        "not a deployment",
        "not a production-readiness proof",
        "not a release verification step",
    ):
        scoped_text = scoped_text.replace(allowed_negative, "")
    for label, pattern in (
        ("v0.1.1_claim", r"`?v0\.1\.1`?"),
        ("release_artifact_claim", r"\brelease artifact\b"),
        ("release_gate_claim", r"\brelease gate\b"),
        ("pypi_claim", r"\bpypi\b"),
        ("deployment_claim", r"\bdeploy(?:ment|s|ed|ing)?\b"),
        ("production_claim", r"\bproduction[- ]readiness\b"),
        ("release_verification_claim", r"\brelease verification step\b"),
    ):
        if re.search(pattern, scoped_text, re.IGNORECASE):
            violations.append(label)
    return violations


def _add_success_field(text: str) -> str:
    return text.replace("and\n  `cleanup`.", "`cleanup`, and `unexpected_field`.")


def _add_failure_code(text: str) -> str:
    return text.replace(
        "`cleanup_failed`, and `proof_failed`.",
        "`cleanup_failed`, `proof_failed`, and `unexpected_code`.",
    )


def _add_v0_1_1_claim(text: str) -> str:
    return text + "\nThis is a `v0.1.1` capability.\n"


def _add_release_gate_claim(text: str) -> str:
    return text + "\nThis proof is a release gate.\n"


def _add_pypi_claim(text: str) -> str:
    return text + "\nThis is a PyPI proof.\n"


def _add_deployment_claim(text: str) -> str:
    return text + "\nThis proof deploys MKE.\n"


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


def test_consumer_source_pack_docs_state_exact_output_ownership_boundary() -> None:
    how_to = normalized(HOW_TO.read_text(encoding="utf-8"))
    assert "Controller subprocess stdout and stderr are hard bounded" in how_to
    assert "MCP server stderr is hard bounded" in how_to
    assert "Raw MCP stdout framing is owned by the official MCP SDK" in how_to
    assert "is not claimed to be hard-capped before SDK parsing" in how_to
    assert "Structured Search and Ask payloads are bounded after parsing" in how_to

    for path in (SPEC, PLAN, PLAN_REVIEW, HOW_TO):
        text = path.read_text(encoding="utf-8")
        assert "max_transport_bytes" not in text
        assert "--max-transport-bytes" not in text


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


@pytest.mark.parametrize(
    "mutation",
    (
        _add_success_field,
        _add_failure_code,
        _add_v0_1_1_claim,
        _add_release_gate_claim,
        _add_pypi_claim,
        _add_deployment_claim,
    ),
    ids=(
        "extra-success-field",
        "extra-failure-code",
        "affirmative-v0.1.1",
        "affirmative-release-gate",
        "affirmative-pypi",
        "affirmative-deploy",
    ),
)
def test_documentation_contract_rejects_mutations(mutation: Callable[[str], str]) -> None:
    how_to = HOW_TO.read_text(encoding="utf-8")
    mutated = mutation(how_to)

    assert mutated != how_to
    assert documentation_violations(
        mutated,
        README.read_text(encoding="utf-8"),
        DOCS_INDEX.read_text(encoding="utf-8"),
    )


def test_current_documentation_contract_has_no_violations() -> None:
    assert documentation_violations(
        HOW_TO.read_text(encoding="utf-8"),
        README.read_text(encoding="utf-8"),
        DOCS_INDEX.read_text(encoding="utf-8"),
    ) == []


@pytest.mark.parametrize(
    ("surface", "claim"),
    (
        (README, "This proof is a release gate."),
        (DOCS_INDEX, "This is a PyPI proof."),
    ),
    ids=("readme-release-gate", "docs-index-pypi"),
)
def test_navigation_contract_rejects_affirmative_claims(surface: Path, claim: str) -> None:
    original = surface.read_text(encoding="utf-8")
    mutated = original.replace(
        "without changing release claims.",
        claim,
    )
    assert mutated != original

    assert documentation_violations(
        HOW_TO.read_text(encoding="utf-8"),
        mutated if surface == README else README.read_text(encoding="utf-8"),
        mutated if surface == DOCS_INDEX else DOCS_INDEX.read_text(encoding="utf-8"),
    )
