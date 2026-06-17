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


def test_product_proof_runner_reports_mcp_observed_fields() -> None:
    report = run_product_proof()
    by_case = {result.case: result for result in report.results}

    assert by_case["mcp_ingest_file"].observed[0].value == "present"
    assert by_case["mcp_get_run"].observed[0].value == "published"
    assert by_case["mcp_search_and_ask"].observed[0].value == "page"
    assert by_case["mcp_search_and_ask"].observed[1].value == "evidence_found"


def test_product_proof_runner_json_payload_contains_no_absolute_paths() -> None:
    from mke.proof.report import render_json_report

    rendered = render_json_report(run_product_proof())
    json.loads(rendered)

    assert "/Users/" not in rendered
    assert "/tmp/" not in rendered


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
