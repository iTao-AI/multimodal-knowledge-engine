import json

from pytest import CaptureFixture

from mke.cli import main


def test_cli_proof_run_outputs_human_report(capsys: CaptureFixture[str]) -> None:
    assert main(["proof", "run"]) == 0

    output = capsys.readouterr().out
    assert "mke proof run" in output
    assert "proof=product status=passed cases=8 passed=8 failed=0" in output
    assert "case=cli_pdf_ingest status=passed evidence_count=2 intake_report=present" in output
    assert (
        "case=mcp_search_and_ask status=passed locator=page answer_status=evidence_found"
        in output
    )


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
