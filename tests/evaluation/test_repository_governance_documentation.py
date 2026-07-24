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
V014_POST_RELEASE_REVIEW = (
    ROOT / "docs/superpowers/reviews/2026-07-23-v0-1-4-post-release-closeout.md"
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


def test_pr_body_final_reconciliation_is_fail_closed_across_governance_docs() -> None:
    agents = _normalized(AGENTS).lower()
    guide = _normalized(CONTRIBUTING_GUIDE).lower()
    template = _normalized(PR_TEMPLATE).lower()

    for text in (agents, guide, template):
        reconciliation = re.search(
            r"(?:reconcile the final pr body|during final reconciliation).{0,900}", text
        )
        assert reconciliation is not None
        contract = reconciliation.group(0)
        for required in (
            "[ ]",
            "[x]",
            "after merge",
            "before closeout",
            "actual checks",
            "authorization",
            "merge identity",
            "mergeability",
            "review blockers",
            "necessary links",
            "cleanup",
            "remaining risk",
            "non-claims",
            "persisted pr body",
            "write-back",
            "persisted-body readback",
            "exact blocker or pending trigger",
            "must not claim complete closeout",
        ):
            assert required in contract


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
    assert "source-built regression and consumer proof for the current source checkout" in text
    assert "historical `v0.1.4` release-candidate verification gate" in normalized


def test_docs_index_links_all_current_documentation_areas() -> None:
    text = _text(DOCS_INDEX)
    missing: list[str] = []

    for area in (
        "tutorials",
        "how-to",
        "reference",
        "explanation",
        "decisions",
        "releases",
    ):
        for path in sorted((ROOT / "docs" / area).glob("*.md")):
            relative = path.relative_to(ROOT / "docs").as_posix()
            if f"](./{relative})" not in text:
                missing.append(relative)

    assert missing == []


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


def test_v014_post_release_review_records_final_authority_without_rewriting_pr89_scope() -> None:
    text = _normalized(V014_POST_RELEASE_REVIEW).lower()

    for fact in (
        "Status: `FINAL POST-RELEASE CLOSEOUT RECORD`",
        "Release-candidate PR:",
        "pull/88",
        "Post-release PR:",
        "pull/89",
        "6a03765b25edd5a0b2c432ad3b3bf705ca36b7d4",
        "071100feb51dd041c41020f71426b75ebffd7654",
        "dbecc45b51e0b884c6c34a329e147310b1e3f83b",
        "5453f2d787185a318794d47f084c0f952939946e",
        "84fb533072a965b2ad833d12723e6ac0fff19d55",
        "exact-head 9/9",
        "exact-main 8/8",
        "`uv graph` is an exact-head check only",
        "independent follow-up",
        "Task-owned release-candidate and post-release branches/worktrees were cleaned",
        "detached historical-source worktree remains retained and untouched",
    ):
        assert fact.lower() in text

    for stale in (
        "PENDING AUTHORITATIVE ACTUAL-DIFF REVIEW",
        "The remaining gates are:",
        "this review remains pending",
        "worktree/branch remain retained",
        "Nine observed exact-main check runs",
    ):
        assert stale.lower() not in text


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
