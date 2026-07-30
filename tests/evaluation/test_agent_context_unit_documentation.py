from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[2]
HOW_TO = (
    ROOT / "docs/how-to/run-agent-context-mechanism-comparison.md"
)
DOCS_README = ROOT / "docs/README.md"
CI = ROOT / ".github/workflows/ci.yml"
PLAN = (
    ROOT
    / "docs/superpowers/plans/"
    "2026-07-30-diagnostic-first-context-mechanism-separation-"
    "implementation.md"
)
BASELINE = (
    ROOT / "benchmarks/retrieval/agent-context-unit-v2-baseline.json"
)
DEVELOPMENT = (
    ROOT / "benchmarks/retrieval/agent-context-unit-v2-development.json"
)
PROTOCOL = ROOT / "tests/fixtures/agent-context-unit-v2/protocol.json"
SCIENTIFIC_LOCK = (
    ROOT
    / "tests/fixtures/agent-context-unit-v2/scientific-input-lock.json"
)
CI_STEP_NAME = "Validate diagnostic-first context comparison evidence"
UNAUTHORIZED_CANONICAL_PATHS = (
    "benchmarks/retrieval/agent-context-unit-v2-holdout-receipt.json",
    "benchmarks/retrieval/agent-context-unit-v2-comparison.json",
)


def _development_artifact() -> dict[str, object]:
    decoded = cast(object, json.loads(DEVELOPMENT.read_bytes()))
    assert isinstance(decoded, dict)
    return cast(dict[str, object], decoded)


def _ci_step() -> str:
    workflow = CI.read_text(encoding="utf-8")
    marker = f"      - name: {CI_STEP_NAME}\n"
    assert workflow.count(marker) == 1
    return workflow.split(marker, 1)[1].split("\n      - ", 1)[0]


def test_how_to_records_exact_observed_result_and_artifact_authority() -> None:
    guide = HOW_TO.read_text(encoding="utf-8")
    prose = " ".join(guide.split())
    artifact = _development_artifact()
    authority = artifact["authority"]
    assert isinstance(authority, dict)
    typed_authority = cast(dict[str, object], authority)

    assert sha256(BASELINE.read_bytes()).hexdigest() in guide
    assert sha256(DEVELOPMENT.read_bytes()).hexdigest() in guide
    assert sha256(PROTOCOL.read_bytes()).hexdigest() in guide
    assert sha256(SCIENTIFIC_LOCK.read_bytes()).hexdigest() in guide
    for value in (
        artifact["content_digest"],
        typed_authority["evaluator_source_sha256"],
        typed_authority["runtime_profile_sha256"],
    ):
        assert isinstance(value, str)
        assert value in guide

    for classification in cast(list[str], artifact["classifications"]):
        assert f"`{classification}`" in guide
    mechanism_statuses = cast(
        dict[str, str], artifact["mechanism_statuses"]
    )
    for mechanism, status in mechanism_statuses.items():
        assert f"`{mechanism.upper()}={status}`" in guide
    for value in cast(list[str], artifact["limitations"]):
        assert f"`{value}`" in guide
    for value in cast(list[str], artifact["nonclaims"]):
        assert f"`{value}`" in guide

    for exact_statement in (
        "deterministic comparison rejected the candidate under the frozen "
        "development protocol",
        "`stage_outcome=candidate_failed`",
        "`holdout_status=not_evaluated`",
        "`runtime_promotion_status=not_evaluated`",
        "`control_guardrail_failed`",
    ):
        assert exact_statement in prose


def test_how_to_explains_product_mechanisms_and_recovery_boundaries() -> None:
    guide = HOW_TO.read_text(encoding="utf-8")
    prose = " ".join(guide.split())

    for statement in (
        "local-first Agent-callable Evidence/Context compiler",
        "compiled-Library fast path",
        "retrieval fallback",
        "exact-read recovery",
        "O0 — current Evidence baseline",
        "O1 — deterministic unit rank",
        "O2 — fixed-rank unit delivery",
        "O3 — source-context index",
        "O4 — source-context delivery",
        "O5 — adjacent-page assembly",
        "caller-owned diagnostic receipt",
        "complete success leaves the diagnostic receipt absent",
        "constructed development corpus",
        "public-nonblind future holdout",
    ):
        assert statement in prose

    for nonclaim in (
        "no retrieval-quality claim",
        "no performance claim",
        "no generalization claim",
        "no runtime-promotion claim",
    ):
        assert nonclaim in prose
    for inaccurate_claim in (
        "mechanism " + "win",
        "retrieval-quality " + "gain",
        "improved " + "retrieval",
        "failed software execution",
    ):
        assert inaccurate_claim not in guide.lower()


def test_how_to_documents_pure_validation_without_recording_commands() -> None:
    guide = HOW_TO.read_text(encoding="utf-8")

    for command in (
        "agent_context_unit_workflow validate-baseline",
        "agent_context_unit_workflow validate-development",
    ):
        assert command in guide
    for forbidden in (
        "agent_context_unit_workflow baseline --",
        "agent_context_unit_workflow development --",
        "agent_context_unit_workflow holdout",
    ):
        assert forbidden not in guide
    assert "Pure validation does not ingest, observe, grade anew, or publish." in guide
    assert "Do not rerun the one-shot observations." in guide


def test_docs_readme_links_the_comparison_guide_as_comparison_only() -> None:
    readme = DOCS_README.read_text(encoding="utf-8")
    prose = " ".join(readme.split())

    assert (
        "./how-to/run-agent-context-mechanism-comparison.md" in readme
    )
    assert "rejected the candidate under the frozen development protocol" in prose
    assert "comparison-only" in prose
    assert "holdout and runtime promotion remain `not_evaluated`" in prose


def test_ci_step_is_pure_model_free_and_guards_unauthorized_paths() -> None:
    step = _ci_step()

    assert "tests/evaluation/test_agent_context_unit_*.py" in step
    for command in (
        "agent_context_unit_workflow validate-baseline",
        "agent_context_unit_workflow validate-development",
    ):
        assert command in step
    for path in UNAUTHORIZED_CANONICAL_PATHS:
        assert step.count(f'test ! -e "{path}"') == 1
    for forbidden in (
        "agent_context_unit_workflow baseline --",
        "agent_context_unit_workflow development --",
        "agent_context_unit_workflow holdout",
        "--record ",
        "--diagnostic-receipt",
    ):
        assert forbidden not in step


def test_plan_records_task_13_completion_without_holdout_or_promotion() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    prose = " ".join(plan.split())

    assert (
        "**Status:** Complete development comparison — the deterministic "
        "comparison rejected the candidate under the frozen development "
        "protocol; holdout and runtime promotion remain `not_evaluated`."
        in prose
    )
    assert (
        "Task 13 documentation and CI closeout is complete; independent "
        "actual-branch-diff review is complete; publication remains pending."
        in prose
    )
    for item in (
        "Document the exact development result and non-claims",
        "Add pure, model-free CI validation and canonical absence guards",
        "Run final verification and the exact committed CI block locally",
        "Commit the five-path documentation and CI closeout",
    ):
        assert f"- [x] {item}" in plan
    assert (
        "Task 13 implementation status: complete; independent "
        "actual-branch-diff review complete; publication pending."
        in prose
    )


def test_task_13_public_changes_contain_no_private_coordination_markers() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (HOW_TO, DOCS_README, CI, PLAN)
    )

    for marker in (
        "/" + "Users/",
        "/private" + "/tmp",
        "return_" + "target",
        "source_" + "thread_id",
        "Career" + " authority",
        "G" + "Stack",
    ):
        assert marker not in combined
