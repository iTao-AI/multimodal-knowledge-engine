"""Product proof runner."""

from __future__ import annotations

import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from mke.application import KnowledgeEngine, PdfIngestError
from mke.domain import FailurePoint
from mke.interfaces.mcp_contract import (
    McpRuntimeConfig,
    ask_library,
    get_run,
    ingest_file,
    search_library,
)
from mke.proof.manifest import PRODUCT_PROOF_MANIFEST, ProofManifest
from mke.proof.report import ObservedField, ProofCaseResult, ProofReport

_EXPECTED_PDF_EVIDENCE_COUNT = 2
_EXPECTED_VIDEO_EVIDENCE_COUNT = 2

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
        if result.evidence_count != _EXPECTED_PDF_EVIDENCE_COUNT or result.intake_report is None:
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
        if (
            result.evidence_count != _EXPECTED_VIDEO_EVIDENCE_COUNT
            or not matches
            or matches[0].locator_kind != "timestamp_ms"
        ):
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
    return "unexpected_error"
