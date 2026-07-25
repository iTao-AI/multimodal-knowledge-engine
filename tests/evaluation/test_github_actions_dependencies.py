from pathlib import Path

import pytest

CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_UV = "astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9"
SETUP_PYTHON = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"

WORKFLOW_ACTIONS = {
    Path(".github/workflows/ci.yml"): (
        CHECKOUT,
        SETUP_UV,
        SETUP_PYTHON,
        CHECKOUT,
        SETUP_UV,
        SETUP_PYTHON,
    ),
    Path(".github/workflows/compiled-library-export-proof.yml"): (
        CHECKOUT,
        SETUP_UV,
        SETUP_PYTHON,
        SETUP_PYTHON,
    ),
    Path(".github/workflows/consumer-source-pack-proof.yml"): (
        CHECKOUT,
        SETUP_UV,
        SETUP_PYTHON,
        SETUP_PYTHON,
    ),
    Path(".github/workflows/mcp-context-completeness-proof.yml"): (
        CHECKOUT,
        SETUP_UV,
        SETUP_PYTHON,
        SETUP_PYTHON,
    ),
}


@pytest.mark.parametrize(("workflow", "expected"), WORKFLOW_ACTIONS.items())
def test_workflow_uses_exact_current_action_inventory(
    workflow: Path,
    expected: tuple[str, ...],
) -> None:
    uses = tuple(
        line.strip().split("uses: ", 1)[1].split(" # ", 1)[0]
        for line in workflow.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith(("- uses:", "uses:"))
    )

    assert uses == expected


@pytest.mark.parametrize("workflow", WORKFLOW_ACTIONS)
def test_setup_uv_v9_preserves_bounded_cache_pruning(workflow: Path) -> None:
    lines = workflow.read_text(encoding="utf-8").splitlines()
    setup_indexes = [index for index, line in enumerate(lines) if SETUP_UV in line]
    assert setup_indexes

    for index in setup_indexes:
        step_indent = len(lines[index]) - len(lines[index].lstrip())
        block: list[str] = []
        for line in lines[index + 1 :]:
            indent = len(line) - len(line.lstrip())
            if line.strip() and indent <= step_indent:
                break
            block.append(line.strip())
        assert "with:" in block
        assert "prune-cache: true" in block
