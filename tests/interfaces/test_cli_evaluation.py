import json
from pathlib import Path

import pytest
from pytest import CaptureFixture

from mke.cli import main

MANIFEST = Path("tests/fixtures/retrieval-eval-v1.json")


def test_cli_eval_retrieval_outputs_human_baseline(
    capsys: CaptureFixture[str],
) -> None:
    assert main(["eval", "retrieval", "--manifest", str(MANIFEST)]) == 0

    output = capsys.readouterr()
    assert output.err == ""
    assert "mke eval retrieval" in output.out
    assert "scope=small_english_page_timestamp_corpus quality_gate=none" in output.out
    assert "status=passed quality_status=baseline_recorded" in output.out
    assert "documents=3 queries=24 answerable=16 unanswerable=8" in output.out
    assert "query_id=volcano-answerable-01 category=answerable" in output.out
    assert "/Users/" not in output.out
    assert "eruption clouds aviation" not in output.out


def test_cli_eval_retrieval_outputs_one_json_object(
    capsys: CaptureFixture[str],
) -> None:
    assert main(["eval", "retrieval", "--manifest", str(MANIFEST), "--json"]) == 0

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["evaluation"] == "retrieval"
    assert payload["benchmark_scope"] == "small_english_page_timestamp_corpus"
    assert payload["quality_gate"] == "none"
    assert payload["status"] == "passed"
    assert payload["quality_status"] == "baseline_recorded"
    assert payload["queries"] == 24
    assert payload["integrity_failures"] == []


def test_cli_eval_integrity_failure_is_exit_one_and_redacted(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    missing = tmp_path / "private" / "missing.json"

    assert main(["eval", "retrieval", "--manifest", str(missing), "--json"]) == 1

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["status"] == "failed"
    assert payload["integrity_failures"][0]["problem"] == (
        "retrieval_eval_manifest_invalid"
    )
    assert payload["integrity_failures"][0]["cause"] == "manifest file is missing"
    assert str(tmp_path) not in output.out
    assert "Traceback" not in output.out


def test_cli_eval_requires_manifest_as_usage_error(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["eval", "retrieval"])

    assert error.value.code == 2
    assert "required" in capsys.readouterr().err


def test_cli_eval_retrieval_help_documents_required_manifest(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["eval", "retrieval", "--help"])

    assert error.value.code == 0
    output = capsys.readouterr()
    normalized = " ".join(output.out.split())
    assert "--manifest" in output.out
    assert "--json" in output.out
    assert "small English" in normalized
    assert "no retrieval-quality threshold" in normalized


def test_cli_eval_rejects_explicit_global_db(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--db",
                str(tmp_path / "ignored.sqlite"),
                "eval",
                "retrieval",
                "--manifest",
                str(MANIFEST),
            ]
        )

    assert error.value.code == 2
    assert "--db is not supported" in capsys.readouterr().err


def test_cli_eval_does_not_create_current_directory_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    manifest = MANIFEST.resolve()
    monkeypatch.chdir(tmp_path)

    assert main(["eval", "retrieval", "--manifest", str(manifest)]) == 0

    assert not (tmp_path / "mke.sqlite").exists()
    capsys.readouterr()


@pytest.mark.parametrize("json_output", [False, True])
def test_cli_eval_renderer_failure_is_redacted_exit_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
    json_output: bool,
) -> None:
    def fail_renderer(*args: object, **kwargs: object) -> str:
        raise RuntimeError("Traceback SECRET /Users/mac/private")

    name = (
        "render_retrieval_json_report"
        if json_output
        else "render_retrieval_human_report"
    )
    monkeypatch.setattr(f"mke.cli.{name}", fail_renderer)
    argv = ["eval", "retrieval", "--manifest", str(MANIFEST)]
    if json_output:
        argv.append("--json")

    assert main(argv) == 1

    output = capsys.readouterr()
    assert output.err == ""
    assert "retrieval evaluation report could not be rendered" in output.out
    assert "Traceback" not in output.out
    assert "SECRET" not in output.out
    assert "/Users/" not in output.out
    if json_output:
        payload = json.loads(output.out)
        assert payload["status"] == "failed"


def test_cli_eval_distinguishes_invalid_json_from_missing_manifest(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{")

    assert main(["eval", "retrieval", "--manifest", str(invalid), "--json"]) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["integrity_failures"][0]["cause"] == "manifest is not valid JSON"
