# Product Proof & Evaluation Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `mke proof run` as a deterministic local product proof harness covering CLI-equivalent application behavior and MCP contract behavior.

**Architecture:** Add a small `src/mke/proof/` module with a built-in ordered `product` manifest, project-owned proof report DTOs, and a runner that uses temporary SQLite workspaces. The runner calls `KnowledgeEngine` for CLI-equivalent proof cases and `mke.interfaces.mcp_contract` for MCP proof cases; it does not start stdio MCP transport.

**Tech Stack:** Python 3.12/3.13, pytest, Ruff, Pyright strict mode, SQLite, existing MKE application and MCP contract APIs.

---

## Review Findings Covered

This plan incorporates:

- `docs/superpowers/specs/2026-06-17-product-proof-evaluation-harness-design.md`
- User review findings on D2 spec:
  - ordered dependency from `mcp_ingest_file` to `mcp_get_run`,
  - fixed MCP and CLI queries,
  - fixture-missing failure report,
  - JSON `observed` privacy allowlist,
  - `mke demo --verify` compatibility.

## File Structure

- Create `src/mke/proof/__init__.py`: public exports for proof runner and report formatting.
- Create `src/mke/proof/report.py`: `ObservedField`, `ProofCaseResult`, `ProofReport`, human and JSON formatting.
- Create `src/mke/proof/manifest.py`: built-in ordered `product` manifest and repository-relative fixture keys.
- Create `src/mke/proof/runner.py`: proof runner and case implementations.
- Modify `src/mke/cli.py`: add `mke proof run` and `mke proof run --json`.
- Create `tests/proof/test_report.py`: report formatting and JSON schema tests.
- Create `tests/proof/test_manifest.py`: manifest ordering and fixture metadata tests.
- Create `tests/proof/test_runner.py`: runner success, fixture-missing, and MCP case tests.
- Create `tests/interfaces/test_cli_proof.py`: CLI entrypoint tests.
- Modify `README.md`, `README_CN.md`, `docs/how-to/run-local-product-proof.md`, `docs/reference/cli.md`, `docs/reference/contracts.md`, and possibly `docs/README.md`.
- Modify this implementation plan checklist as tasks are completed.

## Task 1: Proof Report DTO And Formatting

**Files:**
- Create: `src/mke/proof/__init__.py`
- Create: `src/mke/proof/report.py`
- Create: `tests/proof/test_report.py`

- [x] **Step 1: Add failing report tests**

Create `tests/proof/test_report.py`:

```python
import json

from mke.proof.report import (
    ObservedField,
    ProofCaseResult,
    ProofReport,
    render_human_report,
    render_json_report,
)


def test_human_report_renders_summary_and_case_lines() -> None:
    report = ProofReport(
        proof="product",
        results=(
            ProofCaseResult(
                case="cli_pdf_ingest",
                status="passed",
                summary="PDF ingest published page Evidence and intake diagnostics.",
                observed=(
                    ObservedField("evidence_count", 2),
                    ObservedField("intake_report", "present"),
                ),
                duration_ms=4,
            ),
        ),
        duration_ms=9,
    )

    assert render_human_report(report) == "\n".join(
        [
            "mke proof run",
            "proof=product status=passed cases=1 passed=1 failed=0 duration_ms=9",
            "case=cli_pdf_ingest status=passed evidence_count=2 intake_report=present",
        ]
    )


def test_failed_case_renders_stable_reason() -> None:
    report = ProofReport(
        proof="product",
        results=(
            ProofCaseResult(
                case="fixture_validation",
                status="failed",
                summary="Required fixture is missing.",
                observed=(ObservedField("fixture", "text_layer_pdf"),),
                duration_ms=0,
                reason="fixture_missing",
            ),
        ),
        duration_ms=0,
    )

    assert (
        "case=fixture_validation status=failed reason=fixture_missing fixture=text_layer_pdf"
        in render_human_report(report)
    )
    assert report.status == "failed"
    assert report.failed == 1


def test_json_report_uses_public_safe_schema() -> None:
    report = ProofReport(
        proof="product",
        results=(
            ProofCaseResult(
                case="mcp_search_and_ask",
                status="passed",
                summary="MCP Search and Ask returned active Evidence.",
                observed=(
                    ObservedField("locator", "page"),
                    ObservedField("answer_status", "evidence_found"),
                ),
                duration_ms=3,
            ),
        ),
        duration_ms=5,
    )

    payload = json.loads(render_json_report(report))

    assert payload == {
        "proof": "product",
        "status": "passed",
        "cases": 1,
        "passed": 1,
        "failed": 0,
        "duration_ms": 5,
        "results": [
            {
                "case": "mcp_search_and_ask",
                "status": "passed",
                "summary": "MCP Search and Ask returned active Evidence.",
                "observed": {
                    "locator": "page",
                    "answer_status": "evidence_found",
                },
                "duration_ms": 3,
            }
        ],
    }
```

- [x] **Step 2: Run failing report tests**

Run:

```bash
uv run pytest tests/proof/test_report.py -q
```

Expected: FAIL because `mke.proof.report` does not exist.

- [x] **Step 3: Implement report DTOs and formatters**

Create `src/mke/proof/report.py`:

```python
"""Proof report DTOs and deterministic renderers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

ProofStatus = Literal["passed", "failed"]
ObservedValue = int | bool | str


@dataclass(frozen=True)
class ObservedField:
    key: str
    value: ObservedValue


@dataclass(frozen=True)
class ProofCaseResult:
    case: str
    status: ProofStatus
    summary: str
    observed: tuple[ObservedField, ...] = ()
    duration_ms: int = 0
    reason: str | None = None


@dataclass(frozen=True)
class ProofReport:
    proof: str
    results: tuple[ProofCaseResult, ...]
    duration_ms: int

    @property
    def cases(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for result in self.results if result.status == "passed")

    @property
    def failed(self) -> int:
        return sum(1 for result in self.results if result.status == "failed")

    @property
    def status(self) -> ProofStatus:
        return "failed" if self.failed else "passed"


def render_human_report(report: ProofReport) -> str:
    lines = [
        "mke proof run",
        (
            f"proof={report.proof} status={report.status} cases={report.cases} "
            f"passed={report.passed} failed={report.failed} "
            f"duration_ms={report.duration_ms}"
        ),
    ]
    for result in report.results:
        parts = [f"case={result.case}", f"status={result.status}"]
        if result.reason is not None:
            parts.append(f"reason={result.reason}")
        parts.extend(f"{field.key}={field.value}" for field in result.observed)
        lines.append(" ".join(parts))
    return "\n".join(lines)


def render_json_report(report: ProofReport) -> str:
    return json.dumps(_report_payload(report), indent=2, sort_keys=False)


def _report_payload(report: ProofReport) -> dict[str, object]:
    return {
        "proof": report.proof,
        "status": report.status,
        "cases": report.cases,
        "passed": report.passed,
        "failed": report.failed,
        "duration_ms": report.duration_ms,
        "results": [_case_payload(result) for result in report.results],
    }


def _case_payload(result: ProofCaseResult) -> dict[str, object]:
    payload: dict[str, object] = {
        "case": result.case,
        "status": result.status,
        "summary": result.summary,
        "observed": {field.key: field.value for field in result.observed},
        "duration_ms": result.duration_ms,
    }
    if result.reason is not None:
        payload["reason"] = result.reason
    return payload
```

Create `src/mke/proof/__init__.py`:

```python
"""Deterministic product proof harness."""

from mke.proof.report import (
    ObservedField,
    ProofCaseResult,
    ProofReport,
    render_human_report,
    render_json_report,
)

__all__ = [
    "ObservedField",
    "ProofCaseResult",
    "ProofReport",
    "render_human_report",
    "render_json_report",
]
```

- [x] **Step 4: Run report tests**

Run:

```bash
uv run pytest tests/proof/test_report.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/mke/proof/__init__.py src/mke/proof/report.py tests/proof/test_report.py
git commit -m "feat(proof): add deterministic proof reports"
```

## Task 2: Built-In Product Manifest

**Files:**
- Create: `src/mke/proof/manifest.py`
- Modify: `src/mke/proof/__init__.py`
- Create: `tests/proof/test_manifest.py`

- [ ] **Step 1: Add failing manifest tests**

Create `tests/proof/test_manifest.py`:

```python
from mke.proof.manifest import PRODUCT_PROOF_MANIFEST


def test_product_manifest_has_ordered_cases_and_name() -> None:
    assert PRODUCT_PROOF_MANIFEST.name == "product"
    assert PRODUCT_PROOF_MANIFEST.cases == (
        "cli_pdf_ingest",
        "cli_pdf_search",
        "cli_failed_reprocess",
        "cli_video_ingest_search",
        "cli_ask",
        "mcp_ingest_file",
        "mcp_get_run",
        "mcp_search_and_ask",
    )


def test_product_manifest_uses_repository_relative_fixtures() -> None:
    fixtures = PRODUCT_PROOF_MANIFEST.fixtures

    assert str(fixtures.text_layer_pdf) == "tests/fixtures/pdf/text-layer.pdf"
    assert str(fixtures.revised_pdf) == "tests/fixtures/pdf/text-layer-revised.pdf"
    assert str(fixtures.video) == "tests/fixtures/video/short-audio.mp4"
    assert (
        str(fixtures.video_transcript)
        == "tests/fixtures/video/short-audio.mp4.mke-transcript.json"
    )
```

- [ ] **Step 2: Run failing manifest tests**

Run:

```bash
uv run pytest tests/proof/test_manifest.py -q
```

Expected: FAIL because `mke.proof.manifest` does not exist.

- [ ] **Step 3: Implement manifest**

Create `src/mke/proof/manifest.py`:

```python
"""Built-in product proof manifest."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProofFixtures:
    text_layer_pdf: Path
    revised_pdf: Path
    video: Path
    video_transcript: Path


@dataclass(frozen=True)
class ProofManifest:
    name: str
    cases: tuple[str, ...]
    fixtures: ProofFixtures


PRODUCT_PROOF_MANIFEST = ProofManifest(
    name="product",
    cases=(
        "cli_pdf_ingest",
        "cli_pdf_search",
        "cli_failed_reprocess",
        "cli_video_ingest_search",
        "cli_ask",
        "mcp_ingest_file",
        "mcp_get_run",
        "mcp_search_and_ask",
    ),
    fixtures=ProofFixtures(
        text_layer_pdf=Path("tests/fixtures/pdf/text-layer.pdf"),
        revised_pdf=Path("tests/fixtures/pdf/text-layer-revised.pdf"),
        video=Path("tests/fixtures/video/short-audio.mp4"),
        video_transcript=Path("tests/fixtures/video/short-audio.mp4.mke-transcript.json"),
    ),
)
```

Modify `src/mke/proof/__init__.py`:

```python
from mke.proof.manifest import PRODUCT_PROOF_MANIFEST, ProofFixtures, ProofManifest
```

and add those three names to `__all__`.

- [ ] **Step 4: Run manifest tests**

Run:

```bash
uv run pytest tests/proof/test_manifest.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mke/proof/__init__.py src/mke/proof/manifest.py tests/proof/test_manifest.py
git commit -m "feat(proof): add product proof manifest"
```

## Task 3: CLI-Equivalent Proof Runner Cases

**Files:**
- Create: `src/mke/proof/runner.py`
- Modify: `src/mke/proof/__init__.py`
- Create: `tests/proof/test_runner.py`

- [ ] **Step 1: Add failing runner tests for CLI-equivalent cases**

Create `tests/proof/test_runner.py`:

```python
import json
from pathlib import Path

from mke.proof.manifest import PRODUCT_PROOF_MANIFEST, ProofManifest
from mke.proof.runner import run_product_proof


def test_product_proof_runner_passes_all_cases() -> None:
    report = run_product_proof()

    assert report.status == "passed"
    assert report.cases == 8
    assert report.passed == 8
    assert [result.case for result in report.results] == list(PRODUCT_PROOF_MANIFEST.cases)


def test_product_proof_runner_reports_cli_observed_fields() -> None:
    report = run_product_proof()
    by_case = {result.case: result for result in report.results}

    assert by_case["cli_pdf_ingest"].observed[0].key == "evidence_count"
    assert by_case["cli_pdf_ingest"].observed[0].value == 2
    assert by_case["cli_pdf_search"].observed[0].value == "page"
    assert by_case["cli_failed_reprocess"].observed[0].value == "unchanged"
    assert by_case["cli_video_ingest_search"].observed[0].value == "timestamp_ms"
    assert by_case["cli_ask"].observed[0].value == "evidence_found"


def test_product_proof_runner_json_payload_contains_no_absolute_paths() -> None:
    from mke.proof.report import render_json_report

    payload = json.loads(render_json_report(run_product_proof()))

    def walk(value: object) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            strings: list[str] = []
            for item in value.values():
                strings.extend(walk(item))
            return strings
        if isinstance(value, list):
            strings = []
            for item in value:
                strings.extend(walk(item))
            return strings
        return []

    assert not any("/Users/" in value for value in walk(payload))
    assert not any("/tmp/" in value for value in walk(payload))


def test_product_proof_runner_reports_missing_fixture_without_traceback(
    tmp_path: Path,
) -> None:
    manifest = ProofManifest(
        name="product",
        cases=PRODUCT_PROOF_MANIFEST.cases,
        fixtures=PRODUCT_PROOF_MANIFEST.fixtures.__class__(
            text_layer_pdf=Path("missing/text-layer.pdf"),
            revised_pdf=PRODUCT_PROOF_MANIFEST.fixtures.revised_pdf,
            video=PRODUCT_PROOF_MANIFEST.fixtures.video,
            video_transcript=PRODUCT_PROOF_MANIFEST.fixtures.video_transcript,
        ),
    )

    report = run_product_proof(manifest=manifest, repo_root=tmp_path)

    assert report.status == "failed"
    assert report.results[0].case == "fixture_validation"
    assert report.results[0].reason == "fixture_missing"
    assert report.results[0].observed[0].value == "text_layer_pdf"
```

- [ ] **Step 2: Run failing runner tests**

Run:

```bash
uv run pytest tests/proof/test_runner.py -q
```

Expected: FAIL because `mke.proof.runner` does not exist.

- [ ] **Step 3: Implement runner skeleton, fixture validation, and CLI-equivalent cases**

Create `src/mke/proof/runner.py`:

```python
"""Product proof runner."""

from __future__ import annotations

import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from mke.application import KnowledgeEngine, PdfIngestError
from mke.domain import FailurePoint
from mke.proof.manifest import PRODUCT_PROOF_MANIFEST, ProofManifest
from mke.proof.report import ObservedField, ProofCaseResult, ProofReport

_CaseFn = Callable[["_ProofContext"], ProofCaseResult]


class _ProofContext:
    def __init__(self, repo_root: Path, temp_root: Path, manifest: ProofManifest) -> None:
        self.repo_root = repo_root
        self.temp_root = temp_root
        self.manifest = manifest
        self.cli_db_path = temp_root / "cli.sqlite"
        self.mcp_db_path = temp_root / "mcp.sqlite"
        self.mcp_pdf_run_id: str | None = None

    def fixture(self, path: Path) -> Path:
        return self.repo_root / path


def run_product_proof(
    manifest: ProofManifest = PRODUCT_PROOF_MANIFEST,
    repo_root: Path | None = None,
) -> ProofReport:
    started = time.monotonic()
    root = Path.cwd() if repo_root is None else repo_root
    missing = _missing_fixture(manifest, root)
    if missing is not None:
        return ProofReport(
            proof=manifest.name,
            results=(
                ProofCaseResult(
                    case="fixture_validation",
                    status="failed",
                    summary="Required fixture is missing.",
                    observed=(ObservedField("fixture", missing),),
                    reason="fixture_missing",
                    duration_ms=0,
                ),
            ),
            duration_ms=_elapsed_ms(started),
        )

    results: list[ProofCaseResult] = []
    with tempfile.TemporaryDirectory(prefix="mke-proof-") as temp_dir:
        context = _ProofContext(root, Path(temp_dir), manifest)
        cases: dict[str, _CaseFn] = {
            "cli_pdf_ingest": _case_cli_pdf_ingest,
            "cli_pdf_search": _case_cli_pdf_search,
            "cli_failed_reprocess": _case_cli_failed_reprocess,
            "cli_video_ingest_search": _case_cli_video_ingest_search,
            "cli_ask": _case_cli_ask,
            "mcp_ingest_file": _case_mcp_ingest_file,
            "mcp_get_run": _case_mcp_get_run,
            "mcp_search_and_ask": _case_mcp_search_and_ask,
        }
        for case_id in manifest.cases:
            case_started = time.monotonic()
            try:
                result = cases[case_id](context)
            except Exception as error:
                result = ProofCaseResult(
                    case=case_id,
                    status="failed",
                    summary="Proof case failed.",
                    reason=_stable_reason(error),
                    duration_ms=_elapsed_ms(case_started),
                )
            results.append(result)

    return ProofReport(
        proof=manifest.name,
        results=tuple(results),
        duration_ms=_elapsed_ms(started),
    )


def _case_cli_pdf_ingest(context: _ProofContext) -> ProofCaseResult:
    started = time.monotonic()
    engine = KnowledgeEngine(context.cli_db_path)
    try:
        result = engine.ingest_pdf(context.fixture(context.manifest.fixtures.text_layer_pdf))
        if result.evidence_count != 2 or result.intake_report is None:
            raise AssertionError("PDF ingest did not publish expected Evidence and intake report")
        return ProofCaseResult(
            case="cli_pdf_ingest",
            status="passed",
            summary="PDF ingest published page Evidence and intake diagnostics.",
            observed=(
                ObservedField("evidence_count", result.evidence_count),
                ObservedField("intake_report", "present"),
            ),
            duration_ms=_elapsed_ms(started),
        )
    finally:
        engine.close()


def _case_cli_pdf_search(context: _ProofContext) -> ProofCaseResult:
    started = time.monotonic()
    engine = KnowledgeEngine(context.cli_db_path)
    try:
        matches = engine.search("trustworthy")
        if not matches or matches[0].locator_kind != "page":
            raise AssertionError("PDF search did not return page Evidence")
        return ProofCaseResult(
            case="cli_pdf_search",
            status="passed",
            summary="Active Search returned page-addressed PDF Evidence.",
            observed=(ObservedField("locator", "page"),),
            duration_ms=_elapsed_ms(started),
        )
    finally:
        engine.close()


def _case_cli_failed_reprocess(context: _ProofContext) -> ProofCaseResult:
    started = time.monotonic()
    engine = KnowledgeEngine(context.cli_db_path)
    try:
        before = [match.text for match in engine.search("trustworthy")]
        try:
            engine.reprocess_pdf(
                context.fixture(context.manifest.fixtures.revised_pdf),
                failure_point=FailurePoint.BEFORE_VALIDATION,
            )
        except PdfIngestError:
            pass
        else:
            raise AssertionError("Injected failed reprocess did not fail")
        after = [match.text for match in engine.search("trustworthy")]
        if before != after:
            raise AssertionError("Failed reprocess changed active Publication")
        return ProofCaseResult(
            case="cli_failed_reprocess",
            status="passed",
            summary="Failed reprocess left active Publication unchanged.",
            observed=(ObservedField("active_publication_impact", "unchanged"),),
            duration_ms=_elapsed_ms(started),
        )
    finally:
        engine.close()


def _case_cli_video_ingest_search(context: _ProofContext) -> ProofCaseResult:
    started = time.monotonic()
    engine = KnowledgeEngine(context.cli_db_path)
    try:
        result = engine.ingest_video(context.fixture(context.manifest.fixtures.video))
        matches = engine.search("timestamp proof")
        if result.evidence_count != 2 or not matches or matches[0].locator_kind != "timestamp_ms":
            raise AssertionError("Video ingest/search did not return timestamp Evidence")
        return ProofCaseResult(
            case="cli_video_ingest_search",
            status="passed",
            summary="Video sidecar ingest returned timestamp-addressed Evidence.",
            observed=(ObservedField("locator", "timestamp_ms"),),
            duration_ms=_elapsed_ms(started),
        )
    finally:
        engine.close()


def _case_cli_ask(context: _ProofContext) -> ProofCaseResult:
    started = time.monotonic()
    engine = KnowledgeEngine(context.cli_db_path)
    try:
        result = engine.ask("publication active")
        if result.answer_status != "evidence_found" or not result.evidence:
            raise AssertionError("Ask did not return active Evidence")
        return ProofCaseResult(
            case="cli_ask",
            status="passed",
            summary="Evidence-only Ask returned cited active Evidence.",
            observed=(ObservedField("answer_status", "evidence_found"),),
            duration_ms=_elapsed_ms(started),
        )
    finally:
        engine.close()


def _case_mcp_ingest_file(context: _ProofContext) -> ProofCaseResult:
    raise NotImplementedError("mcp_ingest_file is implemented in Task 4")


def _case_mcp_get_run(context: _ProofContext) -> ProofCaseResult:
    raise NotImplementedError("mcp_get_run is implemented in Task 4")


def _case_mcp_search_and_ask(context: _ProofContext) -> ProofCaseResult:
    raise NotImplementedError("mcp_search_and_ask is implemented in Task 4")


def _missing_fixture(manifest: ProofManifest, repo_root: Path) -> str | None:
    fixtures = manifest.fixtures
    checks = (
        ("text_layer_pdf", fixtures.text_layer_pdf),
        ("revised_pdf", fixtures.revised_pdf),
        ("video", fixtures.video),
        ("video_transcript", fixtures.video_transcript),
    )
    for key, path in checks:
        if not (repo_root / path).exists():
            return key
    return None


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _stable_reason(error: Exception) -> str:
    if isinstance(error, AssertionError):
        return "assertion_failed"
    if isinstance(error, NotImplementedError):
        return "case_not_implemented"
    return "unexpected_error"
```

Modify `src/mke/proof/__init__.py`:

```python
from mke.proof.runner import run_product_proof
```

and add `run_product_proof` to `__all__`.

- [ ] **Step 4: Run runner tests and observe MCP failures**

Run:

```bash
uv run pytest tests/proof/test_runner.py -q
```

Expected: FAIL because MCP cases are intentionally not implemented yet and the full runner does not
pass all 8 cases.

- [ ] **Step 5: Commit CLI-equivalent partial runner**

Do not commit a failing full runner. If the test suite is failing at this point, continue to Task 4
before committing.

## Task 4: MCP Contract Proof Cases

**Files:**
- Modify: `src/mke/proof/runner.py`
- Modify: `tests/proof/test_runner.py`

- [ ] **Step 1: Add focused MCP dependency assertions**

Append to `tests/proof/test_runner.py`:

```python
def test_product_proof_runner_reports_mcp_observed_fields() -> None:
    report = run_product_proof()
    by_case = {result.case: result for result in report.results}

    assert by_case["mcp_ingest_file"].observed[0].value == "present"
    assert by_case["mcp_get_run"].observed[0].value == "published"
    assert by_case["mcp_search_and_ask"].observed[0].value == "page"
    assert by_case["mcp_search_and_ask"].observed[1].value == "evidence_found"
```

- [ ] **Step 2: Implement MCP cases**

Modify imports in `src/mke/proof/runner.py`:

```python
from mke.interfaces.mcp_contract import (
    McpRuntimeConfig,
    ask_library,
    get_run,
    ingest_file,
    search_library,
)
```

Replace the three MCP stubs:

```python
def _case_mcp_ingest_file(context: _ProofContext) -> ProofCaseResult:
    started = time.monotonic()
    config = McpRuntimeConfig(db_path=context.mcp_db_path, allowed_root=context.repo_root)
    result = ingest_file(config, str(context.manifest.fixtures.text_layer_pdf))
    if not result.get("ok"):
        raise AssertionError("MCP ingest_file failed")
    if result.get("run_state") != "published" or "intake_report" not in result:
        raise AssertionError("MCP ingest_file did not publish PDF intake report")
    context.mcp_pdf_run_id = str(result["run_id"])
    return ProofCaseResult(
        case="mcp_ingest_file",
        status="passed",
        summary="MCP ingest_file published PDF Evidence and intake diagnostics.",
        observed=(ObservedField("intake_report", "present"),),
        duration_ms=_elapsed_ms(started),
    )


def _case_mcp_get_run(context: _ProofContext) -> ProofCaseResult:
    started = time.monotonic()
    if context.mcp_pdf_run_id is None:
        raise AssertionError("mcp_get_run requires mcp_ingest_file context")
    config = McpRuntimeConfig(db_path=context.mcp_db_path, allowed_root=context.repo_root)
    result = get_run(config, context.mcp_pdf_run_id)
    if not result.get("ok"):
        raise AssertionError("MCP get_run failed")
    if result["run"]["state"] != "published" or "intake_report" not in result:
        raise AssertionError("MCP get_run did not expose Run state and intake diagnostics")
    if not result["events"]:
        raise AssertionError("MCP get_run did not expose Run events")
    return ProofCaseResult(
        case="mcp_get_run",
        status="passed",
        summary="MCP get_run exposed Run state, events, and intake diagnostics.",
        observed=(ObservedField("run_state", "published"),),
        duration_ms=_elapsed_ms(started),
    )


def _case_mcp_search_and_ask(context: _ProofContext) -> ProofCaseResult:
    started = time.monotonic()
    config = McpRuntimeConfig(db_path=context.mcp_db_path, allowed_root=context.repo_root)
    search = search_library(config, "trustworthy")
    if not search.get("ok") or not search["results"]:
        raise AssertionError("MCP search_library returned no active Evidence")
    locator = search["results"][0]["locator"]["kind"]
    ask = ask_library(config, "publication active")
    if not ask.get("ok") or ask["answer_status"] != "evidence_found" or not ask["evidence"]:
        raise AssertionError("MCP ask_library did not return active Evidence")
    return ProofCaseResult(
        case="mcp_search_and_ask",
        status="passed",
        summary="MCP Search and Ask returned active Evidence.",
        observed=(
            ObservedField("locator", str(locator)),
            ObservedField("answer_status", "evidence_found"),
        ),
        duration_ms=_elapsed_ms(started),
    )
```

- [ ] **Step 3: Run proof runner tests**

Run:

```bash
uv run pytest tests/proof/test_report.py tests/proof/test_manifest.py tests/proof/test_runner.py -q
```

Expected: PASS.

- [ ] **Step 4: Run full tests for regression safety**

Run:

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 5: Commit runner**

```bash
git add src/mke/proof/__init__.py src/mke/proof/runner.py tests/proof/test_runner.py
git commit -m "feat(proof): run product proof cases"
```

## Task 5: Wire `mke proof run` Into CLI

**Files:**
- Modify: `src/mke/cli.py`
- Create: `tests/interfaces/test_cli_proof.py`

- [ ] **Step 1: Add failing CLI tests**

Create `tests/interfaces/test_cli_proof.py`:

```python
import json

from pytest import CaptureFixture

from mke.cli import main


def test_cli_proof_run_outputs_human_report(capsys: CaptureFixture[str]) -> None:
    assert main(["proof", "run"]) == 0

    output = capsys.readouterr().out
    assert "mke proof run" in output
    assert "proof=product status=passed cases=8 passed=8 failed=0" in output
    assert "case=cli_pdf_ingest status=passed evidence_count=2 intake_report=present" in output
    assert "case=mcp_search_and_ask status=passed locator=page answer_status=evidence_found" in output


def test_cli_proof_run_json_outputs_parseable_report(
    capsys: CaptureFixture[str],
) -> None:
    assert main(["proof", "run", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["proof"] == "product"
    assert payload["status"] == "passed"
    assert payload["cases"] == 8
    assert payload["failed"] == 0
    assert [result["case"] for result in payload["results"]] == [
        "cli_pdf_ingest",
        "cli_pdf_search",
        "cli_failed_reprocess",
        "cli_video_ingest_search",
        "cli_ask",
        "mcp_ingest_file",
        "mcp_get_run",
        "mcp_search_and_ask",
    ]
```

- [ ] **Step 2: Run failing CLI proof tests**

Run:

```bash
uv run pytest tests/interfaces/test_cli_proof.py -q
```

Expected: FAIL because `proof` command does not exist.

- [ ] **Step 3: Add CLI parser and handler**

Modify imports in `src/mke/cli.py`:

```python
from mke.proof import render_human_report, render_json_report, run_product_proof
```

After the `demo` parser setup, add:

```python
    proof = subcommands.add_parser("proof")
    proof_subcommands = proof.add_subparsers(dest="proof_command", required=True)
    proof_run = proof_subcommands.add_parser("run")
    proof_run.add_argument("--json", action="store_true", dest="json_output")
```

After the existing `if args.command == "demo":` block, add:

```python
    if args.command == "proof":
        return _proof_run(json_output=args.json_output)
```

Add this helper near `_demo_verify`:

```python
def _proof_run(*, json_output: bool) -> int:
    report = run_product_proof()
    if json_output:
        print(render_json_report(report))
    else:
        print(render_human_report(report))
    return 0 if report.status == "passed" else 1
```

- [ ] **Step 4: Run CLI proof tests**

Run:

```bash
uv run pytest tests/interfaces/test_cli_proof.py -q
```

Expected: PASS.

- [ ] **Step 5: Verify old demo compatibility**

Run:

```bash
uv run pytest tests/interfaces/test_cli_demo.py tests/interfaces/test_cli_video.py -q
uv run mke demo --verify
```

Expected:

- Tests pass.
- `uv run mke demo --verify` still prints `phase=...` lines and `result=passed`.

- [ ] **Step 6: Commit CLI wiring**

```bash
git add src/mke/cli.py tests/interfaces/test_cli_proof.py
git commit -m "feat(cli): add product proof command"
```

## Task 6: Update Public Documentation

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/how-to/run-local-product-proof.md`
- Modify: `docs/reference/cli.md`
- Modify: `docs/reference/contracts.md`
- Modify: `docs/README.md` if the index needs an explicit proof harness label
- Modify: `docs/superpowers/plans/2026-06-17-product-proof-evaluation-harness-implementation.md`

- [ ] **Step 1: Update README proof command**

In `README.md`, change the primary local proof command from:

```bash
uv run mke demo --verify
```

to:

```bash
uv run mke proof run
uv run mke proof run --json
```

Keep a sentence saying `mke demo --verify` remains available as a compatibility proof.

- [ ] **Step 2: Update README_CN proof command**

In `README_CN.md`, make the same command change and keep technical identifiers in English.

- [ ] **Step 3: Rewrite local product proof how-to**

In `docs/how-to/run-local-product-proof.md`, replace the opening command block with:

```bash
uv sync --locked
uv run mke proof run
uv run mke proof run --json
```

Add a section named `Proof Cases` containing the eight case IDs from the spec. Add a short
compatibility note:

```markdown
`mke demo --verify` remains available and keeps its phase-oriented output, but `mke proof run` is
the primary product proof entrypoint.
```

- [ ] **Step 4: Update CLI reference**

In `docs/reference/cli.md`, add `mke proof run` before the old `mke demo --verify` section. Include
the human output shape and note that `--json` emits machine-readable results with no absolute
local paths.

- [ ] **Step 5: Update contracts reference**

In `docs/reference/contracts.md`, update the CLI status table with:

```markdown
| `mke proof run` | implemented in D2 | Runs the deterministic product proof harness across CLI-equivalent application behavior and MCP contract behavior. |
```

Keep `mke demo --verify` as implemented and compatibility-oriented.

- [ ] **Step 6: Documentation safety checks**

Run:

```bash
rg -n "/Users|Career|求职|interview|gstack|restore|token|secret" README.md README_CN.md docs
rg -n "mke proof run" README.md README_CN.md docs/reference docs/how-to docs/README.md
git diff --check
```

Expected:

- First command has no matches except public boundary wording if intentionally present.
- Second command finds README and documentation references.
- `git diff --check` has no output.

- [ ] **Step 7: Commit docs**

```bash
git add README.md README_CN.md docs/how-to/run-local-product-proof.md docs/reference/cli.md docs/reference/contracts.md docs/README.md docs/superpowers/specs/2026-06-17-product-proof-evaluation-harness-design.md docs/superpowers/plans/2026-06-17-product-proof-evaluation-harness-implementation.md
git commit -m "docs(proof): document product proof harness"
```

If `docs/README.md` is unchanged, omit it from `git add`.

## Task 7: Final Verification And PR Preparation

**Files:**
- No new source files unless a verification failure requires a targeted fix.

- [ ] **Step 1: Run focused proof tests**

Run:

```bash
uv run pytest tests/proof tests/interfaces/test_cli_proof.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```bash
uv run pytest -q
```

Expected: all tests pass. Record the exact pass count.

- [ ] **Step 3: Run lint and type checks**

Run:

```bash
uv run ruff check .
uv run pyright
```

Expected:

- Ruff: `All checks passed!`
- Pyright: `0 errors, 0 warnings, 0 informations`

- [ ] **Step 4: Build and run proof commands**

Run:

```bash
uv build
uv run mke proof run
uv run mke proof run --json
uv run mke demo --verify
git diff --check
```

Expected:

- `uv build` builds sdist and wheel.
- `uv run mke proof run` prints `proof=product status=passed cases=8 passed=8 failed=0`.
- `uv run mke proof run --json` prints valid JSON with `"status": "passed"`.
- `uv run mke demo --verify` prints `result=passed` and retains `phase=` lines.
- `git diff --check` has no output.

- [ ] **Step 5: Inspect public boundary**

Run:

```bash
rg -n "/Users|Career|求职|interview|gstack|restore|token|secret|private source" .
```

Expected: no private paths or private motivations. Public boundary references to `private source`
inside docs are acceptable only when describing what must not be included.

- [ ] **Step 6: Prepare Chinese PR body**

Use this structure:

```markdown
## Summary

新增 `mke proof run` 产品证明入口，把现有一次性 demo 升级为覆盖 CLI-equivalent application path 和 MCP contract path 的 deterministic proof harness。

- 增加 `src/mke/proof/` manifest、runner 和 report DTO。
- 新增 8 个内置 proof cases，覆盖 PDF、video、failed reprocess、Ask、MCP ingest/get_run/search/ask。
- 支持 human output 和 `--json` machine-readable report。
- 保留 `mke demo --verify` 兼容输出。
- 更新 README、CLI reference、contracts 和 local product proof how-to。

## Completion

- [x] `mke proof run` 可重复验证 product proof。
- [x] `mke proof run --json` 输出稳定 JSON。
- [x] CLI-equivalent cases 和 MCP contract cases 在同一 report 中执行。
- [x] Missing fixture / case failure 返回 failed report，不输出 traceback。
- [x] `mke demo --verify` 继续可用。

## Verification

| Command | Result |
|---|---|
| `uv run pytest -q` | Record the exact pass count from Task 7 Step 2. |
| `uv run ruff check .` | Record the exact Ruff output from Task 7 Step 3. |
| `uv run pyright` | Record the exact Pyright output from Task 7 Step 3. |
| `uv build` | Record the exact build result from Task 7 Step 4. |
| `uv run mke proof run` | Record the exact summary line from Task 7 Step 4. |
| `uv run mke proof run --json` | Record that the JSON parsed and had `status=passed`. |
| `uv run mke demo --verify` | Record the exact `result=passed` line from Task 7 Step 4. |
| `git diff --check` | Record `passed, no output` after Task 7 Step 4. |

## Scope

- In scope: deterministic local product proof, CLI-equivalent application checks, MCP contract checks, docs.
- Out of scope: retrieval metrics, Unicode retrieval, OCR, real transcription, HTTP, workspace UI, stdio MCP transport tests.

## Risk / Impact

- User impact: `mke proof run` becomes the primary local proof command.
- Compatibility impact: `mke demo --verify` remains available and keeps its existing output shape.
- Rollback plan: remove `src/mke/proof/` and CLI proof command; existing `mke demo --verify` remains the fallback.

## Documentation impact

- README / README_CN, local product proof how-to, CLI reference, contracts, Superpowers spec/plan updated.
```

- [ ] **Step 7: Stop before push/PR unless authorized**

Report:

- branch,
- commits,
- verification results,
- documentation impact,
- remaining risks,
- whether PR body is prepared.
