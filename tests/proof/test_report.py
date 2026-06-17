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


def test_json_report_includes_reason_on_failed_case() -> None:
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
    payload = json.loads(render_json_report(report))
    assert payload["status"] == "failed"
    assert payload["failed"] == 1
    assert payload["results"][0]["reason"] == "fixture_missing"
    assert "reason" in payload["results"][0]


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
