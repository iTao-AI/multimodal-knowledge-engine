import json
from pathlib import Path

import pytest
from pytest import CaptureFixture

from mke.cli import main

MANIFEST = Path("tests/fixtures/retrieval-eval-v1.json")
NUMERIC_PROTOCOL = Path(
    "tests/fixtures/retrieval-numeric-v1/protocol-lock.json"
)


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


def test_cli_eval_numeric_outputs_passing_json(
    capsys: CaptureFixture[str],
) -> None:
    assert main(
        [
            "eval",
            "retrieval-numeric",
            "--protocol",
            str(NUMERIC_PROTOCOL),
            "--json",
        ]
    ) == 0

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["schema_version"] == "mke.retrieval_numeric_comparison.v1"
    assert payload["integrity_status"] == "passed"
    assert payload["candidate_status"] == "passed"
    assert len(payload["gates"]) == 14
    assert "/Users/" not in output.out
    assert "Traceback" not in output.out


def test_cli_eval_numeric_outputs_human_status_first(
    capsys: CaptureFixture[str],
) -> None:
    assert main(
        [
            "eval",
            "retrieval-numeric",
            "--protocol",
            str(NUMERIC_PROTOCOL),
        ]
    ) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "mke eval retrieval-numeric"
    assert "protocol=retrieval-numeric-v1" in lines[1]
    assert "candidate=numeric-grouping-v1 revision=1" in lines[1]
    assert lines[2] == "integrity_status=passed candidate_status=passed"


def test_cli_eval_numeric_missing_protocol_path_is_exit_one_and_redacted(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    missing = tmp_path / "private" / "protocol.json"

    assert main(
        [
            "eval",
            "retrieval-numeric",
            "--protocol",
            str(missing),
            "--json",
        ]
    ) == 1

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["integrity_status"] == "failed"
    assert payload["candidate_status"] == "not_recorded"
    assert str(tmp_path) not in output.out


def test_cli_eval_numeric_requires_protocol_as_usage_error(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["eval", "retrieval-numeric"])

    assert error.value.code == 2
    assert "--protocol" in capsys.readouterr().err


def test_cli_eval_numeric_rejects_db_and_candidate_override(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--db",
                str(tmp_path / "ignored.sqlite"),
                "eval",
                "retrieval-numeric",
                "--protocol",
                str(NUMERIC_PROTOCOL),
            ]
        )
    assert error.value.code == 2
    assert "--db is not supported" in capsys.readouterr().err

    with pytest.raises(SystemExit) as error:
        main(
            [
                "eval",
                "retrieval-numeric",
                "--protocol",
                str(NUMERIC_PROTOCOL),
                "--candidate",
                "current",
            ]
        )
    assert error.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_cli_eval_numeric_help_documents_comparison_boundary(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["eval", "retrieval-numeric", "--help"])

    assert error.value.code == 0
    normalized = " ".join(capsys.readouterr().out.split())
    assert "--protocol" in normalized
    assert "--json" in normalized
    assert "comparison-only" in normalized
    assert "runtime default remains current" in normalized
    assert "public rather than blind" in normalized
    assert "promotion is conditional" in normalized


@pytest.mark.parametrize("json_output", [False, True])
def test_cli_eval_numeric_renderer_failure_is_redacted(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
    json_output: bool,
) -> None:
    def fail_renderer(*args: object, **kwargs: object) -> str:
        raise RuntimeError("Traceback SECRET /Users/mac/private")

    name = (
        "render_numeric_comparison_json"
        if json_output
        else "render_numeric_comparison_human"
    )
    monkeypatch.setattr(f"mke.cli.{name}", fail_renderer)
    argv = [
        "eval",
        "retrieval-numeric",
        "--protocol",
        str(NUMERIC_PROTOCOL),
    ]
    if json_output:
        argv.append("--json")

    assert main(argv) == 1

    output = capsys.readouterr()
    assert output.err == ""
    assert "numeric comparison report could not be rendered" in output.out
    assert "Traceback" not in output.out
    assert "SECRET" not in output.out
    assert "/Users/" not in output.out
