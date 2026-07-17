from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
CONTRIBUTING_GUIDE = ROOT / "docs/how-to/contribute.md"
DOCS_INDEX = ROOT / "docs/README.md"
PR_TEMPLATE = ROOT / ".github/pull_request_template.md"
SUPERPOWERS_README = ROOT / "docs/superpowers/README.md"
RELEASE_DESIGN = ROOT / "docs/superpowers/specs/2026-07-17-v0-1-3-release-closeout-design.md"
RELEASE_PLAN = ROOT / "docs/superpowers/plans/2026-07-17-v0-1-3-release-closeout-implementation.md"
RELEASE_REVIEW = (
    ROOT / "docs/superpowers/reviews/2026-07-17-v0-1-3-release-implementation-review.md"
)
POST_RELEASE_REVIEW = (
    ROOT / "docs/superpowers/reviews/2026-07-17-v0-1-3-post-release-closeout.md"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized(path: Path) -> str:
    return " ".join(_text(path).split())


def test_default_pr_template_uses_plain_completed_fact_placeholders() -> None:
    text = _text(PR_TEMPLATE)

    for heading in (
        "## Summary",
        "## Completion",
        "## Verification",
        "## Documentation Impact",
    ):
        assert heading in text
    assert re.search(r"(?m)^\s*-\s*\[[ xX]\]", text) is None
    assert "ordinary bullets" in text
    assert "pending gates" in text


def test_agents_defines_conditional_parallel_and_controller_ownership() -> None:
    text = _normalized(AGENTS).lower()

    for required in (
        "at least two independent lanes",
        "clear file ownership",
        "independent verification",
        "one primary controller per phase",
        "parent agent owns shared contracts, integration, full verification, and the single "
        "terminal report",
        "gstack",
        "superpowers",
    ):
        assert required in text


def test_agents_defines_hosted_handoff_merge_and_cleanup_authority() -> None:
    text = _normalized(AGENTS).lower()

    for required in (
        "ready",
        "waiting",
        "blocked",
        "do not keep polling unchanged hosted state",
        "query the actual pull request and checks",
        "local workflow yaml is not hosted-state authority",
        "reviewed head",
        "checks head",
        "reviewed tree",
        "merge tree",
        "task-owned",
        "clean",
        "inactive",
        "results are retained",
        "read back the persisted title, body, base, head, and draft state",
    ):
        assert required in text


def test_contribution_docs_split_entry_point_from_executable_policy() -> None:
    entry = _text(CONTRIBUTING)
    guide = _normalized(CONTRIBUTING_GUIDE).lower()

    assert len(entry.splitlines()) < 20
    assert "docs/how-to/contribute.md" in entry
    for required in (
        "risk-based verification",
        "isolated worktree",
        "actual pull request and checks",
        "reviewed head",
        "merge tree",
        "persisted title, body, base, head, and draft state",
        "ordinary bullets",
        "pending gates",
        "task-owned",
    ):
        assert required in guide


def test_superpowers_workspace_is_history_not_current_contract_authority() -> None:
    text = _normalized(SUPERPOWERS_README).replace("`", "").lower()

    for required in (
        "artifact storage",
        "implementation history",
        "not current contract authority",
        "code and tests",
        "accepted adrs",
        "current reference documentation",
        "release documentation",
        "historical skill or subagent wording does not override the current agents.md",
    ):
        assert required in text


def test_docs_index_links_governance_and_completed_authorities() -> None:
    text = _text(DOCS_INDEX)
    normalized = " ".join(text.split())

    assert "[Superpowers Workspace](./superpowers/README.md)" in text
    assert "[ADR-0010](./decisions/0010-pdf-ocr-evaluation-manifest-fingerprint.md)" in text
    assert "post-merge operational gate pending" not in text
    assert "source-built proof for the current source checkout" in text
    assert "`v0.1.3` release-candidate verification gate" in normalized


def test_v013_closeout_docs_record_completed_docs_merge_and_cleanup() -> None:
    combined = "\n".join(
        _text(path)
        for path in (RELEASE_DESIGN, RELEASE_PLAN, RELEASE_REVIEW, POST_RELEASE_REVIEW)
    )
    normalized = " ".join(combined.split())

    assert "PR #74" in combined
    assert "reviewed docs tree" in normalized.lower()
    assert "merge tree" in normalized.lower()
    assert "tag and GitHub Release remained unchanged" in normalized
    assert "task-owned cleanup" in normalized
    for stale in (
        "post-release closeout pending review",
        "POST-RELEASE DOCS PENDING REVIEW",
        "DOCS CLOSURE PENDING REVIEW",
        "prepared locally for review",
        "branch is intentionally not pushed",
        "worktrees and branches remain intact",
    ):
        assert stale not in combined
    assert "- [x] **Step 7: Land docs-only post-release closeout**" in _text(RELEASE_PLAN)
    assert "- [x] **Step 8: Perform safe task-owned cleanup**" in _text(RELEASE_PLAN)


def test_relative_markdown_links_in_governance_docs_resolve() -> None:
    paths = (
        AGENTS,
        CONTRIBUTING,
        CONTRIBUTING_GUIDE,
        SUPERPOWERS_README,
        PR_TEMPLATE,
        DOCS_INDEX,
        RELEASE_DESIGN,
        RELEASE_PLAN,
        RELEASE_REVIEW,
        POST_RELEASE_REVIEW,
    )
    failures: list[str] = []
    for path in paths:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", _text(path)):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            relative = target.split("#", 1)[0]
            if relative and not (path.parent / relative).resolve().exists():
                failures.append(f"{path.relative_to(ROOT)} -> {target}")

    assert failures == []
